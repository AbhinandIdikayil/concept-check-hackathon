"""Groq call: find where the learner stopped reasoning and ask one follow-up.

The model has exactly one job and returns exactly two things:

    {"gap_sentence": "<verbatim sentence from the learner>", "follow_up": "<question>"}

It is never asked for a verdict, a status, a score, or an opinion on whether the
learner understood. Pass/fail is decided in `services.chat_service` by comparing
the learner's answer to the case's reference points.

The model is given the question and the learner's answer only. It never sees the
reference answer, so it cannot leak it into the follow-up.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from groq import Groq

from .config import get_settings

logger = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

GAP_SYSTEM = """You are looking at one answer a candidate gave to a technical question.

Do exactly two things.

1. "gap_sentence": find the exact sentence where the candidate stopped reasoning. That is
   the sentence where they assert something without saying what actually breaks, why, or what
   follows from it. Copy it word for word from the candidate's answer. Do not rewrite it, do
   not summarise it, do not fix its grammar, do not join sentences together.

2. "follow_up": write ONE question that asks what actually breaks at that gap. Make it a
   scenario, not a definition. Do not answer it. Do not give hints. Do not tell the candidate
   they were wrong or what they missed. Never reveal a correct answer or any part of one.

Reply with ONLY a JSON object:
{"gap_sentence": "<verbatim sentence copied from the candidate's answer>", "follow_up": "<one question>"}"""


def _client() -> Groq:
    return Groq(api_key=get_settings().groq_api_key)


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
                model=get_settings().groq_model,
                messages=messages,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            return _parse_json(response.choices[0].message.content or "")
        except Exception as exc:  # noqa: BLE001 - retry any provider/parse failure once
            last_error = exc
            logger.warning("groq call failed (attempt %s): %s", attempt + 1, exc)

    raise RuntimeError(f"groq call failed: {last_error}") from last_error


def find_gap_and_followup(question: str, answer: str) -> dict[str, str]:
    """Return the sentence where reasoning stopped, and one follow-up question.

    Returns {"gap_sentence": str, "follow_up": str}. Raises ValueError when the
    model will not produce a follow-up question.
    """
    user = f"Question:\n{question}\n\nCandidate's answer:\n{answer}"
    result = _complete(GAP_SYSTEM, user)

    gap = str(result.get("gap_sentence") or "").strip()
    follow_up = str(result.get("follow_up") or "").strip()

    # The gap sentence is only useful if it is the learner's own words. If the
    # model paraphrased or invented it, fall back to the learner's answer rather
    # than putting words in their mouth.
    if not gap or gap.strip("\"'") not in answer:
        logger.warning("gap_sentence was not a verbatim quote, falling back to the answer")
        gap = answer.strip()

    if not follow_up:
        raise ValueError("model returned an empty follow_up")

    return {"gap_sentence": gap, "follow_up": follow_up}
