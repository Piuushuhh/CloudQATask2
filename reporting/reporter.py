"""Persist JSON run reports and print a concise terminal summary."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def _redact_text(value):
    value = re.sub(r"(?i)\b(password|passcode|secret|token)\b(?:\s*(?:is|:|=)\s*|\s+)[^\s,;&]+", r"\1 [REDACTED]", value)
    value = re.sub(r"(?i)(https?://)[^/@\s]+@", r"\1[REDACTED]@", value)
    value = re.sub(r"(?i)([?&](?:password|passcode|secret|token|api[_-]?key)=)[^&#\s]+", r"\1[REDACTED]", value)
    return value


def _redact_tree(value):
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, list):
        return [_redact_tree(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_tree(item) for key, item in value.items()}
    return value


def _safe_plan(plan):
    if not plan:
        return None
    data = plan.model_dump(mode="json")
    for step in data["steps"]:
        # Fill values could be credentials or other sensitive inputs; never persist them.
        if step.get("action") == "fill" and step.get("value") is not None:
            step["value"] = "[REDACTED]"
    return _redact_tree(data)


def save_report(directory, instruction, plan, result, planner_error=None, plan_source="ollama"):
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    data = {"run_id": str(uuid4()), "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "FAIL" if planner_error or result is None else result.status,
            "plan_source": plan_source,
            "instruction": _redact_text(instruction),
            "plan": _safe_plan(plan),
            "steps": [x.__dict__ for x in result.steps] if result else [],
            "error_type": "planner" if planner_error else ("execution_or_assertion" if result and result.status == "FAIL" else ("not_run" if result is None else None)),
            "error": planner_error or (result.error if result else None),
            "screenshot": result.screenshot if result else None}
    data = _redact_tree(data)
    target = path / f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}.json"
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return target, data


def print_summary(data, path):
    print(f"\nResult: {data['status']} | report: {path}")
    if data["error"]:
        print(f"Error ({data['error_type']}): {data['error']}")
    for step in data["steps"]:
        print(f"  {step['status']:4} {step['kind']}: {step['description']} ({step['duration_ms']} ms)")
    if data["screenshot"]:
        print(f"Failure screenshot: {data['screenshot']}")
