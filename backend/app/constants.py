"""Hardcoded case data.

`CASES` is the fixed starter set. Each case carries:

- `question`  what the learner is asked,
- `expected`  the reference answer.

The reference answer doubles as the answer key: it is written one point per
sentence (or per `:`/`;` clause), and the code derives the points from it at
grading time. That keeps a single representation of the case data, so there is
nothing to keep in sync. Write new cases accordingly: one point per sentence,
no asides or commentary aimed at a human reader, because every sentence becomes
a point a learner has to cover.

Pass/fail is decided by comparing an answer to those points alone. The model
never grades and never sees the reference answer.
"""


CASES = [
    {
        "id": "1",
        "question": "You put the paid API key inside your frontend JavaScript. What breaks?",
        "expected": "Anyone can open DevTools and read the key. They copy it, use it themselves, and you pay for their calls. The key is not secret on the client.",
    },
    {
        "id": "2",
        "question": "A cache (Redis) sits between server and DB for sessions. The cache goes down for 5 minutes. Better or worse than the DB going down? Why?",
        "expected": "Better only if the cache is a fast path with a database fallback. Same problem if sessions live only in the cache. Every layer moves the single point of failure.",
    },
    {
        "id": "3",
        "question": "Sessions moved to the DB. The DB goes down for 5 minutes. What happens to logged-in users, and what do you do?",
        "expected": "It needs a fallback such as a cache or a queue or a circuit breaker. Moving to the database adds a new single point of failure.",
    },
    {
        "id": "4",
        "question": "Your auth API returns a token. Where do you store it in the browser, and why?",
        "expected": "An HttpOnly cookie, not localStorage, because JavaScript cannot read it. Secure alone only means HTTPS. A short lived access token with a refresh token. CSRF protection.",
    },
    {
        "id": "5",
        "question": "The user copies their HttpOnly cookie and sends it to a friend. Does HttpOnly stop that? What do you do?",
        "expected": "HttpOnly stops JavaScript reading it but not the user copying it. Sharing still works. Limit the damage with short expiry, rotation and revocation. Detect concurrent sessions. Step up authentication.",
    },
    {
        "id": "6",
        "question": "15-min access token + refresh token. After 15 minutes, does the friend get logged out? Walk me through it.",
        "expected": "Only if the refresh token is not also shared. The friend can refresh too. Rotation makes sharing detectable. Revocation limits damage.",
    },
]

# case_id -> expected answer, used for seeding the `answers` table.
EXPECTED_ANSWERS = {case["id"]: case["expected"] for case in CASES}
