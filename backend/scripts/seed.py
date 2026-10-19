"""Seed the `cases` and `answers` tables from app.constants.

Idempotent: safe to run repeatedly.

    .venv\\Scripts\\python.exe scripts\\seed.py
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.constants import CASES, EXPECTED_ANSWERS  # noqa: I001
from app.db import get_client 


def main():
    db = get_client()

    for case in CASES:
        db.table("cases").upsert({"id": case["id"], "text": case["question"]}).execute()

    for case_id, answer in EXPECTED_ANSWERS.items():
        existing = db.table("answers").select("id").eq("case_id", case_id).limit(1).execute().data
        if existing:
            db.table("answers").update({"answer": answer}).eq("id", existing[0]["id"]).execute()
        else:
            db.table("answers").insert({"case_id": case_id, "answer": answer}).execute()

    cases = db.table("cases").select("id", count="exact").execute()
    answers = db.table("answers").select("id", count="exact").execute()
    print(f"seeded: {cases.count} cases, {answers.count} answers")


if __name__ == "__main__":
    main()
