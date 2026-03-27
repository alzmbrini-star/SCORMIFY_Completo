/**
 * Client-side video generation using Canvas + MediaRecorder.
 * Creates MP4 (H.264) or WebM video from slide images + HeyGen video overlays.
 * Includes audio from HeyGen videos via captureStream().
 * No server-side FFmpeg needed.
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
    // Start muted to allow autoplay, we capture audio via captureStream
    video.muted = true;

    const timeout = setTimeout(() => {
      video.oncanplaythrough = null;
      if (video.readyState >= 2) resolve(video);
      else reject(new Error('Video load timeout'));
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

function loadImage(dataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      if (img.naturalWidth === 0 || img.naturalHeight === 0) {
        reject(new Error('Image loaded with zero dimensions'));
        return;
      }
      resolve(img);
    };
    img.onerror = () => reject(new Error('Image failed to load'));
    img.src = dataUrl;
  });
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

  // Load all slide background images
  const images = [];
  for (let i = 0; i < frames.length; i++) {
    try {
      const img = await loadImage(frames[i].dataUrl);
      images.push(img);
      onProgress(10 + Math.round(((i + 1) / frames.length) * 10), `Imagem ${i + 1}/${frames.length}`);
    } catch (e) {
      console.error(`Slide ${i + 1} image load failed:`, e);
      // Create a fallback colored image
      const fallback = document.createElement('canvas');
      fallback.width = width;
      fallback.height = height;
      const fCtx = fallback.getContext('2d');
      fCtx.fillStyle = '#1a1a2e';
      fCtx.fillRect(0, 0, width, height);
      fCtx.fillStyle = '#ffffff';
      fCtx.font = '32px sans-serif';
      fCtx.textAlign = 'center';
      fCtx.fillText(`Slide ${i + 1}`, width / 2, height / 2);
      images.push(fallback);
    }
  }

  // Load HeyGen/overlay videos
  const slideVideos = [];
  for (let i = 0; i < frames.length; i++) {
    const videoEls = frames[i].videoElements || [];
    if (videoEls.length > 0) {
      onProgress(22 + Math.round((i / frames.length) * 5), `Carregando video do slide ${i + 1}...`);
      const loadedVideos = [];
      for (const vel of videoEls) {
        try {
          const proxyUrl = `${apiUrl}/api/proxy-video?url=${encodeURIComponent(vel.src)}`;
          const video = await loadVideo(proxyUrl);
          loadedVideos.push({ video, x: vel.x, y: vel.y, width: vel.width, height: vel.height });
        } catch (e) {
          console.warn(`Video load failed for slide ${i + 1}:`, e.message);
        }
      }
      slideVideos[i] = loadedVideos;
    } else {
      slideVideos[i] = [];
    }
  }

  onProgress(28, 'Preparando gravacao...');

  // Create canvas
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');

  // Draw first frame
  ctx.drawImage(images[0], 0, 0, width, height);

  const { mime: mimeType, ext: fileExt } = pickMimeType();
  console.log(`[VideoExport] Format: ${mimeType} (.${fileExt})`);

  // Build combined stream: canvas video + all video audios
  const canvasStream = canvas.captureStream(30);
  const combinedStream = new MediaStream();

  // Add canvas video track
  for (const track of canvasStream.getVideoTracks()) {
    combinedStream.addTrack(track);
  }

  // Use AudioContext to mix audio from multiple videos
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  // Resume AudioContext (browsers suspend it until user gesture)
  if (audioCtx.state === 'suspended') {
    await audioCtx.resume();
  }
  const mixDestination = audioCtx.createMediaStreamDestination();

  // Add the mixed audio track to our recording stream
  for (const track of mixDestination.stream.getAudioTracks()) {
    combinedStream.addTrack(track);
  }

  // Pre-connect all video audio sources to the mixer
  // createMediaElementSource can only be called once per video, so do it upfront
  const videoAudioSources = new Map();
  const videoGainNodes = new Map();

  for (let i = 0; i < slideVideos.length; i++) {
    for (const { video } of slideVideos[i]) {
      try {
        // Unmute the video (audio will flow through Web Audio API, not speakers)
        video.muted = false;
        const source = audioCtx.createMediaElementSource(video);
        const gain = audioCtx.createGain();
        gain.gain.value = 0; // Start silent, will enable per-slide
        source.connect(gain);
        gain.connect(mixDestination);
        videoAudioSources.set(video, source);
        videoGainNodes.set(video, gain);
      } catch (e) {
        console.warn('Audio source setup failed:', e.message);
      }
    }
  }

  let recorder;
  try {
    recorder = new MediaRecorder(combinedStream, { mimeType, videoBitsPerSecond: 2500000 });
  } catch (e) {
    throw new Error('Seu navegador nao suporta gravacao de video. Tente o Chrome ou Edge.');
  }

  const chunks = [];
  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

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

    recorder.onerror = (e) => reject(new Error('MediaRecorder error: ' + (e.error?.message || 'unknown')));
    recorder.start(1000);

    let currentSlide = 0;
    let slideStartTime = performance.now();
    let animFrameId = null;

    function activateSlideAudio(slideIdx) {
      // Mute all video audio
      for (const [, gain] of videoGainNodes) {
        gain.gain.value = 0;
      }
      // Unmute and play videos for this slide
      const videos = slideVideos[slideIdx] || [];
      for (const { video } of videos) {
        const gain = videoGainNodes.get(video);
        if (gain) gain.gain.value = 1.0;
        video.currentTime = 0;
        video.play().catch(err => console.warn('Video play failed:', err));
      }
    }

    function stopSlideVideos(slideIdx) {
      const videos = slideVideos[slideIdx] || [];
      for (const { video } of videos) {
        video.pause();
        const gain = videoGainNodes.get(video);
        if (gain) gain.gain.value = 0;
      }
    }

    function getEffectiveDuration(slideIdx) {
      const baseDuration = frames[slideIdx]?.duration || defaultDuration;
      const videos = slideVideos[slideIdx] || [];
      if (videos.length > 0) {
        const maxDur = Math.max(...videos.map(v => v.video.duration || 0));
        if (maxDur > 0 && isFinite(maxDur)) return Math.max(baseDuration, maxDur);
      }
      return baseDuration;
    }

    // Start first slide
    activateSlideAudio(0);

    function renderLoop() {
      const now = performance.now();
      const elapsedSec = (now - slideStartTime) / 1000;
      const slideDuration = getEffectiveDuration(currentSlide);

      if (elapsedSec >= slideDuration) {
        stopSlideVideos(currentSlide);
        currentSlide++;
        slideStartTime = now;

        if (currentSlide >= images.length) {
          // Draw last frame once more then stop
          ctx.drawImage(images[images.length - 1], 0, 0, width, height);
          setTimeout(() => {
            if (animFrameId) cancelAnimationFrame(animFrameId);
            recorder.stop();
          }, 500);
          return;
        }

        activateSlideAudio(currentSlide);
        const progress = 30 + Math.round(((currentSlide + 1) / images.length) * 65);
        onProgress(progress, `Gravando slide ${currentSlide + 1}/${images.length}...`);
      }

      // Draw: background image first, then video overlay
      if (currentSlide < images.length) {
        // Clear canvas to prevent ghosting
        ctx.fillStyle = '#000000';
        ctx.fillRect(0, 0, width, height);

        // Draw slide background
        ctx.drawImage(images[currentSlide], 0, 0, width, height);

        // Overlay HeyGen video frames
        const videos = slideVideos[currentSlide] || [];
        for (const { video, x, y, width: vw, height: vh } of videos) {
          if (video.readyState >= 2 && !video.paused && !video.ended) {
            try {
              ctx.drawImage(video, x, y, vw, vh);
            } catch (e) {
              // Video CORS or tainted canvas — skip frame
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
