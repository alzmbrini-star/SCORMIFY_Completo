const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

export function courseAnalysisError(error) {
  if (error instanceof TypeError || /failed to fetch|networkerror|load failed|timeout|tempo de resposta/i.test(error?.message || '')) {
    return 'A conexão com o servidor foi interrompida. A análise pode continuar em segundo plano. Use Retomar análise para consultar o resultado e reaproveitar as leituras salvas. O curso não foi alterado.';
  }
  return error?.message || 'Não foi possível concluir a análise. O curso não foi alterado.';
}

// Submit only once. Lost responses are recovered with status-only reads, which
// must never start another paid analysis or consume the stored result.
export async function runCourseAnalysis({ url, headers, cachedOnly = false, signal,
  onProgress, fetchImpl = fetch, delay = pause, now = Date.now, maxWait = 1800000 }) {
  async function request(target) {
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (signal?.aborted) abort();
    signal?.addEventListener('abort', abort, { once: true });
    const timer = setTimeout(abort, 45000);
    try {
      const response = await fetchImpl(target, { method: 'POST', headers, signal: controller.signal });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        const error = new Error(typeof body.detail === 'string' ? body.detail : `Servidor indisponível (HTTP ${response.status}).`);
        error.permanent = response.status < 500 && response.status !== 429;
        throw error;
      }
      return await response.json();
    } catch (error) {
      if (signal?.aborted) throw error;
      if (error.name === 'AbortError') throw new Error('Tempo de resposta do servidor excedido.');
      throw error;
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
    }
  }
  const finished = value => value.overallScore !== undefined || Array.isArray(value.improvements);
  const statusUrl = `${url}?status_only=true`;
  let data;
  try {
    data = await request(`${url}${cachedOnly ? '?cached_only=true' : '?resume_partial=true'}`);
  } catch (error) {
    if (error.permanent || signal?.aborted || cachedOnly) throw error;
    onProgress?.('Reconectando para consultar a análise já solicitada, sem iniciar outra geração...');
  }
  const started = now();
  let failures = 0;
  while (!signal?.aborted) {
    if (data && finished(data)) return data;
    if (data?.status === 'error') throw new Error(data.error || 'A análise foi interrompida.');
    if (data?.status === 'not_started') throw new TypeError('Failed to fetch');
    if (now() - started >= maxWait) throw new Error('Timeout aguardando análise do curso.');
    if (data) onProgress?.('Análise em andamento. Os conteúdos do curso permanecem preservados.');
    await delay(Math.min(10000, 2000 * (failures + 1)));
    if (signal?.aborted) break;
    try {
      data = await request(statusUrl);
      failures = 0;
    } catch (error) {
      if (error.permanent || signal?.aborted || ++failures >= 6) throw error;
      onProgress?.('Conexão temporariamente indisponível. Reconectando sem refazer as leituras salvas...');
    }
  }
  throw new DOMException('Acompanhamento encerrado.', 'AbortError');
}
