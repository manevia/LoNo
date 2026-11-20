import { useEffect, useRef, useState } from "react";
import MediaPlayer from "@/components/MediaPlayer";
import { resolveMedia } from "@/lib/api";

// Linear playback is calculated at the server clock, not when a viewer tunes in.
// Every viewer uses the same anchor; shorter assets repeat for the full slot.
export default function StationPlayout({ station }) {
  const source = station.playout;
  const ref = useRef(null);
  const clock = useRef({ server: 0, received: 0 });
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const key = source ? `${source.mode}:${source.key}:${source.url}` : "off";
  if (clock.current.server !== Date.parse(station.as_of)) clock.current = { server: Date.parse(station.as_of), received: performance.now() };
  useEffect(() => { setError(""); }, [key, retry]);
  const sync = (force = false) => {
    const el = ref.current;
    if (!el || !source?.anchor || !Number.isFinite(el.duration) || el.duration <= 0) return;
    const elapsed = Math.max(0, (clock.current.server + performance.now() - clock.current.received - Date.parse(source.anchor)) / 1000);
    const position = elapsed % el.duration;
    if (force || Math.abs(el.currentTime - position) > 3) el.currentTime = position;
  };
  useEffect(() => { if (!source?.anchor) return; const timer = setInterval(() => { if (!ref.current?.paused) sync(); }, 4000); return () => clearInterval(timer); }, [key, source?.anchor]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!source) return null;
  const live = source.mode === "live";
  return <section className="rounded-2xl border border-white/10 bg-[#121212] p-5 space-y-3">
    <div className="flex items-center justify-between gap-3 flex-wrap"><h2 className="font-display text-xl">{source.title}</h2><span className="rounded-full bg-red-500/20 text-red-300 text-xs px-3 py-1">{live ? "LIVE PRESENTER" : source.mode === "scheduled" ? "SCHEDULED PLAYOUT" : "CONTINUOUS PLAYOUT"}</span></div>
    <MediaPlayer key={`${key}:${retry}`} ref={ref} src={resolveMedia(source.url)} audio={station.kind === "live_radio"} title={source.title} artist={station.name} live={live} autoPlay showOptions={false} onLoadedMetadata={()=>sync(true)} mediaProps={{loop: !live, onPlay:()=>sync(true)}} onFatalError={setError} />
    {error && <div role="alert" className="text-red-300 text-sm">Playback unavailable. <button className="underline" onClick={()=>setRetry(n=>n+1)}>Retry</button></div>}
    <p className="text-xs text-gray-400">{live ? "Live presenter takes priority over the automated schedule." : "You are tuned to the station clock. Programmes switch automatically; shorter media repeat until the slot ends."}</p>
    <button className="text-sm rounded-full border border-white/15 px-3 py-2" onClick={()=>{sync(true);ref.current?.play().catch(()=>{});}}>Tune in / return to current time</button>
  </section>;
}
