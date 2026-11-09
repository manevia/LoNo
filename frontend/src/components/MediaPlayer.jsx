import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { Cast, Gauge, PictureInPicture2, Settings2 } from "lucide-react";
import { usePrefs } from "@/lib/device";

const SPEEDS = [0.75, 1, 1.25, 1.5, 2];
const isHls = (url) => /\.m3u8($|\?)/i.test(url || "");
const chip = "inline-flex items-center gap-1.5 text-xs rounded-full px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 disabled:opacity-40";

/**
 * Video/audio player with adaptive streaming (HLS via hls.js where the browser
 * lacks it natively), data-saver behaviour, a quality menu, lock-screen/TV-remote
 * controls (Media Session), picture-in-picture, casting and playback speed.
 */
const MediaPlayer = forwardRef(function MediaPlayer(
  { src, poster, audio = false, title, artist, artwork, subtitleUrl, live = false, mediaProps = {}, onLoadedMetadata, testId },
  ref,
) {
  const el = useRef(null);
  const hlsRef = useRef(null);
  const { dataSaver } = usePrefs();
  const [levels, setLevels] = useState([]);       // [{index, label}]
  const [level, setLevel] = useState(-1);          // -1 = automatic
  const [speed, setSpeed] = useState(1);
  const [pip, setPip] = useState(false);
  const [canCast, setCanCast] = useState(false);
  useImperativeHandle(ref, () => el.current);

  // Attach the source: native playback, or hls.js for .m3u8 where needed.
  useEffect(() => {
    const media = el.current;
    if (!media || !src) return;
    setLevels([]); setLevel(-1);
    let cancelled = false;
    const nativeHls = media.canPlayType("application/vnd.apple.mpegurl");
    if (!isHls(src) || nativeHls) {
      media.src = src;
      return () => { media.removeAttribute("src"); media.load(); };
    }
    import("hls.js").then(({ default: Hls }) => {
      if (cancelled) return;
      if (!Hls.isSupported()) { media.src = src; return; }
      const hls = new Hls({
        capLevelToPlayerSize: true,          // never fetch more pixels than the screen shows
        startLevel: dataSaver ? 0 : -1,      // data saver starts at the lowest rendition
        maxBufferLength: dataSaver ? 15 : 30,
      });
      hlsRef.current = hls;
      hls.loadSource(src);
      hls.attachMedia(media);
      hls.on(Hls.Events.MANIFEST_PARSED, (_, data) => {
        const list = data.levels.map((l, i) => ({ index: i, label: l.height ? `${l.height}p` : `${Math.round(l.bitrate / 1000)} kbps` }));
        setLevels(list);
        if (dataSaver && list.length) { hls.autoLevelCapping = 0; }
      });
      hls.on(Hls.Events.ERROR, (_, d) => {
        if (!d.fatal) return;
        if (d.type === Hls.ErrorTypes.NETWORK_ERROR) hls.startLoad();
        else if (d.type === Hls.ErrorTypes.MEDIA_ERROR) hls.recoverMediaError();
      });
    });
    return () => { cancelled = true; hlsRef.current?.destroy(); hlsRef.current = null; };
  }, [src, dataSaver]);

  // Lock screen, headphones, car and TV remote media keys.
  useEffect(() => {
    if (!("mediaSession" in navigator) || !title) return;
    const media = el.current;
    navigator.mediaSession.metadata = new window.MediaMetadata({
      title, artist: artist || "LoNo", album: "LoNo",
      artwork: artwork ? [{ src: artwork, sizes: "512x512" }] : [{ src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" }],
    });
    const seek = (d) => { if (media && !live) media.currentTime = Math.max(0, Math.min(media.duration || Infinity, media.currentTime + d)); };
    const handlers = {
      play: () => media?.play(), pause: () => media?.pause(),
      seekbackward: (e) => seek(-(e.seekOffset || 10)), seekforward: (e) => seek(e.seekOffset || 10),
      seekto: (e) => { if (media && !live && e.seekTime != null) media.currentTime = e.seekTime; },
    };
    for (const [k, fn] of Object.entries(handlers)) { try { navigator.mediaSession.setActionHandler(k, fn); } catch { /* unsupported action */ } }
    return () => { for (const k of Object.keys(handlers)) { try { navigator.mediaSession.setActionHandler(k, null); } catch { /* ignore */ } } };
  }, [title, artist, artwork, live]);

  // Casting (Chromecast / smart TVs) via the Remote Playback API, and PiP state.
  useEffect(() => {
    const media = el.current;
    if (!media) return;
    let id;
    if (media.remote?.watchAvailability) {
      media.remote.watchAvailability((a) => setCanCast(a)).then((x) => { id = x; }).catch(() => setCanCast(false));
    }
    const on = () => setPip(true), off = () => setPip(false);
    media.addEventListener("enterpictureinpicture", on);
    media.addEventListener("leavepictureinpicture", off);
    return () => {
      if (id !== undefined) media.remote.cancelWatchAvailability(id).catch(() => {});
      media.removeEventListener("enterpictureinpicture", on);
      media.removeEventListener("leavepictureinpicture", off);
    };
  }, [src]);

  useEffect(() => { if (el.current) el.current.playbackRate = speed; }, [speed]);
  const chooseLevel = (i) => { setLevel(i); if (hlsRef.current) { hlsRef.current.autoLevelCapping = -1; hlsRef.current.currentLevel = i; } };
  const togglePip = async () => {
    try { if (document.pictureInPictureElement) await document.exitPictureInPicture(); else await el.current.requestPictureInPicture(); } catch { /* user gesture or support missing */ }
  };

  const Tag = audio ? "audio" : "video";
  return (
    <div className="w-full">
      <Tag
        ref={el} data-testid={testId} controls playsInline={!audio || undefined} crossOrigin="anonymous"
        poster={audio ? undefined : poster} preload={dataSaver ? "none" : "metadata"}
        onLoadedMetadata={onLoadedMetadata} {...mediaProps}
        className={audio ? "w-full max-w-lg" : "w-full aspect-video rounded-2xl bg-black ring-1 ring-white/10 shadow-2xl"}>
        {subtitleUrl && !audio && <track key={subtitleUrl} kind="subtitles" label="English" srcLang="en" src={subtitleUrl} default />}
      </Tag>
      <div className="mt-3 flex flex-wrap items-center gap-2" aria-label="Player options">
        {!live && (
          <label className={chip}>
            <Gauge className="w-3.5 h-3.5" aria-hidden="true" />
            <span className="sr-only">Playback speed</span>
            <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="bg-transparent outline-none" data-testid="speed-select">
              {SPEEDS.map((s) => <option key={s} value={s} className="bg-[#121212]">{s === 1 ? "Normal speed" : `${s}×`}</option>)}
            </select>
          </label>
        )}
        {levels.length > 1 && (
          <label className={chip}>
            <Settings2 className="w-3.5 h-3.5" aria-hidden="true" />
            <span className="sr-only">Quality</span>
            <select value={level} onChange={(e) => chooseLevel(Number(e.target.value))} className="bg-transparent outline-none" data-testid="quality-select">
              <option value={-1} className="bg-[#121212]">Auto quality{dataSaver ? " (data saver)" : ""}</option>
              {levels.map((l) => <option key={l.index} value={l.index} className="bg-[#121212]">{l.label}</option>)}
            </select>
          </label>
        )}
        {!audio && document.pictureInPictureEnabled && (
          <button type="button" onClick={togglePip} className={chip} aria-pressed={pip} data-testid="pip-btn">
            <PictureInPicture2 className="w-3.5 h-3.5" /> {pip ? "Exit picture-in-picture" : "Picture-in-picture"}
          </button>
        )}
        {canCast && (
          <button type="button" onClick={() => el.current.remote.prompt().catch(() => {})} className={chip} data-testid="cast-btn">
            <Cast className="w-3.5 h-3.5" /> Cast to TV
          </button>
        )}
        {dataSaver && <span className="text-xs text-gray-500">Data saver on</span>}
      </div>
    </div>
  );
});

export default MediaPlayer;
