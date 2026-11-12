"""Independent Playwright assertion execution."""

import re
from agent.validator import Assertion, AssertionKind
from browser.locator import locate


def verify(page, assertion: Assertion, timeout_ms: int) -> str:
    if assertion.kind == AssertionKind.TITLE:
        actual = page.title()
        if assertion.expected.casefold() not in actual.casefold():
            raise AssertionError(f"Expected title to contain {assertion.expected!r}; got {actual!r}")
    elif assertion.kind == AssertionKind.URL:
        fragment = re.sub(r"(?i)^\s*(?:url\s+)?(?:contains|includes|has|matches)\s+", "", assertion.expected).strip()
        page.wait_for_function("expected => window.location.href.includes(expected)",
                               arg=fragment, timeout=timeout_ms)
    elif assertion.kind == AssertionKind.TEXT:
        page.get_by_text(assertion.expected, exact=False).first.wait_for(state="visible", timeout=timeout_ms)
    elif assertion.kind == AssertionKind.VISIBLE:
        locator = locate(page, assertion.target)
        if locator.count() != 1:
            raise AssertionError(f"Expected one matching element; found {locator.count()}")
        locator.wait_for(state="visible", timeout=timeout_ms)
    return f"{assertion.kind.value} verified: {assertion.expected}"
