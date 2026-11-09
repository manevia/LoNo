# Using LoNo with a TV remote

Once LoNo is open on a TV, everything works with the arrow pad, **OK** and **Back**.
Channel and media buttons work as shortcuts where the remote has them.

## Keys

| Key | What it does |
|---|---|
| Arrows | Move between menus, rows, titles, guide cells and player controls. A thick amber outline marks the focused item |
| OK | Open or play the focused item. In full-screen playback, the first OK shows the hidden controls |
| Back | Close the open overlay (picker, menu, error, full screen) first, then go back a screen. Focus returns to the item you came from |
| Channel Up / Down | Next or previous channel or station in the list you're watching |
| Play/Pause, Play, Pause, Stop | Control playback. On live streams without time-shifting, Stop disconnects and Play reconnects |
| Rewind / Fast-forward | Seek 10 s back, or 10 to 30 s forward, where the stream allows it |
| Next / Previous | Next or previous channel when watching live; next or previous title on demand |

Key codes handled:

| Platform | Back | Channel Up / Down | Media keys |
|---|---|---|---|
| Samsung Tizen | 10009 | 427 / 428 | 10252, 415, 19, 413, 412, 417 |
| LG webOS | 461 | 33 / 34 (PageUp / PageDown) | standard media codes |
| Android TV, Fire TV, HbbTV | standard `GoBack` and `Escape` | `ChannelUp` / `ChannelDown` | standard `Media…` key names |

## Live TV and radio (`/live`)

- **Tabs:** Live TV, Radio, Guide and Favorites.
- **Guide:** shows what's on now and next for every channel and station. OK on a channel or a program plays that channel.
- **Favorites:** the star on a channel, guide row or player adds it. Favorites are saved on the device, so they work without signing in.
- **Player:**
  - full screen, with a tuning banner showing the channel number, name and current program
  - **Channels / Stations picker:** opens with the playing channel highlighted. The current stream keeps playing while you browse, and switches only when you press OK
  - **Rapid switching:** only the most recent selection plays, and only one stream outputs audio
  - **Failed stream:** offers **Retry** and **Return to previous stream**
  - **Live controls:** Play and Stop (reconnect). When the stream supports time-shifting (an HLS stream with a rewind window of at least 30 s), also Pause, Rewind 10 s and **Go Live**, with a "behind live" indicator

## On demand (in TV mode)

- **Controls:** play/pause, a seek bar (Left and Right skip 10 s), back 10 s and forward 30 s, resume where you left off, and **Next** (a similar title).
- **Menus:** captions, audio tracks, quality and speed, when the title has them.
- **Full screen:** the controls hide while playing; OK shows them, and Back leaves full screen.

Mouse, keyboard and touch work as before. Outside TV mode, players keep the browser's own controls.

## Viewer and creator are separate

Everything above changes playback on the viewer's device only. Switching channels, pausing or leaving the player sends nothing to a broadcast, so it can't affect a creator's live stream or its delivery to social platforms.

## Test report (release 2.7)

**Method:** an automated browser test (Playwright with Chromium 141). The browser identified itself as a Samsung Tizen 6.5 TV at 1920×1080. After setup, the test used only arrow keys, Enter (OK), Escape (Back) and PageUp/PageDown (channel keys). Test streams were local:

- a live HLS stream with a rewind window
- a live HLS stream without one
- two audio stations
- a channel whose stream doesn't exist
- an HLS on-demand title with two quality levels

**Result:** 31 of 31 checks passed, with no JavaScript errors. The checks covered:
- opening Live from the menu
- playing a channel, and the tuning banner
- Channel Up and Down
- controls hiding and OK revealing them
- the picker opening on the current channel, and the stream continuing while browsing
- Back closing the picker first
- switching channels from the picker
- Stop and Play
- Back returning to the list with focus restored
- radio stations
- the guide, with its details and focus restored
- rapid switching to the last choice, with one media element
- failure with Retry and Return to previous
- Pause, Rewind and Go Live
- on-demand play and seek
- full screen with OK revealing controls
- Back leaving full screen before the page
- focus restored on Home
- desktop mouse use, with native controls kept

| Platform | How it was tested | Status |
|---|---|---|
| Desktop Chrome/Chromium (keyboard and mouse) | Automated, real browser | **Verified** |
| Samsung Tizen TV | **Emulated**: Chromium with a Tizen user agent and keyboard keys | Arrows, OK and Back logic verified. The Return key code (10009) and channel codes (427/428) are mapped but not tested on a TV. A hosted Tizen app may need `tizen.tvinputdevice.registerKey` for media and channel keys, which remote pages may not be allowed to call. **Not verified on hardware** |
| LG webOS TV | Not run | Back (461) and channel keys (PageUp/PageDown) are mapped; `disableBackHistoryAPI` is set in `apps/webos`. **Not verified** |
| Android TV / Google TV / Fire TV | Not run | The arrow pad arrives as arrow keys in a WebView. Channel keys may not reach a WebView app. **Not verified** |
| Physical remotes | **None tested** | |

No physical remote, real TV or TV emulator (Tizen Studio, webOS emulator, Android TV emulator) was used for this release.
