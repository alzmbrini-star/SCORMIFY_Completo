// Serialized into offline games. Keep all dependencies inside this function.
export function battleRuntime(Game, BANK, QE, stage, SETTINGS) {
  if (!Game || Game.battleVersion === 1) return;
  Game.battleVersion = 1;
  let epoch = 0, transition = null, finished = false;
  const original = {start:Game.start,restart:Game.restart,end:Game.end,sync:Game.sync,renderAdventure:Game.renderAdventure};
  if (!document.getElementById('battle-style-v1')) {
    const style = document.createElement('style'); style.id = 'battle-style-v1';
    style.textContent = `
      #playScreen{overflow-y:auto}
      .battle-layout{width:min(100%,900px);grid-template-columns:310px minmax(0,1fr)}
      .battle-layout .battle-scene{display:block;height:350px;min-height:350px}
      .battle-bars{position:absolute;left:16px;right:16px;top:18px;display:grid;grid-template-columns:1fr 1fr;gap:16px;z-index:2}
      .battle-stat{padding:8px;border:1px solid #94a3b84d;border-radius:12px;background:#0b1634e6}
      .battle-label{font-size:11px;line-height:1.3;display:block;color:#dbeafe}
      .battle-value{display:block;font-size:22px;font-weight:900;color:#f8fafc;margin:4px 0}
      .battle-energy{height:13px;border-radius:8px;background:#450a0a;overflow:hidden}
      .battle-energy i{display:block;height:100%;width:100%;background:#34d399;transition:width .6s ease,background-color .6s ease}
      .battle-scene .fighter{top:146px;font-size:66px;line-height:1.2;animation:battle-idle 2.3s ease-in-out infinite}
      .battle-scene .hero{left:27px}.battle-scene .enemy{right:27px;animation-delay:.5s}
      .battle-caption{position:absolute;top:236px;font-size:12px;font-weight:800;padding:5px 10px;border-radius:8px;background:#0b1634d9;color:#f1f5f9}
      .battle-caption.hero-name{left:36px}.battle-caption.enemy-name{right:18px}
      .battle-message{position:absolute;bottom:14px;left:14px;right:14px;min-height:48px;display:grid;place-items:center;text-align:center;padding:9px;border-radius:12px;background:#0b1634ed;border:1px solid #94a3b84d;font-size:12px;line-height:1.4;color:#e2e8f0}
      .battle-scene .battle-attack-right{animation:battle-attack-right .6s ease both}
      .battle-scene .battle-attack-left{animation:battle-attack-left .6s ease both}
      .battle-scene .battle-impact{animation:battle-impact .7s .25s ease both}
      .battle-projectile{position:absolute;top:177px;left:95px;font-size:30px;z-index:3;pointer-events:none;animation:battle-shot-right .6s ease both}
      .battle-projectile.from-enemy{left:190px;animation-name:battle-shot-left}
      .battle-damage{position:absolute;top:134px;font-size:24px;font-weight:950;color:#fecaca;z-index:4;animation:battle-damage 1s ease both}
      .battle-damage.to-enemy{right:44px}.battle-damage.to-hero{left:44px}
      @keyframes battle-idle{50%{transform:translateY(-5px)}}
      @keyframes battle-attack-right{40%{transform:translateX(25px) rotate(-8deg)}100%{transform:none}}
      @keyframes battle-attack-left{40%{transform:translateX(-25px) rotate(8deg)}100%{transform:none}}
      @keyframes battle-impact{25%,65%{transform:translateX(8px);filter:brightness(1.8)}45%,85%{transform:translateX(-8px)}100%{transform:none}}
      @keyframes battle-shot-right{0%{opacity:0;transform:translateX(0) scale(.6)}30%{opacity:1}100%{opacity:0;transform:translateX(100px) scale(1.2)}}
      @keyframes battle-shot-left{0%{opacity:0;transform:translateX(0) scale(.6)}30%{opacity:1}100%{opacity:0;transform:translateX(-100px) scale(1.2)}}
      @keyframes battle-damage{0%{opacity:0;transform:translateY(0)}25%{opacity:1}100%{opacity:0;transform:translateY(-28px)}}
      @media(max-width:800px){.battle-layout{grid-template-columns:minmax(0,1fr);width:100%}.battle-layout .battle-scene{width:310px;max-width:100%;margin:auto}.battle-layout .card{min-height:280px}}
      @media(prefers-reduced-motion:reduce){.battle-scene *{animation:none!important;transition:none!important}.battle-projectile,.battle-damage{display:none}}
    `;
    document.head.appendChild(style);
  }
  function cancel() { epoch++;clearTimeout(transition);transition=null;clearInterval(Game.tick); }
  function energy() {
    for (const side of ['hero','enemy']) {
      const value=Math.max(0,Math.min(100,Number(side==='hero'?Game.heroHealth:Game.enemyHealth)));
      const bar=stage.querySelector('.battle-energy[data-side="'+side+'"]');
      if(!bar)continue;
      bar.setAttribute('aria-valuenow',String(value));
      const fill=bar.querySelector('i');fill.style.width=value+'%';fill.style.background=value>40?'#34d399':value>20?'#fbbf24':'#f87171';
      bar.parentElement.querySelector('.battle-value').textContent=value+'%';
    }
  }
  Game.sync = function () {original.sync.call(this);energy();};
  Game.renderAdventure = function () {
    original.renderAdventure.call(this);
    stage.querySelector('.layout')?.classList.add('battle-layout');
    const scene=stage.querySelector('.scene');if(!scene)return;
    scene.classList.add('battle-scene');
    scene.innerHTML='<div class="battlefield"></div><div class="battle-bars">'+
      ['hero','enemy'].map(side=>'<div class="battle-stat"><span class="battle-label">'+(side==='hero'?'Sua energia':'Energia do adversário')+'</span><strong class="battle-value">100%</strong><div class="battle-energy" role="progressbar" aria-label="'+(side==='hero'?'Sua energia':'Energia do adversário')+'" aria-valuemin="0" aria-valuemax="100" aria-valuenow="100" data-side="'+side+'"><i></i></div></div>').join('')+
      '</div><div class="fighter hero" role="img" aria-label="Seu personagem">🧙</div><div class="fighter enemy" role="img" aria-label="Adversário">🤖</div><span class="battle-caption hero-name">Você</span><span class="battle-caption enemy-name">Adversário</span><div class="battle-message" role="status" aria-live="polite">Acerte para atacar. Erros ou tempo esgotado causam um contra-ataque.</div>';
    energy();
  };
  function resolve(question,index,button,timeout) {
    if(Game.locked || finished || !question)return;
    Game.locked=true;clearInterval(Game.tick);
    stage.querySelectorAll('.answer').forEach(answer=>{answer.disabled=true;});
    const ok=!timeout && QE.validateAnswer(question,index);
    if(button)button.classList.add(ok?'correct':'wrong');
    if(ok){Game.correct++;Game.xp+=125;Game.coins+=15;Game.enemyHealth=Math.max(0,Game.enemyHealth-20);Game.burst();}
    else{Game.lives=Math.max(0,Game.lives-1);Game.heroHealth=Math.max(0,Game.heroHealth-20);}
    const message=ok?'Você atacou! Adversário perdeu 20 de energia.':timeout?'Tempo esgotado! Você perdeu 20 de energia e uma vida.':'Contra-ataque! Você perdeu 20 de energia e uma vida.';
    const feedback=stage.querySelector('.feedback');if(feedback)feedback.textContent=message+' '+(question.explanation||'');
    const scene=stage.querySelector('.battle-scene');
    if(scene){
      scene.querySelector(ok?'.hero':'.enemy')?.classList.add(ok?'battle-attack-right':'battle-attack-left');
      scene.querySelector(ok?'.enemy':'.hero')?.classList.add('battle-impact');
      scene.querySelector('.battle-message').textContent=message;
      const shot=document.createElement('span');shot.className='battle-projectile'+(ok?'':' from-enemy');shot.textContent=ok?'🔮':'⚡';shot.setAttribute('aria-hidden','true');scene.appendChild(shot);
      const damage=document.createElement('span');damage.className='battle-damage '+(ok?'to-enemy':'to-hero');damage.textContent='−20';damage.setAttribute('aria-hidden','true');scene.appendChild(damage);
    }
    const result={questionId:question.id,correct:ok,type:SETTINGS.type,at:Date.now()};
    if(timeout)result.reason='timeout';QE.saveResult(result);
    Game.index++;Game.sync();
    const token=epoch;
    transition=setTimeout(()=>{
      if(token!==epoch || finished)return;
      transition=null;Game.locked=false;Game.render();if(!finished)Game.resetTimer();
    },1200);
  }
  Game.answer = function (question,index,button) {resolve(question,index,button,false);};
  Game.resetTimer = function () {
    clearInterval(this.tick);this.seconds=Number(SETTINGS.time)||30;this.sync();if(finished)return;
    const token=epoch;
    this.tick=setInterval(()=>{
      if(token!==epoch || finished || this.locked)return;
      this.seconds=Math.max(0,this.seconds-1);this.sync();
      if(this.seconds===0)resolve(BANK[this.index],null,null,true);
    },1000);
  };
  Game.start = function () {cancel();finished=false;this.locked=false;original.start.call(this);};
  Game.restart = function () {cancel();finished=false;this.locked=false;original.restart.call(this);};
  Game.end = function () {if(finished)return;cancel();finished=true;original.end.call(this);};
}
