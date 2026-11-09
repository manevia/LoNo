#!/usr/bin/env bash
# LoNo launcher for macOS/Linux.
#   ./start.sh             run locally with Python on http://localhost:8001 (no database needed)
#   ./start.sh --docker    run the full stack with Docker on http://localhost:8080
#   PORT=9000 ./start.sh   use another port
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"; BACKEND="$ROOT/backend"; FRONTEND="$ROOT/frontend"
PORT="${PORT:-8001}"
say() { printf '\033[36m[lono]\033[0m %s\n' "$*"; }
fail() { printf '\033[31m[lono]\033[0m %s\n' "$*"; exit 1; }
secret() { python3 -c 'import secrets;print(secrets.token_urlsafe(36))'; }

if [[ "${1:-}" == "--docker" ]]; then
  command -v docker >/dev/null || fail "Docker isn't installed."
  docker info >/dev/null 2>&1 || fail "Docker isn't running. Start Docker, then try again."
  if [[ ! -f "$BACKEND/.env.docker" ]]; then
    sed "s/^JWT_SECRET=.*/JWT_SECRET=$(secret)/" "$BACKEND/.env.docker.example" > "$BACKEND/.env.docker"
    say "Created backend/.env.docker with a fresh JWT secret."
  fi
  say "Building and starting containers; open http://localhost:8080 when the logs settle."
  cd "$ROOT" && exec docker compose up --build
fi

command -v python3 >/dev/null || fail "Python 3.10+ is required."
python3 -c 'import sys; sys.exit(sys.version_info < (3,10))' || fail "Python 3.10+ is required."
[[ -x "$BACKEND/.venv/bin/python" ]] || { say "Creating virtual environment..."; python3 -m venv "$BACKEND/.venv"; }
HASH="$(sha256sum "$BACKEND/requirements.txt" 2>/dev/null || shasum -a 256 "$BACKEND/requirements.txt")"; HASH="${HASH%% *}"
if [[ "$(cat "$BACKEND/.venv/.requirements.sha" 2>/dev/null)" != "$HASH" ]]; then
  say "Installing Python packages..."
  "$BACKEND/.venv/bin/python" -m pip install --disable-pip-version-check -q -r "$BACKEND/requirements.txt"
  echo "$HASH" > "$BACKEND/.venv/.requirements.sha"
fi
# Settings for local use: fill in any essential setting that's missing, keep the rest.
ENVF="$BACKEND/.env"
[[ -f "$ENVF" ]] || { printf '# Local settings. See .env.example for every option.\n' > "$ENVF"; NEW=1; }
added=()
for kv in "MONGO_URL=mongomock://" "DB_NAME=lono" "JWT_SECRET=$(secret)" "CORS_ORIGINS=*" \
          "PUBLIC_ORIGIN=http://localhost:$PORT" "STORAGE_BACKEND=local" \
          "ADMIN_EMAILS=msf@ciu.edu.lr" "SUPPORT_EMAIL=lono@ciu.edu.lr"; do
  key="${kv%%=*}"
  grep -qE "^[[:space:]]*$key[[:space:]]*=" "$ENVF" || { [[ -s "$ENVF" && $(tail -c1 "$ENVF" | wc -l) -eq 0 ]] && echo >> "$ENVF"; echo "$kv" >> "$ENVF"; added+=("$key"); }
done
if [[ -n "${NEW:-}" ]]; then say "Created backend/.env (in-memory database)."
elif (( ${#added[@]} )); then say "Added missing settings to backend/.env: ${added[*]}"; fi
# Rebuild the website when its code is newer than the last build (e.g. after git pull).
INDEX="$FRONTEND/build/index.html"
if [[ ! -f "$INDEX" ]] || [[ -n "$(find "$FRONTEND/src" "$FRONTEND/package.json" -newer "$INDEX" -type f -print -quit)" ]]; then
  if ! command -v node >/dev/null; then
    [[ -f "$INDEX" ]] || fail "Install Node.js 20 to build the website once, then run this again."
    say "Website code changed but Node.js isn't installed: you'll see the OLD website until you install Node.js 20."
  else
    say "Building the website (only when its code has changed)..."
    (cd "$FRONTEND" && npx --yes yarn@1.22.22 install --frozen-lockfile && CI=false npx --yes yarn@1.22.22 build)
  fi
fi
say "Starting LoNo at http://localhost:$PORT  (Ctrl+C to stop)"
cd "$BACKEND" && FRONTEND_DIR="$FRONTEND/build" exec .venv/bin/python -m uvicorn server:app --port "$PORT"
