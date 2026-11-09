import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Star } from "lucide-react";
import { resolveMedia } from "@/lib/api";
import { toggleFavorite, useFavorites } from "@/lib/favorites";

const PX_PER_MIN = 6; // 30 minutes = 180px
const time = (d) => new Date(d).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

/**
 * Program guide: one row per channel/station, programs laid out on a time axis.
 * Every cell is a link to the live player, so arrows move through rows and
 * programs, OK plays the channel, and Back returns here with focus restored.
 */
export default function ProgramGuide({ guide, kind }) {
  const favorites = useFavorites();
  const [focused, setFocused] = useState(null);
  const channels = guide[kind] || [];
  const start = new Date(guide.start).getTime();
  const end = new Date(guide.end).getTime();
  const nowPx = ((new Date(guide.now).getTime() - start) / 60000) * PX_PER_MIN;
  const width = ((end - start) / 60000) * PX_PER_MIN;
  const ticks = useMemo(() => {
    const out = [];
    for (let t = start; t < end; t += 30 * 60000) out.push(t);
    return out;
  }, [start, end]);
  const list = kind === "radio" ? "radio" : "tv";

  return (
    <div data-testid={`guide-${kind}`}>
      <div className="mb-4 min-h-[4.5rem] rounded-xl bg-white/[0.03] border border-white/10 px-4 py-3" aria-live="polite" data-testid="guide-details">
        {focused ? (
          <>
            <div className="text-xs text-gray-400">{focused.channel} · {time(focused.start)}–{time(focused.end)}{focused.live && " · On now"}</div>
            <div className="font-display text-lg">{focused.title}</div>
            <div className="text-sm text-gray-400 truncate">{focused.description}</div>
          </>
        ) : <div className="text-sm text-gray-400 pt-3">Move through the guide to see program details. OK plays the channel.</div>}
      </div>
      <div className="overflow-x-auto rounded-xl border border-white/10">
        <div style={{ width: width + 240 }} className="relative">
          <div className="flex sticky top-0 bg-[#0b0b0b] border-b border-white/10 text-xs text-gray-400">
            <div className="w-60 shrink-0 px-4 py-2">{kind === "radio" ? "Station" : "Channel"}</div>
            {ticks.map((t) => <div key={t} style={{ width: 30 * PX_PER_MIN }} className="shrink-0 px-2 py-2 border-l border-white/5">{time(t)}</div>)}
          </div>
          <div className="absolute top-0 bottom-0 w-0.5 bg-[#FF3B30] z-10 pointer-events-none" style={{ left: 240 + nowPx }} aria-hidden="true" />
          {channels.map((c) => {
            const href = `/live/play/${c.id}?list=${list}`;
            const fav = favorites.includes(c.id);
            return (
              <div key={c.id} className="flex border-b border-white/5" data-testid={`guide-row-${c.id}`}>
                <div className="w-60 shrink-0 flex items-center gap-2 px-2 py-2 sticky left-0 bg-[#0b0b0b] z-20">
                  <Link to={href} data-focus-key={`guide:${c.id}`} data-testid={`guide-channel-${c.id}`}
                    onFocus={() => c.now && setFocused({ ...c.now, channel: `${c.number} ${c.title}`, live: true })}
                    className="flex-1 min-w-0 flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-white/10">
                    <span className="w-6 text-right tabular-nums text-gray-400">{c.number}</span>
                    <img src={resolveMedia(c.thumbnail_url)} alt="" className="w-10 h-10 rounded object-cover bg-white/5" />
                    <span className="truncate text-sm font-medium">{c.title}</span>
                  </Link>
                  <button onClick={() => toggleFavorite(c.id)} aria-pressed={fav} aria-label={fav ? `Remove ${c.title} from favorites` : `Add ${c.title} to favorites`}
                    data-testid={`guide-fav-${c.id}`} className="p-2 rounded-lg hover:bg-white/10">
                    <Star className={`w-4 h-4 ${fav ? "fill-[#FFB000] text-[#FFB000]" : "text-gray-500"}`} />
                  </button>
                </div>
                <div className="relative h-16" style={{ width }}>
                  {c.programs.map((p) => {
                    const ps = Math.max(start, new Date(p.start).getTime()), pe = Math.min(end, new Date(p.end).getTime());
                    const left = ((ps - start) / 60000) * PX_PER_MIN, w = ((pe - ps) / 60000) * PX_PER_MIN;
                    const live = c.now && p.start === c.now.start;
                    return (
                      <Link key={p.start} to={href} data-focus-key={`guide:${c.id}:${p.start}`}
                        onFocus={() => setFocused({ ...p, channel: `${c.number} ${c.title}`, live })}
                        style={{ left: left + 2, width: Math.max(0, w - 4) }}
                        className={`absolute top-1.5 bottom-1.5 rounded-lg px-3 py-1.5 text-sm overflow-hidden border ${live ? "bg-[#FF3B30]/15 border-[#FF3B30]/40" : "bg-white/[0.04] border-white/10 hover:bg-white/10"}`}>
                        <div className="truncate font-medium">{p.title}</div>
                        <div className="truncate text-xs text-gray-400">{time(p.start)}</div>
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
