import { useEffect, useState, useRef } from "react";
import { api, resolveMedia } from "@/lib/api";
import { Loader2, Upload, Eye, DollarSign, Coins, Users, Radio, Video, FileVideo, Image as ImageIcon } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import StudioCourses from "@/components/StudioCourses";

const Stat = ({ icon: Icon, label, value, hint, color = "text-white" }) => (
  <div className="p-6 rounded-2xl bg-[#121212] border border-white/10">
    <div className="flex items-center justify-between">
      <div className="text-xs tracking-widest uppercase text-gray-400">{label}</div>
      <Icon className="w-4 h-4 text-gray-500" />
    </div>
    <div className={`mt-3 font-display text-3xl font-medium tracking-tight ${color}`}>{value}</div>
    {hint && <div className="mt-1 text-xs text-gray-500">{hint}</div>}
  </div>
);

export default function Studio() {
  const [dash, setDash] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [form, setForm] = useState({
    title: "", description: "", kind: "movie", category: "Drama",
    thumbnail_url: "https://images.unsplash.com/photo-1782020934325-cfe4cea4fd9c?w=800",
    stream_url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
    duration_sec: 600, is_original: false, is_premium: false,
  });
  const [uploading, setUploading] = useState({ media: 0, thumb: 0 });
  const mediaRef = useRef(null);
  const thumbRef = useRef(null);

  const uploadTo = async (file, kind) => {
    const fd = new FormData();
    fd.append("file", file);
    setUploading((u) => ({ ...u, [kind]: 1 }));
    try {
      const { data } = await api.post("/storage/upload", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => {
          const pct = e.total ? Math.round((e.loaded / e.total) * 100) : 0;
          setUploading((u) => ({ ...u, [kind]: Math.max(1, pct) }));
        },
      });
      if (kind === "media") setForm((f) => ({ ...f, stream_url: data.url }));
      else setForm((f) => ({ ...f, thumbnail_url: data.url }));
      toast.success(`${kind === "media" ? "Media" : "Thumbnail"} uploaded`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Upload failed");
    } finally {
      setUploading((u) => ({ ...u, [kind]: 0 }));
    }
  };

  const load = async () => {
    try { const { data } = await api.get("/creator/dashboard"); setDash(data); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/creator/upload", form);
      toast.success("Content published");
      setUploadOpen(false);
      load();
    } catch (err) { toast.error(err.response?.data?.detail || "Upload failed"); }
  };

  if (loading || !dash) return <div className="min-h-[70vh] grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>;

  return (
    <div data-testid="studio-page" className="max-w-[1600px] mx-auto px-4 md:px-8 pt-8 pb-24">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-10">
        <div>
          <div className="text-[10px] tracking-[0.3em] font-bold text-[#FFB000] uppercase mb-2">Creator Studio</div>
          <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tighter">{dash.channel.name}</h1>
          <div className="mt-2 text-sm text-gray-400">{dash.channel.handle}</div>
        </div>
        <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
          <DialogTrigger asChild>
            <button data-testid="upload-btn" className="flex items-center gap-2 bg-[#FF3B30] hover:bg-[#FF5C53] rounded-full px-6 py-3 font-medium">
              <Upload className="w-4 h-4" /> Upload / Go Live
            </button>
          </DialogTrigger>
          <DialogContent data-testid="upload-dialog" className="bg-[#0a0a0a] border-white/10 text-white max-w-lg">
            <DialogHeader><DialogTitle className="font-display text-xl">Publish new content</DialogTitle></DialogHeader>
            <form onSubmit={submit} className="space-y-3">
              <div><Label className="text-xs">Title</Label><Input data-testid="upload-title" required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="bg-white/5 border-white/10" /></div>
              <div><Label className="text-xs">Description</Label><Textarea data-testid="upload-desc" required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="bg-white/5 border-white/10" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs">Type</Label>
                  <Select value={form.kind} onValueChange={(v) => setForm({ ...form, kind: v })}>
                    <SelectTrigger data-testid="upload-kind" className="bg-white/5 border-white/10"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-[#0a0a0a] border-white/10 text-white">
                      {["movie", "series", "short", "music", "podcast", "live_tv", "live_radio", "course"].map((k) => (
                        <SelectItem key={k} value={k}>{k}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div><Label className="text-xs">Category</Label><Input data-testid="upload-cat" required value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="bg-white/5 border-white/10" /></div>
              </div>
              <div><Label className="text-xs">Thumbnail URL</Label><Input data-testid="upload-thumb" value={form.thumbnail_url} onChange={(e) => setForm({ ...form, thumbnail_url: e.target.value })} className="bg-white/5 border-white/10" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <input ref={thumbRef} type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files?.[0] && uploadTo(e.target.files[0], "thumb")} />
                  <button type="button" data-testid="upload-thumb-file" onClick={() => thumbRef.current?.click()} disabled={uploading.thumb > 0}
                    className="w-full flex items-center justify-center gap-2 bg-white/5 hover:bg-white/10 border border-dashed border-white/15 rounded-lg py-3 text-xs disabled:opacity-60">
                    <ImageIcon className="w-3.5 h-3.5" /> {uploading.thumb > 0 ? `Uploading ${uploading.thumb}%` : "Upload thumbnail"}
                  </button>
                </div>
                <div>
                  <input ref={mediaRef} type="file" accept="video/*,audio/*" className="hidden" onChange={(e) => e.target.files?.[0] && uploadTo(e.target.files[0], "media")} />
                  <button type="button" data-testid="upload-media-file" onClick={() => mediaRef.current?.click()} disabled={uploading.media > 0}
                    className="w-full flex items-center justify-center gap-2 bg-white/5 hover:bg-white/10 border border-dashed border-white/15 rounded-lg py-3 text-xs disabled:opacity-60">
                    <FileVideo className="w-3.5 h-3.5" /> {uploading.media > 0 ? `Uploading ${uploading.media}%` : "Upload media"}
                  </button>
                </div>
              </div>
              <div><Label className="text-xs">Stream URL</Label><Input data-testid="upload-stream" value={form.stream_url} onChange={(e) => setForm({ ...form, stream_url: e.target.value })} className="bg-white/5 border-white/10" /></div>
              <div className="text-[10px] text-gray-500">Up to 100 MB per file. Auto-captions work on media under 25 MB.</div>
              <Button data-testid="upload-submit" type="submit" className="w-full bg-[#FF3B30] hover:bg-[#FF5C53] rounded-full">Publish</Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat icon={Users} label="Subscribers" value={dash.stats.subscribers.toLocaleString()} hint="Total followers" />
        <Stat icon={Eye} label="Total Views" value={dash.stats.total_views.toLocaleString()} hint="Across all uploads" />
        <Stat icon={DollarSign} label="Revenue" value={`$${dash.stats.revenue_usd.toLocaleString()}`} hint="This month" color="text-[#34C759]" />
        <Stat icon={Coins} label="$LONO Earned" value={dash.stats.lono_earned.toLocaleString()} hint="Creator rewards" color="text-[#FFB000]" />
      </div>

      <div className="mt-8 p-6 rounded-2xl bg-[#121212] border border-white/10">
        <div className="text-xs tracking-widest uppercase text-gray-400 mb-4">Views · 14 days</div>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={dash.chart}>
            <CartesianGrid stroke="#1a1a1a" vertical={false} />
            <XAxis dataKey="day" stroke="#666" fontSize={12} />
            <YAxis stroke="#666" fontSize={12} />
            <Tooltip contentStyle={{ background: "#050505", border: "1px solid #262626", borderRadius: 8 }} />
            <Line type="monotone" dataKey="views" stroke="#FF3B30" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <StudioCourses />

      <div className="mt-10">
        <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
          <div>
            <h2 className="font-display text-2xl">Go live and simulcast</h2>
            <p className="text-sm text-gray-400 mt-1">Broadcast from your camera or an encoder (OBS, vMix…) to LoNo and these destinations at once.</p>
          </div>
          <Link to="/studio/live" data-testid="open-live-studio" className="inline-flex items-center gap-2 bg-[#FF3B30] hover:bg-[#FF5C53] rounded-full px-5 py-2.5 text-sm font-medium"><Radio className="w-4 h-4" /> Open Live Studio</Link>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {["YouTube Live", "Facebook Live", "Twitch", "Kick", "X Live", "TikTok Live", "LinkedIn Live", "Instagram Live", "Discord", "Custom RTMP"].map((p) => (
            <Link to="/studio/live" key={p} data-testid={`simulcast-${p.toLowerCase().replace(/\s+/g, "-")}`} className="p-4 rounded-xl bg-white/[0.03] border border-white/10 flex items-center gap-2 hover:border-white/20 transition">
              <Radio className="w-4 h-4 text-[#FF3B30]" />
              <div className="text-sm">{p}</div>
              <div className="ml-auto text-[10px] text-gray-500">{p === "Discord" ? "Not supported" : "Set up"}</div>
            </Link>
          ))}
        </div>
      </div>

      <div className="mt-10">
        <h2 className="font-display text-2xl mb-4">Uploads</h2>
        {dash.videos.length === 0 ? (
          <div className="p-8 rounded-2xl border border-dashed border-white/10 text-center text-gray-400">
            <Video className="w-8 h-8 mx-auto mb-2 opacity-50" />
            No uploads yet. Publish your first video to start earning.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {dash.videos.map((v) => (
              <div key={v.id} className="rounded-xl bg-[#121212] border border-white/10 overflow-hidden">
                <img loading="lazy" decoding="async" src={resolveMedia(v.thumbnail_url)} alt="" className="w-full aspect-video object-cover" />
                <div className="p-4">
                  <div className="font-medium truncate">{v.title}</div>
                  <div className="mt-1 text-xs text-gray-400 flex justify-between">
                    <span>{v.category}</span><span>{v.views?.toLocaleString()} views</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
