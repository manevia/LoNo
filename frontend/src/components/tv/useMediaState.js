import { useEffect, useState } from "react";

const fmt = (s) => {
  if (!isFinite(s) || s < 0) s = 0;
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60);
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}` : `${m}:${String(sec).padStart(2, "0")}`;
};
export { fmt as formatTime };

/** Live view of a media element (and its hls.js instance, if any), polled once a second. */
export default function useMediaState(getMedia, getHls, deps = []) {
  const [st, set] = useState({ paused: true, time: 0, duration: 0, liveStream: false, timeShift: false, behind: 0, waiting: false });
  useEffect(() => {
    const read = () => {
      const m = getMedia();
      if (!m) return;
      const hls = getHls?.();
      const details = hls?.levels?.[Math.max(0, hls.currentLevel)]?.details;
      const s = m.seekable;
      const span = s && s.length ? s.end(s.length - 1) - s.start(0) : 0;
      const liveStream = details ? !!details.live : m.duration === Infinity;
      const edge = hls?.liveSyncPosition ?? (s && s.length ? s.end(s.length - 1) : m.currentTime);
      set({
        paused: m.paused, time: m.currentTime, duration: isFinite(m.duration) ? m.duration : 0,
        liveStream, timeShift: liveStream && span >= 30,
        behind: liveStream ? Math.max(0, edge - m.currentTime) : 0,
        waiting: m.readyState < 3 && !m.paused,
      });
    };
    read();
    const t = setInterval(read, 1000);
    const m = getMedia();
    const evs = ["play", "pause", "playing", "waiting", "seeked", "loadedmetadata", "durationchange"];
    evs.forEach((e) => m?.addEventListener(e, read));
    return () => { clearInterval(t); evs.forEach((e) => m?.removeEventListener(e, read)); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return st;
}
