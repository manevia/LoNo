import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, Loader2, Radio, RefreshCw, Tv, Undo2 } from "lucide-react";
import { api, resolveMedia } from "@/lib/api";
import MediaPlayer from "@/components/MediaPlayer";
import PlayerControls from "@/components/tv/PlayerControls";
import { tvKey, isTyping } from "@/lib/tvKeys";
import { useBack } from "@/lib/backStack";
import { toggleFavorite, useFavorites } from "@/lib/favorites";

const HIDE_AFTER_MS = 5000;
const time = (iso) => new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

/**
 * Full-screen live TV / radio player for remotes.
 * - Channel Up/Down (and Next/Previous media keys) step through the active list.
 * - The Channels/Stations picker keeps the current stream playing until OK confirms.
 * - Rapid switching: the player is keyed by channel, so the previous element (and its
 *   audio) is torn down before the newest selection starts; only the last choice plays.
 * - Viewer actions here only affect this device's playback; nothing is sent to any
 *   broadcast, so a creator's live stream is unaffected.
 */
export default function LivePlayer() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const listName = params.get("list") === "radio" ? "radio" : "tv";
  const favOnly = params.get("fav") === "1";
  const favorites = useFavorites();

  const [guide, setGuide] = useState(null);
  const [currentId, setCurrentId] = useState(id);
  const [lastGoodId, setLastGoodId] = useState(null);
  const [attempt, setAttempt] = useState(0);         // bump to retry the same channel
  const [stopped, setStopped] = useState(false);
  const [error, setError] = useState(null);
  const [picker, setPicker] = useState(false);
  const [visible, setVisible] = useState(true);
  const [banner, setBanner] = useState(true);
  const media = useRef(null);
  const hls = useRef(null);
  const firstControl = useRef(null);
  const hideTimer = useRef(null);
  const bannerTimer = useRef(null);

  useEffect(() => { api.get("/live/guide").then(({ data }) => setGuide(data)).catch(() => setGuide({ tv: [], radio: [] })); }, []);

  const list = useMemo(() => {
    if (!guide) return [];
    const all = guide[listName] || [];
    const favs = all.filter((c) => favorites.includes(c.id));
    return favOnly && favs.length ? favs : all;
  }, [guide, listName, favOnly, favorites]);
  const current = list.find((c) => c.id === currentId) || guide?.[listName]?.find((c) => c.id === currentId);
  const isRadio = current?.kind === "live_radio";

  // ----- controls visibility -----
  const poke = useCallback(() => {
    setVisible(true);
    clearTimeout(hideTimer.current);
    hideTimer.current = setTimeout(() => {
      const m = media.current;
      if (m && !m.paused && !picker && !error) setVisible(false);
    }, HIDE_AFTER_MS);
  }, [picker, error]);
  useEffect(() => { poke(); return () => clearTimeout(hideTimer.current); }, [poke]);
  useEffect(() => { if (picker || error || stopped) setVisible(true); }, [picker, error, stopped]);

  const showBanner = () => {
    setBanner(true);
    clearTimeout(bannerTimer.current);
    bannerTimer.current = setTimeout(() => setBanner(false), 4000);
  };
  useEffect(() => { showBanner(); return () => clearTimeout(bannerTimer.current); }, []);

  // ----- tuning -----
  const tuneTo = useCallback((nextId) => {
    if (!nextId) return;
    setError(null); setStopped(false); setPicker(false);
    setCurrentId(nextId);
    setAttempt((n) => n + 1);
    showBanner(); poke();
    // Replace, so Back still returns to the screen the viewer came from.
    navigate(`/live/play/${nextId}?${params.toString()}`, { replace: true });
  }, [navigate, params, poke]);

  const step = useCallback((dir) => {
    if (!list.length) return;
    const i = list.findIndex((c) => c.id === currentId);
    tuneTo(list[(i + dir + list.length) % list.length].id);
  }, [list, currentId, tuneTo]);

  // ----- Back: close the picker or error first, then leave -----
  useBack(picker, () => setPicker(false));
  useBack(!!error, () => setError(null));

  // ----- keys: channel/media keys always; arrows/OK first reveal hidden controls -----
  useEffect(() => {
    const onKey = (e) => {
      if (isTyping()) return;
      const k = tvKey(e);
      if (!k) return;
      const m = media.current;
      if (k === "channelUp" || k === "next") { e.preventDefault(); e.stopPropagation(); step(1); return; }
      if (k === "channelDown" || k === "previous") { e.preventDefault(); e.stopPropagation(); step(-1); return; }
      if (k === "stop") { e.preventDefault(); setStopped(true); return; }
      if (k === "playPause" || k === "play" || k === "pause") {
        if (e.key === " " && document.activeElement?.tagName === "BUTTON") return; // space presses buttons
        e.preventDefault();
        if (stopped) { setStopped(false); setAttempt((n) => n + 1); return; }
        if (m) { if (k === "pause" || (k === "playPause" && !m.paused)) m.pause(); else m.play().catch(() => {}); }
        poke(); return;
      }
      if ((k === "rewind" || k === "fastForward") && m) {
        e.preventDefault();
        const s = m.seekable;
        if (s.length) m.currentTime = Math.max(s.start(0), Math.min(s.end(s.length - 1), m.currentTime + (k === "rewind" ? -10 : 10)));
        poke(); return;
      }
      if (!visible && ["up", "down", "left", "right", "ok"].includes(k)) {
        // First press only reveals the controls; it doesn't move or click anything.
        e.preventDefault(); e.stopPropagation();
        setVisible(true); poke();
        setTimeout(() => firstControl.current?.focus(), 0);
        return;
      }
      poke();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [visible, stopped, step, poke]);

  useEffect(() => { if (guide && current) setTimeout(() => firstControl.current?.focus(), 50); }, [guide, current?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!guide) return <div className="fixed inset-0 bg-black grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>;
  if (!current) return (
    <div className="fixed inset-0 bg-black grid place-items-center text-center p-6">
      <div><p className="text-gray-300">This channel isn't available.</p>
        <button autoFocus onClick={() => navigate("/live")} className="mt-4 bg-white text-black rounded-full px-5 py-2.5">Go to Live</button></div>
    </div>
  );

  const prev = lastGoodId && lastGoodId !== currentId ? (list.find((c) => c.id === lastGoodId) || guide[listName].find((c) => c.id === lastGoodId)) : null;
  const label = isRadio ? "Stations" : "Channels";

  return (
    <div data-testid="live-player" className="fixed inset-0 z-[60] bg-black text-white overflow-hidden" onMouseMove={poke} onClick={poke}>
      {/* Stream */}
      <div className="absolute inset-0 grid place-items-center">
        {isRadio && <img src={resolveMedia(current.thumbnail_url)} alt="" className="absolute inset-0 w-full h-full object-cover opacity-30 blur-sm" />}
        {!stopped && (
          <MediaPlayer
            key={`${currentId}:${attempt}`} ref={media} testId="live-media" audio={isRadio} live autoPlay
            src={resolveMedia(current.stream_url)} poster={resolveMedia(current.thumbnail_url)}
            title={current.title} artist={current.now?.title} artwork={resolveMedia(current.thumbnail_url)}
            nativeControls={false} showOptions={false}
            className={isRadio ? "hidden" : "w-full h-full object-contain bg-black"}
            onHls={(h) => { hls.current = h; }}
            onFatalError={(message) => setError({ message, id: currentId })}
            mediaProps={{ onPlaying: () => { setLastGoodId(currentId); setError(null); } }}
          />
        )}
        {isRadio && (
          <div className="relative text-center px-6">
            <img src={resolveMedia(current.thumbnail_url)} alt="" className="w-48 h-48 md:w-64 md:h-64 mx-auto rounded-3xl object-cover ring-1 ring-white/20 shadow-2xl" />
            <div className="mt-6 text-sm text-gray-300">Station {current.number}</div>
            <div className="font-display text-4xl font-semibold">{current.title}</div>
            {current.now && <div className="mt-2 text-gray-300">{current.now.title}</div>}
          </div>
        )}
        {stopped && !isRadio && <div className="text-gray-400 text-lg">Stopped. Press Play to reconnect.</div>}
      </div>

      {/* Tuning banner */}
      {banner && (
        <div data-testid="tuning-banner" role="status" aria-live="polite"
          className="absolute top-6 left-6 right-6 md:right-auto md:max-w-xl rounded-2xl bg-black/75 backdrop-blur border border-white/15 px-5 py-4">
          <div className="flex items-center gap-3">
            <span className="font-display text-3xl tabular-nums text-[#FFB000]">{current.number}</span>
            <div className="min-w-0">
              <div className="font-display text-xl truncate" data-testid="tuning-name">{current.title}</div>
              {current.now && <div className="text-sm text-gray-300 truncate">{time(current.now.start)}–{time(current.now.end)} · {current.now.title}</div>}
            </div>
          </div>
        </div>
      )}

      {/* Controls overlay */}
      <div className={`absolute inset-x-0 bottom-0 transition-opacity duration-300 ${visible ? "opacity-100" : "opacity-0 pointer-events-none"}`}
        aria-hidden={!visible} inert={!visible}>
        <div className="bg-gradient-to-t from-black via-black/85 to-transparent pt-24 pb-8 px-6 md:px-12">
          <div className="flex items-start gap-4 mb-5">
            <button onClick={() => navigate(-1)} className="shrink-0 inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-sm bg-white/10 hover:bg-white/20 border border-white/10" data-testid="live-exit">
              <ArrowLeft className="w-4 h-4" /> Back
            </button>
            <div className="min-w-0 flex-1" data-testid="program-details">
              <div className="flex items-center gap-2 text-sm text-gray-300">
                {isRadio ? <Radio className="w-4 h-4" /> : <Tv className="w-4 h-4" />}
                <span>{isRadio ? "Station" : "Channel"} {current.number} · <span data-testid="current-name">{current.title}</span></span>
              </div>
              {current.now ? (
                <>
                  <div className="font-display text-2xl md:text-3xl mt-1">{current.now.title}</div>
                  <div className="text-sm text-gray-400">{time(current.now.start)}–{time(current.now.end)} · {current.now.description}</div>
                  {current.next && <div className="text-sm text-gray-500 mt-1">Next at {time(current.next.start)}: {current.next.title}</div>}
                </>
              ) : <div className="text-gray-400 mt-1">{current.description}</div>}
            </div>
          </div>
          <PlayerControls
            mode="live" streamKey={`${currentId}:${attempt}`} stopped={stopped}
            getMedia={() => media.current} getHls={() => hls.current} firstRef={firstControl}
            onStop={() => setStopped(true)} onPlayLive={() => { setStopped(false); setAttempt((n) => n + 1); }}
            onOpenPicker={() => setPicker(true)} pickerLabel={label}
            favorite={favorites.includes(currentId)} onToggleFavorite={() => toggleFavorite(currentId)}
          />
          <div className="mt-3 text-xs text-gray-500">Channel Up/Down or {label} to switch · Back to leave</div>
        </div>
      </div>

      {/* Channels / Stations picker: the current stream keeps playing until OK */}
      {picker && <Picker list={list} currentId={currentId} label={label} onPick={tuneTo} onClose={() => setPicker(false)} />}

      {/* Failure */}
      {error && (
        <div role="alertdialog" aria-labelledby="stream-error-title" data-testid="stream-error"
          className="absolute inset-0 grid place-items-center bg-black/70 backdrop-blur-sm p-6">
          <div className="max-w-md w-full rounded-2xl bg-[#121212] border border-white/15 p-6 text-center">
            <div id="stream-error-title" className="font-display text-2xl">{current.title} isn't playing</div>
            <p className="mt-2 text-gray-400">{error.message}</p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <button autoFocus data-testid="error-retry" onClick={() => { setError(null); setAttempt((n) => n + 1); }}
                className="inline-flex items-center gap-2 bg-white text-black rounded-full px-5 py-2.5 font-medium"><RefreshCw className="w-4 h-4" /> Retry</button>
              {prev && (
                <button data-testid="error-previous" onClick={() => tuneTo(prev.id)}
                  className="inline-flex items-center gap-2 bg-white/10 border border-white/15 rounded-full px-5 py-2.5"><Undo2 className="w-4 h-4" /> Return to {prev.title}</button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Picker({ list, currentId, label, onPick, onClose }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current?.querySelector('[aria-current="true"]') || ref.current?.querySelector("button");
    el?.focus(); el?.scrollIntoView({ block: "center" });
  }, []);
  return (
    <div role="dialog" aria-label={label} data-testid="channel-picker" ref={ref}
      className="absolute inset-y-0 right-0 w-full max-w-md bg-black/90 backdrop-blur border-l border-white/10 flex flex-col">
      <div className="px-6 pt-6 pb-3 flex items-center justify-between">
        <h2 className="font-display text-2xl">{label}</h2>
        <button onClick={onClose} className="text-sm text-gray-400 hover:text-white px-3 py-1.5 rounded-full">Close</button>
      </div>
      <ul className="flex-1 overflow-y-auto px-3 pb-6 space-y-1">
        {list.map((c) => {
          const playing = c.id === currentId;
          return (
            <li key={c.id}>
              <button onClick={() => (playing ? onClose() : onPick(c.id))} aria-current={playing ? "true" : undefined}
                data-testid={`pick-${c.id}`}
                className={`w-full flex items-center gap-4 text-left px-3 py-3 rounded-xl ${playing ? "bg-[#FF3B30]/15 border border-[#FF3B30]/40" : "hover:bg-white/10 border border-transparent"}`}>
                <span className="w-8 text-right font-display text-xl tabular-nums text-gray-400">{c.number}</span>
                <img src={resolveMedia(c.thumbnail_url)} alt="" className="w-16 aspect-video object-cover rounded-md bg-white/5" />
                <span className="min-w-0 flex-1">
                  <span className="block font-medium truncate">{c.title}</span>
                  <span className="block text-xs text-gray-400 truncate">{c.now ? c.now.title : c.category}</span>
                </span>
                {playing && <span className="text-[10px] font-bold tracking-widest text-[#FF3B30]">PLAYING</span>}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
