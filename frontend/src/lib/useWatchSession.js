import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";

/**
 * Server-verified Watch-to-Earn. Attach the returned handlers to a <video>/<audio>.
 * The server only credits wall-clock time between heartbeats sent while playing.
 */
export default function useWatchSession(contentId, user, onEarn) {
  const [state, setState] = useState({ session: null, earned: 0, verified: 0, dailyRemaining: null, capped: false });
  const sessionRef = useRef(null);
  const timerRef = useRef(null);
  const mediaRef = useRef(null);
  const startingRef = useRef(null);

  const beat = useCallback(async (playing = true) => {
    const s = sessionRef.current;
    if (!s || !user) return;
    try {
      const { data } = await api.post("/watch/heartbeat", {
        session_id: s.session_id, playing, position_sec: mediaRef.current?.currentTime || 0,
      });
      setState((st) => ({ ...st, earned: data.session_earned, verified: data.verified_sec,
        dailyRemaining: data.daily_remaining, capped: data.capped }));
      if (data.earned_now > 0) {
        toast.success(`+${data.earned_now} $LONO`, { description: "Watch-to-Earn credited to your wallet" });
        onEarn?.();
      }
    } catch { /* network blips are fine; next beat catches up */ }
  }, [user, onEarn]);

  const stopTimer = () => { clearInterval(timerRef.current); timerRef.current = null; };

  const onPlay = useCallback(async (e) => {
    mediaRef.current = e.currentTarget;
    if (!sessionRef.current) {
      if (!startingRef.current) {
        startingRef.current = api.post("/watch/start", { content_id: contentId }).then(({ data }) => data);
      }
      try {
        const data = await startingRef.current;
        sessionRef.current = data;
        setState((st) => ({ ...st, session: data, dailyRemaining: data.daily_remaining }));
      } catch { return; }
    } else {
      beat(false); // resuming: reset the server clock without crediting the pause
    }
    if (user && !timerRef.current) {
      timerRef.current = setInterval(() => beat(true), (sessionRef.current?.heartbeat_sec || 30) * 1000);
    }
  }, [contentId, user, beat]);

  const onPause = useCallback(() => { stopTimer(); beat(true); }, [beat]);

  useEffect(() => {
    sessionRef.current = null; startingRef.current = null;
    setState({ session: null, earned: 0, verified: 0, dailyRemaining: null, capped: false });
    return () => { stopTimer(); };
  }, [contentId]);

  return { ...state, mediaProps: { onPlay, onPause, onEnded: onPause } };
}
