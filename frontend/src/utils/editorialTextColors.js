const ID = 'scormify-editorial-text-colors';
const BLOCK = /<style\b[^>]*\bid=["']scormify-editorial-text-colors["'][^>]*>[\s\S]*?<\/style>/gi;
const HEX = /^#[0-9a-f]{6}$/i;
const RULES = {
  text: 'body,body :is(p,span,strong,b,em,div,blockquote,a,label,small,button,input,textarea,td,th,dt,dd,figcaption,summary,code,pre)',
  title: 'body :is(h1,h2,h3,h4,h5,h6),body :is(h1,h2,h3,h4,h5,h6) *',
  card: 'body li,body li *',
  cardBackground: 'body li',
};

export function readEditorialTextColors(html = '') {
  const block = html.match(BLOCK)?.[0] || '';
  const colors = {};
  Object.keys(RULES).forEach(key => {
    const match = block.match(new RegExp(`data-${key}=["'](#[0-9a-f]{6})["']`, 'i'));
    if (match) colors[key] = match[1];
  });
  return colors;
}

export function applyEditorialTextColors(html = '', colors = {}) {
  colors = colors && typeof colors === 'object' ? colors : {};
  const clean = html.replace(BLOCK, '');
  const entries = Object.entries(RULES).filter(([key]) => HEX.test(colors[key] || ''));
  if (!entries.length) return clean;
  const attributes = entries.map(([key]) => `data-${key}="${colors[key]}"`).join(' ');
  const css = entries.map(([key,selector]) => `${selector}{${key === 'cardBackground' ? 'background' : 'color'}:${colors[key]}!important}`).join('\n');
  const block = `<style id="${ID}" ${attributes}>${css}</style>`;
  return /<\/head>/i.test(clean) ? clean.replace(/<\/head>/i, block+'</head>') : clean+block;
}
