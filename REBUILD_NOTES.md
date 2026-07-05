# LoNo — rebuild notes (2 Nov 2026)

## What was done
- Extracted project-backup_tar.gz (138 entries, no unsafe paths).
- Frontend: `yarn install` + `yarn build` → `frontend/build/` (compiled cleanly; main.js 280 kB gz, CSS 12 kB gz).
- Backend: dependencies installed in a venv, `server.py` imports cleanly, 32 `/api` routes registered.
  Smoke-tested against an in-memory Mongo: health, content (29 seeded items), rails, channels, live,
  search, tokenomics, governance, register/login/me, wallet, transactions, creator dashboard, stake → all 200.

## Changes made to the source
- `frontend/package.json`: removed devDependency `@emergentbase/visual-edits` (hosted on assets.emergent.sh,
  only reachable inside Emergent; it's the in-editor visual editing tool). `craco.config.js` already skips it when
  absent. `frontend/yarn.lock` regenerated accordingly. Nothing else in the source was modified.

## Running it outside Emergent
Backend (needs MongoDB):
    cd backend && python -m venv .venv && . .venv/bin/activate
    grep -v emergentintegrations requirements.txt | pip install -r /dev/stdin httpx
    pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/   # AI chat/summary only
    uvicorn server:app --host 0.0.0.0 --port 8001
Frontend:
    cd frontend && yarn install && yarn start      # or: yarn build && npx serve -s build

## Things to set before it works end-to-end
- `frontend/.env` REACT_APP_BACKEND_URL points at the old Emergent preview host; it is baked into the build
  at build time, so change it and rebuild for a new host.
- `backend/.env` MONGO_URL, CORS_ORIGINS, JWT_SECRET for your environment.
- Platform-tied features: AI chat/summarize (emergentintegrations + EMERGENT_LLM_KEY), Whisper transcription and
  file uploads (Emergent object storage at integrations.emergentagent.com), Google login (Emergent OAuth).
  These need the Emergent key or a swap to direct providers (e.g. Anthropic API, S3, Google OAuth).
- Stripe key is a placeholder (`sk_test_emergent`) — checkout returns 500 until a real test key is set.
- `.emergent/` holds Emergent pod cron/infra scripts; harmless but not used elsewhere.
