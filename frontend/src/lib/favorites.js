// Favorite channels and stations, saved on this device so they work on a TV
// without signing in.
import { useEffect, useState } from "react";

const KEY = "lono_favorites";
const listeners = new Set();

function read() {
  try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch { return []; }
}

export function isFavorite(id) { return read().includes(id); }

export function toggleFavorite(id) {
  const list = read();
  const next = list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* storage full or blocked */ }
  listeners.forEach((fn) => fn(next));
  return next.includes(id);
}

export function useFavorites() {
  const [list, set] = useState(read);
  useEffect(() => { listeners.add(set); return () => listeners.delete(set); }, []);
  return list;
}
