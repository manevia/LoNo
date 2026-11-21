import {useEffect,useState} from "react";
import {api,errorText} from "@/lib/api";
import {toast} from "sonner";

const btn="rounded-full border border-white/15 px-3 py-2 text-sm disabled:opacity-40";
export const watchLink=id=>`${window.location.origin}/watch/${encodeURIComponent(id)}`;
export const embedCode=id=>`<iframe src="${window.location.origin}/api/discovery/embed/${encodeURIComponent(id)}" title="LoNo media player" width="640" height="360" loading="lazy" style="max-width:100%;border:0" allowfullscreen></iframe>`;
export async function copyDistribution(value){try{await navigator.clipboard.writeText(value);toast.success("Copied to clipboard");}catch{toast.error("Clipboard unavailable; select and copy the link manually");}}
export default function DistributionTools({channelId}){
 const [rows,setRows]=useState([]),[error,setError]=useState(""),[busy,setBusy]=useState(false);
 const load=async()=>{try{setRows((await api.get(`/discovery/creator/${channelId}`)).data);setError("");}catch(e){setError(errorText(e));}};
 useEffect(()=>{if(channelId)load();},[channelId]); // eslint-disable-line react-hooks/exhaustive-deps
 const toggle=async r=>{setBusy(true);try{await api.put(`/discovery/creator/${channelId}/${r.id}`,{enabled:!r.embeddable});await load();toast.success(r.embeddable?"Embedding disabled":"Public player enabled");}catch(e){toast.error(errorText(e));}finally{setBusy(false);}};
 return <section className="rounded-xl border border-white/10 p-4 mt-6 space-y-3"><h2 className="font-display text-2xl">Content distribution</h2><p className="text-sm text-gray-400">Share published titles by link. Enable a public website player only for media you own and have permission to distribute. Embedded playback does not earn rewards; disabling it removes the player.</p>{error&&<p role="alert" className="text-red-300">{error}</p>}{!rows.length&&!error&&<p className="text-gray-400">No published titles available.</p>}{rows.map(r=><article key={r.id} className="rounded-lg border border-white/10 p-3"><div className="flex gap-3 flex-wrap items-center"><h3 className="font-semibold flex-1">{r.title}</h3><button className={btn} onClick={()=>copyDistribution(watchLink(r.id))}>Copy watch link</button>{(r.can_embed||r.embeddable)&&<button className={btn} disabled={busy} onClick={()=>toggle(r)}>{r.embeddable?"Disable embedding":"Enable embedding"}</button>}{r.can_embed&&r.embeddable&&<button className={btn} onClick={()=>copyDistribution(embedCode(r.id))}>Copy iframe code</button>}</div>{!r.can_embed&&<p className="text-xs text-gray-400 mt-2">Embedding requires supported locally uploaded, unrestricted audio or video.</p>}{r.can_embed&&r.embeddable&&<textarea readOnly aria-label={`Embed code for ${r.title}`} className="w-full bg-white/5 rounded p-2 text-xs mt-2" value={embedCode(r.id)}/>}</article>)}</section>;
}
