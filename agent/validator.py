"""Strict, allowlisted schema for planner output."""

from enum import StrEnum
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    assertions: Annotated[list[Assertion], Field(min_length=1, max_length=30)]
