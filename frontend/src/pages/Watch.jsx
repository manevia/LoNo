import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, API, resolveMedia } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Loader2, Share2, Plus, ThumbsUp, Sparkles, Coins, Captions } from "lucide-react";
import { toast } from "sonner";
import ContentCard from "@/components/ContentCard";

export default function Watch() {
  const { id } = useParams();
  const { user, refresh } = useAuth();
  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState("");
  const [summarizing, setSummarizing] = useState(false);
  const [subtitleUrl, setSubtitleUrl] = useState(null);
  const [transcribing, setTranscribing] = useState(false);
  const rewardedRef = useRef(false);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const { data } = await api.get(`/content/${id}`);
        setItem(data);
      } finally { setLoading(false); }
    })();
    rewardedRef.current = false;
    setSummary("");
  }, [id]);

  // Watch-to-earn: after 20 seconds ping backend
  useEffect(() => {
    if (!item || !user) return;
    const timer = setTimeout(async () => {
      if (rewardedRef.current) return;
      rewardedRef.current = true;
      try {
        const { data } = await api.post("/content/watch", { content_id: item.id, seconds_watched: 120 });
        if (data.reward > 0) {
          toast.success(`+${data.reward} $LONO earned`, { description: "Watch-to-Earn credited to your wallet" });
          refresh();
        }
      } catch { /* silent */ }
    }, 20000);
    return () => clearTimeout(timer);
  }, [item, user, refresh]);

  const summarize = async () => {
    setSummarizing(true);
    try {
      const { data } = await api.post("/ai/summarize", { content_id: id });
      setSummary(data.summary);
    } catch {
      toast.error("Couldn't generate summary");
    } finally { setSummarizing(false); }
  };

  const generateCaptions = async () => {
    setTranscribing(true);
    try {
      await api.post(`/ai/transcribe/${id}`);
      setSubtitleUrl(`${API}/content/${id}/subtitles.vtt?ts=${Date.now()}`);
      toast.success("Captions generated");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Transcription failed");
    } finally { setTranscribing(false); }
  };

  if (loading || !item) return (
    <div className="min-h-[70vh] grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>
  );

  const isAudio = item.kind === "music" || item.kind === "podcast" || item.kind === "live_radio";

  return (
    <div data-testid="watch-page" className="max-w-[1600px] mx-auto px-4 md:px-8 pt-6 pb-24">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-8">
          {isAudio ? (
            <div className="relative rounded-2xl overflow-hidden bg-[#121212] ring-1 ring-white/10 aspect-video">
              <img src={resolveMedia(item.thumbnail_url)} alt={item.title} className="absolute inset-0 w-full h-full object-cover opacity-40" />
              <div className="absolute inset-0 grid place-items-center">
                <audio data-testid="audio-player" controls src={resolveMedia(item.stream_url)} className="w-2/3 max-w-lg" />
              </div>
            </div>
          ) : (
            <video
              data-testid="video-player"
              key={item.id}
              src={resolveMedia(item.stream_url)}
              poster={resolveMedia(item.thumbnail_url)}
              controls
              autoPlay
              crossOrigin="anonymous"
              className="w-full aspect-video rounded-2xl bg-black ring-1 ring-white/10 shadow-2xl"
            >
              {subtitleUrl && (
                <track
                  key={subtitleUrl}
                  data-testid="video-captions-track"
                  kind="subtitles"
                  label="English"
                  srcLang="en"
                  src={subtitleUrl}
                  default
                />
              )}
            </video>
          )}

          <div className="mt-6 flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="text-[10px] tracking-[0.3em] font-bold text-[#FFB000] uppercase mb-2">
                {item.is_original ? "LoNo Original · " : ""}{item.category} · {item.year}
              </div>
              <h1 className="font-display text-3xl md:text-4xl font-medium tracking-tight">{item.title}</h1>
              <div className="mt-2 flex items-center gap-4 text-sm text-gray-400">
                <span>⭐ {item.rating}</span>
                <span>{item.views?.toLocaleString()} views</span>
                <span>{Math.round((item.duration_sec || 0) / 60)} min</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button data-testid="like-btn" className="flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full px-4 py-2 text-sm">
                <ThumbsUp className="w-4 h-4" /> {(item.likes || 0).toLocaleString()}
              </button>
              <button className="flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full px-4 py-2 text-sm"><Plus className="w-4 h-4" /> My List</button>
              <button className="flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full px-4 py-2 text-sm"><Share2 className="w-4 h-4" /> Share</button>
              <button
                data-testid="captions-btn"
                onClick={generateCaptions}
                disabled={transcribing}
                className="flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full px-4 py-2 text-sm disabled:opacity-50"
                title="Generate subtitles with Whisper"
              >
                {transcribing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Captions className="w-4 h-4" />}
                {subtitleUrl ? "Captions on" : "Generate captions"}
              </button>
            </div>
          </div>

          <p className="mt-6 text-gray-300 leading-relaxed max-w-3xl">{item.description}</p>

          {item.channel && (
            <Link to={`/channel/${item.channel.id}`} data-testid="channel-link" className="mt-6 flex items-center gap-3 p-4 rounded-xl bg-white/[0.03] border border-white/10 hover:border-white/20 transition max-w-md">
              <img src={item.channel.avatar_url} alt="" className="w-12 h-12 rounded-full" />
              <div>
                <div className="font-medium">{item.channel.name}</div>
                <div className="text-xs text-gray-400">{item.channel.subscribers?.toLocaleString()} subscribers</div>
              </div>
              <div className="ml-auto text-xs bg-[#FF3B30] rounded-full px-3 py-1.5 font-medium">Subscribe</div>
            </Link>
          )}

          <div className="mt-8 p-5 rounded-2xl bg-gradient-to-br from-white/5 to-transparent border border-white/10">
            <div className="flex items-center justify-between gap-3 mb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#FFB000]" />
                <div className="font-display text-sm font-medium">AI Summary</div>
              </div>
              <button
                data-testid="ai-summarize-btn"
                onClick={summarize}
                disabled={summarizing}
                className="text-xs bg-white/10 hover:bg-white/20 rounded-full px-3 py-1.5 disabled:opacity-50"
              >
                {summarizing ? "Generating…" : summary ? "Regenerate" : "Generate"}
              </button>
            </div>
            <div className="text-sm text-gray-300 whitespace-pre-wrap min-h-[3rem]">
              {summary || <span className="text-gray-500">Get a fresh AI-generated synopsis and SEO tags.</span>}
            </div>
          </div>
        </div>

        <aside className="lg:col-span-4 space-y-4">
          <div className="p-4 rounded-2xl bg-[#121212] border border-white/10 flex items-center gap-3">
            <Coins className="w-6 h-6 text-[#FFB000]" />
            <div className="text-sm">
              <div className="font-medium">Watch-to-Earn active</div>
              <div className="text-xs text-gray-400">Keep watching to accrue $LONO rewards.</div>
            </div>
          </div>

          <div>
            <div className="text-xs tracking-[0.3em] uppercase text-gray-400 mb-3 px-1">More like this</div>
            <div className="grid grid-cols-2 gap-3">
              {item.similar?.slice(0, 8).map((s) => <ContentCard key={s.id} item={s} />)}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
