// Numeric state kernel. Theme, scene and layout remain generated for the topic.
(() => {
  'use strict';
  const model=__CAUSAL_MODEL__, listeners=new Set();
  const timers=new Map(),frames=new Set();
  const nativeTimeout=window.setTimeout.bind(window),nativeInterval=window.setInterval.bind(window),nativeClearTimeout=window.clearTimeout.bind(window),nativeClearInterval=window.clearInterval.bind(window);
  const nativeFrame=window.requestAnimationFrame.bind(window),nativeCancelFrame=window.cancelAnimationFrame.bind(window);
  window.setTimeout=(fn,delay,...args)=>{if(typeof fn!=='function')throw Error('Callback obrigatório');const id=nativeTimeout(()=>{timers.delete(id);fn(...args);},delay);timers.set(id,'timeout');return id;};
  window.setInterval=(fn,delay,...args)=>{if(typeof fn!=='function')throw Error('Callback obrigatório');const id=nativeInterval(fn,delay,...args);timers.set(id,'interval');return id;};
  window.clearTimeout=id=>{timers.delete(id);nativeClearTimeout(id);};
  window.clearInterval=id=>{timers.delete(id);nativeClearInterval(id);};
  window.requestAnimationFrame=fn=>{const id=nativeFrame(time=>{frames.delete(id);fn(time);});frames.add(id);return id;};
  window.cancelAnimationFrame=id=>{frames.delete(id);nativeCancelFrame(id);};
  function cancelAll(){timers.forEach((kind,id)=>(kind==='interval'?nativeClearInterval:nativeClearTimeout)(id));timers.clear();frames.forEach(nativeCancelFrame);frames.clear();}
  document.addEventListener('click',event=>{if(event.target?.closest?.('[data-sim-reset]'))cancelAll();},true);
  let inputs=Object.fromEntries(model.inputs.map(i=>[i.id,i.initial])),history=[];
  const clone=value=>JSON.parse(JSON.stringify(value));
  function evaluate(expr) {
    if(typeof expr==='number')return expr;
    if(Object.prototype.hasOwnProperty.call(expr,'input'))return inputs[expr.input];
    const args=expr.args.map(evaluate);
    const value=expr.op==='add'?args.reduce((a,b)=>a+b,0):expr.op==='mul'?args.reduce((a,b)=>a*b,1):expr.op==='min'?Math.min(...args):expr.op==='max'?Math.max(...args):expr.op==='sub'?args.slice(1).reduce((a,b)=>a-b,args[0]):args.slice(1).reduce((a,b)=>{if(Math.abs(b)<1e-9)throw Error('Divisão por zero');return a/b;},args[0]);
    if(!Number.isFinite(value)||Math.abs(value)>1e12)throw Error('Resultado fora do intervalo seguro');
    return value;
  }
  function snapshot(){return {inputs:clone(inputs),outputs:Object.fromEntries(model.outputs.map(o=>[o.id,evaluate(o.expression)])),history:clone(history)};}
  function notify(){const state=snapshot();listeners.forEach(fn=>fn(clone(state)));return state;}
  window.ScormifyModel=Object.freeze({
    definition:clone(model),getState:snapshot,
    setInput(id,value){
      const input=model.inputs.find(i=>i.id===id);
      if(!input||!Number.isFinite(Number(value)))throw Error('Entrada inválida');
      const before=snapshot();const previous=inputs[id];
      inputs[id]=Math.min(input.max,Math.max(input.min,Number(value)));
      let after;
      try{after=snapshot();}catch(error){inputs[id]=previous;throw error;}
      history.push({input:id,from:previous,to:inputs[id],before:before.outputs,after:after.outputs});
      if(history.length>200)history.shift();
      return notify();
    },
    reset(){cancelAll();inputs=Object.fromEntries(model.inputs.map(i=>[i.id,i.initial]));history=[];return notify();},
    subscribe(fn){listeners.add(fn);fn(snapshot());return()=>listeners.delete(fn);}
  });
})();
