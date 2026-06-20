from datetime import datetime, timezone
import os
from uuid import uuid4

from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

from app.workflow import FlakyTestWorkflow

load_dotenv()

AGENT_SEED = os.getenv(
    "AGENT_SEED",
    "flaky-test-hunter-local-demo-seed-change-this-before-final-demo",
)
AGENT_PORT = int(os.getenv("AGENT_PORT", "8001"))

agent = Agent(
    name="flaky-test-hunter",
    seed=AGENT_SEED,
    port=AGENT_PORT,
    mailbox=True,
    publish_agent_details=True,
    readme_path="README.md",
)

protocol = Protocol(spec=chat_protocol_spec)
workflow = FlakyTestWorkflow()


@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    user_text = "".join(
        item.text for item in msg.content if isinstance(item, TextContent)
    )
    ctx.logger.info("Received chat message from %s: %s", sender, user_text)

    try:
        response = await workflow.diagnose_async(ctx, chat_session_id=sender)
    except Exception:
        ctx.logger.exception("Failed to diagnose seeded Sentry issue")
        response = (
            "I could not parse the seeded Sentry issue into a reproduction plan. "
            "Check the local fixture and contract files."
        )

    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[
                TextContent(type="text", text=response),
                EndSessionContent(type="end-session"),
            ],
        ),
    )


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info("Received acknowledgement from %s", sender)


agent.include(protocol, publish_manifest=True)


if __name__ == "__main__":
    print(f"Agent address: {agent.address}")
    agent.run()
