# Broadcasting and simulcasting

Creators send a live feed to LoNo. LoNo can:

- show it on LoNo's Live TV (or Radio),
- forward it to their social destinations at the same time,
- record it.

Status: **phases 1 to 3 of 4 done** (broadcast core, Live Studio with Devices & Sources, Creator API). Phase 4 is real-world verification. The Live Control Room is described in [CONTROL-ROOM.md](CONTROL-ROOM.md).

| Phase | Scope | Status |
|---|---|---|
| 1 | Ingest (RTMP / RTMPS / SRT), rotatable stream key, private test sessions, go live on LoNo, simulcast with per-destination status and retry, encoder reconnect, recording with an explicit publish choice | **Done (API)** |
| 2 | **Live Studio** (Creator Studio → Open Live Studio): Devices & Sources, external encoder settings, destinations, private test with preview, Go live, per-destination status and Retry, activity log, End, recordings | **Done** |
| 3 | Creator API: scoped credentials, signed webhooks, docs and examples, test environment (see [CREATOR-API.md](CREATOR-API.md)) | **Done** |
| 4 | End-to-end verification with real encoders (OBS Studio and others), hardware and platforms: checklist in [REAL-WORLD-TESTS.md](REAL-WORLD-TESTS.md) | Waiting for on-site testing |

## How it works

```
Encoder (OBS, vMix, Streamlabs, Wirecast, hardware)  ──RTMP/RTMPS/SRT──┐
Creator Studio camera/mic (phase 2)                  ──WebRTC (WHIP)───┤
                                                                       ▼
                                     MediaMTX media server  (path live/<ingest-id>)
                        asks LoNo's API whether the stream key is valid (authMethod: http)
                                             │
              ┌──────────────────────────────┼─────────────────────────────┐
              ▼                              ▼                             ▼
     HLS → LoNo API /media/hls      ffmpeg relay per destination     ffmpeg recorder
     (Live TV players, private      (YouTube, Facebook, Twitch, ...;  (fragmented MP4 parts,
      preview with a signed link)    stream copy, no re-encoding)      joined when it ends)
```

- **Destinations are independent.** Each one has its own ffmpeg process. When one fails, the others keep running, and **Retry** restarts only that one.
- **Encoder reconnects:** the API checks the media server every 2 s. If the feed drops, destinations wait; when it returns, they all resume, and recording continues in a new part.
- **Viewers never touch the broadcast.** They only read HLS through `/media/hls`, so switching channels or leaving the player can't affect delivery.
- **Stream keys:**
  - stored encrypted (Fernet; key from `SECRET_ENC_KEY`, or derived from `JWT_SECRET`)
  - never returned after saving (only a hint like `…1234`)
  - removed from error messages
  - kept out of the API's and the media server's logs

## Live Studio (Creator Studio → Open Live Studio)

**Devices & Sources: "This device"**
- **Inputs:** cameras, microphones, USB audio interfaces and capture cards (Elgato, Magewell, Blackmagic and other UVC/UAC devices, which appear as cameras and microphones), with live preview, resolution and fps.
- **Setup:** creators can rename devices and choose a quality (480p, 720p or 1080p). Choices are remembered on the device.
- **Audio:** an audio meter (dBFS, with peak hold and clipping warning) and mute.
- **Monitoring:** choose headphones or speakers where the browser allows output selection (Chrome and Edge do; Safari and Firefox use the system output). Monitoring plays a separate copy of the mic to that output only, never into the broadcast.
- **Switching sources while live** replaces the track without reconnecting.
- **Unplugging a device:** a warning appears with **Reconnect**, or the creator chooses a replacement. The broadcast keeps running.
- **Behind the scenes:** the browser sends WebRTC (WHIP) to LoNo's API, which adds the stream key server-side, so the key never reaches the browser.
- **Browser codecs:** browsers send Opus audio and often VP8 video. LoNo converts these **once** to H.264/AAC (`tx/<ingest>`), and LoNo viewers, the preview, destinations and the recording all use that copy. Encoder feeds that are already H.264/AAC aren't converted.

**External encoder:** server URLs (RTMP / RTMPS / SRT), the stream key (masked, with Show, Copy and New stream key), and setup steps for OBS Studio, vMix, Streamlabs, Wirecast and hardware encoders and mixers.

**Test Setup** checks:
- **Framing:** resolution and fps, plus a rule-of-thirds grid.
- **Audio levels:** a 5-second measurement giving good, too quiet or clipping.
- **Audio/video sync:** a clap check against the private preview, confirmed by the creator. LoNo doesn't measure sync automatically.
- **Connection:** outgoing bitrate, round trip and packet loss from WebRTC stats, or the encoder feed's bitrate.

**Broadcast:**
- **Before going live:** title, description, TV or Radio, Record, and the destinations to send to. A **private test** shows "What LoNo receives" (preview, tracks, bitrate) without publishing or simulcasting.
- **Go live:** ends the test, starts the broadcast once the feed is connected, then shows each destination's status, error and **Retry**, plus an activity log.
- **End broadcast:** stops LoNo and every destination.
- **Recordings:** private until **Publish now**, **Schedule**, or **Make private**.

## Running it

**Docker (recommended):** `start.cmd -Docker` / `bash start.sh --docker` starts MongoDB, the API (with ffmpeg), the website and the media server. Open these ports to creators:

| Port | Use |
|---|---|
| 1935/tcp | RTMP |
| 1936/tcp | RTMPS (after adding a certificate) |
| 8890/udp | SRT |
| 8889/tcp and 8189/udp | Browser camera ingest (phase 2) |

Set these in `backend/.env.docker`:

```
INGEST_RTMP_URL=rtmp://live.your-domain/live
INGEST_RTMPS_URL=rtmps://live.your-domain:1936/live
INGEST_SRT_URL=srt://live.your-domain:8890
```

**RTMPS:** put `server.crt` and `server.key` (for example, from Let's Encrypt) in `media/certs/`, then set `rtmpEncryption: optional` in `media/mediamtx.yml`.

**Local mode (launcher):** add one option to turn broadcasting on:

```
start.cmd -Broadcast          (Windows)
./start.sh --broadcast        (Linux / macOS)
```

The launcher then:

1. Downloads **MediaMTX 1.9.3** into `tools/mediamtx/` the first time, and checks it against SHA-256 checksums pinned in the launcher (that release publishes none). A mismatch deletes the file and stops.
2. Finds **ffmpeg**. On Windows it installs it with `winget install Gyan.FFmpeg` if it's missing. On macOS run `brew install ffmpeg`; on Debian/Ubuntu, `sudo apt install ffmpeg`.
3. Finds this computer's **network address**, so OBS or other computers on the same network can send to it. Live Studio shows that address as the encoder server.
4. Starts the media server with LoNo. **Ctrl+C stops both.**

**Firewall:** Windows asks once about `mediamtx.exe`. Allow it on **private** networks. These ports are used: 1935 (RTMP), 8890/udp (SRT), 8889 and 8189/udp (browser cameras), and 8888 (HLS, local only).

**Phones** need LoNo on an **https** address. Phone browsers only allow the camera on secure pages; `localhost` counts as secure, but a computer's network address doesn't. Laptops can join on `http://localhost` from the same computer, or through an https address.

## Settings for encoders

Creators find these in Creator Studio (phase 2), or at `GET /api/broadcast/ingest`:

| Encoder field | Value |
|---|---|
| Service | Custom |
| Server | `INGEST_RTMP_URL` (or RTMPS) |
| Stream key | `<ingest-id>?key=<secret>`, exactly as shown |
| SRT (OBS, vMix, hardware) | `srt://host:8890?streamid=publish:live/<ingest-id>:<ingest-id>:<secret>` |
| Video | H.264, keyframe every 2 s, 2,500 to 6,000 kbps (720p/1080p) |
| Audio | AAC, 128 to 160 kbps, 48 kHz |

The relays copy the stream without re-encoding, so the encoder settings are what every destination receives. Use settings all your destinations accept; H.264 and AAC are accepted everywhere.

**Rotating the key** (`POST /api/broadcast/ingest/rotate`) makes the old key stop working straight away. It's blocked while a broadcast is live.

## Destinations

These are the 10 destinations in Creator Studio. Connect each by **server URL and stream key**, as OBS does. Signing in to an account (OAuth) would need LoNo to be an approved app with each platform; that isn't built.

| Destination | Supported | Protocol | Where to get the URL and key |
|---|---|---|---|
| YouTube Live | Yes | RTMP / RTMPS | YouTube Studio → Go live → Stream |
| Facebook Live | Yes | **RTMPS only** | Live video → Streaming software |
| Twitch | Yes | RTMP / RTMPS | Creator Dashboard → Settings → Stream |
| Kick | Yes | RTMPS | Dashboard → Settings → Stream URL & Key |
| X Live | Yes, for accounts with Media Studio Producer | RTMP / RTMPS | Media Studio → Producer → Sources |
| TikTok Live | Yes, for accounts given a stream key | RTMP | LIVE Center / LIVE Studio |
| LinkedIn Live | Yes, for accounts with LinkedIn Live access | RTMPS | Live event → Custom stream |
| Instagram Live | Yes, for professional accounts | RTMPS | Live Producer; keys last for one broadcast |
| Discord | **No**: Discord has no stream-key ingest | none | Share the LoNo link instead |
| Custom RTMP / RTMPS / SRT | Yes | RTMP / RTMPS / SRT | Any compatible server or CDN |

## Recording

Turn on **Record** when creating a broadcast. When it ends, the recording is assembled (joining parts across encoder reconnects) and saved **privately**. The creator then chooses:

- **publish now:** it becomes an on-demand title on their channel
- **schedule:** it's published at a time with a time zone
- **keep it private:** this also unpublishes a title that was already published

## API (phase 1, signed-in creator)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/broadcast/ingest` | Ingest URLs and stream key |
| POST | `/api/broadcast/ingest/rotate` | New stream key |
| GET | `/api/broadcast/platforms` | The 10 destinations and what each needs |
| GET/POST/DELETE | `/api/broadcast/destinations` | The creator's destinations (keys write-only) |
| POST | `/api/broadcast/sessions` | Create a session `{title, kind, test, destination_ids, record}`. Send `Idempotency-Key` to make retries safe |
| GET | `/api/broadcast/sessions/current`, `/{id}` | Status: feed (tracks, bitrate), each destination's state and error, recorder, preview URL |
| POST | `/api/broadcast/sessions/{id}/start` | Go live (needs a connected feed; safe to repeat) |
| POST | `/api/broadcast/sessions/{id}/stop` | End (safe to repeat) |
| POST | `/api/broadcast/sessions/{id}/destinations/{dest}/retry` | Restart one destination |
| GET | `/api/broadcast/sessions/{id}/events` | `broadcast.started/ended`, `stream.connected/disconnected`, `destination.live/failed`, `recording.ready` |
| GET | `/api/broadcast/recordings` | Recordings |
| POST | `/api/broadcast/recordings/{id}/publish` | `{when: now \| schedule \| private, publish_at}` |

## Testing

`scripts/broadcast/integration_test.py` runs the real pipeline, with no mocks:

- LoNo's MediaMTX and API
- ffmpeg as the encoder
- two extra MediaMTX instances posing as platforms (`scripts/broadcast/standin_*.yml`)

Fast API tests with a faked media server (`backend/tests/test_broadcast.py`) run in CI.

### Phase 1 test report (Nov 2026, sandbox)

**Environment:**
- Ubuntu 24 (container)
- MediaMTX 1.9.3
- ffmpeg 6.1 (libx264 / AAC encoder, relays and recorder)
- Python 3.12 API with the in-memory database

**Result:** 38 of 38 checks passed, covering:
- **Ingest:**
  - ingest details for RTMP, RTMPS and SRT
  - wrong key refused; old key refused after rotation
  - RTMP, RTMPS and SRT ingest
- **Destinations:**
  - 10 destinations listed; Discord refused; Facebook requires RTMPS
  - stored keys never returned
- **Private test session:**
  - preview data: H.264 + AAC tracks, about 2.7 Mbit/s
  - signed preview playlist
  - not public, not listed on Live, nothing sent to destinations
- **Going live:**
  - idempotent session creation; go live twice safely
  - listed on Live TV; public HLS served
- **Simulcast:**
  - simultaneous delivery to stand-ins for YouTube (RTMP), Facebook (RTMPS) and Custom SRT
  - unreachable destination fails with a readable message while the others keep running
  - targeted retry fixes only that destination
  - viewer activity has no effect on delivery
- **Encoder drop and reconnect:** destinations wait, then all resume.
- **Events:** recorded.
- **Key rotation:** blocked while live.
- **Ending:** end twice safely; page removed and destinations stopped.
- **Recording:**
  - 22 s recording from 2 parts, private by default, range download works
  - publish now, back to private, schedule
- **Logs:** no stream keys in the API or media server logs.

### Phase 2 test report (Nov 2026, sandbox)

The solo-creator workflow was tested in a browser (Playwright, Chromium 141) using Chromium's **simulated camera and microphone** (`--use-fake-device-for-media-stream`). No real camera, microphone or headset was used.

**Result:** 23 of 24 checks passed.
- **Devices and Test Setup:**
  - camera preview at 1280×720, device lists
  - microphone meter moving
  - renaming a device, mute, monitoring playback
  - Test Setup level, framing and connection checks
- **Destinations:** adding YouTube, Facebook and Twitch through the UI; Discord can't be chosen.
- **Private test:**
  - the camera reaches LoNo over WebRTC (VP8 + Opus)
  - nothing sent to destinations
- **Live:**
  - go live from the Studio, with the YouTube (RTMP) and Facebook (RTMPS) stand-ins live
  - Twitch failing while the others continue, with its error and Retry, and Retry bringing only Twitch live
  - a **separate TV viewer** opening the broadcast, switching channels with Channel Up/Down and leaving, with no effect on any destination
  - a camera disconnect shown, then reconnected while staying live
- **End and recording:**
  - ending stops LoNo and all destinations
  - recording private by default, then published
- **Logs:** no stream keys.

**The 1 failed check:** the private preview showed no picture. The sandbox Chromium can't decode H.264 (it lacks proprietary codecs), and the converted preview is H.264. `ffprobe` confirmed the preview carries H.264 video and AAC audio, converted from a VP8 + Opus source. Chrome, Edge, Safari and smart TVs decode H.264.

**Also found and fixed in this phase:** the security header from release 2.4 (`Permissions-Policy: camera=()`) blocked LoNo's own pages from using the camera and microphone. It now allows them for LoNo only (`camera=(self)`).

**Not tested yet:**

| Area | Not yet tested |
|---|---|
| **Real social platforms** | None of YouTube, Facebook, Twitch, Kick, X, TikTok, LinkedIn or Instagram. Delivery was verified against stand-in servers using the same protocols. Real platforms need the creator's account and stream key |
| **Discord** | Can't be supported (no ingest) |
| **Encoders** | **OBS Studio, vMix, Streamlabs, Wirecast:** none tested (no desktop available); planned for phase 4. Only ffmpeg was used, over RTMP, RTMPS and SRT |
| **Hardware** | No real cameras, microphones, headsets, capture cards or mixers; only Chromium's simulated devices. Output-device selection (`setSinkId`) wasn't exercised with real headphones |
| **Browsers** | Only Chromium (Playwright build). Chrome, Edge, Safari and Firefox weren't tested; Safari and Firefox don't support choosing the monitoring output |
| **Docker** | The compose file was validated, but the full Docker stack with the media server hasn't been run (no Docker in the sandbox). CI builds the images |
