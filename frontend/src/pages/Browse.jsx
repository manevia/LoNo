import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import ContentCard from "@/components/ContentCard";
import { Loader2 } from "lucide-react";

const LABELS = {
  movie: "Movies", series: "Series", short: "Shorts",
  music: "Music", podcast: "Podcasts", course: "Courses",
};

export default function Browse() {
  const { kind } = useParams();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const { data } = await api.get(`/content?kind=${kind}&limit=100`);
        setItems(data);
      } finally { setLoading(false); }
    })();
  }, [kind]);

  return (
    <div data-testid="browse-page" className="max-w-[1600px] mx-auto px-4 md:px-8 pt-8 pb-24">
      <div className="text-[10px] tracking-[0.3em] font-bold text-[#FFB000] uppercase mb-2">Browse</div>
      <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tighter">{LABELS[kind] || "All"}</h1>

      {loading ? (
        <div className="mt-16 grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>
      ) : items.length === 0 ? (
        <div className="mt-16 text-gray-400">No content yet in this category.</div>
      ) : (
        <div className="mt-10 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {items.map((i) => <div key={i.id} className="w-full"><ContentCard item={i} compact /></div>)}
        </div>
      )}
    </div>
  );
}
