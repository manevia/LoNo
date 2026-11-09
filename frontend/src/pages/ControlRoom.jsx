import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Clapperboard, Copy, Loader2, MapPin, Mic, MicOff, Plus, Radio, RefreshCw, Square, Trash2, UserPlus, Columns2, Monitor, PauseCircle } from "lucide-react";
import { api, errorText } from "@/lib/api";
import { useConfig } from "@/lib/config";
import { Compositor } from "@/lib/compositor";
import { publishWhip, playWhep } from "@/lib/whip";
import DestinationsPanel from "@/components/studio/DestinationsPanel";

const card = "rounded-2xl bg-[#121212] border border-white/10";
const chip = "inline-flex items-center gap-1.5 text-xs rounded-full px-2.5 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 disabled:opacity-40";
const field = "w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm";
const STATE = { invited: "Invited", waiting: "Waiting", cued: "Cued", on_air: "On air", left: "Left" };
const STATE_CLS = { on_air: "bg-[#FF3B30] text-white", cued: "bg-[#FFB000] text-black", waiting: "bg-white/10 text-gray-200", invited: "bg-white/5 text-gray-400", left: "bg-white/5 text-gray-500" };
const DSTATE = { live: "text-[#34C759]", failed: "text-[#FF8A82]", connecting: "text-[#FFB000]", retrying: "text-[#FFB000]", waiting: "text-gray-400" };

function RoomList() {
  const nav = useNavigate();
  const [rooms, setRooms] = useState(null);
  const [form, setForm] = useState({ title: "", kind: "news" });
  useEffect(() => { api.get("/rooms").then(({ data }) => setRooms(data)).catch(() => setRooms([])); }, []);
  const create = async (e) => {
    e.preventDefault();
    try { const { data } = await api.post("/rooms", form); nav(`/studio/control/${data.id}`); } catch (err) { toast.error(errorText(err)); }
  };
  return (
    <div className="max-w-3xl mx-auto px-4 md:px-8 pt-8 pb-32" data-testid="control-rooms">
      <Link to="/studio" className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white"><ArrowLeft className="w-4 h-4" /> Studio</Link>
      <h1 className="mt-2 font-display text-3xl md:text-4xl font-semibold tracking-tight">Live Control Room</h1>
      <p className="mt-2 text-gray-400">Run a newscast, match, crusade or community event: bring in reporters and venue feeds, switch between them, and send one continuous program to LoNo and your destinations.</p>
      <form onSubmit={create} className={`${card} p-5 mt-6 flex flex-wrap gap-3 items-end`}>
        <label className="flex-1 min-w-[14rem]"><span className="text-xs text-gray-400">Production name</span>
          <input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className={`${field} mt-1`} data-testid="room-title" placeholder="Evening News" /></label>
        <label><span className="text-xs text-gray-400">Type</span>
          <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} className={`${field} mt-1`}>
            {[["news", "News"], ["sports", "Sports"], ["protest", "Protest / conflict"], ["worship", "Crusade / worship"], ["community", "Community event"], ["other", "Other"]].map(([v, l]) => <option key={v} value={v} className="bg-[#121212]">{l}</option>)}
          </select></label>
        <button className="bg-[#FF3B30] rounded-full px-5 py-2.5 text-sm font-medium" data-testid="room-create"><Plus className="w-4 h-4 inline -mt-0.5" /> Create</button>
      </form>
      <ul className="mt-6 divide-y divide-white/10 border-y border-white/10">
        {(rooms || []).map((r) => <li key={r.id}><Link to={`/studio/control/${r.id}`} className="flex py-3 hover:text-[#FFB000]">{r.title}<span className="ml-auto text-xs text-gray-500 capitalize">{r.kind}</span></Link></li>)}
      </ul>
    </div>
  );
}

function Meter({ comp, id }) {
  const [db, setDb] = useState(-100);
  useEffect(() => { const t = setInterval(() => setDb(comp.current ? comp.current.level(id) : -100), 120); return () => clearInterval(t); }, [comp, id]);
  return <div className="h-1.5 rounded-full bg-white/10 overflow-hidden" data-testid={`meter-${id}`} data-db={Math.round(db)}><div className="h-full bg-[#34C759]" style={{ width: `${Math.max(0, Math.min(100, ((db + 60) / 60) * 100))}%` }} /></div>;
}

function Tile({ c, comp, room, onPreview, onAction, onTalk, talking, splitSel, toggleSplit }) {
  const ref = useRef(null);
  useEffect(() => {
    const s = comp.current?.sources.get(c.id);
    if (ref.current && s?.stream && ref.current.srcObject !== s.stream) { ref.current.srcObject = s.stream; ref.current.play().catch(() => {}); }
  });
  const onAir = room.program.sources.includes(c.id), inPreview = room.preview.sources.includes(c.id);
  return (
    <div className={`${card} overflow-hidden ${onAir ? "ring-2 ring-[#FF3B30]" : inPreview ? "ring-2 ring-[#34C759]" : ""}`} data-testid={`tile-${c.id}`} data-state={c.state} data-connected={c.connected ? "1" : "0"}>
      <div className="relative aspect-video bg-black">
        {c.connected && !c.audio_only ? <video ref={ref} muted playsInline autoPlay className="w-full h-full object-cover" />
          : <div className="absolute inset-0 grid place-items-center text-xs text-gray-500 text-center px-2">{c.connected ? "Audio only" : c.type === "encoder" ? "Waiting for encoder" : c.state === "invited" ? "Not joined yet" : "Disconnected"}</div>}
        <span className={`absolute top-2 left-2 text-[11px] font-semibold px-2 py-0.5 rounded ${STATE_CLS[c.state] || ""}`}>{STATE[c.state] || c.state}</span>
        {c.muted && <span className="absolute top-2 right-2 text-[11px] bg-black/70 px-2 py-0.5 rounded">Muted</span>}
      </div>
      <div className="p-3 space-y-2">
        <div className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={splitSel.includes(c.id)} onChange={() => toggleSplit(c.id)} aria-label={`Select ${c.name} for split screen`} className="accent-[#FFB000]" data-testid={`split-${c.id}`} />
          <span className="font-medium truncate">{c.name}</span><span className="text-xs text-gray-500 capitalize">{c.role}</span>
        </div>
        {c.location && <div className="text-xs text-gray-400 flex items-center gap-1"><MapPin className="w-3 h-3" /> {c.location} {c.show_location ? "(shown on air)" : "(private)"}</div>}
        <Meter comp={comp} id={c.id} />
        <div className="flex flex-wrap gap-1.5">
          <button className={chip} onClick={() => onPreview(c.id)} disabled={!c.connected} data-testid={`preview-${c.id}`}><Monitor className="w-3.5 h-3.5" /> Preview</button>
          {c.state === "cued" ? <button className={chip} onClick={() => onAction(c.id, "uncue")}>Uncue</button>
            : <button className={chip} onClick={() => onAction(c.id, "cue", window.prompt("Cue message", "Stand by: you're next") || "Stand by")} disabled={c.state === "on_air" || !c.connected} data-testid={`cue-${c.id}`}>Cue</button>}
          <button className={`${chip} ${talking ? "!bg-[#FFB000] !text-black" : ""}`} onClick={() => onTalk(c.id)} disabled={!c.connected} data-testid={`talk-${c.id}`}><Mic className="w-3.5 h-3.5" /> {talking ? "Talking" : "Talk"}</button>
          <button className={chip} onClick={() => onAction(c.id, c.muted ? "unmute" : "mute")} data-testid={`mute-${c.id}`}>{c.muted ? <Mic className="w-3.5 h-3.5" /> : <MicOff className="w-3.5 h-3.5" />} {c.muted ? "Unmute" : "Mute"}</button>
          {c.location && <button className={chip} onClick={() => onAction(c.id, c.show_location ? "hide_location" : "show_location")}><MapPin className="w-3.5 h-3.5" /> {c.show_location ? "Hide" : "Show"}</button>}
          <button className={chip} onClick={() => window.confirm(`Remove ${c.name}? Their link stops working.`) && onAction(c.id, "remove")} aria-label={`Remove ${c.name}`}><Trash2 className="w-3.5 h-3.5" /></button>
        </div>
      </div>
    </div>
  );
}

export default function ControlRoom() {
  const { roomId } = useParams();
  const cfg = useConfig();
  if (cfg.broadcasting === false) return <div className="max-w-2xl mx-auto px-4 pt-16 text-center text-gray-400">Live broadcasting is off on this server.</div>;
  return roomId ? <Room roomId={roomId} /> : <RoomList />;
}

function Room({ roomId }) {
  const [room, setRoom] = useState(null);
  const [events, setEvents] = useState([]);
  const [splitSel, setSplitSel] = useState([]);
  const [clips, setClips] = useState([]);
  const [invite, setInvite] = useState({ name: "", role: "reporter", type: "browser", location: "", show_location: false, expires_in_minutes: 240 });
  const [lastInvite, setLastInvite] = useState(null);
  const [selected, setSelected] = useState(() => { try { return JSON.parse(localStorage.getItem("lono_studio_dests") || "[]"); } catch { return []; } });
  const [session, setSession] = useState(null);
  const [busy, setBusy] = useState("");
  const [autoFallback, setAutoFallback] = useState(true);
  const [talkTo, setTalkTo] = useState(null);
  const [title, setTitle] = useState("");
  const programRef = useRef(null), previewRef = useRef(null), comp = useRef(null);
  const feeds = useRef(new Map());     // cid -> {conn}
  const returns = useRef(new Map());   // cid -> publisher
  const programPub = useRef(null);
  const talkStream = useRef(null);
  const roomRef = useRef(null); roomRef.current = room;
  const autoRef = useRef(autoFallback); autoRef.current = autoFallback;

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/rooms/${roomId}`);
      setRoom(data); if (!title) setTitle(data.title);
      setEvents((await api.get(`/rooms/${roomId}/events`)).data.slice(0, 30));
      if (data.session?.id) setSession((await api.get(`/broadcast/sessions/${data.session.id}`)).data); else setSession(null);
    } catch { /* keep last state */ }
  }, [roomId, title]);

  const ready = !!room;
  useEffect(() => {
    if (!ready || comp.current) return undefined;          // canvases exist once the room has loaded
    comp.current = new Compositor({
      programCanvas: programRef.current, previewCanvas: previewRef.current,
      onFeedLost: async (cid) => {
        const name = roomRef.current?.contributors.find((c) => c.id === cid)?.name || "A source";
        if (!autoRef.current) { toast.warning(`${name}'s feed dropped`); return; }
        try { await api.post(`/rooms/${roomId}/fallback`, { contributor_id: cid, reason: "feed_lost" }); toast.warning(`${name}'s feed dropped: back to the anchor`); }
        catch { /* next poll */ }
      },
    });
    api.get("/creator/dashboard").then(({ data }) => setClips(data.videos.filter((v) => v.stream_url?.startsWith("/api/files/")))).catch(() => {});
    const feedMap = feeds.current, returnMap = returns.current;
    return () => {
      for (const f of feedMap.values()) f.conn?.stop();
      for (const p of returnMap.values()) p?.stop?.();
      programPub.current?.stop(); comp.current?.destroy(); comp.current = null;
    };
  }, [roomId, ready]);
  useEffect(() => { load(); const t = setInterval(load, 1000); return () => clearInterval(t); }, [load]);

  // Liveness from the network: a feed is alive while its WebRTC connection receives data.
  useEffect(() => {
    const t = setInterval(async () => {
      for (const [id, f] of feeds.current) {
        if (!f.conn) continue;
        try {
          let bytes = 0;
          (await f.conn.pc.getStats()).forEach((r) => { if (r.type === "inbound-rtp") bytes += r.bytesReceived || 0; });
          if (bytes > (f.lastBytes || 0)) comp.current?.alive(id);
          f.lastBytes = bytes;
        } catch { /* connection closing */ }
      }
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // Keep feeds, returns and scenes in step with the room state.
  useEffect(() => {
    const c = comp.current;
    if (!room || !c) return;
    c.standbyText = room.standby_text;
    c.setScenes(room.program, room.preview);
    for (const ct of room.contributors) {
      c.setSource(ct.id, { name: ct.name, location: ct.location, showLocation: ct.show_location, muted: ct.muted, audioOnly: ct.audio_only });
      let f = feeds.current.get(ct.id);
      // A feed whose own WebRTC connection died is replaced when the source is available again.
      if (f?.conn && ["failed", "closed"].includes(f.conn.pc.connectionState)) { f.conn.stop(); feeds.current.delete(ct.id); c.dropFeed(ct.id); f = null; }
      if (ct.connected && !f) {
        feeds.current.set(ct.id, { connecting: true });
        playWhep({ endpoint: `/rooms/${roomId}/sources/${ct.id}/whep`,
          onState: (s) => { if (s === "failed" || s === "closed") { feeds.current.delete(ct.id); c.dropFeed(ct.id); } } })
          .then((conn) => { feeds.current.set(ct.id, { conn }); const done = () => c.setSource(ct.id, { stream: conn.stream, name: ct.name, location: ct.location, showLocation: ct.show_location, muted: ct.muted, audioOnly: ct.audio_only }); setTimeout(done, 300); })
          .catch(() => feeds.current.delete(ct.id));
      }
      // Note: ct.connected === false alone doesn't drop a working feed (the API's view can lag
      // or time out under load); the compositor's freeze detection and the WebRTC state decide.
      if (["waiting", "cued", "on_air"].includes(ct.state) && !returns.current.has(ct.id) && ct.type === "browser") {
        returns.current.set(ct.id, null);
        publishWhip({ endpoint: `/rooms/${roomId}/returns/${ct.id}/whip`, video: null, audio: c.returnStream(ct.id).getAudioTracks()[0],
          onState: (s) => { if (s === "failed") returns.current.delete(ct.id); } })
          .then((p) => returns.current.set(ct.id, p)).catch(() => returns.current.delete(ct.id));
      }
    }
    for (const id of [...c.sources.keys()]) if (!room.contributors.some((x) => x.id === id)) { feeds.current.get(id)?.conn?.stop(); feeds.current.delete(id); c.removeSource(id); }
  }, [room, roomId]);

  const run = async (k, fn) => { setBusy(k); try { await fn(); } catch (e) { toast.error(e?.response ? errorText(e) : e.message); } finally { setBusy(""); load(); } };
  const setPreview = (body) => run("pv", () => api.put(`/rooms/${roomId}/preview`, body));
  const take = () => run("take", () => api.post(`/rooms/${roomId}/take`));
  const action = (cid, act, message = "") => run("act", () => api.post(`/rooms/${roomId}/contributors/${cid}`, { action: act, message }));
  const anchor = room?.contributors.find((c) => c.role === "anchor" && c.connected);
  const cutToAnchor = () => anchor && run("cut", () => api.put(`/rooms/${roomId}/program`, { scene: "single", sources: [anchor.id] }));
  const toggleSplit = (id) => setSplitSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id].slice(-2)));

  const talk = async (cid) => {
    await comp.current.resume();
    if (talkTo === cid) { comp.current.setTalkback(null); talkStream.current?.getTracks().forEach((t) => t.stop()); talkStream.current = null; setTalkTo(null); return; }
    if (!talkStream.current) talkStream.current = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true } }).catch(() => null);
    if (!talkStream.current) { toast.error("Allow your microphone to talk to contributors"); return; }
    comp.current.setTalkback(talkStream.current, cid); setTalkTo(cid);
  };

  const sendInvite = (e) => { e.preventDefault(); run("inv", async () => {
    const { data } = await api.post(`/rooms/${roomId}/invites`, invite);
    setLastInvite({ ...data, url: window.location.origin + data.join_path });
    setInvite({ ...invite, name: "", location: "" });
  }); };

  // Program output: the composited program feeds a broadcast session (test or live).
  const startProgram = async (test) => {
    await comp.current.resume();
    if (session && session.status !== "ended") { await programPub.current?.stop(); programPub.current = null; await api.post(`/broadcast/sessions/${session.id}/stop`); }
    const { data: s } = await api.post("/broadcast/sessions", test ? { title: `${title} (test)`, test: true } :
      { title, description: `Live from the LoNo Control Room`, category: room.kind === "sports" ? "Sports" : room.kind === "news" ? "News" : "Live", test: false, destination_ids: selected, record: true },
      { headers: { "Idempotency-Key": `cr-${roomId}-${Date.now()}` } });
    await api.put(`/rooms/${roomId}/session`, { session_id: s.id });
    const ps = comp.current.programStream;
    programPub.current = await publishWhip({ video: ps.getVideoTracks()[0], audio: ps.getAudioTracks()[0] });
    if (!test) {
      for (let i = 0; i < 25; i++) { const { data } = await api.get(`/broadcast/sessions/${s.id}`); if (data.feed?.ready) break; await new Promise((r) => setTimeout(r, 1000)); }
      await api.post(`/broadcast/sessions/${s.id}/start`);
      toast.success("Program is live");
    }
  };
  const endProgram = () => run("end", async () => {
    if (!window.confirm("End the broadcast on LoNo and all destinations?")) return;
    await api.post(`/broadcast/sessions/${session.id}/stop`); await programPub.current?.stop(); programPub.current = null;
    await api.put(`/rooms/${roomId}/session`, { session_id: null });
  });

  if (!room) return <div className="min-h-[60vh] grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>;
  const live = session?.status === "live";

  return (
    <div className="max-w-[1700px] mx-auto px-4 md:px-6 pt-6 pb-32" data-testid="control-room">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/studio/control" className="text-sm text-gray-400 hover:text-white"><ArrowLeft className="w-4 h-4 inline" /> Rooms</Link>
        <h1 className="font-display text-2xl md:text-3xl font-semibold mr-auto">{room.title}</h1>
        <span data-testid="program-status" className={`text-sm px-3 py-1 rounded-full border ${live ? "bg-[#FF3B30] border-[#FF3B30]" : session ? "text-[#FFB000] border-[#FFB000]/40" : "text-gray-400 border-white/15"}`}>{live ? "● LIVE" : session ? "Private test" : "Off air"}</span>
      </div>

      {/* Preview / Program */}
      <div className="mt-5 grid lg:grid-cols-2 gap-4">
        <div className={`${card} p-3`}>
          <div className="flex items-center justify-between mb-2"><span className="text-sm font-medium text-[#34C759]">Preview</span><span className="text-xs text-gray-500 capitalize">{room.preview.scene}</span></div>
          <canvas ref={previewRef} className="w-full aspect-video rounded-lg bg-black" data-testid="preview-canvas" />
        </div>
        <div className={`${card} p-3 ${live ? "ring-2 ring-[#FF3B30]" : ""}`}>
          <div className="flex items-center justify-between mb-2"><span className="text-sm font-medium text-[#FF3B30]">On air (program)</span><span className="text-xs text-gray-500 capitalize">{room.program.scene}</span></div>
          <canvas ref={programRef} className="w-full aspect-video rounded-lg bg-black" data-testid="program-canvas" />
          <div className="mt-2"><Meter comp={comp} id="program" /></div>
        </div>
      </div>

      {/* Switcher */}
      <div className={`${card} p-3 mt-4 flex flex-wrap items-center gap-2`} data-testid="switcher">
        <button onClick={take} disabled={!!busy} data-testid="take" className="rounded-full px-6 py-2.5 font-display font-semibold bg-[#FF3B30] hover:bg-[#FF5C53]">TAKE</button>
        <button onClick={cutToAnchor} disabled={!anchor || !!busy} data-testid="cut-anchor" className={chip}>Cut to anchor</button>
        <span className="w-px h-6 bg-white/10 mx-1" />
        <button onClick={() => setPreview({ scene: "split", sources: splitSel })} disabled={splitSel.length !== 2} data-testid="preview-split" className={chip}><Columns2 className="w-3.5 h-3.5" /> Preview split ({splitSel.length}/2)</button>
        <select aria-label="Clip" onChange={(e) => e.target.value && setPreview({ scene: "clip", sources: [], clip_url: e.target.value })} className="text-xs bg-white/5 border border-white/10 rounded-full px-3 py-1.5" defaultValue="">
          <option value="" className="bg-[#121212]">Preview a clip…</option>
          {clips.map((v) => <option key={v.id} value={v.stream_url} className="bg-[#121212]">{v.title}</option>)}
        </select>
        <button onClick={() => setPreview({ scene: "standby", sources: [] })} className={chip} data-testid="preview-standby"><PauseCircle className="w-3.5 h-3.5" /> Preview standby</button>
        <label className="ml-auto flex items-center gap-2 text-xs text-gray-300"><input type="checkbox" checked={autoFallback} onChange={(e) => setAutoFallback(e.target.checked)} className="accent-[#FF3B30]" /> If an on-air feed drops, go to the anchor (or standby)</label>
      </div>

      <div className="mt-4 grid xl:grid-cols-[1fr_380px] gap-4">
        {/* Sources */}
        <div>
          <h2 className="font-display text-lg mb-2">Sources</h2>
          {room.contributors.length === 0 && <p className="text-sm text-gray-400">Invite an anchor and reporters, or add a venue encoder.</p>}
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {room.contributors.map((c) => <Tile key={c.id} c={c} comp={comp} room={room} splitSel={splitSel} toggleSplit={toggleSplit}
              onPreview={(id) => setPreview({ scene: "single", sources: [id] })} onAction={action} onTalk={talk} talking={talkTo === c.id} />)}
          </div>
        </div>

        <div className="space-y-4">
          {/* Invite */}
          <form onSubmit={sendInvite} className={`${card} p-4 space-y-2`} data-testid="invite-form">
            <h2 className="font-display text-lg flex items-center gap-2"><UserPlus className="w-4 h-4" /> Invite</h2>
            <input required value={invite.name} onChange={(e) => setInvite({ ...invite, name: e.target.value })} placeholder="Name" className={field} data-testid="invite-name" />
            <div className="grid grid-cols-2 gap-2">
              <select value={invite.role} onChange={(e) => setInvite({ ...invite, role: e.target.value })} className={field} data-testid="invite-role">{["anchor", "reporter", "guest", "crew"].map((r) => <option key={r} className="bg-[#121212]">{r}</option>)}</select>
              <select value={invite.type} onChange={(e) => setInvite({ ...invite, type: e.target.value })} className={field}><option value="browser" className="bg-[#121212]">Phone / laptop</option><option value="encoder" className="bg-[#121212]">Encoder (field crew, venue)</option></select>
            </div>
            <input value={invite.location} onChange={(e) => setInvite({ ...invite, location: e.target.value })} placeholder="Location (e.g. Gbarnga, Bong County)" className={field} data-testid="invite-location" />
            <label className="flex items-center gap-2 text-xs text-gray-300"><input type="checkbox" checked={invite.show_location} onChange={(e) => setInvite({ ...invite, show_location: e.target.checked })} className="accent-[#FFB000]" /> Show location on air (leave off where it could put someone at risk)</label>
            <label className="text-xs text-gray-400 flex items-center gap-2">Link expires after
              <select value={invite.expires_in_minutes} onChange={(e) => setInvite({ ...invite, expires_in_minutes: Number(e.target.value) })} className="bg-white/5 border border-white/10 rounded px-2 py-1">
                {[[60, "1 hour"], [240, "4 hours"], [720, "12 hours"], [1440, "1 day"], [10080, "7 days"]].map(([v, l]) => <option key={v} value={v} className="bg-[#121212]">{l}</option>)}
              </select></label>
            <button disabled={busy === "inv"} className="w-full bg-white text-black rounded-full py-2 text-sm font-medium" data-testid="invite-send">Create invitation</button>
            {lastInvite && (
              <div className="mt-2 p-3 rounded-lg bg-black/40 border border-white/10 text-xs space-y-2" data-testid="invite-result">
                <div>Send this to {lastInvite.contributor.name} privately (expires {new Date(lastInvite.expires_at).toLocaleString()}):</div>
                {lastInvite.encoder ? (
                  <>
                    <div><b>RTMP server:</b> <code className="break-all">{lastInvite.encoder.rtmp.server}</code></div>
                    <div><b>Stream key:</b> <code className="break-all">{lastInvite.encoder.rtmp.stream_key}</code></div>
                    <div><b>SRT:</b> <code className="break-all">{lastInvite.encoder.srt.url}</code></div>
                  </>
                ) : (
                  <div className="flex gap-2 items-center"><code className="flex-1 break-all" data-testid="invite-url">{lastInvite.url}</code>
                    <button type="button" className={chip} onClick={() => navigator.clipboard.writeText(lastInvite.url).then(() => toast.success("Link copied"))}><Copy className="w-3.5 h-3.5" /></button></div>
                )}
              </div>
            )}
          </form>

          {/* Program output */}
          <div className={`${card} p-4 space-y-3`} data-testid="program-output">
            <h2 className="font-display text-lg flex items-center gap-2"><Clapperboard className="w-4 h-4" /> Program output</h2>
            <input value={title} onChange={(e) => setTitle(e.target.value)} disabled={live} className={field} aria-label="Broadcast title" />
            <div className="text-xs text-gray-400">LoNo Live TV, plus:</div>
            <DestinationsPanel selected={selected} onSelect={setSelected} locked={live} />
            <div className="flex flex-wrap gap-2 pt-1">
              {!live && <button onClick={() => run("test", () => startProgram(true))} disabled={!!busy} className={`${chip} !text-sm !px-4 !py-2`} data-testid="program-test">Private test</button>}
              {!live && <button onClick={() => run("live", () => startProgram(false))} disabled={!!busy} className="inline-flex items-center gap-2 rounded-full px-5 py-2 text-sm font-medium bg-[#FF3B30]" data-testid="program-live">{busy === "live" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Radio className="w-4 h-4" />} Go live</button>}
              {live && <button onClick={endProgram} disabled={!!busy} className="inline-flex items-center gap-2 rounded-full px-5 py-2 text-sm font-medium bg-white text-black" data-testid="program-end"><Square className="w-4 h-4" /> End broadcast</button>}
            </div>
            {session && (
              <ul className="text-sm space-y-1" data-testid="program-destinations">
                <li className="flex gap-2"><span className={session.feed?.ready ? "text-[#34C759]" : "text-[#FFB000]"}>{session.feed?.ready ? "●" : "○"}</span> LoNo {session.feed?.ready ? `(${session.feed.bitrate_kbps ?? "…"} kbps)` : "(waiting for program)"}</li>
                {session.destinations?.map((d) => (
                  <li key={d.id} className="flex flex-wrap items-center gap-2" data-testid={`pd-${d.platform}`} data-state={d.state}>
                    <span className={DSTATE[d.state] || "text-gray-400"}>●</span>{d.name}<span className="text-xs text-gray-500">{d.state === "retrying" ? "reconnecting…" : d.state}</span>
                    {d.error && <span className="w-full text-xs text-[#FF8A82]">{d.error}</span>}
                    {d.state === "failed" && <button className={chip} onClick={() => run("retry", () => api.post(`/broadcast/sessions/${session.id}/destinations/${d.id}/retry`))}><RefreshCw className="w-3 h-3" /> Retry</button>}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className={`${card} p-4`}>
            <h2 className="font-display text-lg mb-2">Activity</h2>
            <ol className="text-xs text-gray-400 space-y-1 max-h-56 overflow-y-auto" data-testid="room-events">
              {events.map((e) => <li key={e.id}><span className="text-gray-600 tabular-nums">{new Date(e.at).toLocaleTimeString()}</span> {e.type.replace(".", " ")}{e.details?.name ? ` · ${e.details.name}` : ""}{e.details?.reason ? ` · ${e.details.reason}` : ""}</li>)}
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
}
