import { useEffect, useState } from "react";
import { Copy, Eye, EyeOff, RotateCw } from "lucide-react";
import { toast } from "sonner";
import { api, errorText } from "@/lib/api";

const chip = "inline-flex items-center gap-1.5 text-xs rounded-full px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10";

const TOOLS = [
  ["OBS Studio", "Settings → Stream → Service: Custom… → paste Server and Stream Key. Settings → Output (Advanced): Encoder x264 or hardware H.264, Rate control CBR, Bitrate 2500–6000 Kbps, Keyframe interval 2 s. Audio: 48 kHz. For SRT: Service Custom, Server = the SRT URL, leave Stream Key empty."],
  ["vMix", "Stream → Destination: Custom RTMP Server → URL = Server, Stream Name or Key = Stream key. Quality: H.264, 2–6 Mbps, keyframe 2 s, AAC 48 kHz. vMix also supports SRT under Outputs → SRT (Caller, using the SRT URL's host, port and streamid)."],
  ["Streamlabs Desktop", "Settings → Stream → Stream Type: Custom Streaming Server → URL = Server, Stream key = Stream key. Output: H.264, CBR, keyframe 2 s."],
  ["Wirecast", "Output → Output Settings → Destination: RTMP Server → Address = Server, Stream = Stream key. Encoding: H.264 + AAC, keyframe every 2 s."],
  ["Hardware encoders and mixers", "Devices such as ATEM Mini Pro, Teradek, LiveU, Magewell and Osprey take an RTMP(S) server and key, or an SRT URL, in their web or app settings. Cameras and mixers without streaming can join through a capture card (Elgato, Magewell, Blackmagic): it appears as a camera under This device, or as a source in OBS/vMix."],
];

/** External encoder settings: ingest URLs and the stream key (masked, copy, rotate). */
export default function EncoderPanel({ live }) {
  const [ing, setIng] = useState(null);
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get("/broadcast/ingest").then(({ data }) => setIng(data)).catch(() => setIng(false)); }, []);

  const copy = async (text, what) => { try { await navigator.clipboard.writeText(text); toast.success(`${what} copied`); } catch { toast.error("Copy failed. Select and copy it manually."); } };
  const rotate = async () => {
    if (!window.confirm("Make a new stream key? The old one stops working immediately; update your encoder afterwards.")) return;
    setBusy(true);
    try { const { data } = await api.post("/broadcast/ingest/rotate"); setIng(data); setShow(true); toast.success("New stream key ready"); }
    catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
  };

  if (ing === false) return <p className="text-sm text-gray-400">Encoder settings couldn't be loaded.</p>;
  if (!ing) return null;
  const masked = ing.rtmp.stream_key.replace(/key=.*/, "key=••••••••••" + ing.key_hint.replace("…", ""));

  const Field = ({ label, value, secret, testId }) => (
    <div>
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className="flex items-center gap-2">
        <code data-testid={testId} className="flex-1 min-w-0 truncate text-sm bg-black/40 border border-white/10 rounded-lg px-3 py-2">{secret && !show ? secret : value}</code>
        {secret && <button className={chip} onClick={() => setShow(!show)} aria-label={show ? "Hide" : "Show"}>{show ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}</button>}
        <button className={chip} onClick={() => copy(value, label)} aria-label={`Copy ${label}`}><Copy className="w-3.5 h-3.5" /></button>
      </div>
    </div>
  );

  return (
    <div data-testid="encoder-panel" className="space-y-4">
      {Field({ label: "Server (RTMP)", value: ing.rtmp.server, testId: "ingest-server" })}
      {ing.rtmps && Field({ label: "Server (RTMPS, encrypted)", value: ing.rtmps.server })}
      {Field({ label: "Stream key", value: ing.rtmp.stream_key, secret: masked, testId: "ingest-key" })}
      {Field({ label: "SRT URL (includes the key)", value: ing.srt.url, secret: ing.srt.url.replace(/:[^:]*$/, ":••••••••••") })}
      <div className="flex flex-wrap items-center gap-2">
        <button className={chip} onClick={rotate} disabled={busy || live} data-testid="rotate-key"><RotateCw className="w-3.5 h-3.5" /> New stream key</button>
        <span className="text-xs text-gray-500">{live ? "You can change the key after the broadcast ends." : "Keep the key private. Anyone with it can broadcast as you."}</span>
      </div>
      <details className="rounded-xl bg-white/[0.03] border border-white/10 p-4">
        <summary className="text-sm cursor-pointer">Setup for OBS, vMix, Streamlabs, Wirecast and hardware</summary>
        <dl className="mt-3 space-y-3 text-sm">
          {TOOLS.map(([t, d]) => <div key={t}><dt className="font-medium">{t}</dt><dd className="text-gray-400 mt-0.5">{d}</dd></div>)}
        </dl>
        <p className="mt-3 text-xs text-gray-500">LoNo forwards what your encoder sends without re-encoding, so use H.264 video and AAC audio. Every social platform accepts those.</p>
      </details>
    </div>
  );
}
