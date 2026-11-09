"""Solo creator in Live Studio with Chromium's SIMULATED camera and microphone
(--use-fake-device-for-media-stream). Not real hardware."""
import asyncio, json, uuid, subprocess, time
from playwright.async_api import async_playwright

B = "http://localhost:8001"
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
TIZEN_UA = "Mozilla/5.0 (SMART-TV; LINUX; Tizen 6.5) AppleWebKit/537.36 (KHTML, like Gecko) 85.0.4183.93/6.5 TV Safari/537.36"
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


async def until(pg, js, timeout=30000):
    try:
        await pg.wait_for_function(js, timeout=timeout)
        return True
    except Exception:
        return False


async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path=CHROME, args=[
            "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required"])
        ctx = await br.new_context(viewport={"width": 1500, "height": 1000}, permissions=["camera", "microphone"])
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))

        await pg.goto(B + "/signup")
        await pg.fill('[data-testid=signup-name]', 'Solo Creator')
        await pg.fill('[data-testid=signup-email]', f"solo{uuid.uuid4().hex[:6]}@example.com")
        await pg.fill('[data-testid=signup-password]', 'Passw0rd!')
        await pg.check('[data-testid=signup-terms]')
        await pg.click('[data-testid=signup-submit]')
        await pg.wait_for_url(B + "/")
        await pg.goto(B + "/studio")
        await pg.click('[data-testid=open-live-studio]')
        await pg.wait_for_selector('[data-testid=live-studio]')
        check("Studio's 10 destination tiles kept and link to Live Studio", await pg.evaluate("location.pathname") == "/studio/live")

        # ---------- Devices & Sources ----------
        await pg.click('[data-testid=allow-devices]')
        await until(pg, "document.querySelector('[data-testid=camera-preview]')?.videoWidth > 0", 15000)
        w = await pg.evaluate("document.querySelector('[data-testid=camera-preview]').videoWidth")
        cams = await pg.locator('[data-testid=select-camera] option').count()
        mics = await pg.locator('[data-testid=select-mic] option').count()
        check("Camera preview and device lists", w > 0 and cams >= 1 and mics >= 1, f"width={w} cameras={cams} mics={mics}")
        db = -120
        for _ in range(25):  # the simulated mic beeps intermittently: watch for a few seconds
            db = max(db, int(await pg.get_attribute('[data-testid=mic-meter]', 'data-db')))
            if db > -60: break
            await pg.wait_for_timeout(200)
        check("Microphone level meter moves", db > -60, f"{db} dBFS")
        await pg.click('button[aria-label="Rename this camera"]')
        await pg.fill('input[aria-label="Name for this camera"]', 'Desk camera')
        await pg.click('form >> text=Save')
        await pg.wait_for_timeout(300)
        renamed = "Desk camera" in await pg.inner_text('[data-testid=select-camera]')
        check("Rename a device (remembered on this device)", renamed)
        await pg.click('[data-testid=toggle-mute]'); await pg.wait_for_timeout(500)
        muted = await pg.inner_text('[data-testid=mic-meter]')
        await pg.click('[data-testid=toggle-mute]')
        check("Mute shows on the meter", "Muted" in muted)
        await pg.check('[data-testid=toggle-monitor]'); await pg.wait_for_timeout(700)
        mon = await pg.evaluate("(() => { const a = document.querySelector('[data-testid=monitor-output]'); return {has: !!a.srcObject, playing: !a.paused}; })()")
        check("Monitoring plays the mic locally", mon["has"] and mon["playing"], json.dumps(mon))
        await pg.click('[data-testid=measure-levels]')
        await pg.wait_for_timeout(5600)
        lvl = await pg.get_attribute('[data-testid=check-1]', 'data-status')
        check("Test Setup: audio level check gives a result", lvl in ("pass", "warn"), lvl)
        frm = await pg.get_attribute('[data-testid=check-0]', 'data-status')
        check("Test Setup: framing check reads resolution and fps", frm in ("pass", "warn"), frm)

        # ---------- destinations ----------
        for plat, url, key in [("youtube", "rtmp://127.0.0.1:2935/youtube", "yt-STUDIO-1111"),
                               ("facebook", "rtmps://127.0.0.1:2936/facebook", "fb-STUDIO-2222"),
                               ("twitch", "rtmp://127.0.0.1:3935/twitch", "tw-STUDIO-3333")]:
            await pg.click('[data-testid=add-destination]')
            await pg.select_option('[data-testid=dest-platform]', plat)
            await pg.fill('[data-testid=dest-url]', url)
            await pg.fill('[data-testid=dest-key]', key)
            await pg.click('[data-testid=dest-save]')
            await pg.wait_for_selector(f'[data-testid=dest-select-{plat}]')
        sel = await pg.evaluate("[...document.querySelectorAll('[data-testid^=dest-select-]')].filter(c => c.checked).length")
        check("Add YouTube, Facebook and Twitch destinations; selected for the broadcast", sel == 3)
        await pg.click('[data-testid=add-destination]')
        disc = await pg.evaluate("[...document.querySelectorAll('[data-testid=dest-platform] option')].find(o => o.value === 'discord')?.disabled")
        await pg.click('[data-testid=add-destination-form] >> text=Cancel')
        check("Discord shown but can't be chosen", disc is True)

        # ---------- private test ----------
        await pg.click('[data-testid=start-test]')
        ok = await until(pg, "document.querySelector('[data-testid=feed-info]')?.textContent.includes('connected') && !document.querySelector('[data-testid=feed-info]').textContent.includes('not connected')", 30000)
        info = await pg.inner_text('[data-testid=feed-info]') if ok else ""
        check("Private test: camera reaches LoNo over WebRTC", ok, info.replace("\n", " | "))
        prev = await until(pg, "document.querySelector('[data-testid=studio-preview]')?.videoWidth > 0", 30000)
        check("Private preview shows the picture LoNo receives (browser codecs converted)", prev)
        await pg.wait_for_timeout(5000)
        conn = await pg.get_attribute('[data-testid=check-3]', 'data-status')
        conn_txt = await pg.inner_text('[data-testid=check-3]')
        check("Test Setup: connection quality measured", conn in ("pass", "warn"), conn_txt.replace("\n", " "))
        stand = subprocess.run(["curl", "-s", "127.0.0.1:9998/v3/paths/list"], capture_output=True, text=True).stdout
        check("Private test sends nothing to destinations", '"ready":true' not in stand)
        await pg.screenshot(path="/tmp/shots/studio_test.png", full_page=True)

        # ---------- go live ----------
        await pg.fill('[data-testid=bc-title]', 'Studio Session Live')
        await pg.click('[data-testid=go-live]')
        live = await until(pg, "document.querySelector('[data-testid=studio-status]')?.textContent.includes('LIVE')", 45000)
        check("Go live from Live Studio", live)
        await until(pg, "document.querySelector('[data-testid=dest-status-youtube]')?.dataset.state === 'live' && document.querySelector('[data-testid=dest-status-facebook]')?.dataset.state === 'live'", 30000)
        await until(pg, "document.querySelector('[data-testid=dest-status-twitch]')?.dataset.state === 'failed'", 30000)
        st = {pl: await pg.get_attribute(f'[data-testid=dest-status-{pl}]', 'data-state') for pl in ("youtube", "facebook", "twitch")}
        check("YouTube and Facebook stand-ins live; Twitch fails while others continue", st == {"youtube": "live", "facebook": "live", "twitch": "failed"}, json.dumps(st))
        has_retry = await pg.locator('[data-testid=retry-twitch]').count() == 1
        err = await pg.inner_text('[data-testid=dest-status-twitch]')
        check("Failed destination shows its error and a Retry button", has_retry and "reach" in err, err.replace("\n", " "))
        await pg.screenshot(path="/tmp/shots/studio_live.png", full_page=True)

        # targeted retry once "Twitch" is reachable
        mtxB = subprocess.Popen(["/tmp/mtx/mediamtx", "/tmp/standin/standin_B.yml"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        await pg.wait_for_timeout(2000)
        await pg.click('[data-testid=retry-twitch]')
        ok = await until(pg, "document.querySelector('[data-testid=dest-status-twitch]')?.dataset.state === 'live'", 30000)
        check("Retry brings Twitch live; YouTube/Facebook untouched", ok and await pg.get_attribute('[data-testid=dest-status-youtube]', 'data-state') == "live")

        # ---------- separate TV viewer session ----------
        tv = await br.new_context(viewport={"width": 1920, "height": 1080}, user_agent=TIZEN_UA)
        v = await tv.new_page()
        await v.goto(B + "/live?tab=tv")
        await v.wait_for_selector('[data-testid=live-page]')
        card = v.locator('a[data-testid^=live-card-]', has_text="Studio Session Live")
        found = await card.count() == 1
        if found:
            await card.focus(); await v.keyboard.press("Enter")
            await v.wait_for_selector('[data-testid=live-player]')
            await v.wait_for_timeout(4000)
            for k in ("PageUp", "PageDown", "PageUp"):
                await v.keyboard.press(k); await v.wait_for_timeout(1200)
            await v.keyboard.press("Escape"); await v.wait_for_timeout(500)
            await v.keyboard.press("Escape"); await v.wait_for_timeout(1000)
        await tv.close()
        await pg.wait_for_timeout(3000)
        st = {pl: await pg.get_attribute(f'[data-testid=dest-status-{pl}]', 'data-state') for pl in ("youtube", "facebook", "twitch")}
        still_live = "LIVE" in await pg.inner_text('[data-testid=studio-status]')
        check("TV viewer watched, switched channels and left: broadcast and destinations unaffected", found and still_live and set(st.values()) == {"live"}, json.dumps(st))

        # ---------- device disconnect and reconnect while live ----------
        await pg.evaluate("document.querySelector('[data-testid=camera-preview]').srcObject.getVideoTracks()[0].dispatchEvent(new Event('ended'))")
        shown = await until(pg, "!!document.querySelector('[data-testid=device-lost]')", 5000)
        await pg.click('[data-testid=reconnect-camera]')
        gone = await until(pg, "!document.querySelector('[data-testid=device-lost]')", 10000)
        await pg.wait_for_timeout(3000)
        st = {pl: await pg.get_attribute(f'[data-testid=dest-status-{pl}]', 'data-state') for pl in ("youtube", "facebook")}
        check("Camera disconnect is shown; Reconnect restores it while staying live", shown and gone and set(st.values()) == {"live"}, json.dumps(st))

        # ---------- end and recording ----------
        await pg.wait_for_timeout(4000)
        await pg.click('[data-testid=end-broadcast]')
        ended = await until(pg, "document.querySelector('[data-testid=studio-status]')?.textContent.includes('Offline')", 15000)
        await pg.wait_for_timeout(2000)
        stand = subprocess.run(["curl", "-s", "127.0.0.1:9998/v3/paths/list"], capture_output=True, text=True).stdout
        check("End broadcast stops LoNo and destinations", ended and '"ready":true' not in stand)
        ready = await until(pg, "document.querySelector('[data-testid=recording-row]')?.dataset.status === 'ready'", 60000)
        vis = await pg.get_attribute('[data-testid=recording-row]', 'data-visibility')
        check("Recording ready and private by default", ready and vis == "private", vis)
        await pg.click('[data-testid=rec-publish]')
        pub = await until(pg, "document.querySelector('[data-testid=recording-row]')?.dataset.visibility === 'public'", 10000)
        check("Publish the recording when the creator chooses", pub)
        mtxB.terminate()

        logs = open("/tmp/api.log").read() + open("/tmp/lono_mtx.log").read()
        check("No stream keys in logs", not any(k in logs for k in ("yt-STUDIO-1111", "fb-STUDIO-2222", "tw-STUDIO-3333")))
        print("JS ERRORS:", errs[:5], flush=True)
        print(f"SUMMARY {sum(r[1] for r in results)}/{len(results)} passed", flush=True)
        json.dump(results, open("/tmp/studio_results.json", "w"))
        await br.close()

asyncio.run(main())
