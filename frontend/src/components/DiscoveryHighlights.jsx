import {useEffect,useState} from "react";
import {api,errorText} from "@/lib/api";
import {useAuth} from "@/lib/auth";
import DiscoveryCard from "@/components/DiscoveryCard";

export default function DiscoveryHighlights({lite=false}){
 const {user}=useAuth();const [rails,setRails]=useState(null),[error,setError]=useState("");
 useEffect(()=>{let active=true;setRails(null);api.get("/discovery/highlights",{params:{lite}}).then(r=>{if(active){setRails(r.data);setError("");}}).catch(e=>{if(active)setError(errorText(e));});return()=>{active=false;};},[lite,user?.id]);
 return <section className="space-y-8">{error&&<p role="alert" className="text-red-300">{error}</p>}{!rails&&!error?<p className="text-gray-400">Loading discovery…</p>:rails?.length===0?<p className="text-gray-400">Featured titles will appear when content is published.</p>:rails?.map(r=><div key={r.key}><h2 className="font-display text-2xl mb-3">{r.title}</h2>{r.description&&<p className="text-gray-400 text-sm mb-3">{r.description}</p>}<div className={lite?"grid gap-2 md:grid-cols-2":"grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3"}>{r.items.map(i=><DiscoveryCard key={i.id} item={i} lite={lite}/>)}</div></div>)}</section>;
}
