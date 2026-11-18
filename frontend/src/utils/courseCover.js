import DOMPurify from 'dompurify';
import {getApiUrl} from './apiUrl';

export function coverAssetUrl(source, backend = getApiUrl()) {
  if (typeof source !== 'string') return '';
  const src = source.trim();
  if (!src || /^(javascript|vbscript):/i.test(src)) return '';
  if (/^data:/i.test(src)) return /^data:image\//i.test(src) ? src : '';
  const local = src.replace(/^https?:\/\/[^/]+(?=\/api\/(?:projects\/|assets\/))/i, '');
  return local.startsWith('/api/') ? (backend || '').replace(/\/+$/, '') + local : local;
}

export function coverDimensions(slide = {}, course = {}) {
  const positive = value => Number.isFinite(Number(value)) && Number(value) > 0 ? Number(value) : 0;
  return {width:positive(slide.width) || positive(course.width) || 1920,
    height:positive(slide.height) || positive(course.height) || 820};
}

export function coverElementRect(element, stage) {
  const pixel = (value, base) => {
    const n = typeof value === 'string' && value.endsWith('%') ? parseFloat(value) * base / 100 : Number(value);
    return Number.isFinite(n) ? n : 0;
  };
  return {left:pixel(element.x, stage.width), top:pixel(element.y, stage.height),
    width:Math.max(1,pixel(element.width,stage.width) || 100), height:Math.max(1,pixel(element.height,stage.height) || 100)};
}

export function staticCoverDocument(source, backend = getApiUrl()) {
  if (typeof source !== 'string' || !source.trim()) return '';
  // Thumbnails are passive documents, not running course players. No scripts or frames.
  const clean = DOMPurify.sanitize(source, {WHOLE_DOCUMENT:true, ADD_TAGS:['style','link'],
    FORBID_TAGS:['script','iframe','object','embed','form','input','textarea','select','audio','video','base','meta'],
    FORBID_ATTR:['srcdoc','autofocus','autoplay','contenteditable']});
  const doc = new DOMParser().parseFromString(clean,'text/html');
  doc.querySelectorAll('[src]').forEach(node => node.setAttribute('src',coverAssetUrl(node.getAttribute('src'),backend)));
  doc.querySelectorAll('img').forEach(node => {node.removeAttribute('srcset');node.removeAttribute('loading');});
  doc.querySelectorAll('link').forEach(node => {
    if (node.getAttribute('rel') !== 'stylesheet') node.remove();
    else node.setAttribute('href',coverAssetUrl(node.getAttribute('href'),backend));
  });
  const cssUrls = text => text.replace(/url\(\s*(['"]?)([^)'"\s]+)\1\s*\)/gi,
    (_,quote,url) => `url("${coverAssetUrl(url,backend).replace(/"/g,'%22')}")`);
  doc.querySelectorAll('style').forEach(node => {node.textContent=cssUrls(node.textContent);});
  doc.querySelectorAll('[style]').forEach(node => node.setAttribute('style',cssUrls(node.getAttribute('style'))));
  const csp = "default-src 'none'; script-src 'none'; connect-src 'none'; frame-src 'none'; media-src 'none'; object-src 'none'; form-action 'none'; base-uri 'none'; img-src https: http: data: blob:; style-src 'unsafe-inline' https: http:; font-src https: http: data:";
  return `<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="${csp}"><meta name="referrer" content="no-referrer">${doc.head.innerHTML}<style>html,body{margin:0;overflow:hidden!important;}html{width:100%;height:100%;}body{min-height:100%;}*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important;}</style></head><body>${doc.body.innerHTML}</body></html>`;
}
