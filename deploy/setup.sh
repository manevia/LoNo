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

# 2. DNS and Cloudflare
LIVE_HOST="${LIVE_HOST:-$PUBLIC_HOST}"
PUBLIC_IP="$(curl -fsS -4 --max-time 8 https://api.ipify.org || true)"
resolve() { getent ahostsv4 "$1" | awk 'NR==1{print $1}' || true; }
CF_V4="$(curl -fsS --max-time 10 https://www.cloudflare.com/ips-v4 || true)"
CF_V6="$(curl -fsS --max-time 10 https://www.cloudflare.com/ips-v6 || true)"
is_cloudflare() {   # is this IPv4 address one of Cloudflare's?
  [[ -n "$CF_V4" ]] && python3 -c "import ipaddress,sys; ip=ipaddress.ip_address(sys.argv[1]); sys.exit(0 if any(ip in ipaddress.ip_network(n.strip()) for n in sys.argv[2].split() if n.strip()) else 1)" "$1" "$CF_V4"
}
PUB_DNS="$(resolve "$PUBLIC_HOST")"
[[ -n "$PUB_DNS" ]] || fail "$PUBLIC_HOST doesn't resolve yet. In Cloudflare DNS for the domain, add: A  $PUBLIC_HOST -> ${PUBLIC_IP:-the public IP of this server}  (Proxy status: DNS only, to start)"

if [[ "${CLOUDFLARE_PROXY:-false}" == "true" ]]; then
  [[ "$LIVE_HOST" != "$PUBLIC_HOST" ]] || fail "Behind the Cloudflare proxy, live ingest needs its own DNS-only name. Set LIVE_HOST (e.g. live.$PUBLIC_HOST) in deploy/.env and add: A  live.$PUBLIC_HOST -> ${PUBLIC_IP:-this server} (DNS only)."
  [[ -n "$CF_V4" ]] || fail "Couldn't download Cloudflare's address list (https://www.cloudflare.com/ips-v4). Check internet access and try again."
  is_cloudflare "$PUB_DNS" || say "WARNING: $PUBLIC_HOST resolves to $PUB_DNS, not Cloudflare. Turn the record to Proxied (orange cloud), or set CLOUDFLARE_PROXY=false."
  LIVE_DNS="$(resolve "$LIVE_HOST")"
  [[ -n "$LIVE_DNS" ]] || fail "$LIVE_HOST doesn't resolve. In Cloudflare DNS add: A  $LIVE_HOST -> ${PUBLIC_IP:-this server}  (Proxy status: DNS only)."
  ! is_cloudflare "$LIVE_DNS" || fail "$LIVE_HOST is proxied by Cloudflare. Set its record to DNS only (grey cloud): encoders and browser cameras can't connect through the proxy."
  { echo "# Written by setup.sh from https://www.cloudflare.com/ips-v4 and ips-v6 ($(date -u +%F))"
    echo "servers {"
    echo "	trusted_proxies static $(echo $CF_V4 $CF_V6)"
    echo "	client_ip_headers CF-Connecting-IP"
    echo "}"; } > "$DEPLOY/caddy.d/cloudflare.caddy"
  cat > "$DEPLOY/sites.d/live.caddy" <<SITE
# Live ingest name (DNS only). Also serves the app unproxied, so staff can upload files larger
# than Cloudflare's 100 MB limit at https://$LIVE_HOST.
$LIVE_HOST {
	encode zstd gzip
	header Strict-Transport-Security "max-age=31536000"
	reverse_proxy web:80 {
		header_up X-Forwarded-For {client_ip}
		flush_interval -1
	}
}
SITE
  say "Cloudflare proxy mode: set SSL/TLS encryption to 'Full (strict)' for the domain in the Cloudflare dashboard."
else
  rm -f "$DEPLOY/caddy.d/cloudflare.caddy" "$DEPLOY/sites.d/live.caddy"
  if is_cloudflare "$PUB_DNS"; then
    fail "$PUBLIC_HOST is Proxied by Cloudflare (orange cloud) but CLOUDFLARE_PROXY=false. Either set the record to DNS only, or set CLOUDFLARE_PROXY=true and LIVE_HOST in deploy/.env."
  elif [[ -n "$PUBLIC_IP" && "$PUB_DNS" != "$PUBLIC_IP" ]]; then
    say "WARNING: $PUBLIC_HOST points to $PUB_DNS but this server's public IP is $PUBLIC_IP."
    say "That's fine behind a NAT/firewall that forwards ports 80/443 here; otherwise fix the A record first."
  fi
fi
# What creators paste into encoders always uses the live name
sed -i "s|^INGEST_RTMP_URL=.*|INGEST_RTMP_URL=rtmp://$LIVE_HOST:1935/live|; s|^INGEST_SRT_URL=.*|INGEST_SRT_URL=srt://$LIVE_HOST:8890|" "$DEPLOY/.env"
if grep -q "^RTMPS=optional" "$DEPLOY/.env"; then sed -i "s|^INGEST_RTMPS_URL=.*|INGEST_RTMPS_URL=rtmps://$LIVE_HOST:1936/live|" "$DEPLOY/.env"; fi

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
CERT="/caddy/caddy/certificates/acme-v02.api.letsencrypt.org-directory/$LIVE_HOST/$LIVE_HOST.crt"
if [[ "${RTMPS:-no}" == "no" ]] && "${COMPOSE[@]}" exec -T media ls "$CERT" >/dev/null 2>&1; then
  sed -i "s|^RTMPS=.*|RTMPS=optional|; s|^INGEST_RTMPS_URL=.*|INGEST_RTMPS_URL=rtmps://$LIVE_HOST:1936/live|" "$DEPLOY/.env"
  "${COMPOSE[@]}" up -d media backend
  say "RTMPS enabled for encoders: rtmps://$LIVE_HOST:1936/live"
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
