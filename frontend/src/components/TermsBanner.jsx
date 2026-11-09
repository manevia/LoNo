import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Asks signed-in users to accept the current terms version when it has changed. */
export default function TermsBanner() {
  const { user, refresh } = useAuth();
  const [busy, setBusy] = useState(false);
  if (!user?.needs_terms) return null;
  const accept = async () => {
    setBusy(true);
    try { await api.post("/auth/accept-terms"); await refresh(); toast.success("Thanks, you're all set"); }
    catch { toast.error("That didn't save. Try again."); } finally { setBusy(false); }
  };
  return (
    <div role="region" aria-label="Updated terms" data-testid="terms-banner"
      className="bg-[#FFB000]/10 border-b border-[#FFB000]/30">
      <div className="max-w-[1600px] mx-auto px-4 md:px-8 py-3 flex flex-wrap items-center gap-3 text-sm">
        <span className="text-gray-200">We've updated our <Link to="/terms" className="underline text-white">Terms and $LONO disclosure</Link>. Please review and accept them to keep using LoNo.</span>
        <button onClick={accept} disabled={busy} data-testid="terms-accept"
          className="ml-auto bg-[#FFB000] text-black rounded-full px-4 py-1.5 font-medium disabled:opacity-50">I accept</button>
      </div>
    </div>
  );
}
