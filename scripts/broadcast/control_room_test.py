"""Live Control Room acceptance test.
Anchor (red, 880 Hz), Reporter A (green, 440 Hz), Reporter B (blue, 660 Hz): each a
SEPARATE Chromium process with simulated camera/mic files. Producer in its own
process. Same machine/network (separate WebRTC connections), not separate ISPs."""
import asyncio, json, subprocess, time, uuid
import httpx
from playwright.async_api import async_playwright

import os
B = os.environ.get("LONO_URL", "http://127.0.0.1:8001"); API = B + "/api"
CHROME = os.environ.get("CHROME") or None   # Playwright's Chromium by default
MEDIA_DIR = os.environ.get("CR_MEDIA_DIR", "/tmp/cr")   # anchor/repA/repB .y4m + .wav (see docs/CONTROL-ROOM.md)
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def standin():
    try:
        items = httpx.get("http://127.0.0.1:9998/v3/paths/list", timeout=3).json()["items"]
        return {p["name"]: p["bytesReceived"] for p in items if p.get("ready")}
    except Exception:
        return {}


async def contributor(p, who, url):
    br = await p.chromium.launch(executable_path=CHROME, args=[
        "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required",
        f"--use-file-for-fake-video-capture={MEDIA_DIR}/{who}.y4m", f"--use-file-for-fake-audio-capture={MEDIA_DIR}/{who}.wav"])
    ctx = await br.new_context(viewport={"width": 420, "height": 860}, permissions=["camera", "microphone"])  # phone-sized
    pg = await ctx.new_page()
    await pg.goto(url)
    await pg.wait_for_selector('[data-testid=allow-devices]')
    await pg.click('[data-testid=allow-devices]')
    await pg.wait_for_function("document.querySelector('[data-testid=camera-preview]')?.videoWidth > 0", timeout=15000)
    await pg.click('[data-testid=join-waiting]')
    return br, pg


async def pixel(pg, canvas, x=0.5, y=0.5):
    return await pg.evaluate(f"""(() => {{ const c = document.querySelector('[data-testid={canvas}]');
      const d = c.getContext('2d').getImageData(Math.floor(c.width*{x}), Math.floor(c.height*{y}), 1, 1).data; return [d[0], d[1], d[2]]; }})()""")


async def wait_color(pg, canvas, want, x=0.5, y=0.5, timeout=12):
    end = time.time() + timeout
    got = None
    while time.time() < end:
        got = color(await pixel(pg, canvas, x, y))
        if got == want:
            return got
        await asyncio.sleep(0.3)
    return got


def color(rgb):
    r, g, b = rgb
    if r > 150 and g < 90 and b < 90: return "red"
    if g > 100 and r < 90 and b < 90: return "green"
    if b > 150 and r < 90 and g < 90: return "blue"
    return f"other{rgb}"


async def tones(pg):
    """Which test tones are present in this contributor's return audio (FFT)."""
    return await pg.evaluate("""() => new Promise((resolve) => {
      const el = document.querySelector('[data-testid=return-audio]');
      if (!el || !el.srcObject) return resolve({});
      const ctx = new AudioContext({sampleRate: 48000}); const src = ctx.createMediaStreamSource(el.srcObject);
      const an = ctx.createAnalyser(); an.fftSize = 8192; src.connect(an); ctx.resume();
      setTimeout(() => { const f = new Float32Array(an.frequencyBinCount); an.getFloatFrequencyData(f);
        const bin = (hz) => Math.max(...[-2,-1,0,1,2].map(d => f[Math.round(hz / (48000 / an.fftSize)) + d]));
        const clean = (v) => (isFinite(v) ? v : -200);   // silence measures as -Infinity
        resolve({440: clean(bin(440)), 660: clean(bin(660)), 880: clean(bin(880))}); ctx.close(); }, 1500);
    })""")


def band_db(path, hz, secs=3):
    """Level of one test tone in a stream on the media server (ffmpeg band-pass + volumedetect)."""
    import os, sys
    sys.path.insert(0, "/home/claude/gh/backend"); os.chdir("/home/claude/gh/backend")
    from app import config
    out = subprocess.run(["ffmpeg", "-hide_banner", "-rtsp_transport", "tcp", "-i", f"rtsp://lono-internal:{config.MEDIA_INTERNAL_SECRET}@127.0.0.1:8554/{path}",
                          "-t", str(secs), "-vn", "-af", f"bandpass=f={hz}:width_type=h:w=30,volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True, timeout=40).stderr
    for l in out.splitlines():
        if "mean_volume" in l:
            return float(l.split("mean_volume:")[1].split("dB")[0])
    return -200.0


async def until(pg, js, timeout=30000):
    try:
        await pg.wait_for_function(js, timeout=timeout); return True
    except Exception:
        return False


async def main():
    c = httpx.Client(timeout=20)
    tok = c.post(f"{API}/auth/register", json={"email": f"prod{uuid.uuid4().hex[:6]}@example.com", "password": "Passw0rd!", "name": "Producer", "accept_terms": True}).json()["token"]
    H = {"Authorization": f"Bearer {tok}"}
    dests = [c.post(f"{API}/broadcast/destinations", headers=H, json=d).json()["id"] for d in (
        {"platform": "youtube", "server_url": "rtmp://127.0.0.1:2935/youtube", "stream_key": "yt-CR-1"},
        {"platform": "facebook", "server_url": "rtmps://127.0.0.1:2936/facebook", "stream_key": "fb-CR-2"})]

    async with async_playwright() as p:
        prod_br = await p.chromium.launch(executable_path=CHROME, args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required"])
        ctx = await prod_br.new_context(viewport={"width": 1700, "height": 1100}, permissions=["camera", "microphone"])
        pg = await ctx.new_page()
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(B + "/")
        await pg.evaluate(f"localStorage.setItem('lono_token', '{tok}'); localStorage.setItem('lono_studio_dests', JSON.stringify({json.dumps(dests)}))")
        await pg.goto(B + "/studio/control")
        await pg.fill('[data-testid=room-title]', 'Evening News')
        await pg.click('[data-testid=room-create]')
        await pg.wait_for_selector('[data-testid=control-room]')
        room_id = pg.url.rstrip("/").split("/")[-1]

        links = {}
        for name, role, loc, show in [("Anchor Desk", "anchor", "Monrovia studio", False), ("Reporter A", "reporter", "Gbarnga", True), ("Reporter B", "reporter", "Ganta", False)]:
            await pg.fill('[data-testid=invite-name]', name)
            await pg.select_option('[data-testid=invite-role]', role)
            await pg.fill('[data-testid=invite-location]', loc)
            if show:
                await pg.check('[data-testid=invite-form] input[type=checkbox]')
            await pg.click('[data-testid=invite-send]')
            await pg.wait_for_function(f"document.querySelector('[data-testid=invite-url]')?.textContent.length > 20 && !window.__last?.includes(document.querySelector('[data-testid=invite-url]').textContent)", timeout=10000)
            url = await pg.inner_text('[data-testid=invite-url]')
            await pg.evaluate("u => window.__last = (window.__last || '') + u", url)
            links[name] = url
            if show:
                await pg.uncheck('[data-testid=invite-form] input[type=checkbox]')
        check("Producer creates secure, expiring invitations from the Control Room", len(set(links.values())) == 3 and all("/join/" in u for u in links.values()))
        room = c.get(f"{API}/rooms/{room_id}", headers=H).json()
        ids = {x["name"]: x["id"] for x in room["contributors"]}

        anchor_br, anchor = await contributor(p, "anchor", links["Anchor Desk"])
        a_br, repA = await contributor(p, "repA", links["Reporter A"])
        b_br, repB = await contributor(p, "repB", links["Reporter B"])
        ok = await until(pg, "document.querySelectorAll('[data-connected=\"1\"]').length === 3", 40000)
        check("Anchor and two reporters join the private waiting area (separate browser processes)", ok)
        await pg.wait_for_timeout(3000)

        # ---------- program on air with the anchor ----------
        await pg.click(f'[data-testid=preview-{ids["Anchor Desk"]}]'); await pg.wait_for_timeout(1500)
        await pg.click('[data-testid=take]'); await pg.wait_for_timeout(1500)
        got = await wait_color(pg, 'program-canvas', "red")
        check("Anchor full screen in program", got == "red", got)
        await pg.click('[data-testid=program-live]')
        sess = None
        for _ in range(90):
            sess = c.get(f"{API}/broadcast/sessions/current", headers=H).json()
            if sess and sess["status"] == "live" and all(d["state"] == "live" for d in sess["destinations"]):
                break
            await asyncio.sleep(1)
        live = bool(sess and sess["status"] == "live")
        label = await until(pg, "document.querySelector('[data-testid=program-status]')?.textContent.includes('LIVE')", 20000)
        check("Control Room shows the program as LIVE", label, await pg.inner_text('[data-testid=program-status]'))
        sid = sess["id"]
        check("Program goes live on LoNo with YouTube and Facebook stand-ins", live and all(d["state"] == "live" for d in sess["destinations"]),
              json.dumps({d["platform"]: d["state"] for d in sess["destinations"]}))
        on_lono = any(ch["title"] == "Evening News" for ch in c.get(f"{API}/live/guide").json()["tv"])
        check("Newscast listed on LoNo Live TV", on_lono)
        await pg.screenshot(path="/tmp/shots/cr_01_anchor.png")

        # ---------- preview Reporter A privately, cue, take ----------
        await pg.click(f'[data-testid=preview-{ids["Reporter A"]}]'); await pg.wait_for_timeout(1500)
        pv = await wait_color(pg, 'preview-canvas', "green"); pr = color(await pixel(pg, 'program-canvas'))
        a_air = await repA.get_attribute('[data-testid=onair-indicator]', 'data-on-air')
        check("Reporter A in Preview only: program still anchor, A not on air", pv == "green" and pr == "red" and a_air == "0", f"preview={pv} program={pr}")
        await pg.evaluate("window.prompt = () => 'Coming to you in 10'")
        await pg.click(f'[data-testid=cue-{ids["Reporter A"]}]')
        cued = await until(repA, "document.querySelector('[data-testid=onair-indicator]').textContent.includes('Coming to you in 10')", 8000)
        check("Producer cues Reporter A privately (shown on A's phone)", cued)
        await pg.click('[data-testid=take]')
        a_on = await until(repA, "document.querySelector('[data-testid=onair-indicator]').dataset.onAir === '1'", 8000)
        await pg.wait_for_timeout(1000)
        check("TAKE puts Reporter A on air; A's ON AIR indicator lights", a_on and await wait_color(pg, 'program-canvas', "green") == "green")
        lt = await pixel(pg, 'program-canvas', 0.06, 0.86)
        check("Reporter A's lower third shown (location allowed on air)", color(lt) != "green", str(lt))

        # ---------- split-screen interview: anchor + Reporter A ----------
        await pg.click(f'[data-testid=split-{ids["Anchor Desk"]}]'); await pg.click(f'[data-testid=split-{ids["Reporter A"]}]')
        await pg.click('[data-testid=preview-split]'); await pg.wait_for_timeout(1200)
        await pg.click('[data-testid=take]'); await pg.wait_for_timeout(2000)
        left = await wait_color(pg, 'program-canvas', "red", 0.25, 0.4); right = color(await pixel(pg, 'program-canvas', 0.75, 0.4))
        check("Split-screen interview on air: anchor left, Reporter A right", left == "red" and right == "green", f"{left}/{right}")
        await pg.screenshot(path="/tmp/shots/cr_02_split.png")
        retA = await until(repA, "document.querySelector('[data-testid=return-status]')?.dataset.on === '1'", 20000)
        retB = await until(repB, "document.querySelector('[data-testid=return-status]')?.dataset.on === '1'", 20000)
        check("Both reporters receive their private audio return", retA and retB)
        tA = {hz: band_db(f"room/{room_id}/ret/{ids['Reporter A']}", hz) for hz in (440, 660, 880)}
        tB = {hz: band_db(f"room/{room_id}/ret/{ids['Reporter B']}", hz) for hz in (440, 660, 880)}
        hears = lambda t, hz: t[hz] > -60
        check("Reporter A's return: hears the anchor (880 Hz), not their own mic (440 Hz)", hears(tA, 880) and not hears(tA, 440), json.dumps({k: round(v) for k, v in tA.items()}))
        check("Reporter B's return: hears the program (anchor 880 + A 440 Hz), not their own mic (660 Hz)", hears(tB, 880) and hears(tB, 440) and not hears(tB, 660),
              json.dumps({k: round(v) for k, v in tB.items()}))
        ing = c.get(f"{API}/broadcast/ingest", headers=H).json()["ingest_id"]
        prog = {hz: band_db(f"live/{ing}", hz) for hz in (440, 880)}
        check("The program LoNo receives carries the on-air audio (anchor + Reporter A)", all(v > -60 for v in prog.values()), json.dumps({k: round(v) for k, v in prog.items()}))

        # ---------- Reporter B on air, then drops mid-segment ----------
        await pg.click(f'[data-testid=split-{ids["Reporter A"]}]'); await pg.click(f'[data-testid=split-{ids["Reporter B"]}]')
        await pg.click('[data-testid=preview-split]'); await pg.wait_for_timeout(1200)
        await pg.click('[data-testid=take]'); await pg.wait_for_timeout(2000)
        right = await wait_color(pg, 'program-canvas', "blue", 0.75, 0.4)
        left = color(await pixel(pg, 'program-canvas', 0.25, 0.4))
        check("Reporter B brought on air (split with anchor)", right == "blue" and left == "red", f"{left}/{right}")
        before = standin()
        await b_br.close()                                   # Reporter B loses signal abruptly
        fell_back = await until(pg, "document.querySelector('[data-testid=program-canvas]') && (() => { const c = document.querySelector('[data-testid=program-canvas]'); const d = c.getContext('2d').getImageData(c.width/2, c.height/2, 1, 1).data; return d[0] > 150 && d[1] < 90; })()", 20000)
        ev = [e["type"] + ":" + str(e["details"].get("reason", "")) for e in c.get(f"{API}/rooms/{room_id}/events", headers=H).json()]
        check("Reporter B drops: program returns to the anchor automatically", fell_back and any("fallback" in e for e in ev), next((e for e in ev if "fallback" in e), ""))
        await pg.wait_for_timeout(3000)
        s_now = c.get(f"{API}/broadcast/sessions/{sid}", headers=H).json()
        after = standin()
        flowing = all(after.get(k, 0) > v for k, v in before.items()) and len(before) == 2
        check("Broadcast continues on LoNo and both destinations during the drop",
              s_now["status"] == "live" and s_now["feed"]["ready"] and all(d["state"] == "live" for d in s_now["destinations"]) and flowing,
              json.dumps({d["platform"]: d["state"] for d in s_now["destinations"]}))

        # ---------- Reporter B reconnects and returns to air ----------
        b_br, repB = await contributor(p, "repB", links["Reporter B"])
        back = await until(pg, f"document.querySelector('[data-testid=tile-{ids['Reporter B']}]')?.dataset.connected === '1'", 30000)
        await pg.wait_for_timeout(3000)
        await pg.click(f'[data-testid=preview-{ids["Reporter B"]}]'); await pg.wait_for_timeout(1500)
        await pg.click('[data-testid=take]')
        b_on = await until(repB, "document.querySelector('[data-testid=onair-indicator]').dataset.onAir === '1'", 10000)
        await pg.wait_for_timeout(1500)
        check("Reporter B reconnects with the same invitation and is brought back on air", back and b_on and await wait_color(pg, 'program-canvas', "blue") == "blue")
        await pg.click('[data-testid=cut-anchor]')
        check("Producer returns to the anchor", await wait_color(pg, 'program-canvas', "red") == "red")

        # ---------- continuity ----------
        sevents = [e["type"] for e in c.get(f"{API}/broadcast/sessions/{sid}/events", headers=H).json()]
        s_now = c.get(f"{API}/broadcast/sessions/{sid}", headers=H).json()
        check("One continuous broadcast: never restarted, program feed never dropped",
              sevents.count("broadcast.started") == 1 and "stream.disconnected" not in sevents and s_now["status"] == "live" and s_now["id"] == sid,
              ",".join(sevents))
        check("Destinations live at the end of the segment", all(d["state"] == "live" for d in s_now["destinations"]))

        # weak signal: audio-only
        await repA.click('[data-testid=toggle-audio-only]'); await pg.wait_for_timeout(2500)
        ao = c.get(f"{API}/rooms/{room_id}", headers=H).json()
        check("Reporter can drop to audio-only", next(x for x in ao["contributors"] if x["name"] == "Reporter A")["audio_only"])
        await pg.screenshot(path="/tmp/shots/cr_03_end.png", full_page=True)

        await pg.click('[data-testid=program-end]')
        ended = await until(pg, "!document.querySelector('[data-testid=program-status]')?.textContent.includes('LIVE')", 20000)
        check("End broadcast", ended)
        print("JS ERRORS:", errs[:5], flush=True)
        for br in (anchor_br, a_br, b_br, prod_br):
            try: await br.close()
            except Exception: pass
    print(f"SUMMARY {sum(r[1] for r in results)}/{len(results)} passed", flush=True)
    json.dump(results, open("/tmp/cr_results.json", "w"))

asyncio.run(main())
