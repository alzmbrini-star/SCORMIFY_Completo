/**
 * Client-side video generation using Canvas + MediaRecorder.
 * Creates WebM video from slide images directly in the browser.
 * No server-side FFmpeg needed — works in any environment.
 */

export async function generateVideoClientSide({ apiUrl, projectId, defaultDuration, onProgress }) {
  // Step 1: Fetch slide images from backend
  onProgress(5, 'Gerando imagens dos slides...');

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

  onProgress(30, `Criando video (${frames.length} slides)...`);

  // Step 2: Load all images
  const images = await Promise.all(
    frames.map(
      (frame) =>
        new Promise((resolve, reject) => {
          const img = new Image();
          img.onload = () => resolve(img);
          img.onerror = () => reject(new Error(`Failed to load slide ${frame.index + 1}`));
          img.src = frame.dataUrl;
        })
    )
  );

  // Step 3: Create canvas and MediaRecorder
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');

  // Check MediaRecorder support
  const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
    ? 'video/webm;codecs=vp9'
    : MediaRecorder.isTypeSupported('video/webm;codecs=vp8')
    ? 'video/webm;codecs=vp8'
    : 'video/webm';

  const stream = canvas.captureStream(6); // 6fps — matches server approach
  const recorder = new MediaRecorder(stream, {
    mimeType,
    videoBitsPerSecond: 2000000, // 2Mbps
  });

  const chunks = [];
  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

  // Step 4: Record each slide
  return new Promise((resolve, reject) => {
    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: mimeType });
      const safeName = projectName.replace(/[^\w\s-]/g, '').replace(/\s+/g, '_');
      const timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15);
      const filename = `${safeName}_${timestamp}.webm`;

      onProgress(100, 'Video pronto!');
      resolve({ blob, filename });
    };

    recorder.onerror = (e) => reject(new Error('MediaRecorder error: ' + e.error));

    recorder.start();

    let currentSlide = 0;

    function drawNextSlide() {
      if (currentSlide >= images.length) {
        // All slides drawn — stop recording after a small delay
        setTimeout(() => recorder.stop(), 200);
        return;
      }

      const img = images[currentSlide];
      const dur = frames[currentSlide].duration;
      const progress = 30 + Math.round(((currentSlide + 1) / images.length) * 65);

      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, width, height);
      ctx.drawImage(img, 0, 0, width, height);

      onProgress(progress, `Gravando slide ${currentSlide + 1}/${images.length}...`);
      currentSlide++;

      // Wait for the slide duration then draw next
      setTimeout(drawNextSlide, dur * 1000);
    }

    drawNextSlide();
  });
}
