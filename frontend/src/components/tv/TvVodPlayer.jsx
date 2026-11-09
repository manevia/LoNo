import { useCallback, useEffect, useRef, useState } from "react";
import MediaPlayer from "@/components/MediaPlayer";
import PlayerControls from "@/components/tv/PlayerControls";
import { tvKey, isTyping } from "@/lib/tvKeys";
import { useBack } from "@/lib/backStack";

const HIDE_AFTER_MS = 5000;

/**
 * On-demand player for TV mode: the existing MediaPlayer with remote controls.
 * Full screen hides the controls while playing; OK or any arrow reveals them,
 * and Back leaves full screen before leaving the page.
 */
export default function TvVodPlayer({ item, audio, src, poster, subtitleUrl, artist, mediaProps, onLoadedMetadata, onPrev, onNext, prevLabel, nextLabel }) {
  const media = useRef(null);
  const hls = useRef(null);
  const first = useRef(null);
  const timer = useRef(null);
  const [full, setFull] = useState(false);
  const [visible, setVisible] = useState(true);

  const poke = useCallback(() => {
    setVisible(true);
    clearTimeout(timer.current);
    if (full) timer.current = setTimeout(() => { if (media.current && !media.current.paused) setVisible(false); }, HIDE_AFTER_MS);
  }, [full]);
  useEffect(() => { poke(); return () => clearTimeout(timer.current); }, [poke]);
  useBack(full, () => { setFull(false); setVisible(true); setTimeout(() => first.current?.focus(), 0); });

  useEffect(() => {
    const onKey = (e) => {
      if (isTyping()) return;
      const k = tvKey(e);
      const m = media.current;
      if (!k || !m) return;
      if (k === "playPause" || k === "play" || k === "pause") {
        if (e.key === " " && document.activeElement?.tagName === "BUTTON") return;
        e.preventDefault();
        if (k === "pause" || (k === "playPause" && !m.paused)) m.pause(); else m.play().catch(() => {});
        poke(); return;
      }
      if (k === "stop") { e.preventDefault(); m.pause(); m.currentTime = 0; poke(); return; }
      if (k === "rewind" || k === "fastForward") { e.preventDefault(); m.currentTime = Math.max(0, m.currentTime + (k === "rewind" ? -10 : 30)); poke(); return; }
      if (k === "next" && onNext) { e.preventDefault(); onNext(); return; }
      if (k === "previous" && onPrev) { e.preventDefault(); onPrev(); return; }
      if (full && !visible && ["up", "down", "left", "right", "ok"].includes(k)) {
        e.preventDefault(); e.stopPropagation();
        setVisible(true); poke();
        setTimeout(() => first.current?.focus(), 0);
        return;
      }
      if (full) poke();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [full, visible, poke, onNext, onPrev]);

  const enter = () => { setFull(true); setVisible(true); setTimeout(() => first.current?.focus(), 0); };

  return (
    <div data-testid="tv-vod-player" onMouseMove={poke}
      className={full ? "fixed inset-0 z-[60] bg-black" : "relative"}>
      <MediaPlayer
        key={item.id} ref={media} testId={audio ? "audio-player" : "video-player"} audio={audio} src={src} poster={poster}
        title={item.title} artist={artist} artwork={poster} subtitleUrl={subtitleUrl}
        nativeControls={false} showOptions={false} mediaProps={mediaProps} onLoadedMetadata={onLoadedMetadata}
        onHls={(h) => { hls.current = h; }}
        className={audio ? "hidden" : full ? "w-full h-full object-contain bg-black" : "w-full aspect-video rounded-2xl bg-black ring-1 ring-white/10"}
      />
      {audio && !full && <div className="aspect-video rounded-2xl bg-[#121212] ring-1 ring-white/10 grid place-items-center text-gray-400">{item.title}</div>}
      <div className={full ? `absolute inset-x-0 bottom-0 bg-gradient-to-t from-black via-black/85 to-transparent pt-24 pb-8 px-6 md:px-12 transition-opacity duration-300 ${visible ? "opacity-100" : "opacity-0 pointer-events-none"}` : "mt-4"}
        aria-hidden={full && !visible} inert={full && !visible}>
        {full && <div className="mb-4 font-display text-2xl">{item.title}</div>}
        <PlayerControls
          mode="vod" streamKey={item.id} getMedia={() => media.current} getHls={() => hls.current} firstRef={first}
          hasCaptions={!!subtitleUrl} onPrev={onPrev} onNext={onNext} prevLabel={prevLabel} nextLabel={nextLabel}
          onFullscreen={full ? () => setFull(false) : enter} isFullscreen={full}
        />
        {full && <div className="mt-3 text-xs text-gray-500">OK shows controls · Back exits full screen</div>}
      </div>
    </div>
  );
}
