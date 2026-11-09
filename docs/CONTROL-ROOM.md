# Live Control Room

For newscasts, protest and conflict coverage, football and other sports, crusades and community events. A producer keeps an anchor live while bringing in reporters and venue feeds from different places. The producer switches between them and returns to the studio, **all inside one continuous broadcast** that goes to LoNo and the selected social destinations.

Open it from **Creator Studio → Control Room**. It needs live broadcasting enabled (see [BROADCAST.md](BROADCAST.md)).

## Roles

| Who | Where | What they do |
|---|---|---|
| **Producer** | Control Room (desktop browser) | Invites contributors, watches every feed, prepares shots in Preview, puts them on air with TAKE, cues and talks to contributors, mutes or removes sources, runs the program output |
| **Anchor / reporter / guest** | Invitation link on a phone or laptop; no LoNo account needed | Checks camera and mic, waits privately, sees ON AIR and cue messages, hears the program without their own voice, can drop to audio-only and reconnect |
| **Field crew / venue** | External encoder (OBS, vMix, hardware) | Sends a feed with RTMP or SRT details from the invitation |

## Invitations

- **The link:** each invitation is a **secret link** containing 32 random bytes. Only a hash of it is stored.
- **Expiry:** links **expire** after a period the producer chooses (1 hour to 7 days). An expired link shows "This invitation has expired".
- **One feed per link:** a contributor can only send their own feed. Their key is checked by the media server on every connection.
- **Removing someone** disconnects them and ends their link straight away.
- **Location:** the producer may record a contributor's location, and **chooses whether it appears on air**. It's off by default; leave it off where showing it could put someone at risk.
- **Encoder invitations** give RTMP and SRT details for a private slot instead of a link. LoNo converts the encoder's AAC audio to Opus so the Control Room can play it.

## Producing

- **Preview and On Air:**
  - Prepare a shot in **Preview**: one source full screen, a **split-screen interview** of any two, a **clip** (media uploaded to LoNo), or the **standby** slate.
  - **TAKE** puts it on air. **Cut to anchor** goes straight back to the studio.
  - On-air sources carry a red frame in the source grid; previewed ones, a green frame.
- **Cue and Talk:**
  - **Cue** sends a private message to the contributor's screen (amber). It's never broadcast.
  - **Talk** routes the producer's microphone into that one contributor's return only.
- **What contributors hear:** each contributor gets a private audio return containing the **program minus their own microphone** (mix-minus), so there's no echo, plus the producer's talkback when active. Only on-air sources are in the program mix.
- **On-air indicator:** the contributor's page turns red with **ON AIR** when they're in the program, and amber with the cue text when cued.
- **Mute / Remove:** mute takes a source out of the program audio. Remove disconnects it and invalidates its link.
- **Lower thirds:** name, plus location where allowed, and a LIVE badge.

## When connections are weak

- **Contributors:**
  - **Audio only** stops sending video and keeps the voice going. The program shows "audio only" for that source.
  - Lost connections **reconnect automatically**, and there's a **Reconnect** button.
- **When an on-air feed drops,** the program automatically cuts to the **anchor** if connected, otherwise to **standby**. This is judged on network evidence: data stopped for 4 s, the feed ended, or it never started within 10 s. A contributor just taken to air gets a grace period.
- **Producer:** brings a reconnected contributor back with Preview → TAKE. The invitation link still works after a drop.
- **Destinations:** one that **drops after being live reconnects automatically** (after 2 s, 5 s and 10 s), showing "reconnecting". One that never connects (usually a wrong URL or key) fails at once with its error and a **Retry** button.

## How it works

- **Contributors** send WebRTC (WHIP) to private media-server paths `room/<room>/c/<contributor>`.
- **The producer's Control Room:**
  - receives every feed (WHEP)
  - **composites the program** on a canvas: scenes, lower thirds, LIVE badge
  - mixes on-air audio (Web Audio)
  - publishes the program into a normal LoNo broadcast session
  - publishes each contributor's return to `room/<room>/ret/<contributor>`
- **Delivery:** the session converts the program to H.264/AAC once. LoNo viewers, the recording and each destination relay all receive the same production.
- **The API holds the room state:** contributors, cues, preview and program scenes, and an activity log. The Control Room renders it, contributor pages read it, and the Creator API (phase 3) can drive it.

**Limit:** the producer's computer and connection carry the program. If the producer's browser closes or loses its connection, the broadcast waits and resumes when it returns (destinations wait, as with an encoder drop). Use a wired connection for the producer. A server-side program renderer is a later step.

**Networks:** contributors on mobile data or behind strict firewalls may need a TURN relay server. Configure `webrtcICEServers2` in `media/mediamtx.yml` and set `webrtcAdditionalHosts` to the server's public address.

## Acceptance test (Nov 2026, sandbox)

`scripts/broadcast/control_room_test.py`:

- One anchor and two reporters, **each in a separate Chromium process**, with **simulated** cameras and microphones: solid red, green and blue pictures, and 880, 440 and 660 Hz tones.
- The producer in a fourth process.
- The program goes to LoNo plus stand-ins for YouTube (RTMP) and Facebook (RTMPS).
- What was on air was checked by reading **program pixel colours**. Mix-minus was checked by **ffmpeg band-pass measurement** of each transmitted return.

**Result: 24 of 24 checks passed, with no JavaScript errors:**
- **Invitations and joining:** invitations created in the Control Room; all three join the private waiting area.
- **Going live:** anchor on air; live on LoNo and both stand-ins; listed on LoNo Live TV; Control Room shows LIVE.
- **Preview and cue:** Reporter A previewed privately (program still the anchor; A not on air); cued privately (shown on A's page).
- **TAKE:** A on air, with the ON AIR indicator and lower third.
- **Split-screen interview** (anchor left, A right).
- **Audio returns:**
  - both reporters receive their return
  - **A hears the anchor (−40 dB), not themselves (−67 dB, below the −60 dB threshold)**
  - **B hears the anchor and A (−40 dB), not themselves (−61 dB)**
- **Program audio:** carries the on-air audio.
- **Drop and recovery:**
  - Reporter B on air in a split, then **B's browser killed mid-segment**
  - **program returned to the anchor automatically**
  - **LoNo and both destinations kept receiving** during the drop
  - **B reconnected with the same link and was brought back on air**
  - producer returned to the anchor
- **Continuity:** **one continuous broadcast** (started once; the program feed never dropped). Destinations live at the end.
- **Finishing:** audio-only works; End.

**Bugs found and fixed while testing:**
1. The Control Room crashed on open: its compositor started before the page had drawn its canvases.
2. Contributor audio wasn't wired in, because it arrived after the video. That would have made **the program silent**.
3. Automatic fallback fired falsely on sources just taken to air.
4. A momentary API status timeout dropped healthy feeds.
5. "Frozen feed" was judged by picture redraws, which **knocked the anchor off air** under load. It's now judged by received network data.
6. A destination that dropped once stayed failed. It now reconnects automatically.

**Not tested:**
- **Separate networks or mobile data:** none. All processes ran on one machine, as separate WebRTC connections.
- **Real phones:** none. The contributor page was tested at phone size in Chromium only.
- **Hardware:** no real cameras, microphones or headsets.
- **Encoder-type contributors:** not exercised end to end (OBS isn't available in the sandbox).
- **TURN relays:** not exercised.
- **Real social platforms:** none; stand-ins only.
