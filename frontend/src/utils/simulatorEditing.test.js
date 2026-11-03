import { simulatorEditPatch,refreshSimulatorPresentation,simulatorSource,simulatorPreferences } from './simulatorEditing';
const model={title:'Órbita',mission:'Observar',experience:{complexity:'guided',visualStyle:'illustrated'}};
const html='<html><body data-sim-engine="finite-rules-v1"><script id="scormify-simulator-plan" type="application/json">'+JSON.stringify(model)+'</script><script id="scormify-rule-visual-v1">oldVisual();</script><script id="scormify-simulator-slide-v3">oldSlide();</script></body></html>';
const target={slideId:'s',elementId:'e',source:html};
const project={course:{slides:[{id:'s',elements:[{id:'e',type:'html',htmlContent:html,x:21,y:42,width:700,height:450}]}]}};
test('explicit presentation refresh preserves authored model and replaces only trusted runtimes',()=>{
 const result=refreshSimulatorPresentation(html);
 expect(result).toContain(JSON.stringify(model));expect(result).not.toContain('oldVisual()');expect(result).not.toContain('oldSlide()');
 expect(result).toContain('sim-motion-tools');expect(result).toContain('sim-visual-stage');
 expect(refreshSimulatorPresentation(result)).toBe(result);
});
test('save targets original element without new placement or implicit insertion',()=>{
 const before=JSON.stringify(project),patch=simulatorEditPatch(project,target,html);
 expect(Object.keys(patch)).toEqual(['htmlContent']);expect(JSON.stringify(project)).toBe(before);
 expect(()=>simulatorEditPatch({course:{slides:[]}},target,html)).toThrow('removido');
 expect(()=>simulatorEditPatch(project,{...target,source:'changed'},html)).toThrow('alterado');
 expect(()=>simulatorEditPatch(project,target,'<p>Other</p>')).toThrow('original foi preservado');
});
test('base64 unicode and previous preferences round-trip without evaluating authored scripts',()=>{
 const encoded='__B64__:'+btoa(unescape(encodeURIComponent(html)));
 expect(simulatorSource(encoded)).toBe(html);
 expect(simulatorPreferences(html)).toEqual({complexity:'guided',visualStyle:'illustrated',activityType:'simulation'});
 expect(simulatorPreferences('<body data-sim-engine="didactic-visualization-v1"></body>').activityType).toBe('visualization');
});
