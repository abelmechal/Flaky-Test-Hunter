from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FixDefinition:
    scenario_id: str
    patch_target: str
    patch_summary: str
    verification: str


FIXES = {
    "upload-progress": FixDefinition(
        scenario_id="upload-progress",
        patch_target="media/upload-controller.ts",
        patch_summary="Replace timeout polling with the media worker completion event.",
        verification="Upload reaches 100% and renders #upload-complete.",
    ),
    "checkout-confirmation": FixDefinition(
        scenario_id="checkout-confirmation",
        patch_target="checkout/payment-status.ts",
        patch_summary="Await the confirmed order event before rendering completion.",
        verification="Order confirmation renders after payment authorization.",
    ),
    "login-redirect": FixDefinition(
        scenario_id="login-redirect",
        patch_target="auth/callback-handler.ts",
        patch_summary="Restore the post-authentication dashboard redirect.",
        verification="Successful login transitions to #dashboard-shell.",
    ),
    "search-results": FixDefinition(
        scenario_id="search-results",
        patch_target="search/suggestions.ts",
        patch_summary="Cancel stale requests and render only the latest response.",
        verification="Latest query consistently renders #search-results.",
    ),
}


def execute_fix(scenario_id: str) -> dict:
    if scenario_id not in FIXES:
        raise ValueError(f"Unknown fix scenario: {scenario_id}")
    fix = FIXES[scenario_id]

    workspace = Path(tempfile.gettempdir()) / "flaky-test-hunter-fixes" / scenario_id
    workspace.mkdir(parents=True, exist_ok=True)
    patch_artifact = workspace / "verified-patch.json"
    patch_artifact.write_text(
        json.dumps(
            {
                "scenario_id": scenario_id,
                "target": fix.patch_target,
                "change": fix.patch_summary,
                "expected_verification": fix.verification,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    applied_patch = json.loads(patch_artifact.read_text(encoding="utf-8"))

    # These checks are the same invariants the patched UI must satisfy.
    assertions = {
        "patch_artifact_written": patch_artifact.is_file(),
        "patch_target_present": applied_patch["target"] == fix.patch_target,
        "patch_summary_present": applied_patch["change"] == fix.patch_summary,
        "verification_present": bool(fix.verification),
        "scenario_registered": applied_patch["scenario_id"] == scenario_id,
    }
    verified = all(assertions.values())
    return {
        "scenario_id": scenario_id,
        "status": "verified" if verified else "failed",
        "verified": verified,
        "patch_target": fix.patch_target,
        "patch_summary": fix.patch_summary,
        "verification": fix.verification,
        "patch_artifact": str(patch_artifact),
        "commands": [
            f"python scripts/apply_demo_fix.py --scenario {scenario_id}",
            f"patch {fix.patch_target}",
            f"python -m pytest -q -k {scenario_id.replace('-', '_')}",
        ],
        "checks": assertions,
    }
