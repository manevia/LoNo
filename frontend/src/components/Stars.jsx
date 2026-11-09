import { useState } from "react";
import { Star } from "lucide-react";

/** Read-only star row. `value` may be fractional (rounded to the nearest half for display). */
export function Stars({ value = 0, size = "w-4 h-4", className = "" }) {
  const v = Math.round((value || 0) * 2) / 2;
  return (
    <span className={`inline-flex items-center gap-0.5 ${className}`} role="img" aria-label={`${value ? value.toFixed(1) : "No"} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className="relative inline-block">
          <Star className={`${size} text-white/20`} />
          {v >= i - 0.5 && (
            <span className="absolute inset-0 overflow-hidden" style={{ width: v >= i ? "100%" : "50%" }}>
              <Star className={`${size} fill-[#FFB000] text-[#FFB000]`} />
            </span>
          )}
        </span>
      ))}
    </span>
  );
}

const LABELS = ["", "Poor", "Fair", "Good", "Very good", "Excellent"];

/** Keyboard-accessible 1–5 star picker (a radio group). */
export function StarPicker({ value, onChange }) {
  const [hover, setHover] = useState(0);
  const shown = hover || value;
  return (
    <div className="flex items-center gap-3">
      <div role="radiogroup" aria-label="Your rating" className="flex" onMouseLeave={() => setHover(0)}>
        {[1, 2, 3, 4, 5].map((i) => (
          <label key={i} className="cursor-pointer p-0.5" onMouseEnter={() => setHover(i)}>
            <input type="radio" name="rating" value={i} checked={value === i} onChange={() => onChange(i)}
              className="sr-only peer" aria-label={`${i} star${i > 1 ? "s" : ""}, ${LABELS[i]}`} />
            <Star className={`w-7 h-7 transition peer-focus-visible:ring-2 peer-focus-visible:ring-[#FFB000] rounded ${i <= shown ? "fill-[#FFB000] text-[#FFB000]" : "text-white/25"}`} />
          </label>
        ))}
      </div>
      <span className="text-sm text-gray-400 w-24">{LABELS[shown] || "Pick a rating"}</span>
    </div>
  );
}
