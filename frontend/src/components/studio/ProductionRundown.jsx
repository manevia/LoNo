import { useState } from "react";
import { toast } from "sonner";
import { api, errorText } from "@/lib/api";

const field="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm";
const btn="rounded-full border border-white/15 px-3 py-2 text-xs disabled:opacity-40";
export default function ProductionRundown({room,refresh}){
  const [items,setItems]=useState(room.rundown||[]),[revision,setRevision]=useState(room.rundown_revision||0);
  const [title,setTitle]=useState(""),[notes,setNotes]=useState(""),[seconds,setSeconds]=useState(60);
  const [headline,setHeadline]=useState(room.preview.headline||""),[ticker,setTicker]=useState(room.preview.ticker||""),[accent,setAccent]=useState(room.preview.accent||"red"),[transition,setTransition]=useState(room.preview.transition||"cut");
  const [dirty,setDirty]=useState(false),[busy,setBusy]=useState(false);
  const style=()=>({ ...room.preview,headline,ticker,accent,transition });
  const request=async(fn)=>{setBusy(true);try{await fn();await refresh();}catch(e){toast.error(errorText(e));}finally{setBusy(false);}};
  const add=()=>{if(!title.trim()||!Number.isInteger(seconds)||seconds<1||seconds>86400||items.length>=50)return;setItems(old=>[...old,{title:title.trim(),notes,planned_seconds:seconds,scene:style()}]);setTitle("");setNotes("");setDirty(true);};
  const move=(i,d)=>{setItems(old=>{const next=[...old];[next[i],next[i+d]]=[next[i+d],next[i]];return next;});setDirty(true);};
  const reload=()=>{setItems(room.rundown||[]);setRevision(room.rundown_revision||0);setDirty(false);};
  const save=()=>request(async()=>{const {data}=await api.put(`/rooms/${room.id}/rundown`,{revision,items});setRevision(data.rundown_revision);setItems(data.rundown);setDirty(false);toast.success("Rundown saved");});
  return <section className="rounded-2xl bg-[#121212] border border-white/10 p-4 space-y-4">
    <h2 className="font-display text-xl">Advanced production & rundown</h2><p className="text-xs text-gray-400">Style the current preview. Save it as a reusable rundown item, including scene, sources and graphics. Cueing a saved item is private until TAKE.</p>
    <div className="grid sm:grid-cols-2 gap-3"><label>Transition<select className={field} value={transition} onChange={e=>setTransition(e.target.value)}><option value="cut">Cut</option><option value="dissolve">Dissolve · 600 ms</option><option value="wipe">Wipe · 600 ms</option></select></label><label>Graphics theme<select className={field} value={accent} onChange={e=>setAccent(e.target.value)}><option value="red">LoNo red</option><option value="blue">News blue</option><option value="gold">Gold</option></select></label><label>Headline<input className={field} maxLength={100} value={headline} onChange={e=>setHeadline(e.target.value)}/></label><label>Scrolling ticker<input className={field} maxLength={160} value={ticker} onChange={e=>setTicker(e.target.value)}/></label></div>
    <button className={btn} disabled={busy} onClick={()=>request(async()=>{await api.put(`/rooms/${room.id}/preview`,style());toast.success("Preview graphics updated");})}>Apply graphics to preview</button>
    <div className="grid sm:grid-cols-2 gap-2"><label>Rundown item name<input className={field} value={title} maxLength={100} onChange={e=>setTitle(e.target.value)}/></label><label>Planned duration (seconds)<input className={field} type="number" min={1} max={86400} value={seconds} onChange={e=>setSeconds(Number(e.target.value))}/></label></div><label className="block">Private producer notes<textarea className={field} maxLength={500} value={notes} onChange={e=>setNotes(e.target.value)}/></label><button className={btn} disabled={!title.trim()||items.length>=50} onClick={add}>Add preview to rundown</button>
    <p className="text-xs text-gray-400">{items.length} items · {Math.round(items.reduce((sum,x)=>sum+x.planned_seconds,0)/60*10)/10} planned minutes. Timing is advisory, not automatic.</p>
    {items.map((item,i)=><article key={i} className="border border-white/10 rounded-lg p-3 space-y-2"><p className="font-medium">{i+1}. {item.title} · {item.planned_seconds}s</p><p className="text-xs text-gray-400">{item.scene.scene} · {item.scene.transition||"cut"}{item.notes&&` · ${item.notes}`}</p><div className="flex flex-wrap gap-2"><button className={btn} disabled={dirty||busy||revision!==(room.rundown_revision||0)} onClick={()=>request(()=>api.post(`/rooms/${room.id}/rundown/${i}/cue?revision=${revision}`))}>Cue item {i+1}</button><button className={btn} disabled={!i} onClick={()=>move(i,-1)}>Move up</button><button className={btn} disabled={i===items.length-1} onClick={()=>move(i,1)}>Move down</button><button className={btn} onClick={()=>{setItems(old=>old.filter((_,j)=>j!==i));setDirty(true);}}>Remove item</button></div></article>)}
    {revision!==(room.rundown_revision||0)&&<p className="text-amber-300 text-xs">A newer rundown is available. Reload it before saving.</p>}
    <div className="flex gap-2"><button className="rounded-full bg-[#FF3B30] px-4 py-2 text-sm disabled:opacity-40" disabled={!dirty||busy} onClick={save}>Save rundown</button><button className={btn} onClick={reload}>Reload saved rundown</button></div>
  </section>;
}
