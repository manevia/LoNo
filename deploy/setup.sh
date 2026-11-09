#!/usr/bin/env bash
# One-time (and safe to repeat) setup of LoNo on an Ubuntu 22.04/24.04 server.
#   sudo ./deploy/setup.sh
# Needs: DNS for PUBLIC_HOST pointing at this server; ports 80 and 443 open to the internet.
set -euo pipefail
cd "$(dirname "$0")"
DEPLOY="$(pwd)"
say()  { printf '\033[36m[lono]\033[0m %s\n' "$*"; }
fail() { printf '\033[31m[lono] %s\033[0m\n' "$*" >&2; exit 1; }
COMPOSE=(docker compose -f "$DEPLOY/docker-compose.yml" --env-file "$DEPLOY/.env")

[[ $EUID -eq 0 ]] || fail "Run with sudo: sudo ./deploy/setup.sh"
. /etc/os-release 2>/dev/null || true
[[ "${ID:-}" == "ubuntu" ]] || say "Not Ubuntu (${PRETTY_NAME:-unknown}); continuing, but this script is tested for Ubuntu."

# 1. Settings with fresh secrets (never overwritten)
if [[ ! -f "$DEPLOY/.env" ]]; then
  cp "$DEPLOY/.env.example" "$DEPLOY/.env"
  for k in JWT_SECRET SECRET_ENC_KEY MEDIA_INTERNAL_SECRET; do
    sed -i "s|^$k=.*|$k=$(openssl rand -hex 32)|" "$DEPLOY/.env"
  done
  chmod 600 "$DEPLOY/.env"
  say "Created deploy/.env with new secrets. Review it (admin email, pilot mode), then run this again."
  exit 0
fi
set -a; . "$DEPLOY/.env"; set +a
[[ -n "${PUBLIC_HOST:-}" && -n "${JWT_SECRET:-}" ]] || fail "deploy/.env needs PUBLIC_HOST and JWT_SECRET."

# 2. DNS must point here, or Let's Encrypt can't issue the certificate
PUBLIC_IP="$(curl -fsS -4 --max-time 8 https://api.ipify.org || true)"
DNS_IP="$(getent ahostsv4 "$PUBLIC_HOST" | awk 'NR==1{print $1}' || true)"
if [[ -z "$DNS_IP" ]]; then
  fail "$PUBLIC_HOST doesn't resolve yet. Ask the ciu.edu.lr DNS administrator for an A record: $PUBLIC_HOST -> ${PUBLIC_IP:-the public IP of this server}"
elif [[ -n "$PUBLIC_IP" && "$DNS_IP" != "$PUBLIC_IP" ]]; then
  say "WARNING: $PUBLIC_HOST points to $DNS_IP but this server's public IP is $PUBLIC_IP."
  say "That's fine behind a NAT/firewall that forwards ports 80/443 here; otherwise fix the A record first."
fi

# 3. Docker
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  say "Installing Docker Engine..."
  curl -fsSL https://get.docker.com | sh
fi

# 4. Firewall (only if ufw is active)
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  say "Opening firewall ports..."
  for r in 22/tcp 80/tcp 443/tcp 443/udp 1935/tcp 1936/tcp 8890/udp 8189/udp; do ufw allow "$r" >/dev/null; done
fi

# 5. Build and start
say "Building and starting LoNo (first build takes several minutes)..."
"${COMPOSE[@]}" up -d --build
say "Waiting for https://$PUBLIC_HOST ..."
for _ in $(seq 1 60); do
  if curl -fsS --max-time 5 "https://$PUBLIC_HOST/api/health" >/dev/null 2>&1; then OK=1; break; fi
  sleep 5
done
[[ "${OK:-}" == 1 ]] || fail "LoNo didn't answer on https://$PUBLIC_HOST yet. Check: docker compose -f deploy/docker-compose.yml logs caddy backend"

# 6. RTMPS for encoders, once the certificate exists
CERT="/caddy/caddy/certificates/acme-v02.api.letsencrypt.org-directory/$PUBLIC_HOST/$PUBLIC_HOST.crt"
if [[ "${RTMPS:-no}" == "no" ]] && "${COMPOSE[@]}" exec -T media ls "$CERT" >/dev/null 2>&1; then
  sed -i "s|^RTMPS=.*|RTMPS=optional|; s|^INGEST_RTMPS_URL=.*|INGEST_RTMPS_URL=rtmps://$PUBLIC_HOST:1936/live|" "$DEPLOY/.env"
  "${COMPOSE[@]}" up -d media backend
  say "RTMPS enabled for encoders: rtmps://$PUBLIC_HOST:1936/live"
fi

# 7. Backups and certificate refresh
install -m 755 "$DEPLOY/backup.sh" /usr/local/bin/lono-backup
install -m 755 "$DEPLOY/rtmps-refresh.sh" /usr/local/bin/lono-rtmps-refresh
cat > /etc/cron.d/lono <<CRON
# LoNo: nightly database backup, weekly media backup, RTMPS certificate refresh
30 2 * * * root LONO_DEPLOY=$DEPLOY /usr/local/bin/lono-backup db >> /var/log/lono-backup.log 2>&1
45 3 * * 0 root LONO_DEPLOY=$DEPLOY /usr/local/bin/lono-backup media >> /var/log/lono-backup.log 2>&1
15 4 * * * root LONO_DEPLOY=$DEPLOY /usr/local/bin/lono-rtmps-refresh >> /var/log/lono-backup.log 2>&1
CRON

PW="$("${COMPOSE[@]}" logs backend 2>/dev/null | grep -A1 "admin account created" | grep -o "Temporary password: .*" | tail -1 || true)"
say "LoNo is live at https://$PUBLIC_HOST"
[[ -n "$PW" ]] && say "Admin ${ADMIN_EMAILS%%,*} - $PW (shown once; change it under Profile > Settings)"
say "Backups: /var/backups/lono (database nightly, media weekly). Logs: docker compose -f deploy/docker-compose.yml logs -f"
