import {Link} from "react-router-dom";
import {resolveMedia} from "@/lib/api";
import {Play} from "lucide-react";

export const discoveryPath=(r)=>r.entity==="station"?`/stations/${r.id}`:r.entity==="channel"?`/channel/${r.id}`:r.entity==="course"?`/learn/${r.id}`:r.kind?.startsWith("live")?`/live/play/${r.id}`:`/watch/${r.id}`;
const names={movie:"Film",series:"Series",short:"Short film",music:"Music",podcast:"Podcast",course:"Course",live_tv:"Live TV",live_radio:"Live radio",tv:"TV station",radio:"Radio station",channel:"Creator"};
export default function DiscoveryCard({item,lite=false}){
 return <Link to={discoveryPath(item)} className={`group rounded-xl border border-white/10 bg-white/5 hover:border-white/25 overflow-hidden ${lite?"flex gap-3 items-center p-3":""}`}>
 {!lite&&<div className="aspect-video bg-[#171717] grid place-items-center overflow-hidden">{item.thumbnail_url?<img className="w-full h-full object-cover" src={resolveMedia(item.thumbnail_url)} alt="" loading="lazy" decoding="async"/>:<Play className="text-[#FFB000] w-7 h-7"/>}</div>}
 <div className={lite?"min-w-0":"p-3"}><p className="text-xs text-[#FFB000] uppercase">{names[item.kind]||names[item.entity]||item.entity}</p><h3 className="font-medium group-hover:text-[#FFB000] line-clamp-2">{item.title}</h3>{item.subtitle&&<p className="text-xs text-gray-400">{item.subtitle}</p>}<p className="text-xs text-gray-400 line-clamp-2">{item.category||item.description}</p></div></Link>;
}
