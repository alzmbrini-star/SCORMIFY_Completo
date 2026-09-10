/**
 * Client-side video generation using html2canvas + Canvas + MediaRecorder.
 * Renders slides in the browser (WYSIWYG) instead of using PIL backend images.
 * Includes HeyGen video overlay + ElevenLabs/slide audio.
 * Output: MP4 (H.264 + AAC) or WebM.
 */
import html2canvas from 'html2canvas';
import DOMPurify from 'dompurify';

function pickMimeType() {
  if (typeof MediaRecorder === 'undefined') {
    throw new Error('Este navegador não oferece suporte à gravação de vídeo. Use uma versão atual do Chrome ou Edge.');
  }
  const candidates = [
    // Canvas capture is consistently implemented for WebM in Chrome/Edge.
    // Some Chromium builds claim MP4/H.264 support but produce an audio-only
    // file when the video track comes from canvas.captureStream().
    { mime: 'video/webm;codecs=vp9,opus', ext: 'webm' },
    { mime: 'video/webm;codecs=vp8,opus', ext: 'webm' },
    { mime: 'video/webm', ext: 'webm' },
    { mime: 'video/mp4;codecs=avc1,mp4a.40.2', ext: 'mp4' },
    { mime: 'video/mp4;codecs=avc1', ext: 'mp4' },
    { mime: 'video/mp4', ext: 'mp4' },
  ];
  for (const c of candidates) {
    if (MediaRecorder.isTypeSupported(c.mime)) return c;
  }
  return { mime: 'video/webm', ext: 'webm' };
}

function absoluteMediaUrl(apiUrl, src) {
  if (!src) return '';
  if (/^(blob:|data:|https?:\/\/)/i.test(src)) return src;
  const base = (apiUrl || window.location.origin || '').replace(/\/+$/, '');
  return `${base}/${String(src).replace(/^\/+/, '')}`;
}

function playableVideoUrl(apiUrl, src) {
  const absolute = absoluteMediaUrl(apiUrl, src);
  if (!absolute) return '';
  // Same-origin/project assets must be requested directly. The old code sent
  // even /api/... URLs through proxy-video, whose validator correctly rejects
  // relative URLs; uploaded, Kling and whiteboard videos therefore vanished.
  try {
    const parsed = new URL(absolute, window.location.origin);
    const apiOrigin = new URL(apiUrl || window.location.origin, window.location.origin).origin;
    if (parsed.origin === apiOrigin) return parsed.href;
  } catch (_) {
    return absolute;
  }
  return `${(apiUrl || '').replace(/\/+$/, '')}/api/proxy-video?url=${encodeURIComponent(absolute)}`;
}

function loadVideo(url) {
  return new Promise((resolve, reject) => {
    const v = document.createElement('video');
    v.crossOrigin = 'anonymous';
    v.preload = 'auto';
    v.playsInline = true;
    v.muted = true;
    const t = setTimeout(() => { v.oncanplaythrough = null; v.readyState >= 2 ? resolve(v) : reject(new Error('timeout')); }, 60000);
    v.oncanplaythrough = () => { clearTimeout(t); resolve(v); };
    v.onerror = () => { clearTimeout(t); reject(new Error('load error')); };
    v.src = url;
    v.load();
  });
}

async function loadAudioBuffer(audioCtx, url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`Audio ${r.status}`);
  return audioCtx.decodeAudioData(await r.arrayBuffer());
}

function drawVideoFit(ctx, video, tx, ty, tw, th) {
  const vw = video.videoWidth, vh = video.videoHeight;
  if (!vw || !vh) { ctx.drawImage(video, tx, ty, tw, th); return; }
  const va = vw / vh, ta = tw / th;
  let dw, dh, dx, dy;
  if (va > ta) { dw = tw; dh = tw / va; dx = tx; dy = ty + (th - dh) / 2; }
  else { dh = th; dw = th * va; dx = tx + (tw - dw) / 2; dy = ty; }
  ctx.drawImage(video, dx, dy, dw, dh);
}

/**
 * Build slide DOM and capture with html2canvas.
 * Replicates the SlideCanvas rendering for WYSIWYG fidelity.
 */
async function renderSlideToImage(slide, apiUrl, canvasW, canvasH) {
  const slideW = slide.width || 1920;
  const slideH = slide.height || 1080;

  // Create hidden container at original slide dimensions
  const container = document.createElement('div');
  const captureId = `video-export-capture-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  container.id = captureId;
  container.style.cssText = `
    position: fixed; left: -9999px; top: -9999px;
    width: ${slideW}px; height: ${slideH}px;
    overflow: hidden; z-index: -1;
  `;

  // Slide background
  const slideDiv = document.createElement('div');
  slideDiv.style.cssText = `
    width: ${slideW}px; height: ${slideH}px;
    position: relative; overflow: hidden;
  `;
  const bg = slide.background || '#FFFFFF';
  if (bg.includes('gradient')) {
    slideDiv.style.background = bg;
  } else {
    slideDiv.style.backgroundColor = bg;
  }

  // Background image
  if (slide.backgroundImage) {
    const bgUrl = absoluteMediaUrl(apiUrl, slide.backgroundImage);
    const bgImg = document.createElement('img');
    bgImg.crossOrigin = 'anonymous';
    bgImg.src = bgUrl;
    bgImg.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:contain;';
    if (slide.backgroundImageOpacity != null) {
      bgImg.style.opacity = slide.backgroundImageOpacity;
    }
    slideDiv.appendChild(bgImg);
    // Wait for it to load
    await new Promise((res) => {
      bgImg.onload = res;
      bgImg.onerror = res;
      setTimeout(res, 5000);
    });
  }

  // Elements (skip video elements — they're overlaid live)
  for (const el of (slide.elements || [])) {
    if (el.visible === false) continue;
    if (el.type === 'video') continue; // HeyGen overlaid live
    if (el.type === 'audio') continue; // No visual

    const wrapper = document.createElement('div');
    const x = el.x || 0;
    const y = el.y || 0;
    const w = el.width || 100;
    const h = el.height || 100;
    wrapper.style.cssText = `
      position: absolute;
      left: ${x}px; top: ${y}px;
      width: ${w}px; height: ${h}px;
      overflow: hidden;
      opacity: ${el.style?.opacity ?? 1};
      z-index: ${(el.zIndex || 0) + 1};
      ${el.rotation ? `transform: rotate(${el.rotation}deg);` : ''}
    `;

    if (el.type === 'text') {
      const textDiv = document.createElement('div');
      textDiv.style.cssText = `
        width: 100%; height: 100%; padding: 8px;
        white-space: pre-wrap; overflow: hidden;
        font-size: ${el.style?.fontSize || 16}px;
        font-family: ${el.style?.fontFamily || 'sans-serif'};
        font-weight: ${el.style?.fontWeight || 'normal'};
        color: ${el.style?.fontColor || '#000000'};
        text-align: ${el.style?.textAlign || 'left'};
        background-color: ${el.style?.transparentBackground ? 'transparent' : (el.style?.backgroundColor || 'rgba(255,255,255,0.8)')};
      `;
      textDiv.textContent = el.content || '';
      wrapper.appendChild(textDiv);
    } else if (el.type === 'image') {
      const imgSrc = absoluteMediaUrl(apiUrl, el.src);
      const img = document.createElement('img');
      img.crossOrigin = 'anonymous';
      img.src = imgSrc;
      img.style.cssText = `width:100%;height:100%;object-fit:${el.objectFit || 'contain'};`;
      wrapper.appendChild(img);
      await new Promise((res) => { img.onload = res; img.onerror = res; setTimeout(res, 5000); });
    } else if (el.type === 'shape') {
      const shapeDiv = document.createElement('div');
      const br = el.shapeType === 'ellipse' || el.shapeType === 'oval' ? '50%'
        : el.shapeType === 'rounded_rectangle' ? '8px' : '0';
      shapeDiv.style.cssText = `
        width:100%;height:100%;display:flex;align-items:center;justify-content:center;
        background-color:${el.style?.fill || '#7C3AED'};
        border:${el.style?.stroke ? `2px solid ${el.style.stroke}` : 'none'};
        border-radius:${br};
      `;
      if (el.content) {
        const span = document.createElement('span');
        span.style.cssText = `text-align:center;padding:8px;font-size:${el.style?.fontSize || 14}px;color:${el.style?.fontColor || '#FFFFFF'};`;
        span.textContent = el.content;
        shapeDiv.appendChild(span);
      }
      wrapper.appendChild(shapeDiv);
    } else if (el.type === 'html') {
      // Render HTML content directly (no iframe — html2canvas can't capture iframes)
      const htmlDiv = document.createElement('div');
      htmlDiv.style.cssText = `width:100%;height:100%;overflow:hidden;color:#f1f5f9;font-size:14px;padding:12px;`;
      // Resolve URLs in HTML content
      let content = el.htmlContent || '<p>HTML</p>';
      content = content.replace(/(src=["'])\/api\//g, `$1${apiUrl}/api/`);
      // Sanitize before injecting into the DOM — content originates from
      // user-editable slides and LLM output that could contain
      // <script> or onerror= payloads. Even though this div is short-lived
      // (only used for html2canvas to rasterize), the script COULD fire
      // before capture and exfiltrate cookies / localStorage. DOMPurify
      // strips all event handlers and unsafe tags but keeps formatting.
      htmlDiv.innerHTML = DOMPurify.sanitize(content);
      wrapper.appendChild(htmlDiv);
    } else if (el.type === 'button') {
      const btn = document.createElement('div');
      btn.style.cssText = `
        width:100%;height:100%;display:flex;align-items:center;justify-content:center;
      `;
      const inner = document.createElement('div');
      inner.style.cssText = `
        padding:12px 24px;border-radius:${el.style?.borderRadius || 8}px;
        font-weight:600;font-size:${el.style?.fontSize || 16}px;
        ${el.buttonStyle === 'outline'
          ? `border:2px solid #7C3AED;color:#7C3AED;background:transparent;`
          : `background:linear-gradient(to right,#7C3AED,#06B6D4);color:white;`
        }
      `;
      inner.textContent = el.buttonText || 'Clique aqui';
      btn.appendChild(inner);
      wrapper.appendChild(btn);
    }

    slideDiv.appendChild(wrapper);
  }

  container.appendChild(slideDiv);
  document.body.appendChild(container);

  // Capture with html2canvas
  try {
    const captured = await html2canvas(slideDiv, {
      width: slideW,
      height: slideH,
      scale: 1,
      useCORS: true,
      allowTaint: false,
      logging: false,
      backgroundColor: null,
      windowWidth: slideW,
      windowHeight: slideH,
      // html2canvas clones the document before painting. Reset the off-screen
      // host in that clone, otherwise Chrome can cull the entire slide and
      // return a transparent frame even though audio recording succeeds.
      onclone: (clonedDocument) => {
        const clonedContainer = clonedDocument.getElementById(captureId);
        if (clonedContainer) {
          clonedContainer.style.left = '0';
          clonedContainer.style.top = '0';
          clonedContainer.style.zIndex = '0';
        }
      },
    });

    // Scale to target canvas size
    const resultCanvas = document.createElement('canvas');
    resultCanvas.width = canvasW;
    resultCanvas.height = canvasH;
    const rCtx = resultCanvas.getContext('2d');
    rCtx.drawImage(captured, 0, 0, canvasW, canvasH);

    return resultCanvas;
  } finally {
    document.body.removeChild(container);
  }
}

export async function generateVideoClientSide({ apiUrl, projectId, defaultDuration = 5, onProgress = () => {} }) {
  onProgress(5, 'Buscando dados dos slides...');

  // Fetch lightweight slide data (no PIL images)
  const response = await fetch(`${apiUrl}/api/course/${projectId}/slides-data?default_duration=${defaultDuration}`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Erro' }));
    throw new Error(err.detail || `HTTP ${response.status}`);
  }

  const data = await response.json();
  const { slides, projectName, globalAudio: globalAudioData } = data;
  if (!slides || slides.length === 0) throw new Error('Nenhum slide encontrado.');

  const canvasW = 1280, canvasH = 720;

  // Audio context (needed early for buffer decoding)
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === 'suspended') await audioCtx.resume();
  const mixDest = audioCtx.createMediaStreamDestination();

  onProgress(8, `Renderizando ${slides.length} slides...`);

  // Render each slide to canvas using html2canvas (WYSIWYG)
  const images = [];
  for (let i = 0; i < slides.length; i++) {
    try {
      const img = await renderSlideToImage(slides[i], apiUrl, canvasW, canvasH);
      images.push(img);
      console.log(`[VideoExport] Slide ${i + 1}: rendered OK`);
    } catch (e) {
      console.error(`[VideoExport] Slide ${i + 1} render failed:`, e);
      const fb = document.createElement('canvas');
      fb.width = canvasW; fb.height = canvasH;
      const cx = fb.getContext('2d');
      cx.fillStyle = '#1a1a2e'; cx.fillRect(0, 0, canvasW, canvasH);
      cx.fillStyle = '#fff'; cx.font = '32px sans-serif'; cx.textAlign = 'center';
      cx.fillText(`Slide ${i + 1}`, canvasW / 2, canvasH / 2);
      images.push(fb);
    }
    onProgress(8 + Math.round(((i + 1) / slides.length) * 15), `Slide ${i + 1}/${slides.length} renderizado`);
  }

  // Load HeyGen videos via proxy
  const slideW = slides[0]?.width || 1920;
  const slideH = slides[0]?.height || 1080;
  const scaleRatio = Math.min(canvasW / slideW, canvasH / slideH);
  const offsetX = (canvasW - slideW * scaleRatio) / 2;
  const offsetY = (canvasH - slideH * scaleRatio) / 2;

  const slideVideos = [];
  for (let i = 0; i < slides.length; i++) {
    const vels = slides[i].videoElements || [];
    if (vels.length > 0) {
      onProgress(24 + Math.round((i / slides.length) * 4), `Video slide ${i + 1}...`);
      const loaded = [];
      for (const vel of vels) {
        try {
          const videoUrl = playableVideoUrl(apiUrl, vel.src);
          if (!videoUrl) throw new Error('URL de vídeo ausente');
          const v = await loadVideo(videoUrl);
          loaded.push({
            video: v,
            x: vel.x * scaleRatio + offsetX,
            y: vel.y * scaleRatio + offsetY,
            width: vel.width * scaleRatio,
            height: vel.height * scaleRatio,
          });
          console.log(`[VideoExport] Slide ${i + 1}: HeyGen ${v.duration.toFixed(1)}s`);
        } catch (e) {
          console.warn(`[VideoExport] Slide ${i + 1}: HeyGen failed - ${e.message}`);
        }
      }
      slideVideos[i] = loaded;
    } else {
      slideVideos[i] = [];
    }
  }

  // Load slide audio
  const slideAudioBuffers = [];
  for (let i = 0; i < slides.length; i++) {
    const auds = slides[i].audioElements || [];
    const loaded = [];
    for (const aud of auds) {
      try {
        const url = absoluteMediaUrl(apiUrl, aud.src);
        const buf = await loadAudioBuffer(audioCtx, url);
        loaded.push({ buffer: buf, startTime: aud.startTime || 0, volume: aud.volume || 1.0 });
        console.log(`[VideoExport] Slide ${i + 1}: audio ${buf.duration.toFixed(1)}s`);
      } catch (e) {
        console.warn(`[VideoExport] Slide ${i + 1}: audio failed - ${e.message}`);
      }
    }
    slideAudioBuffers[i] = loaded;
  }

  // Load global audio
  let globalAudioBuf = null;
  if (globalAudioData?.src) {
    try {
      const url = absoluteMediaUrl(apiUrl, globalAudioData.src);
      globalAudioBuf = { buffer: await loadAudioBuffer(audioCtx, url), volume: globalAudioData.volume || 0.5, loop: !!globalAudioData.loop };
      console.log(`[VideoExport] Global audio: ${globalAudioBuf.buffer.duration.toFixed(1)}s`);
    } catch (e) {
      console.warn('[VideoExport] Global audio failed:', e.message);
    }
  }

  onProgress(28, 'Preparando gravacao...');

  // Setup recording canvas
  const canvas = document.createElement('canvas');
  canvas.width = canvasW; canvas.height = canvasH;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(images[0], 0, 0, canvasW, canvasH);

  const { mime: mimeType, ext: preferredExt } = pickMimeType();
  console.log(`[VideoExport] Format: ${mimeType} (.${preferredExt})`);

  // Connect HeyGen video audio
  const videoGains = new Map();
  for (const vList of slideVideos) {
    for (const { video } of vList) {
      try {
        video.muted = false;
        const src = audioCtx.createMediaElementSource(video);
        const gain = audioCtx.createGain();
        gain.gain.value = 0;
        src.connect(gain); gain.connect(mixDest);
        videoGains.set(video, gain);
      } catch (e) { console.warn('[VideoExport] HeyGen audio:', e.message); }
    }
  }

  // Build combined stream
  const canvasStream = canvas.captureStream(30);
  const canvasVideoTrack = canvasStream.getVideoTracks()[0];
  if (!canvasVideoTrack || canvasVideoTrack.readyState !== 'live') {
    try { audioCtx.close(); } catch (_) { /* noop */ }
    throw new Error('O navegador não conseguiu criar a trilha visual dos slides.');
  }
  const combined = new MediaStream();
  for (const t of canvasStream.getVideoTracks()) combined.addTrack(t);
  for (const t of mixDest.stream.getAudioTracks()) combined.addTrack(t);

  let recorder;
  try {
    recorder = new MediaRecorder(combined, {
      mimeType,
      videoBitsPerSecond: 5000000,
      audioBitsPerSecond: 192000,
    });
  } catch (error) {
    try {
      // Some Chromium builds report a supported codec combination but reject
      // it when audio and canvas tracks are combined. Let the browser choose.
      recorder = new MediaRecorder(combined, { videoBitsPerSecond: 5000000 });
    } catch (_) {
      throw new Error(`Não foi possível iniciar o codificador de vídeo: ${error.message}`);
    }
  }
  const chunks = [];
  recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };

  return new Promise((resolve, reject) => {
    const activeSources = [];

    recorder.onstop = () => {
      for (const s of activeSources) { try { s.stop(); } catch (e) { /* */ } }
      try { audioCtx.close(); } catch (e) { /* */ }
      if (!chunks.length || !chunks.some((chunk) => chunk.size > 0)) {
        reject(new Error('O navegador encerrou a gravação sem produzir dados.'));
        return;
      }
      const actualType = recorder.mimeType || mimeType;
      const actualExt = /mp4/i.test(actualType) ? 'mp4' : 'webm';
      const blob = new Blob(chunks, { type: actualType });
      const safeName = projectName.replace(/[^\w\s-]/g, '').replace(/\s+/g, '_');
      const ts = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15);
      onProgress(100, 'Video pronto!');
      resolve({ blob, filename: `${safeName}_${ts}.${actualExt}` });
    };
    recorder.onerror = (e) => reject(new Error('MediaRecorder: ' + (e.error?.message || 'erro')));
    recorder.start(1000);

    // Start global audio
    if (globalAudioBuf) {
      const src = audioCtx.createBufferSource();
      src.buffer = globalAudioBuf.buffer; src.loop = globalAudioBuf.loop;
      const g = audioCtx.createGain(); g.gain.value = globalAudioBuf.volume;
      src.connect(g); g.connect(mixDest); src.start(0);
      activeSources.push(src);
    }

    let cur = 0, slideStart = performance.now(), animId = null;

    function startSlide(idx) {
      for (const { video } of (slideVideos[idx] || [])) {
        const g = videoGains.get(video);
        if (g) g.gain.value = 1.0;
        video.currentTime = 0;
        video.play().catch(() => {});
      }
      for (const { buffer, startTime, volume } of (slideAudioBuffers[idx] || [])) {
        const src = audioCtx.createBufferSource(); src.buffer = buffer;
        const g = audioCtx.createGain(); g.gain.value = volume;
        src.connect(g); g.connect(mixDest);
        src.start(audioCtx.currentTime + startTime);
        activeSources.push(src);
      }
    }

    function stopSlide(idx) {
      for (const { video } of (slideVideos[idx] || [])) {
        const g = videoGains.get(video);
        if (g) g.gain.value = 0;
        video.pause();
      }
    }

    function durOf(idx) {
      const base = slides[idx]?.duration || defaultDuration;
      let max = base;
      for (const { video } of (slideVideos[idx] || [])) {
        if (video.duration > 0 && isFinite(video.duration)) max = Math.max(max, video.duration);
      }
      for (const { buffer, startTime } of (slideAudioBuffers[idx] || [])) {
        max = Math.max(max, startTime + buffer.duration);
      }
      return max;
    }

    startSlide(0);

    function render() {
      const elapsed = (performance.now() - slideStart) / 1000;
      if (elapsed >= durOf(cur)) {
        stopSlide(cur);
        cur++;
        slideStart = performance.now();
        if (cur >= images.length) {
          ctx.drawImage(images[images.length - 1], 0, 0, canvasW, canvasH);
          setTimeout(() => { cancelAnimationFrame(animId); recorder.stop(); }, 500);
          return;
        }
        startSlide(cur);
        onProgress(30 + Math.round(((cur + 1) / images.length) * 65), `Gravando slide ${cur + 1}/${images.length}...`);
      }

      // Draw slide background
      ctx.drawImage(images[cur], 0, 0, canvasW, canvasH);

      // Overlay HeyGen video
      for (const { video, x, y, width: vw, height: vh } of (slideVideos[cur] || [])) {
        if (video.readyState >= 2 && !video.paused && !video.ended) {
          try { drawVideoFit(ctx, video, x, y, vw, vh); } catch (e) { /* */ }
        }
      }

      animId = requestAnimationFrame(render);
    }

    onProgress(30, `Gravando slide 1/${images.length}...`);
    render();
  });
}
