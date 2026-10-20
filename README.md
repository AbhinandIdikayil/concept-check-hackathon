# CasePilot

you write a full answer against a question, and it points at the exact
sentence where your reasoning stopped — then asks you one follow-up question.

The first try is never graded. The second try is graded by code, not by a model,
and you always see the reference answer afterwards.

```
CASE QUESTION
      |
      v
YOUR FIRST ANSWER ---------------------.
      |                                 |
      |  the gap                        |  the model copies this sentence,
      |  (exactly one sentence)         |  word for word
      v                                 v
"cache going down is better      ->  GAP MARKED (verbatim)
 than db going down."                     |
      |                                   |
      |                                   v
      |                        ONE FOLLOW-UP QUESTION
      |                        (scenario, no answer, no hint)
      v                                   |
YOUR SECOND TRY  <------------------------+
      |
      |   the code compares both turns against the case's key points
      v
CODE DECIDES  passed / failed
      |
      v
REFERENCE ANSWER SHOWN  +  chat closed  +  next case offered
```

---

## Table of contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Project layout](#project-layout)
- [Getting started](#getting-started)
- [Environment variables](#environment-variables)
- [Database setup](#database-setup)
- [API reference](#api-reference)
- [How grading works](#how-grading-works)
- [How the model is used](#how-the-model-is-used)
- [Known limitations](#known-limitations)
- [Scripts](#scripts)

---

## What it does

CasePilot is a **concept check** interviewer for systems-design topics
(security, caching, sessions, idempotency, background jobs, deploy debugging).

Ten seeded cases, each a scenario with a defensible wrong answer:

| # | Topic |
|---|-------|
| 1 | API keys shipped in frontend JavaScript |
| 2 | Cache vs. database going down |
| 3 | Sessions moved into the database |
| 4 | Where to store an auth token in the browser |
| 5 | A user sharing their own HttpOnly cookie |
| 6 | Access token + refresh token expiry |
| 7 | Duplicate orders from a retried POST |
| 8 | Stale frontend data after a successful update |
| 9 | A background worker crashing before completion |
| 10 | Every request 500s only after deployment |

A session is **two turns**:

1. **First try** — the model finds the sentence where you stopped reasoning,
   quotes it verbatim, and asks exactly one follow-up question. Nothing is
   graded, `status` stays `null`.
2. **Second try** — the code grades **both** turns together against the case's
   key points, replies with `passed` or `failed` plus the reference answer, and
   closes the chat. A "next case" is offered on a button.

Because the follow-up exists to draw out the piece the first answer missed,
grading only the second turn would fail an answer that is a fragment of a
complete one. So both turns count.

---

## Architecture

```
┌────────────────────────┐        ┌──────────────────────────┐
│  frontend (Vite/React) │  HTTP  │  backend (FastAPI)       │
│                        │ ─────► │                          │
│  CasePilot.tsx         │        │  routes/   case, chat,   │
│  api/  client, types   │        │             health       │
│  lib/  router, userId  │        │  services/ chat_service  │
└────────────────────────┘        │  llm.py     Groq call    │
                                  │  db.py      Supabase     │
                                  └────────────┬─────────────┘
                                               │
                                  ┌────────────┴─────────────┐
                                  │  Supabase (Postgres)     │
                                  │  cases, answers, chats,   │
                                  │  messages                │
                                  └──────────────────────────┘
```

The split between the model and the code is the core design decision:

- **The model** picks the gap sentence and writes one follow-up question.
  Nothing else. It never sees the reference answer, never returns a verdict,
  score, or status.
- **The code** decides `passed` / `failed`. Pure Python, deterministic,
  reproducible, and impossible to talk into a passing grade.

The backend talks to Supabase with the **secret key**, which bypasses row level
security. That key must never reach the browser.

---

## Tech stack

**Backend**

- Python 3.11+, FastAPI, uvicorn
- Supabase Python client (PostgREST) over HTTP/2
- Groq (`openai/gpt-oss-20b`) for the gap + follow-up call
- Pydantic v2 / pydantic-settings for request models and config
- `python-ulid` for user ids

**Frontend**

- React 19 + TypeScript, Vite 8
- Tailwind CSS v4 (via `@tailwindcss/vite`)
- axios, lucide-react icons
- Hand-rolled history router (no React Router) — the app needs two routes

**Database**

- Supabase Postgres: 4 tables, RLS enabled with no policies (the API is the
  only client)

---

## Project layout

```
.
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app, CORS, error handlers
│   │   ├── config.py          Settings (pydantic-settings)
│   │   ├── constants.py       The 10 seeded cases + reference answers
│   │   ├── db.py              Supabase client, retrying HTTP transport
│   │   ├── llm.py             Groq call: gap sentence + one follow-up
│   │   ├── validators.py      Pydantic request/response schemas
│   │   ├── routes/
│   │   │   ├── case.py        GET /api/case/all
│   │   │   ├── chat.py        chat create, list, message create, list
│   │   │   └── health.py      GET /api/health
│   │   └── services/
│   │       ├── chat_service.py  cases, chats, messages, grading
│   │       └── errors.py        typed service errors -> HTTP status
│   ├── scripts/
│   │   └── seed.py            Idempotent seed of cases + answers
│   ├── supabase/migrations/   Schema SQL, re-runnable
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.tsx
    │   ├── screens/CasePilot.tsx   The single screen
    │   ├── api/                    client, chatApi, caseApi, types
    │   ├── lib/                    router.ts, userId.ts
    │   └── assets/
    ├── package.json
    └── .env.example
```

---

## Getting started

### Prerequisites

- Python 3.11+
- Node.js 20+
- A Supabase project
- A Groq API key

### 1. Backend

```bash
cd backend

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

Copy the env template and fill it in:

```bash
cp .env.example .env             # Windows: copy .env.example .env
```

```dotenv
GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-20b
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_KEY=<your service-role / secret key>
CORS_ORIGINS=http://localhost:5173
```

Run it:

```bash
uvicorn app.main:app --reload --port 8000
```

The API is now on `http://localhost:8000`, with interactive docs at
`http://localhost:8000/docs`.

### 2. Database

Apply the migrations to your Supabase project, then seed the cases.

```bash
cd backend

# Either via psql
psql "$SUPABASE_DB_URL" -f supabase/migrations/20261019070533_init.sql
psql "$SUPABASE_DB_URL" -f supabase/migrations/20261019112426_status_passed_failed.sql

# Or via the Supabase CLI, from the folder holding supabase/
npx supabase db push
```

Then seed:

```bash
python scripts/seed.py
# seeded: 10 cases, 10 answers
```

`scripts/seed.py` is idempotent — safe to run repeatedly.

### 3. Frontend

```bash
cd frontend
npm install

cp .env.example .env
```

```dotenv
VITE_API=http://localhost:8000
```

```bash
npm run dev
```

Open `http://localhost:5173`.

---

## Environment variables

### Backend (`backend/.env`)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `SUPABASE_URL` | yes | — | Supabase project URL |
| `SUPABASE_KEY` | yes | — | Secret / service-role key. **Never ship to the browser.** |
| `GROQ_API_KEY` | yes | — | Groq API key |
| `GROQ_MODEL` | no | `openai/gpt-oss-20b` | Model id for the gap + follow-up call |
| `CORS_ORIGINS` | no | `*` | Comma-separated allowed origins, or `*` for all |

> `backend/.env.example` does not list `CORS_ORIGINS` — add it yourself if you
> want to restrict origins. The default `*` is fine for local development.

### Frontend (`frontend/.env`)

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API` | `http://localhost:8000` | Base URL of the FastAPI backend |

`vite.config.ts` reads `API` first, then `VITE_API`, and inlines **only** those
two into the client bundle via `define`. Defining all of `process.env` would
leak every environment variable — including secrets — into the browser.

---

## Database setup

Four tables. This is the whole persistence layer.

| Table | Columns |
|---|---|
| `cases` | `id varchar pk`, `text text` — the question |
| `answers` | `id uuid pk`, `case_id varchar fk → cases (cascade)`, `answer text` — the reference answer |
| `chats` | `id uuid pk`, `user_id text`, `case_id varchar fk → cases`, `created_at timestamptz`, `ended_at timestamptz null` |
| `messages` | `id uuid pk`, `chat_id uuid fk → chats (cascade)`, `role message_role`, `message text`, `status message_status null`, `created_at timestamptz` |

Enums:

- `message_role` — `'user'` | `'assistant'`
- `message_status` — `'passed'` | `'failed'` (renamed from `'success'` | `'recite'`)

Indexes: `messages (chat_id, created_at)`, `chats (user_id)`, `chats (case_id)`,
plus a unique index on `answers (case_id)` so there is exactly one reference
answer per case.

Row level security is **enabled on all four tables with no policies**: the API
is the only client and it uses the secret key, which bypasses RLS.

---

## API reference

Base URL: `http://localhost:8000`

### `GET /api/health`

```json
{ "status": "ok" }
```

### `GET /api/case/all`

All seeded cases, ordered by id.

```json
[{ "id": "1", "text": "You put the paid API key inside your frontend JavaScript. What breaks?" }]
```

### `POST /api/chat/create`

Opens a chat on a case and seeds the question as the first assistant message.

```json
{ "case_id": "1", "user_id": "01J..." }
```

`user_id` is optional — the backend mints a ULID when it is omitted. The
response returns the id the backend will use, and the frontend stores it.

```json
{
  "chat_id": "8f2c...",
  "user_id": "01J...",
  "case": { "id": "1", "text": "..." }
}
```

### `GET /api/chat/all?user_id=…`

Every chat belonging to one user, newest first, with the text of its case.

```json
[{ "chat_id": "8f2c...", "text": "You put the paid API key..." }]
```

### `POST /api/chat/{chat_id}/message/create`

Send one learner turn.

```json
{ "user_id": "01J...", "message": "Anyone can read the key in devtools." }
```

First turn — no verdict yet, `gap_sentence` points at where reasoning stopped:

```json
{
  "status": null,
  "reply": "You said \"Anyone can read the key in devtools.\". If a user copies that key out of the bundle and runs it from their own machine, what happens to your bill?",
  "ended": false,
  "gap_sentence": "Anyone can read the key in devtools.",
  "correct_answer": null,
  "new_case": null,
  "user_message": { "...": "..." },
  "message": { "...": "..." }
}
```

Second turn — graded, session closed:

```json
{
  "status": "failed",
  "reply": "Not quite this time. Here's the answer we were looking for:\nAnyone can open DevTools and read the key...",
  "ended": true,
  "gap_sentence": null,
  "correct_answer": "Anyone can open DevTools and read the key...",
  "new_case": { "id": "2", "text": "A cache (Redis) sits between server and DB..." },
  "user_message": { "...": "..." },
  "message": { "...": "..." }
}
```

### `GET /api/chat/{chat_id}/message/all`

The full transcript, oldest first.

### Error responses

Errors carry a `detail` string and a matching status code:

| Status | Meaning |
|---|---|
| `400` | Generic `ServiceError` |
| `403` | The chat belongs to another user |
| `404` | Case or chat not found |
| `409` | The chat has already ended |
| `503` | Database unreachable, database error, or the model failed |

---

## How grading works

All of it lives in `backend/app/services/chat_service.py`.

1. **Derive the key points** (`derive_points`) — the reference answer is split
   into one point per sentence, and one point per `:` or `;` clause. Fragments
   with no significant words are dropped, since they could never be covered and
   would permanently lower the best achievable score.
2. **Check coverage** — a point counts as covered when at least
   `POINT_COVERAGE = 0.5` of its significant words (stopwords removed) appear
   anywhere in the learner's answers.
3. **Decide** (`grade_answer`) — the answer passes when at least
   `PASS_THRESHOLD = 0.6` of the case's points are covered.

Case 1 derives three points, so passing it needs two of them. Both turns are
combined before grading.

The thresholds live at the top of `chat_service.py` — change them there.

### Why the code grades and not the model

A deterministic grader is reproducible, cannot be argued with, and cannot be
gamed by a confident tone. It also has one failure mode, and it is the one
that matters here: it measures whether you used the reference's **words**, not
whether you **understood**. A correct answer can score zero if it says
"share" where the reference says "copy". See
[`backend/CONCEPT_CHECK_SUBMISSION.txt`](backend/CONCEPT_CHECK_SUBMISSION.txt)
for the measured examples.

---

## How the model is used

`backend/app/llm.py` — one Groq call per turn, `temperature 0.2`, JSON response
format. The model returns exactly two things:

```json
{ "gap_sentence": "<verbatim sentence from the learner's answer>", "follow_up": "<one question>" }
```

Rules encoded in the system prompt:

- `gap_sentence` must be copied **word for word** from the candidate's answer.
  No rewriting, no summarising, no grammar fixing, no joining sentences.
- `follow_up` is **one** question about what actually breaks at that gap. It
  must be a scenario, not a definition. No answer, no hint, no telling the
  candidate they were wrong, and never any part of a correct answer.

The model is called with the question and the candidate's answer **only** — it
never sees the reference answer, so it cannot leak it into the follow-up.

After the call, the code verifies the quote really occurs in the candidate's
answer. If it does not, the code falls back to the candidate's own answer
rather than putting words in their mouth.

A failed Groq call or an unparseable response is retried once, then raised as
an `UpstreamError` (503). The turn is rolled back, so a failed call never
leaves a half-handled message in the transcript.

---

## Known limitations

- **The grader is surface-form.** It measures overlap with the reference
  wording, not comprehension. This is a deliberate trade-off (reproducible vs.
  eloquent), but it is the main known weakness.
- **A session is exactly two turns.** A third submission returns `409`.
- **No auth.** `user_id` is a client-supplied ULID stored in `localStorage`.
  There is no login, no signature, and no verification that the caller owns
  the browser.
- **No tests.** The repo has no test suite.
- **The chat list is per-browser.** Clearing `localStorage` orphans your chats;
  the next `localStorage` id starts a fresh list.
- **Single case set.** Cases live in `backend/app/constants.py` and are seeded
  into Postgres. To change them, edit the constant and re-run the seed script.

---

## Scripts

### Backend

```bash
uvicorn app.main:app --reload --port 8000   # dev server
python scripts/seed.py                       # seed cases + answers (idempotent)
```

### Frontend

```bash
npm run dev        # dev server on :5173
npm run build      # type-check + production build
npm run preview    # serve the production build
npm run lint       # eslint
```

### Database

```bash
psql "$SUPABASE_DB_URL" -f supabase/migrations/20261019070533_init.sql
psql "$SUPABASE_DB_URL" -f supabase/migrations/20261019112426_status_passed_failed.sql
npx supabase db push    # from backend/
```

All migrations are re-runnable.

---

## Notes for reviewers

- [`backend/CONCEPT_CHECK_SUBMISSION.txt`](backend/CONCEPT_CHECK_SUBMISSION.txt)
  — the design write-up: what the tool was built to do, the drawing of the
  flow, who judges the second try, and the measured failure mode of the grader.
- `backend/app/services/chat_service.py` — the interesting file. Grading, chat
  lifecycle, and the two-turn session logic are all here.
- `backend/app/llm.py` — the entire contract with the model.
- `backend/app/db.py` — a retrying HTTP/2 transport that re-sends a read whose
  pooled connection died, but never re-sends a write.
