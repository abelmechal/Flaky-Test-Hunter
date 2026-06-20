from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from uagents import Context
from uagents.query import send_sync_message
from uagents.resolver import RulesBasedResolver
from uagents_core.identity import Identity
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent

from app.a2a_contracts import A2AReproRequest, A2AReproResponse
from app.contracts import ReproPlan
from app.repro_client import run_repro_plan


def build_repro_request(
    plan: dict[str, Any],
    *,
    conversation_id: str,
    reply_to: str,
) -> dict[str, Any]:
    return A2AReproRequest(
        conversation_id=conversation_id,
        reply_to=reply_to,
        plan=ReproPlan.model_validate(plan),
    ).model_dump(mode="json", exclude_none=True)


def parse_repro_response(
    payload: dict[str, Any],
    *,
    conversation_id: str,
) -> dict[str, Any]:
    response = A2AReproResponse.model_validate(payload)
    if response.conversation_id != conversation_id:
        raise ValueError("Reproducer response conversation_id does not match request")
    return response.result.model_dump(mode="json", exclude_none=True)


def _chat_message(payload: dict[str, Any]) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[
            TextContent(type="text", text=json.dumps(payload, separators=(",", ":")))
        ],
    )


def _extract_json(message: ChatMessage) -> dict[str, Any]:
    text = "".join(
        item.text for item in message.content if isinstance(item, TextContent)
    )
    if not text:
        raise ValueError("Reproducer response did not contain JSON text")
    return json.loads(text)


def _fallback(plan: dict[str, Any], reason: str) -> dict[str, Any]:
    result = run_repro_plan(plan)
    result["_a2a_fallback"] = True
    result["_a2a_error"] = reason
    return result


async def run_repro_plan_via_agent(
    ctx: Context,
    plan: dict[str, Any],
    *,
    conversation_id: str,
) -> dict[str, Any]:
    address = os.getenv("REPRODUCER_AGENT_ADDRESS", "").strip()
    if not address:
        return _fallback(plan, "Missing REPRODUCER_AGENT_ADDRESS")

    request = build_repro_request(
        plan,
        conversation_id=conversation_id,
        reply_to=ctx.agent.address,
    )
    timeout = int(os.getenv("A2A_REPRO_TIMEOUT_SECONDS", "30"))
    try:
        response, _status = await ctx.send_and_receive(
            address,
            _chat_message(request),
            response_type=ChatMessage,
            timeout=timeout,
        )
        if not isinstance(response, ChatMessage):
            return _fallback(plan, "Reproducer Agent timed out or returned no response")
        result = parse_repro_response(
            _extract_json(response),
            conversation_id=conversation_id,
        )
        if str(result.get("error_observed") or "").startswith(
            "BrowserbaseRunnerError"
        ):
            return _fallback(plan, str(result["error_observed"]))
        result["_a2a_delegated"] = True
        return result
    except Exception as exc:
        return _fallback(plan, f"{type(exc).__name__}: {exc}")


async def query_reproducer_agent(
    plan: dict[str, Any],
    *,
    conversation_id: str,
) -> dict[str, Any]:
    """Standalone query path used by the multi-agent smoke script."""
    address = os.getenv("REPRODUCER_AGENT_ADDRESS", "").strip()
    if not address:
        return _fallback(plan, "Missing REPRODUCER_AGENT_ADDRESS")
    request = build_repro_request(
        plan,
        conversation_id=conversation_id,
        reply_to="standalone-demo-client",
    )
    timeout = int(os.getenv("A2A_REPRO_TIMEOUT_SECONDS", "30"))
    try:
        sender = Identity.from_seed(
            os.getenv(
                "A2A_DEMO_CLIENT_SEED",
                "flaky-test-hunter-a2a-demo-client-seed",
            ),
            0,
        )
        endpoint = os.getenv("REPRODUCER_AGENT_ENDPOINT", "").strip()
        resolver = (
            RulesBasedResolver({address: endpoint})
            if endpoint
            else None
        )
        message = await send_sync_message(
            address,
            _chat_message(request),
            response_type=ChatMessage,
            sender=sender,
            resolver=resolver,
            timeout=timeout,
        )
        if not isinstance(message, ChatMessage):
            return _fallback(plan, "Reproducer Agent query returned no ChatMessage")
        result = parse_repro_response(
            _extract_json(message),
            conversation_id=conversation_id,
        )
        if str(result.get("error_observed") or "").startswith(
            "BrowserbaseRunnerError"
        ):
            return _fallback(plan, str(result["error_observed"]))
        result["_a2a_delegated"] = True
        return result
    except Exception as exc:
        return _fallback(plan, f"{type(exc).__name__}: {exc}")
