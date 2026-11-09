import { Play, Info } from "lucide-react";
import { Link } from "react-router-dom";
import { resolveMedia } from "@/lib/api";

export default function HeroBanner({ item }) {
  if (!item) return null;
  return (
    <section data-testid="home-hero" className="relative w-full h-[70vh] min-h-[560px] overflow-hidden">
      <img src={resolveMedia(item.thumbnail_url)} alt={item.title} className="absolute inset-0 w-full h-full object-cover" />
      <div className="absolute inset-0 bg-gradient-to-r from-black via-black/60 to-transparent" />
      <div className="absolute inset-0 bg-gradient-to-t from-[#050505] via-transparent to-transparent" />

      <div className="relative z-10 h-full max-w-[1600px] mx-auto px-4 md:px-8 flex flex-col justify-end pb-16 md:pb-24">
        <div className="text-[10px] tracking-[0.3em] font-bold text-[#FFB000] uppercase mb-3 flex items-center gap-3">
          <span className="w-8 h-px bg-[#FFB000]" />
          LoNo Original · {item.category}
        </div>
        <h1 className="font-display font-semibold tracking-tighter text-5xl md:text-6xl lg:text-7xl max-w-3xl leading-[0.95]">
          {item.title}
        </h1>
        <p className="mt-4 text-base md:text-lg text-gray-300 max-w-2xl leading-relaxed">{item.description}</p>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Link
            to={`/watch/${item.id}`}
            data-testid="hero-play-btn"
            className="inline-flex items-center gap-2 bg-white text-black hover:bg-gray-200 rounded-full px-6 py-3 font-medium transition"
          >
            <Play className="w-4 h-4" fill="black" /> Watch Now
          </Link>
          <Link
            to={`/watch/${item.id}`}
            data-testid="hero-info-btn"
            className="inline-flex items-center gap-2 bg-white/10 backdrop-blur border border-white/20 hover:bg-white/20 rounded-full px-6 py-3 font-medium transition"
          >
            <Info className="w-4 h-4" /> More Info
          </Link>
          <div className="ml-2 flex items-center gap-2 text-xs text-gray-400">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#34C759]" />
            Earn 1 $LONO per minute you watch, up to 10
          </div>
        </div>
      </div>
    </section>
  );
}
