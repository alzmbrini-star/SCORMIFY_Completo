const assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
(async()=>{
  let frames=new Map(),seq=0,errors=[];
  const dom=new JSDOM(fs.readFileSync(0,'utf8'),{runScripts:'dangerously',pretendToBeVisual:true,beforeParse(w){
    w.requestAnimationFrame=fn=>{frames.set(++seq,fn);return seq};w.cancelAnimationFrame=id=>frames.delete(id);
    w.addEventListener('error',e=>errors.push(e.message));
  }});
  await new Promise(resolve=>dom.window.addEventListener('load',resolve,{once:true}));
  const d=dom.window.document,$=id=>d.getElementById(id),image=d.querySelector('[data-object-image="piece"]');
  assert(image,'Image is mounted on semantic piece');
  if(d.body.dataset.simEngine==='finite-rules-v1'){
    image.dispatchEvent(new dom.window.Event('load'));
    const part=d.querySelector('[data-visual-node="piece"]'),initial=part.getAttribute('transform');
    const actual=JSON.parse($('scormify-rule-view').textContent).state;
    for(let t=0;t<=1200;t+=100){const batch=[...frames.values()];frames.clear();batch.forEach(fn=>fn(t));}
    assert.notEqual(part.getAttribute('transform'),initial,'Stage demonstration and continuous motion must coexist');
    assert.deepEqual(JSON.parse($('scormify-rule-view').textContent).state,actual,'Presentation never answers the activity');
    const playback=[...d.querySelectorAll('button')].find(b=>b.textContent==='Pausar movimento');
    assert(playback);playback.click();const paused=part.getAttribute('transform');
    const batch=[...frames.values()];frames.clear();batch.forEach(fn=>fn(1500));
    assert.equal(part.getAttribute('transform'),paused);
    [...d.querySelectorAll('button')].find(b=>b.textContent==='Objetos e legendas').click();
    assert(d.querySelector('[data-legend-object="piece"]'));assert(!d.querySelector('[data-legend-object="body"]'));
    $('reset').click();assert.deepEqual(JSON.parse($('scormify-rule-view').textContent).state,actual);
    assert.equal(image.parentElement,part);assert.deepEqual(errors,[]);dom.window.close();
    console.log('PASS rule image group, stage replay plus rotation, unchanged logical state, pause, reset and semantic legends');return;
  }
  const part=d.querySelector('[data-visual-node="piece"]'),moving=d.querySelector('[data-motion-node="piece"]');
  assert.equal(image.parentElement,part,'Image must inherit the moving group, not float beside it');
  assert.equal(image.getAttribute('width'),'130');assert.equal(image.getAttribute('x'),'-65');
  image.dispatchEvent(new dom.window.Event('load'));
  assert.equal(part.querySelector('[data-motion-node="body"]').style.opacity,'0','Hide vector fallback only once image loads');
  function scrub(seconds){$('time').value=seconds/12*1000;$('time').dispatchEvent(new dom.window.Event('input'));}
  for(const [seconds,x] of [[0,0],[4,60],[8,120],[12,120]]){
    scrub(seconds);const observed=Number(moving.getAttribute('transform').match(/translate\(([^ ]+)/)[1]);
    assert(Math.abs(observed-x)<1,'Stage transition must advance and hold, never oscillate backwards');
    assert.equal(image.parentElement,part);
  }
  scrub(8);assert.match($('progress').textContent,/Observar/);
  d.querySelector('[data-object-id="piece"]').click();assert.match($('detail').textContent,/peça inteira/);
  $('play').click();assert.equal($('play').getAttribute('aria-pressed'),'true');
  $('play').click();assert.equal(frames.size,0);
  $('reset').click();assert.equal(moving.getAttribute('transform'),'translate(0 0)');
  assert.equal($('time').value,'0');assert.deepEqual(errors,[]);
  // Failed images restore the original complete vector object.
  image.dispatchEvent(new dom.window.Event('error'));
  assert.equal(part.querySelector('[data-motion-node="body"]').style.opacity,'');
  assert(!image.isConnected);
  dom.window.close();console.log('PASS semantic image group, staged movement, pause, reset, legends and error fallback');
})().catch(e=>{console.error(e);process.exit(1)});
