from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.contracts import ReproPlan, ReproResult


DEFAULT_TIMEOUT_MS = int(os.getenv("BROWSERBASE_STEP_TIMEOUT_MS", "8000"))
SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "artifacts/screenshots"))


def _safe_issue_id(issue_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", issue_id or "unknown-issue")


def _session_url(session_id: str | None) -> str | None:
    if not session_id:
        return None
    return f"https://browserbase.com/sessions/{session_id}"


def _build_result(
    *,
    plan: dict[str, Any],
    reproduced: bool,
    started_at: float,
    screenshot_url: str | None,
    error_observed: str | None,
    notes: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "issue_id": plan.get("issue_id", "unknown-issue"),
        "reproduced": reproduced,
        "duration_ms": int((time.perf_counter() - started_at) * 1000),
        "screenshot_url": screenshot_url or _session_url(session_id),
        "error_observed": error_observed,
        "notes": notes,
    }
    if session_id:
        result["browserbase_session_id"] = session_id
        result["browserbase_session_url"] = _session_url(session_id)
    return result


def _take_screenshot(page: Any, issue_id: str) -> str:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{_safe_issue_id(issue_id)}-{uuid4().hex[:8]}.png"
    path = SCREENSHOT_DIR / filename
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def _execute_step(page: Any, step: dict[str, Any]) -> None:
    action = step.get("action")
    target = step.get("target")
    value = step.get("value")
    timeout_ms = int(step.get("timeout_ms") or DEFAULT_TIMEOUT_MS)

    if action == "goto":
        if not target:
            raise ValueError("goto step requires target")
        page.goto(target, wait_until="domcontentloaded", timeout=timeout_ms)
        return
    if action == "fill":
        if not target:
            raise ValueError("fill step requires target")
        page.locator(target).fill(value or "", timeout=timeout_ms)
        return
    if action == "click":
        if not target:
            raise ValueError("click step requires target")
        page.locator(target).click(timeout=timeout_ms)
        return
    if action == "wait_for_selector":
        if not target:
            raise ValueError("wait_for_selector step requires target")
        page.wait_for_selector(
            target,
            state=step.get("state", "visible"),
            timeout=timeout_ms,
        )
        return
    raise ValueError(f"Unsupported repro action: {action}")


def run_repro_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Execute the shared Repro Plan contract in a Browserbase session."""
    started_at = time.perf_counter()
    session_id: str | None = None

    try:
        validated_plan = ReproPlan.model_validate(plan)
    except Exception as exc:
        return _build_result(
            plan=plan,
            reproduced=False,
            started_at=started_at,
            screenshot_url=None,
            error_observed=f"InvalidReproPlan: {exc}",
            notes="Browserbase runner could not validate the repro plan.",
        )

    plan_data = validated_plan.model_dump(mode="json", exclude_none=True)
    steps = plan_data["steps"]
    api_key = os.getenv("BROWSERBASE_API_KEY")
    if not api_key:
        return _build_result(
            plan=plan_data,
            reproduced=False,
            started_at=started_at,
            screenshot_url=None,
            error_observed="BrowserbaseRunnerError: Missing BROWSERBASE_API_KEY",
            notes="Browserbase mode was requested, but BROWSERBASE_API_KEY is not set.",
        )

    try:
        from browserbase import Browserbase
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright

        browserbase = Browserbase(api_key=api_key, max_retries=0)
        create_kwargs: dict[str, Any] = {
            "api_timeout": int(
                os.getenv("BROWSERBASE_SESSION_TIMEOUT_SECONDS", "300")
            )
        }
        project_id = os.getenv("BROWSERBASE_PROJECT_ID")
        if project_id:
            create_kwargs["project_id"] = project_id

        session = browserbase.sessions.create(**create_kwargs)
        session_id = getattr(session, "id", None)
        connect_url = getattr(session, "connect_url", None)
        if not connect_url:
            raise RuntimeError("Browserbase session did not return connect_url")

        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(connect_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(DEFAULT_TIMEOUT_MS)
            failed_step_index: int | None = None
            error_observed: str | None = None

            try:
                for index, step in enumerate(steps, start=1):
                    _execute_step(page, step)
                screenshot_url = _take_screenshot(page, validated_plan.issue_id)
                browser.close()
                return _build_result(
                    plan=plan_data,
                    reproduced=False,
                    started_at=started_at,
                    screenshot_url=screenshot_url,
                    error_observed=None,
                    notes=(
                        "Browserbase completed all repro steps successfully. "
                        "The expected failure did not reproduce in this live run."
                    ),
                    session_id=session_id,
                )
            except PlaywrightTimeoutError as exc:
                failed_step_index = index
                error_observed = f"TimeoutError: {str(exc).splitlines()[0]}"
            except Exception as exc:
                failed_step_index = index
                error_observed = f"{type(exc).__name__}: {str(exc).splitlines()[0]}"

            try:
                screenshot_url = _take_screenshot(page, validated_plan.issue_id)
            except Exception:
                screenshot_url = _session_url(session_id)
            try:
                browser.close()
            except Exception:
                pass

            return _build_result(
                plan=plan_data,
                reproduced=True,
                started_at=started_at,
                screenshot_url=screenshot_url,
                error_observed=error_observed,
                notes=(
                    f"Browserbase reproduced a failure at step "
                    f"{failed_step_index} of {len(steps)}."
                ),
                session_id=session_id,
            )
    except Exception as exc:
        return _build_result(
            plan=plan_data,
            reproduced=False,
            started_at=started_at,
            screenshot_url=_session_url(session_id),
            error_observed=(
                f"BrowserbaseRunnerError: {type(exc).__name__}: {str(exc)}"
            ),
            notes=(
                "Browserbase runner failed before completing verification. "
                "The agent should use mock fallback or Redis history."
            ),
            session_id=session_id,
        )
