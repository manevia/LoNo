import { useState } from "react";
import { Link } from "react-router-dom";
import MediaPlayer from "@/components/MediaPlayer";
import { resolveMedia } from "@/lib/api";

const FORMAT={feature:"Feature film",documentary:"Documentary",short_film:"Short film"};
const ADVISORY={unrated:"Unrated",general:"General audience",parental_guidance:"Parental guidance", "13_plus":"13+","16_plus":"16+","18_plus":"18+"};
export default function FilmDetails({item}){
  const [showTrailer,setShowTrailer]=useState(false);const f=item.film;
  if(!f&&!item.trailer_url)return null;
  return <section className="mt-6 border border-white/10 rounded-xl p-4 space-y-3"><h2 className="font-display text-xl">Film information</h2>{f&&<><div className="flex flex-wrap gap-2 text-sm text-gray-300">{[FORMAT[f.format],f.release_year,f.runtime_minutes&&`${f.runtime_minutes} min`,f.country,f.language].filter(Boolean).map((x,i)=><span key={i} className="rounded-full bg-white/5 px-3 py-1">{x}</span>)}</div><p className="text-xs text-gray-400">Content advisory: {ADVISORY[f.maturity]||"Unrated"} · creator-declared</p>{f.genres?.length>0&&<p className="text-sm">Genres: {f.genres.join(", ")}</p>}{f.collection&&<p className="text-sm">Collection: {f.collection} · <Link to="/browse/movie" className="text-[#FF8A82]">Explore films</Link></p>}{f.credits?.length>0&&<><h3 className="font-semibold">Cast & production credits</h3><dl className="grid grid-cols-2 sm:grid-cols-3 gap-3">{f.credits.map((c,i)=><div key={i}><dt className="text-xs text-gray-400">{c.role}</dt><dd className="text-sm">{c.name}</dd></div>)}</dl></>}</>}{item.trailer_url&&<><button className="rounded-full border border-white/15 px-4 py-2 text-sm" onClick={()=>setShowTrailer(x=>!x)}>{showTrailer?"Close trailer":"Watch trailer"}</button>{showTrailer&&<MediaPlayer src={resolveMedia(item.trailer_url)} title={`${item.title} trailer`} showOptions={false}/>}</>}</section>;
}
