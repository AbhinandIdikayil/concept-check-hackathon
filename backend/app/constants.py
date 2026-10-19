"""Hardcoded case data.

`CASES` is the fixed starter set. The expected answer for each case is kept
separate (mirroring the `cases` / `answers` split in the database) and is
derived here so there is a single source of truth.
"""
import json


CASES = [
    {
        "id": "1",
        "question": "You put the paid API key inside your frontend JavaScript. What breaks?",
        "expected": "Anyone can open DevTools and read the key. They copy it, use it themselves, and you pay for their calls. The key is not secret on the client.",
    },
    {
        "id": "2",
        "question": "A cache (Redis) sits between server and DB for sessions. The cache goes down for 5 minutes. Better or worse than the DB going down? Why?",
        "expected": "Better than DB-down IF the cache is a fast path with DB fallback. Same problem if sessions live only in the cache. Every layer moves the single point of failure.",
    },
    {
        "id": "3",
        "question": "Sessions moved to the DB. The DB goes down for 5 minutes. What happens to logged-in users, and what do you do?",
        "expected": "Needs a fallback: cache, queue, or circuit breaker. Moving to DB adds a new single point of failure. 'Nothing much users can do' is not an answer.",
    },
    {
        "id": "4",
        "question": "Your auth API returns a token. Where do you store it in the browser, and why?",
        "expected": "HttpOnly cookie (JS can't read it), not localStorage. Secure alone only means HTTPS. Short-lived access token + refresh token. CSRF protection.",
    },
    {
        "id": "5",
        "question": "The user copies their HttpOnly cookie and sends it to a friend. Does HttpOnly stop that? What do you do?",
        "expected": "No. HttpOnly stops JavaScript reading it, not the user copying it. Sharing still works. Limit damage: short expiry, rotation, revocation, detect concurrent sessions, step-up auth.",
    },
    {
        "id": "6",
        "question": "15-min access token + refresh token. After 15 minutes, does the friend get logged out? Walk me through it.",
        "expected": "Only if the refresh token isn't also shared. If it is, the friend refreshes too. Rotation makes sharing detectable. Revocation limits damage.",
    },
]

# case_id -> expected answer, used for seeding the `answers` table.
EXPECTED_ANSWERS = {case["id"]: case["expected"] for case in CASES}
print(json.dumps(EXPECTED_ANSWERS, indent=2, ensure_ascii=False))

# The themed pool the writer prompt may draw on for follow-up cases.
FIXED_IDEAS = [case["question"] for case in CASES]
print(json.dumps(FIXED_IDEAS, indent=2, ensure_ascii=False))
