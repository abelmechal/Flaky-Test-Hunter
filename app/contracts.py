from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ReproStep(BaseModel):
    action: Literal["goto", "fill", "click", "wait_for_selector"]
    target: str = Field(min_length=1)
    value: str | None = None
    timeout_ms: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_action_fields(self) -> "ReproStep":
        if self.action == "fill" and self.value is None:
            raise ValueError("fill steps require value")
        return self


class ReproPlan(BaseModel):
    issue_id: str = Field(min_length=1)
    test_name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    steps: list[ReproStep] = Field(min_length=1)
    expected_failure: str = Field(min_length=1)
    run_count_recent: int = Field(ge=0)
    first_seen: str = Field(min_length=1)


class ReproResult(BaseModel):
    issue_id: str = Field(min_length=1)
    reproduced: bool
    duration_ms: int = Field(ge=0)
    screenshot_url: str | None = None
    error_observed: str | None = None
    notes: str | None = None
