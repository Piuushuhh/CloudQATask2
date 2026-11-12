"""Allowlisted Playwright browser actions."""

from agent.validator import Action, Step
from browser.locator import locate


def execute_action(page, step: Step, timeout_ms: int, validate_url) -> str:
    if step.action == Action.NAVIGATE:
        page.goto(validate_url(step.url), wait_until="domcontentloaded", timeout=step.timeout_ms or timeout_ms)
        return f"Navigated to {step.url}"
    locator = locate(page, step.target)
    timeout = step.timeout_ms or timeout_ms
    locator.wait_for(state="visible", timeout=timeout)
    count = locator.count()
    if count != 1:
        raise RuntimeError(f"Expected one matching element; found {count}")
    if step.action == Action.CLICK:
        locator.click(timeout=timeout)
    elif step.action == Action.FILL:
        locator.fill(step.value, timeout=timeout)
    elif step.action == Action.SELECT:
        locator.select_option(label=step.option, timeout=timeout)
    elif step.action == Action.CHECK:
        _check_control(locator, timeout)
    elif step.action == Action.RADIO:
        _check_control(locator, timeout)
    elif step.action == Action.WAIT:
        pass
    else:
        raise ValueError(f"Unsupported action: {step.action}")
    return f"{step.action.value} completed"


def _check_control(locator, timeout: int) -> None:
    """Resolve a label target to its associated input before checking it."""
    if locator.evaluate("element => element.tagName") == "LABEL":
        control = locator.evaluate_handle("element => element.control")
        try:
            element = control.as_element()
            if element is None:
                raise RuntimeError("Label does not have an associated form control")
            element.check(timeout=timeout)
        finally:
            control.dispose()
    else:
        locator.check(timeout=timeout)
