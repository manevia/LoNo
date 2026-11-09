import { useCallback, useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api, API, errorText, resolveMedia } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useConfig } from "@/lib/config";
import useWatchSession from "@/lib/useWatchSession";
import { Loader2, Share2, Plus, Check, ThumbsUp, Sparkles, Coins, Captions, GraduationCap, Star } from "lucide-react";
import { toast } from "sonner";
import ContentCard from "@/components/ContentCard";
import MediaPlayer from "@/components/MediaPlayer";

const pill = "flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full px-4 py-2 text-sm disabled:opacity-50 transition";

export default function Watch() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user, refresh } = useAuth();
  const cfg = useConfig();
  const [item, setItem] = useState(null);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState("");
  const [summarizing, setSummarizing] = useState(false);
  const [subtitleUrl, setSubtitleUrl] = useState(null);
  const [transcribing, setTranscribing] = useState(false);
  const [viewer, setViewer] = useState({});
  const [counts, setCounts] = useState({ likes: 0, subscribers: 0 });

  const onEarn = useCallback(() => refresh(), [refresh]);
  const watch = useWatchSession(id, user, onEarn);

  useEffect(() => {
    let live = true;
    setItem(null); setError(null); setSummary(""); setSubtitleUrl(null);
    api.get(`/content/${id}`).then(({ data }) => {
      if (!live) return;
      setItem(data);
      setViewer(data.viewer || {});
      setCounts({ likes: data.likes || 0, subscribers: data.channel?.subscribers || 0 });
      if (data.has_subtitles) setSubtitleUrl(`${API}/content/${id}/subtitles.vtt`);
      if (data.ai_summary) setSummary(data.ai_summary);
    }).catch((e) => live && setError(errorText(e, "This title couldn't be loaded.")));
    return () => { live = false; };
  }, [id]);

  const needUser = () => {
    if (user) return false;
    toast("Sign in to do that", { action: { label: "Sign in", onClick: () => nav("/login") } });
    return true;
  };

  const toggleLike = async () => {
    if (needUser()) return;
    const { data } = await api.post(`/content/${id}/like`);
    setViewer((v) => ({ ...v, liked: data.liked })); setCounts((c) => ({ ...c, likes: data.likes }));
  };
  const toggleList = async () => {
    if (needUser()) return;
    const { data } = await api.post(`/content/${id}/list`);
    setViewer((v) => ({ ...v, in_list: data.in_list }));
    toast.success(data.in_list ? "Added to My list" : "Removed from My list");
  };
  const toggleSub = async (e) => {
    e.preventDefault();
    if (needUser()) return;
    try {
      const { data } = await api.post(`/channels/${item.channel.id}/subscribe`);
      setViewer((v) => ({ ...v, subscribed: data.subscribed })); setCounts((c) => ({ ...c, subscribers: data.subscribers }));
    } catch (err) { toast.error(errorText(err)); }
  };
  const share = async () => {
    const url = window.location.href;
    try {
      if (navigator.share) await navigator.share({ title: item.title, url });
      else { await navigator.clipboard.writeText(url); toast.success("Link copied"); }
    } catch { /* user cancelled */ }
  };

  const summarize = async () => {
    setSummarizing(true);
    try { setSummary((await api.post("/ai/summarize", { content_id: id })).data.summary); }
    catch (e) { toast.error(errorText(e, "Couldn't write a summary")); }
    finally { setSummarizing(false); }
  };

  const generateCaptions = async () => {
    if (needUser()) return;
    setTranscribing(true);
    try {
      await api.post(`/ai/transcribe/${id}`);
      setSubtitleUrl(`${API}/content/${id}/subtitles.vtt?ts=${Date.now()}`);
      toast.success("Captions are on");
    } catch (e) { toast.error(errorText(e, "Captions couldn't be generated")); }
    finally { setTranscribing(false); }
  };

  if (error) return (
    <div className="min-h-[60vh] grid place-items-center text-center px-6">
      <div><p className="text-gray-300">{error}</p><Link to="/" className="mt-4 inline-block text-[#FF3B30]">Back to Home</Link></div>
    </div>
  );
  if (!item) return <div className="min-h-[70vh] grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>;

  const isAudio = ["music", "podcast", "live_radio"].includes(item.kind);
  const isLive = item.kind.startsWith("live");
  const resumeAt = viewer.position_sec || 0;
  const onLoadedMetadata = (e) => {
    const m = e.currentTarget;
    if (isLive || resumeAt < 15 || !isFinite(m.duration) || resumeAt > m.duration - 30) return;
    m.currentTime = resumeAt;
    toast(`Resuming from ${Math.floor(resumeAt / 60)}:${String(Math.floor(resumeAt % 60)).padStart(2, "0")}`, {
      action: { label: "Start over", onClick: () => { m.currentTime = 0; } },
    });
  };

  return (
    <div data-testid="watch-page" className="max-w-[1600px] mx-auto px-4 md:px-8 pt-6 pb-32">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-8">
          {isAudio ? (
            <div className="relative rounded-2xl overflow-hidden bg-[#121212] ring-1 ring-white/10 aspect-video">
              <img loading="lazy" decoding="async" src={resolveMedia(item.thumbnail_url)} alt="" className="absolute inset-0 w-full h-full object-cover opacity-40" />
              <div className="absolute inset-0 grid place-items-center p-6">
                <div className="w-full max-w-lg">
                  <MediaPlayer audio testId="audio-player" src={resolveMedia(item.stream_url)} live={isLive}
                    title={item.title} artist={item.channel?.name} artwork={resolveMedia(item.thumbnail_url)}
                    mediaProps={watch.mediaProps} onLoadedMetadata={onLoadedMetadata} />
                </div>
              </div>
            </div>
          ) : (
            <MediaPlayer key={item.id} testId="video-player" src={resolveMedia(item.stream_url)} poster={resolveMedia(item.thumbnail_url)}
              live={isLive} title={item.title} artist={item.channel?.name} artwork={resolveMedia(item.thumbnail_url)}
              subtitleUrl={subtitleUrl} mediaProps={watch.mediaProps} onLoadedMetadata={onLoadedMetadata} />
          )}

          <div className="mt-6 flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="text-xs text-[#FFB000] mb-2">
                {isLive ? "Live now" : item.is_original ? "LoNo Original" : item.kind.replace("_", " ")}
                {" / "}{item.category}{item.year ? ` / ${item.year}` : ""}
              </div>
              <h1 className="font-display text-3xl md:text-4xl font-medium tracking-tight">{item.title}</h1>
              <div className="mt-2 flex items-center gap-4 text-sm text-gray-400">
                {item.rating && <span className="flex items-center gap-1"><Star className="w-3.5 h-3.5 fill-[#FFB000] text-[#FFB000]" /> {item.rating}</span>}
                <span>{item.views?.toLocaleString()} views</span>
                {!isLive && item.duration_sec > 0 && <span>{Math.round(item.duration_sec / 60)} min</span>}
              </div>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <button data-testid="like-btn" onClick={toggleLike} aria-pressed={!!viewer.liked}
                className={`${pill} ${viewer.liked ? "!bg-[#FF3B30]/15 !border-[#FF3B30]/40 text-[#FF8A82]" : ""}`}>
                <ThumbsUp className={`w-4 h-4 ${viewer.liked ? "fill-current" : ""}`} /> {counts.likes.toLocaleString()}
              </button>
              <button data-testid="list-btn" onClick={toggleList} className={pill}>
                {viewer.in_list ? <Check className="w-4 h-4" /> : <Plus className="w-4 h-4" />} My list
              </button>
              <button onClick={share} className={pill}><Share2 className="w-4 h-4" /> Share</button>
              {(cfg.transcription || subtitleUrl) && !isAudio && (
                <button data-testid="captions-btn" onClick={generateCaptions} disabled={transcribing || !!subtitleUrl} className={pill}>
                  {transcribing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Captions className="w-4 h-4" />}
                  {subtitleUrl ? "Captions on" : transcribing ? "Transcribing…" : "Generate captions"}
                </button>
              )}
            </div>
          </div>

          <p className="mt-6 text-gray-300 leading-relaxed max-w-3xl">{item.description}</p>

          {item.course_id && (
            <Link to={`/learn/${item.course_id}`} data-testid="course-link"
              className="mt-6 flex items-center gap-4 p-4 rounded-xl bg-[#FFB000]/10 border border-[#FFB000]/30 hover:border-[#FFB000]/60 transition max-w-xl">
              <GraduationCap className="w-6 h-6 text-[#FFB000] shrink-0" />
              <div className="text-sm"><div className="font-medium">This is part of a course</div>
                <div className="text-gray-400">Work through the lessons, pass the quiz, and earn a certificate and $LONO.</div></div>
              <span className="ml-auto text-sm text-[#FFB000] whitespace-nowrap">Open course</span>
            </Link>
          )}

          {item.channel && (
            <Link to={`/channel/${item.channel.id}`} data-testid="channel-link" className="mt-6 flex items-center gap-3 p-4 rounded-xl bg-white/[0.03] border border-white/10 hover:border-white/20 transition max-w-md">
              <img loading="lazy" decoding="async" src={item.channel.avatar_url} alt="" className="w-12 h-12 rounded-full bg-white/10" />
              <div>
                <div className="font-medium">{item.channel.name}</div>
                <div className="text-xs text-gray-400">{counts.subscribers.toLocaleString()} subscribers</div>
              </div>
              {item.channel.owner_id !== user?.id && (
                <button onClick={toggleSub} data-testid="subscribe-btn"
                  className={`ml-auto text-xs rounded-full px-3 py-1.5 font-medium ${viewer.subscribed ? "bg-white/10 text-gray-300" : "bg-[#FF3B30]"}`}>
                  {viewer.subscribed ? "Subscribed" : "Subscribe"}
                </button>
              )}
            </Link>
          )}

          <div className="mt-8 p-5 rounded-2xl bg-white/[0.03] border border-white/10">
            <div className="flex items-center justify-between gap-3 mb-3">
              <div className="flex items-center gap-2"><Sparkles className="w-4 h-4 text-[#FFB000]" /><div className="font-display text-sm font-medium">AI summary</div></div>
              {cfg.ai && !summary && (
                <button data-testid="ai-summarize-btn" onClick={summarize} disabled={summarizing} className="text-xs bg-white/10 hover:bg-white/20 rounded-full px-3 py-1.5 disabled:opacity-50">
                  {summarizing ? "Writing…" : "Write summary"}
                </button>
              )}
            </div>
            <div className="text-sm text-gray-300 whitespace-pre-wrap min-h-[3rem]">
              {summary || <span className="text-gray-500">{cfg.ai ? "Get a short, spoiler-free synopsis written by Claude." : "AI summaries appear here once the server has an Anthropic API key."}</span>}
            </div>
          </div>
        </div>

        <aside className="lg:col-span-4 space-y-4">
          <EarnCard user={user} watch={watch} />
          <div>
            <h2 className="text-sm text-gray-400 mb-3 px-1">More like this</h2>
            <div className="grid grid-cols-2 gap-3">
              {item.similar?.slice(0, 8).map((s) => <ContentCard key={s.id} item={s} compact />)}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function EarnCard({ user, watch }) {
  if (!user) return (
    <Link to="/signup" className="p-4 rounded-2xl bg-[#121212] border border-white/10 flex items-center gap-3 hover:border-white/20">
      <Coins className="w-6 h-6 text-[#FFB000]" />
      <div className="text-sm"><div className="font-medium">Earn $LONO while you watch</div>
        <div className="text-xs text-gray-400">Create a free account and get 100 $LONO to start.</div></div>
    </Link>
  );
  const mins = Math.floor((watch.verified || 0) / 60);
  return (
    <div data-testid="earn-card" className="p-4 rounded-2xl bg-[#121212] border border-white/10">
      <div className="flex items-center gap-3">
        <Coins className="w-6 h-6 text-[#FFB000]" />
        <div className="text-sm flex-1">
          <div className="font-medium">{watch.capped ? "Reward limit reached for this title" : watch.session ? "Earning while you watch" : "Press play to start earning"}</div>
          <div className="text-xs text-gray-400">1 $LONO per verified minute, up to 10 per title.</div>
        </div>
        <div className="text-right font-display text-xl text-[#FFB000] tabular-nums">{watch.earned.toFixed(0)}</div>
      </div>
      {watch.session && (
        <div className="mt-3 flex justify-between text-xs text-gray-500">
          <span>{mins} verified min</span>
          {watch.dailyRemaining != null && <span>{Math.max(0, watch.dailyRemaining).toFixed(0)} left today</span>}
        </div>
      )}
    </div>
  );
}
