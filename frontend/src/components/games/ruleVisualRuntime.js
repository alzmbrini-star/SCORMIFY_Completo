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
  function interpolate(b,state){var lo=b.input[0],hi=b.input[1],t=hi===lo?(state[b.var]>=lo?1:0):(state[b.var]-lo)/(hi-lo);return b.output[0]+Math.max(0,Math.min(1,t))*(b.output[1]-b.output[0]);}
  function textValue(value,state){return String(value||'').slice(0,100).replace(/\{([a-z][a-z0-9_]*)\}/g,function(_,key){return Object.prototype.hasOwnProperty.call(state,key)?String(state[key]):'?';});}
  var figure=node('figure');figure.id='rule-visual';figure.className='sim-rule-visual';figure.dataset.visualMode=authored?'illustrated':'conceptual';
  var picture=svg('svg');picture.setAttribute('viewBox','0 0 800 450');picture.setAttribute('preserveAspectRatio','xMidYMid meet');picture.setAttribute('role','group');
  var title=svg('title'),desc=svg('desc');title.textContent=authored?visual.title:'Mapa visual dos estados';desc.textContent=authored?visual.description:((data.visualNotice||'')+' Diagrama conceitual: as formas mostram os estados reais e suas mudanças. Não é uma representação física do ambiente.').trim();picture.appendChild(title);picture.appendChild(desc);picture.setAttribute('aria-label',title.textContent);figure.dataset.visualDescription=desc.textContent;
  picture.style.background=authored?color(visual.background):'#102a43';picture.style.fontFamily='system-ui,sans-serif';figure.appendChild(picture);
  var caption=node('figcaption');caption.className='sim-visual-caption';figure.appendChild(caption);anchor.parentNode.insertBefore(figure,anchor);
  if(data.visualNotice){var warning=node('details');warning.className='sim-visual-warning';warning.style.cssText='flex-shrink:0;font:13px/1.4 system-ui,sans-serif;color:#10243b;background:#fff4d6;border:1px solid #b88c34;border-radius:6px;padding:4px 8px;margin:4px 0';warning.appendChild(node('summary',authored?'Prévia com observações para o autor':'Ilustração indisponível — ver motivo'));warning.appendChild(node('p',data.visualNotice));figure.appendChild(warning);}
  var teaching=authored&&visual.teaching&&visual.teaching.version===1?visual.teaching:null;
  var explanation=null,guide=null,previousState=null;
  if(teaching){
    explanation=node('span');explanation.setAttribute('role','status');explanation.setAttribute('aria-live','polite');caption.appendChild(explanation);
    guide=node('button','Como interpretar');guide.type='button';guide.className='sim-visual-guide';guide.addEventListener('click',function(){document.dispatchEvent(new CustomEvent('scormify:visual-guide'));});caption.appendChild(guide);
    caption.style.display='flex';caption.style.alignItems='center';caption.style.gap='8px';explanation.style.flex='1';explanation.style.minWidth='0';
    explanation.style.display='-webkit-box';explanation.style.webkitLineClamp='2';explanation.style.webkitBoxOrient='vertical';explanation.style.overflow='hidden';guide.style.flexShrink='0';
  }
  var style=node('style');style.id='rule-visual-style';style.textContent='.sim-rule-visual{margin:0;display:flex;flex-direction:column;min-width:0;min-height:0;flex:1;overflow:hidden}.sim-rule-visual>svg{display:block;width:100%;flex:1;min-height:0;border:1px solid #59768f;border-radius:10px}.sim-dialog-body .sim-rule-visual{height:min(65vh,520px);min-height:200px}.sim-visual-caption{font:calc(14px * var(--sim-ui,1))/1.35 system-ui,sans-serif;color:#dceafb;padding-top:6px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.sim-rule-visual [role="button"]{cursor:pointer}.sim-rule-visual [aria-disabled="true"]{cursor:not-allowed}.sim-rule-visual [role="button"]:focus-visible{outline:3px solid #fbbf24;outline-offset:4px}.sim-rule-visual [data-visual-changed="true"]{filter:drop-shadow(0 0 5px #7dd3fc)}';document.head.appendChild(style);
  var entries=[],elements=Object.create(null),frame=null,initial=true,lastStep=0,syncLegend=null;
  var demo=data.didacticMode==='process-demo-v1';
  // Fit the scene itself, not a wide background strip. Never stretch SVG units.
  var stage=node('div');stage.className='sim-visual-stage';figure.insertBefore(stage,picture);stage.appendChild(picture);
  stage.style.cssText='flex:1;min-height:0;min-width:0;display:flex;align-items:center;justify-content:center;overflow:hidden';
  picture.style.flex='none';picture.style.maxWidth='100%';picture.style.maxHeight='100%';picture.style.border='1px solid #59768f';picture.style.borderRadius='10px';
  function fitScene(){var box=stage.getBoundingClientRect();if(!box.width||!box.height)return;var w=Math.min(box.width,box.height*800/450);picture.style.width=w+'px';picture.style.height=(w*450/800)+'px';if(syncLegend)syncLegend();}
  var sceneObserver=typeof ResizeObserver==='function'?new ResizeObserver(fitScene):null;
  if(sceneObserver)sceneObserver.observe(stage);window.addEventListener('resize',fitScene);if(typeof window.requestAnimationFrame==='function')window.requestAnimationFrame(fitScene);else fitScene();
  if(demo&&authored&&teaching)anchor.hidden=true; // The same guidance remains in the scene caption/guide; reserve room for the illustration.
  if(demo){var simplified=node('div','Demonstração didática simplificada · foco no processo, sem precisão de engenharia.');simplified.setAttribute('role','note');simplified.style.cssText='flex-shrink:0;font:12px/1.3 system-ui,sans-serif;color:#d7eef3;background:#183b4a;padding:5px 8px;border-left:3px solid #6ed9c4;border-radius:5px;margin-bottom:5px';figure.insertBefore(simplified,stage);}
  var finish=demo&&authored&&(data.experience||{}).visualStyle==='illustrated',paints=Object.create(null),defs;
  function mix(a,b,t){return '#'+[1,3,5].map(function(i){return Math.round(parseInt(a.slice(i,i+2),16)*(1-t)+parseInt(b.slice(i,i+2),16)*t).toString(16).padStart(2,'0');}).join('');}
  function effect(tag,attrs,parent){var e=svg(tag);Object.keys(attrs).forEach(function(k){e.setAttribute(k,attrs[k]);});parent.appendChild(e);return e;}
  if(finish){
    defs=effect('defs',{id:'process-art-finish'},picture);
    var shadow=effect('filter',{id:'process-art-shadow',x:'-30%',y:'-30%',width:'160%',height:'170%'},defs);
    effect('feDropShadow',{dx:0,dy:2,stdDeviation:2,'flood-color':'#000000','flood-opacity':'.22'},shadow);
    figure.dataset.artFinish='soft-volume';
  }
  function finishShape(entry,attrs){
    var kind=entry.definition.type,base=attrs.fill;
    if(!finish||['group','text','line'].indexOf(kind)>=0||!/^#[0-9a-f]{6}$/i.test(base||''))return;
    if(kind==='rect'&&attrs.width>=780&&attrs.height>=430)return;
    var key=entry.definition.id,p=paints[key];
    if(!p){
      var radial=kind==='circle'||kind==='ellipse',gradient=effect(radial?'radialGradient':'linearGradient',radial?{id:'process-paint-'+key,cx:'30%',cy:'25%',r:'80%'}:{id:'process-paint-'+key,x1:'0%',y1:'0%',x2:'30%',y2:'100%'},defs);
      p=paints[key]={stops:[effect('stop',{offset:'0%'},gradient),effect('stop',{offset:'45%'},gradient),effect('stop',{offset:'100%'},gradient)],base:null};
    }
    if(p.base!==base){[mix(base,'#ffffff',.32),base,mix(base,'#000000',.22)].forEach(function(c,i){p.stops[i].setAttribute('stop-color',c);});p.base=base;}
    entry.el.setAttribute('fill','url(#process-paint-'+key+')');entry.el.setAttribute('filter','url(#process-art-shadow)');
  }
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
  // A declared full rotational cycle can keep demonstrating between decisions.
  // This clock paints only; it never advances the rule engine or its score.
  var cycles=demo?entries.filter(function(e){return(e.definition.bindings||[]).some(function(b){return b.property==='rotation'&&b.output&&Math.abs(b.output[1]-b.output[0])>=300;});}):[];
  var declaredMotions=demo&&authored&&Array.isArray(visual.motions)?visual.motions.slice(0,24).filter(function(m){return m&&entries.some(function(e){return e.definition.id===m.node&&e.definition.type!=='text';})&&['orbit','rotate','translate'].indexOf(m.kind)>=0&&['cx','cy','dx','dy','cycles','phase'].every(function(k){return Number.isFinite(m[k])&&Math.abs(m[k])<=2000;})&&Math.abs(m.cycles)>=.25&&Math.abs(m.cycles)<=8;}):[];
  if(declaredMotions.length)cycles=[];
  // Old guided documents often encode animation as one "advance" action.
  // Replay its unambiguous trajectory on a separate engine, never click the
  // learner's controls, choose a branch, or alter the real state/history.
  var demonstration=[];
  if(demo&&!cycles.length&&!declaredMotions.length&&typeof window.createRuleEngine==='function'){
    try {
      var rehearsal=window.createRuleEngine(data),rehearsalView=rehearsal.getState(),trajectory=[rehearsalView],safe=true;
      for(var rehearsalStep=0;rehearsalStep<Math.min(24,Number(data.maxSteps)||24)&&rehearsalView.outcome==='active';rehearsalStep++){
        var choices=rehearsalView.actions.filter(function(a){return a.enabled;});
        if(choices.length!==1){safe=false;break;}
        var rehearsalResult=rehearsal.act(choices[0].id);
        if(!rehearsalResult.ok){safe=false;break;}
        rehearsalView=rehearsalResult.view;trajectory.push(rehearsalView);
      }
      if(safe&&trajectory.length>1&&rehearsalView.outcome==='success')demonstration=trajectory;
    }catch(_){/* Non-replayable documents retain manual exploration. */}
  }
  var motionFrame=null,motionTime=0,motionStamp=null,motionSpeed=1,motionPlaying=false,motionButton=null;
  function spin(){
    if(declaredMotions.length&&motionPlaying){declaredMotions.forEach(function(m){var e=entries.find(function(e){return e.definition.id===m.node;});if(!e.rendered||e.el.style.display==='none')return;
      var a=Object.assign({},e.rendered),angle=2*Math.PI*m.cycles*motionTime/12+m.phase*Math.PI/180;
      if(m.kind==='orbit'){a.x=m.cx+m.dx*Math.cos(angle);a.y=m.cy+m.dy*Math.sin(angle);}
      apply(e,a);
      if(m.kind==='translate')e.el.setAttribute('transform','translate('+(m.dx*Math.sin(angle))+' '+(m.dy*Math.sin(angle))+') '+e.el.getAttribute('transform'));
      if(m.kind==='rotate')e.el.setAttribute('transform',(e.definition.type==='group'?'translate('+(Number(a.x)||0)+' '+(Number(a.y)||0)+') ':'')+'rotate('+((Number(a.rotation)||0)+angle*180/Math.PI)+' '+m.cx+' '+m.cy+')');
    });}
    if(demonstration.length&&motionPlaying){
      var segmentSeconds=2,travel=(demonstration.length-1)*segmentSeconds,local=motionTime%(travel+1),index=Math.min(demonstration.length-2,Math.floor(local/segmentSeconds)),t=Math.min(1,(local-index*segmentSeconds)/segmentSeconds);
      var before=demonstration[index],after=demonstration[index+1];
      entries.forEach(function(e){var first=projected(e,before.state),last=projected(e,after.state),attrs=Object.assign({},t<.5?first.attrs:last.attrs);
        numeric.forEach(function(k){if(typeof first.attrs[k]==='number'&&typeof last.attrs[k]==='number')attrs[k]=first.attrs[k]+(last.attrs[k]-first.attrs[k])*t;});
        if(attrs.text!==undefined)attrs.text=textValue(attrs.text,(t<.5?before:after).state);
        e.el.style.display=(t<.5?first.visible:last.visible)?'':'none';apply(e,attrs);
      });
      if(!teaching)caption.textContent='Reprodução ilustrativa em ciclo · '+((t<.5?before:after).scene?.title||'Demonstração');
    }
    cycles.forEach(function(e){if(!e.rendered||e.el.style.display==='none')return;var b=e.definition.bindings.find(function(b){return b.property==='rotation';}),a=e.rendered,rotation=(Number(a.rotation)||0)+(b.output[1]>=b.output[0]?1:-1)*motionTime*30;
    e.el.setAttribute('transform',(e.definition.type==='group'?'translate('+(Number(a.x)||0)+' '+(Number(a.y)||0)+') ':'')+'rotate('+rotation+')');});}
  function queueMotion(){if(motionFrame===null&&motionPlaying&&!document.hidden&&typeof window.requestAnimationFrame==='function')motionFrame=window.requestAnimationFrame(tickMotion);}
  function tickMotion(now){motionFrame=null;if(!motionPlaying||document.hidden){motionStamp=null;return;}if(motionStamp!==null)motionTime+=Math.min(.1,(now-motionStamp)/1000)*motionSpeed;motionStamp=now;spin();if(syncLegend)syncLegend();queueMotion();}
  function setMotion(playing){motionPlaying=playing;motionStamp=null;if(motionFrame!==null){window.cancelAnimationFrame(motionFrame);motionFrame=null;}figure.dataset.motionPlaying=String(playing);if(!teaching)caption.textContent=playing?'Reprodução ilustrativa contínua · sem avanço automático de decisões':'Reprodução pausada';if(motionButton){motionButton.textContent=playing?'Pausar movimento':'Reproduzir movimento';motionButton.setAttribute('aria-pressed',String(playing));}document.dispatchEvent(new CustomEvent('scormify:motion-playback'));queueMotion();}
  if(cycles.length||demonstration.length||declaredMotions.length){
    var motionTools=node('div');motionTools.className='sim-motion-tools';motionTools.style.cssText='display:flex;align-items:center;gap:8px;flex-shrink:0;padding:4px 0';
    motionButton=node('button');motionButton.type='button';motionButton.addEventListener('click',function(){setMotion(!motionPlaying);});motionTools.appendChild(motionButton);
    var speedLabel=node('label','Velocidade '),speedControl=node('select');speedControl.setAttribute('aria-label','Velocidade do movimento');[.5,1,2].forEach(function(value){var option=node('option',value+'×');option.value=value;speedControl.appendChild(option);});speedControl.value='1';speedControl.addEventListener('change',function(){motionSpeed=Number(speedControl.value)||1;});speedLabel.appendChild(speedControl);motionTools.appendChild(speedLabel);figure.insertBefore(motionTools,caption);
    setMotion(!(typeof window.matchMedia==='function'&&window.matchMedia('(prefers-reduced-motion: reduce)').matches));
  }
  document.addEventListener('visibilitychange',function(){motionStamp=null;if(document.hidden&&motionFrame!==null){window.cancelAnimationFrame(motionFrame);motionFrame=null;}else queueMotion();});
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
      if((kind==='circle'||kind==='ellipse')&&(key==='x'||key==='y'))name=key==='x'?'cx':'cy';
      if(kind==='line'&&(key==='x'||key==='y'))name=key==='x'?'x1':'y1';
      el.setAttribute(name,String(value));
    });
    finishShape(entry,attrs);
    var rotation=Number(attrs.rotation)||0;el.setAttribute('transform',(kind==='group'?'translate('+(Number(attrs.x)||0)+' '+(Number(attrs.y)||0)+') ':'')+'rotate('+rotation+')');
  }
  function update(view){
    if(!view||!view.state)return;
    if(frame!==null){window.cancelAnimationFrame(frame);frame=null;}
    var reset=view.steps===0,reduce=typeof window.matchMedia==='function'&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if(reset){motionTime=0;motionStamp=null;}
    var animate=!initial&&!reset&&!reduce&&view.steps!==lastStep;lastStep=view.steps;initial=false;
    var targets=entries.map(function(entry){var value=projected(entry,view.state);if(value.attrs.text!==undefined)value.attrs.text=textValue(value.attrs.text,view.state);
      var old=entry.rendered||value.attrs,changed=JSON.stringify(old)!==JSON.stringify(value.attrs);entry.el.dataset.visualChanged=String(changed&&!reset);entry.el.style.display=value.visible?'':'none';
      if(entry.definition.action){var action=(view.actions||[]).find(function(a){return a.id===entry.definition.action;});entry.el.setAttribute('aria-disabled',String(!action||!action.enabled));entry.el.setAttribute('tabindex',action&&action.enabled?'0':'-1');}
      return {entry:entry,from:old,to:value.attrs};
    });
    function paint(t){targets.forEach(function(item){var attrs=Object.assign({},item.to);if(t<1)numeric.forEach(function(k){if(typeof item.from[k]==='number'&&typeof item.to[k]==='number')attrs[k]=item.from[k]+(item.to[k]-item.from[k])*t;});apply(item.entry,attrs);item.entry.rendered=attrs;});spin();if(syncLegend)syncLegend();}
    if(animate&&typeof window.requestAnimationFrame==='function'){
      var start=null;function step(now){if(start===null)start=now;var t=Math.min(1,(now-start)/420);paint(t*t*(3-2*t));frame=t<1?window.requestAnimationFrame(step):null;}frame=window.requestAnimationFrame(step);
    }else paint(1);
    if(teaching){
      var changedLinks=(teaching.links||[]).filter(function(link){return previousState&&previousState[link.var]!==view.state[link.var];});
      if(reset||!previousState)explanation.textContent=teaching.focus;
      else if(changedLinks.length)explanation.textContent='Observe: '+changedLinks.map(function(link){var v=data.variables.find(function(item){return item.id===link.var;});return v.label+': '+previousState[link.var]+' → '+view.state[link.var]+'. '+link.whatChanges+' '+link.whyItMatters;}).join(' ').slice(0,420);
      previousState=Object.assign({},view.state);
      caption.title=explanation.textContent;figure.dataset.observedVariables=changedLinks.map(function(link){return link.var;}).join(',');
    }else caption.textContent=(demo?'Demonstração didática simplificada · ':'')+(authored?(demo?'Cena ilustrativa · ':'Cena vinculada às decisões · '):data.visualNotice?'Ilustração indisponível; diagrama conceitual · ':'Diagrama conceitual dos estados · ')+(view.scene?view.scene.title:'Estado inicial');
  }
  var state=Object.create(null);data.variables.forEach(function(v){state[v.id]=v.initial;});update({state:state,steps:0,actions:[],scene:{title:'Estado inicial'}});
  document.addEventListener('scormify:rules-state',function(event){update(event.detail);});
  // The original engine render ran before this appended upgrade. Its last view
  // is held on a DOM event bridge, not recomputed or guessed from indicator text.
  var bridge=document.getElementById('scormify-rule-view');
  if(bridge){try{update(JSON.parse(bridge.textContent));}catch(_){/* retain initial view */}}
  // A consultable legend, not another layer of permanently overlapping SVG text.
  var objects=authored?entries.filter(function(e){return e.definition.type!=='text'&&String(e.definition.label||'').trim();}):[];
  if(objects.length){
    var legendStyle=node('style');legendStyle.textContent='.sim-object-legend[hidden],.sim-object-name[hidden]{display:none!important}.sim-object-legend{position:fixed;right:12px;top:64px;z-index:1200;width:min(310px,calc(100vw - 24px));max-height:70vh;overflow:auto;background:#f8fbff;color:#10243b;border:1px solid #57758e;border-radius:12px;padding:12px;box-shadow:0 8px 35px #0005;font:14px/1.4 system-ui,sans-serif}.sim-object-legend h2{font-size:17px;margin:0 0 8px}.sim-object-legend .sim-object-list{display:grid;gap:5px}.sim-object-legend .sim-object-list button{text-align:left;width:100%;font-size:14px}.sim-object-legend button[aria-pressed=true]{background:#0e6675!important;color:#fff!important}.sim-object-legend p{font-size:14px;line-height:1.45;margin:8px 0}.sim-object-name{position:absolute;z-index:4;pointer-events:none;max-width:190px;background:#10243b;color:#fff;border:1px solid #facc15;border-radius:6px;padding:4px 7px;font:13px/1.3 system-ui,sans-serif;box-shadow:0 2px 8px #0005}.sim-rule-visual [data-legend-selected=true]{filter:drop-shadow(0 0 5px #facc15)!important}';document.head.appendChild(legendStyle);
    var tools=motionTools;if(!tools){tools=node('div');tools.className='sim-motion-tools';figure.insertBefore(tools,caption);}tools.style.flexWrap='wrap';
    var legendButton=node('button','Objetos e legendas');legendButton.type='button';legendButton.setAttribute('aria-expanded','false');tools.appendChild(legendButton);
    var panel=node('section');panel.className='sim-object-legend';panel.hidden=true;panel.setAttribute('aria-label','Legenda dos objetos');
    panel.appendChild(node('h2','Objetos da cena'));var closeLegend=node('button','Fechar legenda');closeLegend.type='button';panel.appendChild(closeLegend);
    var list=node('div');list.className='sim-object-list';list.setAttribute('aria-label','Selecionar objeto');panel.appendChild(list);
    var detail=node('p','Selecione um nome para identificar o objeto na cena.');detail.setAttribute('role','status');panel.appendChild(detail);figure.appendChild(panel);
    var selectedObject=null,legendButtons=Object.create(null),nameTag=node('span');nameTag.className='sim-object-name';nameTag.hidden=true;stage.style.position='relative';stage.appendChild(nameTag);
    syncLegend=function(){if(!selectedObject){nameTag.hidden=true;return;}var rect=selectedObject.el.getBoundingClientRect(),box=stage.getBoundingClientRect();
      nameTag.hidden=!rect.width&&!rect.height||selectedObject.el.style.display==='none';if(nameTag.hidden)return;
      nameTag.style.left=Math.max(4,Math.min(box.width-nameTag.offsetWidth-4,rect.left-box.left+rect.width/2-nameTag.offsetWidth/2))+'px';
      nameTag.style.top=Math.max(4,Math.min(box.height-nameTag.offsetHeight-4,rect.top-box.top-nameTag.offsetHeight-6))+'px';};
    function selectObject(e){selectedObject=e;objects.forEach(function(other){other.el.dataset.legendSelected=String(other===e);legendButtons[other.definition.id]?.setAttribute('aria-pressed',String(other===e));});
      nameTag.textContent=e.definition.label;var explanation=e.definition.explanation||'';
      if(!explanation&&teaching)explanation=(teaching.links||[]).filter(function(l){return l.node===e.definition.id;}).map(function(l){return l.whatChanges+' '+l.whyItMatters;}).join(' ');
      detail.textContent=e.definition.label+(explanation?': '+explanation:'. Objeto identificado no cenário.');syncLegend();}
    objects.forEach(function(e){var b=node('button',e.definition.label);b.type='button';b.setAttribute('aria-pressed','false');b.dataset.legendObject=e.definition.id;b.addEventListener('click',function(){selectObject(e);});b.addEventListener('focus',function(){selectObject(e);});list.appendChild(b);legendButtons[e.definition.id]=b;
      if(!e.definition.action)e.el.addEventListener('click',function(event){if(event.target.closest('[data-visual-node]')!==e.el)return;event.stopPropagation();selectObject(e);});});
    function showLegend(open){panel.hidden=!open;legendButton.setAttribute('aria-expanded',String(open));if(open)closeLegend.focus();else legendButton.focus();}
    legendButton.addEventListener('click',function(){showLegend(panel.hidden);});closeLegend.addEventListener('click',function(){showLegend(false);});panel.addEventListener('keydown',function(e){if(e.key==='Escape'){e.preventDefault();showLegend(false);}});
    var resetLegend=document.getElementById('reset');if(resetLegend)resetLegend.addEventListener('click',function(){selectedObject=null;nameTag.hidden=true;objects.forEach(function(e){e.el.removeAttribute('data-legend-selected');legendButtons[e.definition.id].setAttribute('aria-pressed','false');});});
  }
  window.addEventListener('pagehide',function(){if(frame!==null)window.cancelAnimationFrame(frame);if(motionFrame!==null)window.cancelAnimationFrame(motionFrame);motionFrame=null;motionPlaying=false;if(sceneObserver)sceneObserver.disconnect();window.removeEventListener('resize',fitScene);});
}
