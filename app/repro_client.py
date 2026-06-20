from __future__ import annotations

import os
from collections.abc import Callable
from importlib import import_module
from typing import Any

from app.contracts import ReproPlan, ReproResult


ReproRunner = Callable[[dict[str, Any]], dict[str, Any]]


def run_repro_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Run the mock reproducer using the shared dict-in/dict-out contract."""
    validated_plan = ReproPlan.model_validate(plan)
    final_target = validated_plan.steps[-1].target
    result = ReproResult(
        issue_id=validated_plan.issue_id,
        reproduced=True,
        duration_ms=4210,
        screenshot_url="https://example.com/screenshot.png",
        error_observed=f"TimeoutError: {final_target} not found",
        notes=f"Failed while waiting for {final_target}",
    )
    return result.model_dump(mode="json", exclude_none=True)


def get_repro_runner(mode: str | None = None) -> ReproRunner:
    selected_mode = (mode or os.getenv("REPRO_MODE", "mock")).lower()
    if selected_mode == "mock":
        return run_repro_plan
    if selected_mode == "browserbase":
        module = import_module("app.browserbase_runner")
        runner = getattr(module, "run_repro_plan")
        return runner
    raise ValueError(
        f"Unsupported REPRO_MODE={selected_mode!r}; expected 'mock' or 'browserbase'"
    )
