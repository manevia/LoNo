import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Loader2, TrendingUp, Flame, Users, Coins, Shield, Activity } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

const COLORS = ["#FF3B30", "#FFB000", "#34C759", "#39B7EA", "#B266FF", "#F5D562"];

const Stat = ({ label, value, hint, icon: Icon, big = false }) => (
  <div className={`p-6 rounded-2xl bg-[#121212] border border-white/10 ${big ? "md:col-span-2" : ""}`}>
    <div className="flex items-center gap-2 text-xs tracking-widest uppercase text-gray-400">
      {Icon && <Icon className="w-3.5 h-3.5" />} {label}
    </div>
    <div className={`mt-2 font-display font-medium tracking-tight ${big ? "text-5xl text-[#FFB000]" : "text-3xl"}`}>{value}</div>
    {hint && <div className="mt-1 text-xs text-gray-500">{hint}</div>}
  </div>
);

const fmt = (n) => new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(n);

export default function Tokenomics() {
  const [data, setData] = useState(null);

  useEffect(() => { api.get("/tokenomics").then(({ data }) => setData(data)); }, []);
  if (!data) return <div className="min-h-[70vh] grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>;

  return (
    <div data-testid="tokenomics-page" className="max-w-[1600px] mx-auto px-4 md:px-8 pt-8 pb-24">
      <div className="text-[10px] tracking-[0.3em] font-bold text-[#FFB000] uppercase mb-2">Token Economy</div>
      <div className="flex items-baseline justify-between flex-wrap gap-4">
        <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tighter">$LONO</h1>
        <div className="flex items-baseline gap-3">
          <div className="font-display text-3xl">${data.price_usd.toFixed(4)}</div>
          <div className={`text-sm font-mono ${data.change_24h >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
            {data.change_24h >= 0 ? "+" : ""}{data.change_24h}% <span className="text-gray-500">24h</span>
          </div>
        </div>
      </div>

      <div className="mt-10 grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Market Cap" value={`$${fmt(data.market_cap)}`} icon={TrendingUp} />
        <Stat label="Circulating" value={fmt(data.circulating_supply)} hint={`of ${fmt(data.max_supply)} max`} icon={Coins} />
        <Stat label="Burned" value={fmt(data.burned)} hint="Deflationary" icon={Flame} />
        <Stat label="Wallets" value={fmt(data.total_wallets)} hint="Active accounts" icon={Users} />
      </div>

      <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 p-6 rounded-2xl bg-[#121212] border border-white/10">
          <div className="flex items-center justify-between mb-4">
            <div className="font-display text-xl">Price · 7 days</div>
            <div className="text-xs text-gray-400 flex items-center gap-2"><Activity className="w-3.5 h-3.5" /> Network health {data.network_health}%</div>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={data.chart_7d}>
              <defs>
                <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#FFB000" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#FFB000" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="day" stroke="#666" fontSize={12} />
              <YAxis stroke="#666" fontSize={12} domain={["auto", "auto"]} />
              <Tooltip contentStyle={{ background: "#050505", border: "1px solid #262626", borderRadius: 8 }} />
              <Area type="monotone" dataKey="price" stroke="#FFB000" strokeWidth={2} fill="url(#g)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="p-6 rounded-2xl bg-[#121212] border border-white/10">
          <div className="font-display text-xl mb-2">Allocation</div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={data.allocation} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2}>
                {data.allocation.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "#050505", border: "1px solid #262626", borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1.5 mt-2">
            {data.allocation.map((a, i) => (
              <div key={a.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                  <span className="text-gray-300">{a.name}</span>
                </div>
                <span className="font-mono text-gray-400">{a.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Treasury" value={fmt(data.treasury)} icon={Shield} />
        <Stat label="Creator Fund" value={fmt(data.creator_fund)} />
        <Stat label="Education Fund" value={fmt(data.education_fund)} />
        <Stat label="Community Fund" value={fmt(data.community_fund)} />
      </div>

      <div className="mt-10 p-8 rounded-2xl border border-white/10 bg-gradient-to-br from-white/[0.03] to-transparent">
        <div className="text-[10px] tracking-[0.3em] uppercase text-[#FFB000] font-bold">Legal notice</div>
        <p className="mt-2 text-sm text-gray-400 max-w-3xl">
          $LONO is a utility token designed to power access, rewards, and governance within the LoNo ecosystem. It is
          not offered or represented as an investment product. Legal counsel should review jurisdiction-specific
          compliance requirements (SEC, FinCEN, IRS, GDPR, CCPA) before public distribution.
        </p>
      </div>
    </div>
  );
}
