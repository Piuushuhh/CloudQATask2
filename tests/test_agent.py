import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from playwright.sync_api import Page

from pydantic import ValidationError
from agent.planner import Planner, PlannerError
from agent.validator import TestPlan
from config import Config
from reporting.reporter import save_report
from browser.engine import BrowserEngine


PLAN = {"name":"fixture form", "steps":[{"action":"navigate", "url":"file:///fixture.html"}],
        "assertions":[{"kind":"title", "expected":"Example Form"}]}


class AgentTests(unittest.TestCase):
    def test_valid_plan_and_reject_unknown_action(self):
        plan = TestPlan.model_validate(PLAN)
        self.assertEqual(plan.steps[0].action.value, "navigate")
        bad = {**PLAN, "steps":[{"action":"execute_python", "value":"print(1)"}]}
        with self.assertRaises(ValidationError): TestPlan.model_validate(bad)

    def test_reject_invalid_locator_strategy(self):
        with self.assertRaises(ValidationError):
            TestPlan.model_validate({"name":"x", "steps":[{"action":"click", "target":{"by":"xpath", "value":"//button"}}], "assertions":[{"kind":"text", "expected":"ok"}]})
        with self.assertRaises(ValidationError):
            TestPlan.model_validate({"name":"x", "steps":[{"action":"click", "target":{"by":"text", "value":"Save", "name":"Save"}}], "assertions":[{"kind":"text", "expected":"ok"}]})

    def test_malformed_llm_response(self):
        client = Mock(); client.chat.return_value = Mock(message=Mock(content="not json"))
        with self.assertRaises(PlannerError): Planner("test", "http://localhost", client).plan("x", "http://localhost")

    def test_planner_corrects_one_invalid_response(self):
        client = Mock()
        client.chat.side_effect = [Mock(message=Mock(content="{}")), Mock(message=Mock(content=json.dumps(PLAN)))]
        plan = Planner("test", "http://localhost", client).plan("x", "http://localhost")
        self.assertEqual(plan.name, "fixture form")
        self.assertEqual(client.chat.call_count, 2)

    def test_ollama_unavailable(self):
        client = Mock(); client.chat.side_effect = ConnectionError("offline")
        with self.assertRaisesRegex(PlannerError, "Could not get a plan"): Planner("test", "http://localhost", client).plan("x", "http://localhost")

    def test_url_allowlist(self):
        config = Config()
        self.assertEqual(config.validate_url("http://localhost/test"), "http://localhost/test")
        with self.assertRaises(ValueError): config.validate_url("https://evil.example/")
        with self.assertRaises(ValueError): config.validate_url("javascript:alert(1)")
        with self.assertRaises(ValueError): config.validate_url("https://user:password@phptravels.com/demo/")

    def test_report_redacts_fill_values_and_instruction_passwords(self):
        plan = TestPlan.model_validate({"name":"Credential form", "steps":[
            {"action":"navigate", "url":"http://localhost/login?token=url-secret"},
            {"action":"fill", "target":{"by":"label", "value":"Password"}, "value":"do-not-log-this"}],
            "assertions":[{"kind":"url", "expected":"/login"}]})
        with tempfile.TemporaryDirectory() as temp:
            path, data = save_report(temp, "Enter password do-not-log-this at https://phptravels.com/?token=do-not-log-this", plan, None)
            serialized = path.read_text(encoding="utf-8")
            self.assertNotIn("do-not-log-this", serialized)
            self.assertNotIn("url-secret", serialized)
            self.assertEqual(data["plan"]["steps"][1]["value"], "[REDACTED]")

    def test_browser_fixture_actions_assertions_and_screenshot(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            config = Config(); config.allowed_domains = ("localhost", "127.0.0.1", "")
            config.screenshots_dir = Path(temp); config.timeout_ms = 3000
            # file URLs are disabled by policy; serve the fixture on loopback.
            from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
            import threading
            blocked_requests = []
            class Handler(SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(root / "fixtures"), **kwargs)
                def log_message(self, *args): pass
                def do_GET(self):
                    if self.path == "/redirect":
                        self.send_response(302); self.send_header("Location", f"http://localhost:{server.server_port}/not-allowed"); self.end_headers()
                    elif self.path == "/not-allowed":
                        blocked_requests.append(self.path)
                        self.send_response(200); self.end_headers()
                    else:
                        super().do_GET()
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/form.html"
                config.validate_url(url)
                plan = TestPlan.model_validate({"name":"Fill and click", "steps":[
                    {"action":"navigate", "url":url},
                    {"action":"fill", "target":{"by":"label", "value":"Full name"}, "value":"Asha"},
                    {"action":"click", "target":{"by":"role", "value":"button", "name":"Send"}}],
                    "assertions":[{"kind":"text", "expected":"Thanks, Asha"}, {"kind":"visible", "expected":"yes", "target":{"by":"css", "value":"#result"}}]})
                result = BrowserEngine(config).run(plan)
                self.assertEqual(result.status, "PASS", result.error)

                # Text targets resolve to labels; check/radio must act on the
                # associated inputs, including explicit and wrapping labels.
                selection_plan = TestPlan.model_validate({"name":"Select controls", "steps":[
                    {"action":"navigate", "url":url},
                    {"action":"check", "target":{"by":"text", "value":"I agree"}},
                    {"action":"radio", "target":{"by":"text", "value":"Choice B"}}],
                    "assertions":[{"kind":"title", "expected":"Example Form"}]})
                selected = BrowserEngine(config).run(selection_plan)
                self.assertEqual(selected.status, "PASS", selected.error)

                # Missing element creates a failure report and screenshot when available.
                fail_plan = TestPlan.model_validate({"name":"Missing", "steps":[{"action":"navigate", "url":f"http://127.0.0.1:{server.server_port}/missing.html"}, {"action":"click", "target":{"by":"text", "value":"Absent"}}], "assertions":[{"kind":"title", "expected":"Missing"}]})
                failed = BrowserEngine(config).run(fail_plan)
                self.assertEqual(failed.status, "FAIL")
                self.assertTrue(failed.screenshot and Path(failed.screenshot).exists())

                privacy_plan = TestPlan.model_validate({"name":"Private screenshot", "steps":[
                    {"action":"navigate", "url":url},
                    {"action":"fill", "target":{"by":"label", "value":"Password"}, "value":"private-value"},
                    {"action":"click", "target":{"by":"text", "value":"Absent"}}],
                    "assertions":[{"kind":"title", "expected":"Example Form"}]})
                screenshot_values = []
                original_screenshot = Page.screenshot
                def capture_after_mask(page, *args, **kwargs):
                    screenshot_values.append(page.locator("#password").input_value())
                    return original_screenshot(page, *args, **kwargs)
                with unittest.mock.patch.object(Page, "screenshot", capture_after_mask):
                    private_result = BrowserEngine(config).run(privacy_plan)
                self.assertEqual(private_result.status, "FAIL")
                self.assertTrue(private_result.screenshot and Path(private_result.screenshot).exists())
                self.assertEqual(screenshot_values, [""])
                path, data = save_report(temp, "test", fail_plan, failed)
                self.assertTrue(path.exists()); self.assertEqual(json.loads(path.read_text())["status"], "FAIL")

                ambiguous = TestPlan.model_validate({"name":"Ambiguous", "steps":[
                    {"action":"navigate", "url":f"http://127.0.0.1:{server.server_port}/changed_selectors.html"},
                    {"action":"click", "target":{"by":"text", "value":"Save"}}],
                    "assertions":[{"kind":"title", "expected":"Changed selectors"}]})
                ambiguous_result = BrowserEngine(config).run(ambiguous)
                self.assertEqual(ambiguous_result.status, "FAIL")
                self.assertIn("strict mode violation", ambiguous_result.error)

                redirect = TestPlan.model_validate({"name":"Blocked redirect", "steps":[
                    {"action":"navigate", "url":f"http://127.0.0.1:{server.server_port}/redirect"}],
                    "assertions":[{"kind":"url", "expected":"/redirect"}]})
                config.allowed_domains = ("127.0.0.1",)
                redirect_result = BrowserEngine(config).run(redirect)
                self.assertEqual(redirect_result.status, "FAIL")
                self.assertEqual(blocked_requests, [])
            finally:
                server.shutdown(); server.server_close()


if __name__ == "__main__": unittest.main()
