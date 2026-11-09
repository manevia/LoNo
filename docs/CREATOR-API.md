# LoNo Creator API (v1)

Lets approved tools manage a creator's broadcasts: newsroom schedulers, sports graphics systems, church media teams, automations.
- **The API manages sessions and production.** Audio and video never pass through it; they go from the encoder or Live Studio to LoNo's ingest.
- **It follows the same rules as Creator Studio.** An integration can only do what its creator could do, limited further by the scopes it was given.

- **Interactive reference:** `https://<your LoNo>/api/docs` (section "creator api v1")
- **Base URL:** `https://<your LoNo>/api/v1`
- **Auth:** `Authorization: Bearer lk_<live|test>_<integration-id>.<secret>`

## Getting credentials

In **Creator Studio → Developer Access → New integration**, choose:
- a **name**
- **Environment:**
  - **Test**: a private test environment. Sessions are always private tests: not public, not simulcast, not recorded, and they can't be started as public broadcasts.
  - **Live**: real broadcasts.
- **Permissions** (scopes):

| Scope | Allows |
|---|---|
| `sessions:read` | Read sessions, health and events |
| `sessions:write` | Create sessions; update them before they go live |
| `broadcast:control` | Start and stop broadcasts; retry a destination |
| `ingest:read` | Read ingest URLs **and the stream key** (grant only to encoder tools) |
| `destinations:read` | List connected destinations (never their keys) |
| `recordings:read` | List recordings and their files |
| `rooms:read` | Read Control Rooms and each source's status |
| `rooms:write` | Create rooms and contributor invitations |
| `production:control` | Preview, take, program, fallback, cue, mute and remove sources |

- **Webhook URL** (optional): must be **public https**. Private, loopback and link-local addresses are refused to protect the server.

The **token** and **webhook secret** are shown **once**; LoNo stores only a hash of the token.
- **Rotating:** **New token** replaces the token (the old one stops at once). There's also **New webhook secret**.
- **Revoking** cuts off all access.
- **Rate limit:** 120 requests per minute per integration (`429` beyond that).
- **Audit:** every write is recorded in the audit log as "API: <integration name>".

## Safe retries

- **`POST /sessions`** accepts an **`Idempotency-Key`** header. Sending the same key again returns the same session instead of creating a second one, so a timeout followed by a retry is safe.
- **`POST /sessions/{id}/start` and `/stop` are safe to repeat.** Starting a live session, or stopping an ended one, returns it unchanged and sends no second command to the destinations.

## Errors

JSON `{"detail": "…"}` with:

| Status | Meaning |
|---|---|
| `401` | Bad or revoked token |
| `403` | Missing scope |
| `404` | Not found, or not yours |
| `409` | Wrong state (for example, no feed yet, already ended, or test credentials starting a public broadcast) |
| `422` | Invalid input |
| `429` | Rate limit |
| `503` | Broadcasting is off on this server |

## Example 1: schedule a broadcast

```bash
curl -X POST "$LONO/api/v1/sessions" \
  -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: match-2026-12-01" -H "Content-Type: application/json" \
  -d '{"title": "County Meet Final", "category": "Sports", "kind": "live_tv",
       "destination_ids": ["<youtube-destination-id>", "<facebook-destination-id>"],
       "record": true, "scheduled_for": "2026-12-01T18:00:00+00:00"}'
```

The session waits for a feed. Change it before air time with `PATCH /api/v1/sessions/{id}` (title, description, category, destinations, record, scheduled_for). Then, when the feed is connected, start it:

```bash
curl -X POST "$LONO/api/v1/sessions/$SESSION/start" -H "Authorization: Bearer $TOKEN"
```

## Example 2: connect an encoder

```bash
curl "$LONO/api/v1/ingest" -H "Authorization: Bearer $TOKEN"     # needs ingest:read
```

```json
{"rtmp": {"server": "rtmp://live.example.org:1935/live", "stream_key": "in…?key=lk_…"},
 "rtmps": {"server": "rtmps://live.example.org:1936/live", "stream_key": "in…?key=lk_…"},
 "srt": {"url": "srt://live.example.org:8890?streamid=publish:live/in…:in…:lk_…"}}
```

Put `server` and `stream_key` into the encoder: OBS, vMix, Wirecast or hardware (H.264 video, AAC audio, 2 s keyframes).

## Example 3: check destination health

```bash
curl "$LONO/api/v1/sessions/$SESSION/health" -H "Authorization: Bearer $TOKEN"
```

```json
{"status": "live",
 "feed": {"ready": true, "tracks": ["H264", "MPEG-4 Audio"], "bitrate_kbps": 4480, "converted": false},
 "destinations": [
   {"platform": "youtube", "name": "YouTube Live", "state": "live", "error": null, "attempts": 1, "auto_retries": 0},
   {"platform": "facebook", "name": "Facebook Live", "state": "failed", "error": "The destination rejected the stream key. Copy a fresh key from the platform.", "attempts": 1}]}
```

**Destination states:**

| State | Meaning |
|---|---|
| `connecting` | Starting to send |
| `live` | Sending |
| `retrying` | Dropped after being live; LoNo reconnects by itself, up to 3 times |
| `failed` | See `error` |
| `waiting` | The feed dropped; resumes when it returns |
| `stopped` | Ended |

To retry one destination without touching the others: `POST /api/v1/sessions/{id}/destinations/{destination_id}/retry`.

## Example 4: receive webhooks

**Events:**
- `stream.connected`, `stream.disconnected`
- `broadcast.started`, `broadcast.ended`
- `destination.live`, `destination.failed`, `destination.reconnecting`
- `recording.ready`
- `scene.changed`
- `source.connected`, `source.disconnected`
- `contributor.joined`, `contributor.left`, `contributor.cue`, `contributor.remove`
- `ping` (sent by `POST /api/v1/webhooks/test`)

```http
POST /your/webhook HTTP/1.1
Content-Type: application/json
LoNo-Event-Id: 2f6c…            (unique: ignore events you've already processed)
LoNo-Event: destination.failed
LoNo-Signature: t=1794240000,v1=5b1c…

{"id":"2f6c…","type":"destination.failed","created_at":"2026-12-01T18:04:11+00:00",
 "data":{"session_id":"…","destination_id":"…","platform":"facebook","error":"…"}}
```

- **Signature:** `v1` is the hex HMAC-SHA256 of `"<t>.<raw body>"`, keyed with your webhook secret. Reject requests whose `t` is more than 5 minutes old.
- **Responses and retries:** answer `2xx` within 10 s. Failures are retried after 2 s, 10 s and 30 s; each attempt appears under **Deliveries** in Developer Access.
- **Never in payloads:** stream keys, invitation links or social keys.

**Python (FastAPI)**

```python
import hashlib, hmac, time
from fastapi import FastAPI, Request, HTTPException

SECRET = "whsec_…"
app = FastAPI()

@app.post("/lono")
async def lono(request: Request):
    body = await request.body()
    parts = dict(p.split("=", 1) for p in request.headers.get("LoNo-Signature", "").split(","))
    t = int(parts.get("t", "0"))
    expected = hmac.new(SECRET.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    if abs(time.time() - t) > 300 or not hmac.compare_digest(expected, parts.get("v1", "")):
        raise HTTPException(400, "bad signature")
    event = await request.json()
    if event["type"] == "destination.failed":
        ...  # alert the producer
    return {"ok": True}
```

**Node.js (Express)**

```js
const crypto = require("crypto");
const express = require("express");
const SECRET = "whsec_…";
const app = express();
app.post("/lono", express.raw({ type: "application/json" }), (req, res) => {
  const parts = Object.fromEntries((req.get("LoNo-Signature") || "").split(",").map((p) => p.split("=")));
  const expected = crypto.createHmac("sha256", SECRET).update(`${parts.t}.`).update(req.body).digest("hex");
  const fresh = Math.abs(Date.now() / 1000 - Number(parts.t)) <= 300;
  if (!fresh || !parts.v1 || !crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(parts.v1))) return res.sendStatus(400);
  const event = JSON.parse(req.body);
  res.sendStatus(200);
});
app.listen(3000);
```

## Control Room endpoints

| Method | Path | Scope |
|---|---|---|
| GET / POST | `/rooms` | rooms:read / rooms:write |
| GET | `/rooms/{id}`: each source's `state` (invited/waiting/cued/on_air/left), `connected`, `tracks`, `audio_only`, `muted` | rooms:read |
| POST | `/rooms/{id}/invites` `{name, role, type: browser|encoder, location, show_location, expires_in_minutes}`: returns the join link or encoder details (keep them private) | rooms:write |
| POST | `/rooms/{id}/contributors/{cid}` `{action: cue|uncue|mute|unmute|remove|show_location|hide_location, message}` | production:control |
| PUT | `/rooms/{id}/preview`, `/rooms/{id}/program` `{scene: single|split|clip|standby, sources, clip_url}` | production:control |
| POST | `/rooms/{id}/take`, `/rooms/{id}/fallback` | production:control |

The producer's Control Room renders whatever the room state says, so a scene changed through the API appears in the program within about a second.

## Recordings

- **`GET /recordings`** and **`GET /recordings/{id}`** return `status` (processing/ready/failed), `visibility` (private/scheduled/public), `duration_sec`, `size` and `url`.
- **Downloading:** each also includes **`download_url`**, a signed link valid for one hour. Private and scheduled recordings can't be downloaded without it; published ones play openly. Publishing stays a creator decision in Creator Studio.
- **`recording.ready`** fires when a recording can be fetched.
