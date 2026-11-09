#!/usr/bin/env bash
# MediaMTX reads its RTMPS certificate at startup. Caddy renews the certificate
# automatically; restart the media server only when the certificate changed, at
# a quiet hour (daily cron 04:15). Live encoders reconnect within seconds.
set -euo pipefail
DEPLOY="${LONO_DEPLOY:-$(cd "$(dirname "$0")" && pwd)}"
set -a; . "$DEPLOY/.env"; set +a
[[ "${RTMPS:-no}" != "no" ]] || exit 0
COMPOSE=(docker compose -f "$DEPLOY/docker-compose.yml" --env-file "$DEPLOY/.env")
H="${LIVE_HOST:-$PUBLIC_HOST}"
CERT="/caddy/caddy/certificates/acme-v02.api.letsencrypt.org-directory/$H/$H.crt"
NOW="$("${COMPOSE[@]}" exec -T media sha256sum "$CERT" 2>/dev/null | cut -d' ' -f1 || true)"
STATE=/var/lib/lono-rtmps.sha; mkdir -p /var/lib
if [[ -n "$NOW" && "$NOW" != "$(cat "$STATE" 2>/dev/null || true)" ]]; then
  [[ -f "$STATE" ]] && "${COMPOSE[@]}" restart media && echo "$(date -Is) RTMPS certificate renewed; media server restarted"
  echo "$NOW" > "$STATE"
fi
