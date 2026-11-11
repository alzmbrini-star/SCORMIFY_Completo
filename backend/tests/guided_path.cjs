const assert=require('node:assert/strict');
const {create,grade}=require('../services/export_assets/guided-core.js');
const plan={id:'p',fingerprint:'v1',unitPassingScore:100,passingScore:80,projectRequired:true,slides:[
 {id:'read',index:0,stage:'learn'}, {id:'original',index:1,stage:'explore'},
 {id:'practice',index:2,stage:'practice',activity:{id:'a',activity:{type:'ordering',items:['Prepare','Execute','Review'],feedback:'Review'}}},
 {id:'assessment',index:3,stage:'assessment',activity:{id:'b'}},
 {id:'project',index:4,stage:'project',activity:{id:'c',minChars:60,deliverables:[{title:'Plan'}]}},
 {id:'final',index:5,stage:'final',activity:{id:'d'}}]};
const engine=create(plan);assert.equal(engine.view().complete,false);
engine.act('final','assessment',100);assert.equal(engine.view().complete,false,'Final score cannot bypass unit work');
engine.act('read','confirm');engine.act('original','confirm');
assert.equal(engine.act('practice','practice',[2,1,0]).ok,false);
assert.equal(engine.act('practice','practice',[0,1,2]).ok,true);
engine.act('assessment','assessment',50);assert.equal(engine.view().slides[3].done,false);
engine.act('assessment','assessment',100);engine.act('assessment','assessment',0);
assert.equal(engine.view().state.scores.b,100,'Best score survives a failed retry');
assert.equal(engine.view().state.last.b,0);
engine.act('project','project',{texts:['x'.repeat(60)],checks:[false],review:true});assert.equal(engine.view().complete,false);
engine.act('project','project',{texts:['x'.repeat(60)],checks:[true],review:true});assert.equal(engine.view().complete,true);
engine.act('read','note','Private essay with sensitive details');
const compact=engine.compact();assert(!JSON.stringify(compact).includes('Private'));assert(!JSON.stringify(compact).includes('xxxxxxxx'));
const resume=create(plan);assert(resume.restore(compact));assert(resume.view().complete);assert.deepEqual(resume.view().state.project,{});
assert.equal(resume.restore({...compact,f:'different'}),false);assert.equal(resume.restore({...compact,d:{}}),false);
engine.act('project','project',{texts:['Changed'],checks:[true],review:false});assert.equal(engine.view().complete,false);
assert.equal(grade({activity:{type:'classification',rows:[{correct:0}]}},[null]),false);
assert.equal(grade({activity:{type:'matrix',rows:[{correct:0},{correct:1}]}},[0,1]),true);
assert.equal(grade({activity:{type:'decision',steps:[{correct:1},{correct:0}]}},[1,0]),true);
assert.equal(grade({activity:{type:'calculator',rows:[{value:20,accepted:true},{value:10,accepted:false},{value:15,accepted:true}]}},{selected:[2,0],total:'35'}),true);
assert.equal(grade({activity:{type:'calculator',rows:[{value:20,accepted:true}]}},{selected:[0],total:'NaN'}),false);
const long={...plan,slides:Array.from({length:1300},(_,i)=>({id:'s'+i,index:i,stage:'learn'}))};
const many=create(long);long.slides.forEach(s=>many.act(s.id,'confirm'));
assert(JSON.stringify(many.compact()).length<1000,'Compact progress leaves room in SCORM 1.2');
console.log('Guided path progress, retries, privacy and five finite practices verified.');
