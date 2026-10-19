"""Groq calls: grading an answer (`find_gap`) and writing a follow-up case
(`write_followup`).

Both functions ask the model for JSON and tolerate a fenced code block around
it. A single retry is attempted when the model returns something unparseable.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from groq import Groq

from .config import settings

logger = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

GRADER_SYSTEM = """You grade a candidate's answer to a technical concept-check question.

You are given the question, a reference answer, and the candidate's answer.
Compare the candidate's answer against the reference answer on substance, not wording.

- verdict "success": the candidate covers the reference points. Paraphrasing is fine.
- verdict "recite": the answer is wrong, shallow, incomplete, or just recites buzzwords
  without covering one or more reference points.

The "feedback" field is shown directly to the candidate, so write it as direct
second-person prose. On success, congratulate them and name what they got right.
On "recite", say precisely which reference point is missing. 2-4 sentences, no markdown.

Reply with ONLY a JSON object:
{"verdict": "success" | "recite", "feedback": "<prose>", "missing_points": ["<short label>"]}
"missing_points" is an empty list when the verdict is "success"."""

WRITER_SYSTEM = """You write follow-up questions for a technical concept-check interview.

The candidate's answer to a question was shallow, so you probe the specific gap.
Write exactly ONE new question that:
- targets the missing points,
- stays in the same problem domain (backend, auth, sessions, caching, secrets),
- is self-contained, with no reference to a previous question or answer,
- is slightly harder than what they failed, written as a scenario, not a definition.

Also write the reference answer for it: the specific points a strong candidate must cover.

Reply with ONLY a JSON object:
{"question": "<the question>", "expected": "<the reference answer>"}"""


def _client() -> Groq:
    return Groq(api_key=settings.groq_api_key)


def _parse_json(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK.search(raw or "")
    if not match:
        raise ValueError(f"model did not return JSON: {raw!r}")
    return json.loads(match.group(0))


def _complete(system: str, user: str) -> dict[str, Any]:
    """Call Groq and return a JSON object, retrying once on a bad response."""
    client = _client()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            return _parse_json(response.choices[0].message.content or "")
        except Exception as exc:  # noqa: BLE001 - retry any provider/parse failure once
            last_error = exc
            logger.warning("groq call failed (attempt %s): %s", attempt + 1, exc)

    raise RuntimeError(f"groq call failed: {last_error}") from last_error


def find_gap(
    question: str,
    expected_answer: str | None,
    user_answer: str,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Grade the user's answer.

    Returns {"verdict": "success" | "recite", "feedback": str, "missing_points": list[str]}.
    """
    transcript = ""
    if history:
        lines = [f"{m.get('role')}: {m.get('message')}" for m in history]
        transcript = "\n\nConversation so far:\n" + "\n".join(lines)

    user = (
        f"Question:\n{question}\n\n"
        f"Reference answer:\n{expected_answer or '(none provided)'}\n\n"
        f"Candidate's answer:\n{user_answer}"
        f"{transcript}"
    )

    result = _complete(GRADER_SYSTEM, user)

    verdict = str(result.get("verdict", "")).strip().lower()
    if verdict not in {"success", "recite"}:
        # Never fail the request over a formatting slip: treat it as a gap.
        logger.warning("unexpected verdict %r, defaulting to recite", result.get("verdict"))
        verdict = "recite"

    feedback = str(result.get("feedback") or "").strip()
    if not feedback:
        feedback = (
            "Nice, that covers the key points."
            if verdict == "success"
            else "You are missing part of the point here, let's dig into it."
        )

    missing = result.get("missing_points") or []
    if not isinstance(missing, list):
        missing = [str(missing)]

    return {
        "verdict": verdict,
        "feedback": feedback,
        "missing_points": [str(point) for point in missing],
    }


def write_followup(
    question: str,
    expected_answer: str | None,
    user_answer: str,
    feedback: str = "",
    missing_points: list[str] | None = None,
) -> dict[str, str]:
    """Write one new case targeting the gap.

    Returns {"question": str, "expected": str}.
    """
    gaps = ", ".join(missing_points or []) or "(see feedback)"
    user = (
        f"Original question:\n{question}\n\n"
        f"Reference answer:\n{expected_answer or '(none provided)'}\n\n"
        f"Candidate's answer:\n{user_answer}\n\n"
        f"Grader feedback:\n{feedback}\n\n"
        f"Missing points:\n{gaps}"
    )

    result = _complete(WRITER_SYSTEM, user)

    new_question = str(result.get("question") or "").strip()
    new_expected = str(result.get("expected") or "").strip()
    if not new_question:
        raise ValueError("model returned an empty follow-up question")

    return {"question": new_question, "expected": new_expected or "(no reference answer provided)"}
