"""Request and response models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CaseOut(BaseModel):
    id: str
    text: str


class ChatCreateRequest(BaseModel):
    case_id: str = Field(min_length=1)
    user_id: str | None = Field(
        default=None,
        description="Existing ULID from the browser's localStorage. Generated when omitted.",
    )


class ChatCreateResponse(BaseModel):
    chat_id: str
    user_id: str
    case: CaseOut


class MessageCreateRequest(BaseModel):
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class MessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    message: str
    status: Literal["success", "recite"] | None = None
    created_at: datetime


class MessageCreateResponse(BaseModel):
    status: Literal["success", "recite"]
    answer: str = Field(description="The assistant's reply.")
    new_case: CaseOut | None = Field(default=None, description="Set when a follow-up case was generated.")
    user_message: MessageOut
    message: MessageOut


class HealthResponse(BaseModel):
    status: str
