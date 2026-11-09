import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Loader2, PlayCircle, Ticket } from "lucide-react";
import { api, errorText, resolveMedia } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import MediaPlayer from "@/components/MediaPlayer";
import useWatchSession from "@/lib/useWatchSession";

const fmtDate = (iso) => new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });

/** /passes: the fan's replay passes. */
export function MyPasses() {
  const [items, setItems] = useState(null);
  useEffect(() => { api.get("/me/passes").then(({ data }) => setItems(data)).catch(() => setItems([])); }, []);
  return (
    <div className="max-w-3xl mx-auto px-4 pt-6 pb-28" data-testid="passes-page">
      <h1 className="font-display text-3xl font-semibold">My passes</h1>
      {!items ? <Loader2 className="mt-8 w-6 h-6 animate-spin text-[#FF3B30]" /> : items.length === 0 ? (
        <p className="mt-6 text-gray-400">No passes yet. <Link to="/offers" className="text-[#FFB000]">See offers</Link></p>
      ) : (
        <ul className="mt-6 space-y-3">
          {items.map((p) => (
            <li key={p.id}>
              <Link to={`/passes/${p.id}`} data-testid={`pass-${p.id}`} className="flex gap-3 rounded-2xl bg-[#121212] border border-white/10 p-3 hover:border-white/25">
                <img src={resolveMedia(p.replay.thumbnail_url)} alt="" className="w-28 aspect-video object-cover rounded-lg bg-white/5" />
                <div className="min-w-0">
                  <div className="font-medium truncate">{p.replay.title}</div>
                  <div className="text-xs text-gray-400">Sponsored by {p.sponsor}</div>
                  <div className={`text-xs mt-1 ${p.valid ? "text-[#34C759]" : "text-gray-500"}`}>{p.valid ? `Watch until ${fmtDate(p.expires_at)}` : "Access period ended"}</div>
                </div>
                {p.valid && <PlayCircle className="ml-auto self-center w-7 h-7 text-white/80 shrink-0" />}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** /passes/:id: plays the replay through a link that only works for this fan. */
export function PassPlayer() {
  const { id } = useParams();
  const { user } = useAuth();
  const [play, setPlay] = useState(null);
  const [error, setError] = useState(null);
  const watch = useWatchSession(play?.content_id, user, () => {});

  useEffect(() => {
    let timer;
    const get = () => api.post(`/me/passes/${id}/play`)
      .then(({ data }) => {
        setPlay(data);
        // renew the link before it expires (it lasts a couple of hours)
        timer = setTimeout(get, Math.max(60, data.expires_at - Date.now() / 1000 - 300) * 1000);
      })
      .catch((e) => setError(errorText(e)));
    get();
    return () => clearTimeout(timer);
  }, [id]);

  if (error) return <div className="max-w-xl mx-auto px-4 pt-10 text-center"><p className="text-gray-300">{error}</p><Link to="/passes" className="mt-4 inline-block text-[#FFB000]">My passes</Link></div>;
  if (!play) return <div className="min-h-[60vh] grid place-items-center"><Loader2 className="w-6 h-6 animate-spin text-[#FF3B30]" /></div>;
  return (
    <div className="max-w-5xl mx-auto px-0 sm:px-4 pt-2 sm:pt-6 pb-24" data-testid="pass-player">
      <div className="px-4 sm:px-0 mb-3"><Link to="/passes" className="inline-flex items-center gap-1.5 text-sm text-gray-400"><ArrowLeft className="w-4 h-4" /> My passes</Link></div>
      <MediaPlayer key={play.url} src={play.url} poster={resolveMedia(play.poster)} title={play.title} testId="replay-video"
        mediaProps={watch.mediaProps} className="w-full aspect-video bg-black sm:rounded-2xl" />
      <div className="px-4 sm:px-0 mt-4">
        <h1 className="font-display text-2xl font-semibold">{play.title}</h1>
        <p className="text-sm text-gray-400 mt-1 flex items-center gap-1.5"><Ticket className="w-4 h-4" /> Your pass lets you watch until {fmtDate(play.access_until)}.</p>
      </div>
    </div>
  );
}

