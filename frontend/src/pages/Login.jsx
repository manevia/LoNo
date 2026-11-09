import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import GoogleButton from "@/components/GoogleButton";
import { errorText } from "@/lib/api";

export default function Login() {
  const { login, user } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (user) nav("/"); }, [user, nav]);


  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(form.email, form.password);
      toast.success("Welcome back");
      nav("/");
    } catch (err) {
      toast.error(errorText(err, "Sign in failed"));
    } finally { setBusy(false); }
  };


  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-[#050505] text-white">
      <div className="relative hidden lg:block overflow-hidden">
        <img loading="lazy" decoding="async" src="https://images.unsplash.com/photo-1782020934325-cfe4cea4fd9c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1NzZ8MHwxfHNlYXJjaHwyfHxjaW5lbWF0aWMlMjBtb3ZpZSUyMHBvc3RlciUyMGRhcmt8ZW58MHx8fHwxNzgzMjUwNjQ4fDA&ixlib=rb-4.1.0&q=85" alt="" className="absolute inset-0 w-full h-full object-cover" />
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

          <GoogleButton text="signin_with" />

          <form onSubmit={submit} className="mt-8 space-y-3">
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
