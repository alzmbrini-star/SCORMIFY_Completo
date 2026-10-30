// Inert parsing only. Preserve the displayed scene as reference; never execute HTML.
export function refinementModel(html) {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  if (doc.body.getAttribute('data-sim-engine') !== 'finite-rules-v1') throw new Error('unsupported');
  const nodes = doc.querySelectorAll('script#scormify-simulator-plan');
  if (nodes.length !== 1) throw new Error('ambiguous model');
  const model = JSON.parse(nodes[0].textContent);
  if (!model || !Array.isArray(model.variables) || !Array.isArray(model.actions)) throw new Error('invalid model');
  delete model.visualNotice;
  const source = JSON.stringify(model);
  if (source.length > 120000) throw new Error('model too large');
  return source;
}
