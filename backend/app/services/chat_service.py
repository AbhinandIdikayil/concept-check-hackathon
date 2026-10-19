"""Business logic for cases, chats and messages."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from supabase import Client
from ulid import ULID

from ..db import get_client
from ..llm import find_gap, write_followup
from ..models import CaseOut, ChatCreateResponse, MessageCreateResponse, MessageOut
from .errors import ConflictError, ForbiddenError, NotFoundError, ServiceError, UpstreamError

logger = logging.getLogger(__name__)


def _single(response: Any) -> dict[str, Any] | None:
    data = getattr(response, "data", None) or []
    return data[0] if data else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Cases
# --------------------------------------------------------------------------- #

def list_cases() -> list[CaseOut]:
    rows = get_client().table("cases").select("id,text").order("id").execute().data or []
    return [CaseOut(**row) for row in rows]


def get_case(db: Client, case_id: str) -> dict[str, Any]:
    row = _single(db.table("cases").select("id,text").eq("id", case_id).limit(1).execute())
    if row is None:
        raise NotFoundError(f"case '{case_id}' does not exist")
    return row


def get_expected_answer(db: Client, case_id: str) -> str | None:
    row = _single(db.table("answers").select("answer").eq("case_id", case_id).limit(1).execute())
    return row["answer"] if row else None


def create_case(db: Client, question: str, expected: str) -> dict[str, Any]:
    """Insert a new case plus its reference answer. Used for LLM written cases."""
    case_id = str(ULID())
    db.table("cases").insert({"id": case_id, "text": question}).execute()
    db.table("answers").insert({"case_id": case_id, "answer": expected}).execute()
    return {"id": case_id, "text": question}


# --------------------------------------------------------------------------- #
# Chats
# --------------------------------------------------------------------------- #

def create_chat(case_id: str, user_id: str | None = None) -> ChatCreateResponse:
    """Start a chat on a case.

    `user_id` is a ULID minted once per browser and kept in localStorage. It is
    reused when supplied and generated when omitted.
    """
    db = get_client()
    case = get_case(db, case_id)

    resolved_user_id = (user_id or "").strip() or str(ULID())

    # chats.id is a uuid with a gen_random_uuid() default, so let the database
    # mint it and read it back. user_id stays a ULID: it is opaque, not a key.
    chat_row = _single(
        db.table("chats")
        .insert({"user_id": resolved_user_id, "case_id": case_id})
        .execute()
    )
    chat_id = chat_row["id"]

    # Seed the case question as the first assistant message.
    db.table("messages").insert(
        {"chat_id": chat_id, "role": "assistant", "message": case["text"]}
    ).execute()

    return ChatCreateResponse(
        chat_id=chat_id,
        user_id=resolved_user_id,
        case=CaseOut(**case),
    )


def get_chat(db: Client, chat_id: str) -> dict[str, Any]:
    row = _single(db.table("chats").select("*").eq("id", chat_id).limit(1).execute())
    if row is None:
        raise NotFoundError(f"chat '{chat_id}' does not exist")
    return row


# --------------------------------------------------------------------------- #
# Messages
# --------------------------------------------------------------------------- #

def list_messages(chat_id: str) -> list[MessageOut]:
    db = get_client()
    get_chat(db, chat_id)
    rows = (
        db.table("messages")
        .select("id,role,message,status,created_at")
        .eq("chat_id", chat_id)
        .order("created_at")
        .execute()
        .data
        or []
    )
    return [MessageOut(**row) for row in rows]


def submit_answer(chat_id: str, user_id: str, message: str) -> MessageCreateResponse:
    """Grade the user's answer and reply.

    - `success`: the answer covers the reference points. Store the status, send an
      appreciation, and close the chat.
    - `recite`: the answer is shallow. Store the status, then have the model write a
      new case and ask it in the same chat.
    """
    db = get_client()
    chat = get_chat(db, chat_id)

    if chat["user_id"] != user_id:
        raise ForbiddenError("this chat belongs to another user")
    if chat["ended_at"] is not None:
        raise ConflictError("this chat has already ended")

    case = get_case(db, chat["case_id"])
    expected_answer = get_expected_answer(db, chat["case_id"])
    history = (
        db.table("messages")
        .select("role,message")
        .eq("chat_id", chat_id)
        .order("created_at")
        .execute()
        .data
        or []
    )

    user_row = _single(
        db.table("messages")
        .insert({"chat_id": chat_id, "role": "user", "message": message})
        .execute()
    )

    try:
        grade = find_gap(case["text"], expected_answer, message, history)
        verdict = grade["verdict"]

        if verdict == "success":
            db.table("messages").update({"status": "success"}).eq("id", user_row["id"]).execute()
            assistant_text = grade["feedback"]
            new_case = None
        else:
            db.table("messages").update({"status": "recite"}).eq("id", user_row["id"]).execute()
            followup = write_followup(
                question=case["text"],
                expected_answer=expected_answer,
                user_answer=message,
                feedback=grade["feedback"],
                missing_points=grade["missing_points"],
            )
            new_case = create_case(db, followup["question"], followup["expected"])
            assistant_text = f"{grade['feedback']}\n\nLet's take it further:\n\n{new_case['text']}"

        assistant_row = _single(
            db.table("messages")
            .insert({"chat_id": chat_id, "role": "assistant", "message": assistant_text})
            .execute()
        )

        if verdict == "success":
            db.table("chats").update({"ended_at": _now()}).eq("id", chat_id).execute()
    except ServiceError:
        db.table("messages").delete().eq("id", user_row["id"]).execute()
        raise
    except Exception as exc:
        # Do not leave an ungraded user message behind when grading or the
        # follow-up write fails.
        db.table("messages").delete().eq("id", user_row["id"]).execute()
        logger.exception("failed to grade answer for chat %s", chat_id)
        raise UpstreamError("the grader is unavailable, please try again") from exc

    user_row["status"] = verdict

    return MessageCreateResponse(
        status=verdict,
        answer=assistant_text,
        new_case=CaseOut(**new_case) if new_case else None,
        user_message=MessageOut(**user_row),
        message=MessageOut(**assistant_row),
    )
