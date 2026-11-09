# LoNo

[![CI](https://github.com/manevia/LoNo/actions/workflows/ci.yml/badge.svg)](https://github.com/manevia/LoNo/actions/workflows/ci.yml)

Streaming TV, radio, podcasts, music and courses in one app, with creator channels and a
simulated utility token ($LONO) that viewers earn by watching and learning, then stake and vote with.

| Learn | Certificate | Mobile |
|---|---|---|
| ![Learn](docs/screenshots/02_learn.png) | ![Certificate](docs/screenshots/05_certificate.png) | ![Mobile](docs/screenshots/10_mobile_learn.png) |

- **Backend:** FastAPI + MongoDB (Motor), in `backend/`
- **Frontend:** React 19 + Tailwind + shadcn/ui, in `frontend/`
- **Version:** 2.4 (rebuilt from the original Emergent prototype so it runs anywhere; adds the course builder, reviews, earnings insights, sign-in protection and account controls)

## Run it

### Get the code

```bash
git clone https://github.com/manevia/LoNo.git
cd LoNo
```

### Quickest: the launcher (needs Python 3.10+)

| | Windows | macOS / Linux |
|---|---|---|
| Run locally | double-click `start.cmd` | `bash start.sh` |
| Run with Docker | `start.cmd -Docker` | `bash start.sh --docker` |

Local mode opens **http://localhost:8001**. Docker mode serves **http://localhost:8080**.
Keep the window open while you use the app.

The launcher sets up everything it needs on the first run:
- a Python virtual environment and its packages
- `backend/.env` with an in-memory database and a random secret
- the website build, if it's missing (this needs Node.js 20)

The in-memory database resets when you stop the app. To keep data, set
`MONGO_URL=mongodb://localhost:27017` in `backend/.env`, or use Docker mode.

### Developing

```bash
# API with auto-reload on :8001
cd backend && python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn server:app --reload --port 8001

# Web app with hot reload on :3000 (forwards /api to :8001)
cd frontend && yarn install && yarn start
```

### Troubleshooting

- **"This site can't be reached":** nothing is running on that port. Start the launcher and wait for `Ready`, and check the port: 8001 for local mode, 8080 for Docker.
- **"Port … is already in use":** run on another port with `start.cmd -Port 8002` or `PORT=8002 bash start.sh`.
- **Docker "not running":** open Docker Desktop and wait for "Engine running".

## Turning features on

Everything below is optional. Without a key, the feature hides itself or explains that it's off.
`GET /api/config` reports what's on.

| Feature | Settings in `backend/.env` |
|---|---|
| AI assistant and summaries (Claude) | `ANTHROPIC_API_KEY`, optional `ANTHROPIC_MODEL` |
| Auto-captions | `TRANSCRIBE_API_KEY` (OpenAI or any compatible speech-to-text endpoint via `TRANSCRIBE_BASE_URL`) |
| Google sign-in | `GOOGLE_CLIENT_ID` (a Google Identity Services *web* client; add your site to its authorised JavaScript origins) |
| Premium subscriptions | `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`; point a Stripe webhook at `/api/payments/webhook` for `checkout.session.completed` and `customer.subscription.deleted` |
| Cloud file storage | `STORAGE_BACKEND=s3`, `S3_BUCKET`, `S3_REGION`, plus `S3_ENDPOINT_URL` for R2 / MinIO / Spaces |

The full list with defaults is in `backend/.env.example`.

## How the token economy works

$LONO is an internal ledger with no cash value. Every balance change writes a transaction, so the
transaction history always adds up to the balance.

| Action | Rule |
|---|---|
| Sign up | +100 $LONO |
| Watch | +1 per verified minute, max 10 per title per session, max 60 per day |
| Pass a course | Course reward (20 to 30), paid once, plus a verifiable certificate |
| Stake | 30 / 90 / 180 / 365 days at 8 / 14 / 22 / 35% APY; unstaking early returns the tokens but no reward |
| Vote | Power = balance + 2 x staked; one vote per proposal |
| Propose | Needs 100 $LONO staked |
| Demo purchase | Adds $LONO without payment, max $500; turn off with `SIMULATED_TOKEN_PURCHASE=false` |

**Verified watching.** The player opens a watch session and sends a heartbeat every 30 seconds
while media plays. The server credits only the wall-clock time it saw between heartbeats (each gap
capped at 45 seconds), so a client can't claim time it didn't spend.

**Certificates.** Each certificate stores a SHA-256 fingerprint of its contents. The public page
`/certificates/<id>` recomputes it, so an edited certificate shows as not valid. A failed quiz
attempt shows which answers were wrong, never the right ones.

## Course builder (for creators)

Creators build courses in **Studio, then Courses, then New course**:

1. Write the lessons: text, an optional video (paste a link or upload) and a duration.
2. Write a quiz of at least 3 questions, mark each correct answer, and set the pass mark.
3. Publish. A checklist in the editor says what's still missing.
4. With `ANTHROPIC_API_KEY` set, the editor can draft quiz questions from your lesson text. You review and save them yourself.

Rules that keep the economy fair:

| Rule | Default | Setting |
|---|---|---|
| Learners who pass earn a platform-set reward; creators can't choose their own | 10 $LONO | `CREATOR_COURSE_REWARD` |
| The creator earns a payout each time someone else passes | 2 $LONO | `CREATOR_PAYOUT_PER_CERT` |
| Passing your own course earns nothing | | |
| A published course can't be edited into an incomplete state | | |
| A course whose learners hold certificates can only be unpublished, not deleted | | |
| Editing lessons keeps learners' progress on the lessons that remain | | |
| Only learners who passed can rate a course (1 to 5 stars), once each; creators can't rate their own | | |

## Tests

```bash
cd backend && pytest
```

43 API tests cover:

- accounts
- likes, My List and subscriptions
- staking and the ledger
- the anti-cheat rules for watch rewards
- governance
- the course-to-certificate flow, including tamper detection
- uploads and video range requests
- the creator studio
- the course builder: drafts, publishing, payouts, editing rules and AI question drafts
- course reviews: who can review, averages, editing and deleting
- sign-in and sign-up rate limits
- wallet earnings insights, watch history and resume position
- account settings: profile, password, data export and account deletion
- security headers

## Project layout

```
backend/
  server.py              entry point (uvicorn server:app)
  app/config.py          all settings and feature flags
  app/ledger.py          every $LONO credit/debit
  app/storage.py         local disk or S3, with range requests
  app/ai.py              Claude + speech-to-text clients
  app/seed.py            demo catalogue and courses
  app/routers/           auth, content, watch, creator, creator_courses, wallet, governance, ai, payments, files, learn
  tests/
frontend/src/
  pages/                 Home, Watch, Live, Browse, Search, Channel, Studio, Wallet,
                         Tokenomics, Governance, Learn, Course, CourseEditor, Certificate, Profile, Login, Signup
  lib/                   api client, auth, feature config, useWatchSession
docs/                    PRD, design guidelines, screenshots
start.cmd / start.ps1    Windows launcher
start.sh                 macOS/Linux launcher
.github/workflows/ci.yml tests + web build + Docker build on every push
```

## Abuse protection

| Limit | Default | Setting |
|---|---|---|
| Failed sign-ins per email from one network, before a pause | 5 per 15 minutes | `LOGIN_MAX_FAILURES`, `LOGIN_WINDOW_SEC` |
| New accounts from one network | 10 per hour | `SIGNUPS_PER_IP_PER_HOUR` |

Limits are kept in the API process's memory, which suits the default single-process setup. If you run several API copies behind a load balancer, move them to Redis so the copies share counts.

## Privacy and account controls

Signed-in users manage their account at **Profile → Settings**:

- **Change** their display name, or change their password. Google sign-ups can set a password here.
- **Download their data:** everything LoNo stores about them, as one JSON file (`GET /api/me/export`). This covers the GDPR right of access.
- **Delete their account** after typing their email and password (`DELETE /api/me`). This covers the right to erasure. Deletion removes:
  - their profile, wallet history, stakes and watch history
  - their certificates, reviews and AI chats
  - their channel, uploads (including the stored files) and courses

Vote totals, view counts and subscriber numbers they contributed to stay, with no link to them. Learners who passed their courses keep their certificates.

Every response also carries security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`). API responses are marked `Cache-Control: no-store` so shared devices and proxies don't keep personal data.

## Before going live

- Set a long random `JWT_SECRET` and restrict `CORS_ORIGINS` to your domain (the server warns at startup if you don't).
- Turn off `SIMULATED_TOKEN_PURCHASE`.
- Replace the demo catalogue (`SEED_DEMO_DATA=false`) with your own content.
- Treat $LONO as in-app points unless you've taken legal advice on token regulation where you operate.
