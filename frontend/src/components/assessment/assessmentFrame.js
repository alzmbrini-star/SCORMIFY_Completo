import { buildAssessmentHtml } from './AssessmentBuilder';

// Only the controlled, data-escaped renderer gets provider-compatible origin
// permissions. Never grant these permissions to saved arbitrary htmlContent.
export function assessmentFrameDocument(element) {
  const config = element.assessmentConfig || {};
  if (Array.isArray(config.questions)) return buildAssessmentHtml(config);
  // Older manual assessments keep their immutable question snapshot in the
  // JSON data block, not assessmentConfig. Parse data only, never saved code.
  const match = String(element.htmlContent || '').match(/<script\b[^>]*\bid=["']assessment-data["'][^>]*>([\s\S]*?)<\/script>/i);
  try {
    const snapshot = JSON.parse(match ? match[1] : 'null');
    if (snapshot && Array.isArray(snapshot.questions)) return buildAssessmentHtml({ ...snapshot, ...config, questions: snapshot.questions });
  } catch (_) { /* Show a controlled error rather than execute saved markup. */ }
  return '<!doctype html><html lang="pt-BR"><body style="background:#081139;color:white;font-family:Arial;padding:24px">Não foi possível ler as questões desta avaliação. Reinsira a avaliação pelo Banco, sem excluir as questões salvas.</body></html>';
}

export const assessmentFrameSandbox = 'allow-scripts allow-same-origin allow-forms allow-downloads allow-popups allow-popups-to-escape-sandbox allow-modals';
export const assessmentFrameAllow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
