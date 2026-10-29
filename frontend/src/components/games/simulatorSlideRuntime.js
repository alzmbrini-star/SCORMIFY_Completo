/* Presentation only: preserve the existing engines, IDs, events and model data. */
export function simulatorSlideRuntime() {
  'use strict';
  function mount() {
    if (document.getElementById('sim-slide-shell')) return;
    var planning = document.body.getAttribute('data-sim-engine') === 'entity-planning-v1';
    var rule = document.body.getAttribute('data-sim-engine') === 'finite-rules-v1';
    var ids = planning ? ['title','subtitle','mission','briefing','connection','coverage','score','overload','late','status','chart','tasks','selectedTitle','description','reference','dependencies','start','duration','resource','include','remove','earlier','later','event','reveal','load','violations','save','versions','comparison','restore','extraName','extraDuration','extraDue','addExtra','finalize','reset','report'] : ['title','subtitle','mission','briefing','connection','counter','status','sceneTitle','sceneDescription','facts','metrics','actions','history','result','resultTitle','resultMessage','debrief','save','snapshots','comparison','reset'];
    var nodes = {};
    ids.forEach(function (id) { nodes[id] = document.getElementById(id); });
    if ((!planning && !rule) || ids.some(function (id) { return !nodes[id]; })) return;
    var style = document.createElement('style');
    style.id = 'scormify-simulator-slide-style-v1';
    if (planning) nodes.finalize.setAttribute('aria-label', nodes.finalize.textContent);
    // Compose this ID so legacy substring-based fit detectors don't mistake
    // this responsive document for a fixed-size design stage.
    var legacyStage = ['__', 'stage'].join('');
    style.textContent = '#' + legacyStage + '{display:contents!important;transform:none!important;min-width:0!important;min-height:0!important}' +
      'html,body.sim-slide{margin:0!important;padding:0!important;width:100%!important;height:100%!important;min-height:0!important;overflow:hidden!important;transform:none!important}' +
      'body.sim-slide{background:#0b1426!important;color:#eef5ff;font:16px/1.4 system-ui,sans-serif}' +
      '.sim-slide [hidden]{display:none!important}.sim-slide *{box-sizing:border-box}' +
      '#sim-slide-shell{position:fixed!important;inset:12px!important;display:grid!important;grid-template-rows:auto 86px minmax(0,1fr) 52px;gap:10px;min-width:0;min-height:0;isolation:isolate}' +
      '.sim-slide button,.sim-slide input,.sim-slide select{font:inherit;min-height:40px;border-radius:9px}' +
      '.sim-slide button{padding:8px 12px;border:1px solid #6686a8;background:#1d3856;color:#f4f8ff;font-weight:650;cursor:pointer;line-height:1.25}' +
      '.sim-slide button:hover:not(:disabled){background:#305a7d}.sim-slide button:disabled{opacity:.6;cursor:not-allowed}' +
      '.sim-slide :is(button,input,select,[role="button"]):focus-visible{outline:3px solid #ffd166;outline-offset:2px}' +
      '.sim-head{display:flex;align-items:center;gap:16px;min-height:48px;padding:0!important;background:none!important;color:#f4f8ff}' +
      '.sim-head h1{font-size:clamp(20px,2.4vw,28px)!important;line-height:1.12!important;margin:0!important;min-width:0;flex:1;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}' +
      '.sim-tools{display:flex;gap:6px;flex-shrink:0}.sim-tools button{font-size:14px}.sim-tools #reset{border-color:#7d97b7}' +
      '.sim-metric-strip{display:flex;align-items:stretch;gap:8px;min-height:0}.sim-metric-strip .metrics{display:flex!important;flex:1;gap:8px;margin:0!important;min-width:0}' +
      '.sim-slide .sim-metric-strip .metric{flex:1;min-width:0;cursor:pointer;margin:0!important;padding:8px 12px!important;border:1px solid #496989!important;border-top:3px solid #62daca!important;border-radius:10px!important;background:#152b43!important;color:#eef5ff!important}' +
      '.sim-metric-strip .metric>div:first-child,.sim-metric-strip .metric>span{font-size:14px!important;line-height:1.2;color:#d4e4f6!important;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}' +
      '.sim-metric-strip .metric strong{display:block;font-size:24px!important;line-height:1.1;margin:3px 0!important;color:#fff!important}.sim-metric-strip .metric small{display:none}.sim-metric-strip .track{height:4px!important;margin:4px 0 0!important}.sim-metric-strip .fill{background:#66decb}' +
      '.sim-pager{display:flex;align-items:center;justify-content:center;gap:8px;min-height:36px;flex-shrink:0;font-size:13px;color:#d7e5f7}.sim-pager button{min-width:38px;min-height:36px;padding:6px}.sim-metric-strip>.sim-pager{flex-direction:column;gap:1px}.sim-metric-strip>.sim-pager button{min-height:25px;padding:2px 8px}.sim-metric-strip>.sim-pager span{font-size:11px}' +
      '.sim-main{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:12px;min-width:0;min-height:0}.sim-pane{display:flex;flex-direction:column;min-width:0;min-height:0;border:1px solid #456483;background:#14273e;border-radius:14px;padding:14px;overflow:hidden}' +
      '.sim-pane h2{font-size:18px!important;line-height:1.2;margin:0 0 10px!important;color:#f5f8ff}.sim-pane .sim-pane-head{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-shrink:0}.sim-pane-head button{font-size:13px;min-height:32px;padding:5px 10px}' +
      '.sim-reader{flex:1;min-height:0;overflow:hidden;color:#e4eefb}.sim-reader p{font-size:16px!important;line-height:1.5!important;margin:0 0 10px!important;white-space:pre-wrap}.sim-reader p:last-child{margin-bottom:0!important}.sim-scene{background:linear-gradient(135deg,#173750,#173d49)}' +
      '.sim-action-viewport{flex:1;min-height:0;overflow:hidden}.sim-slide #actions{display:flex!important;flex-direction:column;gap:8px;min-height:0;height:auto;margin:0}' +
      '.sim-slide #actions>.action{display:grid;grid-template-columns:minmax(0,1fr) 36px;gap:7px;flex-shrink:0;margin:0!important;padding:8px!important;border:1px solid #547797;border-radius:10px;background:#1b354f;min-width:0}' +
      '.sim-slide #actions>.action>button:first-child{width:100%;text-align:left;min-height:44px;background:#23546b;font-size:16px;white-space:normal;overflow-wrap:anywhere}.sim-slide #actions>.action>p{display:none}.sim-slide #actions .reason{grid-column:1/-1;font-size:14px;line-height:1.25;margin:0;color:#ffdda9;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.sim-action-detail{padding:4px!important;min-width:36px;align-self:start;grid-column:2;grid-row:1}' +
      '.sim-foot{display:flex;align-items:center;gap:10px;border-top:1px solid #415e7e;padding-top:8px;min-width:0}.sim-foot .sim-feedback{flex:1;min-width:0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:14px;color:#dcebf9}.sim-counter{font-size:13px;color:#9de9dc;white-space:nowrap}.sim-foot button{font-size:14px;flex-shrink:0}.sim-foot #finalize{background:#087a6b}.sim-mobile-tabs{display:none}' +
      'dialog.sim-dialog{width:min(760px,calc(100vw - 32px));max-height:calc(100vh - 32px);padding:0;background:#142a42;color:#f2f7ff;border:1px solid #7193b5;border-radius:16px;box-shadow:0 20px 90px #0009;font:16px/1.5 system-ui,sans-serif}dialog.sim-dialog:not([open]){display:none!important}dialog.sim-dialog::backdrop{background:#020812c9}.sim-dialog-head{display:flex;align-items:center;gap:16px;justify-content:space-between;padding:14px 18px;border-bottom:1px solid #4a6888}.sim-dialog-head h2{font-size:20px;margin:0;color:#fff}.sim-dialog-body{padding:18px;overflow:auto;max-height:calc(100vh - 118px)}.sim-dialog-body p{line-height:1.55;white-space:pre-wrap;margin:0 0 14px}.sim-dialog-body :is(h2,h3,strong,label,small,.muted){color:inherit}.sim-dialog-body :is(h2,h3){font-size:18px}.sim-dialog-body :is(small,label,.muted){font-size:14px}.sim-dialog-body .panel{background:#193650;color:#eef7ff;border-color:#547799;padding:14px;margin:0}.sim-dialog-body :is(input,select){background:#f4f8ff;color:#172b43}.sim-dialog-body .history li{background:#1a3653;color:#fff}.sim-dialog-body .delta span{color:#fff}.sim-dialog-body .comparison{color:#eef8ff}.sim-dialog-body .report{background:#193e56;color:#fff;border-color:#5d9fbd}.sim-dialog-body .warning{color:#ffd0a1}' +
      '.sim-tabs{display:flex;gap:6px;margin-bottom:10px;flex-shrink:0}.sim-tabs button{font-size:14px;flex:1;min-width:0}.sim-tabs button[aria-selected=true]{background:#216779;border-color:#6ad9d0}.sim-pane-content{display:flex;flex-direction:column;flex:1;min-height:0;min-width:0;overflow:hidden}.sim-plan-tasks{flex:1;min-height:0;overflow:hidden}.sim-slide #tasks{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.sim-slide #tasks .task{margin:0!important;padding:10px;background:#1a354f;color:#f4f8ff;border-color:#6383a3;min-width:0}.sim-slide #tasks .task.selected{border:2px solid #74e5cc;padding:9px}.sim-slide #tasks .task strong{font-size:15px;line-height:1.25}.sim-slide #tasks .task small{font-size:13px;color:#d1e1f5;line-height:1.3}.sim-slide #tasks .task .tag{font-size:12px;background:#244d69;color:#e4fbff}.sim-slide #tasks .task button{margin-top:6px;padding:6px 10px;min-height:36px;font-size:14px}' +
      '.sim-chart-wrap{flex:1;min-height:0;overflow:auto!important;border:1px solid #506c89;border-radius:8px;background:#12263b}.sim-slide #chart .axis{background:#1d3d59;color:#eef6ff;font-size:12px}.sim-slide #chart .row-label{font-size:14px;color:#e4efff;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.sim-slide #chart .track{border-color:#47627d;min-height:53px}.sim-slide #chart .bar{font-size:14px;color:#fff;min-height:34px;padding:5px}.sim-slide #chart .lane{height:44px;background:repeating-linear-gradient(90deg,#1b344a 0,#1b344a calc(100% / var(--slots) - 1px),#44617a calc(100% / var(--slots) - 1px),#44617a calc(100% / var(--slots)))}' +
      '.sim-editor{gap:8px;overflow:hidden}.sim-slide .sim-editor .fields{gap:10px}.sim-slide .sim-editor label{font-size:14px;line-height:1.25;color:#d4e5f8;margin:0}.sim-slide .sim-editor input,.sim-slide .sim-editor select{min-height:40px;padding:7px;background:#f7fbff;color:#132a43;border:1px solid #6d8eac;width:100%}.sim-editor .sim-plan-actions{display:flex;gap:8px;margin-top:2px}.sim-plan-actions button{flex:1;min-width:0;font-size:14px}.sim-start-nudge{display:flex;gap:4px;align-items:end}.sim-start-nudge button{padding:4px 7px;min-width:32px;min-height:40px}.sim-start-nudge input{min-width:0}.sim-slide .sim-editor #selectedTitle{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin:0!important;font-size:18px!important}.sim-slide .sim-event{color:#eaf5ff;font-size:16px;line-height:1.5;flex:1;overflow:hidden}.sim-slide .sim-event #event{background:#47371c;color:#fff1c6;border:1px solid #ad8a44;padding:12px;border-radius:10px;display:-webkit-box;-webkit-line-clamp:7;-webkit-box-orient:vertical;overflow:hidden}.sim-event button{margin-top:10px}' +
      '@media(max-height:500px){#sim-slide-shell{inset:8px!important;gap:7px;grid-template-rows:auto 72px minmax(0,1fr) 44px}.sim-head h1{font-size:20px!important}.sim-pane{padding:10px}.sim-pane h2{font-size:17px!important}.sim-metric-strip .metric{padding:6px 10px!important}.sim-metric-strip .metric strong{font-size:22px!important}.sim-metric-strip .track{display:none}.sim-editor{gap:5px}.sim-tabs{margin-bottom:6px}.sim-editor input,.sim-editor select{min-height:36px!important}}' +
      '@media(max-width:700px){#sim-slide-shell{inset:8px!important;gap:8px;grid-template-rows:auto 76px 38px minmax(0,1fr) 48px}.sim-head{gap:6px;flex-direction:column;align-items:stretch}.sim-head h1{font-size:20px!important}.sim-tools{gap:4px}.sim-tools button{flex:1;min-width:0;font-size:12px;padding:6px;min-height:36px}.sim-main{grid-template-columns:minmax(0,1fr)}.sim-mobile-tabs{display:flex;gap:8px}.sim-mobile-tabs button{flex:1;min-height:36px;padding:5px}.sim-mobile-tabs button[aria-selected=true]{background:#216779}.sim-main>.sim-pane:not(.sim-mobile-active){display:none}.sim-foot{gap:6px}.sim-counter{font-size:12px}.sim-foot button{font-size:13px;padding:6px}.sim-metric-strip .metric>div:first-child,.sim-metric-strip .metric>span{font-size:13px!important}}';
    // Grow typography/spacings for large authored canvases (e.g. 1920×820),
    // which the Editor displays at a reduced zoom. Never shrink the UI below
    // its readable 960×540 base. This is reflow, not a document transform.
    style.textContent += '.sim-pane-head h2{min-width:0;flex:1;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.sim-reader p,.sim-dialog-body p,.sim-pane-head h2,.sim-slide #tasks strong{overflow-wrap:anywhere}';
    style.textContent=style.textContent.replace(/\{([^{}]*)\}/g,function(block){return block.replace(/(\d+(?:\.\d+)?)px/g,function(_,value){return 'calc('+value+'px * var(--sim-ui,1))';});});
    var uiScale=1;
    function setUIScale(){uiScale=Math.max(1,Math.min(2,window.innerWidth/960,window.innerHeight/540));document.body.style.setProperty('--sim-ui',String(uiScale));}
    setUIScale();document.head.appendChild(style);
    document.body.classList.add('sim-slide');
    var bank = document.createElement('div'); bank.id = 'sim-slide-sources'; bank.hidden = true;
    var children = Array.prototype.slice.call(document.body.children);
    document.body.appendChild(bank);
    children.forEach(function (child) { if (!/^(SCRIPT|STYLE|LINK)$/.test(child.tagName)) bank.appendChild(child); });
    function make(tag, text, className) { var n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (className) n.className = className; return n; }
    function button(label, action, className) { var n = make('button',label,className);n.type='button';n.onclick=action;return n; }
    var shell=make('div',undefined);shell.id='sim-slide-shell';document.body.appendChild(shell);
    var head=make('header',undefined,'sim-head'), tools=make('nav',undefined,'sim-tools');tools.setAttribute('aria-label','Ferramentas da simulação');
    nodes.title.title=nodes.title.textContent;head.appendChild(nodes.title);head.appendChild(tools);shell.appendChild(head);
    var dialog=make('dialog',undefined,'sim-dialog');dialog.setAttribute('aria-labelledby','sim-dialog-title');
    var dh=make('div',undefined,'sim-dialog-head'), dt=make('h2');dt.id='sim-dialog-title';var db=make('div',undefined,'sim-dialog-body');
    var closeButton=button('Fechar',closeDialog);dh.appendChild(dt);dh.appendChild(closeButton);dialog.appendChild(dh);dialog.appendChild(db);document.body.appendChild(dialog);
    var returns=[], returnFocus=null;
    function closeDialog() {
      returns.forEach(function (entry) { if (entry.next && entry.next.parentNode===entry.parent) entry.parent.insertBefore(entry.node,entry.next);else entry.parent.appendChild(entry.node); });returns=[];
      if (typeof dialog.close==='function' && dialog.open) dialog.close();else dialog.removeAttribute('open');
      shell.removeAttribute('inert');db.replaceChildren();
      var target=returnFocus && returnFocus.isConnected && returnFocus!==document.body && !returnFocus.disabled ? returnFocus : nodes.reset;target.focus();
    }
    function openDialog(title, content, move) {
      if (dialog.open || dialog.hasAttribute('open')) closeDialog();
      returnFocus=document.activeElement;dt.textContent=title;db.replaceChildren();
      (Array.isArray(content)?content:[content]).forEach(function (item) {
        if (typeof item==='string') db.appendChild(make('p',item));
        else if (item) { if (move) { returns.push({node:item,parent:item.parentNode,next:item.nextSibling});db.appendChild(item);if(item.tagName==='DETAILS')item.open=true;}else db.appendChild(item.cloneNode(true)); }
      });
      shell.setAttribute('inert','');
      if (typeof dialog.showModal==='function') dialog.showModal();else dialog.setAttribute('open','');
      closeButton.focus();
    }
    dialog.addEventListener('cancel',function (e) {e.preventDefault();closeDialog();});
    dialog.addEventListener('keydown',function (e) {
      if(e.key==='Escape'){e.preventDefault();closeDialog();}
      if(e.key==='Tab') {var focusable=Array.prototype.filter.call(dialog.querySelectorAll('button,input,select,textarea,[tabindex="0"]'),function(n){return !n.disabled && !n.hidden;});var first=focusable[0],last=focusable[focusable.length-1];if(e.shiftKey && document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey && document.activeElement===last){e.preventDefault();first.focus();}}
    });
    function context() {openDialog('Objetivo e contexto',[nodes.title.textContent,nodes.subtitle.textContent,nodes.mission.textContent,nodes.briefing.textContent,nodes.connection.textContent,'Modelo didático com dados fictícios. Os indicadores não são previsões reais.']);}
    tools.appendChild(button('Objetivo',context));
    var metricStrip=make('section',undefined,'sim-metric-strip');metricStrip.setAttribute('aria-label','Indicadores da simulação');shell.appendChild(metricStrip);
    var metrics=planning?nodes.coverage.closest('.metrics'):nodes.metrics;metricStrip.appendChild(metrics);
    var mobile=make('nav',undefined,'sim-mobile-tabs');mobile.setAttribute('aria-label','Painel principal');mobile.setAttribute('role','tablist');shell.appendChild(mobile);
    var main=make('main',undefined,'sim-main'), left=make('section',undefined,'sim-pane sim-scene sim-mobile-active'), right=make('section',undefined,'sim-pane');main.appendChild(left);main.appendChild(right);shell.appendChild(main);
    function tabKeys(nav){nav.addEventListener('keydown',function(e){var entries=Array.prototype.slice.call(nav.querySelectorAll('[role="tab"]')),index=entries.indexOf(document.activeElement);if(index<0)return;var next;if(e.key==='ArrowRight')next=(index+1)%entries.length;else if(e.key==='ArrowLeft')next=(index+entries.length-1)%entries.length;else if(e.key==='Home')next=0;else if(e.key==='End')next=entries.length-1;else return;e.preventDefault();entries[next].click();entries[next].focus();});}
    function mobileTab(label,pane){var b=button(label,function(){left.classList.toggle('sim-mobile-active',pane===left);right.classList.toggle('sim-mobile-active',pane===right);Array.prototype.forEach.call(mobile.children,function(c){c.setAttribute('aria-selected',String(c===b));});schedule();});b.setAttribute('role','tab');b.setAttribute('aria-selected',String(pane===left));mobile.appendChild(b);}
    tabKeys(mobile);
    mobileTab(planning?'Tarefas / calendário':'Cenário',left);mobileTab(planning?'Editar / imprevisto':'Decisões',right);
    var foot=make('footer',undefined,'sim-foot'), counter=make('span','', 'sim-counter'), feedback=make('span','', 'sim-feedback');
    var resultButton=button('Ver resultado',function(){showResult();});resultButton.hidden=true;
    var feedbackButton=button('Consequência',function(){openDialog('Consequência da decisão',[nodes.status.textContent, !planning && nodes.history.lastElementChild ? nodes.history.lastElementChild.textContent : '']);});
    foot.appendChild(counter);foot.appendChild(feedback);foot.appendChild(feedbackButton);foot.appendChild(resultButton);shell.appendChild(foot);
    var jobs=[], frame=null;
    function schedule(){if(frame!==null)return;frame=requestAnimationFrame(function(){frame=null;jobs.forEach(function(job){job();});});}
    function pager(parent,label) {
      var bar=make('div',undefined,'sim-pager'),state={page:0,total:1};var info=make('span');
      var prev=button('‹',function(){state.page=Math.max(0,state.page-1);schedule();}),next=button('›',function(){state.page=Math.min(state.total-1,state.page+1);schedule();});
      prev.setAttribute('aria-label',label+': página anterior');next.setAttribute('aria-label',label+': próxima página');bar.appendChild(prev);bar.appendChild(info);bar.appendChild(next);parent.appendChild(bar);
      state.update=function(total){state.total=Math.max(1,total);state.page=Math.min(state.page,state.total-1);info.textContent=(state.page+1)+' / '+state.total;prev.disabled=state.page===0;next.disabled=state.page===state.total-1;bar.hidden=state.total===1;};
      return state;
    }
    var mp=pager(metricStrip,'Indicadores');
    function metricText(card){return Array.prototype.map.call(card.children,function(n){return n.textContent.trim();}).filter(Boolean).join(' · ');}
    jobs.push(function(){var cards=Array.prototype.slice.call(metrics.children);var size=Math.max(1,Math.min(6,Math.floor(((metricStrip.clientWidth||940)-80*uiScale)/(145*uiScale))));mp.update(Math.ceil(cards.length/size));cards.forEach(function(card,i){card.hidden=i<mp.page*size||i>=(mp.page+1)*size;if(!card.hasAttribute('data-sim-detail')){card.setAttribute('data-sim-detail','1');card.setAttribute('role','button');card.tabIndex=0;var detail=function(){openDialog('Indicador',metricText(card));};card.onclick=detail;card.onkeydown=function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();detail();}};}card.setAttribute('aria-label','Detalhes do indicador: '+metricText(card));});});
    function paginate(container,viewport,parent,label,columns,selector,rowHeight) {
      var p=pager(parent,label);
      jobs.push(function(){var items=Array.prototype.slice.call(selector?container.querySelectorAll(selector):container.children);items.forEach(function(item){item.hidden=false;});var height=Math.max(40,(viewport.clientHeight||200)-(selector?52*uiScale:0)),pages=[],page=[],used=0,cols=columns||1;for(var i=0;i<items.length;i+=cols){var row=items.slice(i,i+cols),rh=0;row.forEach(function(item){rh=Math.max(rh,item.getBoundingClientRect().height||(rowHeight||70)*uiScale);});if(page.length && used+rh+8*uiScale>height){pages.push(page);page=[];used=0;}page=page.concat(row);used+=rh+(used?8*uiScale:0);}if(page.length)pages.push(page);p.update(pages.length);items.forEach(function(item){item.hidden=(pages[p.page]||[]).indexOf(item)===-1;});});
      return p;
    }
    function readonlyReader(parent,label,getBlocks) {
      var view=make('div',undefined,'sim-reader');parent.appendChild(view);var p=pager(parent,label),last='';var pages=[];
      jobs.push(function(){var blocks=getBlocks().filter(Boolean),key=JSON.stringify(blocks)+'|'+view.clientWidth+'|'+view.clientHeight;
        if(key!==last){last=key;p.page=0;pages=[];var remaining=blocks.join('\n\n');while(remaining){var low=1,high=remaining.length,best=0;while(low<=high){var mid=Math.floor((low+high)/2);view.replaceChildren(make('p',remaining.slice(0,mid)));if((view.scrollHeight<=view.clientHeight+1 && view.clientHeight>0)||(!view.clientHeight && mid<=320)){best=mid;low=mid+1;}else high=mid-1;}best=Math.max(1,best);if(best<remaining.length){var boundary=remaining.lastIndexOf(' ',best);if(boundary>best*.65)best=boundary;}pages.push(remaining.slice(0,best).trim());remaining=remaining.slice(best).trim();}}
        p.update(pages.length);view.replaceChildren(make('p',pages[p.page]||''));
      });
      return view;
    }
    var previousResult=false;
    function showResult(){if(planning)openDialog('Análise do planejamento',nodes.report);else openDialog(nodes.resultTitle.textContent,[nodes.resultMessage.textContent,nodes.debrief.textContent,nodes.history.lastElementChild?nodes.history.lastElementChild.textContent:'']);}
    if(rule) {
      var lh=make('div',undefined,'sim-pane-head'),sceneTitle=make('h2');lh.appendChild(sceneTitle);lh.appendChild(button('Ler tudo',function(){openDialog(nodes.sceneTitle.textContent,[nodes.sceneDescription.textContent,nodes.facts.textContent]);}));left.appendChild(lh);
      readonlyReader(left,'Cenário',function(){return [nodes.sceneDescription.textContent].concat(Array.prototype.map.call(nodes.facts.children,function(li){return '◆ '+li.textContent;}));});
      var rh=make('div',undefined,'sim-pane-head');rh.appendChild(make('h2','Escolha a próxima ação'));right.appendChild(rh);
      var av=make('div',undefined,'sim-action-viewport');av.appendChild(nodes.actions);right.appendChild(av);
      jobs.push(function(){Array.prototype.forEach.call(nodes.actions.children,function(card){if(card.hasAttribute('data-slide-action'))return;card.setAttribute('data-slide-action','1');var original=card.querySelector('button'),description=card.querySelector('p'),reason=card.querySelector('.reason');var info=button('i',function(){openDialog(original.textContent,[description?description.textContent:'',reason?reason.textContent:'']);},'sim-action-detail');info.setAttribute('aria-label','Detalhes: '+original.textContent);card.appendChild(info);});sceneTitle.textContent=nodes.sceneTitle.textContent;counter.title=nodes.counter.textContent;counter.textContent=window.innerWidth<700?nodes.counter.textContent.replace(/Decisão (\d+) de (\d+).*/,'Decisão $1/$2'):nodes.counter.textContent;});
      paginate(nodes.actions,av,right,'Ações',1,null,78);
      var comparisonPanel=nodes.snapshots.closest('section');
      tools.appendChild(button('Versões',function(){openDialog('Comparar estratégias',[nodes.save,comparisonPanel],true);}));
      tools.appendChild(button('Histórico',function(){openDialog('Histórico e consequências',nodes.history);}));
    } else {
      left.classList.remove('sim-scene');
      var tabsLeft=make('nav',undefined,'sim-tabs'),tabsRight=make('nav',undefined,'sim-tabs');left.appendChild(tabsLeft);right.appendChild(tabsRight);
      var tasksView=make('div',undefined,'sim-pane-content'),calendarView=make('div',undefined,'sim-pane-content');left.appendChild(tasksView);left.appendChild(calendarView);
      var taskViewport=make('div',undefined,'sim-plan-tasks');taskViewport.appendChild(nodes.tasks);tasksView.appendChild(taskViewport);paginate(nodes.tasks,taskViewport,tasksView,'Tarefas',2,null,140);
      var chartViewport=make('div',undefined,'sim-chart-wrap');chartViewport.appendChild(nodes.chart);calendarView.appendChild(chartViewport);paginate(nodes.chart,chartViewport,calendarView,'Calendário',1,'.track',53);
      var editView=make('div',undefined,'sim-pane-content sim-editor'),eventView=make('div',undefined,'sim-pane-content sim-event');right.appendChild(editView);right.appendChild(eventView);
      function tabs(nav,entries){nav.setAttribute('role','tablist');tabKeys(nav);entries.forEach(function(entry,index){var b=button(entry.label,function(){entries.forEach(function(other){other.view.hidden=other!==entry;other.button.setAttribute('aria-selected',String(other===entry));});schedule();});entry.button=b;b.setAttribute('role','tab');b.setAttribute('aria-selected',String(index===0));entry.view.hidden=index!==0;nav.appendChild(b);});}
      tabs(tabsLeft,[{label:'Tarefas',view:tasksView},{label:'Calendário',view:calendarView}]);tabs(tabsRight,[{label:'Editar tarefa',view:editView},{label:'Imprevisto',view:eventView}]);
      var editHead=make('div',undefined,'sim-pane-head');editHead.appendChild(nodes.selectedTitle);editHead.appendChild(button('Detalhes',function(){openDialog(nodes.selectedTitle.textContent,[nodes.description.textContent,nodes.reference.textContent,nodes.dependencies.textContent]);}));editView.appendChild(editHead);
      var fields=make('div',undefined,'fields'),startLabel=nodes.start.closest('label'),durationLabel=nodes.duration.closest('label'),resourceLabel=nodes.resource.closest('label');
      var nudge=make('div',undefined,'sim-start-nudge');nodes.earlier.setAttribute('aria-label',nodes.earlier.textContent);nodes.later.setAttribute('aria-label',nodes.later.textContent);nodes.earlier.textContent='−1';nodes.later.textContent='+1';nudge.appendChild(nodes.earlier);nudge.appendChild(nodes.start);nudge.appendChild(nodes.later);startLabel.htmlFor='start';var startGroup=make('div');startGroup.appendChild(startLabel);startGroup.appendChild(nudge);fields.appendChild(startGroup);fields.appendChild(durationLabel);editView.appendChild(fields);editView.appendChild(resourceLabel);
      var pa=make('div',undefined,'sim-plan-actions');pa.appendChild(nodes.include);pa.appendChild(nodes.remove);editView.appendChild(pa);
      eventView.appendChild(nodes.event);eventView.appendChild(nodes.reveal);eventView.appendChild(button('Ler imprevisto completo',function(){openDialog('Imprevisto',nodes.event.textContent);}));
      tools.appendChild(button('Versões',function(){openDialog('Versões e comparação',nodes.versions.closest('section'),true);}));
      tools.appendChild(button('Alertas',function(){openDialog('Alertas e causas',[nodes.load.textContent,nodes.violations]);}));
      var extraButton=button('Extra',function(){openDialog('Adicionar demanda extra',nodes.extraName.closest('details'),true);});extraButton.setAttribute('aria-label','Adicionar demanda extra');tools.appendChild(extraButton);
      foot.appendChild(nodes.finalize);
      jobs.push(function(){counter.textContent=nodes.coverage.textContent+' tarefas'+(window.innerWidth<700?'':' · '+nodes.score.textContent+' viável');nodes.finalize.textContent=window.innerWidth<700?'Analisar':'Analisar meu planejamento';});
    }
    nodes.reset.setAttribute('aria-label',nodes.reset.textContent);nodes.reset.textContent='Reiniciar';tools.appendChild(nodes.reset);nodes.reset.addEventListener('click',function(){previousResult=false;Array.prototype.forEach.call(shell.querySelectorAll('[role="tablist"]'),function(nav){var first=nav.querySelector('[role="tab"]');if(first)first.click();});schedule();});
    jobs.push(function(){feedback.textContent=nodes.status.textContent;feedbackButton.disabled=!nodes.status.textContent.trim();var activeResult=planning?!nodes.report.hidden:!nodes.result.classList.contains('hidden');resultButton.hidden=!activeResult;feedbackButton.hidden=activeResult;if(activeResult && !previousResult)showResult();previousResult=activeResult;});
    var observer=new MutationObserver(schedule);
    [metrics,nodes.status,planning?nodes.chart:nodes.actions,planning?nodes.tasks:nodes.sceneTitle,planning?nodes.report:nodes.sceneDescription,planning?nodes.selectedTitle:nodes.facts,planning?nodes.event:nodes.result].forEach(function(n){var options={childList:true,subtree:true,characterData:true};if(n===nodes.report || n===nodes.result){options.attributes=true;options.attributeFilter=['class','hidden'];}observer.observe(n,options);});
    window.addEventListener('resize',function(){setUIScale();schedule();});
    if(typeof ResizeObserver!=='undefined'){var sizeObserver=new ResizeObserver(schedule);sizeObserver.observe(shell);}
    schedule();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
}
