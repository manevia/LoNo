// Device detection and viewing preferences (TV mode, data saver).
// Preferences live in localStorage so they apply before the app finishes loading.
import { useEffect, useState } from "react";

const TV_UA = /SmartTV|SMART-TV|Tizen|Web0S|webOS|NetCast|BRAVIA|HbbTV|VIDAA|Android TV|GoogleTV|AFT[A-Z]|CrKey|Roku|Viera|AQUOS/i;
const KEY = { tv: "lono_tv", saver: "lono_data_saver" };
const listeners = new Set();

export function detectTV() {
  return typeof navigator !== "undefined" && TV_UA.test(navigator.userAgent || "");
}

function connectionWantsSaving() {
  const c = typeof navigator !== "undefined" && navigator.connection;
  return !!c && (c.saveData || /(^|-)2g$|^3g$/.test(c.effectiveType || ""));
}

function read(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

/** "1" / "0" = the user's explicit choice; nothing stored = automatic. */
export function getPrefs() {
  const tv = read(KEY.tv), saver = read(KEY.saver);
  return {
    tv: tv === null ? detectTV() : tv === "1",
    tvAuto: tv === null,
    dataSaver: saver === null ? connectionWantsSaving() : saver === "1",
    dataSaverAuto: saver === null,
  };
}

export function setPref(name, value /* true | false | null for automatic */) {
  try {
    if (value === null) localStorage.removeItem(KEY[name]);
    else localStorage.setItem(KEY[name], value ? "1" : "0");
  } catch { /* storage may be unavailable */ }
  applyDeviceClasses();
  listeners.forEach((fn) => fn(getPrefs()));
}

/** Adds html.tv / html.data-saver so CSS can adapt. Call once at startup. */
export function applyDeviceClasses() {
  const p = getPrefs();
  const root = document.documentElement;
  root.classList.toggle("tv", p.tv);
  root.classList.toggle("data-saver", p.dataSaver);
  return p;
}

export function usePrefs() {
  const [prefs, set] = useState(getPrefs);
  useEffect(() => { listeners.add(set); return () => listeners.delete(set); }, []);
  return prefs;
}

/** Smaller, lighter images when data saver is on (only for hosts that support resizing). */
export function lightImage(url) {
  if (!url || !getPrefs().dataSaver) return url;
  try {
    const u = new URL(url, window.location.origin);
    if (u.hostname === "images.unsplash.com") {
      u.searchParams.set("w", "480");
      u.searchParams.set("q", "45");
      u.searchParams.set("auto", "format");
      return u.toString();
    }
  } catch { /* not a URL */ }
  return url;
}
