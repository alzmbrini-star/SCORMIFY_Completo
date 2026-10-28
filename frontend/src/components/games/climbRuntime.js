// Serialized into offline game documents. All dependencies must be local.
export function climbRuntime(Game, BANK, QE, stage, SETTINGS) {
  if(!Game || Game.climbVersion===1)return;
  Game.climbVersion=1;
  let epoch=0,pending=null,finished=false;
  const original={start:Game.start,restart:Game.restart,end:Game.end,sync:Game.sync,renderAdventure:Game.renderAdventure};
  const percent=()=>Math.max(0,Math.min(100,Math.round(Game.correct/Math.max(1,BANK.length)*100)));
  if(!document.getElementById('climb-style-v1')){
    const style=document.createElement('style');style.id='climb-style-v1';
    style.textContent=`
      #playScreen{overflow-y:auto}
      .climb-layout{width:min(100%,900px);grid-template-columns:310px minmax(0,1fr)}
      .climb-layout .climb-scene{display:block;height:350px;min-height:350px;background:#0c2440}
      .climb-art{position:absolute;inset:0;width:100%;height:100%}
      .climb-avatar{position:absolute;left:13%;top:80%;font-size:40px;line-height:1;transform:translate(-50%,-50%);transition:left .9s ease,top .9s ease;z-index:2}
      .climb-avatar span{display:block;filter:drop-shadow(0 3px 3px #0008)}
      .climb-avatar .climb-step{animation:climb-step .8s ease}
      .climb-avatar .climb-slip{animation:climb-slip .65s ease}
      .climb-flag{position:absolute;right:10%;top:5%;font-size:28px}
      .climb-meter{position:absolute;left:12px;top:12px;padding:8px 10px;border-radius:10px;background:#08182de8;border:1px solid #7dd3fc88;color:#f0f9ff;font-size:12px;font-weight:800;z-index:3}
      .climb-status{position:absolute;left:12px;right:12px;bottom:10px;padding:9px;border-radius:10px;min-height:44px;background:#08182df2;color:#e0f2fe;border:1px solid #64748b;font-size:12px;line-height:1.4;text-align:center;z-index:3}
      .climb-status.miss{border-color:#f87171;color:#fecaca}.climb-status.success{border-color:#34d399;color:#bbf7d0}
      .climb-question-progress{font-size:12px;color:#bae6fd;margin:0 0 12px;text-align:center;font-weight:800}
      @keyframes climb-step{25%,75%{transform:rotate(-9deg) translateY(-4px)}50%{transform:rotate(9deg)}}
      @keyframes climb-slip{25%,75%{transform:translateX(-6px)}50%{transform:translateX(6px);filter:drop-shadow(0 0 8px #f87171)}}
      @media(max-width:800px){.climb-layout{grid-template-columns:minmax(0,1fr);width:100%}.climb-layout .climb-scene{width:310px;max-width:100%;margin:auto}.climb-layout .card{min-height:280px}}
      @media(prefers-reduced-motion:reduce){.climb-avatar,.climb-avatar span{animation:none!important;transition:none!important}}
    `;
    document.head.appendChild(style);
  }
  function cancel(){epoch++;clearTimeout(pending);pending=null;clearInterval(Game.tick);}
  function update(){
    const p=percent(),avatar=stage.querySelector('.climb-avatar'),meter=stage.querySelector('.climb-meter');
    if(avatar){avatar.style.left=(13+p*.72)+'%';avatar.style.top=(80-p*.64)+'%';avatar.setAttribute('aria-label','Alpinista: '+p+'% da subida');}
    if(meter){meter.textContent='Subida: '+p+'% · '+Game.correct+'/'+BANK.length+' acertos';meter.setAttribute('aria-valuenow',String(p));}
    const bar=document.getElementById('bar');if(bar){bar.style.width=p+'%';bar.parentElement.setAttribute('role','progressbar');bar.parentElement.setAttribute('aria-label','Subida conquistada por acertos');bar.parentElement.setAttribute('aria-valuemin','0');bar.parentElement.setAttribute('aria-valuemax','100');bar.parentElement.setAttribute('aria-valuenow',String(p));}
  }
  Game.sync=function(){original.sync.call(this);update();};
  Game.scene=function(){
    return '<div class="scene climb-scene"><svg class="climb-art" viewBox="0 0 300 350" preserveAspectRatio="none" aria-hidden="true"><rect width="300" height="350" fill="#164e73"/><path d="M0 350L255 46L300 98V350Z" fill="#475569"/><path d="M0 350L255 46L190 211L118 350Z" fill="#64748b"/><path d="M218 91L255 46L281 79L265 73L253 91L243 80Z" fill="#e2e8f0"/><path d="M39 280L255 56" stroke="#a5f3fc" stroke-width="3" stroke-dasharray="5 7" fill="none"/></svg><span class="climb-flag" aria-label="Topo da montanha">🏁</span><div class="climb-avatar" role="img"><span>🧗</span></div><div class="climb-meter" role="progressbar" aria-label="Subida por acertos" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div><div class="climb-status" role="status" aria-live="polite">Acerte para subir. Erros ou tempo esgotado custam uma vida e não avançam a subida.</div></div>';
  };
  Game.renderAdventure=function(){
    original.renderAdventure.call(this);stage.querySelector('.layout')?.classList.add('climb-layout');
    const counter=document.createElement('p');counter.className='climb-question-progress';counter.textContent='Pergunta '+Math.min(this.index+1,BANK.length)+' de '+BANK.length;
    stage.querySelector('.card')?.prepend(counter);update();
  };
  Game.render=function(){this.sync();if(this.lives<=0 || this.index>=BANK.length)return this.end();this.renderAdventure();};
  function resolve(q,index,button,timeout){
    if(Game.locked || finished || !q)return;
    Game.locked=true;clearInterval(Game.tick);stage.querySelectorAll('.answer').forEach(b=>{b.disabled=true;});
    const ok=!timeout && QE.validateAnswer(q,index);
    if(button)button.classList.add(ok?'correct':'wrong');
    if(ok){Game.correct++;Game.xp+=125;Game.coins+=15;Game.burst();}else Game.lives=Math.max(0,Game.lives-1);
    const message=ok?'Acertou! Você subiu uma etapa.':timeout?'Tempo esgotado: −1 vida. A subida não avançou.':'Resposta incorreta: −1 vida. A subida não avançou.';
    const feedback=stage.querySelector('.feedback');if(feedback)feedback.textContent=message+' '+(q.explanation||'');
    const status=stage.querySelector('.climb-status');if(status){status.textContent=message;status.classList.add(ok?'success':'miss');}
    stage.querySelector('.climb-avatar span')?.classList.add(ok?'climb-step':'climb-slip');
    const result={questionId:q.id,correct:ok,type:SETTINGS.type,at:Date.now()};if(timeout)result.reason='timeout';QE.saveResult(result);
    Game.index++;Game.sync();const token=epoch;
    pending=setTimeout(()=>{if(token!==epoch || finished)return;pending=null;Game.locked=false;Game.render();if(!finished)Game.resetTimer();},1200);
  }
  Game.answer=function(q,index,button){resolve(q,index,button,false);};
  Game.resetTimer=function(){
    clearInterval(this.tick);this.seconds=Number(SETTINGS.time)||30;this.sync();if(finished)return;
    const token=epoch;
    this.tick=setInterval(()=>{if(token!==epoch || finished || this.locked)return;this.seconds=Math.max(0,this.seconds-1);this.sync();if(!this.seconds)resolve(BANK[this.index],null,null,true);},1000);
  };
  Game.start=function(){cancel();finished=false;this.locked=false;original.start.call(this);};
  Game.restart=function(){cancel();finished=false;this.locked=false;original.restart.call(this);};
  Game.end=function(){
    if(finished)return;cancel();finished=true;original.end.call(this);
    const text=document.getElementById('finishText');if(text)text.textContent+=' Subida conquistada: '+percent()+'%.'+(percent()===100?' Topo alcançado!':' Acerte todas as perguntas para alcançar o topo.');
  };
}
