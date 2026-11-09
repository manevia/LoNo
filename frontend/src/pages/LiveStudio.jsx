import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Laptop, Loader2, MonitorUp, Radio, RefreshCw, Square } from "lucide-react";
import { api, errorText } from "@/lib/api";
import { useConfig } from "@/lib/config";
import { publishWhip } from "@/lib/whip";
import MediaPlayer from "@/components/MediaPlayer";
import DevicesPanel from "@/components/studio/DevicesPanel";
import EncoderPanel from "@/components/studio/EncoderPanel";
import DestinationsPanel from "@/components/studio/DestinationsPanel";
import RecordingsPanel from "@/components/studio/RecordingsPanel";
import TestSetup from "@/components/studio/TestSetup";

const card = "rounded-2xl bg-[#121212] border border-white/10 p-5";
const field = "w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm";
const STATE = {
  live: ["Live", "text-[#34C759] border-[#34C759]/40 bg-[#34C759]/10"], connecting: ["Connecting", "text-[#FFB000] border-[#FFB000]/40 bg-[#FFB000]/10"],
  failed: ["Failed", "text-[#FF8A82] border-[#FF3B30]/40 bg-[#FF3B30]/10"], retrying: ["Reconnecting", "text-[#FFB000] border-[#FFB000]/40 bg-[#FFB000]/10"], waiting: ["Waiting for feed", "text-gray-300 border-white/15 bg-white/5"],
  stopped: ["Stopped", "text-gray-400 border-white/15"], idle: ["Not started", "text-gray-400 border-white/15"],
};
const EVENT = { "broadcast.started": "Broadcast started", "broadcast.ended": "Broadcast ended", "stream.connected": "Feed connected",
  "stream.disconnected": "Feed disconnected", "destination.live": "Destination live", "destination.failed": "Destination failed", "destination.reconnecting": "Destination reconnecting", "recording.ready": "Recording ready" };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * Live Studio: broadcast from this device (camera/mic via WebRTC) or an external
 * encoder (RTMP/RTMPS/SRT); private test; go live on LoNo and selected
 * destinations; watch each destination's health; end; manage recordings.
 */
export default function LiveStudio() {
  const cfg = useConfig();
  const [mode, setMode] = useState(() => localStorage.getItem("lono_studio_mode") || "device");
  const [tracks, setTracks] = useState({ video: null, audio: null });
  const [session, setSession] = useState(undefined);
  const [events, setEvents] = useState([]);
  const [selected, setSelected] = useState(() => { try { return JSON.parse(localStorage.getItem("lono_studio_dests") || "[]"); } catch { return []; } });
  const [form, setForm] = useState({ title: "", description: "", kind: "live_tv", record: true });
  const [busy, setBusy] = useState("");
  const [stats, setStats] = useState(null);
  const [recKey, setRecKey] = useState(0);
  const pub = useRef(null);
  const tracksRef = useRef(tracks);
  tracksRef.current = tracks;

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/broadcast/sessions/current");
      setSession(data);
      if (data) setEvents((await api.get(`/broadcast/sessions/${data.id}/events`)).data);
    } catch { setSession(null); }
  }, []);
  useEffect(() => { refresh(); const t = setInterval(refresh, 2000); return () => clearInterval(t); }, [refresh]);
  useEffect(() => { localStorage.setItem("lono_studio_mode", mode); }, [mode]);
  useEffect(() => { localStorage.setItem("lono_studio_dests", JSON.stringify(selected)); }, [selected]);
  useEffect(() => () => { pub.current?.stop(); }, []);
  useEffect(() => {
    if (!pub.current) { setStats(null); return undefined; }
    const t = setInterval(async () => { if (pub.current) setStats(await pub.current.stats()); }, 2000);
    return () => clearInterval(t);
  }, [session?.id]);

  // Switching camera or mic while sending replaces the track without reconnecting.
  const onTracks = useCallback((t) => {
    setTracks(t);
    if (pub.current) { pub.current.replace("video", t.video); pub.current.replace("audio", t.audio); }
  }, []);

  const startPublishing = async () => {
    if (mode !== "device") return;
    const t = tracksRef.current;
    if (!t.audio && !t.video) throw new Error("Allow your camera and microphone first.");
    pub.current = await publishWhip({ video: t.video, audio: t.audio, onState: (s) => { if (s === "failed") toast.error("The camera connection to LoNo dropped. Stop and start the test again."); } });
  };
  const stopPublishing = async () => { const p = pub.current; pub.current = null; await p?.stop(); };

  const run = async (key, fn) => { setBusy(key); try { await fn(); } catch (e) { toast.error(e?.response ? errorText(e) : e.message); } finally { setBusy(""); refresh(); } };

  const startTest = () => run("test", async () => {
    await api.post("/broadcast/sessions", { title: form.title || "Private test", kind: form.kind, test: true });
    await startPublishing();
    toast.success("Private test started. Only you can see the preview.");
  });
  const stopTest = () => run("stoptest", async () => { await stopPublishing(); if (session) await api.post(`/broadcast/sessions/${session.id}/stop`); });

  const goLive = () => run("live", async () => {
    if (!form.title.trim()) throw new Error("Give your broadcast a title.");
    if (session?.visibility === "test") { await stopPublishing(); await api.post(`/broadcast/sessions/${session.id}/stop`); }
    const { data: s } = await api.post("/broadcast/sessions", { ...form, test: false, destination_ids: selected }, { headers: { "Idempotency-Key": `studio-${Date.now()}` } });
    await startPublishing();
    for (let i = 0; i < 20; i++) {                    // wait for the feed to reach LoNo
      const { data } = await api.get(`/broadcast/sessions/${s.id}`);
      if (data.feed?.ready) break;
      await sleep(1000);
    }
    await api.post(`/broadcast/sessions/${s.id}/start`);
    toast.success("You're live");
  });
  const end = () => run("end", async () => {
    if (!window.confirm("End the broadcast on LoNo and every destination?")) return;
    await api.post(`/broadcast/sessions/${session.id}/stop`);
    await stopPublishing();
    setRecKey((n) => n + 1);
    toast("Broadcast ended");
  });
  const retry = (d) => run(`retry-${d.id}`, async () => { await api.post(`/broadcast/sessions/${session.id}/destinations/${d.id}/retry`); });

  if (cfg.broadcasting === false) return (
    <div className="max-w-2xl mx-auto px-4 pt-16 pb-32 text-center">
      <h1 className="font-display text-3xl">Live Studio</h1>
      <p className="mt-3 text-gray-400">Live broadcasting is off on this server. An administrator can turn it on; see docs/BROADCAST.md in the LoNo repository.</p>
    </div>
  );

  const live = session?.status === "live";
  const testing = session?.visibility === "test";
  const feed = session?.feed || {};

  return (
    <div data-testid="live-studio" className="max-w-[1500px] mx-auto px-4 md:px-8 pt-8 pb-32">
      <Link to="/studio" className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white"><ArrowLeft className="w-4 h-4" /> Studio</Link>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tight mr-auto">Live Studio</h1>
        <span data-testid="studio-status" className={`text-sm px-3 py-1 rounded-full border ${live ? "text-white bg-[#FF3B30] border-[#FF3B30]" : testing ? "text-[#FFB000] border-[#FFB000]/40" : "text-gray-400 border-white/15"}`}>
          {live ? "● LIVE" : testing ? "Private test" : "Offline"}
        </span>
      </div>

      <div className="mt-8 grid lg:grid-cols-2 gap-8">
        {/* Source */}
        <section aria-labelledby="src-h" className="space-y-6">
          <div className={card}>
            <h2 id="src-h" className="font-display text-xl mb-4">Devices & Sources</h2>
            <div role="tablist" className="mb-5 grid grid-cols-2 gap-2">
              {[["device", "This device", Laptop, "Camera and microphone in this browser"], ["encoder", "External encoder", MonitorUp, "OBS, vMix, Streamlabs, Wirecast, hardware"]].map(([k, l, I, d]) => (
                <button key={k} role="tab" aria-selected={mode === k} onClick={() => setMode(k)} disabled={!!session} data-testid={`mode-${k}`}
                  className={`text-left rounded-xl p-3 border transition disabled:opacity-60 ${mode === k ? "border-[#FFB000]/60 bg-[#FFB000]/10" : "border-white/10 hover:border-white/25"}`}>
                  <div className="flex items-center gap-2 text-sm font-medium"><I className="w-4 h-4" /> {l}</div>
                  <div className="text-xs text-gray-400 mt-1">{d}</div>
                </button>
              ))}
            </div>
            {mode === "device" ? <DevicesPanel onTracks={onTracks} live={live} /> : <EncoderPanel live={live} />}
          </div>
          <TestSetup mode={mode} videoTrack={tracks.video} audioTrack={tracks.audio} testing={!!session}
            stats={mode === "device" ? stats : feed.ready ? { kbps: feed.bitrate_kbps, lossPct: 0 } : null} />
        </section>

        {/* Broadcast */}
        <section aria-labelledby="bc-h" className="space-y-6">
          <div className={card}>
            <h2 id="bc-h" className="font-display text-xl">What LoNo receives</h2>
            <div className="mt-3 aspect-video rounded-xl overflow-hidden bg-black ring-1 ring-white/10 grid place-items-center" data-testid="feed-preview">
              {session && feed.ready
                ? <MediaPlayer key={`${session.id}-${feed.since}`} src={session.preview_url} live autoPlay nativeControls showOptions={false} testId="studio-preview"
                    audio={form.kind === "live_radio"} className="w-full h-full object-contain" mediaProps={{ muted: true }} />
                : <span className="text-sm text-gray-500 px-6 text-center">{session ? (mode === "encoder" ? "Waiting for your encoder… Start streaming to the server and key on the left." : "Connecting your camera…") : "Start a private test to see what viewers will see."}</span>}
            </div>
            {session && (
              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-gray-400" data-testid="feed-info">
                <span>Feed: <span className={feed.ready ? "text-[#34C759]" : "text-[#FFB000]"}>{feed.ready ? "connected" : "not connected"}</span></span>
                {feed.tracks?.length > 0 && <span>Tracks: {feed.tracks.join(", ")}</span>}
                {feed.bitrate_kbps != null && <span>Bitrate: {feed.bitrate_kbps} kbps</span>}
                {feed.has_audio === false && feed.ready && <span className="text-[#FFB000]">No audio track</span>}
              </div>
            )}
          </div>

          <div className={card}>
            <h2 className="font-display text-xl mb-4">Broadcast</h2>
            <div className="space-y-3">
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Title (required to go live)" disabled={live} className={field} data-testid="bc-title" aria-label="Title" />
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Description" rows={2} disabled={live} className={field} aria-label="Description" />
              <div className="flex flex-wrap gap-4 text-sm">
                <label className="flex items-center gap-2"><input type="radio" name="kind" checked={form.kind === "live_tv"} onChange={() => setForm({ ...form, kind: "live_tv" })} disabled={live} className="accent-[#FF3B30]" /> Live TV</label>
                <label className="flex items-center gap-2"><input type="radio" name="kind" checked={form.kind === "live_radio"} onChange={() => setForm({ ...form, kind: "live_radio" })} disabled={live} className="accent-[#FF3B30]" /> Radio</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.record} onChange={(e) => setForm({ ...form, record: e.target.checked })} disabled={live} className="accent-[#FF3B30]" data-testid="bc-record" /> Record</label>
              </div>
            </div>

            <h3 className="mt-6 mb-2 text-sm font-medium">Send to</h3>
            <div className="mb-2 flex items-center gap-2 text-sm"><input type="checkbox" checked readOnly className="w-4 h-4 accent-[#FF3B30]" /> LoNo Live {form.kind === "live_radio" ? "Radio" : "TV"}</div>
            <DestinationsPanel selected={selected} onSelect={setSelected} locked={live} />

            <div className="mt-6 flex flex-wrap gap-3">
              {!session && <button onClick={startTest} disabled={!!busy} data-testid="start-test" className="rounded-full px-5 py-2.5 text-sm font-medium bg-white/10 border border-white/15 disabled:opacity-50">{busy === "test" ? <Loader2 className="w-4 h-4 animate-spin" /> : "Start private test"}</button>}
              {testing && <button onClick={stopTest} disabled={!!busy} data-testid="stop-test" className="rounded-full px-5 py-2.5 text-sm bg-white/10 border border-white/15">Stop test</button>}
              {!live && <button onClick={goLive} disabled={!!busy} data-testid="go-live" className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium bg-[#FF3B30] hover:bg-[#FF5C53] disabled:opacity-50">{busy === "live" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Radio className="w-4 h-4" />} Go live</button>}
              {live && <button onClick={end} disabled={!!busy} data-testid="end-broadcast" className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium bg-white text-black"><Square className="w-4 h-4" /> End broadcast</button>}
            </div>
            {!session && <p className="mt-3 text-xs text-gray-500">A private test isn't public and isn't sent to destinations.</p>}
          </div>

          {live && (
            <div className={card} data-testid="destination-status">
              <h2 className="font-display text-xl mb-3">Destinations</h2>
              <ul className="space-y-2">
                <li className="flex items-center gap-3 text-sm"><span className={`text-xs px-2.5 py-1 rounded-full border ${STATE.live[1]}`}>Live</span> LoNo {session.public_url && <Link to={`/live/play/${session.content_id}?list=${session.kind === "live_radio" ? "radio" : "tv"}`} className="text-xs text-gray-400 underline">open</Link>}</li>
                {session.destinations.map((d) => {
                  const [label, cls] = STATE[d.state] || STATE.idle;
                  return (
                    <li key={d.id} className="flex flex-wrap items-center gap-3 text-sm" data-testid={`dest-status-${d.platform}`} data-state={d.state}>
                      <span className={`text-xs px-2.5 py-1 rounded-full border ${cls}`}>{label}</span>
                      <span className="flex-1 min-w-0">{d.name}{d.error && <span className="block text-xs text-[#FF8A82]">{d.error}</span>}</span>
                      {d.state === "failed" && <button onClick={() => retry(d)} disabled={!!busy} data-testid={`retry-${d.platform}`} className="inline-flex items-center gap-1.5 text-xs rounded-full px-3 py-1.5 bg-white/10 border border-white/15"><RefreshCw className="w-3.5 h-3.5" /> Retry</button>}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {session && events.length > 0 && (
            <div className={card}>
              <h2 className="font-display text-lg mb-2">Activity</h2>
              <ol className="text-xs text-gray-400 space-y-1 max-h-48 overflow-y-auto" data-testid="bc-events">
                {[...events].reverse().map((e) => <li key={e.id}><span className="tabular-nums text-gray-500">{new Date(e.at).toLocaleTimeString()}</span> {EVENT[e.type] || e.type}{e.details?.platform ? ` · ${e.details.platform}` : ""}{e.details?.error ? ` · ${e.details.error}` : ""}</li>)}
              </ol>
            </div>
          )}
        </section>
      </div>

      <section className={`${card} mt-8`} aria-labelledby="rec-h">
        <h2 id="rec-h" className="font-display text-xl mb-3">Recordings</h2>
        <RecordingsPanel refreshKey={recKey} />
      </section>
    </div>
  );
}
