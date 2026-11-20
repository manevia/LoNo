import { useCallback, useEffect, useState } from "react";
import { Activity, RefreshCw, Radio, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { api, errorText } from "@/lib/api";

const card = "rounded-2xl border border-white/10 bg-[#121212] p-4";
const button = "rounded-full border border-white/20 px-3 py-1.5 text-xs hover:bg-white/10 disabled:opacity-50";
const date = (v) => v ? new Date(v).toLocaleString() : "—";
const count = (v) => v == null ? "—" : v.toLocaleString();

export default function Broadcasts() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [section, setSection] = useState("active");
  const refresh = useCallback(async () => {
    try { const { data } = await api.get("/admin/broadcasts"); setData(data); setError(""); }
    catch (e) { setError(errorText(e)); }
  }, []);
  useEffect(() => {
    let timer; let stopped = false;
    const tick = async () => { if (!document.hidden) await refresh(); if (!stopped) timer = setTimeout(tick, 15000); };
    tick(); return () => { stopped = true; clearTimeout(timer); };
  }, [refresh]);
  const action = async (path, question) => {
    const reason = window.prompt(question)?.trim();
    if (!reason || reason.length < 3) return;
    setBusy(true);
    try { await api.post(path, { reason }); toast.success("Moderation action recorded"); await refresh(); }
    catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
  };
  const resources = data?.resources;
  return <div className="space-y-5">
    <div className="flex flex-wrap justify-between items-center gap-3">
      <div><h2 className="text-2xl font-display flex items-center gap-2"><Radio className="w-6 h-6 text-[#FF3B30]" /> Live Broadcast Management</h2>
        <p className="mt-1 text-sm text-gray-400">Monitor TV, radio and private test sessions. Updates every 15 seconds.</p></div>
      <button className={`${button} flex items-center gap-2`} onClick={refresh}><RefreshCw className="w-3 h-3" /> Refresh</button>
    </div>
    {error && <p role="alert" className="text-red-300 text-sm">Unable to refresh: {error}. Last successful data may be stale.</p>}
    {!data ? <p className="text-gray-400">{error ? "Dashboard unavailable." : "Loading broadcast operations…"}</p> : <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[["Public live sessions", data.live_count], ["Open sessions", data.open_count], ["Adaptive encoders", `${resources.encoders} / ${resources.encoder_limit}`], ["Media disk free", resources.disk_free_gib == null ? "—" : `${resources.disk_free_gib} GiB`]].map(([label, value]) => <div className={card} key={label}><p className="text-xs text-gray-400">{label}</p><p className="text-2xl mt-1 tabular-nums">{value}</p></div>)}
      </div>
      <div className={`${card} flex flex-wrap gap-x-6 gap-y-2 text-sm`}><span className="inline-flex gap-2 items-center"><Activity className="w-4 h-4" /> Media: {resources.media_enabled ? "Enabled" : "Disabled"}</span><span>CPU load (1 min): {count(resources.cpu_load_1m)}</span><span>Admission: {resources.admission_reason || "Capacity available"}</span><span className="text-gray-500">Updated {date(data.as_of)}</span></div>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Broadcast management sections">
        {[["active", "Open broadcasts"], ["history", "History"], ["recordings", "Recordings"]].map(([key, label]) => <button key={key} aria-pressed={section === key} className={`${button} ${section === key ? "bg-white text-black" : ""}`} onClick={() => setSection(key)}>{label}</button>)}
      </div>
      <p className="text-xs text-gray-400">Watch starts count player sessions, not unique or simultaneous viewers. Historical counts are available for broadcasts ended after this update. Showing up to 50 open sessions and 100 recent records per list.</p>
      {section !== "recordings" ? <div className="space-y-3">
        {!data[section].length && <p className="text-gray-400">No {section === "active" ? "open broadcasts" : "broadcast history"}.</p>}
        {data[section].map(s => <article key={s.id} className={card}>
          <div className="flex items-start justify-between gap-3 flex-wrap"><div><h3 className="font-semibold">{s.title}</h3><p className="text-sm text-gray-400">{s.owner_name} · {s.kind === "live_radio" ? "Radio" : "TV"} · {s.visibility === "test" ? "Private test" : "Public"}</p></div><span className={`text-xs rounded-full border px-3 py-1 ${s.status === "live" ? "text-green-400 border-green-500/30" : "text-gray-400 border-white/15"}`}>{s.status}</span></div>
          <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm"><span>Created: {date(s.created_at)}</span><span>Started: {date(s.started_at)}</span>{s.ended_at && <span>Ended: {date(s.ended_at)}</span>}<span>Watch starts: {count(s.watch_starts)}</span>{s.recording_id && <span>Recording available in records</span>}</div>
          {section === "active" && <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-gray-300"><span>Feed: {s.feed ? s.feed.ready ? "Connected" : "Disconnected" : "Unknown / no feed"}</span><span>Bitrate: {count(s.feed?.bitrate_kbps)} kbps</span><span>Tracks: {s.feed?.tracks?.join(", ") || "—"}</span><span>Adaptive: {s.adaptive?.state || "—"}</span><span>Recorder: {s.recorder_state || "Not running"}</span></div>}
          {s.moderation_reason && <p className="mt-2 text-xs text-yellow-300">Moderation: {s.moderation_reason}</p>}
          {section === "active" && <button disabled={busy} className={`${button} mt-4 text-red-300 border-red-500/40 inline-flex items-center gap-2`} onClick={() => action(`/admin/broadcasts/${s.id}/end`, `End “${s.title}” now? This removes public playback. Enter the reason to confirm.`)}><ShieldAlert className="w-4 h-4" /> End broadcast</button>}
        </article>)}
      </div> : <div className="space-y-3">
        {!data.recordings.length && <p className="text-gray-400">No recordings yet.</p>}
        {data.recordings.map(r => <article className={card} key={r.id}><div className="flex flex-wrap justify-between gap-3"><div><h3 className="font-semibold">{r.title}</h3><p className="text-sm text-gray-400">{r.owner_name} · {r.status} · {r.visibility} · {date(r.created_at)}</p></div><button disabled={busy} className={button} onClick={() => action(`/admin/recordings/${r.id}/${r.moderation_hold ? "release" : "hold"}`, r.moderation_hold ? "Release moderation hold? Recording stays private until its creator publishes. Enter reason." : "Hold this recording? It will be unpublished and cannot be republished until released. Enter reason.")}>{r.moderation_hold ? "Release hold" : "Hold recording"}</button></div><p className="mt-2 text-sm">{count(r.duration_sec)} s · {count(Math.round((r.size || 0) / 1048576))} MiB {r.moderation_hold && <span className="text-yellow-300">· Moderation hold</span>}</p></article>)}
      </div>}
    </>}
  </div>;
}
