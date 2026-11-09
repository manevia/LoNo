import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Search, Radio, Wallet, User, LogOut, Home, Compass, Vote, BarChart3, Sparkles, Video, GraduationCap, ShieldCheck, Settings , Gift } from "lucide-react";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useState, useEffect } from "react";

const NAV = [
  { to: "/", label: "Home", icon: Home },
  { to: "/browse/movie", label: "Movies", icon: Compass },
  { to: "/browse/series", label: "Series", icon: Video },
  { to: "/browse/podcast", label: "Podcasts", icon: Radio },
  { to: "/live", label: "Live", icon: Radio },
  { to: "/learn", label: "Learn", icon: GraduationCap },
  { to: "/offers", label: "Offers", icon: Gift },
  { to: "/tokenomics", label: "Token", icon: BarChart3 },
  { to: "/governance", label: "DAO", icon: Vote },
];

export default function Navbar() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const onSearch = (e) => {
    e.preventDefault();
    if (q.trim()) nav(`/search?q=${encodeURIComponent(q.trim())}`);
  };

  return (
    <header
      data-testid="main-navbar"
      className={`sticky top-0 z-50 transition-all duration-300 ${
        scrolled ? "bg-[#050505]/90 backdrop-blur-xl border-b border-white/5" : "bg-gradient-to-b from-[#050505]/80 to-transparent"
      }`}
    >
      <div className="max-w-[1600px] mx-auto px-4 md:px-8 h-16 flex items-center gap-6">
        <Link to="/" data-testid="nav-logo" className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-xl bg-[#FF3B30] grid place-items-center text-white font-black text-lg font-display">
            L
          </div>
          <span className="font-display text-2xl font-semibold tracking-tighter">LoNo</span>
        </Link>

        <nav className="hidden lg:flex items-center gap-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              data-testid={`nav-${n.label.toLowerCase()}`}
              className={({ isActive }) =>
                `px-3 py-2 text-sm rounded-full transition-colors ${
                  isActive ? "text-white bg-white/10" : "text-gray-400 hover:text-white"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>

        <form onSubmit={onSearch} className="ml-auto hidden md:flex items-center relative">
          <Search className="w-4 h-4 text-gray-500 absolute left-3 pointer-events-none" />
          <input
            data-testid="nav-search-input"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search shows, music, courses…"
            aria-label="Search"
            className="bg-white/5 border border-white/10 rounded-full pl-10 pr-4 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-[#FF3B30]/40 focus:w-80 transition-all"
          />
        </form>

        {user ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button data-testid="nav-avatar-btn" className="flex items-center gap-2 rounded-full pl-2 pr-3 py-1.5 hover:bg-white/5">
                <img loading="lazy" decoding="async" src={user.avatar_url} alt="" className="w-8 h-8 rounded-full ring-2 ring-white/10" />
                <span className="hidden md:block text-sm font-medium max-w-[100px] truncate">{user.name}</span>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="bg-[#121212] border-white/10 text-white w-56">
              <DropdownMenuLabel>
                <div className="text-sm font-medium truncate">{user.name}</div>
                <div className="text-xs text-gray-400 truncate">{user.email}</div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator className="bg-white/10" />
              <DropdownMenuItem data-testid="menu-wallet" onClick={() => nav("/wallet")} className="cursor-pointer focus:bg-white/10">
                <Wallet className="w-4 h-4 mr-2" /> Wallet
                <span className="ml-auto text-[#FFB000] font-mono text-xs">{user.wallet?.lono_balance?.toFixed(2)} LONO</span>
              </DropdownMenuItem>
              <DropdownMenuItem data-testid="menu-studio" onClick={() => nav("/studio")} className="cursor-pointer focus:bg-white/10">
                <Sparkles className="w-4 h-4 mr-2" /> Creator Studio
              </DropdownMenuItem>
              <DropdownMenuItem data-testid="menu-profile" onClick={() => nav("/profile")} className="cursor-pointer focus:bg-white/10">
                <User className="w-4 h-4 mr-2" /> Profile
              </DropdownMenuItem>
              <DropdownMenuItem data-testid="menu-settings" onClick={() => nav("/settings")} className="cursor-pointer focus:bg-white/10">
                <Settings className="w-4 h-4 mr-2" /> Settings
              </DropdownMenuItem>
              {user.is_admin && (
                <DropdownMenuItem data-testid="menu-admin" onClick={() => nav("/admin")} className="cursor-pointer focus:bg-white/10">
                  <ShieldCheck className="w-4 h-4 mr-2" /> Admin
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator className="bg-white/10" />
              <DropdownMenuItem data-testid="menu-logout" onClick={() => { logout(); nav("/"); }} className="cursor-pointer focus:bg-white/10 text-[#FF3B30]">
                <LogOut className="w-4 h-4 mr-2" /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <div className="flex items-center gap-2">
            <Link data-testid="nav-signin" to="/login" className="text-sm text-gray-300 hover:text-white px-3 py-2">Sign in</Link>
            <Link data-testid="nav-getstarted" to="/signup" className="text-sm bg-[#FF3B30] hover:bg-[#FF5C53] rounded-full px-4 py-2 font-medium">
              Get Started
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
