// Data-only helpers shared by manual authoring, question-bank imports and AI drafts.
export function videoQuizSnapshot(element) {
  if (element?.videoQuizConfig) return element.videoQuizConfig;
  try {
    const match=/<script\b[^>]*\bid=["']video-quiz-data["'][^>]*>([\s\S]*?)<\/script>/i.exec(element?.htmlContent || '');
    return match ? JSON.parse(match[1]) : null;
  } catch (_) { return null; }
}

export function absoluteVideoQuestions(checkpoints, duration) {
  if (!Number.isFinite(duration) || duration <= 0) return checkpoints;
  return checkpoints.map(cp => cp.relative ? {...cp, at: Math.round(cp.at * duration * 100) / 100, relative: false} : cp);
}

export function nextVideoQuestionTime(checkpoints, duration) {
  const known = Number.isFinite(duration) && duration > 0;
  const rows = absoluteVideoQuestions(checkpoints, duration);
  const relative = !known && rows.some(cp => cp.relative);
  const points = rows.filter(cp => Boolean(cp.relative) === relative).map(cp => Number(cp.at)).filter(Number.isFinite).sort((a,b) => a-b);
  const last = points.length ? points[points.length-1] : 0;
  if (!relative && (!known || last + 10 < duration)) return {at: last + 10, relative: false};
  const end = relative ? 1 : duration;
  const boundaries = [0, ...points.filter(t => t > 0 && t < end), end];
  // Prefer the next segment; when it is full, use the largest free interval.
  let left = last, right = end;
  if (right - left < (relative ? .01 : .2)) {
    left = 0; right = 0;
    for (let i=1; i<boundaries.length; i++) if (boundaries[i]-boundaries[i-1] > right-left) { left = boundaries[i-1]; right = boundaries[i]; }
  }
  return {at: Math.round((left+right)/2 * 1000)/1000, relative};
}

export function prepareVideoQuizDraft(draft, duration) {
  const errors = [];
  const rows = absoluteVideoQuestions(draft.checkpoints || [], duration);
  if (!rows.length || rows.length > 12) errors.push({message: 'Adicione de 1 a 12 perguntas.'});
  const seen = new Set();
  const checkpoints = rows.map((cp, index) => {
    const report = (field, message) => errors.push({index, label: `${field} ${index+1}`, message: `Pergunta ${index+1}: ${message}`});
    const question = String(cp.question || '').trim(), explanation = String(cp.explanation || '').trim();
    if (!question) report('Enunciado', 'preencha o enunciado.');
    if (!explanation) report('Explicação', 'preencha a explicação que permitirá continuar após o limite de erros.');
    const retained = (cp.options || []).map((text, oldIndex) => ({text: String(text || '').trim(), oldIndex})).filter(o => o.text);
    if (retained.length < 2) report('Alternativa 1 da pergunta', 'preencha ao menos duas alternativas. As alternativas extras vazias são opcionais.');
    const correctIndex = retained.findIndex(o => o.oldIndex === cp.correctIndex);
    if (correctIndex < 0) report('Enunciado', 'marque uma alternativa preenchida como correta.');
    const at = cp.at;
    if (typeof at !== 'number' || !Number.isFinite(at) || at < 0 || cp.relative && (at <= 0 || at >= 1)) report('Tempo da pergunta', 'informe um tempo de pausa válido.');
    else if (Number.isFinite(duration) && duration > 0 && !cp.relative && at >= duration) report('Tempo da pergunta', `a pausa em ${at}s precisa acontecer antes do fim do vídeo (${duration.toFixed(1)}s).`);
    else if (seen.has(`${!!cp.relative}:${at}`)) report('Tempo da pergunta', 'escolha um momento diferente das outras perguntas.');
    seen.add(`${!!cp.relative}:${at}`);
    if (!Number.isInteger(cp.maxAttempts) || cp.maxAttempts < 1 || cp.maxAttempts > 10) report('Máximo de tentativas da pergunta', 'o limite deve ser de 1 a 10 tentativas.');
    return {...cp, question, explanation, options: retained.map(o => o.text), correctIndex};
  });
  return {config: {...draft, checkpoints}, errors};
}
