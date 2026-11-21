import { useState } from "react";
import { toast } from "sonner";
import { api, errorText } from "@/lib/api";

const button = "rounded-full border border-white/15 px-3 py-2 text-sm disabled:opacity-40";
const input = "w-full rounded-lg bg-white/5 border border-white/10 p-2 text-sm";

export default function StationPlaylist({ station, media, refresh }) {
  const [items, setItems] = useState(station.playlist_items || []);
  const [continuous, setContinuous] = useState(station.playlist_continuous || false);
  const [file, setFile] = useState("");
  const [busy, setBusy] = useState(false);
  const total = items.reduce((n,x)=>n+Number(x.duration||0),0);
  const update = (i, patch) => setItems(old=>old.map((x,j)=>i===j?{...x,...patch}:x));
  const move = (i,d) => setItems(old=>{const next=[...old];[next[i],next[i+d]]=[next[i+d],next[i]];return next;});
  const add = () => {const f=media.find(x=>x.id===file);if(!f||items.length>=50)return;setItems(old=>[...old,{file_id:f.id,title:f.name.slice(0,140),duration:60,kind:"programme"}]);setFile("");};
  const save = async e => {e.preventDefault();setBusy(true);try{await api.put(`/creator/stations/${station.id}/playlist`,{items,continuous});await refresh();toast.success("Playlist saved");}catch(e){toast.error(errorText(e));}finally{setBusy(false);}};
  return <form onSubmit={save} className="rounded-2xl border border-white/10 bg-[#121212] p-5 space-y-4">
    <h2 className="font-display text-xl">Automated playlist & commercial breaks</h2>
    <p className="text-sm text-gray-400">Arrange programmes, jingles and commercial clips in order. Each item plays for its assigned duration; shorter files loop. Use the actual clip duration for a single play. A live presenter overrides the playlist and the station clock continues.</p>
    <div className="flex flex-wrap gap-2"><select aria-label="Playlist media" className={`${input} flex-1`} value={file} onChange={e=>setFile(e.target.value)}><option value="">Select uploaded media</option>{media.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select><button type="button" className={button} disabled={!file||items.length>=50} onClick={add}>Add to playlist</button></div>
    {items.map((x,i)=><div key={i} className="rounded-lg border border-white/10 p-3 space-y-2"><div className="flex flex-wrap items-center gap-2"><span className="text-sm flex-1">{i+1}. {media.find(f=>f.id===x.file_id)?.name||"Media unavailable"}</span><button type="button" aria-label={`Move item ${i+1} up`} disabled={!i} className={button} onClick={()=>move(i,-1)}>↑</button><button type="button" aria-label={`Move item ${i+1} down`} disabled={i===items.length-1} className={button} onClick={()=>move(i,1)}>↓</button><button type="button" className={button} onClick={()=>setItems(old=>old.filter((_,j)=>i!==j))}>Remove item</button></div><div className="grid md:grid-cols-3 gap-2"><label>Title<input className={input} value={x.title} required maxLength={140} onChange={e=>update(i,{title:e.target.value})}/></label><label>Type<select className={input} value={x.kind} onChange={e=>update(i,{kind:e.target.value})}><option value="programme">Programme</option><option value="jingle">Station jingle</option><option value="commercial">Commercial break</option></select></label><label>Duration (seconds)<input type="number" min={10} max={86400} required className={input} value={x.duration} onChange={e=>update(i,{duration:Number(e.target.value)})}/></label></div></div>)}
    <p className="text-sm text-gray-400">{items.length}/50 items · {Math.floor(total/60)} min {total%60} sec per cycle</p>
    <label className="block"><input type="checkbox" checked={continuous} onChange={e=>setContinuous(e.target.checked)}/> Use this playlist continuously between scheduled programmes</label>
    <p className="text-xs text-gray-400">Save the playlist to use it in a scheduled slot. Scheduled slots retain a copy of the saved lineup. Continuous playout also requires automation to be enabled. Your existing fallback remains available if an item is removed or unavailable.</p>
    <button className="rounded-full bg-[#FF3B30] px-5 py-2 text-sm disabled:opacity-40" disabled={busy||(continuous&&!items.length)||total>86400}>Save playlist</button>
  </form>;
}
