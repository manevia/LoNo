import { useEffect, useState } from "react";
import { AudioLines, Captions, ChevronFirst, ChevronLast, Gauge, ListVideo, Maximize, Minimize, Pause, Play, Radio, RotateCcw, RotateCw, Settings2, Square, Star } from "lucide-react";
import OptionMenu from "@/components/tv/OptionMenu";
import useMediaState, { formatTime } from "@/components/tv/useMediaState";

const btn = "inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-medium bg-white/10 hover:bg-white/20 border border-white/10 disabled:opacity-40";
const SPEEDS = [0.75, 1, 1.25, 1.5, 2];

/**
 * Remote-friendly controls for the TV player. Every control is a real button, so
 * arrows/OK work through TV mode's spatial navigation, and mouse/touch still work.
 *   mode="vod":  play/pause, seek bar (Left/Right = ±10 s), previous/next, captions, audio, quality, speed
 *   mode="live": play/stop (stop = disconnect; play = reconnect at the live edge);
 *                with time-shifting also pause, rewind and Go Live; Channels picker; favorite
 */
export default function PlayerControls({
  mode, getMedia, getHls, streamKey, stopped, onStop, onPlayLive, onPrev, onNext, prevLabel, nextLabel,
  onOpenPicker, pickerLabel = "Channels", favorite, onToggleFavorite, hasCaptions, firstRef,
  onFullscreen, isFullscreen,
}) {
  const st = useMediaState(getMedia, getHls, [streamKey, stopped]);
  const [menu, setMenu] = useState(null);
  const [captionsOn, setCaptionsOn] = useState(true);
  const [speed, setSpeed] = useState(1);
  const hls = getHls?.();
  const levels = hls?.levels || [];
  const audioTracks = hls?.audioTracks || [];

  useEffect(() => { setMenu(null); }, [streamKey]);
  useEffect(() => {
    const m = getMedia();
    if (m) [...m.textTracks].forEach((t) => { t.mode = captionsOn ? "showing" : "disabled"; });
  }, [captionsOn, getMedia, streamKey]);
  useEffect(() => { const m = getMedia(); if (m) m.playbackRate = speed; }, [speed, getMedia, streamKey]);

  const seekBy = (d) => {
    const m = getMedia(); if (!m) return;
    const s = m.seekable;
    const lo = s.length ? s.start(0) : 0, hi = s.length ? s.end(s.length - 1) : m.duration || 0;
    m.currentTime = Math.max(lo, Math.min(hi - 0.5, m.currentTime + d));
  };
  const goLive = () => { const m = getMedia(); const h = getHls?.(); if (!m) return; const s = m.seekable; m.currentTime = h?.liveSyncPosition ?? (s.length ? s.end(s.length - 1) - 2 : m.currentTime); m.play().catch(() => {}); };
  const togglePlay = () => { const m = getMedia(); if (!m) return; if (m.paused) m.play().catch(() => {}); else m.pause(); };

  const live = mode === "live";
  const canPause = !live || st.timeShift;
  const showSeekBar = !live && st.duration > 0;
  const progress = st.duration ? (st.time / st.duration) * 100 : 0;

  return (
    <div className="w-full" data-testid="tv-controls">
      {showSeekBar && (
        <div
          role="slider" tabIndex={0} aria-label="Seek" aria-valuemin={0} aria-valuemax={Math.round(st.duration)}
          aria-valuenow={Math.round(st.time)} aria-valuetext={`${formatTime(st.time)} of ${formatTime(st.duration)}`}
          data-testid="seek-bar"
          onKeyDown={(e) => {
            if (e.key === "ArrowLeft") { e.preventDefault(); e.stopPropagation(); seekBy(-10); }
            if (e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); seekBy(10); }
          }}
          onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); const m = getMedia(); if (m && st.duration) m.currentTime = ((e.clientX - r.left) / r.width) * st.duration; }}
          className="group mb-4 py-3 cursor-pointer rounded-lg">
          <div className="flex justify-between text-sm text-gray-300 mb-2 tabular-nums"><span>{formatTime(st.time)}</span><span>{formatTime(st.duration)}</span></div>
          <div className="h-2 rounded-full bg-white/20 overflow-hidden"><div className="h-full bg-[#FF3B30]" style={{ width: `${progress}%` }} /></div>
          <div className="mt-1.5 text-xs text-gray-400 opacity-0 group-focus:opacity-100">Left and Right skip 10 seconds</div>
        </div>
      )}

      {live && st.timeShift && !stopped && (
        <div className="mb-3 text-sm tabular-nums" data-testid="live-position">
          {st.behind > 8
            ? <span className="text-gray-300">{formatTime(st.behind)} behind live</span>
            : <span className="inline-flex items-center gap-1.5 text-[#FF3B30] font-semibold"><span className="w-2 h-2 rounded-full bg-[#FF3B30]" /> LIVE</span>}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2" role="toolbar" aria-label="Player controls">
        {live && stopped ? (
          <button ref={firstRef} className={btn} onClick={onPlayLive} data-testid="ctl-play"><Play className="w-4 h-4" /> Play</button>
        ) : canPause ? (
          <button ref={firstRef} className={btn} onClick={togglePlay} data-testid="ctl-playpause" aria-label={st.paused ? "Play" : "Pause"}>
            {st.paused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />} {st.paused ? "Play" : "Pause"}
          </button>
        ) : (
          <button ref={firstRef} className={btn} onClick={onStop} data-testid="ctl-stop"><Square className="w-4 h-4" /> Stop</button>
        )}
        {live && st.timeShift && !stopped && <button className={btn} onClick={onStop} data-testid="ctl-stop"><Square className="w-4 h-4" /> Stop</button>}

        {!live && <button className={btn} onClick={() => seekBy(-10)} aria-label="Back 10 seconds" data-testid="ctl-rew"><RotateCcw className="w-4 h-4" /> 10s</button>}
        {!live && <button className={btn} onClick={() => seekBy(30)} aria-label="Forward 30 seconds" data-testid="ctl-ff"><RotateCw className="w-4 h-4" /> 30s</button>}
        {live && st.timeShift && !stopped && <>
          <button className={btn} onClick={() => seekBy(-10)} data-testid="ctl-rewind"><RotateCcw className="w-4 h-4" /> Rewind 10s</button>
          <button className={btn} onClick={goLive} disabled={st.behind <= 8} data-testid="ctl-golive"><Radio className="w-4 h-4" /> Go Live</button>
        </>}

        {onFullscreen && (
          <button className={btn} onClick={onFullscreen} data-testid="ctl-fullscreen">
            {isFullscreen ? <Minimize className="w-4 h-4" /> : <Maximize className="w-4 h-4" />} {isFullscreen ? "Exit full screen" : "Full screen"}
          </button>
        )}
        {onPrev && <button className={btn} onClick={onPrev} data-testid="ctl-prev"><ChevronFirst className="w-4 h-4" /> {prevLabel || "Previous"}</button>}
        {onNext && <button className={btn} onClick={onNext} data-testid="ctl-next">{nextLabel || "Next"} <ChevronLast className="w-4 h-4" /></button>}

        {onOpenPicker && <button className={btn} onClick={onOpenPicker} data-testid="ctl-picker"><ListVideo className="w-4 h-4" /> {pickerLabel}</button>}
        {onToggleFavorite && (
          <button className={btn} onClick={onToggleFavorite} aria-pressed={!!favorite} data-testid="ctl-favorite">
            <Star className={`w-4 h-4 ${favorite ? "fill-[#FFB000] text-[#FFB000]" : ""}`} /> {favorite ? "Favorite" : "Add to favorites"}
          </button>
        )}

        <div className="relative ml-auto flex flex-wrap gap-2">
          {hasCaptions && (
            <div className="relative">
              <button className={btn} onClick={() => setMenu(menu === "cc" ? null : "cc")} aria-expanded={menu === "cc"} data-testid="ctl-captions"><Captions className="w-4 h-4" /> Captions</button>
              {menu === "cc" && <OptionMenu title="Captions" testId="menu-captions" value={captionsOn} onPick={setCaptionsOn} onClose={() => setMenu(null)}
                options={[{ value: true, label: "English" }, { value: false, label: "Off" }]} />}
            </div>
          )}
          {audioTracks.length > 1 && (
            <div className="relative">
              <button className={btn} onClick={() => setMenu(menu === "audio" ? null : "audio")} aria-expanded={menu === "audio"} data-testid="ctl-audio"><AudioLines className="w-4 h-4" /> Audio</button>
              {menu === "audio" && <OptionMenu title="Audio" testId="menu-audio" value={hls.audioTrack} onPick={(v) => { hls.audioTrack = v; }} onClose={() => setMenu(null)}
                options={audioTracks.map((t, i) => ({ value: i, label: t.name || t.lang || `Track ${i + 1}` }))} />}
            </div>
          )}
          {levels.length > 1 && (
            <div className="relative">
              <button className={btn} onClick={() => setMenu(menu === "q" ? null : "q")} aria-expanded={menu === "q"} data-testid="ctl-quality"><Settings2 className="w-4 h-4" /> Quality</button>
              {menu === "q" && <OptionMenu title="Quality" testId="menu-quality" value={hls.manualLevel ?? -1} onClose={() => setMenu(null)}
                onPick={(v) => { hls.autoLevelCapping = -1; hls.currentLevel = v; }}
                options={[{ value: -1, label: "Automatic" }, ...levels.map((l, i) => ({ value: i, label: l.height ? `${l.height}p` : `${Math.round(l.bitrate / 1000)} kbps` }))]} />}
            </div>
          )}
          {!live && (
            <div className="relative">
              <button className={btn} onClick={() => setMenu(menu === "speed" ? null : "speed")} aria-expanded={menu === "speed"} data-testid="ctl-speed"><Gauge className="w-4 h-4" /> {speed === 1 ? "Speed" : `${speed}×`}</button>
              {menu === "speed" && <OptionMenu title="Playback speed" testId="menu-speed" value={speed} onPick={setSpeed} onClose={() => setMenu(null)}
                options={SPEEDS.map((v) => ({ value: v, label: v === 1 ? "Normal" : `${v}×` }))} />}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
