"""Broadcast integration test. Setup (see docs/BROADCAST.md "Testing"):
  - LoNo API with MEDIA_ENABLED=true and SIGNUPS_PER_IP_PER_HOUR raised, LoNo's MediaMTX,
    and stand-in A:  mediamtx scripts/broadcast/standin_a.yml  (run from scripts/broadcast)
  - certificates for the RTMPS stand-ins in scripts/broadcast/certs (server.key, server.crt)
  - env: MEDIAMTX=path/to/mediamtx, API_LOG, MEDIA_LOG
 real MediaMTX, ffmpeg as the encoder, stand-in
platform receivers (MediaMTX) for YouTube (RTMP), Facebook (RTMPS), Twitch
(initially unreachable) and Custom SRT."""
import json, os, signal, subprocess, time, uuid
import httpx

API = "http://127.0.0.1:8001/api"
B = "http://127.0.0.1:8001"
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def encoder(url, proto="rtmp"):
    fmt = "flv" if proto in ("rtmp", "rtmps") else "mpegts"
    cmd = ["ffmpeg", "-loglevel", "error", "-re", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30",
           "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
           "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency", "-g", "60", "-b:v", "2500k",
           "-c:a", "aac", "-b:a", "128k", "-f", fmt, url]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=open(f"/tmp/enc_{proto}.log", "w"), start_new_session=True)


def standin_ready(api_port):
    try:
        items = httpx.get(f"http://127.0.0.1:{api_port}/v3/paths/list", timeout=3).json()["items"]
        return {p["name"]: p["bytesReceived"] for p in items if p.get("ready")}
    except Exception:
        return {}


def wait(fn, timeout=20, step=0.5):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(step)
    return fn()


c = httpx.Client(timeout=20)
email = f"creator{uuid.uuid4().hex[:6]}@example.com"
tok = c.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!", "name": "Studio Creator", "accept_terms": True}).json()["token"]
H = {"Authorization": f"Bearer {tok}"}

# ---------- ingest + destinations ----------
ing = c.get(f"{API}/broadcast/ingest", headers=H).json()
key = ing["rtmp"]["stream_key"].split("key=")[1]
check("Ingest details: RTMP, RTMPS and SRT", ing["rtmp"]["server"] and ing["rtmps"] and ing["srt"]["url"].startswith("srt://"))
plats = {p["id"]: p for p in c.get(f"{API}/broadcast/platforms", headers=H).json()}
check("All 10 Studio destinations listed; Discord marked unsupported", len(plats) == 10 and not plats["discord"]["supported"])
r = c.post(f"{API}/broadcast/destinations", headers=H, json={"platform": "discord", "server_url": "rtmp://x/y", "stream_key": "k"})
check("Discord can't be added (no stream-key ingest)", r.status_code == 422)
r = c.post(f"{API}/broadcast/destinations", headers=H, json={"platform": "facebook", "server_url": "rtmp://127.0.0.1:2935/fb", "stream_key": "k"})
check("Facebook requires RTMPS", r.status_code == 422)
D = {}
for plat, url, sk in [("youtube", "rtmp://127.0.0.1:2935/youtube", "yt-SECRET-111"),
                      ("facebook", "rtmps://127.0.0.1:2936/facebook", "fb-SECRET-222"),
                      ("twitch", "rtmp://127.0.0.1:3935/twitch", "tw-SECRET-333"),
                      ("custom", "srt://127.0.0.1:9890", "publish:custom-srt")]:
    D[plat] = c.post(f"{API}/broadcast/destinations", headers=H, json={"platform": plat, "server_url": url, "stream_key": sk}).json()
lst = c.get(f"{API}/broadcast/destinations", headers=H).text
check("Stored stream keys are never returned (hint only)", "SECRET" not in lst and D["youtube"]["key_hint"] == "…-111")

# ---------- wrong key rejected ----------
bad = encoder(f"{ing['rtmp']['server']}/{ing['ingest_id']}?key=wrong-key")
time.sleep(4)
check("Encoder with a wrong stream key is rejected", bad.poll() is not None or not standin_ready(9997))
try: os.killpg(bad.pid, signal.SIGTERM)
except ProcessLookupError: pass

# ---------- private test session ----------
s = c.post(f"{API}/broadcast/sessions", headers=H, json={"title": "Mic check", "test": True, "destination_ids": [D["youtube"]["id"]]}).json()
check("Private test session ignores destinations", s["visibility"] == "test" and s["destinations"] == [])
enc = encoder(f"{ing['rtmp']['server']}/{ing['rtmp']['stream_key']}")
feed = wait(lambda: c.get(f"{API}/broadcast/sessions/{s['id']}", headers=H).json()["feed"].get("ready") or None, 20)
st = c.get(f"{API}/broadcast/sessions/{s['id']}", headers=H).json()
time.sleep(3)
st = c.get(f"{API}/broadcast/sessions/{s['id']}", headers=H).json()
check("Feed preview data: connected, video+audio, bitrate", st["feed"]["ready"] and st["feed"]["has_video"] and st["feed"]["has_audio"] and (st["feed"]["bitrate_kbps"] or 0) > 500,
      f"tracks={st['feed'].get('tracks')} kbps={st['feed'].get('bitrate_kbps')}")
pl = wait(lambda: (lambda r: r if r.status_code == 200 else None)(c.get(B + st["preview_url"])), 25)
check("Private preview playlist works (signed link)", pl is not None and "#EXTM3U" in pl.text)
check("Test session isn't public", c.get(B + f"/media/hls/{ing['ingest_id']}/index.m3u8").status_code == 404 and
      c.post(f"{API}/broadcast/sessions/{s['id']}/start", headers=H).status_code == 409)
guide = c.get(f"{API}/live/guide").json()
check("Test session not listed on Live", not any(ch["title"] == "Mic check" for ch in guide["tv"]))
check("Nothing sent to destinations during the test", not standin_ready(9998))
c.post(f"{API}/broadcast/sessions/{s['id']}/stop", headers=H)

# ---------- live broadcast with simulcast + recording ----------
s = c.post(f"{API}/broadcast/sessions", headers={**H, "Idempotency-Key": "abc-1"}, json={
    "title": "Evening Show", "description": "Live from the studio", "category": "Culture",
    "destination_ids": [d["id"] for d in D.values()], "record": True}).json()
s2 = c.post(f"{API}/broadcast/sessions", headers={**H, "Idempotency-Key": "abc-1"}, json={"title": "dup"}).json()
check("Creating a session twice with the same Idempotency-Key returns the same session", s2["id"] == s["id"])
r1 = c.post(f"{API}/broadcast/sessions/{s['id']}/start", headers=H).json()
r2 = c.post(f"{API}/broadcast/sessions/{s['id']}/start", headers=H).json()
check("Go live; starting twice is safe", r1["status"] == "live" and r2["status"] == "live" and r1["content_id"] == r2["content_id"])
guide = c.get(f"{API}/live/guide").json()
check("Broadcast appears in Live TV", any(ch["title"] == "Evening Show" for ch in guide["tv"]))
pub = wait(lambda: (lambda r: r if r.status_code == 200 else None)(c.get(B + f"/media/hls/{ing['ingest_id']}/index.m3u8")), 20)
check("Public LoNo stream (HLS) serves", pub is not None and "#EXTM3U" in pub.text)


def dstate():
    return {d["platform"]: d for d in c.get(f"{API}/broadcast/sessions/{s['id']}", headers=H).json()["destinations"]}


wait(lambda: all(dstate()[p]["state"] == "live" for p in ("youtube", "facebook", "custom")) or None, 25)
ds = dstate()
recv = standin_ready(9998)
check("YouTube stand-in (RTMP) receiving", ds["youtube"]["state"] == "live" and "youtube/yt-SECRET-111" in recv, ds["youtube"]["state"])
check("Facebook stand-in (RTMPS) receiving", ds["facebook"]["state"] == "live" and "facebook/fb-SECRET-222" in recv, ds["facebook"]["state"])
check("Custom SRT stand-in receiving", ds["custom"]["state"] == "live" and "custom-srt" in recv, ds["custom"]["state"])
wait(lambda: dstate()["twitch"]["state"] == "failed" or None, 25)
ds = dstate()
check("Unreachable destination fails with a readable message", ds["twitch"]["state"] == "failed" and "reach" in (ds["twitch"]["error"] or ""), ds["twitch"]["error"])
check("Other destinations keep running", all(ds[p]["state"] == "live" for p in ("youtube", "facebook", "custom")))
check("Error message doesn't contain the stream key", "SECRET" not in json.dumps(ds))

# targeted retry after the platform comes back
HERE = os.path.dirname(os.path.abspath(__file__))
B_mtx = subprocess.Popen([os.environ.get("MEDIAMTX", "mediamtx"), "standin_b.yml"], cwd=HERE,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
time.sleep(2)
yt_before = dstate()["youtube"]
c.post(f"{API}/broadcast/sessions/{s['id']}/destinations/{D['twitch']['id']}/retry", headers=H)
wait(lambda: dstate()["twitch"]["state"] == "live" or None, 20)
ds = dstate()
check("Targeted retry brings the failed destination live", ds["twitch"]["state"] == "live" and "twitch/tw-SECRET-333" in standin_ready(9999), ds["twitch"]["state"])
check("Retry didn't restart the healthy destinations", ds["youtube"]["attempts"] == yt_before["attempts"] == 1)

# viewer activity is independent: a TV viewer reads the stream, switches away, leaves
for _ in range(3):
    c.get(B + f"/media/hls/{ing['ingest_id']}/index.m3u8"); c.get(f"{API}/live/guide")
before = {p: d["sent_seconds"] for p, d in dstate().items()}
time.sleep(4)
after = dstate()
check("Viewer channel switching/leaving doesn't affect delivery", all(after[p]["state"] == "live" and after[p]["sent_seconds"] > before[p] for p in after))

# encoder disconnect and reconnect
os.killpg(enc.pid, signal.SIGTERM)
wait(lambda: not c.get(f"{API}/broadcast/sessions/{s['id']}", headers=H).json()["feed"].get("ready") or None, 15)
time.sleep(3)
ds = dstate()
check("Encoder drop: destinations wait for the feed", all(d["state"] in ("waiting", "stopped", "failed", "retrying") for d in ds.values()), json.dumps({p: d["state"] for p, d in ds.items()}))
enc = encoder(f"{ing['rtmp']['server']}/{ing['rtmp']['stream_key']}")
wait(lambda: all(d["state"] == "live" for d in dstate().values()) or None, 30)
ds = dstate()
check("Encoder reconnect: every destination resumes", all(d["state"] == "live" for d in ds.values()), json.dumps({p: d["state"] for p, d in ds.items()}))
ev = [e["type"] for e in c.get(f"{API}/broadcast/sessions/{s['id']}/events", headers=H).json()]
check("Events recorded: started, disconnected, connected, destination failed/live", {"broadcast.started", "stream.disconnected", "stream.connected", "destination.failed", "destination.live"} <= set(ev), ",".join(sorted(set(ev))))

check("Rotating the key while live is blocked", c.post(f"{API}/broadcast/ingest/rotate", headers=H).status_code == 409)
time.sleep(5)

# ---------- end ----------
c.post(f"{API}/broadcast/sessions/{s['id']}/stop", headers=H)
c.post(f"{API}/broadcast/sessions/{s['id']}/stop", headers=H)
end = c.get(f"{API}/broadcast/sessions/{s['id']}", headers=H).json()
time.sleep(3)
check("End broadcast (twice is safe): LoNo page removed and destinations stopped",
      end["status"] == "ended" and not any(ch["title"] == "Evening Show" for ch in c.get(f"{API}/live/guide").json()["tv"]) and not standin_ready(9998))
os.killpg(enc.pid, signal.SIGTERM)

rec = wait(lambda: (lambda rs: rs[0] if rs and rs[0]["status"] != "processing" else None)(c.get(f"{API}/broadcast/recordings", headers=H).json()), 40)
check("Recording ready after the broadcast, private by default", rec and rec["status"] == "ready" and rec["visibility"] == "private" and rec["duration_sec"] > 10,
      f"{rec and rec.get('status')} {rec and rec.get('duration_sec')}s parts={rec and rec.get('parts')}")
if rec and rec["status"] == "ready":
    r = c.get(B + rec["url"], headers={"Range": "bytes=0-99"})
    check("Recording file downloadable (range request)", r.status_code == 206)
    c.post(f"{API}/broadcast/recordings/{rec['id']}/publish", headers=H, json={"when": "now"})
    rec2 = c.get(f"{API}/broadcast/recordings", headers=H).json()[0]
    check("Publish recording now creates an on-demand title", rec2["visibility"] == "public" and c.get(f"{API}/content/{rec2['content_id']}").status_code == 200)
    c.post(f"{API}/broadcast/recordings/{rec['id']}/publish", headers=H, json={"when": "private"})
    c.post(f"{API}/broadcast/recordings/{rec['id']}/publish", headers=H, json={"when": "schedule", "publish_at": "2030-01-01T09:00:00+00:00"})
    rec3 = c.get(f"{API}/broadcast/recordings", headers=H).json()[0]
    check("Recording can go back to private, or be scheduled", rec3["visibility"] == "scheduled" and rec3["content_id"] is None)

# ---------- key rotation; SRT ingest ----------
new = c.post(f"{API}/broadcast/ingest/rotate", headers=H).json()
old_try = encoder(f"{ing['rtmp']['server']}/{ing['rtmp']['stream_key']}")
time.sleep(4)
check("After rotation the old key is refused", old_try.poll() is not None)
try: os.killpg(old_try.pid, signal.SIGTERM)
except ProcessLookupError: pass
s = c.post(f"{API}/broadcast/sessions", headers=H, json={"title": "SRT test", "test": True}).json()
srt = encoder(new["srt"]["url"], proto="srt")
ok = wait(lambda: c.get(f"{API}/broadcast/sessions/{s['id']}", headers=H).json()["feed"].get("ready") or None, 20)
check("SRT ingest with the new key", ok)
os.killpg(srt.pid, signal.SIGTERM)
c.post(f"{API}/broadcast/sessions/{s['id']}/stop", headers=H)
s = c.post(f"{API}/broadcast/sessions", headers=H, json={"title": "RTMPS test", "test": True}).json()
rtmps = encoder(f"{new['rtmps']['server']}/{new['rtmps']['stream_key']}", proto="rtmps")
ok = wait(lambda: c.get(f"{API}/broadcast/sessions/{s['id']}", headers=H).json()["feed"].get("ready") or None, 20)
check("RTMPS ingest", ok)
os.killpg(rtmps.pid, signal.SIGTERM)
c.post(f"{API}/broadcast/sessions/{s['id']}/stop", headers=H)
B_mtx.terminate()

# ---------- secrets stay out of logs ----------
logs = open(os.environ.get("API_LOG", "/tmp/api.log")).read() + open(os.environ.get("MEDIA_LOG", "/tmp/lono_mtx.log")).read()
leaks = [k for k in ("yt-SECRET-111", "fb-SECRET-222", "tw-SECRET-333", key, new["rtmp"]["stream_key"].split("key=")[1]) if k in logs]
check("No stream keys in API or media server logs", not leaks, ",".join(leaks))

print(f"SUMMARY {sum(r[1] for r in results)}/{len(results)} passed", flush=True)
json.dump(results, open("/tmp/bc_results.json", "w"))
