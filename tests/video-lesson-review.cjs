const assert=require('assert'),fs=require('fs'),path=require('path'),{createRequire}=require('module');
const front=createRequire(path.resolve(__dirname,'../frontend/package.json'));
const scripts=createRequire(front.resolve('react-scripts/package.json'));
const {JSDOM}=createRequire(scripts.resolve('jest-environment-jsdom'))('jsdom');
const messages=[],html=fs.readFileSync(0,'utf8');
const dom=new JSDOM(html,{url:'https://course.example/player',runScripts:'dangerously',beforeParse(w){
 w.postMessage=m=>messages.push(m);
 w.HTMLMediaElement.prototype.pause=function(){};
}});
const d=dom.window.document,v=d.getElementById('video');
assert(v.controls,'author can listen to the original speech');
assert(d.getElementById('play').disabled);
assert(d.getElementById('seek').disabled);
for(const event of ['loadedmetadata','timeupdate','ended'])v.dispatchEvent(new dom.window.Event(event));
assert(d.getElementById('options').hidden);
assert(d.getElementById('answer').hidden);
assert(d.getElementById('message').textContent.includes('Editor'));
assert(!messages.some(m=>['result','complete','save'].includes(m.action)),'unreviewed timing cannot score or finish');
dom.window.close();console.log('pending lesson runtime passed');
