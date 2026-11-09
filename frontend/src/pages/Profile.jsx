import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Award, LogOut } from "lucide-react";
import { api, resolveMedia } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import ContentCard from "@/components/ContentCard";

export default function Profile() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [learning, setLearning] = useState({ certificates: [] });
  const [list, setList] = useState([]);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    api.get("/learn/me").then(({ data }) => setLearning(data)).catch(() => {});
    api.get("/me/list").then(({ data }) => setList(data)).catch(() => {});
    api.get("/me/history").then(({ data }) => setHistory(data)).catch(() => {});
  }, []);

  if (!user) return null;
  const stats = [
    { label: "Balance", value: `${user.wallet.lono_balance.toFixed(2)}`, color: "text-[#FFB000]" },
    { label: "Staked", value: user.wallet.staked.toFixed(2), color: "text-white" },
    { label: "Earned all time", value: user.wallet.total_earned.toFixed(2), color: "text-[#34C759]" },
    { label: "Certificates", value: learning.certificates.length, color: "text-white" },
  ];

  return (
    <div data-testid="profile-page" className="max-w-5xl mx-auto px-4 md:px-8 pt-12 pb-32">
      <div className="flex items-center gap-6">
        <img src={user.avatar_url} alt="" className="w-20 h-20 md:w-24 md:h-24 rounded-2xl ring-2 ring-white/10 bg-white/5" />
        <div className="min-w-0">
          <h1 className="font-display text-3xl md:text-4xl tracking-tight truncate">{user.name}</h1>
          <div className="text-sm text-gray-400 truncate">{user.email}</div>
          <div className="mt-2 text-sm text-[#FFB000] capitalize">{user.plan} plan</div>
        </div>
      </div>

      <div className="mt-10 grid grid-cols-2 md:grid-cols-4 gap-3">
        {stats.map((s) => (
          <div key={s.label} className="p-5 rounded-2xl bg-[#121212] border border-white/10">
            <div className="text-sm text-gray-400">{s.label}</div>
            <div className={`mt-1 font-display text-2xl tabular-nums ${s.color}`}>{s.value}</div>
          </div>
        ))}
      </div>

      <section className="mt-12">
        <h2 className="font-display text-xl">Certificates</h2>
        {learning.certificates.length ? (
          <ul className="mt-4 divide-y divide-white/10 border-y border-white/10">
            {learning.certificates.map((c) => (
              <li key={c.id}>
                <Link to={`/certificates/${c.id}`} className="flex items-center gap-3 py-4 hover:text-[#FFB000]">
                  <Award className="w-5 h-5 text-[#FFB000]" />
                  <span className="flex-1">{c.course_title}</span>
                  <span className="text-sm text-gray-500">{new Date(c.issued_at).toLocaleDateString()}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-gray-400">Pass a course quiz to earn your first certificate. <Link to="/learn" className="text-white underline">Browse courses</Link></p>
        )}
      </section>

      <section className="mt-12" data-testid="watch-history">
        <div className="flex items-end justify-between gap-3">
          <h2 className="font-display text-xl">Recently watched</h2>
          {history.length > 0 && (
            <button onClick={async () => {
              if (!window.confirm("Clear your watch history? Your earnings aren't affected.")) return;
              await api.delete("/me/history"); setHistory([]);
            }} className="text-sm text-gray-400 hover:text-white">Clear history</button>
          )}
        </div>
        {history.length ? (
          <ul className="mt-4 divide-y divide-white/10 border-y border-white/10">
            {history.slice(0, 20).map((h) => (
              <li key={h.content.id}>
                <Link to={`/watch/${h.content.id}`} className="grid grid-cols-[112px_1fr_auto] gap-4 items-center py-3 hover:bg-white/[0.02]">
                  <div className="relative">
                    <img src={resolveMedia(h.content.thumbnail_url)} alt="" className="w-full aspect-video object-cover rounded-md ring-1 ring-white/10" />
                    {h.percent != null && (
                      <div className="absolute inset-x-1 bottom-1 h-1 rounded-full bg-black/60 overflow-hidden" aria-hidden="true">
                        <div className="h-full bg-[#FF3B30]" style={{ width: `${Math.max(3, h.percent)}%` }} />
                      </div>
                    )}
                  </div>
                  <div className="min-w-0">
                    <div className="font-medium truncate">{h.content.title}</div>
                    <div className="text-xs text-gray-400 mt-0.5 capitalize">{h.content.kind.replace("_", " ")} / {h.content.category}</div>
                  </div>
                  <div className="text-xs text-gray-500 text-right whitespace-nowrap">
                    {h.percent == null ? "Live" : h.percent >= 95 ? "Finished" : h.percent < 1 ? "Just started" : `${h.percent}% watched`}
                    <div>{new Date(h.watched_at).toLocaleDateString()}</div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        ) : <p className="mt-3 text-gray-400">Titles you watch show up here so you can pick up where you left off.</p>}
      </section>

      <section className="mt-12">
        <h2 className="font-display text-xl">My list</h2>
        {list.length ? (
          <div className="mt-4 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {list.map((i) => <ContentCard key={i.id} item={i} compact />)}
          </div>
        ) : <p className="mt-3 text-gray-400">Use “My list” on any title to save it here.</p>}
      </section>

      <button data-testid="profile-logout" onClick={() => { logout(); nav("/"); }} className="mt-12 inline-flex items-center gap-2 bg-white/5 border border-white/10 rounded-full px-5 py-2.5 hover:bg-white/10">
        <LogOut className="w-4 h-4" /> Sign out
      </button>
    </div>
  );
}
