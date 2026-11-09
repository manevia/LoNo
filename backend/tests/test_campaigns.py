"""Commercial pilot: funded campaigns, earning, claims, protected replay, reversal, reports."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app import config
from app.db import db
from app.routers import campaigns as cmp
from app.storage import storage
from app.util import uid
from test_course_builder import make_user


def _iso(delta_min=0):
    return (datetime.now(timezone.utc) + timedelta(minutes=delta_min)).isoformat()


def _run(coro):
    return asyncio.run(coro)


def setup_assets(client):
    """A protected replay (uploaded MP4) and a public preview."""
    path = f"uploads/test/{uid()}.mp4"
    preview_id, replay_id = uid(), uid()

    async def go():
        await storage.put(path, b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 4096, "video/mp4")
        await db.files.insert_one({"id": uid(), "user_id": "org", "storage_path": path, "content_type": "video/mp4",
                                   "size": 4108, "is_deleted": False})
        base = {"description": "", "category": "Sports", "thumbnail_url": "/icons/icon-512.png", "duration_sec": 5400,
                "is_original": False, "is_premium": False, "views": 0, "likes": 0, "year": 2026, "created_at": _iso()}
        await db.content.insert_one({**base, "id": preview_id, "title": "Final: match preview", "kind": "short",
                                     "stream_url": "https://example.com/preview.mp4"})
        await db.content.insert_one({**base, "id": replay_id, "title": "Final: full replay", "kind": "movie",
                                     "stream_url": f"/api/files/{path}"})
    _run(go())
    return preview_id, replay_id, path


def partners(client, admin):
    org = client.post("/api/admin/campaigns/partners", headers=admin["h"], json={"kind": "organizer", "name": "County FA"}).json()
    spo = client.post("/api/admin/campaigns/partners", headers=admin["h"], json={"kind": "sponsor", "name": "Lone Star Cell"}).json()
    return org, spo


def draft(client, admin, inventory=3, price=30, min_seconds=30, points=30, closes_in=120):
    preview, replay, path = setup_assets(client)
    org, spo = partners(client, admin)
    body = {"title": "County Final replay", "organizer_id": org["id"], "sponsor_id": spo["id"], "replay_content_id": replay,
            "earning_rule": {"content_id": preview, "min_seconds": min_seconds, "points": points},
            "points_price": price, "inventory_total": inventory, "opens_at": _iso(-5), "closes_at": _iso(closes_in),
            "access_days": 7, "financials": {"currency": "USD", "sponsor_payment": 500, "organizer_compensation": 300,
                                             "lono_fee": 150, "direct_costs": [{"label": "Hosting and delivery", "amount": 50}]}}
    r = client.post("/api/admin/campaigns", headers=admin["h"], json=body)
    assert r.status_code == 200, r.text
    return r.json(), preview, replay, path


def fund_and_open(client, admin, c):
    h = admin["h"]
    client.post(f"/api/admin/campaigns/{c['id']}/confirm", headers=h, json={"item": "sponsor_payment", "reference": "INV-001 / bank 7781", "amount": 500})
    client.post(f"/api/admin/campaigns/{c['id']}/confirm", headers=h, json={"item": "distribution_permission", "reference": "Agreement CFA-2026-11"})
    r = client.post(f"/api/admin/campaigns/{c['id']}/confirm", headers=h, json={"item": "playback_ready"})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/admin/campaigns/{c['id']}/open", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "open", r.text


def give_points(user_id, amount):
    _run(db.users.update_one({"id": user_id}, {"$set": {"wallet.lono_balance": float(amount)}}))


def balance(user_id):
    return _run(db.users.find_one({"id": user_id}))["wallet"]["lono_balance"]


# ------------------------------------------------------------------ staff
def test_staff_only_and_cannot_open_unfunded(client, admin):
    fan = make_user(client)
    assert client.get("/api/admin/campaigns", headers=fan["h"]).status_code == 403
    c, *_ = draft(client, admin)
    r = client.post(f"/api/admin/campaigns/{c['id']}/open", headers=admin["h"])
    assert r.status_code == 409 and "sponsor payment" in r.json()["detail"]
    # payment must have a reference and cover the agreed amount
    assert client.post(f"/api/admin/campaigns/{c['id']}/confirm", headers=admin["h"], json={"item": "sponsor_payment", "amount": 500}).status_code == 422
    assert client.post(f"/api/admin/campaigns/{c['id']}/confirm", headers=admin["h"], json={"item": "sponsor_payment", "reference": "x", "amount": 100}).status_code == 422
    client.post(f"/api/admin/campaigns/{c['id']}/confirm", headers=admin["h"], json={"item": "sponsor_payment", "reference": "INV-1", "amount": 500})
    r = client.post(f"/api/admin/campaigns/{c['id']}/open", headers=admin["h"])
    assert r.status_code == 409 and "distribution permission" in r.json()["detail"]
    # fans can't see a draft
    assert client.get(f"/api/offers/{c['id']}", headers=fan["h"]).status_code == 404
    hist = client.get(f"/api/admin/campaigns/{c['id']}", headers=admin["h"]).json()["history"]
    assert [h["action"] for h in hist][:2] == ["created", "confirmed_sponsor_payment"] and hist[0]["by_name"]


def test_external_replay_cannot_be_protected(client, admin):
    preview, replay, _ = setup_assets(client)
    org, spo = partners(client, admin)
    body = {"title": "x x x", "organizer_id": org["id"], "sponsor_id": spo["id"], "replay_content_id": preview,
            "earning_rule": {"content_id": replay, "min_seconds": 30, "points": 5}, "points_price": 5, "inventory_total": 1,
            "opens_at": _iso(-5), "closes_at": _iso(60), "access_days": 1,
            "financials": {"sponsor_payment": 1, "organizer_compensation": 0, "lono_fee": 1}}
    r = client.post("/api/admin/campaigns", headers=admin["h"], json=body)
    assert r.status_code == 422 and "uploaded to LoNo" in r.json()["detail"]


# ------------------------------------------------------------------ earning
def test_earn_by_watching_preview_once(client, admin):
    c, preview, *_ = draft(client, admin)
    fund_and_open(client, admin, c)
    fan = make_user(client)
    give_points(fan["id"], 0)
    s = client.post("/api/watch/start", headers=fan["h"], json={"content_id": preview}).json()
    for _ in range(2):
        _run(db.watch_sessions.update_one({"id": s["session_id"]}, {"$set": {"last_beat_at": _iso(-0.6)}}))   # 36 s ago
        client.post("/api/watch/heartbeat", headers=fan["h"], json={"session_id": s["session_id"], "playing": True, "position_sec": 60})
    assert balance(fan["id"]) >= 30                      # bonus (+ normal watch-to-earn)
    before = balance(fan["id"])
    _run(db.watch_sessions.update_one({"id": s["session_id"]}, {"$set": {"last_beat_at": _iso(-0.6)}}))
    client.post("/api/watch/heartbeat", headers=fan["h"], json={"session_id": s["session_id"], "playing": True, "position_sec": 90})
    assert balance(fan["id"]) - before < 30              # bonus not paid twice
    o = client.get(f"/api/offers/{c['id']}", headers=fan["h"]).json()
    assert o["my_progress"]["earned"] is True and o["sponsor"]["name"] == "Lone Star Cell"
    assert {"points_price", "remaining", "closes_at", "access_days"} <= set(o)


# ------------------------------------------------------------------ claims
def test_claim_insufficient_then_ok_and_idempotent(client, admin):
    c, *_ = draft(client, admin)
    fund_and_open(client, admin, c)
    fan = make_user(client)
    give_points(fan["id"], 10)
    r = client.post(f"/api/offers/{c['id']}/claim", headers=fan["h"])
    assert r.status_code == 402 and balance(fan["id"]) == 10
    assert client.get(f"/api/offers/{c['id']}", headers=fan["h"]).json()["remaining"] == 3     # pass released
    give_points(fan["id"], 45)
    a = client.post(f"/api/offers/{c['id']}/claim", headers=fan["h"]).json()
    b = client.post(f"/api/offers/{c['id']}/claim", headers=fan["h"]).json()                 # double click / retry
    assert a["claim"]["id"] == b["claim"]["id"] and a["claim"]["status"] == "active"
    assert balance(fan["id"]) == 15
    txs = _run(db.transactions.find({"ref": a["claim"]["id"], "kind": "pass_claim"}).to_list(10))
    assert len(txs) == 1
    passes = client.get("/api/me/passes", headers=fan["h"]).json()
    assert passes[0]["valid"] and passes[0]["replay"]["title"] == "Final: full replay"


def test_simultaneous_claims_for_last_pass(client, admin):
    c, *_ = draft(client, admin, inventory=1)
    fund_and_open(client, admin, c)
    fans = [make_user(client) for _ in range(10)]
    for f in fans:
        give_points(f["id"], 30)
    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(lambda f: client.post(f"/api/offers/{c['id']}/claim", headers=f["h"]), fans))
    winners = [r for r in results if r.status_code == 200]
    assert len(winners) == 1, [r.status_code for r in results]
    assert all(r.status_code == 409 for r in results if r.status_code != 200)
    balances = [balance(f["id"]) for f in fans]
    assert sorted(balances) == [0.0] + [30.0] * 9                # losers keep their points
    rep = client.get(f"/api/admin/campaigns/{c['id']}/report", headers=admin["h"]).json()
    assert rep["passes"]["claimed"] == 1 and rep["passes"]["remaining"] == 0 and rep["reconciliation"]["all_ok"] is True


def test_cannot_claim_when_paused_or_closed(client, admin):
    c, *_ = draft(client, admin)
    fund_and_open(client, admin, c)
    fan = make_user(client)
    give_points(fan["id"], 100)
    client.post(f"/api/admin/campaigns/{c['id']}/pause", headers=admin["h"])
    assert client.post(f"/api/offers/{c['id']}/claim", headers=fan["h"]).status_code == 409 and balance(fan["id"]) == 100
    client.post(f"/api/admin/campaigns/{c['id']}/resume", headers=admin["h"])
    assert client.post(f"/api/offers/{c['id']}/claim", headers=fan["h"]).status_code == 200
    hist = [h["action"] for h in client.get(f"/api/admin/campaigns/{c['id']}", headers=admin["h"]).json()["history"]]
    assert "paused" in hist and "resumed" in hist


# ------------------------------------------------------------------ replay protection
def test_replay_protected_and_bound_to_the_fan(client, admin):
    c, _, replay, path = draft(client, admin)
    fund_and_open(client, admin, c)
    fan, other = make_user(client), make_user(client)
    give_points(fan["id"], 30)
    cl = client.post(f"/api/offers/{c['id']}/claim", headers=fan["h"]).json()["claim"]
    client.cookies.clear()
    assert client.get(f"/api/files/{path}").status_code == 403                       # direct file URL
    assert "stream_url" not in client.get(f"/api/content/{replay}", headers=other["h"]).json()
    r = client.post(f"/api/me/passes/{cl['id']}/play", headers=fan["h"])
    url, cookie = r.json()["url"], r.cookies.get("lono_replay")
    client.cookies.clear()
    assert client.get(url, cookies={"lono_replay": cookie}, headers={"Range": "bytes=0-99"}).status_code == 206
    assert client.get(url).status_code == 403                                         # shared link, no cookie
    other_pass = client.post(f"/api/me/passes/{cl['id']}/play", headers=other["h"])
    assert other_pass.status_code == 404                                              # can't play someone else's pass
    assert client.get(url.replace(path, "uploads/other/secret.mp4"), cookies={"lono_replay": cookie}).status_code == 403
    tampered = url.split("/api/replay/")[1].split("/")[0]
    assert client.get(url.replace(tampered, tampered[:-2] + "xx"), cookies={"lono_replay": cookie}).status_code == 403
    # reversed pass stops working immediately
    client.post(f"/api/admin/campaigns/{c['id']}/claims/{cl['id']}/reverse", headers=admin["h"], json={"reason": "test"})
    assert client.get(url, cookies={"lono_replay": cookie}).status_code == 403
    client.cookies.clear()


# ------------------------------------------------------------------ reversal
def test_reverse_refunds_once_and_returns_pass_only_if_open(client, admin):
    c, *_ = draft(client, admin, inventory=2)
    fund_and_open(client, admin, c)
    a, b = make_user(client), make_user(client)
    for f in (a, b):
        give_points(f["id"], 30)
    ca = client.post(f"/api/offers/{c['id']}/claim", headers=a["h"]).json()["claim"]
    cb = client.post(f"/api/offers/{c['id']}/claim", headers=b["h"]).json()["claim"]
    r1 = client.post(f"/api/admin/campaigns/{c['id']}/claims/{ca['id']}/reverse", headers=admin["h"], json={"reason": "Playback failed"}).json()
    r2 = client.post(f"/api/admin/campaigns/{c['id']}/claims/{ca['id']}/reverse", headers=admin["h"], json={"reason": "Playback failed"}).json()
    assert r1["refunded"] == 30 and r1["pass_returned"] is True and r2.get("already_reversed") and r2["refunded"] == 0
    assert balance(a["id"]) == 30
    assert client.get(f"/api/offers/{c['id']}", headers=a["h"]).json()["remaining"] == 1
    # fan can claim again after a reversal (fresh attempt on the same record)
    again = client.post(f"/api/offers/{c['id']}/claim", headers=a["h"])
    assert again.status_code == 200 and again.json()["claim"]["status"] == "active" and balance(a["id"]) == 0
    client.post(f"/api/admin/campaigns/{c['id']}/close", headers=admin["h"])
    r3 = client.post(f"/api/admin/campaigns/{c['id']}/claims/{cb['id']}/reverse", headers=admin["h"], json={"reason": "Canceled"}).json()
    assert r3["refunded"] == 30 and r3["pass_returned"] is False                    # closed: not back in inventory
    rec = client.get(f"/api/admin/campaigns/{c['id']}/report", headers=admin["h"]).json()["reconciliation"]
    assert rec["points_ok"] and rec["inventory_ok"], rec


# ------------------------------------------------------------------ reports
def test_reports_and_reconciliation(client, admin):
    c, preview, replay, _ = draft(client, admin)
    fund_and_open(client, admin, c)
    fan = make_user(client)
    give_points(fan["id"], 30)
    client.post(f"/api/offers/{c['id']}/claim", headers=fan["h"])
    s = client.post("/api/watch/start", headers=fan["h"], json={"content_id": replay}).json()
    _run(db.watch_sessions.update_one({"id": s["session_id"]}, {"$set": {"last_beat_at": _iso(-0.6)}}))
    client.post("/api/watch/heartbeat", headers=fan["h"], json={"session_id": s["session_id"], "playing": True, "position_sec": 40})
    assert balance(fan["id"]) == 0                                                    # no generic reward on the gated replay
    client.post(f"/api/admin/campaigns/{c['id']}/settlement", headers=admin["h"],
                json={"sponsor_invoice_ref": "INV-001", "organizer_paid_amount": 300, "organizer_paid_reference": "TRF-55"})
    r = client.get(f"/api/admin/campaigns/{c['id']}/report", headers=admin["h"]).json()
    assert r["passes"]["claimed"] == 1 and r["viewing"]["unique_viewers"] == 1
    m = r["money"]
    assert m["sponsor_payment_received"] == 500 and m["organizer_paid"] == 300 and m["contribution_after_direct_costs"] == 150
    assert m["covers_direct_costs"] and m["fee_variance"] == 0
    assert r["reconciliation"]["all_ok"], r["reconciliation"]
    sp = client.get(f"/api/admin/campaigns/{c['id']}/sponsor-report", headers=admin["h"]).json()
    assert sp["passes_claimed"] == 1 and sp["fans_who_watched_the_replay"] == 1 and "sponsor_payment" not in str(sp)
    client.put(f"/api/admin/campaigns/{c['id']}/rebooking", headers=admin["h"], json={"sponsor": "yes", "organizer": "in_talks", "notes": "Semi-final in March"})
    csv = client.get(f"/api/admin/campaigns/{c['id']}/sponsor-report.csv", headers=admin["h"])
    assert csv.status_code == 200 and "passes claimed,1" in csv.text and "rebooked: sponsor,yes" in csv.text


# ------------------------------------------------------------------ crash repair
def test_repair_interrupted_claim(client, admin):
    c, *_ = draft(client, admin, inventory=2)
    fund_and_open(client, admin, c)
    fan = make_user(client)

    async def crash_after_reserving():
        await db.campaign_claims.insert_one({"id": uid(), "campaign_id": c["id"], "user_id": fan["id"], "status": "pending",
                                             "attempt": "a1", "points": 30, "created_at": _iso(-10), "updated_at": _iso(-10)})
        await db.campaigns.update_one({"id": c["id"]}, {"$inc": {"remaining": -1, "claimed": 1}})
        return await cmp.repair_pending(0)
    assert _run(crash_after_reserving()) == 1
    o = client.get(f"/api/offers/{c['id']}", headers=fan["h"]).json()
    assert o["remaining"] == 2                                                         # reserved pass released


# ------------------------------------------------------------------ pilot mode
def test_pilot_mode_gates(client, monkeypatch):
    fan = make_user(client)
    give_points(fan["id"], 100)
    monkeypatch.setattr(config, "PILOT_MODE", True)
    monkeypatch.setattr(config, "SIMULATED_TOKEN_PURCHASE", False)
    assert client.post("/api/wallet/stake", headers=fan["h"], json={"amount": 10, "lock_days": 30}).status_code == 403
    assert client.post("/api/payments/token-buy", headers=fan["h"], json={"amount_usd": 10}).status_code == 403
    assert balance(fan["id"]) == 100
