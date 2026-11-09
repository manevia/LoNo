import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, errorText } from "@/lib/api";

const field = "w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm";

/** Social destinations (server URL + stream key). Selected ones are used when going live. */
export default function DestinationsPanel({ selected, onSelect, locked }) {
  const [platforms, setPlatforms] = useState([]);
  const [items, setItems] = useState(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ platform: "youtube", server_url: "", stream_key: "", name: "" });

  const load = () => api.get("/broadcast/destinations").then(({ data }) => setItems(data));
  useEffect(() => { api.get("/broadcast/platforms").then(({ data }) => setPlatforms(data)); load(); }, []);
  const plat = platforms.find((p) => p.id === form.platform);
  useEffect(() => { if (plat) setForm((f) => ({ ...f, server_url: plat.default_url || "" })); }, [form.platform, plat]);

  const add = async (e) => {
    e.preventDefault();
    try { const { data } = await api.post("/broadcast/destinations", form); toast.success(`${data.platform_name} added`); setAdding(false); setForm({ platform: "youtube", server_url: "", stream_key: "", name: "" }); await load(); onSelect([...selected, data.id]); }
    catch (err) { toast.error(errorText(err)); }
  };
  const remove = async (d) => {
    if (!window.confirm(`Remove ${d.name}?`)) return;
    await api.delete(`/broadcast/destinations/${d.id}`); onSelect(selected.filter((x) => x !== d.id)); load();
  };

  return (
    <div data-testid="destinations-panel">
      {items?.length ? (
        <ul className="space-y-2">
          {items.map((d) => (
            <li key={d.id} className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.03] border border-white/10">
              <input type="checkbox" checked={selected.includes(d.id)} disabled={locked} data-testid={`dest-select-${d.platform}`}
                onChange={(e) => onSelect(e.target.checked ? [...selected, d.id] : selected.filter((x) => x !== d.id))}
                aria-label={`Send to ${d.name}`} className="w-4 h-4 accent-[#FF3B30]" />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{d.name}</div>
                <div className="text-xs text-gray-500 truncate">{d.server_url} · key {d.key_hint || "none"}</div>
              </div>
              <button onClick={() => remove(d)} disabled={locked} aria-label={`Remove ${d.name}`} className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 disabled:opacity-30"><Trash2 className="w-4 h-4" /></button>
            </li>
          ))}
        </ul>
      ) : items && <p className="text-sm text-gray-400">No destinations yet. Add one to simulcast. LoNo itself is always included.</p>}

      {adding ? (
        <form onSubmit={add} className="mt-4 p-4 rounded-xl bg-[#121212] border border-white/10 space-y-3" data-testid="add-destination-form">
          <label className="block"><span className="text-xs text-gray-400">Platform</span>
            <select value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })} className={`${field} mt-1`} data-testid="dest-platform">
              {platforms.map((p) => <option key={p.id} value={p.id} disabled={!p.supported} className="bg-[#121212]">{p.name}{!p.supported ? " (not supported)" : ""}</option>)}
            </select></label>
          {plat && <p className="text-xs text-gray-400">{plat.where}</p>}
          <label className="block"><span className="text-xs text-gray-400">Server URL ({plat?.protocols.join(", ").toUpperCase()})</span>
            <input required value={form.server_url} onChange={(e) => setForm({ ...form, server_url: e.target.value })} placeholder={`${plat?.protocols[0] || "rtmp"}://…`} className={`${field} mt-1`} data-testid="dest-url" /></label>
          <label className="block"><span className="text-xs text-gray-400">Stream key (stored encrypted; you won't see it again)</span>
            <input type="password" autoComplete="off" value={form.stream_key} onChange={(e) => setForm({ ...form, stream_key: e.target.value })} className={`${field} mt-1`} data-testid="dest-key" /></label>
          <label className="block"><span className="text-xs text-gray-400">Name (optional)</span>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder={plat?.name} className={`${field} mt-1`} /></label>
          <div className="flex gap-2">
            <button className="bg-white text-black rounded-full px-4 py-2 text-sm font-medium" data-testid="dest-save">Save destination</button>
            <button type="button" onClick={() => setAdding(false)} className="text-sm text-gray-400 px-3">Cancel</button>
          </div>
        </form>
      ) : (
        <button onClick={() => setAdding(true)} disabled={locked} data-testid="add-destination"
          className="mt-3 inline-flex items-center gap-2 text-sm bg-white/5 hover:bg-white/10 border border-white/10 rounded-full px-4 py-2 disabled:opacity-40"><Plus className="w-4 h-4" /> Add destination</button>
      )}
    </div>
  );
}
