"""Business logic for cases, chats and messages."""

from __future__ import annotations  # noqa: I001

import logging
import re
from datetime import datetime, timezone
from typing import Any

from supabase import Client
from ulid import ULID

from ..db import get_client
from ..llm import find_gap_and_followup
from ..validators import CaseOut, ChatCreateResponse, ChatOut, MessageCreateResponse, MessageOut
from .errors import ConflictError, ForbiddenError, NotFoundError, ServiceError, UpstreamError

logger = logging.getLogger(__name__)

# A session is two learner turns against the one case the chat belongs to.
FIRST_TRY = 0
FINAL = 1

# Pass/fail tuning, pure code and nothing else.
#
# A key point counts as covered when at least POINT_COVERAGE of its significant
# words appear anywhere in the learner's answers. The answer passes when at
# least PASS_THRESHOLD of the case's points are covered. Case 1 derives three
# points, so passing it needs two of them.
PASS_THRESHOLD = 0.6
POINT_COVERAGE = 0.5

_STOPWORDS = frozenset(
    """a about above after again against all also am an and any are as at be because been
    before being below between both but by can cannot could did do does doing down during
    each few for from further had has have having he her here hers him his how i if in into
    is it its itself just me more most my no nor not now of off on once only or other our
    out over own same she should so some such than that the their them then there these they
    this those through to too under until up very was we were what when where which while
    who whom why will with would you your""".split()
)

# The reference answer is written one point per sentence. Clauses joined by a
# colon or semicolon are separate points too, so a compound sentence does not
# collapse into one all-or-nothing point.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CLAUSE_SPLIT = re.compile(r"[;:]\s+")


def _single(response: Any) -> dict[str, Any] | None:
    data = getattr(response, "data", None) or []
    return data[0] if data else None


def _require(response: Any, what: str) -> dict[str, Any]:
    """Like `_single`, but a missing row is an error rather than a None.

    An insert that comes back empty would otherwise surface later as a confusing
    TypeError or ValidationError.
    """
    row = _single(response)
    if row is None:
        raise UpstreamError(f"the database did not return the {what}")
    return row


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()  # noqa: UP017


# --------------------------------------------------------------------------- #
# Grading: plain code, no model
# --------------------------------------------------------------------------- #

def _keywords(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if len(word) > 1 and word not in _STOPWORDS
    }


def derive_points(reference: str) -> list[str]:
    """Split a reference answer into the points a learner has to cover.

    One point per sentence, and per `:` or `;` clause. Fragments with no
    significant words are dropped: they could never be covered, so keeping them
    would permanently lower the best achievable score.
    """
    parts: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(reference):
        parts.extend(_CLAUSE_SPLIT.split(sentence))
    return [part.strip() for part in parts if _keywords(part)]


def _point_covered(point: str, answer_words: set[str]) -> bool:
    point_words = _keywords(point)
    if not point_words:
        return False
    return len(point_words & answer_words) / len(point_words) >= POINT_COVERAGE


def grade_answer(answer: str, key_points: list[str]) -> str:
    """Decide "passed" or "failed" by comparing the answer to the key points.

    Deterministic and local: the model is never asked whether the learner
    understood, and never contributes to this decision.
    """
    if not key_points:
        logger.warning("case has no key points, every answer will fail")
        return "failed"

    answer_words = _keywords(answer)
    covered = sum(1 for point in key_points if _point_covered(point, answer_words))
    return "passed" if covered / len(key_points) >= PASS_THRESHOLD else "failed"


# --------------------------------------------------------------------------- #
# Cases
# --------------------------------------------------------------------------- #

def list_cases() -> list[CaseOut]:
    rows = get_client().table("cases").select("id,text").order("id").execute().data or []
    return [CaseOut.model_validate(row) for row in rows]


def get_case(db: Client, case_id: str) -> dict[str, Any]:
    row = _single(db.table("cases").select("id,text").eq("id", case_id).limit(1).execute())
    if row is None:
        raise NotFoundError(f"case '{case_id}' does not exist")
    return row


def get_reference_points(db: Client, case_id: str) -> list[str]:
    """The points to compare an answer against, derived from the reference answer.

    Derived rather than stored: the answer prose already carries one point per
    sentence, so there is a single representation to keep up to date.
    """
    row = _single(
        db.table("answers").select("answer").eq("case_id", case_id).limit(1).execute()
    )
    return derive_points((row or {}).get("answer") or "")


def pick_next_case(db: Client, after_case_id: str) -> dict[str, Any]:
    """The case following `after_case_id` by id, wrapping around.

    The seeded set is fixed and replayable, so the last case wraps back to the
    first. This only names the case to offer once a chat closes; the learner
    starts it in a new chat, so the choice never has to be stored.
    """
    rows = db.table("cases").select("id,text").order("id").execute().data or []
    if not rows:
        raise NotFoundError("no cases available")

    ids = [row["id"] for row in rows]
    index = (ids.index(after_case_id) + 1) % len(ids) if after_case_id in ids else 0
    return rows[index]


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
    chat_row = _require(
        db.table("chats")
        .insert({"user_id": resolved_user_id, "case_id": case_id})
        .execute(),
        "chat",
    )
    chat_id = chat_row["id"]

    # Seed the case question as the first assistant message.
    db.table("messages").insert(
        {"chat_id": chat_id, "role": "assistant", "message": case["text"]}
    ).execute()

    return ChatCreateResponse(
        chat_id=chat_id,
        user_id=resolved_user_id,
        case=CaseOut.model_validate(case),
    )


def get_chat(db: Client, chat_id: str) -> dict[str, Any]:
    row = _single(db.table("chats").select("*").eq("id", chat_id).limit(1).execute())
    if row is None:
        raise NotFoundError(f"chat '{chat_id}' does not exist")
    return row


def list_chats(user_id: str) -> list[ChatOut]:
    """Every chat belonging to `user_id`, oldest first, with its case text.

    Two plain queries rather than an embedded join: the foreign key guarantees
    every `case_id` resolves, and keeping the lookup explicit makes the row
    shape obvious.
    """
    db = get_client()
    rows = (
        db.table("chats")
        .select("id,case_id")
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
        .data
        or []
    )
    if not rows:
        return []

    case_ids = sorted({row["case_id"] for row in rows})
    case_rows = db.table("cases").select("id,text").in_("id", case_ids).execute().data or []
    text_by_id = {case["id"]: case["text"] for case in case_rows}

    return [
        ChatOut(chat_id=row["id"], text=text_by_id[row["case_id"]])
        for row in rows
        if row["case_id"] in text_by_id
    ]


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
    return [MessageOut.model_validate(row) for row in rows]


def _user_messages(db: Client, chat_id: str) -> list[dict[str, Any]]:
    """The learner's turns in this chat, oldest first.

    The length says how many turns have been taken, which is what tells the two
    steps apart. The text is needed as well: the final answer is graded on both
    turns together.
    """
    return (
        db.table("messages")
        .select("id,message,status,created_at")
        .eq("chat_id", chat_id)
        .eq("role", "user")
        .order("created_at")
        .execute()
        .data
        or []
    )


def _add_assistant_message(db: Client, chat_id: str, text: str) -> dict[str, Any]:
    return _require(
        db.table("messages")
        .insert({"chat_id": chat_id, "role": "assistant", "message": text})
        .execute(),
        "assistant message",
    )


def _discard(db: Client, *rows: dict[str, Any] | None) -> None:
    """Best-effort removal of rows written for a turn that could not finish."""
    for row in rows:
        if not row:
            continue
        try:
            db.table("messages").delete().eq("id", row["id"]).execute()
        except Exception:  # noqa: BLE001 - keep the original error, not this one
            logger.warning("could not roll back message %s", row.get("id"))


def submit_answer(chat_id: str, user_id: str, message: str) -> MessageCreateResponse:
    """Handle one learner turn.

    A session is two turns against the one case the chat belongs to:

    1. first try — the model returns `gap_sentence` + `follow_up`, stored as one
       assistant message. No status: nothing has been decided yet.
    2. final answer — the code compares the learner's answers to the case's
       reference points, sets `status` to "passed" or "failed", replies with the
       verdict and the case to play next, and closes the chat.

    Grading reads both turns rather than only the last one: the follow-up exists
    to draw out the piece the first answer missed, so judging the follow-up alone
    would fail an answer that is just a fragment of a complete one.

    The model never grades, and never decides whether the session ends.
    """
    db = get_client()
    chat = get_chat(db, chat_id)

    if chat["user_id"] != user_id:
        raise ForbiddenError("this chat belongs to another user")
    if chat["ended_at"] is not None:
        raise ConflictError("this chat has already ended")

    case = get_case(db, chat["case_id"])

    previous = _user_messages(db, chat_id)
    if len(previous) > FINAL:
        raise ConflictError("this chat has already ended")

    user_row = _require(
        db.table("messages")
        .insert({"chat_id": chat_id, "role": "user", "message": message})
        .execute(),
        "user message",
    )
    assistant_row: dict[str, Any] | None = None

    try:
        if len(previous) == FIRST_TRY:
            gap = find_gap_and_followup(case["text"], message)
            reply = f'You said "{gap["gap_sentence"]}". {gap["follow_up"]}'
            assistant_row = _add_assistant_message(db, chat_id, reply)
            return MessageCreateResponse(
                reply=reply,
                ended=False,
                gap_sentence=gap["gap_sentence"],
                user_message=MessageOut.model_validate(user_row),
                message=MessageOut.model_validate(assistant_row),
            )

        # The chat's own case, so the chat row never contradicts what was graded.
        combined = " ".join([row["message"] for row in previous] + [message])
        verdict = grade_answer(combined, get_reference_points(db, chat["case_id"]))

        print('verdict',verdict)
        db.table("messages").update({"status": verdict}).eq("id", user_row["id"]).execute()
        user_row["status"] = verdict

        # Verdict, a short close, and the next case as an invitation. Which
        # points were missed is never named: that would give away the answer key.
        outcome = "Passed." if verdict == "passed" else "Failed."
        next_case = pick_next_case(db, chat["case_id"])
        reply = f"{outcome} That's this case finished. Next case: {next_case['text']}"
        assistant_row = _add_assistant_message(db, chat_id, reply)
        db.table("chats").update({"ended_at": _now()}).eq("id", chat_id).execute()

        return MessageCreateResponse(
            status=verdict,
            reply=reply,
            ended=True,
            new_case=CaseOut.model_validate(next_case),
            user_message=MessageOut.model_validate(user_row),
            message=MessageOut.model_validate(assistant_row),
        )
    except ServiceError:
        _discard(db, user_row, assistant_row)
        raise
    except Exception as exc:
        # Do not leave a half-handled turn behind when the model or the
        # database fails part-way through.
        _discard(db, user_row, assistant_row)
        logger.exception("failed to handle answer for chat %s", chat_id)
        raise UpstreamError("could not handle your answer, please try again") from exc
