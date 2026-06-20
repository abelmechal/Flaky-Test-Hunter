from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

from app.a2a_contracts import A2AReproRequest, A2AReproResponse
from app.browserbase_runner import run_repro_plan

load_dotenv()

agent = Agent(
    name="flaky-test-reproducer",
    seed=os.getenv(
        "REPRODUCER_AGENT_SEED",
        "flaky-test-reproducer-local-seed-change-before-demo",
    ),
    port=int(os.getenv("REPRODUCER_AGENT_PORT", "8002")),
    endpoint=os.getenv(
        "REPRODUCER_AGENT_ENDPOINT",
        "http://127.0.0.1:8002/submit",
    ),
    mailbox=os.getenv("REPRODUCER_AGENT_MAILBOX", "false").lower() == "true",
    publish_agent_details=True,
)
protocol = Protocol(spec=chat_protocol_spec)


def _text(message: ChatMessage) -> str:
    return "".join(
        item.text for item in message.content if isinstance(item, TextContent)
    )


@protocol.on_message(ChatMessage)
async def handle_repro_request(ctx: Context, sender: str, msg: ChatMessage):
    try:
        request = A2AReproRequest.model_validate_json(_text(msg))
        ctx.logger.info(
            "Received repro_request for %s; running Browserbase",
            request.plan.issue_id,
        )
        result = await asyncio.to_thread(
            run_repro_plan,
            request.plan.model_dump(mode="json", exclude_none=True),
        )
        response = A2AReproResponse(
            conversation_id=request.conversation_id,
            result=result,
        )
        response_text = response.model_dump_json(exclude_none=True)
        ctx.logger.info("Returning repro_response for %s", request.plan.issue_id)
    except Exception as exc:
        ctx.logger.exception("Invalid repro request")
        response_text = json.dumps(
            {
                "type": "repro_error",
                "error": f"{type(exc).__name__}: {exc}",
            }
        )

    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=response_text)],
        ),
    )


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info("Received acknowledgement from %s", sender)


agent.include(protocol, publish_manifest=True)


if __name__ == "__main__":
    print("Reproducer Agent online")
    print(f"Agent address: {agent.address}")
    agent.run()
