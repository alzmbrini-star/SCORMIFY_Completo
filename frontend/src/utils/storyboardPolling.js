function pause(ms, signal) {
  return new Promise((resolve, reject) => {
    const abort = () => {clearTimeout(timer);reject(new DOMException('Acompanhamento encerrado.', 'AbortError'));};
    const timer = setTimeout(() => {signal?.removeEventListener('abort', abort);resolve();}, ms);
    if (signal?.aborted) abort();else signal?.addEventListener('abort', abort, {once:true});
  });
}

// One request at a time; reads never restart or bill a generation.
export async function waitForStoryboard(readSession, {signal, onProgress, onLongWait,
  interval=4000, delay=pause, now=Date.now}={}) {
  let failures=0,longNotice=false;const started=now();
  while (!signal?.aborted) {
    let session;
    try {session=await readSession(signal);failures=0;}
    catch(error) {
      if(error.name==='AbortError'||error.permanent||++failures>=30)throw error;
      onProgress?.('Reconectando ao servidor. Os lotes salvos serão preservados.');
      await delay(interval,signal);continue;
    }
    if(session.step==='storyboarded'&&session.storyboard)return session;
    if(session.step==='structured'&&!session.storyboardProgress)
      throw new Error(session.error||'A geração foi interrompida. Clique em Aprovar e Gerar Storyboard para retomar os lotes salvos.');
    const progress=session.storyboardProgress;
    if(progress) {
      const pct=progress.total>0?Math.max(0,Math.min(100,Math.round(progress.batch/progress.total*100))):0;
      onProgress?.(`${progress.message} (${pct}%)`);
    } else onProgress?.('Processando com IA. Acompanhando os lotes salvos…');
    if(!longNotice&&now()-started>=900000){longNotice=true;onLongWait?.('A geração continua em execução. Cursos extensos podem levar mais tempo; os lotes concluídos ficam salvos.');}
    await delay(interval,signal);
  }
  throw new DOMException('Acompanhamento encerrado.', 'AbortError');
}
