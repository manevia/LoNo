import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { CalendarClock, CheckCircle2, Gift, Loader2, PlayCircle, Ticket, Timer } from "lucide-react";
import { api, errorText } from "@/lib/api";

const fmtDate = (iso) => new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
const mins = (s) => (s >= 60 ? `${Math.round(s / 60)} min` : `${s} s`);

function Facts({ o }) {
  return (
    <dl className="grid grid-cols-2 gap-3 text-sm" data-testid="offer-facts">
      <div className="rounded-xl bg-white/5 p-3"><dt className="text-gray-400 text-xs">Price</dt><dd className="font-display text-xl text-[#FFB000]">{o.points_price} $LONO</dd></div>
      <div className="rounded-xl bg-white/5 p-3"><dt className="text-gray-400 text-xs">Passes left</dt><dd className="font-display text-xl" data-testid="offer-remaining">{o.remaining} of {o.inventory_total}</dd></div>
      <div className="rounded-xl bg-white/5 p-3"><dt className="text-gray-400 text-xs">Claim by</dt><dd>{fmtDate(o.closes_at)}</dd></div>
      <div className="rounded-xl bg-white/5 p-3"><dt className="text-gray-400 text-xs">Watch for</dt><dd>{o.access_days} day{o.access_days === 1 ? "" : "s"} after claiming</dd></div>
    </dl>
  );
}

/** /offers: open sponsored offers. */
export function OffersList() {
  const [items, setItems] = useState(null);
  useEffect(() => { api.get("/offers").then(({ data }) => setItems(data)).catch(() => setItems([])); }, []);
  return (
    <div className="max-w-3xl mx-auto px-4 pt-6 pb-28" data-testid="offers-page">
      <h1 className="font-display text-3xl font-semibold">Offers</h1>
      <p className="mt-1 text-gray-400 text-sm">Spend the $LONO you earn on LoNo. Passes are limited.</p>
      {!items ? <Loader2 className="mt-8 w-6 h-6 animate-spin text-[#FF3B30]" /> : items.length === 0 ? <p className="mt-8 text-gray-400">No offers right now.</p> : (
        <ul className="mt-6 space-y-3">
          {items.map((o) => (
            <li key={o.id}>
              <Link to={`/offers/${o.id}`} data-testid={`offer-${o.id}`} className="block rounded-2xl bg-[#121212] border border-white/10 p-4 hover:border-white/25">
                <div className="text-xs text-gray-400">Sponsored by {o.sponsor.name}</div>
                <div className="font-display text-xl mt-0.5">{o.title}</div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-300">
                  <span className="text-[#FFB000]">{o.points_price} $LONO</span><span>{o.remaining} left</span><span>until {fmtDate(o.closes_at)}</span>
                </div>
                {o.my_claim && <div className="mt-2 text-xs text-[#34C759]">You have this pass</div>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** /offers/:id: details, earning task, and claim with confirmation. */
export function OfferDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [o, setO] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const load = () => api.get(`/offers/${id}`).then(({ data }) => setO(data)).catch((e) => toast.error(errorText(e)));
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const claim = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/offers/${id}/claim`);
      toast.success("Pass claimed. Your replay is in My passes.");
      nav(`/passes/${data.claim.id}`);
    } catch (e) { toast.error(errorText(e)); setConfirming(false); load(); } finally { setBusy(false); }
  };

  if (!o) return <div className="min-h-[60vh] grid place-items-center"><Loader2 className="w-6 h-6 animate-spin text-[#FF3B30]" /></div>;
  const p = o.my_progress;
  const short = Math.max(0, o.points_price - o.my_balance);
  return (
    <div className="max-w-xl mx-auto px-4 pt-5 pb-28" data-testid="offer-detail">
      <div className="text-xs text-gray-400 flex items-center gap-1.5"><Gift className="w-3.5 h-3.5" /> Sponsored by <span className="text-white" data-testid="offer-sponsor">{o.sponsor.name}</span></div>
      <h1 className="font-display text-2xl md:text-3xl font-semibold mt-1">{o.title}</h1>
      {o.description && <p className="mt-2 text-sm text-gray-300">{o.description}</p>}
      <p className="mt-1 text-sm text-gray-400">Replay: {o.replay.title} · from {o.organizer.name}</p>
      <div className="mt-5"><Facts o={o} /></div>

      <div className="mt-5 rounded-2xl bg-[#121212] border border-white/10 p-4" data-testid="earn-task">
        <div className="text-sm font-medium flex items-center gap-2"><Timer className="w-4 h-4 text-[#FFB000]" /> Earn {p.points} $LONO</div>
        <p className="text-sm text-gray-400 mt-1">Watch {mins(p.min_seconds)} of <b className="text-white">{p.content?.title}</b> in one go.</p>
        <div className="mt-3 h-2 rounded-full bg-white/10 overflow-hidden"><div className="h-full bg-[#FFB000]" style={{ width: `${Math.min(100, (p.verified_sec / p.min_seconds) * 100)}%` }} /></div>
        <div className="mt-2 flex items-center justify-between text-xs text-gray-400">
          <span>{p.earned ? <span className="text-[#34C759] inline-flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> Earned</span> : `${mins(p.verified_sec)} of ${mins(p.min_seconds)}`}</span>
          {!p.earned && p.content && <Link to={`/watch/${p.content.id}`} className="text-[#FFB000]" data-testid="earn-watch">Watch now</Link>}
        </div>
      </div>

      <div className="mt-5 text-sm">Your balance: <b className="text-[#FFB000]" data-testid="my-balance">{o.my_balance.toFixed(2)} $LONO</b></div>

      {o.my_claim ? (
        <Link to={`/passes/${o.my_claim.id}`} data-testid="go-to-pass" className="mt-4 flex items-center justify-center gap-2 w-full rounded-full bg-[#34C759] text-black py-3.5 font-semibold"><PlayCircle className="w-5 h-5" /> Watch your replay</Link>
      ) : !o.claimable || o.remaining === 0 ? (
        <div className="mt-4 rounded-xl bg-white/5 p-4 text-center text-gray-300">{o.remaining === 0 ? "All passes have been claimed." : "This offer isn't open for claims right now."}</div>
      ) : confirming ? (
        <div className="mt-4 rounded-2xl border border-[#FFB000]/40 bg-[#FFB000]/10 p-4" role="dialog" aria-label="Confirm" data-testid="claim-confirm">
          <p className="text-sm">Spend <b>{o.points_price} $LONO</b> on a pass for <b>{o.replay.title}</b>? You can watch it for {o.access_days} days. Points spent on a pass aren't returned unless the pass is canceled.</p>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button onClick={() => setConfirming(false)} className="rounded-full py-3 bg-white/10">Cancel</button>
            <button onClick={claim} disabled={busy} data-testid="claim-yes" className="rounded-full py-3 bg-[#FF3B30] font-semibold">{busy ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Claim pass"}</button>
          </div>
        </div>
      ) : (
        <button onClick={() => setConfirming(true)} disabled={short > 0} data-testid="claim-btn"
          className="mt-4 flex items-center justify-center gap-2 w-full rounded-full bg-[#FF3B30] py-3.5 font-semibold disabled:opacity-50">
          <Ticket className="w-5 h-5" /> {short > 0 ? `Earn ${short.toFixed(0)} more $LONO to claim` : `Claim pass for ${o.points_price} $LONO`}
        </button>
      )}
      <p className="mt-3 text-xs text-gray-500 flex gap-1.5"><CalendarClock className="w-3.5 h-3.5 shrink-0" /> One pass per person. $LONO can't be bought or transferred.</p>
    </div>
  );
}
