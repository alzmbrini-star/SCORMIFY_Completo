// Trusted presentation only. No animation loop, equations, metrics or external assets.
export function visualizationFinishRuntime() {
  'use strict';
  var marker='scormify-visualization-finish-style-v1';
  if(document.getElementById(marker))return;
  var scene=document.getElementById('scene'),plan=document.getElementById('scormify-visualization-plan'),data;
  try{data=JSON.parse(plan.textContent);}catch(_){return;}
  if(!scene||!data||!Array.isArray(data.nodes)||data.nodes.length>80)return;
  function hex(value,fallback){return typeof value==='string'&&/^#[0-9a-f]{6}$/i.test(value)?value:fallback;}
  function mix(a,b,t){return '#'+[1,3,5].map(function(i){return Math.round(parseInt(a.slice(i,i+2),16)*(1-t)+parseInt(b.slice(i,i+2),16)*t).toString(16).padStart(2,'0');}).join('');}
  function luminance(c){var p=[1,3,5].map(function(i){var v=parseInt(c.slice(i,i+2),16)/255;return v<=.04045?v/12.92:Math.pow((v+.055)/1.055,2.4);});return p[0]*.2126+p[1]*.7152+p[2]*.0722;}
  function contrast(a,b){var x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
  var p=data.presentation||{},background=hex(data.background,'#10243b');
  var theme=['midnight','daylight','warm'].indexOf(p.theme)>=0?p.theme:(luminance(background)>.35?'daylight':'midnight');
  var atmosphere=['studio','technical','natural'].indexOf(p.atmosphere)>=0?p.atmosphere:'studio';
  var palettes={midnight:{page:'#07111f',panel:'#0d1c2f',ink:'#eef7ff',muted:'#b0c3d7',line:'#36536d',accent:'#4de3ff'},daylight:{page:'#e9f0f5',panel:'#ffffff',ink:'#10243b',muted:'#42566e',line:'#a2b5c7',accent:'#2563eb'},warm:{page:'#f3eee5',panel:'#fffdf8',ink:'#342b22',muted:'#685640',line:'#b5a083',accent:'#9a4b18'}};
  var palette=palettes[theme],accent=hex(p.accent,palette.accent),highlight=mix(background,accent,.13);
  var root=document.documentElement;
  Object.entries({page:palette.page,panel:palette.panel,ink:palette.ink,muted:palette.muted,line:palette.line,accent:accent}).forEach(function(pair){root.style.setProperty('--vf-'+pair[0],pair[1]);});
  root.style.setProperty('--vf-accent-ink',contrast('#ffffff',accent)>=4.5?'#ffffff':'#10243b');
  root.style.setProperty('--vf-accent-soft',mix(palette.panel,accent,.09));
  var style=document.createElement('style');style.id=marker;style.textContent=`
html,body{background:var(--vf-page);color:var(--vf-ink);font-family:system-ui,-apple-system,Segoe UI,Arial,sans-serif}
body{padding:16px;gap:12px;background:radial-gradient(ellipse at 35% 0%,var(--vf-accent-soft),transparent 60%),var(--vf-page)}
header{padding:0 4px}header small{color:var(--vf-ink);opacity:.85;font-size:11px;letter-spacing:.15em}h1{font-weight:750;letter-spacing:-.025em;line-height:1.12;margin:5px 0 7px}#subtitle{color:var(--vf-muted);font-size:clamp(14px,1.4vw,17px)}
main{gap:14px;grid-template-columns:minmax(0,3.25fr) minmax(230px,1fr)}figure{isolation:isolate;border:1px solid var(--vf-line);border-radius:18px;box-shadow:0 14px 38px #00000020,inset 0 1px 0 #ffffff18}figure:after{content:'';position:absolute;inset:0;pointer-events:none;border-radius:inherit;box-shadow:inset 0 0 45px #0000000d}
aside{background:linear-gradient(145deg,var(--vf-panel),var(--vf-accent-soft));border:1px solid var(--vf-line);border-radius:18px;padding:15px;box-shadow:0 10px 26px #00000012;scrollbar-width:thin}aside h2{font-size:18px;letter-spacing:-.02em;padding-bottom:10px;border-bottom:1px solid var(--vf-line)}#goal{font-size:14px;color:var(--vf-muted);line-height:1.5}
.items{gap:7px;margin:12px 0}.items button{background:var(--vf-panel);color:var(--vf-ink);font-size:13px;border:1px solid var(--vf-line);box-shadow:inset 0 1px 0 #ffffff18;padding:7px 10px}.items button[aria-pressed=true]{background:var(--vf-accent-soft);color:var(--vf-ink);border-color:var(--vf-accent)}
button,select{background:var(--vf-panel);color:var(--vf-ink);border:1px solid var(--vf-line);border-radius:10px;min-height:38px;transition:background .15s,border-color .15s}button:hover{border-color:var(--vf-accent);background:var(--vf-accent-soft)}button:focus-visible,select:focus-visible,input:focus-visible,[tabindex]:focus-visible{outline:3px solid var(--vf-accent);outline-offset:3px}#play{background:var(--vf-accent);color:var(--vf-accent-ink);border-color:var(--vf-accent);font-weight:700;min-width:85px}#labels[aria-pressed=true]{background:var(--vf-accent-soft);color:var(--vf-ink);border-color:var(--vf-accent)}
#detail{background:var(--vf-accent-soft);color:var(--vf-ink);font-size:14px;line-height:1.5;border-left:3px solid var(--vf-accent);padding:10px;border-radius:9px}details{margin-top:12px;padding-top:10px;border-top:1px solid var(--vf-line)}summary{font-size:13px;cursor:pointer;font-weight:600}#notice{color:var(--vf-muted);font-size:13px;line-height:1.5;margin-top:8px}
footer{padding:10px 12px;background:var(--vf-panel);border:1px solid var(--vf-line);border-radius:14px;box-shadow:0 5px 18px #0000000d;font-size:14px}footer input{accent-color:var(--vf-accent)}#progress{font-size:13px;color:var(--vf-muted)}#scene g[role=button]{cursor:pointer}#scene g[role=button]:focus-visible>*:not(text),#scene g[data-vf-selected=true]>*:not(text){stroke:var(--vf-accent);stroke-width:3}
@media(max-width:750px){body{padding:9px;gap:8px}main{gap:8px;grid-template-columns:minmax(0,1fr) 210px}aside{padding:10px}.items{gap:5px}.items button{font-size:12px;padding:6px}footer{padding:7px;gap:7px}button,select{min-height:36px}h1{font-size:22px}}
@media(prefers-reduced-motion:reduce){button,select{transition:none}}
`;document.head.appendChild(style);
  scene.style.background='radial-gradient(ellipse at 42% 36%,'+highlight+' 0%,'+background+' 72%)';
  var ns='http://www.w3.org/2000/svg',defs=document.createElementNS(ns,'defs');defs.id='vf-definitions';
  function svg(tag,attrs,parent){var e=document.createElementNS(ns,tag);Object.entries(attrs).forEach(function(k){e.setAttribute(k[0],k[1]);});parent.appendChild(e);return e;}
  var shadow=svg('filter',{id:'vf-shadow',x:'-35%',y:'-35%',width:'170%',height:'180%'},defs);svg('feDropShadow',{dx:0,dy:3,stdDeviation:3,'flood-color':'#000000','flood-opacity':theme==='midnight'?.4:.2},shadow);
  var raised=svg('filter',{id:'vf-raised',x:'-50%',y:'-50%',width:'200%',height:'220%'},defs);svg('feDropShadow',{dx:0,dy:5,stdDeviation:5,'flood-color':'#000000','flood-opacity':theme==='midnight'?.45:.22},raised);
  var glow=svg('filter',{id:'vf-glow',x:'-100%',y:'-100%',width:'300%',height:'300%'},defs);svg('feDropShadow',{dx:0,dy:0,stdDeviation:5,'flood-color':accent,'flood-opacity':.65},glow);
  var groups=Array.from(scene.children).filter(function(e){return e.tagName.toLowerCase()==='g';});scene.insertBefore(defs,scene.firstChild);
  data.nodes.forEach(function(n,index){var g=groups[index],el=g&&g.firstElementChild;if(!g||!el||!n.attrs)return;
    var app=n.appearance||{},material=['flat','matte','metal','glass','liquid','emissive'].indexOf(app.material)>=0?app.material:'matte';
    var depth=['none','soft','raised'].indexOf(app.depth)>=0?app.depth:'soft';
    var base=hex(n.attrs.fill,null);
    if(n.type==='text'){if(base&&(contrast(base,background)<4.5||contrast(base,highlight)<4.5)){var light='#f4f8ff',dark='#10243b';el.setAttribute('fill',Math.min(contrast(light,background),contrast(light,highlight))>=Math.min(contrast(dark,background),contrast(dark,highlight))?light:dark);}return;}
    if(base&&material!=='flat'){
      var radial=(n.type==='circle'||n.type==='ellipse')&&material!=='metal';
      var gradient=svg(radial?'radialGradient':'linearGradient',radial?{id:'vf-paint-'+index,cx:'32%',cy:'25%',r:'78%'}:{id:'vf-paint-'+index,x1:'0%',y1:'0%',x2:material==='metal'?'100%':'35%',y2:'100%'},defs);
      var stops=material==='metal'?[[0,mix(base,'#ffffff',.55)],[.27,mix(base,'#ffffff',.12)],[.47,mix(base,'#000000',.28)],[.62,mix(base,'#ffffff',.35)],[1,mix(base,'#000000',.35)]]:[[0,mix(base,'#ffffff',material==='emissive'?.7:.48)],[.43,base],[1,mix(base,'#000000',material==='glass'?.18:.35)]];
      stops.forEach(function(stop){svg('stop',{offset:stop[0],'stop-color':stop[1]},gradient);});el.setAttribute('fill','url(#vf-paint-'+index+')');
      if(n.attrs.stroke===undefined){el.setAttribute('stroke',mix(base,'#ffffff',.25));el.setAttribute('stroke-width',.8);}
      if(material==='emissive')el.setAttribute('filter','url(#vf-glow)');else if(depth!=='none')el.setAttribute('filter',depth==='raised'?'url(#vf-raised)':'url(#vf-shadow)');
    }else if(n.type==='line'||n.attrs.fill==='none'){
      if(atmosphere==='technical')el.setAttribute('stroke-linecap','round');
      if(material==='emissive')el.setAttribute('filter','url(#vf-glow)');
    }
    g.setAttribute('data-vf-material',material);
    function select(){groups.forEach(function(other){other.removeAttribute('data-vf-selected');});g.setAttribute('data-vf-selected','true');}
    g.addEventListener('click',select);g.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' ')select();});
    var buttons=document.querySelectorAll('#items button');if(buttons[index])buttons[index].addEventListener('click',function(){select();Array.from(buttons).forEach(function(b){b.setAttribute('aria-pressed','false');});buttons[index].setAttribute('aria-pressed','true');});
  });
  if(atmosphere==='technical'){var grid=mix(background,accent,.12);scene.style.backgroundImage='linear-gradient('+grid+' 1px,transparent 1px),linear-gradient(90deg,'+grid+' 1px,transparent 1px),radial-gradient(ellipse at 42% 36%,'+highlight+','+background+' 72%)';scene.style.backgroundSize='32px 32px,32px 32px,auto';}
  if(atmosphere==='natural'){scene.style.background='linear-gradient(160deg,'+mix(background,accent,.07)+','+background+' 75%)';}
  var reset=document.getElementById('reset');if(reset)reset.addEventListener('click',function(){groups.forEach(function(g){g.removeAttribute('data-vf-selected');});document.querySelectorAll('#items button').forEach(function(b){b.setAttribute('aria-pressed','false');});});
  document.body.setAttribute('data-visual-finish','1');document.body.setAttribute('data-visual-theme',theme);
}
