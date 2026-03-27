/**
 * Client-side video generation using Canvas + MediaRecorder.
 * Creates MP4 (H.264 + AAC) video from slide images + HeyGen video overlays.
 * Includes audio from HeyGen videos via Web Audio API.
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

/**
 * Load an image from a data URL. Uses standard Image element
 * which is the most reliable approach for canvas drawing.
 */
function loadImage(dataUrl, index) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      if (img.naturalWidth === 0) {
        reject(new Error(`Slide ${index + 1}: zero dimensions`));
        return;
      }
      resolve(img);
    };
    img.onerror = () => reject(new Error(`Slide ${index + 1}: load failed`));
    img.src = dataUrl;
  });
}

/**
 * Draw video preserving aspect ratio within the target rectangle.
 * Prevents stretching/distortion ("estourado").
 */
function drawVideoPreserveAspect(ctx, video, targetX, targetY, targetW, targetH) {
  const vw = video.videoWidth;
  const vh = video.videoHeight;
  if (!vw || !vh) {
    // Fallback: draw stretched if we don't know native size
    ctx.drawImage(video, targetX, targetY, targetW, targetH);
    return;
  }

  const videoAspect = vw / vh;
  const targetAspect = targetW / targetH;

  let drawW, drawH, drawX, drawY;

  if (videoAspect > targetAspect) {
    // Video is wider — fit by width, center vertically
    drawW = targetW;
    drawH = targetW / videoAspect;
    drawX = targetX;
    drawY = targetY + (targetH - drawH) / 2;
  } else {
    // Video is taller — fit by height, center horizontally
    drawH = targetH;
    drawW = targetH * videoAspect;
    drawX = targetX + (targetW - drawW) / 2;
    drawY = targetY;
  }

  ctx.drawImage(video, drawX, drawY, drawW, drawH);
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

  if (!frames || frames.length === 0) {
    throw new Error('Nenhum slide encontrado para exportar.');
  }

  onProgress(10, `Carregando ${frames.length} imagens...`);

  // Load all slide images
  const images = [];
  for (let i = 0; i < frames.length; i++) {
    try {
      const img = await loadImage(frames[i].dataUrl, i);
      images.push(img);
      console.log(`[VideoExport] Slide ${i + 1}: OK (${img.naturalWidth}x${img.naturalHeight})`);
    } catch (e) {
      console.error(`[VideoExport] ${e.message}`);
      // Fallback: colored placeholder
      const c = document.createElement('canvas');
      c.width = width;
      c.height = height;
      const cx = c.getContext('2d');
      cx.fillStyle = '#1a1a2e';
      cx.fillRect(0, 0, width, height);
      cx.fillStyle = '#fff';
      cx.font = '32px sans-serif';
      cx.textAlign = 'center';
      cx.fillText(`Slide ${i + 1}`, width / 2, height / 2);
      // Convert canvas to Image for consistent handling
      const fallbackImg = new Image();
      fallbackImg.src = c.toDataURL();
      await new Promise(r => { fallbackImg.onload = r; });
      images.push(fallbackImg);
    }
    onProgress(10 + Math.round(((i + 1) / frames.length) * 12), `Imagem ${i + 1}/${frames.length}`);
  }

  // Load HeyGen overlay videos
  const slideVideos = [];
  for (let i = 0; i < frames.length; i++) {
    const videoEls = frames[i].videoElements || [];
    if (videoEls.length > 0) {
      onProgress(23 + Math.round((i / frames.length) * 5), `Carregando video do slide ${i + 1}...`);
      const loaded = [];
      for (const vel of videoEls) {
        try {
          const proxyUrl = `${apiUrl}/api/proxy-video?url=${encodeURIComponent(vel.src)}`;
          const video = await loadVideo(proxyUrl);
          loaded.push({ video, x: vel.x, y: vel.y, width: vel.width, height: vel.height });
          console.log(`[VideoExport] Slide ${i + 1}: HeyGen ${video.videoWidth}x${video.videoHeight}, ${video.duration.toFixed(1)}s`);
        } catch (e) {
          console.warn(`[VideoExport] Slide ${i + 1}: video failed - ${e.message}`);
        }
      }
      slideVideos[i] = loaded;
    } else {
      slideVideos[i] = [];
    }
  }

  onProgress(28, 'Preparando gravacao...');

  // Create recording canvas
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');

  // Verify canvas
  ctx.fillStyle = '#ff0000';
  ctx.fillRect(0, 0, 2, 2);
  const px = ctx.getImageData(0, 0, 1, 1).data;
  console.log(`[VideoExport] Canvas test: R=${px[0]} (should be 255)`);

  // Draw first slide
  ctx.drawImage(images[0], 0, 0, width, height);

  const { mime: mimeType, ext: fileExt } = pickMimeType();
  console.log(`[VideoExport] Format: ${mimeType} (.${fileExt})`);

  // Audio setup
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === 'suspended') await audioCtx.resume();
  const mixDest = audioCtx.createMediaStreamDestination();

  // Pre-connect all video audio with gain nodes
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
        console.warn('[VideoExport] Audio source error:', e.message);
      }
    }
  }

  // Build combined stream
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

  return new Promise((resolve, reject) => {
    recorder.onstop = () => {
      try { audioCtx.close(); } catch (e) { /* */ }
      const blob = new Blob(chunks, { type: mimeType });
      const safeName = projectName.replace(/[^\w\s-]/g, '').replace(/\s+/g, '_');
      const ts = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15);
      onProgress(100, 'Video pronto!');
      resolve({ blob, filename: `${safeName}_${ts}.${fileExt}` });
    };

    recorder.onerror = (e) => reject(new Error('MediaRecorder: ' + (e.error?.message || 'erro')));
    recorder.start(1000);

    let currentSlide = 0;
    let slideStart = performance.now();
    let animId = null;

    function setSlideAudio(idx, active) {
      for (const { video } of (slideVideos[idx] || [])) {
        const g = videoGains.get(video);
        if (active) {
          if (g) g.gain.value = 1.0;
          video.currentTime = 0;
          video.play().catch(() => {});
        } else {
          if (g) g.gain.value = 0;
          video.pause();
        }
      }
    }

    function slideDuration(idx) {
      const base = frames[idx]?.duration || defaultDuration;
      const vids = slideVideos[idx] || [];
      if (vids.length > 0) {
        const maxD = Math.max(...vids.map(v => v.video.duration || 0));
        if (maxD > 0 && isFinite(maxD)) return Math.max(base, maxD);
      }
      return base;
    }

    // Init: mute all, activate slide 0
    for (let i = 0; i < slideVideos.length; i++) setSlideAudio(i, false);
    setSlideAudio(0, true);

    function render() {
      const elapsed = (performance.now() - slideStart) / 1000;
      const dur = slideDuration(currentSlide);

      // Advance slide?
      if (elapsed >= dur) {
        setSlideAudio(currentSlide, false);
        currentSlide++;
        slideStart = performance.now();

        if (currentSlide >= images.length) {
          // Final frame + stop
          ctx.drawImage(images[images.length - 1], 0, 0, width, height);
          setTimeout(() => { cancelAnimationFrame(animId); recorder.stop(); }, 500);
          return;
        }

        setSlideAudio(currentSlide, true);
        const pct = 30 + Math.round(((currentSlide + 1) / images.length) * 65);
        onProgress(pct, `Gravando slide ${currentSlide + 1}/${images.length}...`);
      }

      // DRAW ORDER: background slide first, then video overlay
      // 1. Draw slide background (always)
      ctx.drawImage(images[currentSlide], 0, 0, width, height);

      // 2. Draw HeyGen video overlay (only while playing, preserve aspect ratio)
      for (const { video, x, y, width: vw, height: vh } of (slideVideos[currentSlide] || [])) {
        // Only draw if video is actually playing and has frames
        if (video.readyState >= 2 && !video.paused && !video.ended) {
          try {
            drawVideoPreserveAspect(ctx, video, x, y, vw, vh);
          } catch (e) {
            // CORS tainted canvas — skip
          }
        }
      }

      animId = requestAnimationFrame(render);
    }

    onProgress(30, `Gravando slide 1/${images.length}...`);
    render();
  });
}
