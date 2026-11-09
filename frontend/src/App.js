import "@/App.css";
import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/lib/auth";
import Navbar from "@/components/Navbar";
import AIChatFloat from "@/components/AIChatFloat";
import Home from "@/pages/Home";
import MobileNav from "@/components/MobileNav";
import TermsBanner from "@/components/TermsBanner";
import FocusRestorer from "@/components/FocusRestorer";
import InstallBanner from "@/components/InstallBanner";

// After a new deploy, an open tab may ask for page files that no longer exist.
// Reload once to pick up the new version instead of showing a broken page.
const page = (load) => lazy(() => load().then((mod) => {
  sessionStorage.removeItem("lono_reloaded");
  return mod;
}).catch((err) => {
  if (!sessionStorage.getItem("lono_reloaded")) {
    sessionStorage.setItem("lono_reloaded", "1");
    window.location.reload();
    return new Promise(() => {});
  }
  throw err;
}));

// Home loads with the app; every other page downloads the first time it's opened,
// which keeps the first load small on mobile data.
const Watch = page(() => import("@/pages/Watch"));
const Live = page(() => import("@/pages/Live"));
const Browse = page(() => import("@/pages/Browse"));
const Search = page(() => import("@/pages/Search"));
const Channel = page(() => import("@/pages/Channel"));
const Studio = page(() => import("@/pages/Studio"));
const Wallet = page(() => import("@/pages/Wallet"));
const Tokenomics = page(() => import("@/pages/Tokenomics"));
const Governance = page(() => import("@/pages/Governance"));
const Login = page(() => import("@/pages/Login"));
const Signup = page(() => import("@/pages/Signup"));
const Profile = page(() => import("@/pages/Profile"));
const Learn = page(() => import("@/pages/Learn"));
const Course = page(() => import("@/pages/Course"));
const Certificate = page(() => import("@/pages/Certificate"));
const CourseEditor = page(() => import("@/pages/CourseEditor"));
const Settings = page(() => import("@/pages/Settings"));
const Terms = page(() => import("@/pages/Terms"));
const LivePlayer = page(() => import("@/pages/LivePlayer"));
const LiveStudio = page(() => import("@/pages/LiveStudio"));
const Join = page(() => import("@/pages/Join"));
const ControlRoom = page(() => import("@/pages/ControlRoom"));
const DeveloperAccess = page(() => import("@/pages/DeveloperAccess"));
const OffersList = page(() => import("@/pages/Offers").then((m) => ({ default: m.OffersList })));
const OfferDetail = page(() => import("@/pages/Offers").then((m) => ({ default: m.OfferDetail })));
const MyPasses = page(() => import("@/pages/Passes").then((m) => ({ default: m.MyPasses })));
const PassPlayer = page(() => import("@/pages/Passes").then((m) => ({ default: m.PassPlayer })));
const Admin = page(() => import("@/pages/Admin"));

const PageLoading = () => (
  <div className="min-h-[60vh] grid place-items-center" role="status" aria-label="Loading">
    <div className="w-8 h-8 rounded-full border-2 border-white/15 border-t-[#FF3B30] animate-spin" />
  </div>
);

const Protected = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen bg-[#050505]" />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
};

const Shell = ({ children }) => (
  <div className="min-h-screen bg-[#050505] text-white">
    <Navbar />
    <TermsBanner />
    <main className="pb-16 lg:pb-0"><Suspense fallback={<PageLoading />}>{children}</Suspense></main>
    <AIChatFloat />
    <InstallBanner />
    <MobileNav />
  </div>
);

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster theme="dark" position="top-right" richColors />
        <FocusRestorer />
        <Suspense fallback={<div className="min-h-screen bg-[#050505]"><PageLoading /></div>}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/profile" element={<Protected><Shell><Profile /></Shell></Protected>} />
          <Route path="/" element={<Shell><Home /></Shell>} />
          <Route path="/watch/:id" element={<Shell><Watch /></Shell>} />
          <Route path="/live" element={<Shell><Live /></Shell>} />
          <Route path="/browse/:kind" element={<Shell><Browse /></Shell>} />
          <Route path="/search" element={<Shell><Search /></Shell>} />
          <Route path="/channel/:id" element={<Shell><Channel /></Shell>} />
          <Route path="/studio" element={<Protected><Shell><Studio /></Shell></Protected>} />
          <Route path="/wallet" element={<Protected><Shell><Wallet /></Shell></Protected>} />
          <Route path="/join/:token" element={<Join />} />
          <Route path="/studio/control/:roomId?" element={<Protected><Shell><ControlRoom /></Shell></Protected>} />
          <Route path="/offers" element={<Protected><Shell><OffersList /></Shell></Protected>} />
          <Route path="/offers/:id" element={<Protected><Shell><OfferDetail /></Shell></Protected>} />
          <Route path="/passes" element={<Protected><Shell><MyPasses /></Shell></Protected>} />
          <Route path="/passes/:id" element={<Protected><Shell><PassPlayer /></Shell></Protected>} />
          <Route path="/studio/developers" element={<Protected><Shell><DeveloperAccess /></Shell></Protected>} />
          <Route path="/studio/live" element={<Protected><Shell><LiveStudio /></Shell></Protected>} />
          <Route path="/studio/courses/:id" element={<Protected><Shell><CourseEditor /></Shell></Protected>} />
          <Route path="/live/play/:id" element={<Suspense fallback={<div className="fixed inset-0 bg-black" />}><LivePlayer /></Suspense>} />
          <Route path="/terms" element={<Shell><Terms /></Shell>} />
          <Route path="/admin" element={<Protected><Shell><Admin /></Shell></Protected>} />
          <Route path="/settings" element={<Protected><Shell><Settings /></Shell></Protected>} />
          <Route path="/learn" element={<Shell><Learn /></Shell>} />
          <Route path="/learn/:id" element={<Shell><Course /></Shell>} />
          <Route path="/certificates/:id" element={<Shell><Certificate /></Shell>} />
          <Route path="/tokenomics" element={<Shell><Tokenomics /></Shell>} />
          <Route path="/governance" element={<Shell><Governance /></Shell>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  );
}
