import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import HeroBanner from "@/components/HeroBanner";
import ContentRail from "@/components/ContentRail";
import DiscoveryHighlights from "@/components/DiscoveryHighlights";
import {usePrefs} from "@/lib/device";
import { Film, Tv, Radio, GraduationCap, Music, Mic, ArrowRight, Loader2 } from "lucide-react";

const categories = [
  ["Movies", "Discover stories on screen", "/browse/movie", Film],
  ["Series", "Explore episodic entertainment", "/browse/series", Tv],
  ["Podcasts", "Listen to new perspectives", "/browse/podcast", Mic],
  ["Music", "Discover sounds and artists", "/browse/music", Music],
  ["Live", "Explore live TV and radio", "/live", Radio],
  ["Learn", "Explore courses and skills", "/learn", GraduationCap],
];

function Welcome({ status, retry }) {
  return (
    <>
      <section data-testid="home-welcome" className="relative overflow-hidden border-b border-white/10 bg-gradient-to-br from-[#301313] via-[#101010] to-[#050505]">
        <div className="max-w-[1600px] mx-auto px-6 md:px-12 py-16 md:py-24">
          <p className="text-[#FFB000] uppercase tracking-[0.25em] text-xs font-bold">Welcome to LoNo</p>
          <h1 className="font-display text-4xl md:text-7xl font-semibold tracking-tight max-w-3xl mt-4">Discover. Watch. Listen. Learn.</h1>
          <p className="max-w-xl text-gray-300 text-lg mt-5">Entertainment, live broadcasting, music and education in one place. Explore the platform and discover your next experience.</p>
          <div className="flex flex-wrap gap-3 mt-8">
            <Link to="/live" className="rounded-full bg-[#FF3B30] px-6 py-3 font-semibold inline-flex items-center gap-2">Explore LoNo <ArrowRight className="w-4 h-4" /></Link>
            <Link to="/learn" className="rounded-full border border-white/30 px-6 py-3 font-semibold hover:bg-white/10">Explore learning</Link>
          </div>
          <div className="mt-8 text-sm text-gray-300" role="status" aria-live="polite">
            {status === "loading" && <span className="inline-flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Loading the catalogue…</span>}
            {status === "error" && <><span>The catalogue is temporarily unavailable. </span><button type="button" onClick={retry} className="text-white underline underline-offset-4">Try again</button></>}
            {status === "empty" && <><span>New content will appear here when available. </span><button type="button" onClick={retry} className="text-white underline underline-offset-4">Refresh catalogue</button></>}
          </div>
        </div>
      </section>
      <section className="max-w-[1600px] mx-auto px-6 md:px-12 py-10 pb-24">
        <h2 className="font-display text-2xl font-semibold mb-5">Explore LoNo</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {categories.map(([title, description, to, Icon]) => (
            <Link key={to} to={to} className="rounded-2xl border border-white/10 bg-white/5 p-5 hover:bg-white/10 transition-colors">
              <Icon className="w-7 h-7 text-[#FF3B30] mb-4" />
              <h3 className="font-semibold text-lg">{title}</h3>
              <p className="text-sm text-gray-400 mt-1">{description}</p>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}

export default function Home() {
  const {dataSaver}=usePrefs();
  const [rails, setRails] = useState([]);
  const [status, setStatus] = useState("loading");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setStatus("loading");
    (async () => {
      try {
        const { data } = await api.get("/content/rails", { timeout: 12000, signal: controller.signal });
        if (controller.signal.aborted) return;
        if (!Array.isArray(data) || data.some((rail) => !rail || typeof rail.key !== "string" || typeof rail.title !== "string" || !Array.isArray(rail.items))) {
          throw new Error("Invalid catalogue response");
        }
        const populated = data.map((rail) => ({ ...rail, items: rail.items.filter((item) => item && typeof item.id === "string") })).filter((rail) => rail.items.length > 0);
        setRails(populated);
        setStatus(populated.length ? "ready" : "empty");
      } catch {
        if (!controller.signal.aborted) {
          setRails([]);
          setStatus("error");
        }
      }
    })();
    return () => controller.abort();
  }, [attempt]);

  const featured = rails.find((r) => r.key === "featured")?.items?.[0] || rails.find((r) => r.items?.length)?.items?.[0];

  return (
    <div data-testid="home-page">
      {!featured ? <Welcome status={status} retry={() => setAttempt((n) => n + 1)} /> : <HeroBanner item={featured} />}
      {featured && <div className="pb-20 -mt-24 relative z-10">
        {rails.map((r) => (
          <ContentRail
            key={r.key}
            title={r.title}
            items={r.items}
            showRank={r.key === "top10"}
            accent={r.key === "originals"}
          />
        ))}
      </div>}
      <section className="max-w-[1600px] mx-auto px-4 md:px-8 pb-24 space-y-5"><div className="flex flex-wrap justify-between items-center gap-3"><h2 className="font-display text-3xl">Discover LoNo</h2><Link to="/search" className="rounded-full bg-[#FF3B30] px-5 py-2 text-sm">Explore all media</Link></div><DiscoveryHighlights lite={dataSaver}/></section>
    </div>
  );
}
