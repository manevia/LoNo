import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ArrowLeft, CheckCircle2, Circle, Download, Plus, RefreshCw, XCircle } from "lucide-react";
import { api, errorText } from "@/lib/api";

const field = "w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm";
const btn = "inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm bg-white/10 hover:bg-white/15 border border-white/10 disabled:opacity-40";
const card = "rounded-2xl bg-[#121212] border border-white/10 p-4";
const STATUS = { draft: "bg-white/10 text-gray-300", open: "bg-[#34C759]/20 text-[#34C759]", paused: "bg-[#FFB000]/20 text-[#FFB000]", closed: "bg-white/5 text-gray-500" };
const toIso = (local) => (local ? new Date(local).toISOString() : "");
const fmt = (iso) => (iso ? new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "-");
const money = (v, cur) => (v == null ? "-" : `${cur} ${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);

function ContentPicker({ label, value, onPick, testId }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState([]);
  const [picked, setPicked] = useState(null);
  useEffect(() => {
    if (q.length < 2) { setHits([]); return undefined; }
    const t = setTimeout(() => api.get(`/search?q=${encodeURIComponent(q)}`).then(({ data }) => setHits(Array.isArray(data) ? data : data.results || [])).catch(() => {}), 250);
    return () => clearTimeout(t);
  }, [q]);
  return (
    <div className="relative">
      <span className="text-xs text-gray-400">{label}</span>
      {value && picked ? (
        <div className="mt-1 flex items-center gap-2 text-sm"><span className="truncate">{picked.title}</span><button type="button" className="text-xs text-gray-400 underline" onClick={() => { setPicked(null); onPick(""); }}>change</button></div>
      ) : (
        <>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search titles…" className={`${field} mt-1`} data-testid={testId} />
          {hits.length > 0 && (
            <ul className="absolute z-10 mt-1 w-full max-h-56 overflow-y-auto rounded-lg bg-[#1a1a1a] border border-white/10">
              {hits.slice(0, 8).map((h) => (
                <li key={h.id}><button type="button" data-testid={`${testId}-hit`} onClick={() => { setPicked(h); onPick(h.id); setHits([]); setQ(""); }} className="w-full text-left px-3 py-2 text-sm hover:bg-white/10">{h.title} <span className="text-xs text-gray-500">{h.kind}</span></button></li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

function NewCampaign({ onCreated, onCancel }) {
  const [partners, setPartners] = useState([]);
  const [np, setNp] = useState({ kind: "sponsor", name: "" });
  const [f, setF] = useState({ title: "", description: "", organizer_id: "", sponsor_id: "", replay_content_id: "", preview_id: "", min_minutes: 2, earn_points: 30,
    points_price: 30, inventory_total: 100, opens: "", closes: "", access_days: 7, report_window_days: 14,
    currency: "USD", sponsor_payment: 0, organizer_compensation: 0, lono_fee: 0, costs: [{ label: "Hosting and delivery", amount: 0 }] });
  const loadPartners = () => api.get("/admin/campaigns/partners").then(({ data }) => setPartners(data));
  useEffect(() => { loadPartners(); }, []);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const addPartner = async () => {
    if (!np.name.trim()) return;
    const { data } = await api.post("/admin/campaigns/partners", np);
    await loadPartners(); setF((x) => ({ ...x, [`${np.kind}_id`]: data.id })); setNp({ ...np, name: "" });
  };
  const submit = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post("/admin/campaigns", {
        title: f.title, description: f.description, organizer_id: f.organizer_id, sponsor_id: f.sponsor_id, replay_content_id: f.replay_content_id,
        earning_rule: { content_id: f.preview_id, min_seconds: Math.round(Number(f.min_minutes) * 60), points: Number(f.earn_points) },
        points_price: Number(f.points_price), inventory_total: Number(f.inventory_total), opens_at: toIso(f.opens), closes_at: toIso(f.closes),
        access_days: Number(f.access_days), report_window_days: Number(f.report_window_days),
        financials: { currency: f.currency.toUpperCase(), sponsor_payment: Number(f.sponsor_payment), organizer_compensation: Number(f.organizer_compensation),
          lono_fee: Number(f.lono_fee), direct_costs: f.costs.filter((c) => c.label).map((c) => ({ label: c.label, amount: Number(c.amount) })) },
      });
      toast.success("Draft created"); onCreated(data.id);
    } catch (err) { toast.error(errorText(err)); }
  };
  const sel = (kind) => (
    <select value={f[`${kind}_id`]} onChange={set(`${kind}_id`)} className={`${field} mt-1`} data-testid={`c-${kind}`} required>
      <option value="" className="bg-[#121212]">Choose…</option>
      {partners.filter((p) => p.kind === kind).map((p) => <option key={p.id} value={p.id} className="bg-[#121212]">{p.name}</option>)}
    </select>
  );
  return (
    <form onSubmit={submit} className="space-y-4" data-testid="new-campaign">
      <button type="button" onClick={onCancel} className="text-sm text-gray-400 inline-flex items-center gap-1"><ArrowLeft className="w-4 h-4" /> Campaigns</button>
      <h3 className="font-display text-xl">New campaign (draft)</h3>
      <div className={card + " grid sm:grid-cols-2 gap-3"}>
        <label className="sm:col-span-2"><span className="text-xs text-gray-400">Title fans see</span><input required value={f.title} onChange={set("title")} className={`${field} mt-1`} data-testid="c-title" placeholder="County Final: full-match replay" /></label>
        <label className="sm:col-span-2"><span className="text-xs text-gray-400">Description</span><input value={f.description} onChange={set("description")} className={`${field} mt-1`} /></label>
        <label><span className="text-xs text-gray-400">Organizer</span>{sel("organizer")}</label>
        <label><span className="text-xs text-gray-400">Sponsor</span>{sel("sponsor")}</label>
        <div className="sm:col-span-2 flex gap-2 items-end">
          <select value={np.kind} onChange={(e) => setNp({ ...np, kind: e.target.value })} className={`${field} w-36`}><option value="sponsor" className="bg-[#121212]">Sponsor</option><option value="organizer" className="bg-[#121212]">Organizer</option></select>
          <input value={np.name} onChange={(e) => setNp({ ...np, name: e.target.value })} placeholder="Add a partner by name" className={field} data-testid="p-name" />
          <button type="button" onClick={addPartner} className={btn} data-testid="p-add"><Plus className="w-4 h-4" /> Add</button>
        </div>
        <div className="sm:col-span-2"><ContentPicker label="Replay (must be uploaded to LoNo; it will be protected)" value={f.replay_content_id} onPick={(id) => setF((x) => ({ ...x, replay_content_id: id }))} testId="c-replay" /></div>
      </div>
      <div className={card + " grid sm:grid-cols-3 gap-3"}>
        <div className="sm:col-span-3"><ContentPicker label="Earning activity: fans watch this title (e.g. the match preview)" value={f.preview_id} onPick={(id) => setF((x) => ({ ...x, preview_id: id }))} testId="c-preview" /></div>
        <label><span className="text-xs text-gray-400">Minutes to watch</span><input type="number" min="0.5" step="0.5" value={f.min_minutes} onChange={set("min_minutes")} className={`${field} mt-1`} /></label>
        <label><span className="text-xs text-gray-400">$LONO earned</span><input type="number" min="1" value={f.earn_points} onChange={set("earn_points")} className={`${field} mt-1`} /></label>
        <label><span className="text-xs text-gray-400">Pass price ($LONO)</span><input type="number" min="1" value={f.points_price} onChange={set("points_price")} className={`${field} mt-1`} data-testid="c-price" /></label>
        <label><span className="text-xs text-gray-400">Passes available</span><input type="number" min="1" value={f.inventory_total} onChange={set("inventory_total")} className={`${field} mt-1`} data-testid="c-inventory" /></label>
        <label><span className="text-xs text-gray-400">Opens</span><input type="datetime-local" required value={f.opens} onChange={set("opens")} className={`${field} mt-1`} data-testid="c-opens" /></label>
        <label><span className="text-xs text-gray-400">Claim deadline</span><input type="datetime-local" required value={f.closes} onChange={set("closes")} className={`${field} mt-1`} data-testid="c-closes" /></label>
        <label><span className="text-xs text-gray-400">Replay access (days)</span><input type="number" min="1" value={f.access_days} onChange={set("access_days")} className={`${field} mt-1`} /></label>
        <label><span className="text-xs text-gray-400">Report window (days)</span><input type="number" min="1" value={f.report_window_days} onChange={set("report_window_days")} className={`${field} mt-1`} /></label>
      </div>
      <div className={card + " grid sm:grid-cols-4 gap-3"}>
        <div className="sm:col-span-4 text-sm text-gray-300">Money (ordinary currency; kept separate from $LONO)</div>
        <label><span className="text-xs text-gray-400">Currency</span><input value={f.currency} onChange={set("currency")} maxLength={3} className={`${field} mt-1`} /></label>
        <label><span className="text-xs text-gray-400">Sponsor pays</span><input type="number" min="0" step="0.01" value={f.sponsor_payment} onChange={set("sponsor_payment")} className={`${field} mt-1`} data-testid="c-sponsor-pay" /></label>
        <label><span className="text-xs text-gray-400">Organizer receives</span><input type="number" min="0" step="0.01" value={f.organizer_compensation} onChange={set("organizer_compensation")} className={`${field} mt-1`} data-testid="c-org-pay" /></label>
        <label><span className="text-xs text-gray-400">LoNo fee</span><input type="number" min="0" step="0.01" value={f.lono_fee} onChange={set("lono_fee")} className={`${field} mt-1`} data-testid="c-fee" /></label>
        {f.costs.map((c, i) => (
          <div key={i} className="sm:col-span-4 grid grid-cols-[1fr_8rem] gap-2">
            <input value={c.label} onChange={(e) => setF({ ...f, costs: f.costs.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)) })} placeholder="Direct cost" className={field} />
            <input type="number" min="0" step="0.01" value={c.amount} onChange={(e) => setF({ ...f, costs: f.costs.map((x, j) => (j === i ? { ...x, amount: e.target.value } : x)) })} className={field} data-testid={`c-cost-${i}`} />
          </div>
        ))}
        <button type="button" className="text-xs text-gray-400 underline justify-self-start" onClick={() => setF({ ...f, costs: [...f.costs, { label: "", amount: 0 }] })}>Add a direct cost</button>
      </div>
      <button className="bg-[#FF3B30] rounded-full px-6 py-2.5 text-sm font-medium" data-testid="c-create">Create draft</button>
    </form>
  );
}

function Check({ ok, children }) {
  return <li className="flex items-start gap-2 text-sm">{ok ? <CheckCircle2 className="w-4 h-4 text-[#34C759] mt-0.5" /> : <Circle className="w-4 h-4 text-gray-600 mt-0.5" />}<span>{children}</span></li>;
}

function Detail({ id, onBack }) {
  const [c, setC] = useState(null);
  const [rep, setRep] = useState(null);
  const [claims, setClaims] = useState([]);
  const [conf, setConf] = useState({ payRef: "", payAmt: "", permRef: "" });
  const [st, setSt] = useState({ invoice: "", orgAmt: "", orgRef: "" });
  const load = async () => {
    const [{ data: cc }, { data: rr }, { data: cl }] = await Promise.all([
      api.get(`/admin/campaigns/${id}`), api.get(`/admin/campaigns/${id}/report`), api.get(`/admin/campaigns/${id}/claims`)]);
    setC(cc); setRep(rr); setClaims(cl);
  };
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  const act = async (fn, ok) => { try { await fn(); if (ok) toast.success(ok); await load(); } catch (e) { toast.error(errorText(e)); } };
  const confirm = (item, body) => act(() => api.post(`/admin/campaigns/${id}/confirm`, { item, ...body }), "Recorded");
  const exportCsv = async () => {
    const res = await api.get(`/admin/campaigns/${id}/sponsor-report.csv`, { responseType: "blob" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(res.data); a.download = `sponsor-report-${id.slice(0, 8)}.csv`; a.click();
  };
  if (!c || !rep) return null;
  const cur = c.financials.currency, m = rep.money, r = rep.reconciliation;
  return (
    <div className="space-y-4" data-testid="campaign-detail">
      <button onClick={onBack} className="text-sm text-gray-400 inline-flex items-center gap-1"><ArrowLeft className="w-4 h-4" /> Campaigns</button>
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="font-display text-2xl mr-auto">{c.title}</h3>
        <span className={`text-xs px-2.5 py-1 rounded-full ${STATUS[c.status]}`} data-testid="c-status">{c.status}</span>
        <button className={btn} onClick={load}><RefreshCw className="w-4 h-4" /></button>
      </div>
      <div className="text-sm text-gray-400">{c.organizer?.name} · sponsored by {c.sponsor?.name} · replay: {c.replay_title} · {c.points_price} $LONO · {c.inventory_total} passes · {fmt(c.opens_at)} to {fmt(c.closes_at)} · {c.access_days} days access</div>

      <div className={card}>
        <h4 className="font-medium mb-2">Before the offer opens</h4>
        <ul className="space-y-2">
          <Check ok={!!c.confirmations.sponsor_payment}>Sponsor payment received {c.confirmations.sponsor_payment && <span className="text-gray-400">({money(c.confirmations.sponsor_payment.amount, cur)}, ref {c.confirmations.sponsor_payment.reference}, by {c.confirmations.sponsor_payment.by_name})</span>}</Check>
          <Check ok={!!c.confirmations.distribution_permission}>Replay distribution permission {c.confirmations.distribution_permission && <span className="text-gray-400">(ref {c.confirmations.distribution_permission.reference})</span>}</Check>
          <Check ok={!!c.confirmations.playback_ready}>Playback ready (checked by the server)</Check>
        </ul>
        {c.status === "draft" && (
          <div className="mt-3 grid sm:grid-cols-3 gap-2">
            {!c.confirmations.sponsor_payment && <div className="flex gap-2 sm:col-span-3"><input placeholder="Payment reference" value={conf.payRef} onChange={(e) => setConf({ ...conf, payRef: e.target.value })} className={field} data-testid="conf-pay-ref" /><input placeholder={`Amount (${cur})`} type="number" value={conf.payAmt} onChange={(e) => setConf({ ...conf, payAmt: e.target.value })} className={`${field} w-40`} data-testid="conf-pay-amt" /><button className={btn} data-testid="conf-pay" onClick={() => confirm("sponsor_payment", { reference: conf.payRef, amount: Number(conf.payAmt) })}>Confirm</button></div>}
            {!c.confirmations.distribution_permission && <div className="flex gap-2 sm:col-span-3"><input placeholder="Agreement / permission reference" value={conf.permRef} onChange={(e) => setConf({ ...conf, permRef: e.target.value })} className={field} data-testid="conf-perm-ref" /><button className={btn} data-testid="conf-perm" onClick={() => confirm("distribution_permission", { reference: conf.permRef })}>Confirm</button></div>}
            {!c.confirmations.playback_ready && <button className={btn} data-testid="conf-play" onClick={() => confirm("playback_ready", {})}>Check playback and confirm</button>}
          </div>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          {c.status === "draft" && <button className="rounded-full px-5 py-2 text-sm font-medium bg-[#34C759] text-black disabled:opacity-40" disabled={!c.ready_to_open} data-testid="c-open" onClick={() => act(() => api.post(`/admin/campaigns/${id}/open`), "Offer is open")}>Open offer</button>}
          {c.status === "open" && <button className={btn} data-testid="c-pause" onClick={() => act(() => api.post(`/admin/campaigns/${id}/pause`), "New claims paused")}>Pause new claims</button>}
          {c.status === "paused" && <button className={btn} onClick={() => act(() => api.post(`/admin/campaigns/${id}/resume`), "Resumed")}>Resume</button>}
          {c.status !== "closed" && <button className={btn} data-testid="c-close" onClick={() => window.confirm("Close the campaign? No new claims; claimed passes keep their access.") && act(() => api.post(`/admin/campaigns/${id}/close`), "Closed")}>Close campaign</button>}
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <div className={card} data-testid="c-report">
          <h4 className="font-medium mb-2">Report</h4>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            <dt className="text-gray-400">Passes available / claimed / left</dt><dd>{rep.passes.available} / <b data-testid="r-claimed">{rep.passes.claimed}</b> / {rep.passes.remaining}</dd>
            <dt className="text-gray-400">Reversed · failed attempts</dt><dd>{rep.passes.reversed} · {rep.passes.failed_attempts}</dd>
            <dt className="text-gray-400">Fans who earned the bonus</dt><dd>{rep.fans_who_earned}</dd>
            <dt className="text-gray-400">Unique replay viewers</dt><dd data-testid="r-viewers">{rep.viewing.unique_viewers} ({Math.round(rep.claim_to_view_rate * 100)}% of claims)</dd>
            <dt className="text-gray-400">Repeat viewers ({rep.report_window_days} days)</dt><dd>{rep.viewing.repeat_viewers}</dd>
            <dt className="text-gray-400">Watch minutes</dt><dd>{rep.viewing.watch_minutes}</dd>
            <dt className="text-gray-400 pt-2">Sponsor payment</dt><dd className="pt-2">{money(m.sponsor_payment_received, cur)} of {money(m.sponsor_payment_agreed, cur)}</dd>
            <dt className="text-gray-400">Organizer settlement</dt><dd>{money(m.organizer_paid, cur)} of {money(m.organizer_compensation_agreed, cur)}</dd>
            <dt className="text-gray-400">Direct costs</dt><dd>{money(m.direct_costs_total, cur)}</dd>
            <dt className="text-gray-400">Contribution after direct costs</dt><dd data-testid="r-contribution" className={m.contribution_after_direct_costs >= 0 ? "text-[#34C759]" : "text-[#FF8A82]"}>{money(m.contribution_after_direct_costs, cur)} (fee {money(m.lono_fee_agreed, cur)})</dd>
          </dl>
          <div className="mt-3 text-sm" data-testid="r-reconcile">
            Reconciliation: {r.all_ok ? <span className="text-[#34C759]">all records agree</span> : <span className="text-[#FFB000]">check below</span>}
            <ul className="mt-1 text-xs text-gray-400 space-y-0.5">
              <li>{r.points_ok ? "✓" : "✗"} Points: {r.points_net} net debited = {r.points_expected_from_active_passes} for {r.active_passes} active passes</li>
              <li>{r.inventory_ok ? "✓" : "✗"} Inventory counter {r.inventory_counter} = active {r.active_passes} + reversed kept {r.reversed_passes_not_returned}</li>
              <li>{r.earnings_ok ? "✓" : "✗"} Earning bonus: {r.campaign_points_awarded} awarded = {r.campaign_points_in_ledger} in the ledger</li>
              <li>{r.cash_ok ? "✓" : "✗"} Cash: sponsor payment received; organizer paid as agreed (or not yet)</li>
              {r.pending_claims > 0 && <li>{r.pending_claims} claim(s) still processing</li>}
            </ul>
          </div>
          <button className={`${btn} mt-3`} onClick={exportCsv} data-testid="sponsor-csv"><Download className="w-4 h-4" /> Sponsor report (CSV)</button>
        </div>

        <div className="space-y-4">
          <div className={card}>
            <h4 className="font-medium mb-2">Settlement (recorded, paid outside LoNo)</h4>
            <div className="grid gap-2">
              <div className="flex gap-2"><input placeholder={c.settlement.sponsor_invoice_ref || "Sponsor invoice reference"} value={st.invoice} onChange={(e) => setSt({ ...st, invoice: e.target.value })} className={field} data-testid="s-invoice" /><button className={btn} onClick={() => act(() => api.post(`/admin/campaigns/${id}/settlement`, { sponsor_invoice_ref: st.invoice }), "Saved")}>Save</button></div>
              <div className="flex gap-2"><input placeholder={`Organizer paid (${cur})`} type="number" value={st.orgAmt} onChange={(e) => setSt({ ...st, orgAmt: e.target.value })} className={`${field} w-40`} data-testid="s-org-amt" /><input placeholder="Payment reference" value={st.orgRef} onChange={(e) => setSt({ ...st, orgRef: e.target.value })} className={field} data-testid="s-org-ref" /><button className={btn} data-testid="s-org-save" onClick={() => act(() => api.post(`/admin/campaigns/${id}/settlement`, { organizer_paid_amount: Number(st.orgAmt), organizer_paid_reference: st.orgRef }), "Organizer payment recorded")}>Save</button></div>
              {c.settlement.organizer_paid && <div className="text-xs text-gray-400">Organizer paid {money(c.settlement.organizer_paid.amount, cur)} · ref {c.settlement.organizer_paid.reference} · {fmt(c.settlement.organizer_paid.at)}</div>}
            </div>
          </div>
          <div className={card}>
            <h4 className="font-medium mb-2">Did they book again?</h4>
            <div className="grid grid-cols-2 gap-2">
              {["sponsor", "organizer"].map((who) => (
                <label key={who} className="text-sm"><span className="text-xs text-gray-400 capitalize">{who}</span>
                  <select value={c.rebooking[who]} onChange={(e) => act(() => api.put(`/admin/campaigns/${id}/rebooking`, { ...c.rebooking, [who]: e.target.value, notes: c.rebooking.notes || "" }), "Saved")} className={`${field} mt-1`} data-testid={`rebook-${who}`}>
                    {[["unknown", "Not yet known"], ["in_talks", "In talks"], ["yes", "Booked another campaign"], ["no", "Declined"]].map(([v, l]) => <option key={v} value={v} className="bg-[#121212]">{l}</option>)}
                  </select></label>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className={card}>
        <h4 className="font-medium mb-2">Claims</h4>
        <div className="overflow-x-auto"><table className="w-full text-sm">
          <thead className="text-xs text-gray-400 text-left"><tr><th className="py-1">Fan</th><th>Status</th><th>Claimed</th><th>Access until</th><th /></tr></thead>
          <tbody>
            {claims.map((cl) => (
              <tr key={cl.id} className="border-t border-white/5" data-testid={`claim-row-${cl.id}`}>
                <td className="py-1.5">{cl.fan_name} <span className="text-xs text-gray-500">{cl.fan_email}</span></td>
                <td>{cl.status}{cl.failure ? ` (${cl.failure})` : ""}{cl.status === "reversed" && cl.pass_returned ? " · pass returned" : ""}</td>
                <td>{fmt(cl.claimed_at)}</td><td>{fmt(cl.expires_at)}</td>
                <td className="text-right">{cl.status === "active" && <button className="text-xs text-[#FF8A82] inline-flex items-center gap-1" data-testid={`reverse-${cl.id}`}
                  onClick={() => { const reason = window.prompt("Reason for reversing this redemption"); if (!reason) return; const back = window.confirm("Return the pass to inventory if the offer is still open?"); act(() => api.post(`/admin/campaigns/${id}/claims/${cl.id}/reverse`, { reason, return_pass: back }), "Points restored"); }}><XCircle className="w-3.5 h-3.5" /> Reverse</button>}</td>
              </tr>
            ))}
            {claims.length === 0 && <tr><td colSpan={5} className="py-3 text-gray-500">No claims yet.</td></tr>}
          </tbody>
        </table></div>
      </div>

      <div className={card}>
        <h4 className="font-medium mb-2">Changes</h4>
        <ol className="text-xs text-gray-400 space-y-1" data-testid="c-history">
          {[...c.history].reverse().map((h, i) => <li key={i}><span className="text-gray-500 tabular-nums">{fmt(h.at)}</span> · {h.by_name} · {h.action.replace(/_/g, " ")}{h.details?.reference ? ` (${h.details.reference})` : ""}{h.details?.reason ? `: ${h.details.reason}` : ""}</li>)}
        </ol>
      </div>
    </div>
  );
}

export default function Campaigns() {
  const [items, setItems] = useState(null);
  const [view, setView] = useState({ mode: "list" });
  const load = () => api.get("/admin/campaigns").then(({ data }) => setItems(data));
  useEffect(() => { load(); }, []);
  if (view.mode === "new") return <NewCampaign onCancel={() => setView({ mode: "list" })} onCreated={(id) => { load(); setView({ mode: "detail", id }); }} />;
  if (view.mode === "detail") return <Detail id={view.id} onBack={() => { load(); setView({ mode: "list" }); }} />;
  return (
    <div data-testid="campaigns-tab">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm text-gray-400">Sponsored replay-pass campaigns. Offers open only after payment, permission and playback are confirmed.</p>
        <button className="bg-[#FF3B30] rounded-full px-4 py-2 text-sm font-medium inline-flex items-center gap-1.5" onClick={() => setView({ mode: "new" })} data-testid="c-new"><Plus className="w-4 h-4" /> New campaign</button>
      </div>
      <ul className="divide-y divide-white/10 border-y border-white/10">
        {(items || []).map((c) => (
          <li key={c.id}><button className="w-full text-left py-3 flex flex-wrap items-center gap-3 hover:text-[#FFB000]" onClick={() => setView({ mode: "detail", id: c.id })} data-testid={`c-row-${c.id}`}>
            <span className="font-medium">{c.title}</span><span className="text-xs text-gray-500">{c.organizer_name} · {c.sponsor_name}</span>
            <span className="ml-auto text-xs text-gray-400">{c.claimed}/{c.inventory_total} claimed</span><span className={`text-xs px-2 py-0.5 rounded-full ${STATUS[c.status]}`}>{c.status}</span>
          </button></li>
        ))}
        {items && items.length === 0 && <li className="py-6 text-gray-500 text-sm">No campaigns yet.</li>}
      </ul>
    </div>
  );
}
