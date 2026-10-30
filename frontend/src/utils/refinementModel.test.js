import {refinementModel} from './refinementModel';
test('refinement preserves scene and component reference without executing HTML',()=>{
  const model={variables:[],actions:[],visual:{nodes:[{id:'gate'}]},visualProject:{version:1},visualNotice:'old'};
  const html=`<body data-sim-engine="finite-rules-v1"><script id="scormify-simulator-plan" type="application/json">${JSON.stringify(model)}</script><script>window.shouldNeverRun=true;</script></body>`;
  const source=JSON.parse(refinementModel(html));
  expect(source.visual).toEqual(model.visual);expect(source.visualProject).toEqual(model.visualProject);
  expect(source.visualNotice).toBeUndefined();expect(window.shouldNeverRun).toBeUndefined();
  expect(()=>refinementModel(html+html)).toThrow();
  expect(()=>refinementModel('<body>Other document</body>')).toThrow();
});
