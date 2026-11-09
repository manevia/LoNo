"""Staging rehearsal of the first paid campaign (see docs/PILOT-OPERATOR-GUIDE.md).

Needs a LoNo API in pilot mode (PILOT_MODE=true) on a real MongoDB, an admin
account (ADMIN_EMAILS / ADMIN_PASSWORD), Playwright with Chromium, and two test
videos the browser can play: PREVIEW_MP4 and REPLAY_MP4.

Covers: the organizer uploading through the creator workflow; staff creating a
campaign in the admin console; opening refused until funded; a fan earning
points and claiming a pass on a phone-sized screen; simultaneous claims for the
last pass; an unauthorized viewer blocked; a reversal; settlement; and the report
reconciling with the points ledger and the cash records."""
import asyncio, json, os, time, uuid
from datetime import datetime, timedelta, timezone
import httpx
from playwright.async_api import async_playwright

B = os.environ.get("LONO_URL", "http://127.0.0.1:8001"); API = B + "/api"
ADMIN = (os.environ.get("ADMIN_EMAIL", "msf@ciu.edu.lr"), os.environ.get("ADMIN_PASSWORD", "E2e-Admin-Pass1"))
PREVIEW, REPLAY = os.environ.get("PREVIEW_MP4", "/tmp/pilot/preview.mp4"), os.environ.get("REPLAY_MP4", "/tmp/pilot/replay.mp4")
CHROME = os.environ.get("CHROME") or None
SHOTS = os.environ.get("SHOTS", "/tmp/shots")
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def local(dt):  # value for <input type=datetime-local>
    return dt.astimezone().strftime("%Y-%m-%dT%H:%M")


async def register(c, name):
    r = await c.post(f"{API}/auth/register", json={"email": f"{name.lower().replace(' ', '')}{uuid.uuid4().hex[:6]}@example.com",
                                                    "password": "Passw0rd!", "name": name, "accept_terms": True})
    d = r.json()
    return {"id": d["user"]["id"], "token": d["token"], "h": {"Authorization": f"Bearer {d['token']}"}, "name": name}


async def earn_by_watching(c, fan, preview_id, secs=33):
    """The pilot's earning rule, through the normal verified-watching API (real time)."""
    s = (await c.post(f"{API}/watch/start", headers=fan["h"], json={"content_id": preview_id})).json()
    await asyncio.sleep(secs)
    await c.post(f"{API}/watch/heartbeat", headers=fan["h"], json={"session_id": s["session_id"], "playing": True, "position_sec": secs})


async def balance(c, fan):
    return (await c.get(f"{API}/wallet", headers=fan["h"])).json()["wallet"]["lono_balance"]


async def main():
    os.makedirs(SHOTS, exist_ok=True)
    c = httpx.AsyncClient(timeout=60)
    admin_tok = (await c.post(f"{API}/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})).json()["token"]
    AH = {"Authorization": f"Bearer {admin_tok}"}
    cfg = (await c.get(f"{API}/config")).json()
    check("Staging runs in pilot mode (no simulated purchases)", cfg.get("pilot_mode") and not cfg.get("simulated_token_purchase"))

    # ---------- organizer uploads preview and replay through the creator workflow ----------
    org = await register(c, "County FA Media")
    ids = {}
    for key, path, kind, title in (("preview", PREVIEW, "short", "Rehearsal Final: match preview"), ("replay", REPLAY, "movie", "Rehearsal Final: full replay")):
        with open(path, "rb") as f:
            up = (await c.post(f"{API}/storage/upload", headers=org["h"], files={"file": (os.path.basename(path), f, "video/mp4")})).json()
        item = (await c.post(f"{API}/creator/upload", headers=org["h"], json={"title": title, "kind": kind, "category": "Sports",
                                                                             "thumbnail_url": "/icons/icon-512.png", "stream_url": up["url"], "duration_sec": 60})).json()
        ids[key] = item["id"]
    check("Organizer uploads preview and replay through the creator workflow", all(ids.values()))

    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path=CHROME, args=["--autoplay-policy=no-user-gesture-required"])
        errs = []

        # ---------- staff creates the campaign in the admin console ----------
        staff = await br.new_context(viewport={"width": 1400, "height": 1000})
        sp = await staff.new_page(); sp.on("pageerror", lambda e: errs.append(str(e)))
        sp.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await sp.goto(B + "/"); await sp.evaluate(f"localStorage.setItem('lono_token', '{admin_tok}')")
        await sp.goto(B + "/admin"); await sp.click('[data-testid=admin-tab-campaigns]'); await sp.click('[data-testid=c-new]')
        for kind, name in (("sponsor", "Test Sponsor Ltd"), ("organizer", "Test County FA")):
            await sp.locator('[data-testid=new-campaign] select').nth(2).select_option(kind)
            await sp.fill('[data-testid=p-name]', name); await sp.click('[data-testid=p-add]'); await sp.wait_for_timeout(500)
        await sp.fill('[data-testid=c-title]', 'Rehearsal Final: full-match replay')
        for tid, q in (("c-replay", "Rehearsal Final: full"), ("c-preview", "Rehearsal Final: match")):
            await sp.fill(f'[data-testid={tid}]', q); await sp.wait_for_selector(f'[data-testid={tid}-hit]'); await sp.click(f'[data-testid={tid}-hit] >> nth=0')
        await sp.fill('input[type=number] >> nth=0', "0.5")                                    # minutes to watch
        await sp.fill('[data-testid=c-price]', "30"); await sp.fill('[data-testid=c-inventory]', "3")
        now = datetime.now(timezone.utc)
        await sp.fill('[data-testid=c-opens]', local(now - timedelta(minutes=2))); await sp.fill('[data-testid=c-closes]', local(now + timedelta(hours=3)))
        await sp.fill('[data-testid=c-sponsor-pay]', "500"); await sp.fill('[data-testid=c-org-pay]', "300"); await sp.fill('[data-testid=c-fee]', "150")
        await sp.fill('[data-testid=c-cost-0]', "50")
        await sp.click('[data-testid=c-create]')
        await sp.wait_for_selector('[data-testid=campaign-detail]')
        lst = (await c.get(f"{API}/admin/campaigns", headers=AH)).json()
        camp = next(x for x in lst if x["title"] == "Rehearsal Final: full-match replay")
        cid = camp["id"]
        check("Staff create a draft campaign in the admin console", camp["status"] == "draft" and camp["inventory_total"] == 3 and camp["earning_rule"]["min_seconds"] == 30)

        # ---------- cannot open unfunded ----------
        disabled = await sp.is_disabled('[data-testid=c-open]')
        r = await c.post(f"{API}/admin/campaigns/{cid}/open", headers=AH)
        check("Staff cannot open an unfunded campaign (button disabled; API refuses)", disabled and r.status_code == 409, r.json()["detail"])
        fan_probe = await register(c, "Probe Fan")
        check("Fans can't see the draft offer", (await c.get(f"{API}/offers/{cid}", headers=fan_probe["h"])).status_code == 404)
        await sp.fill('[data-testid=conf-pay-ref]', "INV-REH-001 / bank ref 99812"); await sp.fill('[data-testid=conf-pay-amt]', "500"); await sp.click('[data-testid=conf-pay]'); await sp.wait_for_timeout(800)
        await sp.fill('[data-testid=conf-perm-ref]', "Distribution agreement TCFA-2026-01"); await sp.click('[data-testid=conf-perm]'); await sp.wait_for_timeout(800)
        await sp.click('[data-testid=conf-play]'); await sp.wait_for_timeout(800)
        await sp.click('[data-testid=c-open]'); await sp.wait_for_timeout(1000)
        status = await sp.inner_text('[data-testid=c-status]')
        hist = (await c.get(f"{API}/admin/campaigns/{cid}", headers=AH)).json()["history"]
        check("After payment, permission and playback are confirmed, staff open the offer", status == "open", status)
        check("Every change is recorded with who made it", all(h.get("by_name") for h in hist) and {"created", "confirmed_sponsor_payment", "confirmed_distribution_permission", "confirmed_playback_ready", "opened"} <= {h["action"] for h in hist})
        await sp.screenshot(path=f"{SHOTS}/pilot_01_staff.png", full_page=True)

        # ---------- fan on a phone: earn, see the offer, claim, watch ----------
        phone = await br.new_context(**p.devices["iPhone 13"])
        fp = await phone.new_page(); fp.on("pageerror", lambda e: errs.append(str(e)))
        await fp.goto(B + "/signup")
        await fp.fill('[data-testid=signup-name]', 'Phone Fan'); await fp.fill('[data-testid=signup-email]', f"phonefan{uuid.uuid4().hex[:6]}@example.com")
        await fp.fill('[data-testid=signup-password]', 'Passw0rd!'); await fp.check('[data-testid=signup-terms]'); await fp.click('[data-testid=signup-submit]')
        await fp.wait_for_url(B + "/")
        fan_tok = await fp.evaluate("localStorage.getItem('lono_token')")
        FAN = {"h": {"Authorization": f"Bearer {fan_tok}"}}
        check("Pilot: no signup bonus (points only from verified activity)", await balance(c, FAN) == 0)
        await fp.goto(B + "/offers"); await fp.click(f'[data-testid=offer-{cid}]'); await fp.wait_for_selector('[data-testid=offer-detail]')
        facts = await fp.inner_text('[data-testid=offer-facts]')
        sponsor = await fp.inner_text('[data-testid=offer-sponsor]')
        check("Offer shows sponsor, points, passes left, claim deadline and access period before claiming",
              sponsor == "Test Sponsor Ltd" and "30 $LONO" in facts and "3 of 3" in facts and "Claim by" in facts and "7 days" in facts, facts.replace("\n", " | "))
        check("Claim is blocked until the fan has enough points", await fp.is_disabled('[data-testid=claim-btn]'))
        await fp.screenshot(path=f"{SHOTS}/pilot_02_offer_mobile.png", full_page=True)
        await fp.click('[data-testid=earn-watch]')
        await fp.wait_for_selector('[data-testid=video-player]')
        await fp.evaluate("document.querySelector('[data-testid=video-player]').play()")   # the fan taps Play
        await fp.wait_for_function("document.querySelector('[data-testid=video-player]')?.currentTime > 1", timeout=20000)
        await fp.wait_for_timeout(36000)                                   # watch 30+ seconds of the preview
        await fp.go_back(); await fp.wait_for_selector('[data-testid=offer-detail]'); await fp.wait_for_timeout(1500)
        earned_txt = await fp.inner_text('[data-testid=earn-task]')
        bal = await balance(c, FAN)
        check("Fan earns points by watching the preview (verified viewing)", "Earned" in earned_txt and bal >= 30, f"balance {bal}")
        await fp.click('[data-testid=claim-btn]'); await fp.wait_for_selector('[data-testid=claim-confirm]')
        confirm_txt = await fp.inner_text('[data-testid=claim-confirm]')
        await fp.click('[data-testid=claim-yes]')
        await fp.wait_for_selector('[data-testid=pass-player]', timeout=15000)
        await fp.wait_for_selector('[data-testid=replay-video]')
        await fp.evaluate("document.querySelector('[data-testid=replay-video]').play()")    # tap Play
        await fp.wait_for_function("document.querySelector('[data-testid=replay-video]')?.videoWidth > 0 && document.querySelector('[data-testid=replay-video]').currentTime > 1", timeout=20000)
        check("Fan confirms and claims on mobile; the replay plays on the phone", "30 $LONO" in confirm_txt and await balance(c, FAN) == bal - 30)
        await fp.screenshot(path=f"{SHOTS}/pilot_03_replay_mobile.png")
        await fp.wait_for_timeout(36000)                                   # a real replay view (≥30 s verified)
        await fp.goto(B + "/passes"); await fp.wait_for_selector('[data-testid=passes-page]')
        has_pass = await fp.locator('[data-testid^=pass-]').count()
        check("The replay is easy to find in My passes", has_pass >= 1)
        my_claim = (await c.get(f"{API}/offers/{cid}", headers=FAN["h"])).json()["my_claim"]

        # repeated clicks / retries
        before = await balance(c, FAN)
        rs = await asyncio.gather(*[c.post(f"{API}/offers/{cid}/claim", headers=FAN["h"]) for _ in range(5)])
        same = {r.json()["claim"]["id"] for r in rs if r.status_code == 200}
        check("Repeated clicks and retries return the existing claim without a second deduction", same == {my_claim["id"]} and await balance(c, FAN) == before)

        # ---------- simultaneous claims for the last pass ----------
        fans = await asyncio.gather(*[register(c, f"Fan {i}") for i in range(12)])
        await asyncio.gather(*[earn_by_watching(c, f, ids["preview"]) for f in fans])
        bals = await asyncio.gather(*[balance(c, f) for f in fans])
        check("Twelve more fans earn points through the same verified-viewing rule", all(b >= 30 for b in bals), f"min {min(bals)}")
        first = await c.post(f"{API}/offers/{cid}/claim", headers=fans[0]["h"])                  # leaves exactly one pass
        left = (await c.get(f"{API}/offers/{cid}", headers=fans[1]["h"])).json()["remaining"]
        racers = fans[1:]
        before = {f["id"]: await balance(c, f) for f in racers}
        t0 = time.time()
        rs = await asyncio.gather(*[c.post(f"{API}/offers/{cid}/claim", headers=f["h"]) for f in racers])
        took = time.time() - t0
        wins = [f for f, r in zip(racers, rs) if r.status_code == 200]
        losers = [f for f, r in zip(racers, rs) if r.status_code != 200]
        kept = all([await balance(c, f) == before[f["id"]] for f in losers])
        check(f"{len(racers)} fans claim the last pass at the same moment: exactly one wins, the others keep their points",
              first.status_code == 200 and left == 1 and len(wins) == 1 and kept and all(r.status_code == 409 for r in rs if r.status_code != 200),
              f"{len(wins)} winner, {len(losers)} refused in {took:.2f}s, codes {sorted({r.status_code for r in rs})}")
        after_left = (await c.get(f"{API}/offers/{cid}", headers=fans[1]["h"])).json()["remaining"]
        check("Inventory never goes below zero", after_left == 0)

        # ---------- unauthorized viewer ----------
        play = await c.post(f"{API}/me/passes/{my_claim['id']}/play", headers=FAN["h"])
        url = play.json()["url"]
        rc = (await c.get(f"{API}/content/{ids['replay']}")).json()
        file_path = url.split("/api/replay/")[1].split("/", 1)[1]
        stranger = await br.new_context(**p.devices["Pixel 7"])
        sg = await stranger.new_page()
        resp = await sg.goto(B + url)
        anon = await httpx.AsyncClient().get(B + url)
        file_direct = await httpx.AsyncClient().get(f"{B}/api/files/{file_path}")
        check("A viewer without a pass can't play a shared playback URL", resp.status == 403 and anon.status_code == 403, f"browser {resp.status}, anonymous {anon.status_code}")
        check("The replay file can't be fetched directly, and the title doesn't expose it", file_direct.status_code == 403 and "stream_url" not in rc)
        stranger_fan = await register(c, "No Pass Fan")
        await sg.goto(B + "/"); await sg.evaluate(f"localStorage.setItem('lono_token', '{stranger_fan['token']}')")
        await sg.goto(B + f"/watch/{ids['replay']}")
        try:
            await sg.wait_for_selector('[data-testid=gated-title]', timeout=10000)   # page is lazy-loaded
            gated = 1
        except Exception:
            gated = 0
        resp2 = await sg.goto(B + url)
        print("signed-in stranger: gated card", gated, "| shared URL status", resp2.status if resp2 else None, flush=True)
        check("A signed-in fan without a pass sees 'needs a pass' and still can't use the shared URL", gated == 1 and resp2.status == 403)
        await sg.goto(B + f"/watch/{ids['replay']}"); await sg.screenshot(path=f"{SHOTS}/pilot_04_no_pass.png")

        # ---------- reversal ----------
        claims = (await c.get(f"{API}/admin/campaigns/{cid}/claims", headers=AH)).json()
        cl = next(x for x in claims if x["user_id"] == fans[0]["id"])
        b0 = await balance(c, fans[0])
        r1 = (await c.post(f"{API}/admin/campaigns/{cid}/claims/{cl['id']}/reverse", headers=AH, json={"reason": "Rehearsal: fan reported playback failure", "return_pass": True})).json()
        r2 = (await c.post(f"{API}/admin/campaigns/{cid}/claims/{cl['id']}/reverse", headers=AH, json={"reason": "duplicate", "return_pass": True})).json()
        left2 = (await c.get(f"{API}/offers/{cid}", headers=fans[1]["h"])).json()["remaining"]
        check("Staff reverse a failed redemption: points restored exactly once; pass back in inventory while open",
              r1["refunded"] == 30 and r2.get("already_reversed") and await balance(c, fans[0]) == b0 + 30 and left2 == 1)

        # ---------- settlement, rebooking, reports ----------
        await sp.goto(B + "/admin"); await sp.click('[data-testid=admin-tab-campaigns]'); await sp.click(f'[data-testid=c-row-{cid}]')
        await sp.wait_for_selector('[data-testid=campaign-detail]')
        await sp.fill('[data-testid=s-invoice]', "INV-REH-001"); await sp.locator('[data-testid=s-invoice] + button').click(); await sp.wait_for_timeout(600)
        await sp.fill('[data-testid=s-org-amt]', "300"); await sp.fill('[data-testid=s-org-ref]', "Bank transfer TRF-REH-77"); await sp.click('[data-testid=s-org-save]'); await sp.wait_for_timeout(800)
        await sp.select_option('[data-testid=rebook-sponsor]', "yes"); await sp.wait_for_timeout(800)
        rep = (await c.get(f"{API}/admin/campaigns/{cid}/report", headers=AH)).json()
        m, rcn = rep["money"], rep["reconciliation"]
        check("Campaign report: passes available/claimed, unique viewers, repeat window, payments, contribution",
              rep["passes"]["available"] == 3 and rep["passes"]["claimed"] == 2 and rep["viewing"]["unique_viewers"] >= 1 and
              m["sponsor_payment_received"] == 500 and m["organizer_paid"] == 300 and m["contribution_after_direct_costs"] == 150,
              f"claimed {rep['passes']['claimed']}, viewers {rep['viewing']['unique_viewers']}, contribution {m['contribution_after_direct_costs']}")
        check("Report reconciles with the points ledger and the cash records", rcn["all_ok"], json.dumps({k: v for k, v in rcn.items() if k.endswith("ok")}))

        # independent ledger check: every fan's balance equals the sum of their transactions
        mismatches = []
        for f in [FAN] + list(fans):
            w = (await c.get(f"{API}/wallet", headers=f["h"])).json()["wallet"]["lono_balance"]
            txs = (await c.get(f"{API}/wallet/transactions", headers=f["h"])).json()
            if abs(sum(t["amount"] for t in txs) - w) > 1e-6:
                mismatches.append(w)
        check("Every fan's balance equals the sum of their ledger entries", not mismatches, f"{len(mismatches)} mismatches")
        spr = (await c.get(f"{API}/admin/campaigns/{cid}/sponsor-report", headers=AH)).json()
        csv = (await c.get(f"{API}/admin/campaigns/{cid}/sponsor-report.csv", headers=AH)).text
        check("Sponsor report separates claimed passes from actual replay views; export and rebooking field",
              spr["passes_claimed"] == 2 and spr["fans_who_watched_the_replay"] >= 1 and spr["claimed_but_not_yet_watched"] == spr["passes_claimed"] - spr["fans_who_watched_the_replay"]
              and "rebooked: sponsor,yes" in csv and "500" not in csv, f"claimed {spr['passes_claimed']}, watched {spr['fans_who_watched_the_replay']}")
        await sp.screenshot(path=f"{SHOTS}/pilot_05_report.png", full_page=True)

        # ---------- pause and close ----------
        no_pass = losers[0]                                    # a fan who doesn't hold a pass
        await c.post(f"{API}/admin/campaigns/{cid}/pause", headers=AH)
        paused = await c.post(f"{API}/offers/{cid}/claim", headers=no_pass["h"])
        await c.post(f"{API}/admin/campaigns/{cid}/close", headers=AH)
        closed = await c.post(f"{API}/offers/{cid}/claim", headers=no_pass["h"])
        replay_still = (await c.post(f"{API}/me/passes/{my_claim['id']}/play", headers=FAN["h"])).status_code
        check("Pause and close stop new claims; claimed passes keep working", paused.status_code == 409 and closed.status_code == 409 and replay_still == 200)
        check("No browser errors", not errs, str(errs[:3]))
        await br.close()
    print(f"SUMMARY {sum(r[1] for r in results)}/{len(results)} passed", flush=True)
    json.dump(results, open("/tmp/pilot_results.json", "w"))

asyncio.run(main())
