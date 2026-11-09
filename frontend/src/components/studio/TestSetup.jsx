import { useEffect, useRef, useState } from "react";
import { CheckCircle2, AlertTriangle, Circle } from "lucide-react";
import { useAudioLevel } from "@/lib/devices";

const Icon = ({ s }) => s === "pass" ? <CheckCircle2 className="w-5 h-5 text-[#34C759]" /> : s === "warn" ? <AlertTriangle className="w-5 h-5 text-[#FFB000]" /> : <Circle className="w-5 h-5 text-gray-600" />;

/**
 * Test Setup: framing, audio levels, audio/video sync and connection, before
 * going live. `stats` gives connection numbers once a private test is running.
 */
export default function TestSetup({ videoTrack, audioTrack, stats, testing, mode }) {
  const level = useAudioLevel(mode === "device" ? audioTrack : null);
  const [levelResult, setLevelResult] = useState(null);
  const [measuring, setMeasuring] = useState(false);
  const [syncOk, setSyncOk] = useState(false);
  const peaks = useRef([]);

  useEffect(() => {
    if (!measuring) return undefined;
    peaks.current.push({ db: level.db, clip: level.clipping });
    return undefined;
  }, [level, measuring]);

  const measure = () => {
    peaks.current = []; setMeasuring(true); setLevelResult(null);
    setTimeout(() => {
      setMeasuring(false);
      const p = peaks.current;
      const max = Math.max(...p.map((x) => x.db), -100);
      const clipped = p.some((x) => x.clip);
      setLevelResult(clipped ? { s: "warn", msg: "Too loud: it clipped. Lower the input gain on your mic or interface." }
        : max < -30 ? { s: "warn", msg: `Too quiet (peak ${Math.round(max)} dB). Move closer or raise the gain.` }
        : { s: "pass", msg: `Good level (peak ${Math.round(max)} dB).` });
    }, 5000);
  };

  const st = videoTrack?.getSettings?.() || {};
  const framing = mode === "encoder" ? { s: "pass", msg: "Check framing in your encoder and in the preview." }
    : !videoTrack ? { s: "warn", msg: "Camera is off (audio-only broadcast)." }
    : st.height >= 720 && (st.frameRate || 0) >= 24 ? { s: "pass", msg: `${st.width}×${st.height} at ${Math.round(st.frameRate)} fps. Use the framing grid to line up eyes on the top third.` }
    : { s: "warn", msg: `${st.width}×${st.height} at ${Math.round(st.frameRate || 0)} fps. 720p and 24 fps or more look best.` };
  const conn = !testing ? { s: null, msg: "Start a private test to measure your connection." }
    : !stats || stats.kbps == null ? { s: null, msg: "Measuring…" }
    : stats.kbps >= 1500 && (stats.lossPct ?? 0) < 2 ? { s: "pass", msg: `${stats.kbps} kbps${stats.rttMs != null ? `, ${stats.rttMs} ms round trip` : ""}${stats.lossPct != null ? `, ${stats.lossPct}% loss` : ""}.` }
    : { s: "warn", msg: `${stats.kbps} kbps${stats.lossPct ? `, ${stats.lossPct}% loss` : ""}. Use a wired connection or a lower quality for a steadier stream.` };

  const rows = [
    ["Camera framing", framing.s, framing.msg],
    ["Audio levels", mode === "encoder" ? "pass" : levelResult?.s, mode === "encoder" ? "Check levels in your encoder's mixer; the preview meter shows what LoNo receives." : measuring ? "Speak normally for 5 seconds…" : levelResult?.msg || "Speak normally and measure."],
    ["Audio and video in sync", syncOk ? "pass" : null, testing ? "Clap once on camera, then watch the private preview: the sound should land with your hands." : "Start a private test, then clap and watch the preview."],
    ["Connection quality", conn.s, conn.msg],
  ];

  return (
    <div data-testid="test-setup" className="rounded-2xl bg-[#121212] border border-white/10 p-5">
      <h3 className="font-display text-lg">Test Setup</h3>
      <ul className="mt-3 space-y-3">
        {rows.map(([title, s, msg], i) => (
          <li key={title} className="flex gap-3" data-testid={`check-${i}`} data-status={s || "pending"}>
            <Icon s={s} />
            <div className="flex-1">
              <div className="text-sm font-medium">{title}</div>
              <div className="text-xs text-gray-400 mt-0.5">{msg}</div>
              {i === 1 && mode === "device" && audioTrack && <button onClick={measure} disabled={measuring} data-testid="measure-levels" className="mt-2 text-xs rounded-full px-3 py-1.5 bg-white/5 border border-white/10 disabled:opacity-50">{measuring ? "Listening…" : "Measure levels"}</button>}
              {i === 2 && testing && <label className="mt-2 flex items-center gap-2 text-xs"><input type="checkbox" checked={syncOk} onChange={(e) => setSyncOk(e.target.checked)} className="accent-[#34C759]" data-testid="sync-ok" /> Sound and picture match</label>}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
