/**
 * Client-side video generation using Canvas + MediaRecorder.
 * Creates MP4 (H.264) or WebM video from slide images + HeyGen video overlays.
 * Includes audio from HeyGen videos via AudioContext.
 * No server-side FFmpeg needed — works in any environment.
 *
 * MP4 is preferred (plays on Windows/Mac/mobile natively).
 * WebM fallback for older browsers.
 */

/**
 * Pick the best MIME type for recording. Prefer MP4 (H.264) for universal playback.
 */
function pickMimeType() {
  const candidates = [
    { mime: 'video/mp4;codecs=avc1,opus', ext: 'mp4' },
    { mime: 'video/mp4;codecs=avc1', ext: 'mp4' },
    { mime: 'video/mp4', ext: 'mp4' },
    { mime: 'video/webm;codecs=vp9,opus', ext: 'webm' },
    { mime: 'video/webm;codecs=vp9', ext: 'webm' },
    { mime: 'video/webm;codecs=vp8,opus', ext: 'webm' },
    { mime: 'video/webm;codecs=vp8', ext: 'webm' },
    { mime: 'video/webm', ext: 'webm' },
  ];

  for (const c of candidates) {
    if (MediaRecorder.isTypeSupported(c.mime)) {
      return c;
    }
  }
  // Last resort
  return { mime: 'video/webm', ext: 'webm' };
}

/**
 * Load a video element from a proxied URL. Returns the <video> element ready to play.
 */
function loadVideo(proxyUrl) {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    video.crossOrigin = 'anonymous';
    video.preload = 'auto';
    video.muted = false;
    video.playsInline = true;

    const timeout = setTimeout(() => {
      video.oncanplaythrough = null;
      if (video.readyState >= 2) {
        resolve(video);
      } else {
        reject(new Error('Video load timeout'));
      }
    }, 60000);

    video.oncanplaythrough = () => {
      clearTimeout(timeout);
      resolve(video);
    };
    video.onerror = () => {
      clearTimeout(timeout);
      reject(new Error('Failed to load video'));
    };

    video.src = proxyUrl;
    video.load();
  });
}

export async function generateVideoClientSide({ apiUrl, projectId, defaultDuration, onProgress }) {
  // Step 1: Fetch slide images + video metadata from backend
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

  // Step 2: Load all slide background images
  const images = await Promise.all(
    frames.map(
      (frame, i) =>
        new Promise((resolve, reject) => {
          const img = new Image();
          img.onload = () => resolve(img);
          img.onerror = () => reject(new Error(`Falha ao carregar slide ${frame.index + 1}`));
          img.src = frame.dataUrl;
        })
    )
  );

  // Step 3: Load HeyGen/overlay videos (proxied through our backend for CORS)
  const slideVideos = [];
  for (let i = 0; i < frames.length; i++) {
    const videoEls = frames[i].videoElements || [];
    if (videoEls.length > 0) {
      onProgress(15 + Math.round((i / frames.length) * 10), `Carregando video do slide ${i + 1}...`);
      const loadedVideos = [];
      for (const vel of videoEls) {
        try {
          const proxyUrl = `${apiUrl}/api/proxy-video?url=${encodeURIComponent(vel.src)}`;
          const video = await loadVideo(proxyUrl);
          loadedVideos.push({
            video,
            x: vel.x,
            y: vel.y,
            width: vel.width,
            height: vel.height,
          });
        } catch (e) {
          console.warn(`Failed to load video for slide ${i + 1}:`, e.message);
        }
      }
      slideVideos[i] = loadedVideos;
    } else {
      slideVideos[i] = [];
    }
  }

  onProgress(28, 'Preparando gravacao...');

  // Step 4: Create canvas and setup recording
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');

  // Draw first frame immediately
  ctx.drawImage(images[0], 0, 0, width, height);

  // Pick best available format (MP4 preferred for universal playback)
  const { mime: mimeType, ext: fileExt } = pickMimeType();
  console.log(`[VideoExport] Using format: ${mimeType} (.${fileExt})`);

  // Setup audio context for mixing video audio into the recording
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const destination = audioCtx.createMediaStreamDestination();

  // Get canvas video stream at 30fps
  const canvasStream = canvas.captureStream(30);

  // Combine canvas video track + audio destination track
  const combinedStream = new MediaStream();
  for (const track of canvasStream.getVideoTracks()) {
    combinedStream.addTrack(track);
  }
  for (const track of destination.stream.getAudioTracks()) {
    combinedStream.addTrack(track);
  }

  let recorder;
  try {
    recorder = new MediaRecorder(combinedStream, {
      mimeType,
      videoBitsPerSecond: 2500000,
    });
  } catch (e) {
    throw new Error('Seu navegador nao suporta gravacao de video. Tente o Chrome ou Edge.');
  }

  const chunks = [];
  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

  // Step 5: Record slides with video overlay + audio
  return new Promise((resolve, reject) => {
    recorder.onstop = () => {
      try { audioCtx.close(); } catch (e) { /* ignore */ }

      const blob = new Blob(chunks, { type: mimeType });
      const safeName = projectName.replace(/[^\w\s-]/g, '').replace(/\s+/g, '_');
      const timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15);
      const filename = `${safeName}_${timestamp}.${fileExt}`;

      onProgress(100, 'Video pronto!');
      resolve({ blob, filename });
    };

    recorder.onerror = (e) => reject(new Error('Erro no MediaRecorder: ' + (e.error?.message || e.error || 'desconhecido')));

    recorder.start(1000);

    let currentSlide = 0;
    let slideStartTime = performance.now();
    let currentAudioSources = [];
    let animFrameId = null;

    function startSlideVideos(slideIdx) {
      for (const src of currentAudioSources) {
        try { src.disconnect(); } catch (e) { /* ignore */ }
      }
      currentAudioSources = [];

      const videos = slideVideos[slideIdx] || [];
      for (const { video } of videos) {
        try {
          const source = audioCtx.createMediaElementSource(video);
          source.connect(destination);
          currentAudioSources.push(source);
        } catch (e) {
          console.warn('Audio source already connected:', e.message);
        }

        video.currentTime = 0;
        video.play().catch(() => {});
      }
    }

    function stopSlideVideos(slideIdx) {
      const videos = slideVideos[slideIdx] || [];
      for (const { video } of videos) {
        video.pause();
      }
    }

    function getEffectiveDuration(slideIdx) {
      const baseDuration = frames[slideIdx]?.duration || defaultDuration;
      const videos = slideVideos[slideIdx] || [];
      if (videos.length > 0) {
        const maxVideoDur = Math.max(...videos.map(v => v.video.duration || 0));
        if (maxVideoDur > 0 && isFinite(maxVideoDur)) {
          return Math.max(baseDuration, maxVideoDur);
        }
      }
      return baseDuration;
    }

    startSlideVideos(0);

    function renderLoop() {
      const now = performance.now();
      const elapsedSec = (now - slideStartTime) / 1000;
      const slideDuration = getEffectiveDuration(currentSlide);

      if (elapsedSec >= slideDuration) {
        stopSlideVideos(currentSlide);
        currentSlide++;
        slideStartTime = now;

        if (currentSlide >= images.length) {
          ctx.drawImage(images[images.length - 1], 0, 0, width, height);
          setTimeout(() => {
            if (animFrameId) cancelAnimationFrame(animFrameId);
            recorder.stop();
          }, 500);
          return;
        }

        startSlideVideos(currentSlide);

        const progress = 30 + Math.round(((currentSlide + 1) / images.length) * 65);
        onProgress(progress, `Gravando slide ${currentSlide + 1}/${images.length}...`);
      }

      // Draw background image
      if (currentSlide < images.length) {
        ctx.drawImage(images[currentSlide], 0, 0, width, height);

        // Overlay video frames on top
        const videos = slideVideos[currentSlide] || [];
        for (const { video, x, y, width: vw, height: vh } of videos) {
          if (video.readyState >= 2 && !video.paused) {
            try {
              ctx.drawImage(video, x, y, vw, vh);
            } catch (e) {
              // Canvas tainted or video not ready
            }
          }
        }
      }

      animFrameId = requestAnimationFrame(renderLoop);
    }

    onProgress(30, `Gravando slide 1/${images.length}...`);
    renderLoop();
  });
}
