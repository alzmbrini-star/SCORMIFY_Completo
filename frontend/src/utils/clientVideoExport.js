/**
 * Client-side video generation using Canvas + MediaRecorder.
 * Creates WebM video from slide images directly in the browser.
 * No server-side FFmpeg needed — works in any environment.
 *
 * Uses requestAnimationFrame for continuous redraw so that
 * captureStream always has fresh pixel data to encode.
 */

export async function generateVideoClientSide({ apiUrl, projectId, defaultDuration, onProgress }) {
  // Step 1: Fetch slide images from backend
  onProgress(5, 'Buscando imagens dos slides...');

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

  onProgress(20, `Carregando ${frames.length} imagens...`);

  // Step 2: Load all images
  const images = await Promise.all(
    frames.map(
      (frame, i) =>
        new Promise((resolve, reject) => {
          const img = new Image();
          img.onload = () => {
            onProgress(20 + Math.round(((i + 1) / frames.length) * 10), `Imagem ${i + 1}/${frames.length} carregada`);
            resolve(img);
          };
          img.onerror = () => reject(new Error(`Falha ao carregar slide ${frame.index + 1}`));
          img.src = frame.dataUrl;
        })
    )
  );

  onProgress(30, 'Iniciando gravacao do video...');

  // Step 3: Create canvas and MediaRecorder
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');

  // Draw the first frame immediately so the stream starts with content
  ctx.drawImage(images[0], 0, 0, width, height);

  // Check MediaRecorder support
  const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
    ? 'video/webm;codecs=vp9'
    : MediaRecorder.isTypeSupported('video/webm;codecs=vp8')
    ? 'video/webm;codecs=vp8'
    : 'video/webm';

  const stream = canvas.captureStream(30); // 30fps for smooth capture

  let recorder;
  try {
    recorder = new MediaRecorder(stream, {
      mimeType,
      videoBitsPerSecond: 2500000, // 2.5Mbps for better quality
    });
  } catch (e) {
    throw new Error('Seu navegador nao suporta gravacao de video. Tente o Chrome ou Edge.');
  }

  const chunks = [];
  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

  // Step 4: Record using requestAnimationFrame for continuous redraw
  return new Promise((resolve, reject) => {
    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: mimeType });
      const safeName = projectName.replace(/[^\w\s-]/g, '').replace(/\s+/g, '_');
      const timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15);
      const filename = `${safeName}_${timestamp}.webm`;

      onProgress(100, 'Video pronto!');
      resolve({ blob, filename });
    };

    recorder.onerror = (e) => reject(new Error('Erro no MediaRecorder: ' + (e.error?.message || e.error || 'desconhecido')));

    // Collect data every second for resilience
    recorder.start(1000);

    let currentSlide = 0;
    let slideStartTime = performance.now();
    let animFrameId = null;

    function renderLoop() {
      const now = performance.now();
      const elapsedSec = (now - slideStartTime) / 1000;
      const slideDuration = frames[currentSlide]?.duration || defaultDuration;

      // Check if it's time to advance to next slide
      if (elapsedSec >= slideDuration) {
        currentSlide++;
        slideStartTime = now;

        if (currentSlide >= images.length) {
          // All slides done — give a small buffer then stop
          // Draw the last slide one more time to ensure it's captured
          ctx.drawImage(images[images.length - 1], 0, 0, width, height);
          setTimeout(() => {
            if (animFrameId) cancelAnimationFrame(animFrameId);
            recorder.stop();
          }, 500);
          return;
        }

        const progress = 30 + Math.round(((currentSlide + 1) / images.length) * 65);
        onProgress(progress, `Gravando slide ${currentSlide + 1}/${images.length}...`);
      }

      // Continuously redraw the current slide — this ensures captureStream
      // always has fresh pixel data to encode into the video
      if (currentSlide < images.length) {
        ctx.drawImage(images[currentSlide], 0, 0, width, height);
      }

      animFrameId = requestAnimationFrame(renderLoop);
    }

    onProgress(32, `Gravando slide 1/${images.length}...`);
    renderLoop();
  });
}
