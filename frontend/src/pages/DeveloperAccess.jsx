import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Copy, KeyRound, Plus, RotateCw, Trash2, Webhook } from "lucide-react";
import { api, errorText } from "@/lib/api";

const card = "rounded-2xl bg-[#121212] border border-white/10 p-5";
const field = "w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm";
const chip = "inline-flex items-center gap-1.5 text-xs rounded-full px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10";
const copy = (t, what) => navigator.clipboard.writeText(t).then(() => toast.success(`${what} copied`), () => toast.error("Copy failed"));

/** Creator Studio → Developer Access: integrations for the LoNo Creator API. */
export default function DeveloperAccess() {
  const [meta, setMeta] = useState(null);
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(null);
  const [secret, setSecret] = useState(null);       // shown once after create/rotate
  const [open, setOpen] = useState(null);           // integration id showing deliveries
  const [deliveries, setDeliveries] = useState([]);

  const load = () => api.get("/integrations").then(({ data }) => setItems(data));
  useEffect(() => { api.get("/integrations/meta").then(({ data }) => setMeta(data)); load(); }, []);
  useEffect(() => { if (open) api.get(`/integrations/${open}/deliveries`).then(({ data }) => setDeliveries(data)); }, [open]);

  const create = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post("/integrations", { ...form, webhook_url: form.webhook_url || null });
      setSecret({ name: data.name, token: data.token, webhook_secret: data.webhook_secret }); setForm(null); load();
    } catch (err) { toast.error(errorText(err)); }
  };
  const rotate = async (i) => {
    if (!window.confirm(`Make a new token for ${i.name}? The current one stops working immediately.`)) return;
    const { data } = await api.post(`/integrations/${i.id}/rotate`); setSecret({ name: i.name, token: data.token });
  };
  const rotateWh = async (i) => { const { data } = await api.post(`/integrations/${i.id}/webhook-secret/rotate`); setSecret({ name: i.name, webhook_secret: data.webhook_secret }); };
  const revoke = async (i) => { if (window.confirm(`Revoke ${i.name}? Apps using it lose access.`)) { await api.delete(`/integrations/${i.id}`); load(); } };

  if (!meta) return null;
  return (
    <div className="max-w-4xl mx-auto px-4 md:px-8 pt-8 pb-32" data-testid="developer-access">
      <Link to="/studio" className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white"><ArrowLeft className="w-4 h-4" /> Studio</Link>
      <h1 className="mt-2 font-display text-3xl md:text-4xl font-semibold tracking-tight">Developer Access</h1>
      <p className="mt-2 text-gray-400">Connect scheduling tools, newsroom systems and automations to your LoNo broadcasts with the Creator API. Each integration acts for your account with only the permissions you choose. Audio and video still go through your encoder or Live Studio.</p>
      <div className="mt-3 flex flex-wrap gap-2 text-sm">
        <a href="/api/docs#/creator%20api%20v1" target="_blank" rel="noreferrer" className={chip}>API reference</a>
        <a href="https://github.com/manevia/LoNo/blob/main/docs/CREATOR-API.md" target="_blank" rel="noreferrer" className={chip}>Guide and examples</a>
      </div>

      {secret && (
        <div role="alert" className="mt-6 p-4 rounded-2xl border border-[#FFB000]/40 bg-[#FFB000]/10 space-y-2" data-testid="integration-secret">
          <div className="font-medium">Copy these now for {secret.name}. They won't be shown again.</div>
          {secret.token && <div className="flex items-center gap-2"><code className="flex-1 break-all text-xs bg-black/40 rounded px-2 py-1.5" data-testid="integration-token">{secret.token}</code><button className={chip} onClick={() => copy(secret.token, "Token")}><Copy className="w-3.5 h-3.5" /></button></div>}
          {secret.webhook_secret && <div className="flex items-center gap-2"><code className="flex-1 break-all text-xs bg-black/40 rounded px-2 py-1.5">{secret.webhook_secret}</code><button className={chip} onClick={() => copy(secret.webhook_secret, "Webhook secret")}><Copy className="w-3.5 h-3.5" /></button></div>}
          <button className="text-xs text-gray-300 underline" onClick={() => setSecret(null)}>I've saved them</button>
        </div>
      )}

      <div className="mt-6 space-y-3">
        {items.map((i) => (
          <div key={i.id} className={card} data-testid={`integration-${i.id}`}>
            <div className="flex flex-wrap items-center gap-2">
              <KeyRound className="w-4 h-4 text-[#FFB000]" /><span className="font-medium">{i.name}</span>
              <span className={`text-[11px] px-2 py-0.5 rounded-full ${i.environment === "live" ? "bg-[#FF3B30]/20 text-[#FF8A82]" : "bg-white/10 text-gray-300"}`}>{i.environment === "live" ? "Live" : "Test (private sessions only)"}</span>
              {i.revoked_at && <span className="text-[11px] px-2 py-0.5 rounded-full bg-white/10 text-gray-400">Revoked</span>}
              <span className="ml-auto text-xs text-gray-500">token …{i.secret_hint} · last used {i.last_used_at ? new Date(i.last_used_at).toLocaleString() : "never"}</span>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">{i.scopes.map((s) => <span key={s} className="text-[11px] px-2 py-0.5 rounded bg-white/5 text-gray-300" title={meta.scopes[s]}>{s}</span>)}</div>
            {i.webhook_url && <div className="mt-2 text-xs text-gray-400 flex items-center gap-1.5"><Webhook className="w-3.5 h-3.5" /> {i.webhook_url} · {(i.webhook_events || []).join(", ")}</div>}
            {!i.revoked_at && (
              <div className="mt-3 flex flex-wrap gap-2">
                <button className={chip} onClick={() => rotate(i)}><RotateCw className="w-3.5 h-3.5" /> New token</button>
                {i.webhook_url && <button className={chip} onClick={() => rotateWh(i)}><RotateCw className="w-3.5 h-3.5" /> New webhook secret</button>}
                {i.webhook_url && <button className={chip} onClick={() => setOpen(open === i.id ? null : i.id)}>Deliveries</button>}
                <button className={chip} onClick={() => revoke(i)}><Trash2 className="w-3.5 h-3.5" /> Revoke</button>
              </div>
            )}
            {open === i.id && (
              <ul className="mt-3 text-xs divide-y divide-white/5 border-t border-white/10">
                {deliveries.length === 0 && <li className="py-2 text-gray-500">No deliveries yet.</li>}
                {deliveries.map((d) => <li key={d.id} className="py-1.5 flex gap-3"><span className="text-gray-500 tabular-nums">{new Date(d.created_at).toLocaleTimeString()}</span><span>{d.type}</span><span className={d.status === "delivered" ? "text-[#34C759]" : d.status === "failed" ? "text-[#FF8A82]" : "text-[#FFB000]"}>{d.status}</span><span className="text-gray-500">{d.attempts.length} attempt(s), last {d.attempts.at(-1)?.status ?? d.attempts.at(-1)?.error ?? "-"}</span></li>)}
              </ul>
            )}
          </div>
        ))}
      </div>

      {form ? (
        <form onSubmit={create} className={`${card} mt-6 space-y-3`} data-testid="integration-form">
          <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Name (e.g. Newsroom scheduler)" className={field} data-testid="integration-name" />
          <fieldset><legend className="text-sm text-gray-400 mb-1">Environment</legend>
            <label className="mr-4 text-sm"><input type="radio" checked={form.environment === "test"} onChange={() => setForm({ ...form, environment: "test" })} className="accent-[#FFB000]" /> Test: private test sessions only, nothing public or simulcast</label>
            <label className="text-sm"><input type="radio" checked={form.environment === "live"} onChange={() => setForm({ ...form, environment: "live" })} className="accent-[#FF3B30]" data-testid="integration-live" /> Live</label>
          </fieldset>
          <fieldset><legend className="text-sm text-gray-400 mb-1">Permissions</legend>
            <div className="grid sm:grid-cols-2 gap-1.5">
              {Object.entries(meta.scopes).map(([s, d]) => (
                <label key={s} className="flex gap-2 text-sm"><input type="checkbox" checked={form.scopes.includes(s)} data-testid={`scope-${s}`}
                  onChange={(e) => setForm({ ...form, scopes: e.target.checked ? [...form.scopes, s] : form.scopes.filter((x) => x !== s) })} className="accent-[#FFB000] mt-1" />
                  <span><code className="text-xs">{s}</code><span className="block text-xs text-gray-500">{d}</span></span></label>
              ))}
            </div>
          </fieldset>
          <input value={form.webhook_url} onChange={(e) => setForm({ ...form, webhook_url: e.target.value })} placeholder="Webhook URL (https, optional)" className={field} data-testid="integration-webhook" />
          <div className="flex gap-2">
            <button disabled={!form.scopes.length} className="bg-white text-black rounded-full px-5 py-2 text-sm font-medium disabled:opacity-50" data-testid="integration-create">Create integration</button>
            <button type="button" onClick={() => setForm(null)} className="text-sm text-gray-400 px-3">Cancel</button>
          </div>
        </form>
      ) : (
        <button onClick={() => setForm({ name: "", environment: "test", scopes: ["sessions:read"], webhook_url: "", webhook_events: ["*"] })} data-testid="new-integration"
          className="mt-6 inline-flex items-center gap-2 bg-[#FF3B30] rounded-full px-5 py-2.5 text-sm font-medium"><Plus className="w-4 h-4" /> New integration</button>
      )}
    </div>
  );
}
