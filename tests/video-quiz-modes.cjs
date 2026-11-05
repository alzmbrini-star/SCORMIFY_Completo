const assert=require('assert'),fs=require('fs'),path=require('path'),{createRequire}=require('module');
const front=createRequire(path.resolve(__dirname,'../frontend/package.json'));
const scripts=createRequire(front.resolve('react-scripts/package.json'));
const {JSDOM}=createRequire(scripts.resolve('jest-environment-jsdom'))('jsdom');
const {ungraded,graded,host}=JSON.parse(fs.readFileSync(0,'utf8'));
function setup(html,saved='{}') {
 let current=0,paused=true,store=saved,writes=[],messages=[];
 const dom=new JSDOM(html,{url:'https://course.example/player',runScripts:'dangerously',beforeParse(w){
  w.TextEncoder=TextEncoder;
  w.API={LMSGetValue:k=>k==='cmi.suspend_data'?store:'',LMSSetValue:(k,v)=>{writes.push([k,v]);if(k==='cmi.suspend_data')store=v;return'true';},LMSCommit:()=> 'true'};
  Object.defineProperties(w.HTMLMediaElement.prototype,{duration:{get(){return 30;}},currentTime:{get(){return current;},set(n){current=n;}},paused:{get(){return paused;}}});
  w.HTMLMediaElement.prototype.play=function(){paused=false;this.dispatchEvent(new w.Event('play'));return Promise.resolve();};
  w.HTMLMediaElement.prototype.pause=function(){const change=!paused;paused=true;if(change)this.dispatchEvent(new w.Event('pause'));};
  w.postMessage=message=>messages.push(message);
 }});
 const w=dom.window,d=w.document,v=d.getElementById('video');v.dispatchEvent(new w.Event('loadedmetadata'));
 const tick=n=>{v.currentTime=n;v.dispatchEvent(new w.Event('timeupdate'));};
 const answer=n=>{d.querySelectorAll('input[name="answer"]')[n].checked=true;d.getElementById('answer').click();};
 const next=()=>d.getElementById('continue').click();
 return{dom,w,d,v,tick,answer,next,writes,messages,saved:()=>store};
}
function finish(t){t.tick(5);t.answer(1);t.next();t.tick(10);t.answer(0);t.answer(0);t.next();t.tick(30);t.v.dispatchEvent(new t.w.Event('ended'));}
let t=setup(ungraded);finish(t);
assert.equal(t.d.getElementById('feedback').parentNode.id,'panel','explanation belongs beside the video');
assert.equal(t.d.getElementById('video-load-status').parentNode.id,'panel','network feedback never reduces video height');
assert(!t.d.querySelector('.avatar #feedback'));
assert(!t.messages.some(m=>m.action==='result'),'ungraded never reports a score');
assert(!t.writes.some(([k])=>/score|lesson_status/.test(k)));
const completed=t.saved();t.dom.window.close();
t=setup(ungraded,completed);
assert(!t.d.getElementById('restart-video-quiz').hidden);
t.d.getElementById('restart-video-quiz').click();assert.equal(t.v.currentTime,0);
const config=JSON.parse(t.d.getElementById('video-quiz-data').textContent);
t.w.dispatchEvent(new t.w.MessageEvent('message',{source:t.w.parent,data:{type:'scormify-video-quiz-resume',key:config.key,state:Object.values(JSON.parse(completed).videoQuizzes)[0]}}));
t.tick(5);assert.equal(t.d.getElementById('question').textContent,'Primeira?');assert(!t.d.getElementById('answer').hidden);
t.answer(1);t.next();t.tick(10);assert.equal(t.d.getElementById('question').textContent,'Segunda?');assert(!t.d.getElementById('answer').hidden);
t.dom.window.close();
t=setup(graded);assert(t.d.getElementById('restart-video-quiz').hidden);finish(t);
assert.equal(t.messages.filter(m=>m.action==='result').length,1);
assert.equal(t.messages.find(m=>m.action==='result').score,50);
assert.match(t.d.getElementById('message').textContent,/50%/);
const evaluated=t.saved();t.dom.window.close();
t=setup(graded,evaluated);assert.equal(t.messages.find(m=>m.action==='result').score,50,'graded result resumes');
t.tick(5);assert(t.d.getElementById('answer').hidden,'rewind does not erase graded responses');
t.d.getElementById('restart-video-quiz').click();assert(t.messages.some(m=>m.action==='retry'));
t.tick(5);assert(!t.d.getElementById('answer').hidden,'explicit graded retry can recover a failed attempt');
t.dom.window.close();

const dom=new JSDOM('<iframe></iframe><iframe></iframe>',{url:'https://course.example',runScripts:'dangerously'}),w=dom.window;
w.eval(host);const [g,f]=w.document.querySelectorAll('iframe');let scores=[],retries=0;
const key='a'.repeat(20),freeKey='b'.repeat(20);
w.VideoQuizHost.bindFrame(g,{videoQuizConfig:{key,graded:true,checkpoints:[{},{}]}},score=>scores.push(score),()=>retries++);
w.VideoQuizHost.bindFrame(f,{videoQuizConfig:{key:freeKey,graded:false,checkpoints:[{},{}]}},()=>{throw Error('ungraded score accepted');});
function send(frame,msg){w.dispatchEvent(new w.MessageEvent('message',{source:frame.contentWindow,data:{type:'scormify-video-quiz',action:'result',key:frame===g?key:freeKey,correct:1,total:2,score:50,...msg}}));}
send(f,{});send(g,{score:99});send(f,{key});assert.deepEqual(scores,[],'reject free, forged score and wrong source');
send(g,{});assert.deepEqual(scores,[50]);send(g,{action:'retry'});assert.equal(retries,1);
dom.window.close();

// Actual classic SCORM player + result ledger, not a mocked grade callback.
const assets=path.resolve(__dirname,'../backend/services/export_assets');
function courseSession(document) {
 const dom=new JSDOM(fs.readFileSync(path.join(assets,'player_template.html'),'utf8'),{url:'https://course.example/index.html',runScripts:'outside-only'});
 const w=dom.window,values={'cmi.core.lesson_status':'incomplete','cmi.student_data.mastery_score':'80','cmi.suspend_data':'{}'};
 w.TextEncoder=TextEncoder;w.TextDecoder=TextDecoder;w.console={log(){},warn(){},error(){}};
 w.matchMedia=()=>({matches:false,addListener(){},addEventListener(){}});w.fetch=()=>new Promise(()=>{});
 w.HTMLMediaElement.prototype.pause=function(){};w.HTMLMediaElement.prototype.play=function(){return Promise.resolve();};
 w.API={LMSInitialize:()=> 'true',LMSGetValue:k=>values[k]||'',LMSSetValue:(k,v)=>{values[k]=v;return'true';},LMSCommit:()=> 'true',LMSFinish:()=> 'true'};
 w.eval(fs.readFileSync(path.join(assets,'scorm-api.js'),'utf8'));w.eval(host);w.eval(fs.readFileSync(path.join(assets,'video-quiz-viewport.js'),'utf8'));w.eval(fs.readFileSync(path.join(assets,'player.js'),'utf8'));
 const config=JSON.parse(/<script id="video-quiz-data" type="application\/json">([\s\S]*?)<\/script>/.exec(document)[1]);
 w.CoursePlayer.load({metadata:{title:'Video test'},slides:[{id:'s',title:'Slide',width:960,height:540,elements:[{id:'video',type:'html',x:0,y:0,width:960,height:540,videoQuizConfig:config,htmlContent:document}]}]});
 const frame=w.document.querySelector('iframe[data-video-quiz-key]');assert(frame,'classic player registers video frame');
 function send(action,correct=1){w.dispatchEvent(new w.MessageEvent('message',{source:frame.contentWindow,data:{type:'scormify-video-quiz',key:config.key,action,correct,total:2,score:correct*50}}));}
 return {dom,w,values,send};
}
let c=courseSession(graded);
assert.equal(c.w.ScormAPI.setComplete(),false,'pending graded video blocks completion');
c.send('result',1);assert.equal(c.w.ScormAPI.setComplete(),true);assert.equal(c.values['cmi.core.score.raw'],'50');assert.equal(c.values['cmi.core.lesson_status'],'failed');
c.send('retry');assert.equal(c.w.ScormAPI.setComplete(),false,'retry clears the pending result');
c.send('result',2);c.w.ScormAPI.setComplete();assert.equal(c.values['cmi.core.lesson_status'],'passed');c.dom.window.close();
c=courseSession(ungraded);c.send('result',2);assert.equal(c.values['cmi.core.score.raw'],undefined,'ungraded cannot report a course grade');c.w.ScormAPI.setComplete();assert.equal(c.values['cmi.core.lesson_status'],'completed');c.dom.window.close();
console.log('video quiz grading/replay/bridge/classic LMS checks passed');

// Single-page result recovery after its end card is already unlocked.
const spdom=new JSDOM('<iframe data-video-quiz-graded="true" data-video-quiz-key="'+key+'"></iframe>',{url:'https://course.example',runScripts:'outside-only'});
const sw=spdom.window;let spScores=[],spResults=[],savedState={};
sw.SCORM={api:{LMSGetValue:()=>JSON.stringify(savedState)},setScore:n=>spScores.push(n),saveSuspend:s=>{savedState=s;},setLocation(){},commit(){},complete:passed=>spResults.push(passed)};
sw.eval(fs.readFileSync(path.resolve(assets,'../sp_runtime/runtime.js'),'utf8').replace('__SECTIONS_INDEX__','[{"index":0,"title":"Video"}]').replace('__SCORM_MODE__','true'));
sw.SP.advance();assert.deepEqual(spResults,[],'pending graded video cannot complete singlepage');
sw.SP.recordVideoQuizResult(key,1,2);assert.equal(spScores.at(-1),50);assert.equal(spResults.at(-1),false);
sw.SP.retryVideoQuiz(key);assert(!savedState.quizScores['videoquiz:'+key]);
sw.SP.recordVideoQuizResult(key,2,2);assert.equal(spScores.at(-1),100);assert.equal(spResults.at(-1),true,'singlepage retake can recover failure without relocking sections');
spdom.window.close();

const vp=new JSDOM('<div id="wrapper"><div id="stage"><div class="slide-element"><iframe></iframe></div></div></div>',{runScripts:'outside-only'});
vp.window.eval(fs.readFileSync(path.join(assets,'video-quiz-viewport.js'),'utf8'));
const stage=vp.window.document.getElementById('stage'),wrapper=vp.window.document.getElementById('wrapper');
let rect={width:390,height:720};wrapper.getBoundingClientRect=()=>rect;
const slide={width:1920,height:820,elements:[{type:'html',x:0,y:0,width:1920,height:820,htmlContent:graded}]},original=JSON.stringify(slide);
assert(vp.window.VideoQuizViewport.fit(stage,wrapper,slide));assert.equal(stage.style.width,'378px');assert.equal(stage.style.transform,'none');assert.equal(stage.querySelector('.slide-element').style.width,'100%');
rect={width:1100,height:600};assert(vp.window.VideoQuizViewport.fit(stage,wrapper,slide));assert.equal(stage.style.width,'1088px');
assert.equal(JSON.stringify(slide),original,'responsive rendering never mutates authored geometry/questions');
assert(!vp.window.VideoQuizViewport.fit(stage,wrapper,{...slide,elements:[...slide.elements,{type:'text'}]}),'custom multi-element slides retain authored layout');
assert(!vp.window.VideoQuizViewport.fit(stage,wrapper,{...slide,annotations:[{}]}),'annotated canvases retain authored layout');
vp.window.close();
