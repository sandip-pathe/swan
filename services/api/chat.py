"""Authenticated free-text chat; model calls are user-triggered, not per tick."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from services.agents.chat import answer_question
from services.api.auth import account_identity
from services.market.settings import ProviderError

router = APIRouter()


class ChatTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=6)


@router.post("/api/chat/messages")
async def chat_message(body: ChatRequest, request: Request, owner: UUID = Depends(account_identity)):
    try:
        return await answer_question(request, owner, body.question, [turn.model_dump() for turn in body.history])
    except (ProviderError, ValueError, TimeoutError):
        raise HTTPException(503, "CHAT_UNAVAILABLE_NO_ACTION_TAKEN") from None
