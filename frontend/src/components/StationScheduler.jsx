import { useState } from "react";
import { resolveMedia } from "@/lib/api";

const box = "rounded-2xl border border-white/10 bg-[#121212] p-5 space-y-4";
const btn = "rounded-full border border-white/15 px-4 py-2 text-sm hover:bg-white/10";
const localDay = date => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`;
const time = date => date.toLocaleTimeString(undefined,{hour:"2-digit",minute:"2-digit"});

export function ProgrammeLibrary({ station, media, onScheduleMedia }) {
  const [search,setSearch] = useState("");
  const [preview,setPreview] = useState(null);
  const selected = media.find(f=>f.id===preview);
  const items = media.filter(f=>f.name.toLowerCase().includes(search.toLowerCase()));
  return <section className={box}>
    <div><h2 className="font-display text-xl">Programme media library</h2><p className="text-sm text-gray-400">{media.length} eligible {station.kind==="live_tv"?"video":"audio"} uploads. Use authorized media only.</p></div>
    <input aria-label="Search programme media" placeholder="Search media by filename" className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2" value={search} onChange={e=>setSearch(e.target.value)}/>
    {selected && <div className="space-y-2"><p className="text-sm">Preview: {selected.name}</p>{station.kind==="live_tv"?<video key={selected.id} className="max-h-64 w-full" controls preload="metadata" src={resolveMedia(selected.url)}/>:<audio key={selected.id} className="w-full" controls preload="metadata" src={resolveMedia(selected.url)}/>}<button className={btn} onClick={()=>setPreview(null)}>Close preview</button></div>}
    {!items.length?<p className="text-sm text-gray-400">No matching media. Upload programme media above.</p>:<div className="max-h-72 overflow-auto divide-y divide-white/10">{items.map(f=><article key={f.id} className="py-3 flex flex-wrap items-center gap-2"><div className="flex-1 min-w-0"><p className="break-all font-medium">{f.name}</p><p className="text-xs text-gray-400">{f.content_type}{Number.isFinite(f.size)?` · ${(f.size/1048576).toFixed(2)} MB`:""}{station.fallback_file_id===f.id?" · Continuous fallback":""}</p></div><button className={btn} onClick={()=>setPreview(f.id)}>Preview</button><button className={btn} onClick={()=>onScheduleMedia(f)}>Schedule media</button></article>)}</div>}
  </section>;
}

export function DayCalendar({ station }) {
  const [day,setDay] = useState(()=>localDay(new Date()));
  const start = new Date(`${day}T00:00:00`);
  const end = new Date(start); end.setDate(end.getDate()+1);
  const duration = end-start;
  const slots = (station.programmes||[]).filter(p=>new Date(p.end)>start&&new Date(p.start)<end);
  const move = offset=>{const next=new Date(start);next.setDate(next.getDate()+offset);setDay(localDay(next));};
  return <section className={box}><div className="flex flex-wrap gap-2 items-center"><h2 className="font-display text-xl flex-1">24-hour broadcast calendar</h2><button className={btn} onClick={()=>move(-1)}>Previous day</button><input aria-label="Calendar date" type="date" value={day} onChange={e=>e.target.value&&setDay(e.target.value)} className="bg-white/5 border border-white/10 rounded-lg p-2"/><button className={btn} onClick={()=>move(1)}>Next day</button></div>
    <p className="text-xs text-gray-400">Local time · Red: prerecorded · Gold: planned live · Unscheduled time uses your configured fallback if enabled.</p>
    <div className="relative h-16 rounded-lg bg-white/5 overflow-hidden" aria-label="Daily programme timeline">{slots.map(p=><div key={p.id} title={`${p.title} · ${time(new Date(p.start))} – ${time(new Date(p.end))}`} className={`absolute top-0 h-full border-r border-black/50 overflow-hidden px-1 text-xs flex items-center ${p.format==="live"?"bg-amber-700":"bg-red-700"}`} style={{left:`${100*(Math.max(+start,+new Date(p.start))-start)/duration}%`,width:`${100*(Math.min(+end,+new Date(p.end))-Math.max(+start,+new Date(p.start)))/duration}%`}}>{p.title}</div>)}</div>
    <div className="flex justify-between text-xs text-gray-400"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div>
    {!slots.length?<p className="text-sm text-gray-400">No upcoming slots on this date.</p>:<ul className="space-y-2">{slots.map(p=><li key={p.id} className="text-sm"><span className="text-gray-400">{time(new Date(p.start))} – {time(new Date(p.end))}</span> · {p.title}{p.repeat&&` · ${p.repeat}`}</li>)}</ul>}
  </section>;
}
