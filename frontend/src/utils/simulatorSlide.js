import { simulatorSlideRuntime } from '../components/games/simulatorSlideRuntime';
import { ruleVisualRuntime } from '../components/games/ruleVisualRuntime';
import { visualizationFinishRuntime } from '../components/games/visualizationFinishRuntime';

export function isSlideSimulator(html) {
  if (typeof html === 'string' && html.startsWith('__B64__:')) {
    try { return isSlideSimulator(atob(html.slice(8))); } catch (_) { return false; }
  }
  return typeof html === 'string' && /<body\b[^>]*\bdata-sim-engine=["'](?:finite-rules-v1|entity-planning-v1|didactic-visualization-v1)["']/i.test(html);
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
  if (!isSlideSimulator(html)) return html;
  if (/data-sim-engine=["']didactic-visualization-v1["']/.test(html)) {
    if (html.includes('scormify-visualization-finish-v1') || !/id=["']scormify-visualization-plan["']/.test(html)) return html;
    const finish = '<script id="scormify-visualization-finish-v1">(' + visualizationFinishRuntime.toString() + ')();</script>';
    return /<\/body>/i.test(html) ? html.replace(/<\/body>/i, finish + '</body>') : html;
  }
  if (!html.includes('id="scormify-simulator-plan"')) return html;
  if (html.includes('data-sim-engine="finite-rules-v1"') && !html.includes('id="scormify-rule-visual-v1"') && html.includes('function render(view){')) {
    const bridge = "var bridge=document.getElementById('scormify-rule-view');if(!bridge){bridge=document.createElement('script');bridge.id='scormify-rule-view';bridge.type='application/json';document.body.appendChild(bridge);}bridge.textContent=JSON.stringify(view);document.dispatchEvent(new CustomEvent('scormify:rules-state',{detail:view}));";
    html=html.replace('function render(view){','function render(view){'+bridge);
    html=html.replace(/<\/body>/i,'<script id="scormify-rule-visual-v1">('+ruleVisualRuntime.toString()+')();</script></body>');
  }
  if (html.includes('id="scormify-simulator-slide-v3"')) return html;
  html=html.replace(/<script id="scormify-simulator-slide-v[12]">[\s\S]*?<\/script>/i,'');
  const script = '<script id="scormify-simulator-slide-v3">(' + simulatorSlideRuntime.toString() + ')();</script>';
  return /<\/body>/i.test(html) ? html.replace(/<\/body>/i, script + '</body>') : html + script;
}
