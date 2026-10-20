"""Chat endpoints."""

from uuid import UUID  # noqa: I001

from fastapi import APIRouter, Query, status

from ..validators import (
    ChatCreateRequest,
    ChatCreateResponse,
    ChatOut,
    MessageCreateRequest,
    MessageCreateResponse,
    MessageOut,
)
from ..services import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/create", response_model=ChatCreateResponse, status_code=status.HTTP_201_CREATED)
def create_chat(payload: ChatCreateRequest) -> ChatCreateResponse:
    """Select a case and open a chat on it."""
    return chat_service.create_chat(payload.case_id, payload.user_id)


@router.get("/all", response_model=list[ChatOut])
def list_all_chats(
    user_id: str = Query(
        min_length=1, description="Owner ULID; only this user's chats are returned."
    ),
) -> list[ChatOut]:
    """Every chat belonging to one user, newest first, with the text of its case."""
    return chat_service.list_chats(user_id)


# chat_id is typed as UUID because chats.id is a uuid column: a malformed id
# would otherwise reach Postgres and fail a cast instead of being rejected here.
@router.post(
    "/{chat_id}/message/create",
    response_model=MessageCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message(chat_id: UUID, payload: MessageCreateRequest) -> MessageCreateResponse:
    """Send the user's answer and get the graded reply."""
    return chat_service.submit_answer(str(chat_id), payload.user_id, payload.message)


@router.get("/{chat_id}/message/all", response_model=list[MessageOut])
def list_messages(chat_id: UUID) -> list[MessageOut]:
    return chat_service.list_messages(str(chat_id))
