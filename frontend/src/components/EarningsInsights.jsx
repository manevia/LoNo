import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Flame, Clock, TrendingUp, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

// One colour per source; legend + tooltip carry the names so colour isn't the only cue.
const SOURCES = [
  { key: "watching", label: "Watching", color: "#FF3B30" },
  { key: "courses", label: "Courses", color: "#FFB000" },
  { key: "staking", label: "Staking", color: "#34C759" },
  { key: "creator", label: "Creator payouts", color: "#64D2FF" },
  { key: "bonus", label: "Bonuses", color: "#8E8E93" },
];
const PERIODS = [7, 30, 90];

const fmtDay = (iso, days) => {
  const d = new Date(`${iso}T00:00:00`);
  return days === 7 ? d.toLocaleDateString(undefined, { weekday: "short" }) : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((p) => p.value > 0);
  const total = rows.reduce((n, p) => n + p.value, 0);
  return (
    <div className="rounded-lg bg-[#050505] border border-white/15 px-3 py-2 text-xs shadow-xl">
      <div className="text-gray-400 mb-1">{label}</div>
      {rows.length ? rows.map((p) => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-sm" style={{ background: p.fill }} />
          <span className="text-gray-300">{SOURCES.find((s) => s.key === p.dataKey)?.label}</span>
          <span className="ml-auto pl-4 tabular-nums">{p.value.toFixed(2)}</span>
        </div>
      )) : <div className="text-gray-500">Nothing earned</div>}
      {rows.length > 1 && <div className="mt-1 pt-1 border-t border-white/10 flex"><span className="text-gray-400">Total</span><span className="ml-auto tabular-nums">{total.toFixed(2)}</span></div>}
    </div>
  );
}

/** Wallet section: where $LONO came from over the last 7/30/90 days, watch time and streak. */
export default function EarningsInsights() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);

  useEffect(() => {
    setData(null);
    api.get("/wallet/insights", { params: { days } }).then(({ data }) => setData(data)).catch(() => setData(false));
  }, [days]);

  const chart = data ? data.series.map((d) => ({ ...d, label: fmtDay(d.date, days) })) : [];
  const active = data ? SOURCES.filter((s) => data.totals[s.key] > 0) : [];

  return (
    <section data-testid="earnings-insights" className="mt-12" aria-labelledby="earnings-heading">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <h2 id="earnings-heading" className="font-display text-2xl flex items-center gap-2"><TrendingUp className="w-5 h-5 text-[#34C759]" /> Your earnings</h2>
        <div role="group" aria-label="Period" className="flex rounded-full bg-white/5 border border-white/10 p-0.5 text-sm">
          {PERIODS.map((p) => (
            <button key={p} onClick={() => setDays(p)} aria-pressed={days === p}
              className={`px-3.5 py-1.5 rounded-full transition ${days === p ? "bg-white text-black font-medium" : "text-gray-400 hover:text-white"}`}>
              {p} days
            </button>
          ))}
        </div>
      </div>

      {data === null ? (
        <div className="h-72 grid place-items-center rounded-2xl bg-[#121212] border border-white/10"><Loader2 className="w-6 h-6 animate-spin text-gray-500" /></div>
      ) : data === false ? (
        <p className="text-gray-400">Your earnings couldn't be loaded. Refresh to try again.</p>
      ) : (
        <div className="rounded-2xl bg-[#121212] border border-white/10 p-5 md:p-6">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <div className="text-sm text-gray-400">Earned</div>
              <div className="mt-1 font-display text-2xl md:text-3xl tabular-nums text-[#34C759]">{data.total_earned.toFixed(2)}</div>
              <div className="text-xs text-gray-500">$LONO in {days} days</div>
            </div>
            <div>
              <div className="text-sm text-gray-400 flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" /> Watch time</div>
              <div className="mt-1 font-display text-2xl md:text-3xl tabular-nums">
                {data.watch_minutes >= 60 ? `${Math.floor(data.watch_minutes / 60)}h ${data.watch_minutes % 60}m` : `${data.watch_minutes}m`}
              </div>
              <div className="text-xs text-gray-500">verified</div>
            </div>
            <div>
              <div className="text-sm text-gray-400 flex items-center gap-1.5"><Flame className="w-3.5 h-3.5" /> Streak</div>
              <div className="mt-1 font-display text-2xl md:text-3xl tabular-nums text-[#FFB000]">{data.streak_days} day{data.streak_days === 1 ? "" : "s"}</div>
              <div className="text-xs text-gray-500">{data.streak_days ? "watched in a row" : "watch today to start one"}</div>
            </div>
          </div>

          <div className="mt-6 h-56 -ml-2" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chart} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="#262626" vertical={false} />
                <XAxis dataKey="label" stroke="#6b7280" fontSize={11} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={18} />
                <YAxis stroke="#6b7280" fontSize={11} tickLine={false} axisLine={false} width={36} allowDecimals={false} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                {SOURCES.map((s, i) => (
                  <Bar key={s.key} dataKey={s.key} stackId="earned" fill={s.color} maxBarSize={28}
                    radius={i === SOURCES.length - 1 ? [3, 3, 0, 0] : 0} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>

          {active.length ? (
            <ul className="mt-5 flex flex-wrap gap-x-6 gap-y-2 text-sm" aria-label="Earnings by source">
              {active.map((s) => (
                <li key={s.key} className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-sm" style={{ background: s.color }} aria-hidden="true" />
                  <span className="text-gray-400">{s.label}</span>
                  <span className="tabular-nums">{data.totals[s.key].toFixed(2)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-5 text-sm text-gray-400">Nothing earned in this period yet. Watch something or pass a course to start.</p>
          )}
        </div>
      )}
    </section>
  );
}
