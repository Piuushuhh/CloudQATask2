"""Ollama planning adapter. Model output is treated as untrusted JSON."""

import json
from ollama import Client
from pydantic import ValidationError
from agent.prompts import SYSTEM_PROMPT, user_prompt
from agent.validator import TestPlan


class PlannerError(RuntimeError):
    """Planning failed before browser execution."""


def _validation_summary(exc: ValidationError) -> str:
    """Report schema paths and error types without echoing untrusted values."""
    details = "; ".join(
        f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
        for item in exc.errors(include_input=False)
    )
    return details or "schema validation failed"


class Planner:
    def __init__(self, model: str, host: str, client=None):
        self.model = model
        self.client = client or Client(host=host, timeout=60)

    def plan(self, instruction: str, base_url: str) -> TestPlan:
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt(instruction, base_url)}]
        for attempt in range(2):
            try:
                response = self.client.chat(model=self.model, format=TestPlan.model_json_schema(), messages=messages)
            except Exception as exc:
                raise PlannerError(f"Could not get a plan from Ollama ({self.model}): {exc}") from exc
            content = response.message.content
            try:
                return TestPlan.model_validate(json.loads(content))
            except (ValidationError, json.JSONDecodeError) as exc:
                if attempt == 0:
                    messages.extend([{"role": "assistant", "content": content},
                                     {"role": "user", "content": f"The JSON was rejected by the schema ({_validation_summary(exc) if isinstance(exc, ValidationError) else 'invalid JSON'}). Return a corrected complete JSON plan matching the required schema exactly. Do not omit locator strategy keys."}])
                    continue
                detail = _validation_summary(exc) if isinstance(exc, ValidationError) else "invalid JSON syntax"
                raise PlannerError(f"Ollama returned an invalid test plan after one correction attempt: {detail}") from exc
        raise PlannerError("Ollama did not return a valid plan")
