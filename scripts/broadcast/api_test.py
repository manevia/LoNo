"""Creator API end-to-end test against a real media server.
Needs: LoNo API (MEDIA_ENABLED=true, WEBHOOK_ALLOW_PRIVATE=true for the local
receiver), LoNo's MediaMTX, stand-in A (scripts/broadcast/standin_a.yml), ffmpeg."""
import hashlib, hmac, json, os, signal, subprocess, threading, time, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
import httpx

B = os.environ.get("LONO_URL", "http://127.0.0.1:8001"); API = B + "/api"
results, received = [], []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


class Hook(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        received.append({"headers": dict(self.headers), "body": body})
        self.send_response(200); self.end_headers()

    def log_message(self, *a):
        pass


srv = HTTPServer(("127.0.0.1", 9100), Hook)
threading.Thread(target=srv.serve_forever, daemon=True).start()

c = httpx.Client(timeout=20)
tok = c.post(f"{API}/auth/register", json={"email": f"api{uuid.uuid4().hex[:6]}@example.com", "password": "Passw0rd!", "name": "API Creator", "accept_terms": True}).json()["token"]
U = {"Authorization": f"Bearer {tok}"}
yt = c.post(f"{API}/broadcast/destinations", headers=U, json={"platform": "youtube", "server_url": "rtmp://127.0.0.1:2935/youtube", "stream_key": "yt-API-7777"}).json()
scopes = ["sessions:read", "sessions:write", "broadcast:control", "ingest:read", "destinations:read", "recordings:read"]
integ = c.post(f"{API}/integrations", headers=U, json={"name": "Newsroom scheduler", "scopes": scopes, "environment": "live",
                                                     "webhook_url": "http://127.0.0.1:9100/lono"}).json()
H = {"Authorization": f"Bearer {integ['token']}"}
whsec = integ["webhook_secret"]
check("Integration registered; token shown once", integ["token"].startswith("lk_live_") and "token" not in c.get(f"{API}/integrations", headers=U).text)

ping = c.post(f"{API}/v1/webhooks/test", headers=H).json()
check("Webhook test ping delivered", ping["delivered"])

# test environment can't go public
tint = c.post(f"{API}/integrations", headers=U, json={"name": "Sandbox", "scopes": scopes, "environment": "test"}).json()
TH = {"Authorization": f"Bearer {tint['token']}"}
ts = c.post(f"{API}/v1/sessions", headers=TH, json={"title": "Sandbox run", "destination_ids": [yt["id"]], "record": True}).json()
check("Test credentials: private session, no simulcast or recording", ts["visibility"] == "test" and ts["destinations"] == [] and ts["record"] is False)
check("Test credentials can't start a public broadcast", c.post(f"{API}/v1/sessions/{ts['id']}/start", headers=TH).status_code == 409)
c.post(f"{API}/v1/sessions/{ts['id']}/stop", headers=TH)

# connect an encoder using the ingest details from the API
ing = c.get(f"{API}/v1/ingest", headers=H).json()
enc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-re", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
                        "-c:v", "libx264", "-preset", "veryfast", "-g", "60", "-b:v", "2500k", "-c:a", "aac", "-f", "flv",
                        f"{ing['rtmp']['server']}/{ing['rtmp']['stream_key']}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

# schedule (create) with a retry after a simulated timeout: same Idempotency-Key → same session
body = {"title": "API Evening News", "category": "News", "destination_ids": [yt["id"]], "record": True, "scheduled_for": "2026-11-09T20:00:00+00:00"}
s1 = c.post(f"{API}/v1/sessions", headers={**H, "Idempotency-Key": "news-1109"}, json=body).json()
s2 = c.post(f"{API}/v1/sessions", headers={**H, "Idempotency-Key": "news-1109"}, json=body).json()
sid = s1["id"]
check("Create session; retried create returns the same session", s1["id"] == s2["id"] and len([x for x in c.get(f"{API}/v1/sessions", headers=H).json() if x["title"] == "API Evening News"]) == 1)
c.patch(f"{API}/v1/sessions/{sid}", headers=H, json={"description": "Tonight's headlines"})

for _ in range(30):
    h = c.get(f"{API}/v1/sessions/{sid}/health", headers=H).json()
    if h["feed"].get("ready"):
        break
    time.sleep(1)
check("Health shows the encoder feed", h["feed"]["ready"] and h["feed"]["has_video"], f"tracks={h['feed'].get('tracks')}")

a = c.post(f"{API}/v1/sessions/{sid}/start", headers=H).json()
b = c.post(f"{API}/v1/sessions/{sid}/start", headers=H).json()             # retried start (e.g. after a timeout)
for _ in range(25):
    h = c.get(f"{API}/v1/sessions/{sid}/health", headers=H).json()
    if h["destinations"] and h["destinations"][0]["state"] == "live":
        break
    time.sleep(1)
relays = [l for l in subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout.splitlines() if "yt-API-7777" in l and "ffmpeg" in l]
check("Start (and a retried start) → one broadcast, one relay per destination", a["status"] == b["status"] == "live" and a["content_id"] == b["content_id"] and len(relays) == 1, f"relays={len(relays)}")
check("Destination health: YouTube stand-in live", h["destinations"][0]["state"] == "live", json.dumps(h["destinations"][0]))
time.sleep(8)

x = c.post(f"{API}/v1/sessions/{sid}/stop", headers=H).json()
y = c.post(f"{API}/v1/sessions/{sid}/stop", headers=H).json()
check("Stop (and a retried stop) → ended once", x["status"] == y["status"] == "ended" and
      [e["type"] for e in c.get(f"{API}/v1/sessions/{sid}/events", headers=H).json()].count("broadcast.ended") == 1)
os.killpg(enc.pid, signal.SIGTERM)

rec = None
for _ in range(40):
    recs = c.get(f"{API}/v1/recordings", headers=H).json()
    rec = next((r for r in recs if r["session_id"] == sid and r["status"] != "processing"), None)
    if rec:
        break
    time.sleep(1)
full = c.get(f"{API}/v1/recordings/{rec['id']}", headers=H).json() if rec else {}
dl = c.get(B + full.get("download_url", "/x"), headers={"Range": "bytes=0-99"}) if rec else None
check("Recording retrieved through the API (signed link; private by default)", rec and rec["status"] == "ready" and dl.status_code == 206 and
      c.get(B + rec["url"]).status_code == 403, f"{rec and rec['status']} {rec and rec.get('duration_sec')}s")

time.sleep(3)
types = [json.loads(r["body"])["type"] for r in received]
need = {"ping", "stream.connected", "broadcast.started", "destination.live", "broadcast.ended", "recording.ready"}
check("Webhooks received for connect, start, destination, end, recording", need <= set(types), ",".join(types))


def valid(r):
    parts = dict(p.split("=", 1) for p in r["headers"]["LoNo-Signature"].split(","))
    exp = hmac.new(whsec.encode(), f"{parts['t']}.".encode() + r["body"], hashlib.sha256).hexdigest()
    return hmac.compare_digest(exp, parts["v1"]) and abs(time.time() - int(parts["t"])) < 300


check("Every webhook signature verifies with the webhook secret", received and all(valid(r) for r in received), f"{len(received)} deliveries")
blob = b"".join(r["body"] for r in received).decode()
check("No stream keys or tokens in webhook payloads", "yt-API-7777" not in blob and ing["rtmp"]["stream_key"].split("key=")[1] not in blob and integ["token"] not in blob)
logs = open(os.environ.get("API_LOG", "/tmp/api.log")).read()
check("No API token or stream keys in the server log", integ["token"].split(".")[1] not in logs and "yt-API-7777" not in logs)
print(f"SUMMARY {sum(r[1] for r in results)}/{len(results)} passed", flush=True)
srv.shutdown()
