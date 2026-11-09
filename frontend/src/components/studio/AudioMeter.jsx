import { useAudioLevel } from "@/lib/devices";

/** Horizontal level meter in dBFS with a peak marker. Green → amber → red. */
export default function AudioMeter({ track, label = "Level", testId }) {
  const { db, peak, clipping } = useAudioLevel(track);
  const pct = (v) => Math.max(0, Math.min(100, ((v + 60) / 60) * 100));
  return (
    <div data-testid={testId} data-db={Math.round(db)} data-clipping={clipping ? "1" : "0"}>
      <div className="flex justify-between text-xs text-gray-400 mb-1">
        <span>{label}</span>
        <span className={`tabular-nums ${clipping ? "text-[#FF3B30]" : ""}`}>{track?.enabled === false ? "Muted" : clipping ? "Too loud" : db > -100 ? `${Math.round(db)} dB` : "-"}</span>
      </div>
      <div className="relative h-2.5 rounded-full bg-white/10 overflow-hidden" role="meter" aria-label={label}
        aria-valuemin={-60} aria-valuemax={0} aria-valuenow={Math.round(Math.max(-60, db))}>
        <div className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-75"
          style={{ width: `${pct(db)}%`, background: "linear-gradient(90deg,#34C759 0%,#34C759 65%,#FFB000 85%,#FF3B30 100%)", backgroundSize: "400px 100%" }} />
        <div className="absolute inset-y-0 w-0.5 bg-white/80" style={{ left: `${pct(peak)}%` }} aria-hidden="true" />
      </div>
      <div className="flex justify-between text-[10px] text-gray-600 mt-0.5" aria-hidden="true"><span>-60</span><span>-18</span><span>0</span></div>
    </div>
  );
}
