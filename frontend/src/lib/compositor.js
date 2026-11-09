// Program compositor for the Live Control Room (runs in the producer's browser).
//
// Inputs: contributor feeds (WHEP MediaStreams), an optional clip (<video> of
// LoNo media). Outputs:
//   - program: canvas video + mixed audio → published into the broadcast session
//   - preview: a second canvas the producer sees before TAKE (not published)
//   - returns: per contributor, program audio minus their own mic (+ talkback)
// The program canvas keeps running whatever the sources do, so switching never
// interrupts the broadcast.

const W = 1280, H = 720;

export class Compositor {
  constructor({ programCanvas, previewCanvas, standbyText = "We'll be right back", onFeedLost }) {
    this.program = programCanvas; this.preview = previewCanvas;
    this.program.width = W; this.program.height = H; this.preview.width = W; this.preview.height = H;
    this.pctx = this.program.getContext("2d"); this.vctx = this.preview.getContext("2d");
    this.sources = new Map();          // id -> {video, stream, name, location, showLocation, muted, gain, analyser, returnBus, lastFrameAt, lastTime}
    this.scene = { program: { scene: "standby", sources: [] }, preview: { scene: "standby", sources: [] } };
    this.standbyText = standbyText;
    this.onFeedLost = onFeedLost;
    this.ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 });
    this.programBus = this.ctx.createGain();
    this.programDest = this.ctx.createMediaStreamDestination();
    this.programBus.connect(this.programDest);
    this.programAnalyser = this.ctx.createAnalyser(); this.programBus.connect(this.programAnalyser);
    this.talk = null;                  // {source, gain} producer talkback mic
    this.clip = null;                  // {url, video, node}
    this.lostReported = new Set();
    this.running = true;
    this.videoStream = this.program.captureStream(30);
    if (typeof window !== "undefined") window.__lonoCompositor = this;   // inspection in tests and the browser console
    this._loop();
  }

  /** The stream to publish as the broadcast: canvas video + program mix. */
  get programStream() {
    return new MediaStream([this.videoStream.getVideoTracks()[0], this.programDest.stream.getAudioTracks()[0]]);
  }

  resume() { return this.ctx.resume(); }

  setSource(id, { stream, name, location, showLocation, muted, audioOnly }) {
    let s = this.sources.get(id);
    if (!s) {
      const video = document.createElement("video");
      video.muted = true; video.playsInline = true; video.autoplay = true;
      const gain = this.ctx.createGain(); gain.gain.value = 0;
      const analyser = this.ctx.createAnalyser(); analyser.fftSize = 1024;
      const returnBus = this.ctx.createGain();
      const returnDest = this.ctx.createMediaStreamDestination();
      returnBus.connect(returnDest);
      s = { id, video, gain, analyser, returnBus, returnDest, node: null, stream: null, lastAliveAt: performance.now(), everAlive: false };
      gain.connect(this.programBus);
      this.sources.set(id, s);
      // everyone else's return hears this source; its own return never does (mix-minus)
      for (const other of this.sources.values()) if (other !== s) { gain.connect(other.returnBus); other.gain.connect(s.returnBus); }
      if (this.clip?.node) this.clip.node.connect(s.returnBus);
    }
    Object.assign(s, { name, location, showLocation, muted, audioOnly });
    if (stream && stream !== s.stream) {
      s.stream = stream; s.video.srcObject = stream; s.video.play().catch(() => {});
      s.node?.disconnect(); s.node = null;
      const wire = () => {
        if (s.node || !stream.getAudioTracks().length || s.stream !== stream) return;
        s.node = this.ctx.createMediaStreamSource(stream);
        s.node.connect(s.gain); s.node.connect(s.analyser);
      };
      wire();
      stream.addEventListener("addtrack", wire);   // audio that arrives after the video
      s.lastAliveAt = performance.now(); s.everAlive = false; this.lostReported.delete(id);
    }
    this._applyGains();
  }

  removeSource(id) {
    const s = this.sources.get(id);
    if (!s) return;
    s.node?.disconnect(); s.gain.disconnect(); s.returnBus.disconnect();
    s.video.srcObject = null;
    this.sources.delete(id);
  }

  /** Remove a source's feed (it dropped) but keep its slot and return bus. */
  dropFeed(id) {
    const s = this.sources.get(id);
    if (!s) return;
    s.node?.disconnect(); s.node = null; s.stream = null; s.video.srcObject = null;
  }

  returnStream(id) { return this.sources.get(id)?.returnDest.stream; }

  level(id) {
    const an = id === "program" ? this.programAnalyser : this.sources.get(id)?.analyser;
    if (!an) return -100;
    const buf = new Float32Array(an.fftSize); an.getFloatTimeDomainData(buf);
    let sum = 0; for (const v of buf) sum += v * v;
    return 20 * Math.log10(Math.sqrt(sum / buf.length) || 1e-6);
  }

  setScenes(program, preview) {
    const changed = JSON.stringify(program) !== JSON.stringify(this.scene.program);
    this.scene = { program, preview };
    if (changed) { this._syncClip(program); this._applyGains(); }
  }

  /** Talkback: the producer's mic goes into one contributor's return only. */
  setTalkback(stream, targetId) {
    if (this.talk) { this.talk.source.disconnect(); this.talk = null; }
    if (!stream || !targetId) return;
    const target = this.sources.get(targetId);
    if (!target) return;
    const source = this.ctx.createMediaStreamSource(stream);
    source.connect(target.returnBus);
    this.talk = { source };
  }

  _onAir() { return new Set(this.scene.program.sources || []); }

  _applyGains() {
    const air = this._onAir();
    for (const s of this.sources.values()) {
      s.gain.gain.setTargetAtTime(air.has(s.id) && !s.muted ? 1 : 0, this.ctx.currentTime, 0.05);  // short fade, no clicks
    }
  }

  _syncClip(program) {
    const url = program.scene === "clip" ? program.clip_url : null;
    if (this.clip?.url === url) return;
    if (this.clip) { this.clip.video.pause(); this.clip.node?.disconnect(); this.clip = null; }
    if (!url) return;
    const video = document.createElement("video");
    video.src = url; video.crossOrigin = "anonymous"; video.playsInline = true; video.loop = false;
    const node = this.ctx.createMediaElementSource(video);
    node.connect(this.programBus);
    for (const s of this.sources.values()) node.connect(s.returnBus);  // field reporters hear the clip too
    video.play().catch(() => {});
    this.clip = { url, video, node };
  }

  _drawVideo(ctx, s, x, y, w, h) {
    const v = s?.video;
    if (v && v.readyState >= 2 && v.videoWidth && !s.audioOnly) {
      const r = Math.max(w / v.videoWidth, h / v.videoHeight);       // cover
      const sw = w / r, sh = h / r;
      ctx.drawImage(v, (v.videoWidth - sw) / 2, (v.videoHeight - sh) / 2, sw, sh, x, y, w, h);
    } else {
      ctx.fillStyle = "#111"; ctx.fillRect(x, y, w, h);
      ctx.fillStyle = "#9ca3af"; ctx.font = "600 28px system-ui, sans-serif"; ctx.textAlign = "center";
      ctx.fillText(s?.audioOnly ? `${s.name}: audio only` : s ? `${s.name}: reconnecting…` : "No source", x + w / 2, y + h / 2);
      ctx.textAlign = "left";
    }
  }

  _lowerThird(ctx, s, x, y) {
    if (!s) return;
    const line2 = s.showLocation && s.location ? s.location : "";
    ctx.font = "700 30px system-ui, sans-serif";
    const w = Math.max(ctx.measureText(s.name).width, line2 ? (ctx.font = "400 22px system-ui, sans-serif", ctx.measureText(line2).width) : 0) + 40;
    ctx.fillStyle = "rgba(0,0,0,.72)"; ctx.fillRect(x, y, w, line2 ? 84 : 54);
    ctx.fillStyle = "#FF3B30"; ctx.fillRect(x, y, 6, line2 ? 84 : 54);
    ctx.fillStyle = "#fff"; ctx.font = "700 30px system-ui, sans-serif"; ctx.fillText(s.name, x + 20, y + 38);
    if (line2) { ctx.fillStyle = "#d1d5db"; ctx.font = "400 22px system-ui, sans-serif"; ctx.fillText(line2, x + 20, y + 70); }
  }

  _render(ctx, scene, isProgram) {
    ctx.fillStyle = "#000"; ctx.fillRect(0, 0, W, H);
    const src = (i) => this.sources.get(scene.sources?.[i]);
    if (scene.scene === "single") {
      this._drawVideo(ctx, src(0), 0, 0, W, H); this._lowerThird(ctx, src(0), 48, H - 140);
    } else if (scene.scene === "split") {
      const gap = 12, w = (W - gap * 3) / 2, h = w * 9 / 16, y = (H - h) / 2;
      ctx.fillStyle = "#0b0b0b"; ctx.fillRect(0, 0, W, H);
      this._drawVideo(ctx, src(0), gap, y, w, h); this._drawVideo(ctx, src(1), gap * 2 + w, y, w, h);
      this._lowerThird(ctx, src(0), gap + 20, y + h - 110); this._lowerThird(ctx, src(1), gap * 2 + w + 20, y + h - 110);
    } else if (scene.scene === "clip" && isProgram && this.clip?.video.readyState >= 2) {
      const v = this.clip.video; ctx.drawImage(v, 0, 0, W, H);
    } else if (scene.scene === "clip") {
      ctx.fillStyle = "#111"; ctx.fillRect(0, 0, W, H); ctx.fillStyle = "#9ca3af"; ctx.font = "600 30px system-ui"; ctx.textAlign = "center";
      ctx.fillText("Clip", W / 2, H / 2); ctx.textAlign = "left";
    } else {
      const g = ctx.createLinearGradient(0, 0, W, H); g.addColorStop(0, "#1a0503"); g.addColorStop(1, "#050505");
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = "#FF3B30"; ctx.fillRect(W / 2 - 40, H / 2 - 110, 80, 80);
      ctx.fillStyle = "#fff"; ctx.font = "900 56px system-ui"; ctx.textAlign = "center"; ctx.fillText("L", W / 2, H / 2 - 50);
      ctx.font = "600 40px system-ui"; ctx.fillText(this.standbyText, W / 2, H / 2 + 50); ctx.textAlign = "left";
    }
    if (isProgram) {                     // LIVE bug, top right
      ctx.fillStyle = "#FF3B30"; ctx.fillRect(W - 120, 28, 92, 36);
      ctx.fillStyle = "#fff"; ctx.font = "800 22px system-ui"; ctx.fillText("LIVE", W - 104, 54);
    }
  }

  /** Called by the Control Room while a source's connection is receiving data. */
  alive(id) {
    const s = this.sources.get(id);
    if (s) { s.lastAliveAt = performance.now(); s.everAlive = true; }
  }

  _watchDrops() {
    // An on-air source counts as lost only on network evidence: its data stopped
    // arriving for 4 s, its feed ended, or it never started within 10 s of going
    // on air. Picture redraw timing isn't used (a busy computer can delay it).
    const now = performance.now();
    const air = this._onAir();
    for (const s of this.sources.values()) {
      if (!air.has(s.id)) { s.airSince = null; continue; }
      if (s.airSince == null) s.airSince = now;
    }
    for (const id of air) {
      const s = this.sources.get(id);
      if (!s || id === "local" || this.lostReported.has(id)) continue;
      const onAirFor = now - s.airSince;
      const ended = s.stream && s.stream.getTracks().length > 0 && s.stream.getTracks().every((tr) => tr.readyState === "ended");
      const stopped = s.everAlive && now - s.lastAliveAt > 4000;
      const neverStarted = !s.everAlive && onAirFor > 10000;
      if (ended || stopped || neverStarted) {
        this.lostReported.add(id);
        this.onFeedLost?.(id);
      }
    }
  }

  _loop() {
    if (!this.running) return;
    this._render(this.pctx, this.scene.program, true);
    this._render(this.vctx, this.scene.preview, false);
    this._watchDrops();
    // requestAnimationFrame pauses in background tabs; a timer keeps the program running.
    this._timer = setTimeout(() => this._loop(), 1000 / 30);
  }

  destroy() {
    this.running = false; clearTimeout(this._timer);
    for (const id of [...this.sources.keys()]) this.removeSource(id);
    this.ctx.close().catch(() => {});
  }
}
