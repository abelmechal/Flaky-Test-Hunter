from __future__ import annotations

import os
from collections.abc import Callable
from importlib import import_module
from typing import Any

from app.contracts import ReproPlan, ReproResult


ReproRunner = Callable[[dict[str, Any]], dict[str, Any]]


def run_repro_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Run the configured reproducer with automatic Browserbase fallback."""
    selected_mode = os.getenv("REPRO_MODE", "mock").lower()
    if selected_mode == "browserbase":
        try:
            browserbase_runner = get_repro_runner("browserbase")
            result = browserbase_runner(plan)
            error = str(result.get("error_observed") or "")
            if not error.startswith("BrowserbaseRunnerError"):
                return result
            if os.getenv("REPRO_FALLBACK_TO_MOCK", "true").lower() != "true":
                return result
            fallback = run_mock_repro_plan(plan)
            fallback["notes"] = (
                "Browserbase failed, so mock fallback was used. "
                + str(fallback.get("notes") or "")
            )
            fallback["browserbase_error"] = error
            return fallback
        except Exception as exc:
            if os.getenv("REPRO_FALLBACK_TO_MOCK", "true").lower() != "true":
                raise
            fallback = run_mock_repro_plan(plan)
            fallback["notes"] = (
                "Browserbase import/runtime failed, so mock fallback was used. "
                + str(fallback.get("notes") or "")
            )
            fallback["browserbase_error"] = f"{type(exc).__name__}: {exc}"
            return fallback
    if selected_mode != "mock":
        raise ValueError(
            f"Unsupported REPRO_MODE={selected_mode!r}; "
            "expected 'mock' or 'browserbase'"
        )
    return run_mock_repro_plan(plan)


def run_mock_repro_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Run the deterministic mock using the shared dict contract."""
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
        return run_mock_repro_plan
    if selected_mode == "browserbase":
        module = import_module("app.browserbase_runner")
        runner = getattr(module, "run_repro_plan")
        return runner
    raise ValueError(
        f"Unsupported REPRO_MODE={selected_mode!r}; expected 'mock' or 'browserbase'"
    )
