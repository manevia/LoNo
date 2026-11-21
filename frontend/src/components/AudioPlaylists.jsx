import {useEffect,useState} from "react";
import {Link} from "react-router-dom";
import {api,errorText} from "@/lib/api";
import {useAuth} from "@/lib/auth";
import {toast} from "sonner";

const btn="rounded-full border border-white/15 px-3 py-2 text-sm disabled:opacity-40";
export const playlistState=(items)=>({audioQueue:items.map(x=>({id:x.id,title:x.title})),autoNext:true,autoplay:true});
export default function AudioPlaylists({item}){
 const {user}=useAuth();const [rows,setRows]=useState([]),[name,setName]=useState(""),[selected,setSelected]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState("");
 const load=async()=>{try{setRows((await api.get("/audio/playlists")).data);setError("");}catch(e){setError(errorText(e));}};
 useEffect(()=>{if(user)load();else setRows([]);},[user?.id]); // eslint-disable-line react-hooks/exhaustive-deps
 const run=async(fn)=>{setBusy(true);try{await fn();await load();toast.success("Playlist updated");}catch(e){toast.error(errorText(e));}finally{setBusy(false);}};
 const save=(row,items)=>run(()=>api.put(`/audio/playlists/${row.id}`,{name:row.name,revision:row.revision,items:items.map(i=>i.id)}));
 const add=()=>{const p=rows.find(r=>r.id===selected);if(p&&!p.items.some(i=>i.id===item.id))save(p,[...p.items,item]);};
 const move=(p,index,delta)=>{const items=[...p.items];[items[index],items[index+delta]]=[items[index+delta],items[index]];save(p,items);};
 if(!user)return <p className="text-sm text-gray-400"><Link className="text-[#FF8A82]" to="/login">Sign in</Link> to create private audio playlists.</p>;
 return <section className="space-y-3"><h3 className="font-display text-xl">{item?"Save to playlist":"My audio playlists"}</h3>{error&&<p role="alert" className="text-red-300">{error}</p>}
 <form className="flex gap-2 flex-wrap" onSubmit={e=>{e.preventDefault();run(async()=>{await api.post("/audio/playlists",{name,items:item?[item.id]:[]});setName("");});}}><input aria-label="New playlist name" className="rounded-lg px-3 py-2 bg-white/5 border border-white/10" required maxLength={100} value={name} onChange={e=>setName(e.target.value)} placeholder="New playlist name"/><button className={btn} disabled={busy}>Create private playlist</button></form>
 {item?<div className="flex gap-2 flex-wrap"><select className="rounded-lg bg-[#171717] border border-white/10 px-3" aria-label="Choose playlist" value={selected} onChange={e=>setSelected(e.target.value)}><option value="">Choose playlist</option>{rows.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><button className={btn} disabled={busy||!selected||rows.find(p=>p.id===selected)?.items.some(i=>i.id===item.id)} onClick={add}>Add audio</button></div>:rows.map(p=><article key={p.id} className="border border-white/10 rounded-xl p-3 space-y-2"><div className="flex items-center gap-2 flex-wrap"><h4 className="font-semibold flex-1">{p.name} · {p.items.length}</h4>{p.items.length>0&&<Link className="rounded-full bg-[#FF3B30] px-3 py-2 text-sm" to={`/watch/${p.items[0].id}`} state={playlistState(p.items)}>Play playlist</Link>}<button className={btn} disabled={busy} onClick={()=>{if(window.confirm(`Delete playlist “${p.name}”? The original audio will remain available.`))run(()=>api.delete(`/audio/playlists/${p.id}`));}}>Delete playlist</button></div>{p.unavailable>0&&<p className="text-xs text-gray-400">{p.unavailable} unavailable audio item(s) omitted.</p>}{p.items.map((i,n)=><div key={i.id} className="flex items-center gap-2 text-sm"><Link className="flex-1" to={`/watch/${i.id}`} state={playlistState(p.items)}>{n+1}. {i.title}</Link><button className={btn} aria-label={`Move ${i.title} up`} disabled={busy||n===0} onClick={()=>move(p,n,-1)}>↑</button><button className={btn} aria-label={`Move ${i.title} down`} disabled={busy||n===p.items.length-1} onClick={()=>move(p,n,1)}>↓</button><button className={btn} disabled={busy} onClick={()=>save(p,p.items.filter(x=>x.id!==i.id))}>Remove</button></div>)}</article>)}
 </section>;
}
