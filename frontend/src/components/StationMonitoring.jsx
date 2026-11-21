import { useCallback, useEffect, useState } from "react";
import { api, errorText } from "@/lib/api";

const labels={media_available:"Media available",media_missing:"Media missing",storage_unreachable:"Storage unreachable",live_session:"Live session active",off_air:"Off air",unknown:"Unknown"};
export default function StationMonitoring({ station }) {
  const [data,setData]=useState(null);
  const [error,setError]=useState("");
  const load=useCallback(async()=>{try{const r=await api.get(`/creator/stations/${station.id}/monitoring`);setData(r.data);setError("");}catch(e){setError(errorText(e));}},[station.id]);
  useEffect(()=>{load();const timer=setInterval(load,30000);return ()=>clearInterval(timer);},[load]);
  return <section className="rounded-2xl border border-white/10 bg-[#121212] p-5 space-y-4">
    <div className="flex items-center gap-3"><h2 className="font-display text-xl flex-1">Broadcast reliability & monitoring</h2><button className="rounded-full border border-white/15 px-3 py-2 text-sm" onClick={load}>Refresh monitoring</button></div>
    {error&&<p role="alert" className="text-red-300">{error}</p>}
    {!data?<p className="text-gray-400">Loading monitoring…</p>:<><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[["Current source",labels[data.status]||data.status],["Recent signed-in accounts",data.recent_signed_in_accounts],["Signed-in accounts today",data.today_signed_in_accounts],["Commercial samples · 24h",data.commercial_samples_24h]].map(([label,value])=><div key={label} className="rounded-lg bg-white/5 p-3"><p className="text-xs text-gray-400">{label}</p><p className="text-xl font-semibold mt-1">{value}</p></div>)}</div>
    <p className="text-sm text-gray-300">Current: {data.playout?.title||"No configured source"} · Checked {new Date(data.as_of).toLocaleString()}</p><p className="text-xs text-gray-400">Storage checks verify object availability, not successful playback. Audience counts reflect signed-in accounts reporting playable media, not total or audited viewers. Commercial samples are clock observations, not billable impressions or verified airtime. History begins after this feature is deployed.</p>
    <h3 className="font-semibold">Recent source observations</h3>{!data.samples.length?<p className="text-sm text-gray-400">Awaiting the first monitoring sample.</p>:<div className="max-h-80 overflow-auto"><table className="w-full text-sm text-left"><thead><tr className="text-gray-400"><th className="p-2">Observed</th><th className="p-2">Source</th><th className="p-2">Type</th><th className="p-2">Status</th></tr></thead><tbody>{data.samples.map(s=><tr key={s.at} className="border-t border-white/10"><td className="p-2">{new Date(s.at).toLocaleString()}</td><td className="p-2">{s.title||"—"}</td><td className="p-2">{s.item_kind||s.mode}</td><td className="p-2">{labels[s.status]||s.status}</td></tr>)}</tbody></table></div>}</>}
  </section>;
}
