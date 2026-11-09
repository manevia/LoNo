import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Download, Loader2 } from "lucide-react";
import { api, errorText } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const field = "w-full bg-white/5 border border-white/10 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#FFB000]/40";
const card = "p-5 md:p-6 rounded-2xl bg-[#121212] border border-white/10";
const primary = "bg-white text-black rounded-full px-5 py-2.5 text-sm font-medium hover:bg-gray-200 disabled:opacity-50";

export default function Settings() {
  const { user, refresh, logout } = useAuth();
  const nav = useNavigate();
  const [name, setName] = useState(user?.name || "");
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [del, setDel] = useState({ confirm_email: "", password: "" });
  const [busy, setBusy] = useState("");

  if (!user) return null;
  const run = async (key, fn) => { setBusy(key); try { await fn(); } finally { setBusy(""); } };

  const saveName = (e) => { e.preventDefault(); run("name", async () => {
    try { await api.patch("/auth/me", { name }); await refresh(); toast.success("Name updated"); }
    catch (err) { toast.error(errorText(err)); }
  }); };

  const savePw = (e) => { e.preventDefault(); run("pw", async () => {
    try {
      await api.post("/auth/password", user.has_password ? pw : { new_password: pw.new_password });
      setPw({ current_password: "", new_password: "" }); await refresh();
      toast.success(user.has_password ? "Password changed" : "Password set. You can now also sign in with your email.");
    } catch (err) { toast.error(errorText(err, "Password wasn't changed")); }
  }); };

  const exportData = () => run("export", async () => {
    try {
      const { data, headers } = await api.get("/me/export", { responseType: "blob" });
      const name = /filename="([^"]+)"/.exec(headers["content-disposition"] || "")?.[1] || "lono-data.json";
      const url = URL.createObjectURL(data);
      const a = Object.assign(document.createElement("a"), { href: url, download: name });
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
      toast.success("Your data was downloaded");
    } catch (err) { toast.error("The export failed. Try again."); }
  });

  const deleteAccount = (e) => { e.preventDefault(); run("delete", async () => {
    try {
      await api.request({ method: "delete", url: "/me", data: del });
      logout(); nav("/"); toast("Your account and data were deleted");
    } catch (err) { toast.error(errorText(err, "Your account wasn't deleted")); }
  }); };

  const emailMatches = del.confirm_email.trim().toLowerCase() === user.email;

  return (
    <div data-testid="settings-page" className="max-w-2xl mx-auto px-4 md:px-8 pt-10 pb-32">
      <Link to="/profile" className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white"><ArrowLeft className="w-4 h-4" /> Profile</Link>
      <h1 className="mt-3 font-display text-3xl md:text-4xl font-semibold tracking-tight">Settings</h1>
      <p className="mt-2 text-sm text-gray-400">Signed in as {user.email}</p>

      <section className="mt-10" aria-labelledby="s-profile">
        <h2 id="s-profile" className="font-display text-xl mb-3">Profile</h2>
        <form onSubmit={saveName} className={`${card} flex flex-col sm:flex-row gap-3 sm:items-end`}>
          <label className="flex-1"><span className="text-sm text-gray-400">Display name</span>
            <input data-testid="settings-name" required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} className={`${field} mt-1.5`} /></label>
          <button disabled={busy === "name" || !name.trim() || name.trim() === user.name} className={primary}>Save</button>
        </form>
      </section>

      <section className="mt-10" aria-labelledby="s-password">
        <h2 id="s-password" className="font-display text-xl mb-3">{user.has_password ? "Password" : "Set a password"}</h2>
        <form onSubmit={savePw} className={`${card} space-y-3`}>
          {!user.has_password && <p className="text-sm text-gray-400">You signed up with Google. Add a password to also sign in with your email.</p>}
          {user.has_password && (
            <label className="block"><span className="text-sm text-gray-400">Current password</span>
              <input type="password" autoComplete="current-password" required value={pw.current_password}
                onChange={(e) => setPw({ ...pw, current_password: e.target.value })} className={`${field} mt-1.5`} /></label>
          )}
          <label className="block"><span className="text-sm text-gray-400">New password (8 characters or more)</span>
            <input data-testid="settings-new-password" type="password" autoComplete="new-password" required minLength={8} value={pw.new_password}
              onChange={(e) => setPw({ ...pw, new_password: e.target.value })} className={`${field} mt-1.5`} /></label>
          <button disabled={busy === "pw"} className={primary}>{user.has_password ? "Change password" : "Set password"}</button>
        </form>
      </section>

      <section className="mt-10" aria-labelledby="s-data">
        <h2 id="s-data" className="font-display text-xl mb-3">Your data</h2>
        <div className={card}>
          <p className="text-sm text-gray-300">Download everything LoNo stores about you: your profile, wallet history, stakes, watch history, votes, courses, certificates, reviews and uploads, as one JSON file.</p>
          <button data-testid="export-data" onClick={exportData} disabled={busy === "export"}
            className="mt-4 inline-flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full px-5 py-2.5 text-sm disabled:opacity-50">
            {busy === "export" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />} Download my data
          </button>
        </div>
      </section>

      <section className="mt-10" aria-labelledby="s-delete">
        <h2 id="s-delete" className="font-display text-xl mb-3 text-[#FF8A82]">Delete account</h2>
        <form onSubmit={deleteAccount} className="p-5 md:p-6 rounded-2xl border border-[#FF3B30]/30 bg-[#FF3B30]/[0.05] space-y-3">
          <p className="text-sm text-gray-300">
            This permanently deletes your account, $LONO balance and stakes, history, certificates, reviews, channel, uploads and courses.
            It can't be undone. Vote totals and view counts you contributed to stay, with no link to you.
          </p>
          <label className="block"><span className="text-sm text-gray-400">Type <span className="text-white">{user.email}</span> to confirm</span>
            <input data-testid="delete-confirm-email" autoComplete="off" value={del.confirm_email} onChange={(e) => setDel({ ...del, confirm_email: e.target.value })} className={`${field} mt-1.5`} /></label>
          {user.has_password && (
            <label className="block"><span className="text-sm text-gray-400">Password</span>
              <input data-testid="delete-password" type="password" autoComplete="current-password" value={del.password}
                onChange={(e) => setDel({ ...del, password: e.target.value })} className={`${field} mt-1.5`} /></label>
          )}
          <button data-testid="delete-account" disabled={!emailMatches || (user.has_password && !del.password) || busy === "delete"}
            className="bg-[#FF3B30] hover:bg-[#FF5C53] rounded-full px-5 py-2.5 text-sm font-medium disabled:opacity-40">
            Delete my account for good
          </button>
        </form>
      </section>
    </div>
  );
}
