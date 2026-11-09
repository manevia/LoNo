import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CalendarDays, Loader2, Radio, Star, Tv } from "lucide-react";
import { api, resolveMedia } from "@/lib/api";
import ProgramGuide from "@/components/tv/ProgramGuide";
import { toggleFavorite, useFavorites } from "@/lib/favorites";

const TABS = [
  ["tv", "Live TV", Tv], ["radio", "Radio", Radio], ["guide", "Guide", CalendarDays], ["favorites", "Favorites", Star],
];
const time = (iso) => new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

function ChannelCard({ item, list, fav }) {
  const href = `/live/play/${item.id}?list=${list}${fav ? "&fav=1" : ""}`;
  const isFav = useFavorites().includes(item.id);
  return (
    <div className="relative" data-focus-key={`ch:${item.id}`}>
      <Link to={href} data-testid={`live-card-${item.id}`}
        className="group block relative aspect-video rounded-xl overflow-hidden border border-white/10 hover:border-white/30 transition">
        <img loading="lazy" decoding="async" src={resolveMedia(item.thumbnail_url)} alt="" className="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" />
        <div className="absolute inset-0 bg-gradient-to-t from-black via-black/50 to-transparent" />
        <div className="absolute top-3 left-3 flex items-center gap-2">
          <span className="font-display text-lg tabular-nums bg-black/60 rounded px-2">{item.number}</span>
          <span className="flex items-center gap-1.5 bg-[#FF3B30] px-2 py-1 rounded text-[10px] font-bold tracking-widest">
            <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" /> LIVE
          </span>
        </div>
        <div className="absolute bottom-3 left-3 right-3">
          <div className="font-display font-medium truncate">{item.title}</div>
          <div className="text-xs text-gray-300 truncate">{item.now ? `${item.now.title} · until ${time(item.now.end)}` : item.category}</div>
        </div>
      </Link>
      <button onClick={() => toggleFavorite(item.id)} aria-pressed={isFav} data-testid={`fav-${item.id}`}
        aria-label={isFav ? `Remove ${item.title} from favorites` : `Add ${item.title} to favorites`}
        className="absolute top-2.5 right-2.5 p-2 rounded-full bg-black/60 hover:bg-black/80">
        <Star className={`w-4 h-4 ${isFav ? "fill-[#FFB000] text-[#FFB000]" : "text-white"}`} />
      </button>
    </div>
  );
}

const Grid = ({ items, list, fav }) => (
  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
    {items.map((i) => <ChannelCard key={i.id} item={i} list={list} fav={fav} />)}
  </div>
);

export default function Live() {
  const [params, setParams] = useSearchParams();
  const tab = TABS.some(([k]) => k === params.get("tab")) ? params.get("tab") : "tv";
  const [guide, setGuide] = useState(null);
  const [guideKind, setGuideKind] = useState("tv");
  const favorites = useFavorites();

  useEffect(() => { api.get("/live/guide").then(({ data }) => setGuide(data)).catch(() => setGuide({ tv: [], radio: [] })); }, []);

  if (!guide) return <div className="min-h-[70vh] grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>;
  const favTv = guide.tv.filter((c) => favorites.includes(c.id));
  const favRadio = guide.radio.filter((c) => favorites.includes(c.id));

  return (
    <div data-testid="live-page" className="max-w-[1600px] mx-auto px-4 md:px-8 pt-8 pb-24">
      <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tighter">Live</h1>
      <p className="mt-3 text-gray-400 max-w-2xl">Live TV, radio and 24/7 streams from creators and stations across the LoNo network.</p>

      <div role="tablist" aria-label="Live sections" className="mt-8 flex gap-2 overflow-x-auto">
        {TABS.map(([k, label, Icon]) => (
          <button key={k} role="tab" aria-selected={tab === k} data-testid={`live-tab-${k}`}
            onClick={() => setParams({ tab: k }, { replace: true })}
            className={`shrink-0 inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm ${tab === k ? "bg-white text-black font-medium" : "bg-white/5 text-gray-300 hover:bg-white/10"}`}>
            <Icon className="w-4 h-4" /> {label}{k === "favorites" && favorites.length ? ` (${favTv.length + favRadio.length})` : ""}
          </button>
        ))}
      </div>

      <div role="tabpanel" className="mt-8">
        {tab === "tv" && <Grid items={guide.tv} list="tv" />}
        {tab === "radio" && <Grid items={guide.radio} list="radio" />}
        {tab === "guide" && (
          <>
            <div role="group" aria-label="Guide type" className="mb-4 flex gap-2 text-sm">
              {[["tv", "TV channels"], ["radio", "Radio stations"]].map(([k, l]) => (
                <button key={k} onClick={() => setGuideKind(k)} aria-pressed={guideKind === k} data-testid={`guide-kind-${k}`}
                  className={`px-4 py-2 rounded-full ${guideKind === k ? "bg-white/15 text-white" : "bg-white/5 text-gray-400"}`}>{l}</button>
              ))}
            </div>
            <ProgramGuide guide={guide} kind={guideKind} />
          </>
        )}
        {tab === "favorites" && (
          favTv.length + favRadio.length === 0 ? (
            <p className="text-gray-400" data-testid="favorites-empty">No favorites yet. Select the star on a channel or station to add it here. Favorites are saved on this device.</p>
          ) : (
            <div className="space-y-10" data-testid="favorites">
              {favTv.length > 0 && <section><h2 className="font-display text-2xl mb-4">TV channels</h2><Grid items={favTv} list="tv" fav /></section>}
              {favRadio.length > 0 && <section><h2 className="font-display text-2xl mb-4">Radio stations</h2><Grid items={favRadio} list="radio" fav /></section>}
            </div>
          )
        )}
      </div>
    </div>
  );
}
