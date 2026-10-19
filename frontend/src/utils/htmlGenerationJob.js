// A lost connection must resume the same job, never create another paid request.
export async function generateHtmlJob(api, payload, headers, options = {}) {
  const wait = options.wait || (ms => new Promise(resolve => setTimeout(resolve, ms)));
  const pollMs = options.pollMs ?? 3000;
  const maxWaitMs = options.maxWaitMs ?? 20 * 60 * 1000;
  const key = `scormify-html-job:${payload.projectId || 'editor'}`;
  let storage = options.storage;
  if (storage === undefined) { try { storage = globalThis.sessionStorage; } catch { storage = null; } }
  const signatureBytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(payload)));
  const signature = Array.from(new Uint8Array(signatureBytes), value => value.toString(16).padStart(2, '0')).join('');
  let pending;
  try { pending = JSON.parse(storage?.getItem(key) || 'null'); } catch { pending = null; }
  if (!pending || pending.signature !== signature) pending = { signature, requestId: crypto.randomUUID() };
  const persist = () => { try { storage?.setItem(key, JSON.stringify(pending)); } catch { /* Storage can be disabled. */ } };
  const clear = () => { try { storage?.removeItem(key); } catch { /* Not required for generation. */ } };
  persist();
  async function request(url, init) {
    for (let attempt = 0; attempt < 5; attempt++) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 25000);
      try {
        const response = await fetch(url, { ...init, credentials: 'include', signal: controller.signal });
        if ([502, 503, 504].includes(response.status)) throw new TypeError('Serviço temporariamente indisponível');
        const data = await response.json().catch(() => { throw new TypeError('Resposta incompleta do servidor'); });
        if (!response.ok) { clear(); throw new Error(data.detail || 'Não foi possível consultar a geração.'); }
        return data;
      } catch (error) {
        if (!(error instanceof TypeError) && error.name !== 'AbortError') throw error;
        options.onProgress?.('Reconectando ao servidor… sua geração será consultada novamente.');
        if (attempt === 4) throw new Error('A conexão com o servidor foi interrompida. Clique em Gerar HTML novamente para consultar a mesma geração.');
        await wait(Math.min(1000 * 2 ** attempt, 8000));
      } finally { clearTimeout(timeout); }
    }
  }
  let state;
  if (!pending.jobId) {
    options.onProgress?.('Enviando pedido de geração…');
    state = await request(`${api}/api/generate-html/jobs`, { method: 'POST', headers,
      body: JSON.stringify({ ...payload, requestId: pending.requestId }) });
    if (!state.jobId) { clear(); throw new Error('O servidor não confirmou o pedido de geração.'); }
    pending.jobId = state.jobId; persist();
  }
  const started = Date.now();
  while (Date.now() - started < maxWaitMs) {
    state = state || await request(`${api}/api/generate-html/jobs/${encodeURIComponent(pending.jobId)}`, { headers });
    if (state.status === 'done') { clear(); if (!state.html) throw new Error('O resultado da geração está vazio.'); return state.html; }
    if (state.status === 'error') { clear(); throw new Error(state.error || 'A geração não pôde ser concluída.'); }
    if (!['queued', 'running'].includes(state.status)) throw new Error('O servidor retornou um estado desconhecido. Tente consultar a geração novamente.');
    options.onProgress?.('Gerando em segundo plano… o resultado será recuperado automaticamente.');
    await wait(pollMs); state = null;
  }
  throw new Error('A geração está demorando mais que o esperado. Clique em Gerar HTML novamente para consultar o resultado.');
}
