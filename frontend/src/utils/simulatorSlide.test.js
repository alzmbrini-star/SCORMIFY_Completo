import { isSlideSimulator, upgradeSimulatorSlide } from './simulatorSlide';
import { wrapInteractiveFullbleed } from './htmlUtils';

test.each(['finite-rules-v1','entity-planning-v1'])('upgrades existing %s data only once without the fixed-stage shrinker',engine=>{
  const html='<html><body data-sim-engine="'+engine+'"><script id="scormify-simulator-plan" type="application/json">{"title":"Prática ç"}</script><script>const originalEngine=true;</script></body></html>';
  const updated=upgradeSimulatorSlide(html);
  expect(updated).toContain('id="scormify-simulator-slide-v3"');
  expect(updated).toContain('originalEngine=true');
  expect(updated).toContain('Prática ç');
  expect(upgradeSimulatorSlide(updated)).toBe(updated);
  expect(wrapInteractiveFullbleed(html,'fit')).not.toContain('id="__scormify_fit_v3"');
  expect(updated).not.toContain('scale(');
  expect(isSlideSimulator('__B64__:' + btoa(html))).toBe(true);
});

test('keeps ordinary pages untouched',()=>{
  const html='<html><body><h1>Conteúdo comum</h1></body></html>';
  expect(upgradeSimulatorSlide(html)).toBe(html);
});

test('upgrades the previous slide layout and bridges the existing engine only once',()=>{
  const html='<html><body data-sim-engine="finite-rules-v1"><script id="scormify-simulator-plan" type="application/json">{}</script><script>function render(view){original(view);}</script><script id="scormify-simulator-slide-v1">oldLayout();</script></body></html>';
  const updated=upgradeSimulatorSlide(html);
  expect(updated).not.toContain('oldLayout();');
  expect(updated).toContain('id="scormify-rule-visual-v1"');
  expect(updated).toContain('scormify:rules-state');
  expect(updated).toContain('original(view);');
  expect(upgradeSimulatorSlide(updated)).toBe(updated);
});
