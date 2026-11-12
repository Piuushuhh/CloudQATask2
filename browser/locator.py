"""Build Playwright locators from validated semantic targets."""

from playwright.sync_api import Locator, Page
from agent.validator import LocatorBy, Target


def locate(page: Page, target: Target) -> Locator:
    if target.by == LocatorBy.ROLE:
        return page.get_by_role(target.value, name=target.name, exact=target.name is not None)
    if target.by == LocatorBy.LABEL:
        return page.get_by_label(target.value, exact=True)
    if target.by == LocatorBy.PLACEHOLDER:
        return page.get_by_placeholder(target.value, exact=True)
    if target.by == LocatorBy.TEXT:
        return page.get_by_text(target.value, exact=True)
    if target.by == LocatorBy.CSS:
        return page.locator(target.value)
    raise ValueError("No supported locator strategy")
