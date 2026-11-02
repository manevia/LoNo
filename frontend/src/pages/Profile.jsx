import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Award, LogOut } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import ContentCard from "@/components/ContentCard";

export default function Profile() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [learning, setLearning] = useState({ certificates: [] });
  const [list, setList] = useState([]);

  useEffect(() => {
    api.get("/learn/me").then(({ data }) => setLearning(data)).catch(() => {});
    api.get("/me/list").then(({ data }) => setList(data)).catch(() => {});
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
