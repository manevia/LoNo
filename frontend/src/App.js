import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/lib/auth";
import Navbar from "@/components/Navbar";
import AIChatFloat from "@/components/AIChatFloat";
import Home from "@/pages/Home";
import Watch from "@/pages/Watch";
import Live from "@/pages/Live";
import Browse from "@/pages/Browse";
import Search from "@/pages/Search";
import Channel from "@/pages/Channel";
import Studio from "@/pages/Studio";
import Wallet from "@/pages/Wallet";
import Tokenomics from "@/pages/Tokenomics";
import Governance from "@/pages/Governance";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import Profile from "@/pages/Profile";
import Learn from "@/pages/Learn";
import Course from "@/pages/Course";
import Certificate from "@/pages/Certificate";
import MobileNav from "@/components/MobileNav";

const Protected = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen bg-[#050505]" />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
};

const Shell = ({ children }) => (
  <div className="min-h-screen bg-[#050505] text-white">
    <Navbar />
    <main className="pb-16 lg:pb-0">{children}</main>
    <AIChatFloat />
    <MobileNav />
  </div>
);

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster theme="dark" position="top-right" richColors />
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
          <Route path="/learn" element={<Shell><Learn /></Shell>} />
          <Route path="/learn/:id" element={<Shell><Course /></Shell>} />
          <Route path="/certificates/:id" element={<Shell><Certificate /></Shell>} />
          <Route path="/tokenomics" element={<Shell><Tokenomics /></Shell>} />
          <Route path="/governance" element={<Shell><Governance /></Shell>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
