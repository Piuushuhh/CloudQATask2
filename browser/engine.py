"""Execute validated test plans with bounded, recorded browser operations."""

import time
from dataclasses import dataclass, field
from pathlib import Path
from playwright.sync_api import sync_playwright
from agent.validator import TestPlan
from browser.actions import execute_action
from verification.assertions import verify


@dataclass
class StepResult:
    kind: str
    description: str
    status: str
    duration_ms: int
    error: str | None = None


@dataclass
class ExecutionResult:
    status: str
    steps: list[StepResult] = field(default_factory=list)
    screenshot: str | None = None
    error: str | None = None


class BrowserEngine:
    def __init__(self, config):
        self.config = config

    def run(self, plan: TestPlan) -> ExecutionResult:
        if len(plan.steps) > self.config.max_steps:
            return ExecutionResult("FAIL", error=f"Plan exceeds maximum of {self.config.max_steps} steps")
        results = []
        screenshot = None
        error = None
        status = "PASS"
        start = time.monotonic()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self.config.headless)
            context = browser.new_context()
            page = context.new_page()
            # Playwright's route handlers see only the original request in a
            # redirect chain. CDP's Fetch interception sees each redirect hop.
            cdp = context.new_cdp_session(page)

            def guard_navigation(event):
                request_id = event["requestId"]
                if event.get("resourceType") == "Document":
                    try:
                        self.config.validate_url(event["request"]["url"])
                    except ValueError:
                        cdp.send("Fetch.failRequest", {"requestId": request_id, "errorReason": "BlockedByClient"})
                        return
                cdp.send("Fetch.continueRequest", {"requestId": request_id})

            cdp.on("Fetch.requestPaused", guard_navigation)
            cdp.send("Fetch.enable", {"patterns": [{"urlPattern": "*", "requestStage": "Request"}]})
            page.set_default_timeout(self.config.timeout_ms)
            try:
                for i, step in enumerate(plan.steps, 1):
                    if time.monotonic() - start > self.config.execution_timeout_s:
                        raise TimeoutError("Maximum execution time exceeded")
                    t = time.monotonic()
                    try:
                        description = execute_action(page, step, self.config.timeout_ms, self.config.validate_url)
                        results.append(StepResult(f"action[{i}]", description, "PASS", int((time.monotonic()-t)*1000)))
                    except Exception as exc:
                        results.append(StepResult(f"action[{i}]", step.action.value, "FAIL", int((time.monotonic()-t)*1000), str(exc)))
                        status, error = "FAIL", f"Execution error at action {i}: {exc}"
                        break
                if status == "PASS":
                    for i, assertion in enumerate(plan.assertions, 1):
                        t = time.monotonic()
                        try:
                            description = verify(page, assertion, self.config.timeout_ms)
                            results.append(StepResult(f"assertion[{i}]", description, "PASS", int((time.monotonic()-t)*1000)))
                        except Exception as exc:
                            results.append(StepResult(f"assertion[{i}]", assertion.kind.value, "FAIL", int((time.monotonic()-t)*1000), str(exc)))
                            status, error = "FAIL", f"Assertion failure {i}: {exc}"
                            break
            finally:
                if status == "FAIL":
                    try:
                        # Failure screenshots can outlive the browser session; remove
                        # values from every form control before saving the page.
                        page.evaluate("""() => {
                            for (const control of document.querySelectorAll('input, textarea, select')) {
                                if (control instanceof HTMLSelectElement) {
                                    control.selectedIndex = -1;
                                } else {
                                    control.value = '';
                                }
                            }
                        }""")
                        directory = Path(self.config.screenshots_dir)
                        directory.mkdir(parents=True, exist_ok=True)
                        path = directory / f"failure-{int(time.time())}.png"
                        page.screenshot(path=str(path), full_page=True, timeout=5000)
                        screenshot = str(path)
                    except Exception:
                        pass
                browser.close()
        return ExecutionResult(status, results, screenshot, error)
