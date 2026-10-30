const text = value => typeof value === 'string' ? value.slice(0, 800) : '';
const normalized = value => text(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

// Exact project membership wins. Context matches are suggestions, not assertions
// that arbitrary SVG artwork is a catalog component. No AI calls or rule edits.
export function componentLibraryFilter(catalog, model, project, showAll = false) {
  const entries = Object.entries(catalog?.components || {});
  const original = Array.isArray(model?.visualProject?.instances) ? model.visualProject.instances.slice(0, 6) : [];
  const current = Array.isArray(project?.instances) ? project.instances.slice(0, 6) : [];
  const used = new Set([...original, ...current].map(row => row?.component).filter(id => typeof id === 'string'));
  if (showAll) return { entries, basis: 'all', total: entries.length };
  if (used.size) return { entries: entries.filter(([id]) => used.has(id)), basis: 'used', total: entries.length };
  const fields = [model?.title, model?.subtitle, model?.mission, model?.visual?.title, model?.visual?.description];
  (Array.isArray(model?.variables) ? model.variables.slice(0, 10) : []).forEach(v => fields.push(v?.id, v?.label));
  (Array.isArray(model?.actions) ? model.actions.slice(0, 18) : []).forEach(a => fields.push(a?.id, a?.label));
  (Array.isArray(model?.visual?.nodes) ? model.visual.nodes.slice(0, 100) : []).forEach(n => fields.push(n?.id, n?.label));
  const context = ' ' + fields.map(normalized).filter(Boolean).join(' ') + ' ';
  const related = entries.filter(([id, def]) => {
    const terms = Array.isArray(def.searchTerms) ? def.searchTerms : [id, def.description];
    return terms.some(term => { const value = normalized(term); return value.length > 2 && context.includes(' ' + value + ' '); });
  });
  return { entries: related, basis: related.length ? 'context' : 'none', total: entries.length };
}
