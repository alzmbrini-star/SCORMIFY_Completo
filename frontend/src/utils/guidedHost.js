(function(root){'use strict';
function mount(plan,options){
 options=options||{};var engine=null,key='',storageOK=true,lmsOK=true,current=0,timer=null,disposed=false,toolbar=document.createElement('div'),dialog=document.createElement('dialog'),warning='';
 toolbar.id='guided-toolbar';dialog.className='guided-dialog';dialog.setAttribute('aria-label','Meu percurso guiado');(options.container||document.body).appendChild(dialog);
 var controls=document.getElementById('controls');if(options.container)options.container.appendChild(toolbar);else if(controls)controls.parentNode.insertBefore(toolbar,controls);else document.body.appendChild(toolbar);
 function api(){try{return !options.preview&&root.ScormAPI?.isInitialized?.()?root.ScormAPI.getAPI():null;}catch(_){return null;}}
 function init(){var lms=api(),learner='local';try{if(lms){learner=String(lms.LMSGetValue('cmi.core.student_id')||'anonymous');var threshold=Number(lms.LMSGetValue('cmi.student_data.mastery_score'));if(Number.isFinite(threshold)&&threshold>plan.passingScore&&threshold<=100)plan.passingScore=threshold;}}catch(_){}var nextKey=(options.preview?'guided-preview:':'guided-course:')+plan.id+':'+plan.fingerprint+':'+learner;if(engine&&key===nextKey)return;key=nextKey;var saved=null;try{saved=JSON.parse(localStorage.getItem(key)||'null');}catch(_){storageOK=false;}engine=root.ScormifyGuidedCore.create(plan,saved);
  if(lms){try{var all=JSON.parse(lms.LMSGetValue('cmi.suspend_data')||'{}');engine.restore(all.guidedPath);}catch(_){}}
 }
 function persist(){init();var view=engine.view();try{localStorage.setItem(key,JSON.stringify(view.state));storageOK=true;}catch(_){storageOK=false;}
  var lms=api();if(lms){try{var raw=lms.LMSGetValue('cmi.suspend_data')||'{}',all=JSON.parse(raw);if(!all||typeof all!=='object'||Array.isArray(all))throw Error('Formato de retomada incompatível');all.guidedPath=engine.compact();var value=JSON.stringify(all);if(new TextEncoder().encode(value).length>3800)throw Error('Resumo de retomada cheio');lmsOK=String(lms.LMSSetValue('cmi.suspend_data',value))==='true'&&String(lms.LMSCommit(''))==='true';}catch(_){lmsOK=false;}}
  if(!storageOK)warning='O navegador não conseguiu guardar os textos. Exporte o portfólio antes de sair.';else if(!lmsOK)warning='O LMS não confirmou a retomada do percurso. Mantenha esta janela aberta e exporte o portfólio.';else warning='';
  render();options.onChange?.(view);document.dispatchEvent(new CustomEvent('scormify-guided-change',{detail:{progress:view.progress}}));return lms?lmsOK:storageOK;
 }
 function element(tag,text,parent){var n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(parent)parent.appendChild(n);return n;}
 function button(label,fn,parent){var b=element('button',label,parent);b.type='button';b.onclick=fn;return b;}
 function navigate(index){dialog.close();if(options.navigate)options.navigate(index);else if(root.CoursePlayer)root.CoursePlayer.goTo(index);else root.Player?.goTo(index);}
 function open(title){dialog.replaceChildren();element('h2',title,dialog);button('Fechar',()=>dialog.close(),dialog);if(!dialog.open)dialog.showModal();}
 function portfolio(){init();var s=engine.view().state,lines=['Meu portfólio · '+(plan.title||'Percurso guiado'),'Autoverificação: não substitui correção do instrutor.',''];plan.slides.forEach(slide=>{var a=slide.activity;if(a?.kind==='project')a.deliverables.forEach((d,i)=>lines.push(d.title,s.project[a.id]?.[i]||'[Não preenchido]','Critério: '+d.criterion,'Revisão declarada: '+(s.checks[a.id]?.[i]?'sim':'não'),''));});plan.units.forEach(u=>lines.push('Anotações · '+u.title,s.notes[u.id]||'[Sem anotações]',''));var url=URL.createObjectURL(new Blob([lines.join('\n')],{type:'text/plain;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='Meu_portfolio.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 function showProgress(pendingOnly){init();var v=engine.view();open(pendingOnly?'O que falta concluir':'Meu percurso guiado');if(warning)element('p',warning,dialog).className='guided-hint';element('p',v.progress+'% das etapas concluídas. Você pode revisar e tentar novamente. A melhor nota é preservada.',dialog);
  plan.units.forEach(u=>{var rows=v.slides.filter(s=>s.unitId===u.id&&s.stage!=='reinforcement');if(!rows.length||pendingOnly&&rows.every(s=>s.done))return;var section=element('section',undefined,dialog);element('h3',u.title,section);rows.forEach(s=>{if(pendingOnly&&s.done)return;var row=element('div',undefined,section);row.className='guided-row';element('span',(s.done?'✓ ':'○ ')+s.title,row);button('Abrir',()=>navigate(s.index),row);});});
  v.slides.filter(s=>!s.unitId&&['project','final'].includes(s.stage)).forEach(s=>{if(pendingOnly&&s.done)return;var row=element('div',undefined,dialog);row.className='guided-row';element('span',(s.done?'✓ ':'○ ')+s.title,row);button('Abrir',()=>navigate(s.index),row);});button('Exportar meu portfólio',portfolio,dialog);element('p','Textos e anotações ficam neste navegador. O LMS guarda somente o resumo de progresso; não envia as entregas ao instrutor.',dialog);
 }
 function notes(){init();var slide=plan.slides.find(s=>s.index===current),unit=slide?.unitId||plan.units[0]?.id;open('Minhas anotações');var area=element('textarea',undefined,dialog);area.setAttribute('aria-label','Anotações da unidade');area.value=engine.view().state.notes[unit]||'';area.maxLength=5000;area.oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{engine.act(slide?.id||plan.slides[0].id,'note',area.value);persist();},500);};button('Guardar anotações',()=>{clearTimeout(timer);engine.act(slide?.id||plan.slides[0].id,'note',area.value);persist();dialog.close();},dialog);button('Exportar portfólio',portfolio,dialog);}
 function render(){if(disposed)return;init();var view=engine.view(),slide=plan.slides.find(s=>s.index===current);toolbar.replaceChildren();element('span',(options.preview?'Prévia · ':'')+(slide?slide.title:'Percurso guiado')+' · '+view.progress+'%',toolbar);var actions=element('div',undefined,toolbar);actions.className='guided-toolbar-actions';
  if(slide&&['learn','explore'].includes(slide.stage)&&plan.confirmReading!==false){var completed=view.slides.find(s=>s.id===slide.id)?.done;button(completed?'✓ Confirmado':slide.stage==='learn'?'Confirmar leitura':'Conferi a referência',()=>{engine.act(slide.id,'confirm');persist();},actions);}
  if(slide?.stage==='explore'){var image=document.querySelector('#slide-container img');if(image)button('Ampliar imagem',()=>{open('Referência visual');var img=element('img',undefined,dialog);img.src=image.src;img.alt=image.alt||'Imagem original da unidade';},actions);}
  button('Meu percurso',()=>showProgress(false),actions);button('Anotações',notes,actions);
 }
 function frame(event,id){return Array.from(document.querySelectorAll('iframe[data-guided-id]')).find(f=>f.contentWindow===event.source&&f.getAttribute('data-guided-id')===id);}
 function onMessage(event){var m=event.data;if(!m||typeof m!=='object'||typeof m.id!=='string'||!frame(event,m.id))return;var slide=plan.slides.find(s=>s.activity?.id===m.id);if(!slide)return;init();
  if(m.type==='scormify-guided-assessment-result'&&['assessment','final'].includes(slide.stage)){if(engine.act(slide.id,'assessment',m.score).ok){if(slide.stage==='final'&&api())root.ScormAPI.recordAssessment(m.id,engine.view().state.scores[m.id]);persist();}return;}
  if(m.type!=='scormify-guided-action')return;
  if(m.action==='ready'){event.source.postMessage({type:'scormify-guided-state',id:m.id,state:engine.view().state},'*');return;}
  if(m.action==='export'){portfolio();return;}
  if(['practice','project'].includes(m.action)&&engine.act(slide.id,m.action,m.payload).ok)persist();
 }
 root.addEventListener('message',onMessage);
 var instance={slide(index){current=index;render();},canComplete(){init();return engine.view().complete;},showPending(){showProgress(true);},state(){init();return engine.view();},slideState(id){init();return engine.view().slides.find(s=>s.id===id);},persist:persist,destroy(){disposed=true;clearTimeout(timer);root.removeEventListener('message',onMessage);toolbar.remove();dialog.remove();}};
 render();return instance;
}
root.mountScormifyGuided=mount;var script=document.getElementById('guided-path-plan');if(script){var plan=JSON.parse(script.textContent);document.addEventListener('DOMContentLoaded',()=>{root.ScormifyGuided=mount(plan);});}
})(typeof window!=='undefined'?window:globalThis);
