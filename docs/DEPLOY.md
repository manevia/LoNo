# Putting LoNo on https://lono.ciu.edu.lr

Everything runs in Docker on one Linux server:
- **Caddy:** HTTPS, with automatic Let's Encrypt certificates and renewal.
- **The website and API.**
- **MongoDB.**
- **The live media server.**

Setup is one command once the server and DNS are ready.

## 1. What you need

**A server:** Ubuntu 22.04 or 24.04 with a **public IP address**.

| | Minimum | Recommended for the pilot and live events |
|---|---|---|
| CPU / RAM | 2 vCPU, 4 GB | 4 vCPU, 8 GB (live conversion and relays use CPU) |
| Disk | 80 GB | 250 GB+ (a full-match replay is about 1 to 2 GB; recordings add up) |
| Upload bandwidth | 50 Mbit/s | 200 Mbit/s+ |

**Bandwidth decides where to host.** Every viewer pulls their own stream, about 1.5 to 3 Mbit/s each, so:
- 100 fans watching the replay at once needs about 250 Mbit/s **outbound**.
- Each social destination in a simulcast needs a few Mbit/s more.

If the campus uplink can't sustain that, use a cloud server (any provider with Ubuntu VMs) and keep the `lono.ciu.edu.lr` name pointing to it. A CDN can be added later for larger audiences.

**DNS (Cloudflare).** `ciu.edu.lr` is managed in Cloudflare, so you add the record yourself: **Cloudflare dashboard → ciu.edu.lr → DNS → Records → Add record**.

**Option A: DNS only (recommended for the pilot).** One record:

| Type | Name | Content | Proxy status |
|---|---|---|---|
| A | `lono` | the server's public IP | **DNS only** (grey cloud) |

Everything works as built: the server gets its own Let's Encrypt certificate, uploads up to 4 GB work, and encoders and browser cameras connect to the same name. Keep `CLOUDFLARE_PROXY=false` in `deploy/.env`.

**Option B: Proxied (Cloudflare caching and DDoS protection for the website).** Two records:

| Type | Name | Content | Proxy status |
|---|---|---|---|
| A | `lono` | the server's public IP | **Proxied** (orange cloud) |
| A | `live.lono` | the server's public IP | **DNS only** (grey cloud) |

Then, in `deploy/.env`, set `CLOUDFLARE_PROXY=true` and `LIVE_HOST=live.lono.ciu.edu.lr`. Under **SSL/TLS → Overview**, set encryption to **Full (strict)**.

What changes in proxied mode:
- **Visitor addresses:** `setup.sh` downloads Cloudflare's current address ranges. Caddy then trusts the visitor address in `CF-Connecting-IP` **only** from those ranges, so per-address limits keep working and can't be spoofed.
- **Live ingest** (RTMP, RTMPS, SRT and browser cameras) uses `live.lono.ciu.edu.lr`, because Cloudflare's proxy only carries web traffic. Live Studio shows that address to creators automatically.
- **Uploads through Cloudflare's proxy are limited to 100 MB** on Free and Pro plans. Upload large files such as match replays at **https://live.lono.ciu.edu.lr**, which serves the same app without the proxy.
- **Cloudflare's CDN terms** restrict serving video that isn't stored on Cloudflare (Stream, Images or R2). In proxied mode, replays and on-demand videos would pass through Cloudflare's CDN from your server. **Start with Option A**, and switch to Option B once videos are stored in Cloudflare R2.

**Open ports.** In the cloud, set these in the provider's firewall or security group. On campus behind NAT, forward them to the server.

| Port | For |
|---|---|
| 80/tcp, 443/tcp, 443/udp | The website (HTTPS; 80 is needed for certificates) |
| 1935/tcp, 1936/tcp | RTMP and RTMPS from OBS, vMix and hardware encoders |
| 8890/udp | SRT from encoders |
| 8189/udp | Browser cameras and field reporters (WebRTC) |

Keep everything else closed. MongoDB, the API and the media server's control ports are never published. In proxied mode, ports 80 and 443 can additionally be limited to Cloudflare's address ranges, except for the live name, which needs them for its own certificate and uploads.

## 2. Install

On the server:

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/manevia/LoNo.git /opt/lono
cd /opt/lono
sudo ./deploy/setup.sh          # first run: creates deploy/.env with new secrets, then stops
sudo nano deploy/.env           # check: ADMIN_EMAILS, ACME_EMAIL, PILOT_MODE, SEED_DEMO_DATA
sudo ./deploy/setup.sh          # second run: installs Docker if needed, builds, starts, checks HTTPS
```

The second run:
1. Checks the DNS, and **stops with the exact record to add in Cloudflare** if something's missing. It also catches a record whose proxy status (orange or grey) doesn't match `CLOUDFLARE_PROXY`.
2. Opens the firewall ports if `ufw` is active.
3. Builds and starts everything, then waits until `https://lono.ciu.edu.lr` answers.
4. Turns on RTMPS for encoders once the certificate exists.
5. Installs **backups**: the database nightly (14 kept) and media weekly (2 kept) in `/var/backups/lono`, plus a daily RTMPS certificate refresh.
6. Prints the **one-time admin password** for `msf@ciu.edu.lr`. Sign in, then change it under Profile → Settings.

## 3. Check it

1. Open **https://lono.ciu.edu.lr**: the padlock should show a valid certificate.
2. Sign in as the admin, then open **https://lono.ciu.edu.lr/api/admin/request-info**:
   - `scheme` should be **https**
   - `client_ip` should be **your own public IP**, not a 172.x Docker address
3. **Admin → Overview** loads.
4. **Live broadcasting:** in Creator Studio → Live Studio → External encoder, the server shows `rtmp://lono.ciu.edu.lr:1935/live` (and RTMPS). A private test from OBS shows "connected".
5. **Phone camera:** on a phone, open a Control Room invitation link. The camera works now that the site is https.

## 4. Settings worth knowing (`deploy/.env`)

| Setting | Meaning |
|---|---|
| `PILOT_MODE=true` | The commercial pilot rules for $LONO (see PILOT-OPERATOR-GUIDE.md) |
| `SEED_DEMO_DATA=false` | Start with an empty catalogue. `true` adds demo titles that stream from the internet |
| `MAX_UPLOAD_MB=4096` | Largest upload; uploads stream to disk, so large files don't use memory |
| `GOOGLE_CLIENT_ID` | Google sign-in. In Google Cloud Console, add `https://lono.ciu.edu.lr` as an authorised JavaScript origin |
| `ANTHROPIC_API_KEY`, `TRANSCRIBE_API_KEY` | AI assistant and captions |
| `ANDROID_APP_PACKAGE`, `ANDROID_CERT_SHA256` | For the Play Store app (TWA) |
| `MONGO_CACHE_GB` | About a quarter of the server's RAM |

After changing `deploy/.env`: `sudo docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d`

## 5. Everyday operations

```bash
cd /opt/lono
# Update to the latest version (recommended right after a backup)
sudo lono-backup db && git pull && sudo docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build

# Logs
sudo docker compose -f deploy/docker-compose.yml logs -f backend caddy

# Restore the database from a backup
sudo docker compose -f deploy/docker-compose.yml exec -T mongo mongorestore --archive --gzip --drop < /var/backups/lono/mongo-YYYYMMDD-HHMM.archive.gz
```

- **Off-site backups:** copy `/var/backups/lono` to another machine or storage regularly. A backup on the same disk doesn't survive a disk failure.
- **Certificates** renew automatically. Let's Encrypt emails `ACME_EMAIL` only if renewal keeps failing.
- **Updates:** live broadcasts and the Control Room depend on the API process, so update outside live events.

## 6. The TV apps and phones

- The Samsung (Tizen), LG (webOS) and Android TV packages in `apps/` already use `https://lono.ciu.edu.lr/?tv=1`, so they can be built and installed now (see `docs/DEVICES.md`).
- Phones can **install LoNo** from the browser (Add to Home Screen).
- The **phase 4 real-world tests** (`docs/REAL-WORLD-TESTS.md`) can now include phones as reporters.

## How this was tested

I couldn't reach CIU's servers from the development sandbox, so the production stack was tested locally:
- the same Caddyfile (validated by Caddy 2.8.4), with a local test certificate instead of Let's Encrypt
- the same nginx configuration (nginx 1.24)
- the API started with the production container's flags
- a real MongoDB 7.0

Checks that passed:
- **HTTPS and headers:** the page over HTTPS, with HSTS; http redirects to https; app deep links and service-worker caching.
- **What the API sees:** **`https` as the scheme**, and a client's **forged `X-Forwarded-For` and `X-Forwarded-Proto` discarded** by Caddy. The API uses the first forwarded address, which Caddy writes from the real connection.
- **Large uploads:** **a 600 MB upload streamed through all three layers in 5 s, with the API's memory flat** (81 → 84 MB), and range requests for seeking worked.
- The deployment scripts pass `bash -n` and ShellCheck.

- **Cloudflare proxy mode, through the same chain:**
  - a request from a trusted Cloudflare address carrying `CF-Connecting-IP: 9.9.9.9` and a forged `X-Forwarded-For` → the API saw **9.9.9.9**
  - the same headers from an untrusted address, or with proxy mode off → **both ignored**

**Not tested:**
- **On real infrastructure:** Docker Compose itself (not available in the sandbox), real Let's Encrypt issuance, the DNS check, the firewall rules, and the backup and RTMPS-refresh jobs.
- **Real visitors' addresses** reaching the API. Locally, every hop shares 127.0.0.1, so step 3's `request-info` check on the server is the real test.
