import {useEffect,useState} from "react";
import {Link} from "react-router-dom";
import {api,errorText,resolveMedia} from "@/lib/api";
import {Music,Radio} from "lucide-react";
import AudioPlaylists from "@/components/AudioPlaylists";

const btn="rounded-full border border-white/15 px-4 py-2 text-sm";
export default function AudioLibrary({kind}){
 const [data,setData]=useState(null),[page,setPage]=useState(0),[loading,setLoading]=useState(true),[error,setError]=useState("");
 useEffect(()=>{let active=true;setLoading(true);api.get("/audio/catalogue",{params:{kind,offset:page*100}}).then(r=>{if(active){setData(r.data);setError("");}}).catch(e=>{if(active)setError(errorText(e));}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[kind,page]);
 const music=kind==="music",Icon=music?Music:Radio;
 return <section className="max-w-[1600px] mx-auto px-4 md:px-8 pt-8 pb-24 space-y-6"><header><div className="text-xs uppercase tracking-widest text-[#FFB000]">LoNo Audio</div><h1 className="font-display text-4xl md:text-5xl mt-2">{music?"Music, Albums & Singles":"Podcasts & Audio Shows"}</h1><p className="text-gray-400 mt-2">{music?"Discover artists, singles and albums from Liberia and around the world.":"Listen to conversations, interviews and stories, episode by episode."}</p></header><div className="flex gap-2"><Link className={`${btn} ${music?"bg-white text-black":""}`} to="/browse/music">Music</Link><Link className={`${btn} ${!music?"bg-white text-black":""}`} to="/browse/podcast">Podcasts</Link></div>
 {error&&<p role="alert" className="text-red-300">{error}</p>}{loading?<p className="text-gray-400">Loading audio…</p>:data?.items.length?<div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">{data.items.map(a=><Link key={a.key} to={`/watch/${a.id}`} className="rounded-xl overflow-hidden border border-white/10 bg-white/5 group"><div className="aspect-square bg-[#171717] grid place-items-center overflow-hidden">{a.thumbnail_url?<img src={resolveMedia(a.thumbnail_url)} className="w-full h-full object-cover" alt="" loading="lazy"/>:<Icon className="w-10 h-10 text-[#FFB000]"/>}</div><div className="p-3"><h2 className="font-display text-lg group-hover:text-[#FFB000]">{a.title}</h2><p className="text-sm text-gray-400">{a.audio?.artist||a.category}</p><p className="text-xs text-gray-400">{a.audio?.collection_key?`${a.count} ${music?"tracks":"episodes"}`:music?"Single":"Episode"}{a.audio?.explicit?" · Explicit":""}</p></div></Link>)}</div>:<p className="text-gray-400">No published {music?"music":"podcasts"} yet.</p>}
 <div className="flex gap-2">{page>0&&<button className={btn} onClick={()=>setPage(p=>p-1)}>Previous</button>}{data?.has_more&&<button className={btn} onClick={()=>setPage(p=>p+1)}>Next page</button>}</div><AudioPlaylists/></section>;
}
