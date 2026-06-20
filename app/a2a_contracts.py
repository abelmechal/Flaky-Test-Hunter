from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.contracts import ReproPlan, ReproResult


class A2AReproRequest(BaseModel):
    type: Literal["repro_request"] = "repro_request"
    conversation_id: str = Field(min_length=1)
    reply_to: str = Field(min_length=1)
    plan: ReproPlan


class A2AReproResponse(BaseModel):
    type: Literal["repro_response"] = "repro_response"
    conversation_id: str = Field(min_length=1)
    result: ReproResult
