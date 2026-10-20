"""Request and response models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CaseOut(BaseModel):
    id: str
    text: str


class ChatOut(BaseModel):
    """One row of the chat listing."""

    chat_id: str
    text: str = Field(description="The text of the case this chat was opened on.")


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
    status: Literal["passed", "failed"] | None = None
    created_at: datetime


class MessageCreateResponse(BaseModel):
    """One step of the session.

    A session is two learner turns against the chat's own case. `status` is null
    on the first and set on the second, the only turn the code grades; `ended`
    becomes true along with it.
    """

    status: Literal["passed", "failed"] | None = Field(
        default=None,
        description="Set only on the final answer, the only turn the code grades.",
    )
    reply: str = Field(description="The assistant's reply for this step.")
    ended: bool = Field(default=False, description="True once the session has closed.")
    gap_sentence: str | None = Field(
        default=None,
        description="Verbatim sentence from the learner's own answer where reasoning stopped.",
    )
    correct_answer: str | None = Field(
        default=None,
        description="The case's reference answer, shown once the session closes.",
    )
    new_case: CaseOut | None = Field(
        default=None,
        description="The case offered to play next, once this one is closed.",
    )
    user_message: MessageOut
    message: MessageOut


class HealthResponse(BaseModel):
    status: str
