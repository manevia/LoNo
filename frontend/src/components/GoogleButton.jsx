import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { useConfig } from "@/lib/config";
import { errorText } from "@/lib/api";

const GIS_SRC = "https://accounts.google.com/gsi/client";

function loadGis() {
  if (window.google?.accounts?.id) return Promise.resolve();
  return new Promise((resolve, reject) => {
    let s = document.querySelector(`script[src="${GIS_SRC}"]`);
    if (!s) {
      s = document.createElement("script");
      s.src = GIS_SRC; s.async = true;
      document.head.appendChild(s);
    }
    s.addEventListener("load", resolve);
    s.addEventListener("error", reject);
  });
}

/** Renders Google's own sign-in button. Renders nothing when Google sign-in isn't configured. */
export default function GoogleButton({ text = "continue_with", onDone }) {
  const cfg = useConfig();
  const clientId = process.env.REACT_APP_GOOGLE_CLIENT_ID || cfg.google_client_id;
  const ref = useRef(null);
  const { googleLogin } = useAuth();
  const nav = useNavigate();

  useEffect(() => {
    if (!clientId) return;
    let cancelled = false;
    loadGis().then(() => {
      if (cancelled || !ref.current) return;
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: async ({ credential }) => {
          try {
            await googleLogin(credential);
            toast.success("Signed in with Google");
            onDone ? onDone() : nav("/");
          } catch (e) { toast.error(errorText(e, "Google sign-in failed")); }
        },
      });
      window.google.accounts.id.renderButton(ref.current, {
        theme: "filled_black", size: "large", shape: "pill", text,
        width: Math.min(ref.current.offsetWidth || 400, 400),
      });
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [clientId, googleLogin, nav, onDone, text]);

  if (!clientId) return null;
  return (
    <>
      <div ref={ref} data-testid="google-signin" className="mt-8 w-full flex justify-center min-h-[44px]" />
      <div className="my-6 flex items-center gap-3 text-xs text-gray-500">
        <div className="flex-1 h-px bg-white/10" /> or use email <div className="flex-1 h-px bg-white/10" />
      </div>
    </>
  );
}
