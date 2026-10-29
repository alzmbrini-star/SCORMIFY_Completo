/* Pure scheduling operations. No network, generated code, timers or DOM. */
function createPlanningEngine(definition) {
  'use strict';
  const clone = value => JSON.parse(JSON.stringify(value));
  const spec = clone(definition), listeners = new Set();
  let tasks, eventActive, history, snapshots, report, serial;
  const baseline = new Map(spec.tasks.map(task => [task.id, task]));
  function initial() {
    tasks = spec.tasks.map(task => Object.assign({}, clone(task), {start:null, estimated:task.duration, original:true}));
    eventActive=false;history=[];snapshots=[];report=null;serial=0;
  }
  initial();
  function metrics() {
    const scheduled=tasks.filter(task=>task.start!==null), byId=new Map(tasks.map(task=>[task.id,task]));
    const violations=[], affected=new Set();let overload=0, late=0, quality=0;
    const usage=Object.fromEntries(spec.resources.map(resource=>[resource.id,Array(spec.horizon).fill(0)]));
    let load=0;
    const eventCapacity=spec.resources.find(resource=>resource.id===spec.event.resourceId).capacity;
    if(eventActive) for(let slot=spec.event.start;slot<spec.event.start+spec.event.duration;slot++)usage[spec.event.resourceId][slot]+=eventCapacity;
    scheduled.forEach(task=>{
      const end=task.start+task.duration;
      load+=task.duration;
      for(let slot=task.start;slot<Math.min(end,spec.horizon);slot++)usage[task.resourceId][slot]++;
      if(end>task.due){late++;affected.add(task.id);violations.push(task.label+': termina em '+end+', depois do prazo '+task.due+'.');}
      if(end>spec.horizon){affected.add(task.id);violations.push(task.label+': ultrapassa o horizonte do planejamento.');}
      if(task.duration<task.estimated){quality++;affected.add(task.id);violations.push(task.label+': duração abaixo da estimativa mínima; risco de qualidade.');}
      task.dependencies.forEach(id=>{const dep=byId.get(id);if(!dep || dep.start===null || dep.start+dep.duration>task.start){affected.add(task.id);violations.push(task.label+': precisa começar após '+(dep?dep.label:id)+'.');}});
    });
    spec.resources.forEach(resource=>{
      usage[resource.id].forEach((count,slot)=>{
        if(count>resource.capacity){
          overload+=count-resource.capacity;
          violations.push(resource.label+': capacidade excedida no intervalo '+slot+'–'+(slot+1)+'.');
          scheduled.filter(task=>task.resourceId===resource.id && task.start<=slot && task.start+task.duration>slot).forEach(task=>affected.add(task.id));
        }
      });
    });
    const required=tasks.filter(task=>task.original), placed=required.filter(task=>task.start!==null);
    const totalWeight=spec.tasks.reduce((sum,task)=>sum+task.priority,0);
    const validWeight=required.filter(task=>task.start!==null && !affected.has(task.id)).reduce((sum,task)=>sum+baseline.get(task.id).priority,0);
    const coverage=Math.round(placed.length/spec.tasks.length*100), score=Math.round(validWeight/totalWeight*100);
    const capacity=spec.resources.reduce((sum,resource)=>sum+resource.capacity*spec.horizon,0)-(eventActive?eventCapacity*spec.event.duration:0);
    const success=coverage===100 && !violations.length && eventActive;
    return {coverage,score,late,overload,quality,load,usage,violations,success,
      utilization:Math.round(load/capacity*100),placed:placed.length,required:spec.tasks.length,
      valid:required.filter(task=>task.start!==null && !affected.has(task.id)).length};
  }
  function state() {return clone({tasks,eventActive,history,snapshots,report,metrics:metrics()});}
  function notify() {const value=state();listeners.forEach(listener=>listener(clone(value)));return value;}
  function change(action, operation) {
    const before=metrics();operation();report=null;const after=metrics();
    history.push({action,before:{score:before.score,late:before.late,overload:before.overload,coverage:before.coverage},
      after:{score:after.score,late:after.late,overload:after.overload,coverage:after.coverage}});
    if(history.length>100)history.shift();
    notify();return {ok:true,message:action+'. Viabilidade: '+after.score+'%. '+(after.violations[0]||'Sem conflitos entre as tarefas alocadas.')};
  }
  const fail=message=>({ok:false,message});
  const api={
    getState:state,
    subscribe(listener){listeners.add(listener);listener(state());return ()=>listeners.delete(listener);},
    updateTask(id,patch){
      const task=tasks.find(item=>item.id===id);if(!task)return fail('Selecione uma tarefa existente.');
      if(Object.keys(patch).some(key=>!['start','duration','resourceId'].includes(key)))return fail('Os dados de referência do caso não podem ser alterados.');
      if('start' in patch && patch.start!==null && (!Number.isInteger(patch.start)||patch.start<0||patch.start>=spec.horizon))return fail('Informe um início inteiro de 0 a '+(spec.horizon-1)+'.');
      if('duration' in patch && (!Number.isInteger(patch.duration)||patch.duration<1||patch.duration>spec.horizon))return fail('Informe uma duração inteira de 1 a '+spec.horizon+'.');
      if('resourceId' in patch && !task.allowedResources.includes(patch.resourceId))return fail('Esse recurso não está habilitado para a tarefa.');
      return change('Alterou '+task.label,()=>Object.assign(task,patch));
    },
    removeTask(id){return api.updateTask(id,{start:null});},
    addTask(raw){
      if(tasks.length>=20)return fail('Limite de 20 tarefas nesta atividade.');
      if(!raw || typeof raw.label!=='string'||!raw.label.trim()||raw.label.length>100)return fail('Informe um nome de tarefa de até 100 caracteres.');
      if(!Number.isInteger(raw.duration)||raw.duration<1||raw.duration>spec.horizon||!Number.isInteger(raw.due)||raw.due<1||raw.due>spec.horizon)return fail('Duração e prazo precisam de valores inteiros dentro do calendário.');
      const id='extra_'+(++serial);
      return change('Adicionou demanda extra: '+raw.label.trim(),()=>tasks.push({id,label:raw.label.trim(),description:'Demanda adicional definida pelo aluno; não substitui as tarefas obrigatórias do caso.',duration:raw.duration,estimated:raw.duration,due:raw.due,priority:1,
        dependencies:[],resourceId:spec.resources[0].id,allowedResources:spec.resources.map(resource=>resource.id),start:null,original:false}));
    },
    revealEvent(){
      if(eventActive)return fail('O imprevisto já está ativo.');
      if(tasks.filter(task=>task.original&&task.start!==null).length<2)return fail('Aloque pelo menos duas tarefas do caso antes de receber o imprevisto.');
      return change('Recebeu o imprevisto: '+spec.event.title,()=>{eventActive=true;});
    },
    saveSnapshot(){
      if(!tasks.some(task=>task.start!==null))return fail('Aloque uma tarefa antes de guardar uma versão.');
      const saved={id:'version_'+(++serial),label:'Versão '+serial,tasks:clone(tasks),eventActive,metrics:metrics()};
      snapshots.push(saved);if(snapshots.length>5)snapshots.shift();notify();return {ok:true,message:'Versão registrada na memória desta atividade. Ela será apagada ao reiniciar ou fechar o conteúdo.'};
    },
    compare(id){
      const saved=snapshots.find(item=>item.id===id);if(!saved)return null;
      const current=metrics();return {score:current.score-saved.metrics.score,late:current.late-saved.metrics.late,overload:current.overload-saved.metrics.overload};
    },
    restoreSnapshot(id){
      const saved=snapshots.find(item=>item.id===id);if(!saved)return fail('Escolha uma versão existente.');
      // The interruption is knowledge already revealed: restoring cannot erase it.
      return change('Restaurou '+saved.label,()=>{tasks=clone(saved.tasks);eventActive=eventActive||saved.eventActive;});
    },
    finalize(){
      const value=metrics();
      if(!eventActive)return fail('Receba e analise o imprevisto antes da análise final.');
      if(!value.placed)return fail('O cronograma está vazio. Aloque tarefas para analisar.');
      report={outcome:value.success?'Plano viável':value.score>=50?'Plano parcialmente viável':'Plano precisa de revisão',success:value.success,score:value.score,
        notes:[value.placed+'/'+value.required+' tarefas do caso alocadas.',value.valid+' tarefas do caso respeitam prazo, dependências, capacidade e estimativa.',
          value.late+' tarefas atrasadas; '+value.overload+' unidades de sobrecarga; '+value.quality+' riscos de qualidade.'],
        causes:value.violations.slice(0,8),actions:history.slice(-6).map(item=>item.action)};
      notify();return {ok:true,message:report.outcome+'. Você pode continuar ajustando e analisar novamente.'};
    },
    reset(){initial();notify();return {ok:true,message:'Estado inicial restaurado. Histórico e versões foram limpos.'};}
  };
  return Object.freeze(api);
}
if(typeof module!=='undefined' && module.exports)module.exports={createPlanningEngine};
