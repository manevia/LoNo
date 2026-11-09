// Publish a camera/mic stream to LoNo with WHIP (WebRTC-HTTP ingest).
// The offer goes to LoNo's API, which adds the creator's stream key server-side.
import { api } from "@/lib/api";

function preferH264(pc) {
  // H.264 can be forwarded to social platforms without re-encoding.
  const caps = RTCRtpSender.getCapabilities?.("video");
  if (!caps) return;
  const h264 = caps.codecs.filter((c) => /h264/i.test(c.mimeType));
  const rest = caps.codecs.filter((c) => !/h264/i.test(c.mimeType));
  for (const t of pc.getTransceivers()) {
    if (t.sender.track?.kind === "video" && h264.length && t.setCodecPreferences) {
      try { t.setCodecPreferences([...h264, ...rest]); } catch { /* not supported */ }
    }
  }
}

function waitForIce(pc, ms = 2500) {
  if (pc.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => { if (pc.iceGatheringState === "complete") { pc.removeEventListener("icegatheringstatechange", done); resolve(); } };
    pc.addEventListener("icegatheringstatechange", done);
    setTimeout(resolve, ms);
  });
}

export async function publishWhip({ video, audio, onState }) {
  const pc = new RTCPeerConnection({ iceServers: [] });
  const senders = {};
  if (video) senders.video = pc.addTransceiver(video, { direction: "sendonly", sendEncodings: [{ maxBitrate: 2_500_000 }] }).sender;
  if (audio) senders.audio = pc.addTransceiver(audio, { direction: "sendonly" }).sender;
  preferH264(pc);
  pc.addEventListener("connectionstatechange", () => onState?.(pc.connectionState));
  await pc.setLocalDescription(await pc.createOffer());
  await waitForIce(pc);
  const { data } = await api.post("/broadcast/whip", pc.localDescription.sdp, {
    headers: { "Content-Type": "application/sdp" }, transformRequest: [(d) => d], responseType: "text",
  });
  await pc.setRemoteDescription({ type: "answer", sdp: data });

  let last = null;
  return {
    pc,
    /** Swap camera or mic while live, without reconnecting. */
    async replace(kind, track) { if (senders[kind]) await senders[kind].replaceTrack(track); },
    async stats() {
      const report = await pc.getStats();
      let bytes = 0, lost = 0, sent = 0, rtt = null, ts = 0;
      report.forEach((r) => {
        if (r.type === "outbound-rtp") { bytes += r.bytesSent || 0; sent += r.packetsSent || 0; ts = r.timestamp; }
        if (r.type === "remote-inbound-rtp") { lost += r.packetsLost || 0; if (r.roundTripTime != null) rtt = r.roundTripTime; }
        if (r.type === "candidate-pair" && r.state === "succeeded" && r.currentRoundTripTime != null) rtt = r.currentRoundTripTime;
      });
      let kbps = null;
      if (last && ts > last.ts) kbps = Math.round(((bytes - last.bytes) * 8) / (ts - last.ts));
      last = { bytes, ts };
      return { kbps, rttMs: rtt != null ? Math.round(rtt * 1000) : null, lossPct: sent ? +((lost / (sent + lost)) * 100).toFixed(1) : 0, state: pc.connectionState };
    },
    async stop() {
      pc.close();
      try { await api.delete("/broadcast/whip"); } catch { /* already gone */ }
    },
  };
}
