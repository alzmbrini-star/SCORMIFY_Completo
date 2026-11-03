export function canCreateSimulators(user) {
  if (!user) return false;
  if (user.role === 'super_admin' || user.roles?.includes('super_admin')) return true;
  return user.permissions?.createSimulators === undefined || user.permissions.createSimulators === true;
}

export function isSimulatorRequest(prompt, activityType = 'simulation', source = '') {
  if (source || activityType === 'visualization') return true;
  const text = String(prompt || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  if (/estudos?\s+de\s+caso|analise\s+de\s+caso|case\s+stud(?:y|ies)/.test(text)) return false;
  return /\bsimul(?:ador(?:es)?|acao|ations?|ators?)\b/.test(text)
    || /\b(?:demonstracao|demonstration|animacao|visualizacao)\b[^.!?\n]{0,80}\b(?:visual|guiad[ao]|didatic[ao]|guided|didactic)\b/.test(text)
    || /\b(?:guided|didactic)\s+(?:visual\s+)?demonstration\b/.test(text);
}
