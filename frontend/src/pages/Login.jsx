import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

export default function Login() {
  const { login, googleExchange, user } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (user) nav("/"); }, [user, nav]);

  // Emergent Google session exchange
  useEffect(() => {
    const hash = window.location.hash;
    const m = hash.match(/session_id=([^&]+)/);
    if (m) {
      (async () => {
        try {
          await googleExchange(m[1]);
          window.history.replaceState(null, "", "/");
          toast.success("Signed in with Google");
          nav("/");
        } catch { toast.error("Google sign-in failed"); }
      })();
    }
  }, [googleExchange, nav]);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(form.email, form.password);
      toast.success("Welcome back");
      nav("/");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Sign in failed");
    } finally { setBusy(false); }
  };

  const google = () => {
    const redirect = `${window.location.origin}/login`;
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirect)}`;
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-[#050505] text-white">
      <div className="relative hidden lg:block overflow-hidden">
        <img src="https://images.unsplash.com/photo-1782020934325-cfe4cea4fd9c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1NzZ8MHwxfHNlYXJjaHwyfHxjaW5lbWF0aWMlMjBtb3ZpZSUyMHBvc3RlciUyMGRhcmt8ZW58MHx8fHwxNzgzMjUwNjQ4fDA&ixlib=rb-4.1.0&q=85" alt="" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-br from-black/60 via-black/40 to-black/80" />
        <div className="absolute bottom-12 left-12 right-12">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-xl bg-[#FF3B30] grid place-items-center font-black font-display">L</div>
            <span className="font-display text-2xl">LoNo</span>
          </Link>
          <h2 className="mt-12 font-display text-5xl font-semibold leading-tight tracking-tighter">Watch. Listen.<br />Learn. Earn.</h2>
          <p className="mt-4 text-gray-300 max-w-md">Enter the world's first hybrid media, broadcasting & Web3 ecosystem.</p>
        </div>
      </div>

      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <Link to="/" className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-9 h-9 rounded-xl bg-[#FF3B30] grid place-items-center font-black font-display">L</div>
            <span className="font-display text-2xl">LoNo</span>
          </Link>
          <h1 className="font-display text-3xl md:text-4xl tracking-tight">Sign in</h1>
          <p className="mt-2 text-sm text-gray-400">Welcome back to your LoNo account.</p>

          <button data-testid="login-google-btn" onClick={google} className="mt-8 w-full flex items-center justify-center gap-3 bg-white text-black rounded-full py-3 font-medium hover:bg-gray-200 transition">
            <svg width="18" height="18" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z"/><path fill="#FBBC05" d="M5.84 14.09A6.5 6.5 0 0 1 5.5 12c0-.72.12-1.42.34-2.09V7.07H2.18A11 11 0 0 0 1 12c0 1.77.42 3.45 1.18 4.93l2.85-2.22z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.07l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z"/></svg>
            Continue with Google
          </button>

          <div className="my-6 flex items-center gap-3 text-xs text-gray-500 uppercase tracking-widest">
            <div className="flex-1 h-px bg-white/10" /> Or <div className="flex-1 h-px bg-white/10" />
          </div>

          <form onSubmit={submit} className="space-y-3">
            <input data-testid="login-email" required type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                   className="w-full bg-white/5 border border-white/10 rounded-full px-5 py-3 focus:outline-none focus:ring-2 focus:ring-[#FF3B30]/40" />
            <input data-testid="login-password" required type="password" placeholder="Password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
                   className="w-full bg-white/5 border border-white/10 rounded-full px-5 py-3 focus:outline-none focus:ring-2 focus:ring-[#FF3B30]/40" />
            <button data-testid="login-submit" disabled={busy} className="w-full bg-[#FF3B30] hover:bg-[#FF5C53] rounded-full py-3 font-medium disabled:opacity-50 flex items-center justify-center gap-2">
              {busy && <Loader2 className="w-4 h-4 animate-spin" />} Sign in
            </button>
          </form>

          <p className="mt-6 text-sm text-gray-400 text-center">
            Don't have an account? <Link to="/signup" className="text-white font-medium hover:text-[#FF3B30]">Create one</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
