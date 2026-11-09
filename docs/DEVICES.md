# Installing LoNo on phones, computers and TVs

LoNo is one web app that adapts to each screen: an installable app on phones and
computers, and a TV mode driven by the remote on smart TVs.

| Device | How | Status |
|---|---|---|
| Android phones/tablets | Install from Chrome or Samsung Internet; optional Play Store app via PWABuilder | Ready once hosted |
| iPhone / iPad | Safari → Share → **Add to Home Screen** | Ready once hosted |
| Windows / macOS / ChromeOS | Install button in Chrome or Edge; optional Microsoft Store via PWABuilder | Ready once hosted |
| Android TV / Google TV / Fire TV | WebView app in `apps/android-tv` | Template; build in Android Studio |
| Samsung Smart TV (Tizen) | Hosted app in `apps/tizen` | Template; build in Tizen Studio |
| LG Smart TV (webOS) | Hosted app in `apps/webos` | Template; build with webOS CLI |
| Chromecast / AirPlay | **Cast to TV** button on the player; AirPlay from iPhone Safari | Ready |
| Apple TV, Roku | Need native apps (Swift / BrightScript) | Not started |

## Step 0: put LoNo on a public HTTPS address

Every option below needs LoNo online at a secure address, for example `https://lono.ciu.edu.lr`.
Browsers allow installing apps only from HTTPS, and TV apps load the live site.

1. Run Docker mode on a server (`start.sh --docker`), behind HTTPS. A reverse proxy such as
   Caddy or Nginx with Let's Encrypt works well.
2. In `backend/.env.docker`, set `PUBLIC_ORIGIN` and `CORS_ORIGINS` to that address.
3. In `apps/tizen/config.xml`, `apps/webos/index.html` and `apps/android-tv/.../MainActivity.kt`,
   replace `https://lono.ciu.edu.lr` with your address.

## Phones and computers (installable app)

Nothing to build. Open the site and:

- **Android:** LoNo shows an **Install** banner, or use Chrome's menu → *Install app*.
- **iPhone/iPad:** Safari → Share → *Add to Home Screen*. LoNo shows these steps itself.
- **Windows/macOS:** the install icon in Chrome's or Edge's address bar.

Signed-in users also find **Install the LoNo app** under *Profile → Settings → Devices and display*.

**Optional store listings:** go to <https://www.pwabuilder.com>, enter your address, and
download the **Android** package (Google Play) or the **Windows** package (Microsoft Store).
For the Android package, copy the signing key's SHA-256 fingerprint into `backend/.env`:

```
ANDROID_APP_PACKAGE=lr.edu.ciu.lono
ANDROID_CERT_SHA256=AB:CD:...
```

LoNo then serves `/.well-known/assetlinks.json`, which lets the Play Store app open full
screen without a browser bar.

## TV mode

TV mode is on automatically when LoNo detects a TV browser (Tizen, webOS, Android TV,
Fire TV, HbbTV, VIDAA and others). The TV packages also force it with `?tv=1`. You can
switch it under *Settings → Devices and display*. In TV mode:

- **Arrow keys** move between rows and titles, **OK** opens them, and **Back** goes back.
  This includes Samsung's Return key (10009) and LG's Back key (461).
- Text is larger, the focused item is highlighted and enlarged, and there's a safe margin
  for screens that crop their edges.
- The floating AI chat is hidden, since typing with a remote isn't practical.

To try it on a computer, open `http://localhost:8001/?tv=1` and use the arrow keys.
Open `/?tv=0` to switch it off.

## Android TV, Google TV and Fire TV

Android TVs don't ship Chrome, so the Play Store web-app route doesn't work there. Use the
WebView wrapper instead:

1. In Android Studio, create a new **Empty Views Activity** project: package
   `lr.edu.ciu.lono.tv`, minimum SDK 23, language Kotlin.
2. Replace its `AndroidManifest.xml`, `MainActivity.kt` and `res/drawable` with the files
   in `apps/android-tv`.
3. Set `home` in `MainActivity.kt` to your HTTPS address.
4. Build an APK or App Bundle.
   - **To test:** enable developer options on the TV and install with `adb install`.
   - **To publish:** Google Play (Android TV / Google TV) or the Amazon Appstore (Fire TV).

## Samsung Smart TV (Tizen)

1. Install **Tizen Studio** with the TV extensions, and create a Samsung certificate.
2. Create a **Web Application** project for TV, and replace its `config.xml` and
   `icon.png` with `apps/tizen`'s.
3. **To test:** enable Developer Mode on the TV, then *Run As → Tizen Web Application*.
4. **To publish:** Samsung Apps TV Seller Office.

## LG Smart TV (webOS)

1. Install the **webOS TV CLI** (`ares-*` tools) and enable Developer Mode on the TV.
2. Package and install:
   ```bash
   ares-package apps/webos
   ares-install --device tv lr.edu.ciu.lono_1.0.0_all.ipk
   ```
3. **To publish:** LG Seller Lounge.

## Streaming quality and data use

- **Adaptive streaming:** use HLS (`.m3u8`) addresses for titles. LoNo plays them with
  automatic quality switching and offers a quality menu. A streaming service such as Mux,
  Cloudflare Stream or AWS MediaConvert can produce HLS from your uploads.
- **Data saver** (automatic when the phone asks to save data, or set in Settings):
  - images are about 480 px wide at lower quality
  - nothing preloads
  - HLS starts at the lowest quality and stays there unless the viewer picks higher
- **Player controls:**
  - playback speed
  - picture-in-picture
  - **Cast to TV**
  - lock-screen and headphone controls (Media Session)
- **Offline:** the app shell and recently viewed images are cached, and with no
  connection LoNo shows a "You're offline" screen instead of a browser error.
  Downloading videos to watch offline isn't built yet.
