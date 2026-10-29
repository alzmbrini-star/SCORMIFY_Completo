import { simulatorSlideRuntime } from '../components/games/simulatorSlideRuntime';

export function isSlideSimulator(html) {
  if (typeof html === 'string' && html.startsWith('__B64__:')) {
    try { return isSlideSimulator(atob(html.slice(8))); } catch (_) { return false; }
  }
  return typeof html === 'string' && /<body\b[^>]*\bdata-sim-engine=["'](?:finite-rules-v1|entity-planning-v1)["']/i.test(html);
}

export function upgradeSimulatorSlide(html) {
  if (!html || typeof html !== 'string') return html;
  if (html.startsWith('__B64__:')) {
    try {
      const binary = atob(html.slice(8));
      const source = decodeURIComponent(Array.from(binary, c => '%' + c.charCodeAt(0).toString(16).padStart(2, '0')).join(''));
      const upgraded = upgradeSimulatorSlide(source);
      return upgraded === source ? html : '__B64__:' + btoa(unescape(encodeURIComponent(upgraded)));
    } catch (_) { return html; }
  }
  if (!isSlideSimulator(html) || html.includes('id="scormify-simulator-slide-v1"')) return html;
  if (!html.includes('id="scormify-simulator-plan"')) return html;
  const script = '<script id="scormify-simulator-slide-v1">(' + simulatorSlideRuntime.toString() + ')();</script>';
  return /<\/body>/i.test(html) ? html.replace(/<\/body>/i, script + '</body>') : html + script;
}
