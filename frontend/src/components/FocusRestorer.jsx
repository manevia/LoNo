import { useEffect, useRef } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

// When a remote or keyboard user goes back to a screen, put focus back on the item
// they left from (the channel, title or guide row), not at the top of the page.
// Mouse and touch users aren't affected: restoring only happens after key input.

let lastInput = "pointer";
if (typeof window !== "undefined") {
  window.addEventListener("keydown", () => { lastInput = "key"; }, true);
  window.addEventListener("pointerdown", () => { lastInput = "pointer"; }, true);
}

export function focusKey(el) {
  if (!el || el === document.body) return null;
  const tagged = el.closest("[data-focus-key]");
  if (tagged) return `k:${tagged.getAttribute("data-focus-key")}`;
  const href = el.getAttribute?.("href");
  if (href) return `h:${href}`;
  const tid = el.getAttribute?.("data-testid");
  return tid ? `t:${tid}` : null;
}

function find(key) {
  const [type, value] = [key.slice(0, 1), key.slice(2)];
  const sel = type === "k" ? `[data-focus-key="${CSS.escape(value)}"]`
    : type === "h" ? `[href="${CSS.escape(value)}"]` : `[data-testid="${CSS.escape(value)}"]`;
  const el = document.querySelector(sel);
  if (!el) return null;
  // A tagged wrapper may not be focusable itself: focus its first control.
  return el.matches("a,button,[tabindex]") ? el : el.querySelector("a,button,[tabindex]");
}

export default function FocusRestorer() {
  const location = useLocation();
  const navType = useNavigationType();
  const saved = useRef(new Map()); // location.key -> focus key

  // Remember what's focused on the current screen.
  useEffect(() => {
    const onFocus = (e) => {
      const k = focusKey(e.target);
      if (k) saved.current.set(location.key, k);
    };
    document.addEventListener("focusin", onFocus);
    return () => document.removeEventListener("focusin", onFocus);
  }, [location.key]);

  // On Back (POP), wait for the screen to render, then restore focus.
  useEffect(() => {
    if (navType !== "POP" || lastInput !== "key") return undefined;
    const k = saved.current.get(location.key);
    if (!k) return undefined;
    let tries = 0;
    const timer = setInterval(() => {
      const el = find(k);
      if (el || ++tries > 40) {
        clearInterval(timer);
        if (el) {
          el.focus({ preventScroll: true });
          el.scrollIntoView({ block: "center", inline: "nearest" });
        }
      }
    }, 75);
    return () => clearInterval(timer);
  }, [location.key, navType]);

  return null;
}
