/**
 * Client-side video generation using html2canvas + Canvas + MediaRecorder.
 * Renders slides in the browser (WYSIWYG) instead of using PIL backend images.
 * Includes HeyGen video overlay + ElevenLabs/slide audio.
 * Output: MP4 (H.264 + AAC) or WebM.
 */
import html2canvas from 'html2canvas';
import DOMPurify from 'dompurify';
import { recordCanvasVideo, validateVideoBlob } from './canvasVideoRecorder';

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

export async function embeddableImageUrl(apiUrl, src) {
  const absolute = absoluteMediaUrl(apiUrl, src);
  if (!absolute || /^(data:|blob:)/i.test(absolute)) return absolute;
  try {
    // Imported PowerPoint slides are stored as background PNGs on the API
    // origin, while the editor runs on the static-app origin. Turning the
    // response into a data URL prevents html2canvas from discarding the image
    // because of canvas tainting/CORS redirects.
    // Assets use bearer authentication when needed, not cross-site cookies.
    // A Request also avoids the legacy global interceptor sending API tokens
    // to an unrelated external image whose path happens to contain /api/.
    const api = new URL(apiUrl || window.location.origin, window.location.origin);
    const image = new URL(absolute, window.location.origin);
    const headers = {};
    const publicAsset = /^\/api\/projects\/[^/]+\/assets\/[^/]+$/.test(image.pathname);
    if (image.origin === api.origin && image.pathname.startsWith('/api/') && !publicAsset) {
      const token = localStorage.getItem('scormify_auth_token');
      if (token) headers.Authorization = `Bearer ${token}`;
    }
    let response;
    for (let attempt = 0; attempt < 2; attempt++) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 20000);
      try {
        // A thumbnail may already have cached this URL as a no-cors image.
        // Never reuse that response for the export's readable CORS request.
        response = await fetch(new Request(absolute, {credentials:'omit', mode:'cors', cache:'no-store', headers, signal:controller.signal}));
        break;
      } catch (error) {
        if (attempt === 1) throw error;
        await new Promise(resolve => setTimeout(resolve, 500));
      } finally { clearTimeout(timeout); }
    }
    if (!response.ok) throw new Error(`Imagem ${response.status}`);
    const blob = await response.blob();
    return await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error || new Error('Falha ao ler imagem'));
      reader.readAsDataURL(blob);
    });
  } catch (error) {
    throw new Error('Não foi possível carregar uma imagem do slide. Verifique a conexão e o acesso à imagem. ' + (error?.message || 'Falha de rede'));
  }
}

function waitForImage(img, timeout = 15000) {
  return new Promise((resolve, reject) => {
    if (img.complete && img.naturalWidth > 0) { resolve(); return; }
    const timer = setTimeout(() => reject(new Error('Tempo esgotado ao carregar imagem')), timeout);
    img.onload = () => { clearTimeout(timer); resolve(); };
    img.onerror = () => { clearTimeout(timer); reject(new Error('Falha ao carregar imagem')); };
  });
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

function firstFlipbookPage(el) {
  const pages = [
    ...(Array.isArray(el.pdfPages) ? el.pdfPages : []),
    ...(Array.isArray(el.flipbookPages) ? el.flipbookPages : []),
  ];
  const page = pages.find(Boolean);
  if (typeof page === 'string') return page;
  if (page && typeof page === 'object') {
    return page.url || page.src || page.imageUrl || page.thumbnail || '';
  }
  return el.coverUrl || el.thumbnail || el.poster || '';
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
    const bgUrl = await embeddableImageUrl(apiUrl, slide.backgroundImage);
    const bgImg = document.createElement('img');
    bgImg.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:contain;';
    if (slide.backgroundImageOpacity != null) {
      bgImg.style.opacity = slide.backgroundImageOpacity;
    }
    slideDiv.appendChild(bgImg);
    const bgReady = waitForImage(bgImg);
    bgImg.src = bgUrl;
    await bgReady;
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
      const imgSrc = await embeddableImageUrl(apiUrl, el.src);
      const img = document.createElement('img');
      img.style.cssText = `width:100%;height:100%;object-fit:${el.objectFit || 'contain'};`;
      wrapper.appendChild(img);
      const imgReady = waitForImage(img);
      img.src = imgSrc;
      await imgReady;
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
      for (const image of htmlDiv.querySelectorAll('img[src]')) {
        const embedded = await embeddableImageUrl(apiUrl, image.getAttribute('src'));
        image.removeAttribute('srcset');
        const ready = waitForImage(image);
        image.src = embedded;
        await ready;
      }
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
    } else if (el.type === 'flipbook') {
      // html2canvas cannot paint cross-origin iframes or the browser's native
      // PDF viewer. Rasterize the first available page/cover instead so the
      // flipbook remains visible in the exported video.
      const pageSrc = firstFlipbookPage(el);
      if (pageSrc) {
        const img = document.createElement('img');
        img.style.cssText = 'width:100%;height:100%;object-fit:contain;background:#f8fafc;';
        wrapper.appendChild(img);
        const imgReady = waitForImage(img);
        img.src = await embeddableImageUrl(apiUrl, pageSrc);
        await imgReady;
      } else {
        const book = document.createElement('div');
        book.style.cssText = `
          width:100%;height:100%;display:flex;flex-direction:column;
          align-items:center;justify-content:center;gap:14px;
          box-sizing:border-box;padding:28px;text-align:center;
          color:#e2e8f0;background:linear-gradient(135deg,#172554,#0f172a);
          border:2px solid rgba(56,189,248,.45);border-radius:12px;
          font-family:sans-serif;
        `;
        const icon = document.createElement('div');
        icon.style.cssText = 'font-size:52px;line-height:1;';
        icon.textContent = '📖';
        const label = document.createElement('div');
        label.style.cssText = 'font-size:24px;font-weight:700;';
        label.textContent = el.title || 'Flipbook';
        const hint = document.createElement('div');
        hint.style.cssText = 'font-size:14px;color:#94a3b8;max-width:90%;';
        hint.textContent = el.flipbookType === 'pdf' ? 'Documento PDF' : 'Conteúdo interativo';
        book.append(icon, label, hint);
        wrapper.appendChild(book);
      }
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
  const images = [], slideVideos = [];
  let recordingCanvas;
  try {

  onProgress(8, `Renderizando ${slides.length} slides...`);

  // Render each slide to canvas using html2canvas (WYSIWYG)
  for (let i = 0; i < slides.length; i++) {
    try {
      const img = await renderSlideToImage(slides[i], apiUrl, canvasW, canvasH);
      images.push(img);
      console.log(`[VideoExport] Slide ${i + 1}: rendered OK`);
    } catch (e) {
      throw new Error(`Slide ${i + 1}: ${e.message || 'Não foi possível renderizar o conteúdo.'}`);
    }
    onProgress(8 + Math.round(((i + 1) / slides.length) * 15), `Slide ${i + 1}/${slides.length} renderizado`);
  }

  // Load HeyGen videos via proxy
  const slideW = slides[0]?.width || 1920;
  const slideH = slides[0]?.height || 1080;
  const scaleRatio = Math.min(canvasW / slideW, canvasH / slideH);
  const offsetX = (canvasW - slideW * scaleRatio) / 2;
  const offsetY = (canvasH - slideH * scaleRatio) / 2;

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
          throw new Error(`Slide ${i + 1}: não foi possível carregar o vídeo. ${e.message}`);
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
        throw new Error(`Slide ${i + 1}: não foi possível carregar a narração. ${e.message}`);
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
      throw new Error(`Não foi possível carregar a trilha sonora. ${e.message}`);
    }
  }

  onProgress(28, 'Preparando gravacao...');

  // Setup recording canvas
  const canvas = document.createElement('canvas');
  recordingCanvas = canvas;
  canvas.width = canvasW; canvas.height = canvasH;
  // Chromium may never submit frames for a detached, never-painted canvas.
  // Keep a small live preview in the document throughout the recording.
  canvas.setAttribute('aria-label', 'Prévia da gravação do vídeo');
  canvas.style.cssText = 'position:fixed;right:16px;bottom:16px;width:min(320px,40vw);height:auto;z-index:2147483000;pointer-events:none;border:2px solid #0891b2;border-radius:8px;background:#000';
  document.body.appendChild(canvas);
  const ctx = canvas.getContext('2d');
  ctx.drawImage(images[0], 0, 0, canvasW, canvasH);
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));

  // Connect HeyGen video audio
  const videoGains = new Map();
  for (const vList of slideVideos) {
    for (const { video } of vList) {
      try {
        // Keep the media element muted while starting playback. Export begins
        // after several async rendering steps, so browser user-activation has
        // expired and Chromium blocks unmuted play(). Audio is routed through
        // WebAudio below; the element itself must satisfy autoplay policy.
        video.muted = true;
        const src = audioCtx.createMediaElementSource(video);
        const gain = audioCtx.createGain();
        gain.gain.value = 0;
        src.connect(gain); gain.connect(mixDest);
        videoGains.set(video, gain);
      } catch (e) { console.warn('[VideoExport] HeyGen audio:', e.message); }
    }
  }

  const durations = slides.map((slide, idx) => Math.max(Number(slide.duration) || defaultDuration,
    ...slideVideos[idx].map(({video}) => Number.isFinite(video.duration) ? video.duration : 0),
    ...slideAudioBuffers[idx].map(({buffer, startTime}) => startTime + buffer.duration)));
  const totalDuration = durations.reduce((sum, value) => sum + value, 0);
  const hasAudio = Boolean(globalAudioBuf || videoGains.size || slideAudioBuffers.some(list => list.length));
  const sources = [];
  let current = -1, silentClock, recording = false;
  function stopMedia() {
    sources.splice(0).forEach(source => { try { source.stop(); } catch (_) { /* already ended */ } });
    try { silentClock?.stop(); } catch (_) { /* noop */ }
    silentClock = null;
    slideVideos.flat().forEach(({video}) => { video.pause(); videoGains.get(video)?.gain.setValueAtTime(0, audioCtx.currentTime); });
    current = -1;
    recording = false;
  }
  const blob = await recordCanvasVideo({
    canvas, audioTracks: hasAudio ? mixDest.stream.getAudioTracks() : [], duration: totalDuration,
    start: () => {
      current = -1; recording = true;
      if (hasAudio) {
        // A live but un-fed WebAudio destination can stall muxing. Keep the
        // clock producing silence until narration/video actually begins.
        silentClock = audioCtx.createConstantSource(); silentClock.offset.value = 0;
        silentClock.connect(mixDest); silentClock.start();
      }
      if (globalAudioBuf) {
        const source = audioCtx.createBufferSource(); source.buffer = globalAudioBuf.buffer; source.loop = globalAudioBuf.loop;
        const gain = audioCtx.createGain(); gain.gain.value = globalAudioBuf.volume;
        source.connect(gain); gain.connect(mixDest); source.start(); sources.push(source);
      }
    },
    stop: stopMedia,
    draw: elapsed => {
      let idx = 0, boundary = durations[0];
      while (idx < images.length - 1 && elapsed >= boundary) boundary += durations[++idx];
      if (recording && idx !== current) {
        if (current >= 0) slideVideos[current].forEach(({video}) => { video.pause(); videoGains.get(video)?.gain.setValueAtTime(0, audioCtx.currentTime); });
        current = idx;
        slideVideos[idx].forEach(({video}) => {
          video.currentTime = 0; video.muted = true;
          videoGains.get(video)?.gain.setValueAtTime(1, audioCtx.currentTime);
          video.play().catch(error => console.warn('[VideoExport] Reprodução de vídeo:', error.message));
        });
        slideAudioBuffers[idx].forEach(({buffer, startTime, volume}) => {
          const source = audioCtx.createBufferSource(), gain = audioCtx.createGain();
          source.buffer = buffer; gain.gain.value = volume;
          source.connect(gain); gain.connect(mixDest); source.start(audioCtx.currentTime + startTime); sources.push(source);
        });
      }
      ctx.drawImage(images[idx], 0, 0, canvasW, canvasH);
      slideVideos[idx].forEach(({video, x, y, width, height}) => {
        if (video.readyState >= 2) drawVideoFit(ctx, video, x, y, width, height);
      });
      onProgress(30 + Math.round(elapsed / totalDuration * 65), `Gravando slide ${idx + 1}/${images.length}... Mantenha esta aba ativa.`);
    },
    onRetry: (type,error) => {
      console.warn('[VideoExport] Tentativa de gravação:',type||'automático',error.message);
      onProgress(28, 'Tentando outro codificador de vídeo...');
    },
  });
  const ext = /mp4/i.test(blob.type) ? 'mp4' : 'webm';
  onProgress(97, 'Conferindo a trilha visual do vídeo...');
  await validateVideoBlob(blob);
  const safeName = (projectName || 'Curso').replace(/[^\w\s-]/g, '').replace(/\s+/g, '_');
  const ts = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15);
  onProgress(100, 'Vídeo pronto!');
  return {blob, filename: `${safeName}_${ts}.${ext}`};
  } finally {
    recordingCanvas?.remove();
    slideVideos.flat().forEach(({video}) => { video.pause(); video.removeAttribute('src'); video.load(); });
    images.forEach(image => { image.width = 0; image.height = 0; });
    mixDest.stream.getTracks().forEach(track => track.stop());
    if (audioCtx.state !== 'closed') await audioCtx.close().catch(() => {});
  }
}
