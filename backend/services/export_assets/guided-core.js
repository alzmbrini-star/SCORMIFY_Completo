(function(root){'use strict';
function fresh(){return {v:1,done:{},scores:{},last:{},attempts:{},project:{},checks:{},notes:{}};}
function grade(spec,answer){
 if(!answer||typeof answer!=='object')return false;
 var a=spec.activity||{},same=(x,y)=>JSON.stringify(x)===JSON.stringify(y);
 if(a.type==='ordering')return same(answer,a.items.map((_,i)=>i));
 if(a.type==='classification'||a.type==='matrix')return Array.isArray(answer)&&answer.length===a.rows.length&&a.rows.every((r,i)=>answer[i]!==null&&Number(answer[i])===r.correct&&answer[i]!==''&&answer[i]!==undefined);
 if(a.type==='decision')return Array.isArray(answer)&&answer.length===a.steps.length&&a.steps.every((s,i)=>answer[i]!==null&&Number(answer[i])===s.correct&&answer[i]!==''&&answer[i]!==undefined);
 if(a.type==='calculator'){var expected=a.rows.map((r,i)=>r.accepted?i:-1).filter(i=>i>=0),total=expected.reduce((sum,i)=>sum+a.rows[i].value,0);return same((answer.selected||[]).slice().sort((x,y)=>x-y),expected)&&String(answer.total).trim()!==''&&Math.abs(Number(answer.total)-total)<.000001;}
 return false;
}
function create(plan,seed){
 var state=fresh();if(seed&&seed.v===1)Object.assign(state,JSON.parse(JSON.stringify(seed)));
 var slides=plan.slides||[],byId=Object.fromEntries(slides.map(s=>[s.id,s]));
 function done(s){
  if(!s)return false;var a=s.activity;
  if(s.stage==='reinforcement')return true;
  if(s.stage==='learn'||s.stage==='explore')return plan.confirmReading===false||!!state.done[s.id];
  if(s.stage==='practice')return !!(a&&state.done[a.id]);
  if(s.stage==='assessment')return !!a&&state.scores[a.id]!==undefined&&state.scores[a.id]>=plan.unitPassingScore;
  if(s.stage==='final')return !!a&&state.scores[a.id]!==undefined&&state.scores[a.id]>=plan.passingScore;
  if(s.stage==='project')return plan.projectRequired===false||!!(a&&state.done[a.id]);
  return true;
 }
 function view(){var rows=slides.map(s=>({id:s.id,index:s.index,title:s.title,unitId:s.unitId,stage:s.stage,done:done(s)}));var gates=rows.filter(s=>s.stage!=='reinforcement');return {state:JSON.parse(JSON.stringify(state)),slides:rows,pending:gates.filter(s=>!s.done),complete:gates.length>0&&gates.every(s=>s.done),progress:gates.length?Math.round(gates.filter(s=>s.done).length/gates.length*100):0};}
 function action(id,kind,payload){var s=byId[id];if(!s)return {ok:false};var a=s.activity;
  if(kind==='confirm'&&['learn','explore'].includes(s.stage))state.done[id]=true;
  else if(kind==='practice'&&a&&s.stage==='practice'){if(!grade(a,payload))return {ok:false,feedback:a.activity.feedback};state.done[a.id]=true;}
  else if(kind==='assessment'&&a&&['assessment','final'].includes(s.stage)){if(typeof payload!=='number'||!Number.isFinite(payload)||payload<0||payload>100)return {ok:false};state.last[a.id]=payload;state.scores[a.id]=Math.max(state.scores[a.id]||0,payload);state.attempts[a.id]=(state.attempts[a.id]||0)+1;}
  else if(kind==='project'&&a&&s.stage==='project'){
    if(!payload||!Array.isArray(payload.texts)||!Array.isArray(payload.checks))return {ok:false};
    state.project[a.id]=a.deliverables.map((_,i)=>String(payload.texts[i]||'').slice(0,10000));state.checks[a.id]=a.deliverables.map((_,i)=>payload.checks[i]===true);
    state.done[a.id]=payload.review===true&&state.project[a.id].every((t,i)=>t.trim().length>=a.minChars&&state.checks[a.id][i]);
  }else if(kind==='note'){state.notes[s.unitId||id]=String(payload||'').slice(0,5000);}
  else return {ok:false};return {ok:true,view:view()};
 }
 function compact(){var rows=view().slides,bits='',scores=[];for(var i=0;i<rows.length;i+=4){var value=0;for(var j=0;j<4;j++)if(rows[i+j]?.done)value|=1<<j;bits+=value.toString(16);}slides.forEach((s,i)=>{if(s.activity&&state.scores[s.activity.id]!==undefined)scores.push([i,state.scores[s.activity.id]]);});return {v:2,f:plan.fingerprint,d:bits,s:scores};}
 function restore(raw){if(!raw||![1,2].includes(raw.v)||raw.f!==plan.fingerprint||!Array.isArray(raw.s))return false;if(raw.v===1&&!Array.isArray(raw.d)||raw.v===2&&(typeof raw.d!=='string'||!/^[0-9a-f]*$/.test(raw.d)))return false;var local=state;state=fresh();state.project=local.project;state.checks=local.checks;state.notes=local.notes;var indices=raw.v===1?raw.d:slides.map((_,i)=>(parseInt(raw.d[Math.floor(i/4)]||'0',16)&(1<<(i%4)))?i:-1);indices.forEach(i=>{var s=Number.isInteger(i)&&slides[i];if(s)state.done[s.activity?s.activity.id:s.id]=true;});var scores=raw.v===1?raw.s.map((v,i)=>[i,v]):raw.s;scores.forEach(pair=>{if(!Array.isArray(pair))return;var i=pair[0],v=pair[1],s=Number.isInteger(i)&&slides[i];if(s&&s.activity&&typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=100)state.scores[s.activity.id]=v;});return true;}
 return {view:view,act:action,compact:compact,restore:restore};
}
root.ScormifyGuidedCore={create:create,grade:grade,fresh:fresh};if(typeof module!=='undefined'&&module.exports)module.exports=root.ScormifyGuidedCore;
})(typeof window!=='undefined'?window:globalThis);
