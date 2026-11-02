import { useEffect, useState } from "react";
import { api, errorText } from "@/lib/api";
import { useConfig } from "@/lib/config";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Loader2, ArrowUpRight, ArrowDownRight, Copy, Coins, TrendingUp, Lock, Unlock, CreditCard } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function Wallet() {
  const { refresh, user } = useAuth();
  const cfg = useConfig();
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [tx, setTx] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stakeOpen, setStakeOpen] = useState(false);
  const [buyOpen, setBuyOpen] = useState(false);
  const [stakeForm, setStakeForm] = useState({ amount: 50, lock_days: 30 });
  const [buyAmt, setBuyAmt] = useState(25);

  const load = async () => {
    const [w, t] = await Promise.all([api.get("/wallet"), api.get("/wallet/transactions")]);
    setData(w.data); setTx(t.data); setLoading(false);
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    const c = params.get("checkout");
    if (!c) return;
    if (c === "success") { toast.success("Payment received", { description: "Your plan updates as soon as Stripe confirms it." }); setTimeout(refresh, 3000); }
    if (c === "cancelled") toast("Checkout cancelled. You haven't been charged.");
    setParams({}, { replace: true });
  }, [params, setParams, refresh]);

  const doStake = async () => {
    try {
      await api.post("/wallet/stake", stakeForm);
      toast.success(`Staked ${stakeForm.amount} $LONO`);
      setStakeOpen(false); refresh(); load();
    } catch (e) { toast.error(errorText(e, "Staking didn't go through")); }
  };

  const doUnstake = async (id) => {
    try {
      const { data } = await api.post(`/wallet/unstake/${id}`);
      toast.success(`Returned ${data.returned.toFixed(2)} $LONO`, { description: data.early ? "Unstaked early, so no reward was paid" : `Includes ${data.reward.toFixed(4)} reward` });
      refresh(); load();
    } catch (e) { toast.error(errorText(e, "Unstaking didn't go through")); }
  };

  const doBuy = async () => {
    try {
      const { data } = await api.post("/payments/token-buy", { amount_usd: Number(buyAmt) });
      toast.success(data.message);
      setBuyOpen(false); refresh(); load();
    } catch (e) { toast.error(errorText(e, "Purchase didn't go through")); }
  };

  const checkout = async (plan) => {
    try {
      const { data } = await api.post("/payments/checkout", { plan });
      if (data.url) window.location.href = data.url;
    } catch (e) { toast.error(errorText(e, "Checkout couldn't start")); }
  };

  if (loading || !data) return <div className="min-h-[70vh] grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>;

  const total = data.wallet.lono_balance + data.wallet.staked;

  return (
    <div data-testid="wallet-page" className="max-w-[1600px] mx-auto px-4 md:px-8 pt-8 pb-24">
      <div className="text-[10px] tracking-[0.3em] font-bold text-[#FFB000] uppercase mb-2">LoNo Wallet</div>
      <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tighter">Your $LONO</h1>

      <div className="mt-10 grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Balance hero */}
        <div className="lg:col-span-2 p-8 rounded-3xl border border-white/10 bg-gradient-to-br from-[#1a0a08] via-[#121212] to-[#050505] relative overflow-hidden">
          <div className="absolute -top-24 -right-24 w-96 h-96 rounded-full bg-[#FF3B30]/20 blur-3xl" />
          <div className="relative">
            <div className="text-xs tracking-widest uppercase text-gray-400">Total Balance</div>
            <div className="mt-2 font-display font-semibold text-6xl md:text-7xl tracking-tighter text-glow-amber text-[#FFB000]" data-testid="wallet-balance-text">
              {total.toFixed(2)}
              <span className="text-2xl text-gray-400 ml-3 font-normal">$LONO</span>
            </div>
            <div className="mt-2 text-sm text-gray-400">≈ ${(total * cfg.lono_price_usd).toFixed(2)} USD (simulated price)</div>

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <button onClick={() => setStakeOpen(true)} data-testid="stake-btn" className="flex items-center gap-2 bg-white text-black hover:bg-gray-200 rounded-full px-5 py-2.5 text-sm font-medium">
                <Lock className="w-4 h-4" /> Stake
              </button>
              {cfg.simulated_token_purchase && <Dialog open={buyOpen} onOpenChange={setBuyOpen}>
                <DialogTrigger asChild>
                  <button data-testid="buy-btn" className="flex items-center gap-2 bg-white/10 hover:bg-white/20 border border-white/20 rounded-full px-5 py-2.5 text-sm font-medium">
                    <TrendingUp className="w-4 h-4" /> Buy $LONO
                  </button>
                </DialogTrigger>
                <DialogContent className="bg-[#0a0a0a] border-white/10 text-white">
                  <DialogHeader><DialogTitle className="font-display">Buy $LONO</DialogTitle></DialogHeader>
                  <p className="text-sm text-gray-400">Demo mode: this adds $LONO to your wallet without taking a payment. Up to $500 per purchase.</p>
                  <div className="space-y-4">
                    <div>
                      <Label className="text-xs">Amount (USD)</Label>
                      <Input data-testid="buy-amount" type="number" value={buyAmt} onChange={(e) => setBuyAmt(e.target.value)} className="bg-white/5 border-white/10" />
                    </div>
                    <div className="text-sm text-gray-400">You'll receive ≈ <span className="text-[#FFB000] font-mono">{(buyAmt / cfg.lono_price_usd).toFixed(2)} LONO</span></div>
                    <Button data-testid="buy-confirm" onClick={doBuy} className="w-full bg-[#FF3B30] hover:bg-[#FF5C53] rounded-full">Add $LONO</Button>
                  </div>
                </DialogContent>
              </Dialog>}
              {user?.plan === "free" && cfg.payments && <button onClick={() => checkout("premium")} data-testid="upgrade-premium-btn" className="flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full px-5 py-2.5 text-sm">
                <CreditCard className="w-4 h-4" /> Upgrade Premium
              </button>}
            </div>

            <div className="mt-6 flex items-center gap-2 text-xs text-gray-400">
              <span className="font-mono truncate">{data.address}</span>
              <button onClick={() => { navigator.clipboard.writeText(data.address); toast.success("Address copied"); }} className="p-1 rounded hover:bg-white/10"><Copy className="w-3 h-3" /></button>
            </div>
          </div>
        </div>

        {/* Side stats */}
        <div className="space-y-4">
          <div className="p-6 rounded-2xl bg-[#121212] border border-white/10">
            <div className="text-xs tracking-widest uppercase text-gray-400">Available</div>
            <div className="mt-2 font-display text-3xl">{data.wallet.lono_balance.toFixed(2)}</div>
          </div>
          <div className="p-6 rounded-2xl bg-[#121212] border border-white/10">
            <div className="text-xs tracking-widest uppercase text-gray-400">Staked</div>
            <div className="mt-2 font-display text-3xl">{data.wallet.staked.toFixed(2)}</div>
          </div>
          <div className="p-6 rounded-2xl bg-[#121212] border border-white/10">
            <div className="text-xs tracking-widest uppercase text-gray-400">Total Earned</div>
            <div className="mt-2 font-display text-3xl text-[#34C759]">{data.wallet.total_earned.toFixed(2)}</div>
          </div>
        </div>
      </div>

      {/* Stakes */}
      <div className="mt-12">
        <h2 className="font-display text-2xl mb-4 flex items-center gap-2"><Lock className="w-5 h-5 text-[#FF3B30]" /> Active Stakes</h2>
        {data.stakes.length === 0 ? (
          <div className="p-8 rounded-2xl border border-dashed border-white/10 text-gray-400 text-sm">
            You have no active stakes. Stake $LONO to earn up to 35% APY.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.stakes.map((s) => (
              <div key={s.id} className="p-5 rounded-2xl bg-[#121212] border border-white/10">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="text-xs uppercase tracking-widest text-gray-400">{s.lock_days}-day lock</div>
                    <div className="mt-1 font-display text-2xl">{s.amount} <span className="text-sm text-gray-400">LONO</span></div>
                  </div>
                  <div className="text-[#34C759] font-mono text-sm">{s.apy}% APY</div>
                </div>
                <div className="mt-3 text-xs text-gray-500">Unlocks: {new Date(s.unlock_at).toLocaleDateString()}</div>
                <button data-testid={`unstake-${s.id}`} onClick={() => doUnstake(s.id)} className="mt-4 w-full flex items-center justify-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full py-2 text-sm">
                  <Unlock className="w-3.5 h-3.5" /> {s.unlocked ? `Unstake with ${s.accrued.toFixed(2)} reward` : "Unstake early (no reward)"}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Stake dialog */}
      <Dialog open={stakeOpen} onOpenChange={setStakeOpen}>
        <DialogContent className="bg-[#0a0a0a] border-white/10 text-white">
          <DialogHeader><DialogTitle className="font-display">Stake $LONO</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-xs">Amount</Label>
              <Input data-testid="stake-amount" type="number" value={stakeForm.amount} onChange={(e) => setStakeForm({ ...stakeForm, amount: Number(e.target.value) })} className="bg-white/5 border-white/10" />
            </div>
            <div>
              <Label className="text-xs">Lock period</Label>
              <Select value={String(stakeForm.lock_days)} onValueChange={(v) => setStakeForm({ ...stakeForm, lock_days: Number(v) })}>
                <SelectTrigger data-testid="stake-lock" className="bg-white/5 border-white/10"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-[#0a0a0a] border-white/10 text-white">
                  <SelectItem value="30">30 days · 8% APY</SelectItem>
                  <SelectItem value="90">90 days · 14% APY</SelectItem>
                  <SelectItem value="180">180 days · 22% APY</SelectItem>
                  <SelectItem value="365">365 days · 35% APY</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button data-testid="stake-confirm" onClick={doStake} className="w-full bg-[#FF3B30] hover:bg-[#FF5C53] rounded-full">Confirm stake</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Transactions */}
      <div className="mt-12">
        <h2 className="font-display text-2xl mb-4 flex items-center gap-2"><Coins className="w-5 h-5 text-[#FFB000]" /> Transactions</h2>
        <div className="rounded-2xl overflow-hidden border border-white/10">
          <table className="w-full text-sm">
            <thead className="bg-white/[0.03] text-gray-400 uppercase text-xs tracking-widest">
              <tr><th className="text-left px-4 py-3">Type</th><th className="text-left px-4 py-3">Memo</th><th className="text-right px-4 py-3">Amount</th><th className="text-right px-4 py-3 hidden md:table-cell">Date</th></tr>
            </thead>
            <tbody>
              {tx.length === 0 && <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-500">No transactions yet.</td></tr>}
              {tx.map((t) => (
                <tr key={t.id} className="border-t border-white/5">
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 text-xs uppercase tracking-widest ${t.amount >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                      {t.amount >= 0 ? <ArrowDownRight className="w-3 h-3" /> : <ArrowUpRight className="w-3 h-3" />}
                      {t.kind.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-300 truncate max-w-xs">{t.memo}</td>
                  <td className={`px-4 py-3 text-right font-mono ${t.amount >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"}`}>{t.amount >= 0 ? "+" : ""}{t.amount.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right text-gray-500 hidden md:table-cell">{new Date(t.at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
