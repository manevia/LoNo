# Real-world tests (phase 4)

Everything in releases 2.7 to 3.0 was tested automatically with **simulated** devices and **stand-in** platforms. These tests check the parts that need real hardware, real software and real accounts.

- **Recording results:** fill in the **Result** column with ✅, ⚠️ (works with a problem; add a note) or ❌, then send the file back. It becomes the compatibility report.
- **Time:** about 1 to 2 hours in total. Each section stands alone.

## Before you start

1. `git pull`, then run `start.cmd -Broadcast` (Windows) or `./start.sh --broadcast`.
   - **First run:** it downloads the media server and may install ffmpeg. If Windows asks about `mediamtx.exe`, allow **private networks**.
   - **Then:** it shows an address like `Encoder server: rtmp://192.168.x.x:1935/live`.
2. Sign in (the admin password is printed the first time) and open **Creator Studio**.
3. Record what you're using:

| Item | Yours |
|---|---|
| Windows version | |
| Browser and version | |
| Camera (make/model, USB or built in) | |
| Microphone / headset | |
| Capture card or mixer (if any) | |
| OBS Studio version | |
| Other encoder (vMix, Streamlabs, Wirecast…) | |
| Internet: upload speed (speedtest.net) | |

## A. TV remote (if you have a smart TV or Android TV box)

Open LoNo on the TV, through the TV app package or the TV's browser, at `http://<PC address>:8001/?tv=1`.

| # | Do this with the remote only | Expected | Result |
|---|---|---|---|
| A1 | Arrows to **Live**, OK | Live TV list; a thick outline on the focused item | |
| A2 | OK on a channel | Plays full screen; banner with channel name | |
| A3 | Channel Up / Down (if your remote has them) | Next / previous channel | |
| A4 | OK, then arrows to **Channels**, OK | Picker opens on the playing channel; stream keeps playing | |
| A5 | Back | Picker closes; Back again returns to the list with focus on your channel | |
| A6 | Play/Pause button (if present) | Pauses on demand / stops live | |

**TV make, model and OS:** ______

## B. Solo creator: webcam and headset (Live Studio)

| # | Do this | Expected | Result |
|---|---|---|---|
| B1 | **Open Live Studio** → This device → Allow | Your camera preview; your devices listed by name | |
| B2 | Speak | Meter moves; **Measure levels** says Good, or too quiet/loud | |
| B3 | Choose your headset under Monitoring; tick **Hear my microphone** | You hear yourself in the headset only | |
| B4 | **Start private test** | "What LoNo receives" shows you within ~10 s; no destinations used | |
| B5 | Clap on camera | Sound and hands match in the preview (tick the box) | |
| B6 | Unplug the USB camera (or mic), then plug it back in | Warning appears; **Reconnect** works | |
| B7 | Stop the test | Back to Offline | |

## C. OBS Studio and another encoder

1. **Live Studio** → **External encoder**. Copy **Server** and **Stream key**.
2. In OBS: Settings → Stream → Service **Custom…** → paste both. Output: x264 or hardware encoder, 2500 to 6000 Kbps, keyframe 2 s.

| # | Do this | Expected | Result |
|---|---|---|---|
| C1 | OBS **Start Streaming**, then **Start private test** in Live Studio | Preview shows your OBS scene; Feed: connected, H264 + MPEG-4 Audio | |
| C2 | Switch scenes in OBS | Preview follows | |
| C3 | Stop and restart streaming in OBS | Feed reconnects | |
| C4 | Repeat C1 with **SRT** (Server = the SRT URL, empty key) | Feed connects | |
| C5 | Repeat C1 with another encoder (name: ______) | Feed connects | |
| C6 | **New stream key**, then stream with the old key | Refused; works with the new key | |

**Capture card or mixer:** if you have one, use it as a camera under **This device** (B1) or as a source in OBS (C1), and note the model: ______

## D. Simulcast to your real accounts

Add one or two destinations in Live Studio → **Add destination**, using the server URL and stream key from each platform (see docs/BROADCAST.md, "Destinations").

| # | Do this | Expected | Result |
|---|---|---|---|
| D1 | Title, tick **Record**, select destinations, **Go live** (from OBS or your webcam) | LoNo shows LIVE; each destination shows **Live** | |
| D2 | Check each platform's live dashboard | Stream visible there, with picture and sound | |
| D3 | Open LoNo Live TV on another device or browser | Your broadcast is listed and plays | |
| D4 | On one platform, end/reset its stream key (or block it) | That destination shows Reconnecting, then Failed with a message; **others continue** | |
| D5 | Fix it and press **Retry** | It goes Live again | |
| D6 | **End broadcast** | Ends on LoNo and every platform | |
| D7 | Recordings → **Publish now** | Becomes an on-demand title on your channel | |

**Platforms tested (name, Live/Failed, notes):** ______

## E. Live Control Room

1. **Creator Studio → Control Room** → create a production.
2. Invite an **anchor** and **two reporters**. Open the links on **laptops**, or on phones if LoNo has an https address. Use **headphones**. If you can, put one reporter on a **different network** (a phone hotspot).

| # | Do this | Expected | Result |
|---|---|---|---|
| E1 | Each opens their link, allows devices, **Join waiting area** | Tiles show connected in the Control Room | |
| E2 | Preview the anchor, **TAKE**, then **Go live** (add a real destination if you like) | Program on air; LoNo LIVE | |
| E3 | **Preview** reporter 1 | Only the Preview monitor changes; reporter 1 sees "Waiting" | |
| E4 | **Cue** reporter 1, then **TAKE** | Their screen goes amber with the cue, then red **ON AIR** | |
| E5 | Tick anchor + reporter 1, **Preview split**, **TAKE** | Split-screen interview on air | |
| E6 | Reporter 1 listens in headphones | Hears the anchor, **not themselves**, no echo | |
| E7 | **Talk** to reporter 2 | Only reporter 2 hears you | |
| E8 | Put reporter 2 on air, then turn off their Wi-Fi | Program returns to the anchor within ~5 s; broadcast continues | |
| E9 | Wi-Fi back on; reporter 2 presses **Reconnect** if needed; Preview → TAKE | Back on air | |
| E10 | Reporter 1: **Audio only** | Voice continues; tile shows audio only | |
| E11 | Wait for an invitation to expire (set 1 hour), or **Remove** someone | Their link stops working | |

## F. Creator API (optional)

**Creator Studio → Developer Access** → New integration (Test environment). Follow docs/CREATOR-API.md example 3 with `curl`, and set a webhook URL from a webhook-testing service.

| # | Do this | Expected | Result |
|---|---|---|---|
| F1 | `curl …/api/v1/me` with the token | Your name and scopes | |
| F2 | Create a session twice with the same Idempotency-Key | Same id both times | |
| F3 | Send a webhook test (`POST /api/v1/webhooks/test`) | Arrives with a LoNo-Signature header | |

## Notes

Anything confusing, slow or broken, with the step number:

