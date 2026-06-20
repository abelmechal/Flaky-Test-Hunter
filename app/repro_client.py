from __future__ import annotations

from app.contracts import ReproPlan, ReproResult


class MockReproClient:
    """Contract-compatible stand-in for the Browserbase runner."""

    def run(self, plan: ReproPlan) -> ReproResult:
        final_target = plan.steps[-1].target
        return ReproResult(
            issue_id=plan.issue_id,
            reproduced=True,
            duration_ms=4210,
            screenshot_url="https://example.com/screenshot.png",
            error_observed=f"TimeoutError: {final_target} not found",
            notes=f"Failed while waiting for {final_target}",
        )
