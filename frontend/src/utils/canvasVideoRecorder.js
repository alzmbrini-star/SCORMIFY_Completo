/** Canvas recorder lifecycle. No course writes, uploads, or AI calls. */
export function videoMimeCandidates(Recorder = window.MediaRecorder) {
  if (!Recorder) throw new Error('Este navegador não oferece gravação de vídeo. Use Chrome ou Edge atualizado.');
  return ['video/webm;codecs=vp8,opus', 'video/webm', 'video/webm;codecs=vp9,opus',
    'video/mp4;codecs=avc1,mp4a.40.2', 'video/mp4', ''].filter(type => !type || Recorder.isTypeSupported(type));
}

export function recordCanvasAttempt({canvas, audioTracks = [], mimeType, duration, draw, start, stop,
  firstDataTimeout = 10000, Recorder = window.MediaRecorder}) {
  return new Promise((resolve, reject) => {
    let recorder, stream, videoStream, timer, watchdog, flush, ending = false, settled = false;
    const chunks = [];
    function cleanup() {
      clearInterval(timer); clearInterval(flush); clearTimeout(watchdog);
      try { stop?.(); } catch (_) { /* preserve recorder error */ }
      for (const track of videoStream?.getTracks() || []) track.stop();
    }
    function fail(error) {
      if (settled) return;
      settled = true;
      if (recorder?.state !== 'inactive') { try { recorder?.stop(); } catch (_) { /* noop */ } }
      cleanup(); reject(error);
    }
    try {
      draw(0);
      // Manual frame requests make static slides capture reliably as well.
      videoStream = canvas.captureStream(30);
      const track = videoStream.getVideoTracks()[0];
      if (!track || track.readyState !== 'live') throw new Error('Não foi possível criar a trilha visual dos slides.');
      stream = new MediaStream([...videoStream.getVideoTracks(), ...audioTracks]);
      recorder = new Recorder(stream, { ...(mimeType ? {mimeType} : {}), videoBitsPerSecond: 5000000,
        ...(audioTracks.length ? {audioBitsPerSecond: 192000} : {}) });
      recorder.ondataavailable = e => {
        if (e.data?.size) { chunks.push(e.data); clearTimeout(watchdog); }
      };
      recorder.onerror = e => fail(new Error('Falha no codificador: ' + (e.error?.message || 'gravação interrompida')));
      recorder.onstop = () => {
        if (settled) return;
        settled = true; cleanup();
        if (!ending || !chunks.length) { reject(new Error('O navegador encerrou a gravação antes de gerar o vídeo completo.')); return; }
        const type = recorder.mimeType || mimeType || 'video/webm';
        resolve(new Blob(chunks, {type}));
      };
      // Timing begins only after the encoder accepts the stream.
      recorder.onstart = () => {
        try {
          start?.();
          const begun = performance.now();
          const tick = () => {
            try {
              const elapsed = Math.min(duration, (performance.now() - begun) / 1000);
              draw(elapsed); track.requestFrame?.();
              if (elapsed >= duration && !ending) {
                ending = true; clearInterval(timer); clearInterval(flush);
                recorder.requestData(); recorder.stop();
              }
            } catch (error) { fail(error); }
          };
          tick();
          // Unlike requestAnimationFrame, timers do not depend on repainting
          // the off-screen canvas. Keep the Editor tab active during export.
          if (!ending) timer = setInterval(tick, 1000 / 30);
        } catch (error) { fail(error); }
      };
      watchdog = setTimeout(() => fail(new Error('O codificador não produziu dados. Mantenha a aba do Editor ativa e tente novamente.')), firstDataTimeout);
      flush = setInterval(() => { if (recorder.state === 'recording') { try { recorder.requestData(); } catch (e) { fail(e); } } }, 1000);
      recorder.start(1000);
    } catch (error) { fail(error); }
  });
}

export async function recordCanvasVideo(options) {
  let failure;
  for (const mimeType of videoMimeCandidates(options.Recorder)) {
    try { return await recordCanvasAttempt({...options, mimeType}); }
    catch (error) { failure = error; options.onRetry?.(mimeType, error); }
  }
  throw new Error('Não foi possível gravar o vídeo neste navegador. ' + (failure?.message || 'Atualize o Chrome ou Edge.'));
}

export function validateVideoBlob(blob, timeout = 20000) {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video'), url = URL.createObjectURL(blob);
    let settled = false;
    const finish = error => {
      if (settled) return;
      settled = true; clearTimeout(timer); video.onloadeddata = null; video.onerror = null;
      video.pause(); video.removeAttribute('src'); video.load(); URL.revokeObjectURL(url);
      error ? reject(error) : resolve();
    };
    const timer = setTimeout(() => finish(new Error('Não foi possível validar a imagem do vídeo gravado.')), timeout);
    video.muted = true; video.preload = 'auto';
    video.onloadeddata = () => finish(video.videoWidth > 0 && video.videoHeight > 0 ? null : new Error('O vídeo gravado não contém uma trilha visual válida.'));
    video.onerror = () => finish(new Error('O navegador não conseguiu reproduzir o vídeo gravado.'));
    video.src = url;
  });
}
