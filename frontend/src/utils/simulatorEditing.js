import { isSlideSimulator, upgradeSimulatorSlide } from './simulatorSlide';
import { simulatorSlideRuntime } from '../components/games/simulatorSlideRuntime';
import { ruleVisualRuntime } from '../components/games/ruleVisualRuntime';
import { visualizationFinishRuntime } from '../components/games/visualizationFinishRuntime';

export function simulatorSource(content) {
  if (typeof content !== 'string') throw new Error('Simulador sem código HTML.');
  if (!content.startsWith('__B64__:')) return content;
  return decodeURIComponent(Array.from(atob(content.slice(8)), c => '%' + c.charCodeAt(0).toString(16).padStart(2, '0')).join(''));
}

export function simulatorPreferences(content) {
  const html=simulatorSource(content),doc=new DOMParser().parseFromString(html,'text/html');
  let experience={};
  try { experience=JSON.parse(doc.querySelector('#scormify-simulator-plan')?.textContent||'{}').experience||{}; } catch (_) { /* Existing HTML still remains editable. */ }
  return {complexity:['guided','applied','advanced'].includes(experience.complexity)?experience.complexity:'guided',
    visualStyle:['illustrated','technical'].includes(experience.visualStyle)?experience.visualStyle:'illustrated',
    activityType:doc.body.getAttribute('data-sim-engine')==='didactic-visualization-v1'?'visualization':'simulation'};
}

// Explicit author edit only. Keep the JSON model and authored scene byte-for-byte.
export function refreshSimulatorPresentation(content) {
  let html=simulatorSource(content);
  if (!isSlideSimulator(html)) throw new Error('Este elemento não é um simulador compatível.');
  html=html.replace(/<script id="scormify-simulator-slide-v3">[\s\S]*?<\/script>/i,
    () => '<script id="scormify-simulator-slide-v3">('+simulatorSlideRuntime.toString()+')();</script>');
  if (/data-sim-engine=["']finite-rules-v1["']/.test(html)) {
    html=html.replace(/<script id="scormify-rule-visual-v1">[\s\S]*?<\/script>/i,
      () => '<script id="scormify-rule-visual-v1">('+ruleVisualRuntime.toString()+')();</script>');
  }
  if (/data-sim-engine=["']didactic-visualization-v1["']/.test(html)) {
    html=html.replace(/<script id="scormify-visualization-finish-v1">[\s\S]*?<\/script>/i,
      () => '<script id="scormify-visualization-finish-v1">('+visualizationFinishRuntime.toString()+')();</script>');
  }
  return upgradeSimulatorSlide(html);
}

export function simulatorEditPatch(project,target,html) {
  const slide=project?.course?.slides?.find(s=>s.id===target?.slideId);
  const element=slide?.elements?.find(e=>e.id===target?.elementId);
  if (!element || element.type!=='html') throw new Error('O simulador original foi removido. Nenhuma alteração foi salva.');
  if (element.htmlContent!==target.source) throw new Error('O simulador foi alterado enquanto esta janela estava aberta. Reabra a edição para não sobrescrever mudanças.');
  if (!isSlideSimulator(html)) throw new Error('O código não identifica mais um simulador. O original foi preservado.');
  return {htmlContent:refreshSimulatorPresentation(html)};
}
