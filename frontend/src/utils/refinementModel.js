// Inert parsing only. Preserve the displayed scene as reference; never execute HTML.
export function refinementModel(html, preserveImages = false) {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  if (doc.body.getAttribute('data-sim-engine') !== 'finite-rules-v1') throw new Error('unsupported');
  const nodes = doc.querySelectorAll('script#scormify-simulator-plan');
  if (nodes.length !== 1) throw new Error('ambiguous model');
  const model = JSON.parse(nodes[0].textContent);
  if (!model || !Array.isArray(model.variables) || !Array.isArray(model.actions)) throw new Error('invalid model');
  delete model.visualNotice;
  // Raster bytes are already saved in the library. Never send megabytes of
  // pixels as text to the scene planner; refino creates a new explicit layer.
  if (model.visual && !preserveImages) delete model.visual.illustrations;
  const source = JSON.stringify(model);
  if (source.length > (preserveImages ? 2000000 : 120000)) throw new Error('model too large');
  return source;
}

export function objectImageCount(html) {
  try {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const data = JSON.parse(doc.querySelector('#scormify-simulator-plan')?.textContent || '{}');
    return Array.isArray(data.visual?.illustrations) ? data.visual.illustrations.length : 0;
  } catch { return 0; }
}
