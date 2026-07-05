import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import HeroBanner from "@/components/HeroBanner";
import ContentRail from "@/components/ContentRail";
import { Loader2 } from "lucide-react";

export default function Home() {
  const [rails, setRails] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/content/rails");
        setRails(data);
      } finally { setLoading(false); }
    })();
  }, []);

  if (loading) return (
    <div className="min-h-[70vh] grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>
  );

  const featured = rails.find((r) => r.key === "featured")?.items?.[0] || rails.find((r) => r.items?.length)?.items?.[0];

  return (
    <div data-testid="home-page">
      <HeroBanner item={featured} />
      <div className="pb-20 -mt-24 relative z-10">
        {rails.map((r) => (
          <ContentRail
            key={r.key}
            title={r.title}
            items={r.items}
            showRank={r.key === "top10"}
            accent={r.key === "originals"}
          />
        ))}
      </div>
    </div>
  );
}
