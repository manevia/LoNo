#!/usr/bin/env bash
# LoNo launcher for macOS/Linux.
#   ./start.sh             run locally with Python on http://localhost:8001 (no database needed)
#   ./start.sh --docker    run the full stack with Docker on http://localhost:8080
#   ./start.sh --broadcast also run the media server for live broadcasting (needs ffmpeg)
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
# Live broadcasting (optional: ./start.sh --broadcast)
MTX_PID=""
if [[ " $* " == *" --broadcast "* ]]; then
  command -v ffmpeg >/dev/null || fail "ffmpeg is needed for broadcasting (macOS: brew install ffmpeg; Debian/Ubuntu: sudo apt install ffmpeg)."
  V=v1.9.3
  case "$(uname -s)-$(uname -m)" in
    Linux-x86_64) A=linux_amd64.tar.gz; SHA=0b885dbfa4ef9c14cd00191c57d90d804255ff50403a28b85ceee7988c535b60 ;;
    Linux-aarch64|Linux-arm64) A=linux_arm64v8.tar.gz; SHA=f2f02109dd3d88773d7de5ae84385d41041bc9d60d0459eb6c61462cb2da0d1e ;;
    Darwin-x86_64) A=darwin_amd64.tar.gz; SHA=935ed174245004b425a93f6b7c1eac52310d833d4ebbca041d0f19195291eaf6 ;;
    Darwin-arm64) A=darwin_arm64.tar.gz; SHA=562b7f8fe24d9005510efe1d15589119a2bf4e77e6a4d3fe35b1d3f55c75263c ;;
    *) fail "No MediaMTX build is set up for $(uname -s) $(uname -m)." ;;
  esac
  MTX_DIR="$ROOT/tools/mediamtx"
  if [[ ! -x "$MTX_DIR/mediamtx" ]]; then
    say "Downloading the MediaMTX media server $V..."
    mkdir -p "$MTX_DIR"
    F="$MTX_DIR/mediamtx_${V}_$A"
    curl -fsSL -o "$F" "https://github.com/bluenviron/mediamtx/releases/download/$V/mediamtx_${V}_$A" || fail "Couldn't download MediaMTX."
    GOT=$( (command -v sha256sum >/dev/null && sha256sum "$F" || shasum -a 256 "$F") | cut -d' ' -f1)
    [[ "$GOT" == "$SHA" ]] || { rm -f "$F"; fail "The MediaMTX download didn't match LoNo's pinned checksum, so it was deleted."; }
    tar -xzf "$F" -C "$MTX_DIR" && rm -f "$F"
  fi
  LAN=$( (hostname -I 2>/dev/null || ipconfig getifaddr en0 2>/dev/null) | awk '{print $1}')
  LAN="${LAN:-127.0.0.1}"
  export MEDIA_ENABLED=true FFMPEG_BIN="$(command -v ffmpeg)" INGEST_RTMP_URL="rtmp://$LAN:1935/live" INGEST_SRT_URL="srt://$LAN:8890"
  export MTX_AUTHHTTPADDRESS="http://127.0.0.1:$PORT/api/broadcast/mtx/auth" MTX_WEBRTCADDITIONALHOSTS="$LAN"
  say "Starting the media server..."
  (cd "$MTX_DIR" && ./mediamtx "$ROOT/media/mediamtx.yml") &
  MTX_PID=$!
  trap '[[ -n "$MTX_PID" ]] && kill "$MTX_PID" 2>/dev/null' EXIT INT TERM
  sleep 1
  kill -0 "$MTX_PID" 2>/dev/null || fail "The media server stopped during startup. Scroll up for its message."
  say "Broadcasting on. Encoder server: rtmp://$LAN:1935/live (stream key in Creator Studio > Live Studio)"
fi

# Not "exec": the launcher stays to stop the media server when LoNo exits.
cd "$BACKEND" && FRONTEND_DIR="$FRONTEND/build" .venv/bin/python -m uvicorn server:app --port "$PORT"
