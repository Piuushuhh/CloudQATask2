"""Strict, allowlisted schema for planner output."""

from enum import StrEnum
import re
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator


class Action(StrEnum):
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SELECT = "select"
    CHECK = "check"
    RADIO = "radio"
    WAIT = "wait"


class LocatorBy(StrEnum):
    ROLE = "role"
    LABEL = "label"
    PLACEHOLDER = "placeholder"
    TEXT = "text"
    CSS = "css"


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    by: LocatorBy
    value: str = Field(min_length=1, max_length=300)
    name: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def name_only_for_role(self):
        if self.name is not None and self.by != LocatorBy.ROLE:
            raise ValueError("name is only supported for role locators")
        return self


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Action
    url: str | None = None
    target: Target | None = None
    value: str | None = Field(default=None, max_length=2000)
    option: str | None = None
    timeout_ms: int | None = Field(default=None, ge=100, le=120000)

    @model_validator(mode="after")
    def fields_match_action(self):
        if self.action == Action.NAVIGATE:
            if not self.url or self.target or self.option:
                raise ValueError("navigate requires url and no target/option")
        elif self.action in (Action.CLICK, Action.WAIT):
            if not self.target or self.url or self.value is not None or self.option:
                raise ValueError(f"{self.action} requires only a target")
        elif self.action == Action.FILL:
            if not self.target or self.value is None or self.url or self.option:
                raise ValueError("fill requires target and value")
        elif self.action == Action.SELECT:
            if not self.target or self.option is None or self.url or self.value is not None:
                raise ValueError("select requires target and option")
        elif self.action in (Action.CHECK, Action.RADIO):
            if not self.target or self.url or self.value is not None or self.option:
                raise ValueError(f"{self.action} requires only a target")
        return self


class AssertionKind(StrEnum):
    TITLE = "title"
    TEXT = "text"
    URL = "url"
    VISIBLE = "visible"


class Assertion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: AssertionKind
    expected: str = Field(min_length=1, max_length=1000)
    target: Target | None = None

    @model_validator(mode="after")
    def visible_requires_target(self):
        if self.kind == AssertionKind.VISIBLE and not self.target:
            raise ValueError("visible assertion requires target")
        if self.kind != AssertionKind.VISIBLE and self.target:
            raise ValueError("target is only supported for visible assertions")
        return self


class TestPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    steps: Annotated[list[Step], Field(min_length=1, max_length=30)]
    assertions: Annotated[list[Assertion], Field(max_length=30)]

    @model_validator(mode="after")
    def actions_match_instruction(self, info: ValidationInfo):
        context = info.context or {}
        instruction = context.get("instruction")
        if not instruction:
            return self

        requested = {
            Action.CLICK: bool(re.search(r"\b(click|tap|press|submit|follow)\b", instruction, re.IGNORECASE)),
            Action.FILL: bool(re.search(r"\b(fill|type|enter|input)\b", instruction, re.IGNORECASE)),
            Action.SELECT: bool(re.search(r"\b(select|choose|pick)\b", instruction, re.IGNORECASE)),
            Action.CHECK: bool(re.search(r"\b(check|tick|mark)\b.{0,40}\b(checkbox|check box|box)\b|\b(checkbox|check box|box)\b.{0,40}\b(check|tick|mark)\b", instruction, re.IGNORECASE)),
            Action.RADIO: bool(re.search(r"\b(select|choose|pick|check)\b.{0,40}\bradio\b|\bradio\b.{0,40}\b(select|choose|pick|check)\b", instruction, re.IGNORECASE)),
            Action.WAIT: bool(re.search(r"\b(wait|pause)\b.{0,30}\b(for\s+)?\d+\s*(ms|milliseconds?|seconds?|minutes?)\b", instruction, re.IGNORECASE)),
        }
        for step in self.steps:
            if step.action in requested and not requested[step.action]:
                raise ValueError(f"{step.action.value} action was not explicitly requested; represent verification as an assertion")

        verification_requested = bool(re.search(
            r"\b(verify|assert|confirm|ensure|make sure|check)\b", instruction, re.IGNORECASE
        ))
        for assertion in self.assertions:
            expected_in_instruction = assertion.expected.casefold() in instruction.casefold()
            if not verification_requested or not expected_in_instruction:
                raise ValueError("assertion is not grounded in an explicit verification requirement and expected value")
            if assertion.kind == AssertionKind.TITLE and not re.search(r"\b(title|page title)\b", instruction, re.IGNORECASE):
                raise ValueError("title assertion requires an explicit title verification")
            if assertion.kind == AssertionKind.URL and not re.search(r"\b(url|address|path|route)\b", instruction, re.IGNORECASE):
                raise ValueError("URL assertion requires an explicit URL verification")
            if assertion.kind == AssertionKind.TEXT and not re.search(
                r"\b(text|content|message|says|contains|visible|displayed|shown)\b", instruction, re.IGNORECASE
            ):
                raise ValueError("text assertion requires an explicit text or content verification")
            if assertion.kind == AssertionKind.VISIBLE:
                target_text = assertion.target.name if assertion.target.by.value == "role" and assertion.target.name else assertion.target.value
                if not re.search(r"\b(visible|displayed|shown|present)\b", instruction, re.IGNORECASE):
                    raise ValueError("visibility assertion requires an explicit visibility verification")
                if target_text.casefold() not in instruction.casefold():
                    raise ValueError("visibility assertion target is not named in the instruction")
        return self
