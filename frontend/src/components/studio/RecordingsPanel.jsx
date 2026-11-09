import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api, errorText } from "@/lib/api";

const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/** Recordings after a broadcast: private until the creator chooses to publish now or later. */
export default function RecordingsPanel({ refreshKey }) {
  const [items, setItems] = useState([]);
  const [when, setWhen] = useState({});
  const load = () => api.get("/broadcast/recordings").then(({ data }) => setItems(data)).catch(() => {});
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [refreshKey]);

  const act = async (r, body) => {
    try { await api.post(`/broadcast/recordings/${r.id}/publish`, body); toast.success(body.when === "now" ? "Published" : body.when === "private" ? "Kept private" : "Scheduled"); load(); }
    catch (e) { toast.error(errorText(e)); }
  };
  const schedule = (r) => {
    const v = when[r.id];
    if (!v) { toast.error("Pick a date and time first"); return; }
    act(r, { when: "schedule", publish_at: new Date(v).toISOString().replace("Z", "+00:00") });
  };

  if (!items.length) return <p className="text-sm text-gray-400">Turn on Record before going live to keep a copy. Recordings stay private until you publish them.</p>;
  return (
    <ul className="divide-y divide-white/10 border-y border-white/10" data-testid="recordings">
      {items.map((r) => (
        <li key={r.id} className="py-4 flex flex-wrap items-center gap-3" data-testid="recording-row" data-status={r.status} data-visibility={r.visibility}>
          <div className="flex-1 min-w-[12rem]">
            <div className="font-medium">{r.title}</div>
            <div className="text-xs text-gray-400">
              {r.status === "processing" ? "Preparing…" : r.status === "failed" ? `Failed: ${r.error}` : `${fmt(r.duration_sec)} · ${(r.size / 1e6).toFixed(1)} MB`}
              {" · "}{r.visibility === "public" ? "Public" : r.visibility === "scheduled" ? `Publishes ${new Date(r.publish_at).toLocaleString()}` : "Private"}
            </div>
          </div>
          {r.status === "ready" && (
            <div className="flex flex-wrap items-center gap-2">
              <a href={r.url} className="text-xs rounded-full px-3 py-1.5 bg-white/5 border border-white/10">Download</a>
              {r.visibility !== "public"
                ? <button onClick={() => act(r, { when: "now" })} data-testid="rec-publish" className="text-xs rounded-full px-3 py-1.5 bg-white text-black font-medium">Publish now</button>
                : <Link to={`/watch/${r.content_id}`} className="text-xs rounded-full px-3 py-1.5 bg-white/5 border border-white/10">View</Link>}
              <input type="datetime-local" aria-label="Publish at" value={when[r.id] || ""} onChange={(e) => setWhen({ ...when, [r.id]: e.target.value })}
                className="text-xs bg-white/5 border border-white/10 rounded-full px-3 py-1" />
              <button onClick={() => schedule(r)} className="text-xs rounded-full px-3 py-1.5 bg-white/5 border border-white/10">Schedule</button>
              {r.visibility !== "private" && <button onClick={() => act(r, { when: "private" })} data-testid="rec-private" className="text-xs rounded-full px-3 py-1.5 bg-white/5 border border-white/10">Make private</button>}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
