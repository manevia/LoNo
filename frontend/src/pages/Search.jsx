import {useEffect,useState} from "react";
import {useSearchParams} from "react-router-dom";
import {api,errorText} from "@/lib/api";
import {usePrefs} from "@/lib/device";
import {Search as SearchIcon} from "lucide-react";
import DiscoveryCard from "@/components/DiscoveryCard";
import DiscoveryHighlights from "@/components/DiscoveryHighlights";

const filters=[["all","All"],["movie","Movies"],["series","Series"],["short","Shorts"],["music","Music"],["podcast","Podcasts"],["course","Courses"],["live_tv","Live TV"],["live_radio","Live radio"],["station","Stations"],["channel","Creators"]];
const btn="rounded-full border border-white/15 px-4 py-2 text-sm";
export default function Search(){
 const [params,setParams]=useSearchParams(),q=params.get("q")||"",kind=filters.some(([k])=>k===params.get("kind"))?params.get("kind"):"all",sort=params.get("sort")==="popular"?"popular":"newest";
 const {dataSaver}=usePrefs();const [lite,setLite]=useState(dataSaver),[term,setTerm]=useState(q),[offset,setOffset]=useState(0),[data,setData]=useState(null),[loading,setLoading]=useState(false),[error,setError]=useState("");
 useEffect(()=>{setTerm(q);setOffset(0);},[q,kind,sort]);
 useEffect(()=>{let active=true;setLoading(true);setData(null);api.get("/discovery/search",{params:{q,kind,sort,offset,lite}}).then(r=>{if(active){setData(r.data);setError("");}}).catch(e=>{if(active)setError(errorText(e));}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[q,kind,sort,offset,lite]);
 const change=(next)=>{setOffset(0);setParams({...Object.fromEntries(params),...next});};
 return <main data-testid="search-page" className="max-w-[1600px] mx-auto px-4 md:px-8 pt-8 pb-24 space-y-6"><header><p className="text-xs uppercase tracking-widest text-[#FFB000]">LoNo Discovery</p><h1 className="font-display text-4xl md:text-5xl mt-2">Discover. Watch. Listen. Learn.</h1><p className="text-gray-400 mt-2">Search titles, artists, albums, shows, stations, courses and creators.</p></header>
 <form className="flex gap-2 max-w-3xl" onSubmit={e=>{e.preventDefault();change({q:term.trim()});}}><input aria-label="Search catalogue" maxLength={120} value={term} onChange={e=>setTerm(e.target.value)} placeholder="Search LoNo…" className="flex-1 min-w-0 rounded-full border border-white/15 bg-white/5 px-4 py-3"/><button className="rounded-full bg-[#FF3B30] px-4 py-2 flex gap-2 items-center"><SearchIcon className="w-4 h-4"/>Search</button></form>
 <div role="group" aria-label="Media type" className="flex flex-wrap gap-2">{filters.map(([k,name])=><button key={k} className={`${btn} ${kind===k?"bg-white text-black":""}`} aria-pressed={kind===k} onClick={()=>change({kind:k})}>{name}</button>)}</div>
 <div className="flex gap-4 flex-wrap items-center"><label>Sort content <select aria-label="Sort content" className="rounded-lg bg-[#171717] border border-white/15 px-3 py-2" value={sort} onChange={e=>change({sort:e.target.value})}><option value="newest">Newest</option><option value="popular">Most viewed</option></select></label><label className="flex gap-2 items-center text-sm"><input type="checkbox" checked={lite} onChange={e=>{setOffset(0);setLite(e.target.checked);}}/> Low-data discovery (no images)</label></div>
 {!q&&kind==="all"&&offset===0&&<DiscoveryHighlights lite={lite}/>}
 <section className="space-y-4"><h2 className="font-display text-2xl">{q?`Results for “${q}”`:"Explore the catalogue"}</h2>{error&&<p role="alert" className="text-red-300">{error}</p>}{loading?<p role="status" className="text-gray-400">Loading results…</p>:data?.items.length?<div className={lite?"grid gap-2 md:grid-cols-2":"grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4"}>{data.items.map(i=><DiscoveryCard key={`${i.entity}:${i.id}`} item={i} lite={lite}/>)}</div>:!error&&<p className="text-gray-400">No published results match these filters.</p>}<div className="flex gap-2">{offset>0&&<button className={btn} onClick={()=>setOffset(Math.max(0,offset-(data?.page_size||48)))}>Previous</button>}{data?.has_more&&<button className={btn} onClick={()=>setOffset(offset+data.page_size)}>Next page</button>}</div></section></main>;
}
