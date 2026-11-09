import { useEffect, useState } from "react";
import { api, resolveMedia } from "@/lib/api";
import { Link } from "react-router-dom";
import { Loader2, Radio, Tv } from "lucide-react";

const Card = ({ item }) => (
  <Link to={`/watch/${item.id}`} data-testid={`live-card-${item.id}`} className="group relative aspect-video rounded-xl overflow-hidden border border-white/10 hover:border-white/30 transition">
    <img loading="lazy" decoding="async" src={resolveMedia(item.thumbnail_url)} alt={item.title} className="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" />
    <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent" />
    <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-[#FF3B30] px-2 py-1 rounded text-[10px] font-bold tracking-widest">
      <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" /> LIVE
    </div>
    <div className="absolute bottom-3 left-3 right-3">
      <div className="text-[10px] tracking-widest uppercase text-gray-300">{item.category}</div>
      <div className="font-display font-medium truncate">{item.title}</div>
    </div>
  </Link>
);

export default function Live() {
  const [data, setData] = useState({ tv: [], radio: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try { const { data } = await api.get("/live/channels"); setData(data); }
      finally { setLoading(false); }
    })();
  }, []);

  if (loading) return <div className="min-h-[70vh] grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>;

  return (
    <div data-testid="live-page" className="max-w-[1600px] mx-auto px-4 md:px-8 pt-8 pb-24">
      <div className="text-[10px] tracking-[0.3em] font-bold text-[#FF3B30] uppercase mb-2">Live & 24/7</div>
      <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tighter">Broadcast Right Now</h1>
      <p className="mt-3 text-gray-400 max-w-2xl">Live television, radio and 24/7 streams from creators and stations across the LoNo network.</p>

      <section className="mt-12">
        <div className="flex items-center gap-2 mb-4"><Tv className="w-4 h-4 text-[#FF3B30]" /><h2 className="font-display text-2xl">Live TV</h2></div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {data.tv.map((i) => <Card key={i.id} item={i} />)}
        </div>
      </section>

      <section className="mt-16">
        <div className="flex items-center gap-2 mb-4"><Radio className="w-4 h-4 text-[#FFB000]" /><h2 className="font-display text-2xl">Live Radio</h2></div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {data.radio.map((i) => <Card key={i.id} item={i} />)}
        </div>
      </section>
    </div>
  );
}
