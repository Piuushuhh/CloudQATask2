"""Build Playwright locators from validated semantic targets."""

from playwright.sync_api import Locator, Page
from agent.validator import LocatorBy, Target


_CANDIDATE_DETAILS = r"""element => {
    const inMain = !!element.closest('main, [role="main"]');
    const inFooter = !!element.closest('footer, [role="contentinfo"]');
    const inNavigation = !!element.closest('nav, [role="navigation"]');
    const inHeader = !!element.closest('header, [role="banner"]');
    const cta = !!element.closest('[class*="cta" i], [id*="cta" i], [class*="hero" i], [id*="hero" i], [data-testid*="cta" i]');
    const inSearch = !!element.closest('form[role="search"], [role="search"], [class*="search" i], [id*="search" i], [class*="suggest" i], [id*="suggest" i], [role="listbox"], [role="option"]');
    const inMenu = !!element.closest('[role="menu"], [role="menubar"], [class*="mobile-menu" i], [id*="mobile-menu" i]');
    const labelledBy = (element.getAttribute('aria-labelledby') || '').split(/\s+/)
        .map(id => document.getElementById(id)).filter(Boolean)
        .map(label => label.innerText || label.textContent || '').join(' ').trim();
    const tag = element.tagName.toLowerCase();
    const type = (element.getAttribute('type') || '').toLowerCase();
    const implicitRole = tag === 'a' && element.hasAttribute('href') ? 'link' :
        (tag === 'button' ? 'button' : (tag === 'input' && ['button', 'submit', 'reset'].includes(type) ? 'button' :
        (tag === 'input' && ['checkbox', 'radio'].includes(type) ? type : element.getAttribute('role'))));
    const context = [];
    if (inMain) context.push('main');
    if (cta) context.push('cta/hero');
    if (inNavigation) context.push('navigation');
    if (inFooter) context.push('footer');
    if (inHeader) context.push('header');
    if (inSearch) context.push('search/suggestions');
    if (inMenu) context.push('menu');
    return {
        tag,
        role: element.getAttribute('role') || implicitRole || 'generic',
        accessible_name: element.getAttribute('aria-label') || labelledBy || element.getAttribute('alt') ||
            (element.innerText || element.textContent || '').trim().replace(/\s+/g, ' ') ||
            element.getAttribute('value') || element.getAttribute('title') || '',
        href: element.getAttribute('href'),
        inMain, inFooter, inNavigation, inHeader, inSearch, inMenu, cta, context
    };
}"""


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


def locate_click_target(page: Page, target: Target) -> Locator:
    """Resolve click targets semantically and disambiguate only by page context."""
    if target.by == LocatorBy.ROLE and target.value in {"link", "button"}:
        role_names = [(target.value, target.name)]
    elif target.by == LocatorBy.TEXT:
        role_names = [("link", target.value), ("button", target.value)]
    else:
        return _inspect_fallback(target, locate(page, target))

    candidates = []
    for role, name in role_names:
        matches = page.get_by_role(role, name=name, exact=name is not None)
        for candidate in matches.all():
            if candidate.is_visible():
                details = _describe_candidate(candidate, name)
                candidates.append((_relevance_score(details), candidate, details))

    if not candidates:
        return _inspect_fallback(target, locate(page, target))
    best_score = max(score for score, _, _ in candidates)
    best = [(candidate, details) for score, candidate, details in candidates if score == best_score]
    if len(best) != 1:
        descriptions = "; ".join(_candidate_summary(details) for _, details in best)
        raise RuntimeError(
            f"Ambiguous click target {target.value!r}: {len(best)} equally relevant visible candidates: {descriptions}"
        )
    return best[0][0]


def _describe_candidate(candidate: Locator, accessible_name: str | None = None) -> dict:
    details = candidate.evaluate(_CANDIDATE_DETAILS)
    if accessible_name is not None:
        # An exact get_by_role query establishes this accessible name.
        details["accessible_name"] = accessible_name
    details["visible"] = True
    return details


def _relevance_score(details: dict) -> int:
    score = (100 if details["inMain"] else 0) + (80 if details["cta"] else 0)
    if details["inSearch"]:
        score -= 300
    if details["inMenu"]:
        score -= 180
    if details["inFooter"]:
        score -= 200
    elif details["inNavigation"] and not details["inMain"]:
        score -= 120
    elif details["inHeader"] and not details["inMain"]:
        score -= 60
    return score


def _candidate_summary(details: dict) -> str:
    return (
        f"role={details['role']!r}, name={details['accessible_name']!r}, "
        f"href={details['href']!r}, visible={details['visible']}, context={details['context']}"
    )


def _inspect_fallback(target: Target, locator: Locator) -> Locator:
    visible = [candidate for candidate in locator.all() if candidate.is_visible()]
    if len(visible) > 1:
        descriptions = "; ".join(_candidate_summary(_describe_candidate(candidate)) for candidate in visible)
        raise RuntimeError(
            f"Ambiguous click target {target.value!r}: {len(visible)} visible candidates without a unique semantic match: {descriptions}"
        )
    return visible[0] if visible else locator
