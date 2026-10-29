/* Trusted scene graph. Reads rule state; never writes logical variables. */
export function ruleVisualRuntime() {
  'use strict';
  if (document.getElementById('rule-visual')) return;
  var plan=document.getElementById('scormify-simulator-plan'),data;
  try { data=JSON.parse(plan.textContent); } catch (_) { return; }
  if (!data || !Array.isArray(data.variables) || !Array.isArray(data.actions)) return;
  var anchor=document.getElementById('sceneDescription');if(!anchor)return;
  var ns='http://www.w3.org/2000/svg',visual=data.visual,authored=visual&&visual.version===1&&Array.isArray(visual.nodes)&&visual.nodes.length<=100;
  function node(tag,text){var el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;}
  function svg(tag){return document.createElementNS(ns,tag);}
  function color(value){return typeof value==='string'&&/^(#[0-9a-fA-F]{6}|none)$/.test(value)?value:'#dbeafe';}
  function evalExpr(expr,state){
    if(typeof expr==='boolean'||typeof expr==='number')return expr;
    if(!expr||typeof expr!=='object')return false;
    if(Object.prototype.hasOwnProperty.call(expr,'var'))return state[expr.var];
    var a=(expr.args||[]).map(function(e){return evalExpr(e,state);});
    switch(expr.op){case'eq':return a[0]===a[1];case'ne':return a[0]!==a[1];case'lt':return a[0]<a[1];case'le':return a[0]<=a[1];case'gt':return a[0]>a[1];case'ge':return a[0]>=a[1];case'all':return a.every(Boolean);case'any':return a.some(Boolean);case'not':return!a[0];case'add':return a[0]+a[1];case'sub':return a[0]-a[1];case'mul':return a[0]*a[1];case'min':return Math.min.apply(Math,a);case'max':return Math.max.apply(Math,a);default:return false;}
  }
  function interpolate(b,state){var t=(state[b.var]-b.input[0])/(b.input[1]-b.input[0]);return b.output[0]+Math.max(0,Math.min(1,t))*(b.output[1]-b.output[0]);}
  function textValue(value,state){return String(value||'').slice(0,100).replace(/\{([a-z][a-z0-9_]*)\}/g,function(_,key){return Object.prototype.hasOwnProperty.call(state,key)?String(state[key]):'?';});}
  var figure=node('figure');figure.id='rule-visual';figure.className='sim-rule-visual';figure.dataset.visualMode=authored?'illustrated':'conceptual';
  var picture=svg('svg');picture.setAttribute('viewBox','0 0 800 450');picture.setAttribute('preserveAspectRatio','xMidYMid meet');picture.setAttribute('role','group');
  var title=svg('title'),desc=svg('desc');title.textContent=authored?visual.title:'Mapa visual dos estados';desc.textContent=authored?visual.description:((data.visualNotice||'')+' Diagrama conceitual: as formas mostram os estados reais e suas mudanças. Não é uma representação física do ambiente.').trim();picture.appendChild(title);picture.appendChild(desc);picture.setAttribute('aria-label',title.textContent);figure.dataset.visualDescription=desc.textContent;
  picture.style.background=authored?color(visual.background):'#102a43';picture.style.fontFamily='system-ui,sans-serif';figure.appendChild(picture);
  var caption=node('figcaption');caption.className='sim-visual-caption';figure.appendChild(caption);anchor.parentNode.insertBefore(figure,anchor);
  var style=node('style');style.id='rule-visual-style';style.textContent='.sim-rule-visual{margin:0;display:flex;flex-direction:column;min-width:0;min-height:0;flex:1;overflow:hidden}.sim-rule-visual>svg{display:block;width:100%;flex:1;min-height:0;border:1px solid #59768f;border-radius:10px}.sim-dialog-body .sim-rule-visual{height:min(65vh,520px);min-height:200px}.sim-visual-caption{font:calc(14px * var(--sim-ui,1))/1.35 system-ui,sans-serif;color:#dceafb;padding-top:6px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.sim-rule-visual [role="button"]{cursor:pointer}.sim-rule-visual [aria-disabled="true"]{cursor:not-allowed}.sim-rule-visual [role="button"]:focus-visible{outline:3px solid #fbbf24;outline-offset:4px}.sim-rule-visual [data-visual-changed="true"]{filter:drop-shadow(0 0 5px #7dd3fc)}';document.head.appendChild(style);
  var entries=[],elements=Object.create(null),frame=null,initial=true,lastStep=0;
  var propertyNames={strokeWidth:'stroke-width',fontSize:'font-size',fontWeight:'font-weight',anchor:'text-anchor'};
  var numeric=['x','y','width','height','r','rx','ry','x2','y2','rotation','opacity','strokeWidth','fontSize','fontWeight'];
  var shapes={group:'g',rect:'rect',circle:'circle',ellipse:'ellipse',line:'line',path:'path',polygon:'polygon',text:'text'};
  var permitted={group:['x','y','rotation','opacity'],rect:['x','y','width','height','rx'],circle:['x','y','r'],ellipse:['x','y','rx','ry'],line:['x','y','x2','y2'],path:['d'],polygon:['points'],text:['x','y','text','fontSize','fontWeight','anchor']};
  Object.keys(permitted).forEach(function(k){permitted[k]=permitted[k].concat(['fill','stroke','strokeWidth','opacity','rotation']);});
  function activate(action){var button=document.querySelector('[data-action="'+action+'"]');if(button&&!button.disabled)button.click();}
  function addShape(definition){
    if(!shapes[definition.type]||!/^[a-z][a-z0-9_]{0,31}$/.test(definition.id)||elements[definition.id])return;
    var el=svg(shapes[definition.type]),tooltip=svg('title');tooltip.textContent=String(definition.label||'').slice(0,120);el.appendChild(tooltip);el.dataset.visualNode=definition.id;
    var parent=definition.parent&&elements[definition.parent];(parent||picture).appendChild(el);elements[definition.id]=el;
    var entry={definition:definition,el:el,rendered:null};entries.push(entry);
    if(definition.action&&/^[a-z][a-z0-9_]{0,31}$/.test(definition.action)&&data.actions.some(function(a){return a.id===definition.action;})){
      el.setAttribute('role','button');el.setAttribute('tabindex','0');el.setAttribute('aria-label',tooltip.textContent);el.addEventListener('click',function(){activate(definition.action);});el.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();activate(definition.action);}});
    }
  }
  if(authored)visual.nodes.forEach(addShape);
  else {
    // Accurate fallback for existing courses and unavailable illustration service.
    // It is explicitly labelled as a conceptual map, never a fabricated scene.
    var total=data.variables.length,cols=total<=4?2:3,rows=Math.ceil(total/cols),cw=760/cols,ch=400/rows;
    data.variables.forEach(function(v,i){var x=20+(i%cols)*cw,y=20+Math.floor(i/cols)*ch;
      addShape({id:'state_'+i,type:'rect',label:v.label,attrs:{x:x,y:y,width:cw-14,height:ch-14,rx:14,fill:'#193d58',stroke:'#6589a3',strokeWidth:2}});
      var label=String(v.label).slice(0,42),words=label.split(' '),lines=[''];words.forEach(function(w){var n=lines.length-1;if((lines[n]+' '+w).length>18&&n===0)lines.push(w);else lines[lines.length-1]+=(lines[lines.length-1]?' ':'')+w;});
      lines.slice(0,2).forEach(function(t,j){addShape({id:'label_'+i+'_'+j,type:'text',label:v.label,attrs:{x:x+12,y:y+30+j*28,text:t,fontSize:26,fill:'#eef6ff'}});});
      addShape({id:'value_'+i,type:'text',label:v.label+' atual',attrs:{x:x+12,y:y+ch-40,text:'{'+v.id+'} '+v.unit,fontSize:30,fill:'#9df1da'}});
      addShape({id:'bar_'+i,type:'rect',label:'Variação de '+v.label,attrs:{x:x+12,y:y+ch-28,width:0,height:8,rx:4,fill:'#62daca'},bindings:[{property:'width',var:v.id,input:[v.min,v.max],output:[0,cw-38]}]});
    });
  }
  function projected(entry,state){var def=entry.definition,attrs=Object.assign({},def.attrs||{});(def.bindings||[]).forEach(function(b){if(numeric.indexOf(b.property)!==-1&&b.input&&b.output)attrs[b.property]=interpolate(b,state);});var matched=(def.states||[]).find(function(s){return evalExpr(s.when,state);});if(matched)Object.assign(attrs,matched.set);return{attrs:attrs,visible:def.visibleWhen===undefined||!!evalExpr(def.visibleWhen,state)};}
  function apply(entry,attrs){
    var el=entry.el,kind=entry.definition.type,allowed=permitted[kind];
    allowed.forEach(function(key){if(attrs[key]===undefined)return;var value=attrs[key],name=propertyNames[key]||key;
      if(key==='rotation'||kind==='group'&&(key==='x'||key==='y'))return;
      if(key==='text'){while(el.childNodes.length>1)el.removeChild(el.lastChild);el.appendChild(document.createTextNode(String(value).slice(0,100)));return;}
      if(key==='fill'||key==='stroke')value=color(value);
      else if(numeric.indexOf(key)!==-1){if(!Number.isFinite(value)||Math.abs(value)>2000)return;}
      else if(key==='anchor'){if(['start','middle','end'].indexOf(value)===-1)return;}
      else if(key==='d'){if(typeof value!=='string'||value.length>1600||!/^[MLHVCSQTAZmlhvcsqtaz0-9eE.,+\s-]+$/.test(value))return;}
      else if(key==='points'){if(!Array.isArray(value)||value.length>40)return;value=value.map(function(p){return Array.isArray(p)?p.slice(0,2).map(Number).join(','):'';}).join(' ');}
      if((kind==='circle'||kind==='ellipse')&&(key==='x'||key==='y'))name=key==='x'?'cx':'cy';el.setAttribute(name,String(value));
    });
    var rotation=Number(attrs.rotation)||0;el.setAttribute('transform',(kind==='group'?'translate('+(Number(attrs.x)||0)+' '+(Number(attrs.y)||0)+') ':'')+'rotate('+rotation+')');
  }
  function update(view){
    if(!view||!view.state)return;
    if(frame!==null){window.cancelAnimationFrame(frame);frame=null;}
    var reset=view.steps===0,reduce=typeof window.matchMedia==='function'&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var animate=!initial&&!reset&&!reduce&&view.steps!==lastStep;lastStep=view.steps;initial=false;
    var targets=entries.map(function(entry){var value=projected(entry,view.state);if(value.attrs.text!==undefined)value.attrs.text=textValue(value.attrs.text,view.state);
      var old=entry.rendered||value.attrs,changed=JSON.stringify(old)!==JSON.stringify(value.attrs);entry.el.dataset.visualChanged=String(changed&&!reset);entry.el.style.display=value.visible?'':'none';
      if(entry.definition.action){var action=(view.actions||[]).find(function(a){return a.id===entry.definition.action;});entry.el.setAttribute('aria-disabled',String(!action||!action.enabled));entry.el.setAttribute('tabindex',action&&action.enabled?'0':'-1');}
      return {entry:entry,from:old,to:value.attrs};
    });
    function paint(t){targets.forEach(function(item){var attrs=Object.assign({},item.to);if(t<1)numeric.forEach(function(k){if(typeof item.from[k]==='number'&&typeof item.to[k]==='number')attrs[k]=item.from[k]+(item.to[k]-item.from[k])*t;});apply(item.entry,attrs);item.entry.rendered=attrs;});}
    if(animate&&typeof window.requestAnimationFrame==='function'){
      var start=null;function step(now){if(start===null)start=now;var t=Math.min(1,(now-start)/420);paint(t*t*(3-2*t));frame=t<1?window.requestAnimationFrame(step):null;}frame=window.requestAnimationFrame(step);
    }else paint(1);
    caption.textContent=(authored?'Cena vinculada às decisões · ':data.visualNotice?'Ilustração indisponível; diagrama conceitual · ':'Diagrama conceitual dos estados · ')+(view.scene?view.scene.title:'Estado inicial');
  }
  var state=Object.create(null);data.variables.forEach(function(v){state[v.id]=v.initial;});update({state:state,steps:0,actions:[],scene:{title:'Estado inicial'}});
  document.addEventListener('scormify:rules-state',function(event){update(event.detail);});
  // The original engine render ran before this appended upgrade. Its last view
  // is held on a DOM event bridge, not recomputed or guessed from indicator text.
  var bridge=document.getElementById('scormify-rule-view');
  if(bridge){try{update(JSON.parse(bridge.textContent));}catch(_){/* retain initial view */}}
  window.addEventListener('pagehide',function(){if(frame!==null)window.cancelAnimationFrame(frame);});
}
