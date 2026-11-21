const field="block w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm mt-1";
export const episodeDefaults={series_title:"",series_description:"",season:1,episode:1,season_title:"",runtime_minutes:null};

export default function EpisodeMetadata({episode,onChange,editable}){
  const value={...episodeDefaults,...episode};
  const set=(key,v)=>onChange({...value,[key]:v});
  return <fieldset disabled={!editable} className="border border-white/10 rounded-xl p-4 space-y-3">
    <legend className="px-2 text-[#FFB000] font-semibold">Series, season & episode</legend>
    <p className="text-xs text-gray-400">Use the same series title on this channel for every episode. Each episode has its own private media, review and release date. Title above is the episode title.</p>
    <label>Series title<input className={field} required maxLength={140} value={value.series_title} onChange={e=>set("series_title",e.target.value)}/></label>
    <label>Series synopsis<textarea className={field} maxLength={2000} value={value.series_description} onChange={e=>set("series_description",e.target.value)}/></label>
    <div className="grid md:grid-cols-2 gap-3">
      <label>Season number<input className={field} type="number" min={1} max={999} required value={value.season??""} onChange={e=>set("season",e.target.value===""?null:Number(e.target.value))}/></label>
      <label>Episode number<input className={field} type="number" min={1} max={9999} required value={value.episode??""} onChange={e=>set("episode",e.target.value===""?null:Number(e.target.value))}/></label>
      <label>Season title (optional)<input className={field} maxLength={100} value={value.season_title} onChange={e=>set("season_title",e.target.value)}/></label>
      <label>Runtime (minutes)<input className={field} type="number" min={1} max={1440} value={value.runtime_minutes??""} onChange={e=>set("runtime_minutes",e.target.value===""?null:Number(e.target.value))}/></label>
    </div>
  </fieldset>;
}
