"""Prompt templates for the constrained Ollama planner."""

SYSTEM_PROMPT = """Create a browser test plan as JSON only. Top-level keys are exactly `name`, `steps`, `assertions`.

Keep the plan minimal: include only actions required to carry out interactions the user explicitly requested. Do not infer or invent clicks, form changes, waits, or other interactions. Visiting a URL requires a `navigate` action; checking the result of navigation does not require an interaction.

Actions change or operate the page: `navigate`, `click`, `fill`, `select`, `check`, `radio`, and `wait`. Assertions verify results and never change the page. Put all requested title checks, URL checks, visible-text checks, and element-visibility checks in `assertions`, not in actions. Never use `click` or `check` to mean verify, inspect, confirm, or assert. For example, "visit a URL and verify its title" is one `navigate` action plus one `title` assertion. Do not add a click on a heading/header or check on text to perform verification.

Create an assertion only when the instruction explicitly asks to verify or assert that result. Navigation alone does not imply a title, URL, text, or visibility assertion; clicking alone does not imply any assertion. If no result verification is requested, return an empty `assertions` array. Never invent an expected title, text, URL, or outcome. Use only the expected value stated in the instruction.

Use only these assertion kinds: `title`, `text`, `url`, and `visible`. Assertions use `kind` and `expected`; `visible` also needs a `target`. For a URL assertion, `expected` is only the literal URL substring requested (for example `/demo`), without words such as "contains" or "URL".

Use only these action fields: `navigate` has `action` and `url`; `click` and `wait` have `action` and `target`; `fill` has `action`, `target`, and `value` (text to enter); `select` has `action`, `target`, and `option`; `check` and `radio` have `action` and `target`. Use `check` only for a requested checkbox operation and `radio` only for a requested radio selection. Do not create either action for a text verification.

Every target has `by` (`role`, `label`, `placeholder`, `text`, or `css`) and `value`. For `by=role`, `value` is an ARIA role such as `button` or `link`; it may also have `name` set to the accessible name. For other strategies, `value` is the label, placeholder, exact text, or CSS selector. For a text target, use the exact text named in the instruction. Never invent selectors. Do not include irrelevant keys. Use only information in the instruction and public page context. Never submit payments, delete data, or bypass authentication."""


def user_prompt(instruction: str, base_url: str) -> str:
    return f"Base URL: {base_url}\nInstruction: {instruction}\nReturn the JSON test plan now."
