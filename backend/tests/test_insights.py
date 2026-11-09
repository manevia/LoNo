from datetime import timedelta

import app.routers.watch as watch
from app.util import now as real_now


def watch_minutes(client, user, monkeypatch, content_id, minutes):
    s = client.post("/api/watch/start", json={"content_id": content_id}, headers=user["h"]).json()
    clock = {"t": real_now()}  # start the fake clock after the session opens
    monkeypatch.setattr(watch, "now", lambda: clock["t"])
    for _ in range(minutes * 2):
        clock["t"] += timedelta(seconds=30)
        client.post("/api/watch/heartbeat", json={"session_id": s["session_id"], "position_sec": 30 * (_ + 1)},
                    headers=user["h"])


def test_insights_breakdown_and_streak(client, user, monkeypatch):
    movie = client.get("/api/content", params={"kind": "movie"}).json()[0]
    watch_minutes(client, user, monkeypatch, movie["id"], 3)
    r = client.get("/api/wallet/insights", params={"days": 7}, headers=user["h"])
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["series"]) == 7 and d["series"][-1]["date"] == real_now().strftime("%Y-%m-%d")
    assert d["totals"]["watching"] == 3 and d["totals"]["bonus"] == 100
    assert d["total_earned"] == 103
    assert d["series"][-1]["watching"] == 3 and d["series"][-1]["watch_minutes"] == 3
    assert d["streak_days"] == 1
    # purchases and stakes are not earnings
    client.post("/api/payments/token-buy", json={"amount_usd": 10}, headers=user["h"])
    assert client.get("/api/wallet/insights", headers=user["h"]).json()["total_earned"] == 103


def test_insights_periods(client, user):
    for days in (7, 30, 90):
        assert len(client.get("/api/wallet/insights", params={"days": days}, headers=user["h"]).json()["series"]) == days
    assert client.get("/api/wallet/insights", params={"days": 12}, headers=user["h"]).status_code == 422
    assert client.get("/api/wallet/insights").status_code == 401


def test_history_progress_and_clear(client, user, monkeypatch):
    items = client.get("/api/content", params={"kind": "series"}).json()[:2]
    for it in items:
        watch_minutes(client, user, monkeypatch, it["id"], 1)
    watch_minutes(client, user, monkeypatch, items[0]["id"], 2)  # rewatch first title
    h = client.get("/api/me/history", headers=user["h"]).json()
    assert [x["content"]["id"] for x in h] == [items[0]["id"], items[1]["id"]]  # newest first, no duplicates
    assert h[0]["position_sec"] == 120
    assert h[0]["percent"] == round(100 * 120 / items[0]["duration_sec"])
    assert client.delete("/api/me/history", headers=user["h"]).json()["ok"]
    assert client.get("/api/me/history", headers=user["h"]).json() == []


def test_detail_reports_resume_position(client, user, monkeypatch):
    item = client.get("/api/content", params={"kind": "movie"}).json()[1]
    assert client.get(f"/api/content/{item['id']}", headers=user["h"]).json()["viewer"]["position_sec"] == 0
    watch_minutes(client, user, monkeypatch, item["id"], 2)
    assert client.get(f"/api/content/{item['id']}", headers=user["h"]).json()["viewer"]["position_sec"] == 120
