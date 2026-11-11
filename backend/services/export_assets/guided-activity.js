(function(){'use strict';
var spec=JSON.parse(document.getElementById('guided-data').textContent),root=document.getElementById('guided-app'),answers={},texts=[],checks=[],step=0,order=[],notice='',good=false,connected=false,reviewed=false,saveTimer;
function make(tag,text,parent,cls){var n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;if(parent)parent.appendChild(n);return n;}
function button(text,fn,parent){var b=make('button',text,parent);b.type='button';b.onclick=fn;return b;}
function send(action,payload){window.parent.postMessage({type:'scormify-guided-action',id:spec.id,action:action,payload:payload},'*');}
function projectPayload(review){return {texts:texts,checks:checks,review:review===true};}
function exportLocal(){var lines=[spec.title,'Autoverificação, não correção automática.'];(spec.deliverables||[]).forEach((d,i)=>lines.push('\n'+d.title,texts[i]||'[Não preenchido]',d.criterion));var a=document.createElement('a'),url=URL.createObjectURL(new Blob([lines.join('\n')],{type:'text/plain;charset=utf-8'}));a.href=url;a.download='Meu_portfolio.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function saveProject(){reviewed=false;send('project',projectPayload(false));}
function render(){root.replaceChildren();make('h1',spec.title,root);make('p',spec.instructions,root,'brief');var body=make('section',undefined,root,'body');
 if(spec.kind==='project'){
  make('p','Suas respostas ficam neste navegador. Exporte o portfólio para guardar e entregar ao instrutor. No LMS, somente o resumo de progresso é retomado em outro dispositivo.',body,'note');
  spec.deliverables.forEach((d,i)=>{var box=make('section',undefined,body,'delivery');make('h2',(i+1)+'. '+d.title,box);make('p',d.prompt,box);var input=make('textarea',undefined,box);input.setAttribute('aria-label','Entrega '+(i+1));input.value=texts[i]||'';input.maxLength=10000;var count=make('small',(input.value.trim().length)+' / '+spec.minChars+' caracteres mínimos',box);input.oninput=()=>{texts[i]=input.value;count.textContent=input.value.trim().length+' / '+spec.minChars+' caracteres mínimos';saveProject();};make('p',d.criterion,box,'criterion');var label=make('label',undefined,box),check=make('input',undefined,label);check.type='checkbox';check.checked=!!checks[i];check.onchange=()=>{checks[i]=check.checked;saveProject();};label.appendChild(document.createTextNode(' Revisei esta entrega com o critério acima.'));});
 }else{
  var cards=make('div',undefined,body,'cards');spec.cards.forEach(c=>{var d=make('details',undefined,cards,'card');make('summary',c.front,d);make('p',c.back,d);});
  var a=spec.activity;
  if(a.type==='ordering'){
   if(!order.length)order=a.items.map((_,i)=>i).reverse();
   order.forEach((id,pos)=>{var row=make('div',undefined,body,'row order-item');make('strong',(pos+1)+'. '+a.items[id],row);var up=button('↑',()=>{[order[pos],order[pos-1]]=[order[pos-1],order[pos]];render();},row);up.disabled=pos===0;up.setAttribute('aria-label','Mover etapa para cima');var down=button('↓',()=>{[order[pos],order[pos+1]]=[order[pos+1],order[pos]];render();},row);down.disabled=pos===order.length-1;down.setAttribute('aria-label','Mover etapa para baixo');});
  }else if(a.type==='classification'||a.type==='matrix'){
   a.rows.forEach((r,i)=>{var row=make('div',undefined,body,'row'),label=make('label',r.text,row),select=make('select',undefined,row);select.id='class-'+i;label.htmlFor=select.id;var first=make('option','Selecione uma interpretação',select);first.value='';a.targets.forEach((t,j)=>{var o=make('option',t,select);o.value=String(j);});select.value=answers[i]===undefined?'':String(answers[i]);select.onchange=()=>{answers[i]=select.value;};});
  }else if(a.type==='decision'){
   var s=a.steps[step];if(s){make('h2','Decisão '+(step+1)+' de '+a.steps.length,body);make('p',s.prompt,body);s.options.forEach((v,i)=>{var b=button(v,()=>{answers[step]=i;render();},body);b.className='choice'+(answers[step]===i?' selected':'');b.setAttribute('aria-pressed',String(answers[step]===i));});}else make('p','Decisões resolvidas. Revise o feedback e confirme a prática.',body);
  }else if(a.type==='calculator'){
   a.rows.forEach((r,i)=>{var row=make('div',undefined,body,'row'),label=make('label',undefined,row),check=make('input',undefined,label);check.type='checkbox';check.checked=(answers.selected||[]).includes(i);check.onchange=()=>{var selected=new Set(answers.selected||[]);if(check.checked)selected.add(i);else selected.delete(i);answers.selected=Array.from(selected);};label.appendChild(document.createTextNode(' '+r.text+' · '+r.value+' '+a.unit+' · '+r.status));});var label=make('label','Total aceito ('+a.unit+')',body),input=make('input',undefined,label);input.type='number';input.step='any';input.className='calc-value';input.setAttribute('aria-label','Total aceito');input.value=answers.total||'';input.oninput=()=>answers.total=input.value;
  }
 }
 if(notice){var feedback=make('div',notice,body,'feedback'+(good?' good':''));feedback.setAttribute('role','status');}
 var actions=make('div',undefined,root,'actions');
 if(spec.kind==='project'){
  button('Exportar meu portfólio',()=>{if(connected)send('export');else exportLocal();},actions);
  button('Registrar autoverificação',()=>{clearTimeout(saveTimer);good=spec.deliverables.every((_,i)=>String(texts[i]||'').trim().length>=spec.minChars&&checks[i]===true);reviewed=good;notice=good?'Autoverificação registrada. Isto não é correção pedagógica do conteúdo.':'Preencha todas as entregas e confirme sua revisão.';send('project',projectPayload(good));render();},actions);
 }else{
  button('Conferir minha resposta',()=>{var a=spec.activity;if(a.type==='decision'&&step<a.steps.length){var s=a.steps[step];good=answers[step]===s.correct;notice=s.feedback;if(good)step++;if(step<a.steps.length){render();return;}}
   var payload=a.type==='ordering'?order:a.type==='calculator'?answers:Array.from({length:(a.rows||a.steps).length},(_,i)=>answers[i]);good=ScormifyGuidedCore.grade(spec,payload);notice=(good?'Prática concluída. ':'Revise e tente novamente. ')+a.feedback;if(good)send('practice',payload);render();},actions);
  button('Reiniciar prática',()=>{answers={};step=0;order=[];notice='';render();},actions);
 }
 make('p',connected?'Progresso integrado ao percurso.':'Prévia da atividade. Abra Visualizar ou a exportação para acompanhar o percurso completo.',root,'note');
}
window.addEventListener('message',e=>{if(e.source!==window.parent||e.data?.type!=='scormify-guided-state'||e.data.id!==spec.id)return;connected=true;var s=e.data.state||{};if(spec.kind==='project'){texts=s.project?.[spec.id]||texts;checks=s.checks?.[spec.id]||checks;reviewed=!!s.done?.[spec.id];}render();});
render();send('ready');[250,1000,2500].forEach(delay=>setTimeout(()=>{if(!connected)send('ready');},delay));window.addEventListener('pagehide',()=>{clearTimeout(saveTimer);if(spec.kind==='project')send('project',projectPayload(reviewed));});
})();
