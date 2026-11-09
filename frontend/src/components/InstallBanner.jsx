import { useState } from "react";
import { Download, Share, X } from "lucide-react";
import { useInstall } from "@/lib/install";
import { usePrefs } from "@/lib/device";

const KEY = "lono_install_dismissed";

/** A small, dismissible "Install LoNo" prompt for phones and tablets. */
export default function InstallBanner() {
  const { installed, canPrompt, ios, prompt } = useInstall();
  const { tv } = usePrefs();
  const [hidden, setHidden] = useState(() => { try { return !!localStorage.getItem(KEY); } catch { return false; } });
  const [showIOS, setShowIOS] = useState(false);

  if (installed || hidden || tv || !(canPrompt || ios)) return null;
  const dismiss = () => { try { localStorage.setItem(KEY, "1"); } catch { /* ignore */ } setHidden(true); };

  return (
    <div role="region" aria-label="Install LoNo" data-testid="install-banner"
      className="lg:hidden fixed inset-x-3 bottom-[4.5rem] z-50 rounded-2xl bg-[#121212] border border-white/15 shadow-2xl p-3.5"
      style={{ marginBottom: "env(safe-area-inset-bottom)" }}>
      <div className="flex items-center gap-3">
        <img src="/icons/icon-192.png" alt="" className="w-11 h-11 rounded-xl" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium">Install LoNo</div>
          <div className="text-xs text-gray-400">Opens full screen from your home screen, and loads faster.</div>
        </div>
        {canPrompt ? (
          <button onClick={async () => { if ((await prompt()) === "accepted") dismiss(); }}
            className="shrink-0 inline-flex items-center gap-1.5 bg-white text-black rounded-full px-3.5 py-2 text-sm font-medium">
            <Download className="w-4 h-4" /> Install
          </button>
        ) : (
          <button onClick={() => setShowIOS((v) => !v)} className="shrink-0 bg-white text-black rounded-full px-3.5 py-2 text-sm font-medium">How?</button>
        )}
        <button onClick={dismiss} aria-label="Not now" className="shrink-0 p-1.5 text-gray-400 hover:text-white"><X className="w-4 h-4" /></button>
      </div>
      {showIOS && (
        <p className="mt-3 text-xs text-gray-300 leading-relaxed">
          In Safari, tap <Share className="inline w-3.5 h-3.5 -mt-0.5" aria-label="Share" /> <strong>Share</strong>, then <strong>Add to Home Screen</strong>.
        </p>
      )}
    </div>
  );
}
