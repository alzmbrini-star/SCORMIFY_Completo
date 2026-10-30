// The Render frontend/API are separate origins. Use the existing bearer header,
// not cross-site cookies (which require a different CORS policy).
export async function fetchHtmlDiagnostic(api, projectId, headers) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 25000);
  try {
    const response = await fetch(`${api}/api/generate-html/jobs/diagnostics/latest?projectId=${encodeURIComponent(projectId || '')}`, {
      method: 'GET', headers, credentials: 'omit', signal: controller.signal,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      if (response.status === 401) throw new Error('Sua sessão expirou. Entre novamente para baixar o diagnóstico. Não é necessário gerar outra atividade.');
      if (response.status === 403) throw new Error('Você não tem permissão para baixar este diagnóstico.');
      throw new Error(typeof data?.detail === 'string' ? data.detail : `Não foi possível consultar o diagnóstico (HTTP ${response.status}). Nenhuma nova geração foi iniciada.`);
    }
    if (!data || typeof data.jobId !== 'string' || !Array.isArray(data.diagnostic?.attempts)) {
      throw new Error('O servidor não retornou um diagnóstico válido. Nenhuma nova geração foi iniciada.');
    }
    return data;
  } catch (error) {
    if (error.name === 'AbortError' || error instanceof TypeError) {
      throw new Error('A conexão para baixar o diagnóstico falhou. Tente somente o download novamente; não é necessário gerar outra atividade.');
    }
    throw error;
  } finally { clearTimeout(timer); }
}
