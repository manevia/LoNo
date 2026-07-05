import { useAuth } from "@/lib/auth";
import { useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";

export default function Profile() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  if (!user) return null;

  return (
    <div data-testid="profile-page" className="max-w-3xl mx-auto px-4 md:px-8 pt-12 pb-24">
      <div className="flex items-center gap-6">
        <img src={user.avatar_url} alt="" className="w-24 h-24 rounded-2xl ring-2 ring-white/10" />
        <div>
          <h1 className="font-display text-4xl tracking-tight">{user.name}</h1>
          <div className="text-sm text-gray-400">{user.email}</div>
          <div className="mt-2 text-xs uppercase tracking-widest text-[#FFB000]">Plan: {user.plan}</div>
        </div>
      </div>

      <div className="mt-12 grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Balance", value: `${user.wallet.lono_balance.toFixed(2)} LONO`, color: "text-[#FFB000]" },
          { label: "Staked", value: user.wallet.staked.toFixed(2), color: "text-white" },
          { label: "Total Earned", value: user.wallet.total_earned.toFixed(2), color: "text-[#34C759]" },
          { label: "Watch History", value: (user.watch_history?.length || 0), color: "text-white" },
        ].map((s) => (
          <div key={s.label} className="p-6 rounded-2xl bg-[#121212] border border-white/10">
            <div className="text-xs uppercase tracking-widest text-gray-400">{s.label}</div>
            <div className={`mt-2 font-display text-2xl ${s.color}`}>{s.value}</div>
          </div>
        ))}
      </div>

      <button data-testid="profile-logout" onClick={() => { logout(); nav("/"); }} className="mt-10 inline-flex items-center gap-2 bg-white/5 border border-white/10 rounded-full px-5 py-2.5 hover:bg-white/10">
        <LogOut className="w-4 h-4" /> Sign out
      </button>
    </div>
  );
}
