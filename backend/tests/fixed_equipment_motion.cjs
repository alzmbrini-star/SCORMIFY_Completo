const assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
(async()=>{
const frames=new Map();let seq=0;
const dom=new JSDOM(fs.readFileSync(0,'utf8'),{runScripts:'dangerously',pretendToBeVisual:true,beforeParse(w){
  w.requestAnimationFrame=fn=>{frames.set(++seq,fn);return seq};w.cancelAnimationFrame=id=>frames.delete(id);
}});
await new Promise(resolve=>dom.window.addEventListener('load',resolve,{once:true}));
const d=dom.window.document,$=id=>d.getElementById(id);
const equipment=d.querySelector('[data-motion-node="piece"]'),content=d.querySelector('[data-motion-node="liquid_marker"]');
const image=d.querySelector('[data-object-image="piece"]');assert(image);
function scrub(t){$('time').value=t/12*1000;$('time').dispatchEvent(new dom.window.Event('input'));}
const fixed=equipment.getAttribute('transform');scrub(0);const before=content.getAttribute('transform');
scrub(3);const during=content.getAttribute('transform');scrub(4);
assert.notEqual(before,during);assert.notEqual(during,content.getAttribute('transform'));
assert.equal(equipment.getAttribute('transform'),fixed,'Whole equipment must never rotate with contents');
scrub(10);const after=content.getAttribute('transform');scrub(12);assert.equal(content.getAttribute('transform'),after,'Contents stop outside mixing stage');
$('play').click();assert.equal($('play').getAttribute('aria-pressed'),'true');$('play').click();assert.equal(frames.size,0);
d.querySelector('[data-object-id="piece"]').click();assert($('detail').textContent.includes('Equipamento fixo'));
$('labels').click();assert.equal($('labels').getAttribute('aria-pressed'),'false');$('reset').click();
assert.equal($('time').value,'0');assert.equal(equipment.getAttribute('transform'),fixed);
dom.window.close();console.log('PASS fixed illustrated equipment, separate stage-bound contents, pause, reset and legends');
})().catch(e=>{console.error(e);process.exit(1)});
