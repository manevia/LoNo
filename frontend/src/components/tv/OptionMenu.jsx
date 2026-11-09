import { useEffect, useRef } from "react";
import { Check } from "lucide-react";
import { useBack } from "@/lib/backStack";

/** A small list menu (captions, audio, quality, speed). Arrows move, OK picks, Back closes. */
export default function OptionMenu({ title, options, value, onPick, onClose, testId }) {
  const ref = useRef(null);
  useBack(true, onClose);
  useEffect(() => {
    const sel = ref.current?.querySelector('[aria-checked="true"]') || ref.current?.querySelector("button");
    sel?.focus();
  }, []);
  return (
    <div ref={ref} role="dialog" aria-label={title} data-testid={testId}
      className="absolute bottom-full mb-3 right-0 min-w-[220px] rounded-xl bg-[#0b0b0b]/95 border border-white/15 p-2 shadow-2xl backdrop-blur">
      <div className="px-3 py-2 text-xs text-gray-400">{title}</div>
      <div role="radiogroup" aria-label={title}>
        {options.map((o) => (
          <button key={String(o.value)} role="radio" aria-checked={o.value === value}
            onClick={() => { onPick(o.value); onClose(); }}
            className="w-full flex items-center gap-3 text-left px-3 py-2.5 rounded-lg text-sm hover:bg-white/10">
            <span className="w-4">{o.value === value && <Check className="w-4 h-4 text-[#FFB000]" />}</span>{o.label}
          </button>
        ))}
      </div>
    </div>
  );
}
