import { useRef } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import ContentCard from "@/components/ContentCard";

export default function ContentRail({ title, items, showRank = false, accent = false }) {
  const ref = useRef(null);
  if (!items?.length) return null;

  const scroll = (dir) => {
    const el = ref.current;
    if (!el) return;
    el.scrollBy({ left: dir * el.clientWidth * 0.85, behavior: "smooth" });
  };

  return (
    <section data-testid={`rail-${title.toLowerCase().replace(/\s+/g, "-")}`} className="relative group/rail py-4">
      <div className="flex items-baseline justify-between px-4 md:px-8 mb-4">
        <h2 className={`font-display text-xl md:text-2xl font-medium tracking-tight ${accent ? "text-[#FFB000]" : "text-white"}`}>
          {title}
        </h2>
      </div>
      <div className="relative">
        <button
          onClick={() => scroll(-1)}
          className="hidden md:grid absolute left-2 top-1/2 -translate-y-1/2 z-20 w-10 h-10 rounded-full bg-black/70 backdrop-blur place-items-center opacity-0 group-hover/rail:opacity-100 transition"
          aria-label="Scroll left"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>
        <button
          onClick={() => scroll(1)}
          className="hidden md:grid absolute right-2 top-1/2 -translate-y-1/2 z-20 w-10 h-10 rounded-full bg-black/70 backdrop-blur place-items-center opacity-0 group-hover/rail:opacity-100 transition"
          aria-label="Scroll right"
        >
          <ChevronRight className="w-5 h-5" />
        </button>
        <div
          ref={ref}
          className="flex gap-4 overflow-x-auto no-scrollbar px-4 md:px-8 pb-4 rail-fade"
        >
          {items.map((it, i) => (
            <ContentCard key={it.id} item={it} rank={showRank ? i + 1 : null} />
          ))}
        </div>
      </div>
    </section>
  );
}
