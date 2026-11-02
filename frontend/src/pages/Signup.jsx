import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import GoogleButton from "@/components/GoogleButton";
import { errorText } from "@/lib/api";

export default function Signup() {
  const { register, user } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (user) nav("/"); }, [user, nav]);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await register(form.email, form.password, form.name);
      toast.success("Welcome to LoNo! +100 $LONO bonus.");
      nav("/");
    } catch (err) {
      toast.error(errorText(err, "Registration failed"));
    } finally { setBusy(false); }
  };


  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-[#050505] text-white">
      <div className="relative hidden lg:block overflow-hidden">
        <img src="https://images.unsplash.com/photo-1759771963975-8a4885446f1f?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjh8MHwxfHNlYXJjaHwyfHxhYnN0cmFjdCUyMG5ldHdvcmslMjBub2RlJTIwZGFya3xlbnwwfHx8fDE3ODMyNTA2NDh8MA&ixlib=rb-4.1.0&q=85" alt="" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-br from-black/70 via-black/40 to-black/90" />
        <div className="absolute bottom-12 left-12 right-12">
          <h2 className="font-display text-5xl font-semibold leading-tight tracking-tighter">Get 100 $LONO<br />on signup.</h2>
          <p className="mt-4 text-gray-300 max-w-md">Watch, learn, and create — everything earns you tokens.</p>
        </div>
      </div>

      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <Link to="/" className="flex items-center gap-2 mb-8">
            <div className="w-9 h-9 rounded-xl bg-[#FF3B30] grid place-items-center font-black font-display">L</div>
            <span className="font-display text-2xl">LoNo</span>
          </Link>
          <h1 className="font-display text-3xl md:text-4xl tracking-tight">Create account</h1>
          <p className="mt-2 text-sm text-gray-400">Watch, listen and learn. Every verified minute earns $LONO.</p>

          <GoogleButton text="signup_with" />

          <form onSubmit={submit} className="mt-8 space-y-3">
            <input data-testid="signup-name" required placeholder="Full name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                   className="w-full bg-white/5 border border-white/10 rounded-full px-5 py-3 focus:outline-none focus:ring-2 focus:ring-[#FF3B30]/40" />
            <input data-testid="signup-email" required type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                   className="w-full bg-white/5 border border-white/10 rounded-full px-5 py-3 focus:outline-none focus:ring-2 focus:ring-[#FF3B30]/40" />
            <input data-testid="signup-password" required type="password" placeholder="Password (min 8 chars)" minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
                   className="w-full bg-white/5 border border-white/10 rounded-full px-5 py-3 focus:outline-none focus:ring-2 focus:ring-[#FF3B30]/40" />
            <button data-testid="signup-submit" disabled={busy} className="w-full bg-[#FF3B30] hover:bg-[#FF5C53] rounded-full py-3 font-medium disabled:opacity-50 flex items-center justify-center gap-2">
              {busy && <Loader2 className="w-4 h-4 animate-spin" />} Create account
            </button>
          </form>

          <p className="mt-6 text-sm text-gray-400 text-center">
            Already have an account? <Link to="/login" className="text-white font-medium hover:text-[#FF3B30]">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
