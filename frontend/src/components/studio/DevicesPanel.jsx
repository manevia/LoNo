import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, Headphones, Mic, MicOff, Pencil, RefreshCw, Video, VideoOff, AlertTriangle, Grid3x3 } from "lucide-react";
import { deviceName, loadDevicePrefs, openCamera, openMic, saveDevicePrefs, useMediaDevices } from "@/lib/devices";
import AudioMeter from "@/components/studio/AudioMeter";

const sel = "w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm";
const chip = "inline-flex items-center gap-1.5 text-xs rounded-full px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10";

/**
 * Devices & Sources: pick, name, preview and switch cameras, microphones (incl.
 * USB interfaces and capture cards, which appear as cameras/mics) and the
 * monitoring output. Monitoring plays the mic only to the creator's headphones
 * or speakers; it is never mixed into what is broadcast.
 */
export default function DevicesPanel({ onTracks, live }) {
  const [devices, refresh] = useMediaDevices();
  const prefs = loadDevicePrefs();
  const [cameraId, setCameraId] = useState(prefs.camera || "");
  const [micId, setMicId] = useState(prefs.mic || "");
  const [outputId, setOutputId] = useState(prefs.output || "");
  const [quality, setQuality] = useState(prefs.quality || "720p");
  const [cameraOn, setCameraOn] = useState(prefs.cameraOn !== false);
  const [cam, setCam] = useState(null);
  const [mic, setMic] = useState(null);
  const [muted, setMuted] = useState(false);
  const [monitor, setMonitor] = useState(false);
  const [grid, setGrid] = useState(false);
  const [lost, setLost] = useState({});           // {camera: true, mic: true} when unplugged
  const [error, setError] = useState(null);
  const [renaming, setRenaming] = useState(null);
  const [allowed, setAllowed] = useState(false);
  const video = useRef(null);
  const monitorEl = useRef(null);
  const camRef = useRef(null); const micRef = useRef(null);

  const report = useCallback((c, m) => onTracks?.({ video: c?.getVideoTracks()[0] || null, audio: m?.getAudioTracks()[0] || null }), [onTracks]);

  const startCamera = useCallback(async (id = cameraId, q = quality) => {
    camRef.current?.getTracks().forEach((t) => t.stop());
    if (!cameraOn) { camRef.current = null; setCam(null); return null; }
    try {
      const s = await openCamera(id, q);
      const t = s.getVideoTracks()[0];
      t.addEventListener("ended", () => setLost((l) => ({ ...l, camera: true })));
      camRef.current = s; setCam(s); setLost((l) => ({ ...l, camera: false })); setError(null);
      const actual = t.getSettings().deviceId;
      if (actual) { setCameraId(actual); saveDevicePrefs({ camera: actual }); }
      return s;
    } catch (e) {
      setError(e.name === "NotAllowedError" ? "Camera access was blocked. Allow it in the browser's address bar." :
        e.name === "NotFoundError" || e.name === "OverconstrainedError" ? "That camera isn't available. Choose another." : `Camera error: ${e.message}`);
      return null;
    }
  }, [cameraId, quality, cameraOn]);

  const startMic = useCallback(async (id = micId) => {
    micRef.current?.getTracks().forEach((t) => t.stop());
    try {
      const s = await openMic(id);
      const t = s.getAudioTracks()[0];
      t.enabled = !muted;
      t.addEventListener("ended", () => setLost((l) => ({ ...l, mic: true })));
      micRef.current = s; setMic(s); setLost((l) => ({ ...l, mic: false })); setError(null);
      const actual = t.getSettings().deviceId;
      if (actual) { setMicId(actual); saveDevicePrefs({ mic: actual }); }
      return s;
    } catch (e) {
      setError(e.name === "NotAllowedError" ? "Microphone access was blocked. Allow it in the browser's address bar." : `Microphone error: ${e.message}`);
      return null;
    }
  }, [micId, muted]);

  const allow = async () => {
    const [c, m] = await Promise.all([startCamera(), startMic()]);
    setAllowed(true); refresh(); report(c, m);
  };

  // The preview element appears after permission is granted, so attach on either change.
  useEffect(() => { if (video.current && video.current.srcObject !== cam) video.current.srcObject = cam; }, [cam, allowed]);
  useEffect(() => () => { camRef.current?.getTracks().forEach((t) => t.stop()); micRef.current?.getTracks().forEach((t) => t.stop()); }, []);

  // Monitoring: mic → chosen output only (separate element, never part of the broadcast).
  useEffect(() => {
    const el = monitorEl.current;
    if (!el) return;
    el.srcObject = monitor && mic ? new MediaStream(mic.getAudioTracks().map((t) => t.clone())) : null;
    if (outputId && el.setSinkId) el.setSinkId(outputId).catch(() => {});
    if (monitor) el.play().catch(() => {});
  }, [monitor, mic, outputId]);

  // A device disappeared: notice when it comes back (devicechange) or let the creator pick another.
  useEffect(() => {
    if (lost.camera && devices.video.some((d) => d.deviceId === cameraId)) setLost((l) => ({ ...l, cameraBack: true }));
    if (lost.mic && devices.audio.some((d) => d.deviceId === micId)) setLost((l) => ({ ...l, micBack: true }));
  }, [devices, lost.camera, lost.mic, cameraId, micId]);

  const switchCamera = async (id) => { setCameraId(id); saveDevicePrefs({ camera: id }); const c = await startCamera(id); report(c, micRef.current); };
  const switchMic = async (id) => { setMicId(id); saveDevicePrefs({ mic: id }); const m = await startMic(id); report(camRef.current, m); };
  const toggleMute = () => { const t = micRef.current?.getAudioTracks()[0]; if (t) t.enabled = muted; setMuted(!muted); };
  const toggleCamera = async () => {
    const on = !cameraOn; setCameraOn(on); saveDevicePrefs({ cameraOn: on });
    if (!on) { camRef.current?.getTracks().forEach((t) => t.stop()); camRef.current = null; setCam(null); report(null, micRef.current); }
    else { const c = await openCamera(cameraId, quality).catch(() => null); camRef.current = c; setCam(c); report(c, micRef.current); }
  };
  const rename = (id, name) => { const names = { ...(loadDevicePrefs().names || {}), [id]: name.trim() || undefined }; saveDevicePrefs({ names }); setRenaming(null); refresh(); };

  const videoTrack = cam?.getVideoTracks()[0];
  const settings = videoTrack?.getSettings() || {};

  const DeviceSelect = ({ kind, list, value, onChange, testId }) => (
    <div className="flex gap-2">
      {renaming === kind ? (
        <form className="flex-1 flex gap-2" onSubmit={(e) => { e.preventDefault(); rename(value, e.target.elements.n.value); }}>
          <input name="n" autoFocus defaultValue={deviceName(list.find((d) => d.deviceId === value) || {}, 0, kind)} className={sel} aria-label={`Name for this ${kind}`} />
          <button className={chip}>Save</button>
        </form>
      ) : (
        <>
          <select value={value} onChange={(e) => onChange(e.target.value)} className={sel} data-testid={testId} aria-label={kind}>
            {list.map((d, i) => <option key={d.deviceId} value={d.deviceId} className="bg-[#121212]">{deviceName(d, i, kind)}</option>)}
          </select>
          {value && <button type="button" className={chip} onClick={() => setRenaming(kind)} aria-label={`Rename this ${kind}`}><Pencil className="w-3.5 h-3.5" /></button>}
        </>
      )}
    </div>
  );

  if (devices.unsupported) return <p className="text-sm text-gray-400">This browser can't access cameras or microphones. Use Chrome, Edge or Safari, or broadcast with an external encoder.</p>;

  return (
    <div data-testid="devices-panel" className="space-y-5">
      {!allowed ? (
        <div className="p-6 rounded-2xl border border-dashed border-white/15 text-center">
          <Camera className="w-8 h-8 mx-auto text-gray-500" />
          <p className="mt-3 text-sm text-gray-300">LoNo needs permission to use your camera and microphone. Nothing is sent until you start a test or go live.</p>
          <button data-testid="allow-devices" onClick={allow} className="mt-4 bg-white text-black rounded-full px-5 py-2.5 text-sm font-medium">Allow camera and microphone</button>
        </div>
      ) : (
        <>
          {error && <div role="alert" className="p-3 rounded-xl bg-[#FF3B30]/10 border border-[#FF3B30]/30 text-sm text-[#FF8A82]">{error}</div>}
          {(lost.camera || lost.mic) && (
            <div role="alert" data-testid="device-lost" className="p-3 rounded-xl bg-[#FFB000]/10 border border-[#FFB000]/30 text-sm flex flex-wrap items-center gap-3">
              <AlertTriangle className="w-4 h-4 text-[#FFB000]" />
              <span>{lost.camera && "Your camera disconnected. "}{lost.mic && "Your microphone disconnected. "}{live && "The broadcast continues; viewers see the last frame or hear silence."}</span>
              {lost.camera && <button className={chip} data-testid="reconnect-camera" onClick={() => switchCamera(cameraId)}><RefreshCw className="w-3.5 h-3.5" /> Reconnect camera</button>}
              {lost.mic && <button className={chip} data-testid="reconnect-mic" onClick={() => switchMic(micId)}><RefreshCw className="w-3.5 h-3.5" /> Reconnect microphone</button>}
              <span className="text-gray-400">or choose a replacement below.</span>
            </div>
          )}

          <div className="relative aspect-video rounded-xl overflow-hidden bg-black ring-1 ring-white/10">
            {cam ? <video ref={video} autoPlay muted playsInline data-testid="camera-preview" className="w-full h-full object-cover" />
              : <div className="absolute inset-0 grid place-items-center text-gray-500 text-sm">{cameraOn ? "No camera" : "Camera off (audio only)"}</div>}
            {grid && cam && (
              <div className="absolute inset-0 pointer-events-none" aria-hidden="true"
                style={{ backgroundImage: "linear-gradient(to right, transparent 33.1%, rgba(255,255,255,.35) 33.3%, transparent 33.5%, transparent 66.5%, rgba(255,255,255,.35) 66.7%, transparent 66.9%), linear-gradient(to bottom, transparent 33.1%, rgba(255,255,255,.35) 33.3%, transparent 33.5%, transparent 66.5%, rgba(255,255,255,.35) 66.7%, transparent 66.9%)" }} />
            )}
            {cam && <div className="absolute bottom-2 left-2 text-[11px] bg-black/60 rounded px-2 py-0.5 tabular-nums">{settings.width}×{settings.height} · {Math.round(settings.frameRate || 0)} fps</div>}
          </div>

          <div className="flex flex-wrap gap-2">
            <button className={chip} onClick={toggleCamera} aria-pressed={!cameraOn} data-testid="toggle-camera">{cameraOn ? <><VideoOff className="w-3.5 h-3.5" /> Turn camera off</> : <><Video className="w-3.5 h-3.5" /> Turn camera on</>}</button>
            <button className={chip} onClick={toggleMute} aria-pressed={muted} data-testid="toggle-mute">{muted ? <><Mic className="w-3.5 h-3.5" /> Unmute</> : <><MicOff className="w-3.5 h-3.5" /> Mute</>}</button>
            <button className={chip} onClick={() => setGrid(!grid)} aria-pressed={grid}><Grid3x3 className="w-3.5 h-3.5" /> Framing grid</button>
          </div>

          <label className="block"><span className="text-sm text-gray-400 flex items-center gap-1.5 mb-1.5"><Camera className="w-4 h-4" /> Camera or capture card</span>
            {DeviceSelect({ kind: "camera", list: devices.video, value: cameraId, onChange: switchCamera, testId: "select-camera" })}</label>
          <label className="block"><span className="text-sm text-gray-400 mb-1.5 block">Quality</span>
            <select value={quality} onChange={async (e) => { setQuality(e.target.value); saveDevicePrefs({ quality: e.target.value }); const c = await startCamera(cameraId, e.target.value); report(c, micRef.current); }} className={sel}>
              {["480p", "720p", "1080p"].map((q) => <option key={q} className="bg-[#121212]">{q}</option>)}
            </select></label>
          <label className="block"><span className="text-sm text-gray-400 flex items-center gap-1.5 mb-1.5"><Mic className="w-4 h-4" /> Microphone or audio interface</span>
            {DeviceSelect({ kind: "microphone", list: devices.audio, value: micId, onChange: switchMic, testId: "select-mic" })}</label>
          <AudioMeter track={mic?.getAudioTracks()[0]} label="Microphone level (aim for -18 to -6 dB when speaking)" testId="mic-meter" />

          <div className="pt-1">
            <span className="text-sm text-gray-400 flex items-center gap-1.5 mb-1.5"><Headphones className="w-4 h-4" /> Monitoring</span>
            {devices.output.length > 0 && typeof HTMLMediaElement !== "undefined" && "setSinkId" in HTMLMediaElement.prototype ? (
              DeviceSelect({ kind: "output", list: devices.output, value: outputId, onChange: (id) => { setOutputId(id); saveDevicePrefs({ output: id }); }, testId: "select-output" })
            ) : <p className="text-xs text-gray-500">This browser plays monitoring through the system's default output. Choose headphones in your system settings.</p>}
            <label className="mt-2 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={monitor} onChange={(e) => setMonitor(e.target.checked)} data-testid="toggle-monitor" className="accent-[#FFB000] w-4 h-4" />
              Hear my microphone. Use headphones; this sound is never sent to viewers.
            </label>
            <audio ref={monitorEl} data-testid="monitor-output" />
          </div>
        </>
      )}
    </div>
  );
}
