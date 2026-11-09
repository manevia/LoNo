from datetime import datetime


def test_guide_shape_and_numbers(client):
    g = client.get("/api/live/guide", params={"hours": 3}).json()
    assert g["tv"] and g["radio"]
    assert [c["number"] for c in g["tv"]] == list(range(1, len(g["tv"]) + 1))
    start, end, nowt = (datetime.fromisoformat(g[k]) for k in ("start", "end", "now"))
    for c in g["tv"] + g["radio"]:
        progs = c["programs"]
        assert progs, c["title"]
        # contiguous, covering the window, and the current program contains "now"
        for a, b in zip(progs, progs[1:]):
            assert a["end"] == b["start"]
        assert datetime.fromisoformat(progs[0]["start"]) <= start and datetime.fromisoformat(progs[-1]["end"]) >= end
        assert c["now"] and datetime.fromisoformat(c["now"]["start"]) <= nowt < datetime.fromisoformat(c["now"]["end"])
        assert c["next"]["start"] == c["now"]["end"]


def test_guide_is_stable(client):
    a = client.get("/api/live/guide").json()
    b = client.get("/api/live/guide").json()
    assert [c["programs"] for c in a["tv"]] == [c["programs"] for c in b["tv"]]


def test_news_channel_gets_news_programs(client):
    g = client.get("/api/live/guide").json()
    news = next(c for c in g["tv"] if c["category"] == "News")
    from app.routers.guide import POOLS
    titles = {t for t, _ in POOLS["News"]}
    assert all(p["title"] in titles for p in news["programs"])
