export function analysisMessage(result) {
  const visual = result.visualAnalysis;
  if (visual && visual.readSlides < visual.totalSlides) {
    return `Análise incompleta: ${visual.readSlides} de ${visual.totalSlides} slides lidos. Leituras válidas preservadas; confira o motivo das falhas por slide. Nenhuma mudança foi aplicada.`;
  }
  return `Análise concluída! Nota geral: ${result.overallScore}/10. ${result.improvements?.length || 0} melhorias sugeridas. Revise e selecione as sugestões para gerar uma prévia; nada foi aplicado ao curso.`;
}

export function updateAnalysisStatus(messages, projectId, text, status) {
  const entry = { role: 'agent', text, analysisProjectId: projectId, status };
  const index = messages.findIndex(m => m.analysisProjectId === projectId);
  return index < 0 ? [...messages, entry] : messages.map((m, i) => i === index ? entry : m);
}
