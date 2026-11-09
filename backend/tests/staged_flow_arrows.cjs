const assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
const frames=new Map();let seq=0;
const dom=new JSDOM(fs.readFileSync(0,'utf8'),{runScripts:'dangerously',pretendToBeVisual:true,beforeParse(w){
 w.requestAnimationFrame=fn=>{frames.set(++seq,fn);return seq};w.cancelAnimationFrame=id=>frames.delete(id);
}});
const d=dom.window.document,$=id=>d.getElementById(id),plan=JSON.parse($('scormify-visualization-plan').textContent);
const arrows=plan.motions.filter(m=>m.kind==='flow');assert.equal(arrows.length,3);
const group=id=>d.querySelector('[data-motion-node="'+id+'"]');
const line=id=>d.querySelector('[data-visual-node="'+id+'"]');
function scrub(t){$('time').value=t/plan.duration*1000;$('time').dispatchEvent(new dom.window.Event('input'));}
for(const active of arrows){
 const mid=(active.start+active.end)/2;scrub(mid);
 arrows.forEach(m=>assert.equal(group(m.node).dataset.flowActive,String(m.node===active.node)));
 const offset=line(active.node).style.strokeDashoffset;scrub(mid+.3);
 assert.notEqual(line(active.node).style.strokeDashoffset,offset,'Flow advances without moving connection');
 assert.equal(group(active.node).getAttribute('transform'),null);
}
scrub(0);$('play').click();const frameBatch=[...frames.values()];frames.clear();frameBatch.forEach(fn=>fn(100));
const next=[...frames.values()];frames.clear();next.forEach(fn=>fn(200));
$('play').click();const paused=arrows.map(m=>line(m.node).style.strokeDashoffset);
assert.equal(frames.size,0);assert.deepEqual(arrows.map(m=>line(m.node).style.strokeDashoffset),paused);
$('labels').click();assert.equal($('labels').getAttribute('aria-pressed'),'false');$('reset').click();
assert.equal(group(arrows[0].node).dataset.flowActive,'true');assert.equal($('time').value,'0');
assert.equal(line(arrows[0].node).style.strokeDashoffset,'0');
dom.window.close();console.log('PASS three stage-specific flow arrows, scrub, playback, pause, labels and reset');
