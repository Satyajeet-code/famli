# Famli Retirement Chatbot

A conversational retirement-corpus calculator. Users sign up, chat with **Research Buddy** (a Groq-powered LLM), and it walks them through a few questions before computing how much money they need to retire — using the NISM formula from the Famli product spec.

- **Frontend:** plain HTML + CSS + vanilla JS, deployed to Vercel
- **Backend:** FastAPI + SQLAlchemy + Groq SDK, deployed to Render
- **Database:** Postgres (DigitalOcean managed, but any Postgres works)
- **Live demo:** https://famli-ten.vercel.app/

---

## Repository layout

```
.
├── backend/
│   ├── api/                          # FastAPI routers (thin HTTP layer)
│   │   ├── auth_routes.py            # /api/auth/signup, /api/auth/login
│   │   └── retirement_routes.py      # /api/retirement/chat, /history
│   ├── app/
│   │   ├── controller/               # Per-request orchestration + error mapping
│   │   ├── models/
│   │   │   └── retirement_schemas.py # Pydantic request/response models
│   │   ├── services/
│   │   │   ├── auth/                 # signup + login (bcrypt + JWT)
│   │   │   ├── database/
│   │   │   │   ├── db_engine.py      # Async SQLAlchemy + metadata reflection
│   │   │   │   └── schema.sql        # DDL for the three Postgres tables
│   │   │   ├── llm/
│   │   │   │   └── groq_client.py    # Thin wrapper around the official groq SDK
│   │   │   └── retirement/
│   │   │       ├── prompts.py        # System prompt + welcome message
│   │   │       ├── tools.py          # `calculate_retirement_corpus` tool def + impl
│   │   │       ├── corpus_calculator.py  # NISM formula (Decimal-precision math)
│   │   │       └── retirement_service.py # The chat orchestrator
│   │   └── utils/
│   │       ├── auth.py               # bcrypt + JWT helpers
│   │       └── logger.py             # AppLogger
│   ├── main.py                       # FastAPI entry point
│   └── requirements.txt
├── frontend/
│   ├── index.html                    # Login screen
│   ├── signup.html                   # Signup screen
│   ├── chat.html                     # Chat + collected-values panel + corpus card
│   ├── styles.css
│   └── app.js                        # API client, auth helpers, formatters
├── .env.example                      # Template for backend env vars
├── .gitignore
└── README.md
```

---

## How it works (high level)

### Signup / login

1. User signs up via `POST /api/auth/signup`. The service hashes the password with **bcrypt**, inserts a row into `users_dummy`, and — in the same transaction — seeds the bot's welcome message into `chat_history_dummy`.
2. Login is the standard verify-and-issue: `POST /api/auth/login` validates the password and returns a JWT (HS256).
3. JWTs are issued and currently stored client-side, but **not yet verified** on protected routes — the chat endpoint trusts `user_id` in the request body. For an internal demo this is acceptable; for production add a `Depends(require_user)` dependency.

### Chat turn

`POST /api/retirement/chat` with `{ user_id, message }`. The service:

1. Persists the user's message to `chat_history_dummy`.
2. Loads the last **10** chat turns + any **previously established inputs** from `retirement_inputs_dummy`.
3. Calls Groq's `chat.completions` with the system prompt, the history, and the `calculate_retirement_corpus` tool schema.
4. Two paths:
   - **Plain text reply** → save and return.
   - **Tool call** → execute `calculate_retirement_corpus`, upsert the inputs, run the NISM math, feed the result back as a `tool` role message, call Groq once more for the natural-language summary, save and return.
5. Every assistant turn ends with a `COLLECTED: {...}` JSON block that the frontend parses to populate the live values panel.

### NISM corpus formula

```
Future Annual Expense = Current Annual Expense × (1 + inflation)^years_to_retire
Real Rate (r)         = (1 + return) / (1 + inflation) − 1
Retirement Period (p) = life_expectancy − retirement_age
Corpus                = Future Annual Expense × ((1 − (1 + r)^−p) / r) × (1 + r)
```

The trailing `(1 + r)` multiplier accounts for annuity-due (expenses drawn at the start of each retirement year), matching the spec's worked example. Defaults applied if user doesn't specify: **6%** inflation, **7%** return, life expectancy **80**.

---

## Database

Three tables, all defined in [backend/app/services/database/schema.sql](backend/app/services/database/schema.sql):

| Table | Purpose |
|---|---|
| `users_dummy` | Username + bcrypt password hash |
| `chat_history_dummy` | Append-only log of every user / assistant turn |
| `retirement_inputs_dummy` | One row per user; upserted after each successful calculation. Used as "previously established values" on future sessions |

SQLAlchemy `metadata.reflect()` reads the schema at app startup — no Python `Table()` definitions in code; the live DB is the source of truth.

---

## Local setup

### 1. Clone

```bash
git clone <repo-url>
cd text
```

### 2. Create Postgres + apply schema

Any Postgres works (Neon, DigitalOcean, Supabase, local). Then:

```bash
psql "$DATABASE_URL" -f backend/app/services/database/schema.sql
```

Verify with:

```bash
psql "$DATABASE_URL" -c "SELECT tablename FROM pg_tables WHERE schemaname='public';"
```

You should see `users_dummy`, `chat_history_dummy`, `retirement_inputs_dummy`.

### 3. Backend

```bash
# venv
python3 -m venv .venv
source .venv/bin/activate

# deps
pip install -r backend/requirements.txt

# env vars
cp .env.example .env
# edit .env — fill in DATABASE_URL, GROQ_API_KEY, JWT_SECRET

# run
cd backend
uvicorn main:app --host 0.0.0.0 --port 8003 --reload
```

Smoke-test it:

```bash
curl http://localhost:8003/health
# → {"status":"ok"}
```

### 4. Frontend

The frontend points at `https://famli-backend.onrender.com` by default. For local testing, edit [frontend/app.js](frontend/app.js):

```javascript
const API_BASE = "http://localhost:8003";
```

Then open `frontend/index.html` directly in a browser, or serve it:

```bash
python3 -m http.server -d frontend 5500
# open http://localhost:5500
```

---

## Environment variables

See [.env.example](.env.example). Required at minimum:

| Var | What it does |
|---|---|
| `DATABASE_URL` | Postgres connection string. Use the standard `postgresql://user:pw@host:port/dbname?sslmode=require` form. The async engine auto-derives the `+asyncpg` variant. |
| `GROQ_API_KEY` | From https://console.groq.com |
| `GROQ_MODEL` | Optional. Defaults to `llama-3.3-70b-versatile`. The deployed version uses `openai/gpt-oss-120b`. |
| `JWT_SECRET` | Used to sign JWTs. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `JWT_ALGORITHM` | Defaults to `HS256`. |
| `JWT_EXPIRES_MINUTES` | Token lifetime. Defaults to `60`; deployed value is `1440` (24h). |

---

## Deployment

The repo is wired for one specific deployment shape, but nothing's married to it:

| Concern | Service | Notes |
|---|---|---|
| Frontend | **Vercel** | Static, no build. Root Directory: `frontend`. Framework Preset: `Other`. |
| Backend | **Render** | Free web service. Root Directory: `backend`. Build: `pip install -r requirements.txt`. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`. |
| Database | **DigitalOcean managed Postgres** | Public-internet accessible, TLS-required. Render's free tier has no fixed egress IP, so don't IP-allowlist. |

### Free-tier quirks

- **Render sleeps after 15 min idle.** First request after sleep takes 30–60s for the container to wake up. Subsequent requests are fast.
- **Render filesystem is ephemeral.** The `logs/*.txt` debug dumps in this code work locally but disappear on every redeploy. That's fine — they're marked `TODO REMOVE`.
- **No streaming yet.** Each chat turn waits for the full Groq reply before responding. With the tool-call flow this means two LLM round-trips per calculation turn. A typing indicator in the frontend smooths over the perceived wait.

---


## Useful endpoints

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | — | `{"status":"ok"}` |
| POST | `/api/auth/signup` | `{username, first_name, last_name, password}` | JWT + user_id |
| POST | `/api/auth/login` | `{username, password}` | JWT + user_id |
| POST | `/api/retirement/chat` | `{user_id, message}` | `{bot_message, corpus?}` |
| GET | `/api/retirement/history?user_id=N` | — | `{messages: [...]}` |
