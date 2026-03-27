/**
 * Client-side video generation using Canvas + MediaRecorder.
 * Creates MP4 (H.264 + AAC) from slide images + HeyGen video overlays + ElevenLabs audio.
 * No server-side FFmpeg needed.
 */

function pickMimeType() {
  const candidates = [
    { mime: 'video/mp4;codecs=avc1,mp4a.40.2', ext: 'mp4' },
    { mime: 'video/mp4;codecs=avc1', ext: 'mp4' },
    { mime: 'video/mp4', ext: 'mp4' },
    { mime: 'video/webm;codecs=vp9,opus', ext: 'webm' },
    { mime: 'video/webm;codecs=vp8,opus', ext: 'webm' },
    { mime: 'video/webm;codecs=vp9', ext: 'webm' },
    { mime: 'video/webm', ext: 'webm' },
  ];
  for (const c of candidates) {
    if (MediaRecorder.isTypeSupported(c.mime)) return c;
  }
  return { mime: 'video/webm', ext: 'webm' };
}

function loadVideo(proxyUrl) {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    video.crossOrigin = 'anonymous';
    video.preload = 'auto';
    video.playsInline = true;
    video.muted = true;
    const timeout = setTimeout(() => {
      video.oncanplaythrough = null;
      if (video.readyState >= 2) resolve(video);
      else reject(new Error('Video load timeout'));
    }, 60000);
    video.oncanplaythrough = () => { clearTimeout(timeout); resolve(video); };
    video.onerror = () => { clearTimeout(timeout); reject(new Error('Failed to load video')); };
    video.src = proxyUrl;
    video.load();
  });
}

function loadImage(dataUrl, index) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      if (img.naturalWidth === 0) { reject(new Error(`Slide ${index + 1}: zero dim`)); return; }
      resolve(img);
    };
    img.onerror = () => reject(new Error(`Slide ${index + 1}: load failed`));
    img.src = dataUrl;
  });
}

/**
 * Load an audio file and decode it into an AudioBuffer for Web Audio API playback.
 */
async function loadAudioBuffer(audioCtx, url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Audio fetch failed: ${resp.status}`);
  const arrayBuffer = await resp.arrayBuffer();
  return audioCtx.decodeAudioData(arrayBuffer);
}

/**
 * Draw video preserving aspect ratio within the target rectangle.
 */
function drawVideoFit(ctx, video, tx, ty, tw, th) {
  const vw = video.videoWidth;
  const vh = video.videoHeight;
  if (!vw || !vh) { ctx.drawImage(video, tx, ty, tw, th); return; }
  const va = vw / vh, ta = tw / th;
  let dw, dh, dx, dy;
  if (va > ta) { dw = tw; dh = tw / va; dx = tx; dy = ty + (th - dh) / 2; }
  else { dh = th; dw = th * va; dx = tx + (tw - dw) / 2; dy = ty; }
  ctx.drawImage(video, dx, dy, dw, dh);
}

export async function generateVideoClientSide({ apiUrl, projectId, defaultDuration, onProgress }) {
  onProgress(5, 'Buscando dados dos slides...');

  const response = await fetch(`${apiUrl}/api/course/${projectId}/export-video-frames`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ default_duration: defaultDuration }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Erro ao gerar frames' }));
    throw new Error(err.detail || `HTTP ${response.status}`);
  }

  const data = await response.json();
  const { frames, width, height, projectName } = data;
  if (!frames || frames.length === 0) throw new Error('Nenhum slide encontrado.');

  // ── Audio Context (needed early for decoding) ──
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === 'suspended') await audioCtx.resume();
  const mixDest = audioCtx.createMediaStreamDestination();

  onProgress(8, `Carregando ${frames.length} imagens...`);

  // ── Load slide images ──
  const images = [];
  for (let i = 0; i < frames.length; i++) {
    try {
      images.push(await loadImage(frames[i].dataUrl, i));
      console.log(`[VideoExport] Slide ${i + 1}: OK`);
    } catch (e) {
      console.error(`[VideoExport] ${e.message}`);
      const c = document.createElement('canvas');
      c.width = width; c.height = height;
      const cx = c.getContext('2d');
      cx.fillStyle = '#1a1a2e'; cx.fillRect(0, 0, width, height);
      cx.fillStyle = '#fff'; cx.font = '32px sans-serif'; cx.textAlign = 'center';
      cx.fillText(`Slide ${i + 1}`, width / 2, height / 2);
      const fb = new Image(); fb.src = c.toDataURL();
      await new Promise(r => { fb.onload = r; });
      images.push(fb);
    }
    onProgress(8 + Math.round(((i + 1) / frames.length) * 10), `Imagem ${i + 1}/${frames.length}`);
  }

  // ── Load HeyGen videos ──
  const slideVideos = [];
  for (let i = 0; i < frames.length; i++) {
    const vels = frames[i].videoElements || [];
    if (vels.length > 0) {
      onProgress(19 + Math.round((i / frames.length) * 4), `Video slide ${i + 1}...`);
      const loaded = [];
      for (const vel of vels) {
        try {
          const v = await loadVideo(`${apiUrl}/api/proxy-video?url=${encodeURIComponent(vel.src)}`);
          loaded.push({ video: v, x: vel.x, y: vel.y, width: vel.width, height: vel.height });
          console.log(`[VideoExport] Slide ${i + 1}: HeyGen ${v.videoWidth}x${v.videoHeight} ${v.duration.toFixed(1)}s`);
        } catch (e) {
          console.warn(`[VideoExport] Slide ${i + 1}: HeyGen failed - ${e.message}`);
        }
      }
      slideVideos[i] = loaded;
    } else {
      slideVideos[i] = [];
    }
  }

  // ── Load ElevenLabs / slide audio as AudioBuffers ──
  const slideAudioBuffers = []; // array of { buffer, startTime, volume }[] per slide
  for (let i = 0; i < frames.length; i++) {
    const audioEls = frames[i].audioElements || [];
    const loaded = [];
    for (const aud of audioEls) {
      try {
        const url = aud.src.startsWith('http') ? aud.src : `${apiUrl}${aud.src}`;
        onProgress(24 + Math.round((i / frames.length) * 4), `Audio slide ${i + 1}...`);
        const buffer = await loadAudioBuffer(audioCtx, url);
        loaded.push({ buffer, startTime: aud.startTime || 0, volume: aud.volume || 1.0 });
        console.log(`[VideoExport] Slide ${i + 1}: audio ${buffer.duration.toFixed(1)}s`);
      } catch (e) {
        console.warn(`[VideoExport] Slide ${i + 1}: audio failed - ${e.message}`);
      }
    }
    slideAudioBuffers[i] = loaded;
  }

  // ── Load global audio (background music) ──
  let globalAudioSource = null;
  const globalAudioData = frames[0]?.globalAudio;
  if (globalAudioData) {
    try {
      const url = globalAudioData.src.startsWith('http') ? globalAudioData.src : `${apiUrl}${globalAudioData.src}`;
      const buffer = await loadAudioBuffer(audioCtx, url);
      console.log(`[VideoExport] Global audio: ${buffer.duration.toFixed(1)}s`);
      globalAudioSource = { buffer, volume: globalAudioData.volume || 0.5, loop: globalAudioData.loop };
    } catch (e) {
      console.warn('[VideoExport] Global audio failed:', e.message);
    }
  }

  onProgress(28, 'Preparando gravacao...');

  // ── Setup canvas ──
  const canvas = document.createElement('canvas');
  canvas.width = width; canvas.height = height;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(images[0], 0, 0, width, height);

  const { mime: mimeType, ext: fileExt } = pickMimeType();
  console.log(`[VideoExport] Format: ${mimeType} (.${fileExt})`);

  // ── Connect HeyGen video audio to mixer ──
  const videoGains = new Map();
  for (const vList of slideVideos) {
    for (const { video } of vList) {
      try {
        video.muted = false;
        const src = audioCtx.createMediaElementSource(video);
        const gain = audioCtx.createGain();
        gain.gain.value = 0;
        src.connect(gain);
        gain.connect(mixDest);
        videoGains.set(video, gain);
      } catch (e) {
        console.warn('[VideoExport] HeyGen audio setup:', e.message);
      }
    }
  }

  // ── Build combined stream ──
  const canvasStream = canvas.captureStream(30);
  const combined = new MediaStream();
  for (const t of canvasStream.getVideoTracks()) combined.addTrack(t);
  for (const t of mixDest.stream.getAudioTracks()) combined.addTrack(t);

  let recorder;
  try {
    recorder = new MediaRecorder(combined, { mimeType, videoBitsPerSecond: 2500000 });
  } catch (e) {
    throw new Error('Navegador nao suporta gravacao. Tente Chrome ou Edge.');
  }

  const chunks = [];
  recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };

  // ── Recording loop ──
  return new Promise((resolve, reject) => {
    // Track active AudioBufferSourceNodes for cleanup
    const activeAudioSources = [];

    recorder.onstop = () => {
      // Stop all audio
      for (const s of activeAudioSources) { try { s.stop(); } catch (e) { /* */ } }
      try { audioCtx.close(); } catch (e) { /* */ }

      const blob = new Blob(chunks, { type: mimeType });
      const safeName = projectName.replace(/[^\w\s-]/g, '').replace(/\s+/g, '_');
      const ts = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15);
      onProgress(100, 'Video pronto!');
      resolve({ blob, filename: `${safeName}_${ts}.${fileExt}` });
    };
    recorder.onerror = (e) => reject(new Error('MediaRecorder: ' + (e.error?.message || 'erro')));
    recorder.start(1000);

    // Start global background audio
    if (globalAudioSource) {
      const src = audioCtx.createBufferSource();
      src.buffer = globalAudioSource.buffer;
      src.loop = !!globalAudioSource.loop;
      const gain = audioCtx.createGain();
      gain.gain.value = globalAudioSource.volume;
      src.connect(gain);
      gain.connect(mixDest);
      src.start(0);
      activeAudioSources.push(src);
    }

    let currentSlide = 0;
    let slideStart = performance.now();
    let animId = null;

    function startSlide(idx) {
      // HeyGen video audio
      for (const { video } of (slideVideos[idx] || [])) {
        const g = videoGains.get(video);
        if (g) g.gain.value = 1.0;
        video.currentTime = 0;
        video.play().catch(() => {});
      }
      // ElevenLabs / slide audio (AudioBuffer sources)
      for (const { buffer, startTime, volume } of (slideAudioBuffers[idx] || [])) {
        const src = audioCtx.createBufferSource();
        src.buffer = buffer;
        const gain = audioCtx.createGain();
        gain.gain.value = volume;
        src.connect(gain);
        gain.connect(mixDest);
        // Play after startTime offset (relative to slide start)
        src.start(audioCtx.currentTime + startTime);
        activeAudioSources.push(src);
      }
    }

    function stopSlide(idx) {
      for (const { video } of (slideVideos[idx] || [])) {
        const g = videoGains.get(video);
        if (g) g.gain.value = 0;
        video.pause();
      }
      // AudioBufferSource nodes stop automatically when buffer ends
      // No need to stop them manually (they're one-shot)
    }

    function slideDuration(idx) {
      const base = frames[idx]?.duration || defaultDuration;
      // Extend for HeyGen video
      const vids = slideVideos[idx] || [];
      let maxD = base;
      if (vids.length > 0) {
        const vMax = Math.max(...vids.map(v => v.video.duration || 0));
        if (vMax > 0 && isFinite(vMax)) maxD = Math.max(maxD, vMax);
      }
      // Extend for slide audio duration
      for (const { buffer, startTime } of (slideAudioBuffers[idx] || [])) {
        const audioDur = startTime + buffer.duration;
        if (audioDur > maxD) maxD = audioDur;
      }
      return maxD;
    }

    // Init
    startSlide(0);

    function render() {
      const elapsed = (performance.now() - slideStart) / 1000;
      const dur = slideDuration(currentSlide);

      if (elapsed >= dur) {
        stopSlide(currentSlide);
        currentSlide++;
        slideStart = performance.now();

        if (currentSlide >= images.length) {
          ctx.drawImage(images[images.length - 1], 0, 0, width, height);
          setTimeout(() => { cancelAnimationFrame(animId); recorder.stop(); }, 500);
          return;
        }

        startSlide(currentSlide);
        const pct = 30 + Math.round(((currentSlide + 1) / images.length) * 65);
        onProgress(pct, `Gravando slide ${currentSlide + 1}/${images.length}...`);
      }

      // DRAW: slide background, then video overlay
      ctx.drawImage(images[currentSlide], 0, 0, width, height);

      for (const { video, x, y, width: vw, height: vh } of (slideVideos[currentSlide] || [])) {
        if (video.readyState >= 2 && !video.paused && !video.ended) {
          try { drawVideoFit(ctx, video, x, y, vw, vh); } catch (e) { /* CORS */ }
        }
      }

      animId = requestAnimationFrame(render);
    }

    onProgress(30, `Gravando slide 1/${images.length}...`);
    render();
  });
}
