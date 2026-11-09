// "Back" closes the most recent overlay first (picker, menu, full-screen player),
// and only then leaves the screen. Components register a handler while their
// overlay is open; the TV key handler and Escape call the top one.
import { useEffect, useRef } from "react";

const stack = [];

export function pushBack(fn) {
  const entry = { fn };
  stack.push(entry);
  return () => { const i = stack.indexOf(entry); if (i >= 0) stack.splice(i, 1); };
}

/** Runs the top handler. Returns true if an overlay consumed Back. */
export function runBack() {
  const top = stack[stack.length - 1];
  if (!top) return false;
  top.fn();
  return true;
}

export function hasBackHandler() { return stack.length > 0; }

/** Register `onBack` while `active` is true. */
export function useBack(active, onBack) {
  const ref = useRef(onBack);
  ref.current = onBack;
  useEffect(() => {
    if (!active) return undefined;
    return pushBack(() => ref.current());
  }, [active]);
}

// Escape works the same way for keyboard users outside TV mode.
if (typeof window !== "undefined") {
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !e.defaultPrevented && stack.length && runBack()) e.preventDefault();
  });
}
