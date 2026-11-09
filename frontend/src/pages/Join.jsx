import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Headphones, Loader2, LogOut, Mic, Radio, RefreshCw, Video, VideoOff, Wifi, WifiOff } from "lucide-react";
import { api, errorText } from "@/lib/api";
import { publishWhip, playWhep } from "@/lib/whip";
import DevicesPanel from "@/components/studio/DevicesPanel";

const btn = "inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-sm font-medium disabled:opacity-50";

/**
 * Field contributor page (invitation link). Works on phones and laptops:
 * check camera and mic, wait privately, go on air when the producer takes
 * you, hear the program without your own voice, drop to audio-only when the
 * signal is weak, and reconnect.
 */
export default function Join() {
  const { token } = useParams();
  const [info, setInfo] = useState(null);
  const [error, setError] = useState(null);
  const [tracks, setTracks] = useState({ video: null, audio: null });
  const [joined, setJoined] = useState(false);
  const [conn, setConn] = useState("idle");          // idle | connecting | connected | reconnecting | failed
  const [audioOnly, setAudioOnly] = useState(false);
  const [returnOn, setReturnOn] = useState(false);
  const pub = useRef(null);
  const ret = useRef(null);
  const returnEl = useRef(null);
  const tracksRef = useRef(tracks); tracksRef.current = tracks;
  const retryTimer = useRef(null);
  const audioOnlyRef = useRef(false); audioOnlyRef.current = audioOnly;

  const load = useCallback(async () => {
    try { const { data } = await api.get(`/join/${token}`); setInfo(data); setError(null); }
    catch (e) { setError(errorText(e, "This invitation isn't valid.")); }
  }, [token]);
  useEffect(() => { load(); const t = setInterval(load, 1500); return () => clearInterval(t); }, [load]);

  const publish = useCallback(async () => {
    clearTimeout(retryTimer.current);
    setConn((c) => (c === "connected" || c === "reconnecting" ? "reconnecting" : "connecting"));
    try {
      await pub.current?.stop();
      const t = tracksRef.current;
      pub.current = await publishWhip({
        endpoint: `/join/${token}/whip`, video: audioOnlyRef.current ? null : t.video, audio: t.audio,
        onState: (s) => {
          if (s === "connected") setConn("connected");
          if (s === "failed" || s === "disconnected") {   // weak coverage: retry until it's back
            setConn("reconnecting");
            clearTimeout(retryTimer.current);
            retryTimer.current = setTimeout(() => publish(), s === "failed" ? 1000 : 4000);
          }
        },
      });
    } catch {
      setConn("reconnecting");
      retryTimer.current = setTimeout(() => publish(), 3000);
    }
  }, [token]);

  // Private audio return: try until the producer's Control Room provides it.
  const listen = useCallback(async () => {
    try {
      ret.current?.stop();
      ret.current = await playWhep({ endpoint: `/join/${token}/return/whep`, audioOnly: true,
        onState: (s) => { if (s === "failed" || s === "disconnected") { setReturnOn(false); setTimeout(listen, 3000); } } });
      if (returnEl.current) { returnEl.current.srcObject = ret.current.stream; returnEl.current.play().catch(() => {}); }
      setReturnOn(true);
    } catch { setReturnOn(false); setTimeout(listen, 2000); }   // the producer may not be sending it yet
  }, [token]);

  const join = async () => {
    await api.post(`/join/${token}/ready`);
    setJoined(true);
    await publish();
    listen();
  };
  const leave = async () => {
    clearTimeout(retryTimer.current);
    await pub.current?.stop(); ret.current?.stop(); pub.current = null;
    await api.post(`/join/${token}/leave`).catch(() => {});
    setJoined(false); setConn("idle");
  };
  const toggleAudioOnly = async () => {
    const on = !audioOnly; setAudioOnly(on); audioOnlyRef.current = on;
    await api.post(`/join/${token}/audio-only`, { on }).catch(() => {});
    if (pub.current) await pub.current.replace("video", on ? null : tracksRef.current.video);
  };
  useEffect(() => () => { clearTimeout(retryTimer.current); pub.current?.stop(); ret.current?.stop(); }, []);

  const onTracks = useCallback((t) => {
    setTracks(t);
    if (pub.current) { pub.current.replace("audio", t.audio); if (!audioOnlyRef.current) pub.current.replace("video", t.video); }
  }, []);

  if (error) return <div className="min-h-screen bg-[#050505] text-white grid place-items-center p-6 text-center"><div><p className="text-lg">{error}</p></div></div>;
  if (!info) return <div className="min-h-screen bg-[#050505] grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>;
  const c = info.contributor;
  const onAir = info.on_air;

  return (
    <div data-testid="join-page" className={`min-h-screen text-white transition-colors ${onAir ? "bg-[#2a0503]" : "bg-[#050505]"}`}>
      {/* On-air indicator: impossible to miss */}
      <div data-testid="onair-indicator" data-on-air={onAir ? "1" : "0"}
        className={`sticky top-0 z-10 px-4 py-3 text-center font-display text-xl tracking-wide ${onAir ? "bg-[#FF3B30] text-white" : c.state === "cued" ? "bg-[#FFB000] text-black" : "bg-white/5 text-gray-300"}`}
        style={{ paddingTop: "calc(env(safe-area-inset-top) + 0.75rem)" }} role="status" aria-live="assertive">
        {onAir ? "● ON AIR" : c.state === "cued" ? `CUED: ${c.cue || "Stand by"}` : joined ? "Waiting: you're not on air" : "Not connected"}
      </div>

      <div className="max-w-xl mx-auto px-4 pt-6 pb-24">
        <div className="text-sm text-gray-400">{info.room.title}</div>
        <h1 className="font-display text-2xl mt-1">{c.name}</h1>
        <div className="text-sm text-gray-400 capitalize">{c.role}{c.location ? ` · ${c.location}` : ""}{info.live ? " · Broadcast is live" : ""}</div>

        <div className="mt-6 rounded-2xl bg-[#121212] border border-white/10 p-4">
          <DevicesPanel onTracks={onTracks} live={joined} />
        </div>

        {!joined ? (
          <>
            <p className="mt-4 text-sm text-gray-400 flex gap-2"><Headphones className="w-4 h-4 shrink-0 mt-0.5" /> Use headphones. You'll hear the program in them, without your own voice.</p>
            <button onClick={join} disabled={!tracks.audio} data-testid="join-waiting" className={`${btn} mt-4 w-full bg-[#FF3B30]`}>
              <Radio className="w-4 h-4" /> Join waiting area
            </button>
            {!tracks.audio && <p className="mt-2 text-xs text-gray-500 text-center">Allow your microphone first.</p>}
          </>
        ) : (
          <div className="mt-5 space-y-3">
            <div className="flex flex-wrap items-center gap-3 text-sm" data-testid="join-connection" data-state={conn}>
              {conn === "connected" ? <Wifi className="w-4 h-4 text-[#34C759]" /> : <WifiOff className="w-4 h-4 text-[#FFB000]" />}
              <span>{conn === "connected" ? "Connected to the control room" : conn === "reconnecting" ? "Signal lost: reconnecting…" : "Connecting…"}</span>
              <span className="text-gray-500">·</span>
              <span className={returnOn ? "text-[#34C759]" : "text-gray-400"} data-testid="return-status" data-on={returnOn ? "1" : "0"}>{returnOn ? "Program audio in your headphones" : "Waiting for program audio"}</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <button onClick={toggleAudioOnly} data-testid="toggle-audio-only" aria-pressed={audioOnly} className={`${btn} bg-white/10 border border-white/15`}>
                {audioOnly ? <><Video className="w-4 h-4" /> Send video again</> : <><VideoOff className="w-4 h-4" /> Audio only (weak signal)</>}
              </button>
              <button onClick={publish} data-testid="reconnect" className={`${btn} bg-white/10 border border-white/15`}><RefreshCw className="w-4 h-4" /> Reconnect</button>
            </div>
            <button onClick={leave} data-testid="leave" className={`${btn} w-full text-gray-300`}><LogOut className="w-4 h-4" /> Leave</button>
          </div>
        )}
        <audio ref={returnEl} data-testid="return-audio" autoPlay />
        <p className="mt-6 text-xs text-gray-600 flex gap-1.5"><Mic className="w-3.5 h-3.5" /> Invitation expires {new Date(c.expires_at).toLocaleString()}. Only the producer sees your feed until you're on air.</p>
      </div>
    </div>
  );
}
