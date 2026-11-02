import { Link } from "react-router-dom";
import { Play, Star, Radio } from "lucide-react";
import { resolveMedia } from "@/lib/api";

export default function ContentCard({ item, rank = null, compact = false }) {
  const isLive = item.kind === "live_tv" || item.kind === "live_radio";
  return (
    <Link
      to={`/watch/${item.id}`}
      data-testid={`content-card-${item.id}`}
      className={`group relative ${compact ? "w-full" : "flex-shrink-0 w-[220px] md:w-[260px]"}`}
    >
      {rank !== null && (
        <div className="absolute -left-2 top-0 z-10 font-display text-[8rem] leading-none font-black text-transparent"
             style={{ WebkitTextStroke: "2px rgba(255,255,255,0.6)" }}>
          {rank}
        </div>
      )}
      <div className="relative aspect-[16/10] rounded-xl overflow-hidden bg-[#121212] border border-white/5 group-hover:border-white/20 transition-all">
        <img
          src={resolveMedia(item.thumbnail_url)}
          alt={item.title}
          loading="lazy"
          className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent opacity-80" />

        {isLive && (
          <div className="absolute top-3 left-3 flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#FF3B30] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#FF3B30]"></span>
            </span>
            <span className="text-[10px] font-bold tracking-widest text-white">LIVE</span>
          </div>
        )}
        {item.is_original && (
          <div className="absolute top-3 right-3 text-[10px] tracking-widest font-bold text-[#FFB000] bg-black/60 px-2 py-1 rounded">
            LONO ORIGINAL
          </div>
        )}

        <div className="absolute inset-0 grid place-items-center opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="w-14 h-14 rounded-full bg-white/95 grid place-items-center shadow-2xl">
            <Play className="w-6 h-6 text-black ml-1" fill="black" />
          </div>
        </div>

        <div className="absolute bottom-0 left-0 right-0 p-3">
          <div className="flex items-center gap-2 text-[10px] text-gray-300 uppercase tracking-widest mb-1">
            {isLive && <Radio className="w-3 h-3" />}
            <span>{item.category}</span>
            {item.rating && <><span>·</span><Star className="w-3 h-3 fill-[#FFB000] text-[#FFB000]" /><span>{item.rating}</span></>}
          </div>
          <h3 className="text-white font-display font-medium text-base leading-tight truncate">{item.title}</h3>
        </div>
      </div>
    </Link>
  );
}
