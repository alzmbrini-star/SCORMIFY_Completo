// Extract inert, visible editorial text. Do not mistake CSS/JS for a heading.
export function slidePreviewText(html, selectors = []) {
  if (typeof html !== 'string' || !html.trim()) return '';
  const doc = new DOMParser().parseFromString(html, 'text/html');
  doc.querySelectorAll('style,script,template,noscript,svg,iframe,object,[hidden],[aria-hidden="true"]').forEach(node => node.remove());
  doc.querySelectorAll('[style]').forEach(node => {
    if (/display\s*:\s*none|visibility\s*:\s*hidden/i.test(node.getAttribute('style') || '')) node.remove();
  });
  const text = node => (node?.textContent || '').replace(/\s+/g, ' ').trim();
  for (const selector of selectors) {
    const value = text(doc.body.querySelector(selector));
    if (value) return value;
  }
  return text(doc.body);
}
