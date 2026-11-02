import { useEffect, useState } from "react";
import { api, errorText } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useAuth } from "@/lib/auth";
import { Loader2, Vote, Clock, CheckCircle, XCircle, Plus } from "lucide-react";
import { toast } from "sonner";

const Bar = ({ label, value, total, color }) => {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-400 mb-1"><span>{label}</span><span className="font-mono">{pct}%</span></div>
      <div className="h-2 bg-white/5 rounded-full overflow-hidden"><div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} /></div>
    </div>
  );
};

export default function Governance() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState({ title: "", summary: "", days: 7 });
  const [props, setProps] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => { const { data } = await api.get("/governance/proposals"); setProps(data); setLoading(false); };
  useEffect(() => { load(); }, []);

  const vote = async (id, choice) => {
    if (!user) { toast.error("Sign in to vote"); return; }
    try {
      const { data } = await api.post("/governance/vote", { proposal_id: id, choice });
      toast.success(`Voted with ${data.power.toFixed(0)} voting power`);
      load();
    } catch (e) { toast.error(errorText(e, "Your vote didn't go through")); }
  };

  const propose = async (e) => {
    e.preventDefault();
    try {
      await api.post("/governance/proposals", { ...draft, days: Number(draft.days) });
      toast.success("Proposal submitted"); setOpen(false); setDraft({ title: "", summary: "", days: 7 }); load();
    } catch (err) { toast.error(errorText(err, "Your proposal wasn't submitted")); }
  };

  if (loading) return <div className="min-h-[70vh] grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>;

  return (
    <div data-testid="governance-page" className="max-w-[1600px] mx-auto px-4 md:px-8 pt-8 pb-24">
      <div className="text-[10px] tracking-[0.3em] font-bold text-[#FFB000] uppercase mb-2">LoNo DAO</div>
      <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tighter">Governance</h1>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
        <p className="text-gray-400 max-w-2xl">Token holders decide how LoNo's funds and features change. Your voting power is your balance plus twice what you've staked. One vote per proposal.</p>
        {user && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <button data-testid="new-proposal" className="flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full px-4 py-2 text-sm"><Plus className="w-4 h-4" /> New proposal</button>
            </DialogTrigger>
            <DialogContent className="bg-[#121212] border-white/10 text-white">
              <DialogHeader><DialogTitle className="font-display">New proposal</DialogTitle></DialogHeader>
              <p className="text-sm text-gray-400">You need at least 100 $LONO staked to submit a proposal.</p>
              <form onSubmit={propose} className="space-y-3">
                <input required minLength={8} maxLength={120} placeholder="Title" value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#FF3B30]/40" />
                <textarea required minLength={20} maxLength={2000} rows={4} placeholder="What should change, and why?" value={draft.summary} onChange={(e) => setDraft({ ...draft, summary: e.target.value })}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#FF3B30]/40" />
                <label className="flex items-center gap-3 text-sm text-gray-300">Voting runs for
                  <select value={draft.days} onChange={(e) => setDraft({ ...draft, days: e.target.value })} className="bg-white/5 border border-white/10 rounded-lg px-3 py-2">
                    <option value={3}>3 days</option><option value={7}>7 days</option><option value={14}>14 days</option>
                  </select>
                </label>
                <button className="w-full bg-[#FF3B30] hover:bg-[#FF5C53] rounded-full py-2.5 font-medium">Submit proposal</button>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      <div className="mt-10 grid grid-cols-1 md:grid-cols-2 gap-4">
        {props.map((p) => {
          const votes = p.votes || { for: 0, against: 0, abstain: 0 };
          const total = votes.for + votes.against + votes.abstain;
          const active = p.status === "active";
          return (
            <div key={p.id} data-testid={`proposal-${p.id}`} className="p-6 rounded-2xl bg-[#121212] border border-white/10">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className={`text-xs font-medium ${active ? "text-[#FFB000]" : p.status === "passed" ? "text-[#34C759]" : "text-gray-500"}`}>
                    {active ? "Voting open" : p.status === "passed" ? "Passed" : "Rejected"}
                  </div>
                  <h3 className="mt-1 font-display text-lg leading-tight">{p.title}</h3>
                </div>
                {active ? <Clock className="w-4 h-4 text-gray-400 mt-1" /> : p.status === "passed" ? <CheckCircle className="w-4 h-4 text-[#34C759] mt-1" /> : <XCircle className="w-4 h-4 text-gray-500 mt-1" />}
              </div>
              <p className="mt-3 text-sm text-gray-400">{p.summary}</p>
              <div className="mt-5 space-y-2.5">
                <Bar label="For" value={votes.for} total={total} color="#34C759" />
                <Bar label="Against" value={votes.against} total={total} color="#FF3B30" />
                <Bar label="Abstain" value={votes.abstain} total={total} color="#666" />
              </div>
              {p.my_vote && <div className="mt-5 text-sm text-gray-300">You voted <span className="font-medium text-white">{p.my_vote}</span>.</div>}
              {active && !p.my_vote && (
                <div className="mt-5 grid grid-cols-3 gap-2">
                  <button data-testid={`vote-for-${p.id}`} onClick={() => vote(p.id, "for")} className="flex items-center justify-center gap-1 bg-[#34C759]/10 text-[#34C759] hover:bg-[#34C759]/20 rounded-full py-2 text-xs uppercase tracking-widest">
                    <Vote className="w-3.5 h-3.5" /> For
                  </button>
                  <button data-testid={`vote-against-${p.id}`} onClick={() => vote(p.id, "against")} className="flex items-center justify-center gap-1 bg-[#FF3B30]/10 text-[#FF3B30] hover:bg-[#FF3B30]/20 rounded-full py-2 text-xs uppercase tracking-widest">
                    <Vote className="w-3.5 h-3.5" /> Against
                  </button>
                  <button data-testid={`vote-abstain-${p.id}`} onClick={() => vote(p.id, "abstain")} className="bg-white/5 hover:bg-white/10 rounded-full py-2 text-xs uppercase tracking-widest text-gray-400">
                    Abstain
                  </button>
                </div>
              )}
              <div className="mt-3 text-xs text-gray-500">{active ? "Closes" : "Closed"} {new Date(p.ends_at).toLocaleDateString()}{p.author_name ? ` / proposed by ${p.author_name}` : ""}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
