// Camera / microphone / speaker handling for Creator Studio.
import { useCallback, useEffect, useState } from "react";

const KEY = "lono_studio_devices";

export function loadDevicePrefs() {
  try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch { return {}; }
}
export function saveDevicePrefs(patch) {
  const next = { ...loadDevicePrefs(), ...patch };
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* storage blocked */ }
  return next;
}

/** Lists devices and refreshes when something is plugged in or removed. */
export function useMediaDevices() {
  const [devices, setDevices] = useState({ video: [], audio: [], output: [], ready: false });
  const refresh = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) { setDevices((d) => ({ ...d, ready: true, unsupported: true })); return; }
    const list = await navigator.mediaDevices.enumerateDevices();
    setDevices({
      video: list.filter((d) => d.kind === "videoinput"),
      audio: list.filter((d) => d.kind === "audioinput"),
      output: list.filter((d) => d.kind === "audiooutput"),
      ready: true,
    });
  }, []);
  useEffect(() => {
    refresh();
    navigator.mediaDevices?.addEventListener?.("devicechange", refresh);
    return () => navigator.mediaDevices?.removeEventListener?.("devicechange", refresh);
  }, [refresh]);
  return [devices, refresh];
}

/** Friendly name: the creator's own label, else the system label, else a fallback. */
export function deviceName(d, i, kind) {
  const names = loadDevicePrefs().names || {};
  return names[d.deviceId] || d.label || `${kind} ${i + 1}`;
}

export async function openCamera(deviceId, quality = "720p") {
  const size = quality === "1080p" ? { width: 1920, height: 1080 } : quality === "480p" ? { width: 854, height: 480 } : { width: 1280, height: 720 };
  return navigator.mediaDevices.getUserMedia({
    video: { deviceId: deviceId ? { exact: deviceId } : undefined, width: { ideal: size.width }, height: { ideal: size.height }, frameRate: { ideal: 30 } },
    audio: false,
  });
}

export async function openMic(deviceId, { echoCancellation = true, noiseSuppression = true } = {}) {
  return navigator.mediaDevices.getUserMedia({
    audio: { deviceId: deviceId ? { exact: deviceId } : undefined, echoCancellation, noiseSuppression, autoGainControl: false, channelCount: 2 },
    video: false,
  });
}

/** Audio level of a track, in dBFS (about -60 quiet … 0 clipping), polled by animation frame. */
export function useAudioLevel(track) {
  const [level, setLevel] = useState({ db: -100, peak: -100, clipping: false });
  useEffect(() => {
    if (!track) { setLevel({ db: -100, peak: -100, clipping: false }); return undefined; }
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ctx = new Ctx();
    const src = ctx.createMediaStreamSource(new MediaStream([track]));
    const an = ctx.createAnalyser();
    an.fftSize = 2048;
    src.connect(an); // analyser only: nothing is played or sent
    const buf = new Float32Array(an.fftSize);
    let raf, peak = -100, peakAt = 0, clipAt = 0;
    const tick = () => {
      an.getFloatTimeDomainData(buf);
      let sum = 0, max = 0;
      for (let i = 0; i < buf.length; i++) { const v = buf[i]; sum += v * v; if (Math.abs(v) > max) max = Math.abs(v); }
      const db = 20 * Math.log10(Math.sqrt(sum / buf.length) || 1e-6);
      const now = performance.now();
      if (db > peak || now - peakAt > 1500) { peak = db; peakAt = now; }
      if (max >= 0.99) clipAt = now;
      setLevel({ db: track.enabled ? db : -100, peak, clipping: now - clipAt < 1000 });
      raf = requestAnimationFrame(tick);
    };
    ctx.resume().catch(() => {});
    tick();
    return () => { cancelAnimationFrame(raf); src.disconnect(); ctx.close().catch(() => {}); };
  }, [track]);
  return level;
}
