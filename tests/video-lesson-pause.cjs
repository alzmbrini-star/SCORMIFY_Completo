const assert=require('assert'),fs=require('fs'),path=require('path'),{createRequire}=require('module');
const front=createRequire(path.resolve(__dirname,'../frontend/package.json'));
const scripts=createRequire(front.resolve('react-scripts/package.json'));
const {JSDOM}=createRequire(scripts.resolve('jest-environment-jsdom'))('jsdom');
let current=0,paused=true,frames=new Map(),serial=0;
const dom=new JSDOM(fs.readFileSync(0,'utf8'),{url:'https://course.example/player',runScripts:'dangerously',beforeParse(w){
 w.TextEncoder=TextEncoder;
 w.requestAnimationFrame=fn=>{frames.set(++serial,fn);return serial;};
 w.cancelAnimationFrame=id=>frames.delete(id);
 Object.defineProperties(w.HTMLMediaElement.prototype,{duration:{get(){return 10;}},currentTime:{get(){return current;},set(n){current=n;}},paused:{get(){return paused;}}});
 w.HTMLMediaElement.prototype.play=function(){paused=false;this.dispatchEvent(new w.Event('play'));return Promise.resolve();};
 w.HTMLMediaElement.prototype.pause=function(){if(!paused){paused=true;this.dispatchEvent(new w.Event('pause'));}};
}});
const w=dom.window,d=w.document,v=d.getElementById('video');
v.dispatchEvent(new w.Event('loadedmetadata'));d.getElementById('play').click();
assert(!paused);assert(frames.size>0);
// Deliberately do not emit timeupdate: this used to let the next spoken phrase
// begin before the question could pause the media.
current=3.19;
for(const [id,fn] of [...frames]){frames.delete(id);fn();}
assert(paused,'pause reads the media clock before the next timeupdate');
assert.equal(d.getElementById('question').textContent,'Qual?');
assert.equal(frames.size,0,'paused media must not retain animation loops');
dom.window.close();console.log('speech pause monitor passed');
