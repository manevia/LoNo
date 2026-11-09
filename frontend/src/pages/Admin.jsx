import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Download, Loader2, ShieldCheck } from "lucide-react";
import Campaigns from "@/components/admin/Campaigns";
import { api, errorText } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Stars } from "@/components/Stars";

const TABS = [["overview", "Overview"], ["campaigns", "Campaigns"], ["reports", "Reports"], ["users", "Users"], ["courses", "Courses"], ["audit", "Audit log"]];
const card = "rounded-2xl bg-[#121212] border border-white/10";
const btn = "text-xs rounded-full px-3 py-1.5 border transition disabled:opacity-40";
const ACTION_LABELS = {
  account_created: "Account created", account_deleted: "Account deleted", data_export: "Data downloaded",
  password_changed: "Password changed", password_set: "Password set", terms_accepted: "Terms accepted",
  review_hidden: "Review hidden", review_report_dismissed: "Report dismissed", review_restored: "Review restored",
  user_suspended: "User suspended", user_reinstated: "User reinstated", course_unpublished: "Course unpublished",
  audit_exported: "Audit log exported",
};
const fmt = (iso) => new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
const ask = (q) => { const r = window.prompt(q); return r && r.trim().length >= 3 ? r.trim() : null; };

function Overview() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/admin/overview").then(({ data }) => setD(data)); }, []);
  if (!d) return <Loader2 className="w-6 h-6 animate-spin text-gray-500" />;
  const stats = [
    ["Accounts", d.users], ["Watching today", d.active_today], ["Suspended", d.suspended],
    ["Titles", d.content], ["Published courses", d.courses_published], ["Draft courses", d.courses_draft],
    ["Certificates issued", d.certificates], ["Open reports", d.open_reports, d.open_reports > 0],
    ["Data downloads (30 days)", d.data_exports_30d], ["Account deletions (30 days)", d.deletions_30d],
  ];
  return (
    <dl className="grid grid-cols-2 md:grid-cols-5 gap-3">
      {stats.map(([k, v, warn]) => (
        <div key={k} className={`${card} p-4`}>
          <dt className="text-xs text-gray-400">{k}</dt>
          <dd className={`mt-1 font-display text-2xl tabular-nums ${warn ? "text-[#FFB000]" : ""}`}>{v.toLocaleString()}</dd>
        </div>
      ))}
    </dl>
  );
}

function Reports() {
  const [status, setStatus] = useState("open");
  const [items, setItems] = useState(null);
  const load = useCallback(() => api.get("/admin/reports", { params: { status } }).then(({ data }) => setItems(data)), [status]);
  useEffect(() => { setItems(null); load(); }, [load]);
  const act = async (r, action) => {
    try { await api.post(`/admin/reports/${r.id}/resolve`, { action }); toast.success(action === "hide" ? "Review hidden" : "Report dismissed"); load(); }
    catch (e) { toast.error(errorText(e)); }
  };
  const restore = async (r) => {
    try { await api.post(`/admin/reviews/${r.target_id}/restore`); toast.success("Review restored"); load(); }
    catch (e) { toast.error(errorText(e)); }
  };
  return (
    <div>
      <div role="group" aria-label="Report status" className="flex gap-2 mb-4 text-sm">
        {["open", "resolved", "all"].map((s) => (
          <button key={s} onClick={() => setStatus(s)} aria-pressed={status === s}
            className={`px-3 py-1.5 rounded-full capitalize ${status === s ? "bg-white text-black" : "bg-white/5 text-gray-300 hover:bg-white/10"}`}>{s}</button>
        ))}
      </div>
      {!items ? <Loader2 className="w-6 h-6 animate-spin text-gray-500" /> : items.length === 0 ? (
        <p className="text-gray-400">{status === "open" ? "No open reports. Nothing needs your attention." : "No reports here."}</p>
      ) : (
        <ul className="space-y-3">
          {items.map((r) => (
            <li key={r.id} data-testid="report-item" className={`${card} p-4`}>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-400">
                <span>Review on <span className="text-gray-200">{r.course_title || "a removed course"}</span></span>
                <span>Reported by {r.reporter_name} / {fmt(r.created_at)}</span>
                {r.status !== "open" && <span className="text-gray-300">Resolved: {r.resolution === "hide" ? "hidden" : "dismissed"}</span>}
              </div>
              <p className="mt-2 text-sm"><span className="text-gray-500">Reason:</span> {r.reason}</p>
              {r.review ? (
                <blockquote className="mt-3 pl-3 border-l-2 border-white/15 text-sm text-gray-300">
                  <div className="flex items-center gap-2 text-xs text-gray-400 mb-1"><Stars value={r.review.rating} size="w-3 h-3" /> {r.review.user_name}{r.review.hidden && " / hidden"}</div>
                  {r.review.text || <span className="text-gray-500">(no text)</span>}
                </blockquote>
              ) : <p className="mt-3 text-sm text-gray-500">The review was deleted by its author.</p>}
              <div className="mt-3 flex gap-2">
                {r.status === "open" && r.review && <>
                  <button onClick={() => act(r, "hide")} className={`${btn} border-[#FF3B30]/40 text-[#FF8A82] hover:bg-[#FF3B30]/10`}>Hide review</button>
                  <button onClick={() => act(r, "dismiss")} className={`${btn} border-white/15 text-gray-300 hover:bg-white/10`}>Dismiss</button>
                </>}
                {r.review?.hidden && <button onClick={() => restore(r)} className={`${btn} border-white/15 text-gray-300 hover:bg-white/10`}>Restore review</button>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Users() {
  const [q, setQ] = useState("");
  const [items, setItems] = useState(null);
  const load = useCallback((term) => api.get("/admin/users", { params: { q: term } }).then(({ data }) => setItems(data)), []);
  useEffect(() => { load(""); }, [load]);
  const toggle = async (u) => {
    try {
      if (u.suspended) await api.post(`/admin/users/${u.id}/reinstate`);
      else {
        const reason = ask(`Why are you suspending ${u.name}? (recorded in the audit log)`);
        if (!reason) return;
        await api.post(`/admin/users/${u.id}/suspend`, { reason });
      }
      load(q);
    } catch (e) { toast.error(errorText(e)); }
  };
  return (
    <div>
      <form onSubmit={(e) => { e.preventDefault(); load(q); }} className="mb-4 flex gap-2 max-w-md">
        <input aria-label="Search users" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name or email"
          className="flex-1 bg-white/5 border border-white/10 rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#FFB000]/40" />
        <button className="bg-white/10 hover:bg-white/15 rounded-full px-4 text-sm">Search</button>
      </form>
      {!items ? <Loader2 className="w-6 h-6 animate-spin text-gray-500" /> : (
        <div className="overflow-x-auto"><table className="w-full text-sm">
          <thead className="text-left text-xs text-gray-400"><tr>
            <th className="py-2 pr-4 font-normal">Name</th><th className="py-2 pr-4 font-normal">Email</th>
            <th className="py-2 pr-4 font-normal">Joined</th><th className="py-2 pr-4 font-normal text-right">Balance</th><th className="py-2 font-normal" />
          </tr></thead>
          <tbody className="divide-y divide-white/10">
            {items.map((u) => (
              <tr key={u.id}>
                <td className="py-2.5 pr-4 whitespace-nowrap">{u.name}{u.is_admin && <span className="ml-2 text-[10px] text-[#FFB000]">ADMIN</span>}
                  {u.suspended && <span className="ml-2 text-[10px] text-[#FF8A82]">SUSPENDED</span>}</td>
                <td className="py-2.5 pr-4 text-gray-400">{u.email}</td>
                <td className="py-2.5 pr-4 text-gray-400 whitespace-nowrap">{new Date(u.created_at).toLocaleDateString()}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums">{u.wallet?.lono_balance?.toFixed(0)}</td>
                <td className="py-2.5 text-right">{!u.is_admin && (
                  <button onClick={() => toggle(u)} className={`${btn} ${u.suspended ? "border-white/15 text-gray-300" : "border-[#FF3B30]/40 text-[#FF8A82]"}`}>
                    {u.suspended ? "Reinstate" : "Suspend"}
                  </button>)}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
    </div>
  );
}

function Courses() {
  const [items, setItems] = useState(null);
  const load = () => api.get("/admin/courses").then(({ data }) => setItems(data));
  useEffect(() => { load(); }, []);
  const unpublish = async (c) => {
    const reason = ask(`Why are you unpublishing “${c.title}”? The creator sees this note.`);
    if (!reason) return;
    try { await api.post(`/admin/courses/${c.id}/unpublish`, { reason }); toast.success("Course unpublished"); load(); }
    catch (e) { toast.error(errorText(e)); }
  };
  if (!items) return <Loader2 className="w-6 h-6 animate-spin text-gray-500" />;
  return (
    <ul className="divide-y divide-white/10 border-y border-white/10">
      {items.map((c) => (
        <li key={c.id} className="py-3 flex flex-wrap items-center gap-3">
          <div className="min-w-0 flex-1">
            <div className="font-medium truncate">{c.status === "published" ? <Link to={`/learn/${c.id}`} className="hover:underline">{c.title}</Link> : c.title}</div>
            <div className="text-xs text-gray-400">by {c.owner_name} / {c.enrolled || 0} enrolled / {c.certificates_issued || 0} passed
              {c.rating_count > 0 && ` / ★ ${c.rating_avg.toFixed(1)}`}{c.moderation_note && ` / note: ${c.moderation_note}`}</div>
          </div>
          <span className={`text-xs px-2 py-0.5 rounded-full border capitalize ${c.status === "published" ? "text-[#34C759] border-[#34C759]/30" : "text-gray-400 border-white/15"}`}>{c.status}</span>
          {c.status === "published" && <button onClick={() => unpublish(c)} className={`${btn} border-[#FF3B30]/40 text-[#FF8A82]`}>Unpublish</button>}
        </li>
      ))}
    </ul>
  );
}

function Audit() {
  const [action, setAction] = useState("");
  const [days, setDays] = useState(30);
  const [d, setD] = useState(null);
  useEffect(() => { setD(null); api.get("/admin/audit", { params: { action, days } }).then(({ data }) => setD(data)); }, [action, days]);
  const download = async () => {
    const { data } = await api.get("/admin/audit.csv", { params: { action, days }, responseType: "blob" });
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(data), download: `lono-audit-${new Date().toISOString().slice(0, 10)}.csv` });
    document.body.appendChild(a); a.click(); a.remove();
  };
  const sel = "bg-white/5 border border-white/10 rounded-full px-3 py-1.5 text-sm";
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select aria-label="Action" value={action} onChange={(e) => setAction(e.target.value)} className={sel}>
          <option value="">All actions</option>
          {(d?.actions || []).map((a) => <option key={a} value={a}>{ACTION_LABELS[a] || a}</option>)}
        </select>
        <select aria-label="Period" value={days} onChange={(e) => setDays(Number(e.target.value))} className={sel}>
          {[7, 30, 90, 365].map((n) => <option key={n} value={n}>Last {n} days</option>)}
        </select>
        <button data-testid="audit-csv" onClick={download} className="ml-auto inline-flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full px-4 py-1.5 text-sm">
          <Download className="w-4 h-4" /> Download CSV
        </button>
      </div>
      {!d ? <Loader2 className="w-6 h-6 animate-spin text-gray-500" /> : (
        <>
          <p className="text-xs text-gray-500 mb-2">{d.total.toLocaleString()} entries{d.total > d.items.length && `, showing the newest ${d.items.length}`}. Deleted accounts appear only as an ID and an email fingerprint.</p>
          <div className="overflow-x-auto"><table className="w-full text-sm">
            <thead className="text-left text-xs text-gray-400"><tr>
              <th className="py-2 pr-4 font-normal">When</th><th className="py-2 pr-4 font-normal">What</th>
              <th className="py-2 pr-4 font-normal">Who</th><th className="py-2 font-normal">Details</th>
            </tr></thead>
            <tbody className="divide-y divide-white/10">
              {d.items.map((e) => (
                <tr key={e.id} data-testid="audit-row">
                  <td className="py-2 pr-4 text-gray-400 whitespace-nowrap">{fmt(e.at)}</td>
                  <td className="py-2 pr-4 whitespace-nowrap">{ACTION_LABELS[e.action] || e.action}</td>
                  <td className="py-2 pr-4 text-gray-300 whitespace-nowrap">{e.actor_name || <span className="text-gray-500">{e.actor_id ? `${e.actor_id.slice(0, 8)}…` : "system"}</span>}</td>
                  <td className="py-2 text-gray-400 text-xs">
                    {Object.entries(e.details || {}).filter(([, v]) => v).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" / ")}
                    {e.subject_email_hash && <span title={e.subject_email_hash}>email fingerprint {e.subject_email_hash.slice(0, 10)}…</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </>
      )}
    </div>
  );
}

export default function Admin() {
  const { user } = useAuth();
  const [tab, setTab] = useState(() => (window.location.hash.slice(1) || "overview"));
  useEffect(() => { window.history.replaceState(null, "", `#${tab}`); }, [tab]);

  if (!user?.is_admin) return (
    <div className="min-h-[60vh] grid place-items-center text-center px-6">
      <div><ShieldCheck className="w-8 h-8 mx-auto text-gray-500" /><p className="mt-3 text-gray-300">This area is for LoNo admins.</p>
        <Link to="/" className="mt-3 inline-block text-[#FF3B30]">Back to Home</Link></div>
    </div>
  );
  const Panel = { overview: Overview, campaigns: Campaigns, reports: Reports, users: Users, courses: Courses, audit: Audit }[tab] || Overview;

  return (
    <div data-testid="admin-page" className="max-w-6xl mx-auto px-4 md:px-8 pt-10 pb-32">
      <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tight">Admin</h1>
      <div role="tablist" aria-label="Admin sections" className="mt-6 mb-8 flex gap-1 overflow-x-auto border-b border-white/10">
        {TABS.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} data-testid={`admin-tab-${k}`}
            className={`px-4 py-2.5 text-sm whitespace-nowrap border-b-2 -mb-px transition ${tab === k ? "border-[#FF3B30] text-white" : "border-transparent text-gray-400 hover:text-white"}`}>
            {label}
          </button>
        ))}
      </div>
      <div role="tabpanel"><Panel /></div>
    </div>
  );
}
