from datetime import timedelta

import app.routers.watch as watch
from app.util import now as real_now


def bal(client, user):
    return client.get("/api/wallet", headers=user["h"]).json()["wallet"]["lono_balance"]


def test_stake_and_early_unstake(client, user):
    s = client.post("/api/wallet/stake", json={"amount": 40, "lock_days": 90}, headers=user["h"]).json()
    assert s["apy"] == 14 and bal(client, user) == 60
    assert client.post("/api/wallet/stake", json={"amount": 1000, "lock_days": 30}, headers=user["h"]).status_code == 400
    assert client.post("/api/wallet/stake", json={"amount": 5, "lock_days": 45}, headers=user["h"]).status_code == 422
    r = client.post(f"/api/wallet/unstake/{s['id']}", headers=user["h"]).json()
    assert r["early"] is True and r["reward"] == 0 and bal(client, user) == 100
    assert client.post(f"/api/wallet/unstake/{s['id']}", headers=user["h"]).status_code == 404


def test_ledger_reconciles(client, user):
    client.post("/api/payments/token-buy", json={"amount_usd": 18.4}, headers=user["h"])
    client.post("/api/wallet/stake", json={"amount": 30, "lock_days": 30}, headers=user["h"])
    w = client.get("/api/wallet", headers=user["h"]).json()["wallet"]
    txs = client.get("/api/wallet/transactions", headers=user["h"]).json()
    assert round(sum(t["amount"] for t in txs), 4) == round(w["lono_balance"], 4)
    assert w["lono_balance"] == 170 and w["staked"] == 30


def test_token_buy_capped(client, user):
    assert client.post("/api/payments/token-buy", json={"amount_usd": 5000}, headers=user["h"]).status_code == 422


def test_watch_to_earn_needs_real_time(client, user, monkeypatch):
    cid = client.get("/api/content", params={"kind": "movie"}).json()[0]["id"]
    s = client.post("/api/watch/start", json={"content_id": cid}, headers=user["h"]).json()
    assert s["earning"] is True
    # Rapid-fire heartbeats earn nothing: no wall-clock time has passed.
    for _ in range(20):
        r = client.post("/api/watch/heartbeat", json={"session_id": s["session_id"]}, headers=user["h"]).json()
    assert r["session_earned"] == 0

    clock = {"t": real_now()}
    monkeypatch.setattr(watch, "now", lambda: clock["t"])
    for _ in range(6):  # 6 x 30s of verified playback = 3 minutes
        clock["t"] += timedelta(seconds=30)
        r = client.post("/api/watch/heartbeat", json={"session_id": s["session_id"]}, headers=user["h"]).json()
    assert r["session_earned"] == 3 and bal(client, user) == 103

    # A long silent gap is capped at 1.5x the heartbeat, not credited in full.
    clock["t"] += timedelta(hours=2)
    r = client.post("/api/watch/heartbeat", json={"session_id": s["session_id"]}, headers=user["h"]).json()
    assert r["verified_sec"] == 225

    # Paused time earns nothing.
    clock["t"] += timedelta(seconds=30)
    r2 = client.post("/api/watch/heartbeat", json={"session_id": s["session_id"], "playing": False},
                     headers=user["h"]).json()
    assert r2["verified_sec"] == 225


def test_watch_reward_cap_per_title(client, user, monkeypatch):
    cid = client.get("/api/content", params={"kind": "series"}).json()[0]["id"]
    s = client.post("/api/watch/start", json={"content_id": cid}, headers=user["h"]).json()
    clock = {"t": real_now()}
    monkeypatch.setattr(watch, "now", lambda: clock["t"])
    for _ in range(60):  # 30 minutes
        clock["t"] += timedelta(seconds=30)
        r = client.post("/api/watch/heartbeat", json={"session_id": s["session_id"]}, headers=user["h"]).json()
    assert r["session_earned"] == 10 and r["capped"] is True


def test_other_users_session_rejected(client, user):
    cid = client.get("/api/content").json()[0]["id"]
    s = client.post("/api/watch/start", json={"content_id": cid}).json()  # anonymous
    assert s["earning"] is False
    assert client.post("/api/watch/heartbeat", json={"session_id": s["session_id"]}, headers=user["h"]).status_code == 404


def test_governance(client, user):
    props = client.get("/api/governance/proposals").json()
    active = next(p for p in props if p["status"] == "active")
    closed = next(p for p in props if p["status"] == "passed")
    r = client.post("/api/governance/vote", json={"proposal_id": active["id"], "choice": "for"}, headers=user["h"])
    assert r.status_code == 200 and r.json()["power"] == 100
    again = client.post("/api/governance/vote", json={"proposal_id": active["id"], "choice": "against"}, headers=user["h"])
    assert again.status_code == 400
    assert client.post("/api/governance/vote", json={"proposal_id": closed["id"], "choice": "for"},
                       headers=user["h"]).status_code == 400
    mine = {p["id"]: p["my_vote"] for p in client.get("/api/governance/proposals", headers=user["h"]).json()}
    assert mine[active["id"]] == "for"
    # Proposing needs 100 staked
    body = {"title": "Add a jazz radio channel", "summary": "A 24/7 jazz station curated by the community."}
    assert client.post("/api/governance/proposals", json=body, headers=user["h"]).status_code == 400
    client.post("/api/wallet/stake", json={"amount": 100, "lock_days": 30}, headers=user["h"])
    assert client.post("/api/governance/proposals", json=body, headers=user["h"]).status_code == 200


def test_tokenomics_live_numbers(client, user):
    t = client.get("/api/tokenomics").json()
    assert t["simulated"] is True and t["total_wallets"] >= 1 and len(t["chart_7d"]) == 7
