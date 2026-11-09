// Remote-control navigation for TVs: arrow keys move focus to the nearest
// focusable element in that direction, OK/Enter activates it, Back goes back.
// Active only in TV mode, so arrow keys keep scrolling pages on computers.

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), video[controls], audio[controls], [tabindex]:not([tabindex="-1"])';
const BACK_KEYS = new Set(["GoBack", "BrowserBack", "Escape"]);
const BACK_CODES = new Set([10009 /* Samsung Tizen RETURN */, 461 /* LG webOS BACK */, 8 /* Backspace */]);

function visible(el) {
  const r = el.getBoundingClientRect();
  if (r.width === 0 || r.height === 0) return false;
  const style = getComputedStyle(el);
  return style.visibility !== "hidden" && style.display !== "none" && !el.closest("[aria-hidden='true'], [inert]");
}

function candidates() {
  // Prefer the top-most open dialog so focus can't wander behind it.
  const dialog = [...document.querySelectorAll('[role="dialog"], [role="alertdialog"]')].filter(visible).pop();
  return [...(dialog || document).querySelectorAll(FOCUSABLE)].filter(visible);
}

function center(r) { return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }

export function nextInDirection(from, dir, list = candidates()) {
  const a = from.getBoundingClientRect(), ca = center(a);
  let best = null, bestScore = Infinity;
  for (const el of list) {
    if (el === from) continue;
    const b = el.getBoundingClientRect(), cb = center(b);
    const dx = cb.x - ca.x, dy = cb.y - ca.y;
    let primary, secondary;
    if (dir === "ArrowRight") { if (b.left < a.right - 4 && dx <= 0) continue; primary = Math.max(0, b.left - a.right); secondary = Math.abs(dy); }
    else if (dir === "ArrowLeft") { if (b.right > a.left + 4 && dx >= 0) continue; primary = Math.max(0, a.left - b.right); secondary = Math.abs(dy); }
    else if (dir === "ArrowDown") { if (b.top < a.bottom - 4 && dy <= 0) continue; primary = Math.max(0, b.top - a.bottom); secondary = Math.abs(dx); }
    else { if (b.bottom > a.top + 4 && dy >= 0) continue; primary = Math.max(0, a.top - b.bottom); secondary = Math.abs(dx); }
    // Stay in the same row/column where possible: sideways distance weighs more.
    const score = primary + secondary * 2.5;
    if (score < bestScore) { bestScore = score; best = el; }
  }
  return best;
}

function typing(el) {
  if (!el) return false;
  const tag = el.tagName;
  return el.isContentEditable || tag === "TEXTAREA" || tag === "SELECT" ||
    (tag === "INPUT" && !["checkbox", "radio", "button", "submit", "range"].includes(el.type));
}

export function installSpatialNav(isEnabled) {
  const onKey = (e) => {
    if (!isEnabled()) return;
    const active = document.activeElement;
    const isBack = BACK_KEYS.has(e.key) || BACK_CODES.has(e.keyCode);

    if (isBack) {
      if (typing(active) && e.keyCode === 8) return; // Backspace deletes text in fields
      if (document.querySelector('[role="dialog"]')) return; // let dialogs close themselves
      e.preventDefault();
      if (window.history.length > 1) window.history.back();
      return;
    }
    if (!e.key.startsWith("Arrow")) return;
    // In text fields, Left/Right move the cursor; Up/Down leave the field.
    if (typing(active) && (e.key === "ArrowLeft" || e.key === "ArrowRight")) return;
    // Media elements use Left/Right to seek.
    if ((active?.tagName === "VIDEO" || active?.tagName === "AUDIO") && (e.key === "ArrowLeft" || e.key === "ArrowRight")) return;

    const list = candidates();
    const from = list.includes(active) ? active : null;
    const target = from ? nextInDirection(from, e.key, list) : list.find((el) => el.closest("main")) || list[0];
    if (!target) return;
    e.preventDefault();
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
    // Rows scroll sideways, but also keep the focused row comfortably on screen.
    const r = target.getBoundingClientRect();
    if (r.top < 90 || r.bottom > window.innerHeight - 40) target.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
  };
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}
