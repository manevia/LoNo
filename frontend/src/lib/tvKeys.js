// Remote-control keys across platforms. Browsers report most of these as
// KeyboardEvent.key values; some TVs only give a numeric keyCode.
//   Samsung Tizen: 10009 Return, 427/428 Channel up/down, 10252 Play/Pause, 415 Play,
//                  19 Pause, 413 Stop, 412 Rewind, 417 Fast-forward, 10233/10232 Next/Previous
//   LG webOS:      461 Back, 33/34 Channel up/down (also PageUp/PageDown), 415/19/413/412/417
//   Android TV / Fire TV WebView and HbbTV: standard key names (ChannelUp, MediaPlayPause, ...)
const BY_KEY = {
  ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right", Enter: "ok",
  GoBack: "back", BrowserBack: "back", Escape: "back", Backspace: "back",
  ChannelUp: "channelUp", ChannelDown: "channelDown", PageUp: "channelUp", PageDown: "channelDown",
  MediaPlayPause: "playPause", MediaPlay: "play", MediaPause: "pause", MediaStop: "stop",
  MediaRewind: "rewind", MediaFastForward: "fastForward", MediaTrackNext: "next", MediaTrackPrevious: "previous",
  " ": "playPause", // space bar on keyboards
};
const BY_CODE = {
  10009: "back", 461: "back", 427: "channelUp", 428: "channelDown", 33: "channelUp", 34: "channelDown",
  10252: "playPause", 415: "play", 19: "pause", 413: "stop", 412: "rewind", 417: "fastForward",
  10233: "next", 10232: "previous", 179: "playPause", 178: "stop", 176: "next", 177: "previous",
};

export function tvKey(e) {
  return BY_CODE[e.keyCode] || BY_KEY[e.key] || null;
}

export const MEDIA_KEYS = new Set(["playPause", "play", "pause", "stop", "rewind", "fastForward", "next", "previous", "channelUp", "channelDown"]);

export function isTyping(el = document.activeElement) {
  if (!el) return false;
  const tag = el.tagName;
  return el.isContentEditable || tag === "TEXTAREA" || tag === "SELECT" ||
    (tag === "INPUT" && !["checkbox", "radio", "button", "submit", "range"].includes(el.type));
}
