# Publish a browser-like feed (VP8 + Opus) over internal RTSP with the creator's key,
# then confirm the private preview serves the converted H.264/AAC stream.
import subprocess, time, uuid, json, os, signal, httpx
API="http://127.0.0.1:8001/api"; B="http://127.0.0.1:8001"
c=httpx.Client(timeout=20)
tok=c.post(f"{API}/auth/register",json={"email":f"tx{uuid.uuid4().hex[:6]}@example.com","password":"Passw0rd!","name":"TX","accept_terms":True}).json()["token"]
H={"Authorization":f"Bearer {tok}"}
ing=c.get(f"{API}/broadcast/ingest",headers=H).json(); key=ing["rtmp"]["stream_key"].split("key=")[1]; iid=ing["ingest_id"]
s=c.post(f"{API}/broadcast/sessions",headers=H,json={"title":"tx","test":True}).json()
enc=subprocess.Popen(["ffmpeg","-loglevel","error","-re","-f","lavfi","-i","testsrc2=size=640x360:rate=25","-f","lavfi","-i","sine=frequency=500:sample_rate=48000",
  "-c:v","libvpx","-deadline","realtime","-b:v","800k","-c:a","libopus","-f","rtsp","-rtsp_transport","tcp",f"rtsp://{iid}:{key}@127.0.0.1:8554/live/{iid}"],start_new_session=True)
for _ in range(40):
    v=c.get(f"{API}/broadcast/sessions/{s['id']}",headers=H).json()
    if v["feed"].get("converted"): break
    time.sleep(0.5)
print("source tracks:", v["feed"].get("tracks"), "| converted:", v["feed"].get("converted"))
time.sleep(6)
out=subprocess.run(["ffprobe","-v","error","-show_entries","stream=codec_name,width,height","-of","json",B+v["preview_url"]],capture_output=True,text=True,timeout=30).stdout
print("preview stream:", [ (x.get("codec_name"), x.get("width")) for x in json.loads(out or '{"streams":[]}')["streams"]])
os.killpg(enc.pid, signal.SIGTERM); c.post(f"{API}/broadcast/sessions/{s['id']}/stop",headers=H)
