import {visualizationFinishRuntime} from './visualizationFinishRuntime';
afterEach(()=>{document.head.querySelectorAll('#scormify-visualization-finish-style-v1').forEach(n=>n.remove());document.body.innerHTML='';});
test.each(['midnight','daylight','warm'])('portable finish function executes with %s theme without changing data or motion',theme=>{
  const plan={background:theme==='midnight'?'#10243b':'#faf5ee',presentation:{theme,atmosphere:'studio',accent:'#48c6d7'},nodes:[{id:'ball',type:'circle',label:'Objeto',attrs:{x:300,y:200,r:20,fill:'#42a5e6'},appearance:{material:'emissive',depth:'soft'}}]};
  const original=JSON.stringify(plan);
  document.body.innerHTML='<figure><svg id="scene"><g role="button" transform="translate(20 30)"><circle cx="300" cy="200" r="20" fill="#42a5e6"/></g></svg></figure><aside><div id="items"><button>Objeto</button></div></aside><script id="scormify-visualization-plan" type="application/json">'+original+'</script>';
  const reset=document.createElement('button');reset.id='reset';document.body.appendChild(reset);
  // Same stringified, closure-free function embedded by the Editor upgrader.
  new Function('('+visualizationFinishRuntime.toString()+')()')();
  expect(document.body.dataset.visualTheme).toBe(theme);
  expect(document.querySelector('circle').getAttribute('filter')).toBe('url(#vf-glow)');
  expect(document.querySelector('g').getAttribute('transform')).toBe('translate(20 30)');
  expect(document.getElementById('scormify-visualization-plan').textContent).toBe(original);
  document.querySelector('#items button').click();expect(document.querySelector('g').dataset.vfSelected).toBe('true');
  reset.click();expect(document.querySelector('g').hasAttribute('data-vf-selected')).toBe(false);
  expect(document.querySelector('#items button').getAttribute('aria-pressed')).toBe('false');
  visualizationFinishRuntime();expect(document.querySelectorAll('#vf-definitions')).toHaveLength(1);
});
