import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import ContentCard from "@/components/ContentCard";
import { Loader2, Users, PlayCircle } from "lucide-react";

export default function Channel() {
  const { id } = useParams();
  const [ch, setCh] = useState(null);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();
  const nav = useNavigate();

  const subscribe = async () => {
    if (!user) { nav("/login"); return; }
    try {
      const { data } = await api.post(`/channels/${id}/subscribe`);
      setCh((c) => ({ ...c, subscribed: data.subscribed, subscribers: data.subscribers }));
    } catch (e) { toast.error(errorText(e)); }
  };

  useEffect(() => {
    (async () => {
      try { const { data } = await api.get(`/channels/${id}`); setCh(data); }
      finally { setLoading(false); }
    })();
  }, [id, user]);

  if (loading || !ch) return <div className="min-h-[70vh] grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>;

  return (
    <div data-testid="channel-page">
      <div className="relative h-64 md:h-80 overflow-hidden">
        <img src={ch.banner_url} alt="" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#050505] to-transparent" />
      </div>
      <div className="max-w-[1600px] mx-auto px-4 md:px-8 -mt-16 relative">
        <div className="flex items-end gap-6">
          <img src={ch.avatar_url} alt="" className="w-24 h-24 md:w-32 md:h-32 rounded-2xl ring-4 ring-[#050505] bg-white/10" />
          <div className="pb-4">
            <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tight">{ch.name}</h1>
            <div className="text-sm text-gray-400 flex items-center gap-3">
              <span>{ch.handle}</span>
              <span className="flex items-center gap-1"><Users className="w-3 h-3" /> {ch.subscribers?.toLocaleString()}</span>
              <span className="flex items-center gap-1"><PlayCircle className="w-3 h-3" /> {ch.content?.length || 0} uploads</span>
            </div>
          </div>
          {ch.owner_id !== user?.id && (
            <button data-testid="subscribe-btn" onClick={subscribe} aria-pressed={!!ch.subscribed}
              className={`ml-auto mb-4 rounded-full px-6 py-2.5 font-medium ${ch.subscribed ? "bg-white/10 text-gray-200" : "bg-[#FF3B30] hover:bg-[#FF5C53]"}`}>
              {ch.subscribed ? "Subscribed" : "Subscribe"}
            </button>
          )}
        </div>
        <p className="mt-6 text-gray-300 max-w-2xl">{ch.bio}</p>

        <div className="mt-12">
          <h2 className="font-display text-2xl mb-6">Uploads</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 pb-24">
            {ch.content?.length ? ch.content.map((c) => <ContentCard key={c.id} item={c} compact />)
              : <p className="col-span-full text-gray-400">No uploads yet.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
