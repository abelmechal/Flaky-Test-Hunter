import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.a2a_reproducer_client import query_reproducer_agent
from app.workflow import FlakyTestWorkflow


async def run() -> None:
    plan = json.loads(
        (ROOT / "contracts" / "repro_plan.example.json").read_text(
            encoding="utf-8"
        )
    )
    print("Delegating reproduction to Reproducer Agent...")
    result = await query_reproducer_agent(
        plan,
        conversation_id="demo-checkout-001",
    )
    if result.get("_a2a_delegated"):
        print("Reproducer Agent returned Browserbase result.")
    else:
        print("Reproducer Agent unavailable; local fallback returned a result.")
    print()
    print(
        FlakyTestWorkflow().diagnose_from_result(
            chat_session_id="multi-agent-demo",
            result_data=result,
        )
    )


if __name__ == "__main__":
    asyncio.run(run())
