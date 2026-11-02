import { NavLink } from "react-router-dom";
import { Home, Radio, GraduationCap, Search, Wallet, User } from "lucide-react";
import { useAuth } from "@/lib/auth";

/** Bottom tab bar for phones; the top navbar's links are hidden below lg. */
export default function MobileNav() {
  const { user } = useAuth();
  const tabs = [
    { to: "/", label: "Home", icon: Home },
    { to: "/live", label: "Live", icon: Radio },
    { to: "/learn", label: "Learn", icon: GraduationCap },
    { to: "/search", label: "Search", icon: Search },
    user ? { to: "/wallet", label: "Wallet", icon: Wallet } : { to: "/login", label: "Sign in", icon: User },
  ];
  return (
    <nav aria-label="Main" data-testid="mobile-nav"
      className="lg:hidden fixed bottom-0 inset-x-0 z-50 bg-[#050505]/95 backdrop-blur-xl border-t border-white/10"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
      <ul className="grid grid-cols-5">
        {tabs.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <NavLink to={to} end={to === "/"}
              className={({ isActive }) => `flex flex-col items-center gap-1 py-2.5 text-[11px] ${isActive ? "text-white" : "text-gray-500"}`}>
              <Icon className="w-5 h-5" />{label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
