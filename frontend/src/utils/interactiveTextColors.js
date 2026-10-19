const STYLE_ID = 'scormify-interactive-text-colors';
const BLOCK = /<style\b[^>]*\bid=["']scormify-interactive-text-colors["'][^>]*>[\s\S]*?<\/style>/gi;
const HEX = /^#[0-9a-f]{6}$/i;
const REGIONS = {
  title: ['#app>header h1', '#app>header .mission', 'body>header h1'],
  scene: ['.conversation', '.dossier', '.scene-caption', '.transcript', '.metrics'],
  panel: ['.panel', '.decision'],
};
const TEXT = ':is(h1,h2,h3,h4,p,div,span,strong,b,small,li,label,summary,blockquote,button:not(.primary):not(.secondary),textarea)';

export function readInteractiveTextColors(html = '') {
  const block = html.match(BLOCK)?.[0] || '';
  const result = {};
  Object.keys(REGIONS).forEach(key => {
    const match = block.match(new RegExp(`data-${key}=["'](#[0-9a-f]{6})["']`, 'i'));
    if (match) result[key] = match[1];
  });
  return result;
}

export function applyInteractiveTextColors(html = '', colors = {}) {
  const clean = html.replace(BLOCK, '');
  const valid = Object.entries(REGIONS).filter(([key]) => HEX.test(colors[key] || ''));
  if (!valid.length) return clean;
  const attrs = valid.map(([key]) => `data-${key}="${colors[key]}"`).join(' ');
  const css = valid.map(([key, regions]) => {
    const selectors = regions.flatMap(region => [region, `${region} ${TEXT}`]);
    return `${selectors.join(',')}{color:${colors[key]}!important}`;
  }).join('\n');
  const style = `<style id="${STYLE_ID}" ${attrs}>${css}</style>`;
  // Append after original CSS so dynamic text and future turns inherit the
  // same override. No changes to scripts, state, scoring, URLs or SVG artwork.
  return /<\/head>/i.test(clean) ? clean.replace(/<\/head>/i, style + '</head>') : clean + style;
}
