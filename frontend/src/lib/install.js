// "Install app" support. Chrome/Edge/Samsung Internet fire beforeinstallprompt;
// iPhone/iPad Safari doesn't, so we show Share → Add to Home Screen instructions.
import { useEffect, useState } from "react";

let deferred = null;
const listeners = new Set();
const notify = () => listeners.forEach((fn) => fn());

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); deferred = e; notify(); });
  window.addEventListener("appinstalled", () => { deferred = null; notify(); });
}

export const isStandalone = () =>
  typeof window !== "undefined" &&
  (window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true);

export const isIOS = () =>
  typeof navigator !== "undefined" &&
  (/iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1));

export function useInstall() {
  const [, tick] = useState(0);
  useEffect(() => { const fn = () => tick((n) => n + 1); listeners.add(fn); return () => listeners.delete(fn); }, []);
  return {
    installed: isStandalone(),
    canPrompt: !!deferred,
    ios: isIOS() && !isStandalone(),
    async prompt() {
      if (!deferred) return "unavailable";
      deferred.prompt();
      const { outcome } = await deferred.userChoice;
      deferred = null; notify();
      return outcome; // "accepted" | "dismissed"
    },
  };
}
