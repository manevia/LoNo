import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { Loader2, ShieldCheck, ShieldAlert, Printer, Copy } from "lucide-react";
import { toast } from "sonner";

export default function Certificate() {
  const { id } = useParams();
  const [cert, setCert] = useState(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => { api.get(`/learn/certificates/${id}`).then(({ data }) => setCert(data)).catch(() => setMissing(true)); }, [id]);

  if (missing) return <div className="min-h-[60vh] grid place-items-center text-gray-400 px-6 text-center">No certificate has this ID. Check the link and try again.</div>;
  if (!cert) return <div className="min-h-[70vh] grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>;

  const issued = new Date(cert.issued_at).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
  const copy = async () => { await navigator.clipboard.writeText(window.location.href); toast.success("Verification link copied"); };

  return (
    <div data-testid="certificate-page" className="max-w-4xl mx-auto px-4 md:px-8 pt-10 pb-32">
      <div className={`flex items-center gap-2 text-sm ${cert.valid ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
        {cert.valid ? <ShieldCheck className="w-4 h-4" /> : <ShieldAlert className="w-4 h-4" />}
        {cert.valid ? "Verified: this certificate matches LoNo's records." : "Not valid: this certificate's details don't match its fingerprint."}
      </div>

      <div className="cert mt-6 relative overflow-hidden rounded-2xl p-8 md:p-14 bg-[#0d0b07] border border-[#FFB000]/30">
        <div aria-hidden className="absolute inset-3 rounded-xl border border-[#FFB000]/15 pointer-events-none" />
        <div className="relative">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-[#FF3B30] grid place-items-center font-black font-display text-sm">L</div>
            <span className="font-display text-lg">LoNo Learn</span>
          </div>
          <p className="mt-12 text-gray-400">This certifies that</p>
          <p className="mt-2 font-display text-4xl md:text-6xl font-semibold tracking-tighter text-[#FFB000] break-words">{cert.user_name}</p>
          <p className="mt-6 text-gray-400">completed the course and passed its final assessment</p>
          <p className="mt-2 font-display text-2xl md:text-3xl tracking-tight">{cert.course_title}</p>
          <div className="mt-12 grid grid-cols-2 md:grid-cols-3 gap-6 text-sm">
            <div><div className="text-gray-500">Issued</div><div className="mt-1">{issued}</div></div>
            <div><div className="text-gray-500">Score</div><div className="mt-1 tabular-nums">{Math.round(cert.score * 100)}%</div></div>
            <div className="col-span-2 md:col-span-1"><div className="text-gray-500">Certificate ID</div><div className="mt-1 break-all text-xs">{cert.id}</div></div>
          </div>
          <div className="mt-8 pt-6 border-t border-white/10 text-xs text-gray-500">
            <div>SHA-256 fingerprint</div>
            <div className="mt-1 break-all font-mono text-gray-400">{cert.fingerprint}</div>
          </div>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-2 print:hidden">
        <button onClick={copy} className="flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full px-4 py-2 text-sm"><Copy className="w-4 h-4" /> Copy verification link</button>
        <button onClick={() => window.print()} className="flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full px-4 py-2 text-sm"><Printer className="w-4 h-4" /> Print or save as PDF</button>
        <Link to="/learn" className="flex items-center gap-2 px-4 py-2 text-sm text-gray-400 hover:text-white">Browse more courses</Link>
      </div>
    </div>
  );
}
