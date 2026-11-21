import {useEffect,useState} from "react";
import {Link} from "react-router-dom";
import {api,errorText,resolveMedia} from "@/lib/api";
import {Play} from "lucide-react";

export default function SeriesLibrary(){
  const [page,setPage]=useState(0),[data,setData]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(true);
  useEffect(()=>{let active=true;setLoading(true);api.get("/series",{params:{offset:page*100}}).then(r=>{if(active){setData(r.data);setError("");}}).catch(e=>{if(active)setError(errorText(e));}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[page]);
  const btn="rounded-full border border-white/15 px-4 py-2 text-sm";
  return <section className="max-w-[1600px] mx-auto px-4 md:px-8 pt-8 pb-24 space-y-6">
    <header><div className="text-xs uppercase tracking-widest text-[#FFB000]">LoNo Series</div><h1 className="font-display text-4xl md:text-5xl mt-2">Series, Seasons & Episodes</h1><p className="text-gray-400 mt-2">Explore published series and continue the story, one episode at a time.</p></header>
    {error&&<p role="alert" className="text-red-300">{error}</p>}{loading?<p className="text-gray-400">Loading series…</p>:data?.items.length?<div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">{data.items.map(s=><Link key={s.key} to={`/watch/${s.id}`} className="group rounded-xl border border-white/10 overflow-hidden bg-white/5"><div className="aspect-video bg-[#171717] relative grid place-items-center">{s.thumbnail_url?<img className="w-full h-full object-cover" src={resolveMedia(s.thumbnail_url)} alt="" loading="lazy"/>:<Play className="w-9 h-9 text-[#FFB000]"/>}</div><div className="p-3"><h2 className="font-display text-lg group-hover:text-[#FFB000]">{s.title}</h2><p className="text-xs text-gray-400 mt-1">{s.series?`${s.seasons.length} ${s.seasons.length===1?"season":"seasons"} · ${s.episodes} ${s.episodes===1?"episode":"episodes"}`:s.category}</p></div></Link>)}</div>:<p className="text-gray-400">No published series yet.</p>}
    <div className="flex gap-2">{page>0&&<button className={btn} onClick={()=>setPage(p=>p-1)}>Previous</button>}{data?.has_more&&<button className={btn} onClick={()=>setPage(p=>p+1)}>Next page</button>}</div>
  </section>;
}
