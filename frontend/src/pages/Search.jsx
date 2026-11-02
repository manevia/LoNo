import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import ContentCard from "@/components/ContentCard";
import { Loader2, Search as SearchIcon } from "lucide-react";

export default function Search() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const q = params.get("q") || "";
  const [term, setTerm] = useState(q);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setTerm(q);
    if (!q) { setItems([]); return; }
    setLoading(true);
    api.get("/search", { params: { q } }).then(({ data }) => setItems(data)).finally(() => setLoading(false));
  }, [q]);

  const submit = (e) => { e.preventDefault(); if (term.trim()) nav(`/search?q=${encodeURIComponent(term.trim())}`); };

  return (
    <div data-testid="search-page" className="max-w-[1600px] mx-auto px-4 md:px-8 pt-8 pb-24">
      <form onSubmit={submit} className="relative max-w-2xl md:hidden mb-8">
        <SearchIcon className="w-5 h-5 text-gray-500 absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input autoFocus={!q} value={term} onChange={(e) => setTerm(e.target.value)} aria-label="Search" placeholder="Search shows, music, courses…"
          className="w-full bg-white/5 border border-white/10 rounded-full pl-12 pr-5 py-3 focus:outline-none focus:ring-2 focus:ring-[#FF3B30]/40" />
      </form>
      {q && <h1 className="font-display text-3xl md:text-4xl tracking-tight mb-8">Results for “{q}”</h1>}
      {loading ? (
        <Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" />
      ) : !q ? (
        <p className="text-gray-400">Search by title, description or category, like “Sci-Fi” or “podcast”.</p>
      ) : items.length === 0 ? (
        <p className="text-gray-400">Nothing matches “{q}”. Try a broader word, or browse <a href="/live" className="text-white underline">Live</a> and <a href="/learn" className="text-white underline">Learn</a>.</p>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {items.map((i) => <ContentCard key={i.id} item={i} compact />)}
        </div>
      )}
    </div>
  );
}
