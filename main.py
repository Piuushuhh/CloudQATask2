"""CLI entry point for the CloudQA browser testing agent."""

import argparse
import json
import sys
from pathlib import Path

from agent.planner import Planner, PlannerError
from browser.engine import BrowserEngine, ExecutionResult
from config import Config
from reporting.reporter import print_summary, save_report
from agent.validator import TestPlan


def parse_args():
    parser = argparse.ArgumentParser(description="Plan, execute, and report browser tests with local Ollama.")
    parser.add_argument("--instruction", help="Plain-English browser test instruction")
    parser.add_argument("--base-url", default="https://phptravels.com/demo/", help="Base URL supplied to the planner")
    parser.add_argument("--timeout", type=int, help="Per-action timeout in milliseconds")
    parser.add_argument("--reports-dir", type=Path, help="Directory for JSON reports")
    parser.add_argument("--headed", action="store_true", help="Show the Chromium window")
    parser.add_argument("--model", help="Ollama model (default: llama3.2:latest)")
    parser.add_argument("--smoke-phptravels", action="store_true", help="Run the safe public PHPTravels page-load smoke test")
    return parser.parse_args()


def main():
    args = parse_args()
    instruction = args.instruction
    smoke_mode = args.smoke_phptravels
    if smoke_mode:
        instruction = "Open https://phptravels.com/demo/ and verify the page URL contains /demo."
    if not instruction:
        try:
            instruction = input("Describe the browser test to run: ").strip()
        except EOFError:
            instruction = ""
    if not instruction:
        print("Please provide --instruction or type an instruction.", file=sys.stderr)
        return 2

    config = Config()
    config.headless = not args.headed
    if args.timeout:
        config.timeout_ms = args.timeout
    if args.reports_dir:
        config.reports_dir = args.reports_dir
    if args.model:
        config.model = args.model
    plan = None
    result = None
    planner_error = None
    print("Preparing the deterministic public PHPTravels smoke plan..." if smoke_mode else f"Planning with Ollama ({config.model})...")
    try:
        if smoke_mode:
            plan = TestPlan.model_validate({"name": "PHPTravels public demo URL smoke", "steps": [
                {"action": "navigate", "url": "https://phptravels.com/demo/"}],
                "assertions": [{"kind": "url", "expected": "/demo"}]})
        else:
            plan = Planner(config.model, config.ollama_host).plan(instruction, args.base_url)
        if len(plan.steps) > config.max_steps:
            raise PlannerError(f"Plan exceeds configured maximum of {config.max_steps} steps")
        print(f"Plan ready: {plan.name} ({len(plan.steps)} actions, {len(plan.assertions)} assertions)")
        print("Executing in Chromium...")
        result = BrowserEngine(config).run(plan)
    except PlannerError as exc:
        planner_error = str(exc)
    except Exception as exc:
        if plan is not None:
            result = ExecutionResult("FAIL", error=f"Browser setup/execution error: {exc}")
        else:
            planner_error = f"Unexpected planning error: {exc}"
    path, data = save_report(config.reports_dir, instruction, plan, result, planner_error,
                             "deterministic_phptravels_smoke" if smoke_mode else "ollama")
    print_summary(data, path)
    return 0 if data["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
