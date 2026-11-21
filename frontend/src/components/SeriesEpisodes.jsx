import {useEffect,useState} from "react";
import {Link} from "react-router-dom";
import {api,errorText,resolveMedia} from "@/lib/api";
import {Play} from "lucide-react";

export default function SeriesEpisodes({item,autoNext,setAutoNext}){
  const series=item.series;
  const [season,setSeason]=useState(series.season),[page,setPage]=useState(0),[data,setData]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(true);
  useEffect(()=>{let active=true;setLoading(true);api.get(`/series/${series.key}`,{params:{season,offset:page*100}}).then(r=>{if(active){setData(r.data);setError("");}}).catch(e=>{if(active)setError(errorText(e));}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[series.key,season,page]);
  const btn="rounded-full border border-white/15 px-4 py-2 text-sm";
  return <section className="mt-6 rounded-xl border border-white/10 p-4 space-y-4"><div className="flex flex-wrap justify-between gap-3"><div><p className="text-xs uppercase text-[#FFB000]">Season {series.season} · Episode {series.episode}</p><h2 className="font-display text-2xl">{series.series_title}</h2></div><Link to="/browse/series" className={btn}>All series</Link></div>
    {series.series_description&&<p className="text-sm text-gray-300">{series.series_description}</p>}
    <div className="flex gap-2 flex-wrap">{item.previous_episode&&<Link className={btn} to={`/watch/${item.previous_episode.id}`} state={{autoNext}}>← Previous episode</Link>}{item.next_episode&&<Link className="rounded-full bg-[#FF3B30] px-4 py-2 text-sm" to={`/watch/${item.next_episode.id}`} state={{autoNext}}>Next: {item.next_episode.title} →</Link>}</div>
    <label className="flex gap-2 items-center text-sm"><input type="checkbox" checked={autoNext} onChange={e=>setAutoNext(e.target.checked)}/> Automatically play next published episode</label>
    <label className="text-sm">Season <select className="rounded-lg border border-white/15 bg-[#171717] px-3 py-2" value={season} onChange={e=>{setSeason(Number(e.target.value));setPage(0);}}>{(data?.seasons||[series.season]).map(s=><option key={s} value={s}>Season {s}</option>)}</select></label>
    {error&&<p role="alert" className="text-red-300">{error}</p>}{loading?<p className="text-gray-400">Loading episodes…</p>:<div className="space-y-2">{data?.items.map(e=><Link key={e.id} to={`/watch/${e.id}`} state={{autoNext}} aria-current={e.id===item.id?"page":undefined} className={`flex gap-3 rounded-lg p-2 border ${e.id===item.id?"border-[#FF3B30] bg-white/5":"border-white/10"}`}><div className="w-28 aspect-video shrink-0 bg-[#171717] rounded grid place-items-center overflow-hidden">{e.thumbnail_url?<img className="w-full h-full object-cover" src={resolveMedia(e.thumbnail_url)} alt=""/>:<Play className="w-6 h-6"/>}</div><div><p className="text-xs text-gray-400">Episode {e.series.episode}{e.duration_sec?` · ${Math.round(e.duration_sec/60)} min`:""}</p><h3 className="text-sm font-semibold">{e.title}{e.id===item.id?" · Now watching":""}</h3><p className="text-xs text-gray-400 line-clamp-2">{e.description}</p></div></Link>)}</div>}
    <div className="flex gap-2">{page>0&&<button className={btn} onClick={()=>setPage(p=>p-1)}>Previous page</button>}{data?.has_more&&<button className={btn} onClick={()=>setPage(p=>p+1)}>Next page</button>}</div>
  </section>;
}
