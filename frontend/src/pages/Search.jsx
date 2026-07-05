import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import ContentCard from "@/components/ContentCard";
import { Loader2, Search as SearchIcon } from "lucide-react";

export default function Search() {
  const [params] = useSearchParams();
  const q = params.get("q") || "";
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!q) { setItems([]); return; }
    setLoading(true);
    api.get(`/search?q=${encodeURIComponent(q)}`)
      .then(({ data }) => setItems(data))
      .finally(() => setLoading(false));
  }, [q]);

  return (
    <div data-testid="search-page" className="max-w-[1600px] mx-auto px-4 md:px-8 pt-8 pb-24">
      <div className="flex items-center gap-3 mb-8">
        <SearchIcon className="w-5 h-5 text-gray-400" />
        <h1 className="font-display text-3xl md:text-4xl tracking-tight">Results for "{q}"</h1>
      </div>
      {loading ? (
        <Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" />
      ) : items.length === 0 ? (
        <div className="text-gray-400">No matches found. Try another term.</div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {items.map((i) => <ContentCard key={i.id} item={i} />)}
        </div>
      )}
    </div>
  );
}
