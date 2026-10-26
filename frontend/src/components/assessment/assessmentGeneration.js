// Resume the same paid request after a lost connection. No re-generation on poll.
export async function generateAssessment(api, payload, headers, options = {}) {
  const wait = options.wait || (ms => new Promise(resolve => setTimeout(resolve, ms)));
  let storage = options.storage;
  if (storage === undefined) { try { storage = globalThis.sessionStorage; } catch { storage = null; } }
  const key = `scormify-assessment-job:${payload.projectId}`;
  const signature = JSON.stringify(payload);
  let pending;
  try { pending = JSON.parse(storage?.getItem(key) || 'null'); } catch { pending = null; }
  if (!pending || pending.signature !== signature) pending = { signature, requestId: crypto.randomUUID() };
  const persist = () => { try { storage?.setItem(key, JSON.stringify(pending)); } catch { /* optional */ } };
  const clear = () => { try { storage?.removeItem(key); } catch { /* optional */ } };
  persist();
  async function request(url, init) {
    for (let attempt = 0; attempt < 4; attempt++) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 25000);
      try {
        const response = await fetch(url, { ...init, credentials: 'include', signal: controller.signal });
        if ([502, 503, 504].includes(response.status)) throw new TypeError('Serviço indisponível');
        const data = await response.json().catch(() => { throw new TypeError('Resposta incompleta'); });
        if (!response.ok) { clear(); throw new Error(data.detail || 'Não foi possível consultar a geração.'); }
        return data;
      } catch (error) {
        if (!(error instanceof TypeError) && error.name !== 'AbortError') throw error;
        options.onProgress?.('Reconectando… o mesmo pedido será recuperado, sem gerar novamente.');
        if (attempt === 3) throw new Error('Conexão interrompida. Clique em Gerar novamente para consultar a mesma geração.');
        await wait(1000 * (attempt + 1));
      } finally { clearTimeout(timeout); }
    }
  }
  let state;
  if (!pending.jobId) {
    options.onProgress?.('Criando questões e preparando as imagens…');
    state = await request(`${api}/api/assessment-questions/generate/jobs`, {
      method: 'POST', headers, body: JSON.stringify({ ...payload, requestId: pending.requestId }),
    });
    if (!state.jobId) throw new Error('O servidor não confirmou a geração.');
    pending.jobId = state.jobId; persist();
  }
  const started = Date.now();
  while (Date.now() - started < (options.maxWaitMs ?? 19 * 60 * 1000)) {
    state = state || await request(`${api}/api/assessment-questions/generate/jobs/${encodeURIComponent(pending.jobId)}`, { headers });
    if (state.status === 'done') { clear(); return state; }
    if (state.status === 'error') { clear(); throw new Error(state.error || 'Não foi possível concluir a geração.'); }
    if (!['queued', 'running'].includes(state.status)) throw new Error('Estado desconhecido. Consulte a geração novamente.');
    options.onProgress?.(state.imagesTotal ? `Gerando imagens de apoio: ${state.imagesCompleted || 0} de ${state.imagesTotal} processadas…` : 'Criando questões com IA…');
    await wait(options.pollMs ?? 3000); state = null;
  }
  throw new Error('A geração continua em processamento. Clique em Gerar novamente para consultar o mesmo pedido.');
}
