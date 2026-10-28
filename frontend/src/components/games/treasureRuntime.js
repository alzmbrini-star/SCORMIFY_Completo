// Serialized into offline game documents; no module-scope dependencies.
export function treasureRuntime(Game, BANK, QE, stage) {
  if (!Game || Game.treasureVersion === 1) return;
  Game.treasureVersion = 1;
  Game.treasureResults = [];
  const original = {answer:Game.answer,sync:Game.sync,renderAdventure:Game.renderAdventure,restart:Game.restart};
  if (!document.getElementById('treasure-style-v1')) {
    const style=document.createElement('style');style.id='treasure-style-v1';
    style.textContent=`
      .map .route .node.correct{opacity:1;background:#15803d;border-color:#bbf7d0;color:#fff;box-shadow:none}
      .map .route .node.missed{opacity:1;background:#b91c1c;border-color:#fecaca;color:#fff;box-shadow:none}
      .map .route .node.current{background:#713f12;border-color:#fde68a;color:#fff}
      .map-legend{position:absolute;bottom:12px;left:12px;right:12px;padding:7px 6px;border-radius:9px;background:#422006e8;color:#fff;text-align:center;font-size:11px;line-height:1.4;font-weight:800}
    `;
    document.head.appendChild(style);
  }
  function paint() {
    // The original timeout advances the index without calling answer().
    // Such completed, unrecorded stages are misses, never successes.
    for(let i=0;i<Math.min(Game.index,BANK.length);i++) {
      if(Game.treasureResults[i] === undefined)Game.treasureResults[i]=false;
    }
    stage.querySelectorAll('.map .route .node').forEach((node,index)=>{
      const result=Game.treasureResults[index];
      node.classList.remove('open','correct','missed','current');
      let status;
      if(result===true){node.classList.add('open','correct');node.textContent='✓';status='resposta correta';}
      else if(result===false){node.classList.add('missed');node.textContent='✕';status='resposta incorreta ou tempo esgotado';}
      else{if(index===Game.index)node.classList.add('current');node.textContent=index===BANK.length-1?'💎':'?';status=index===Game.index?'etapa atual':'não respondida';}
      const label='Etapa '+(index+1)+': '+status;
      node.setAttribute('role','img');node.setAttribute('aria-label',label);node.title=label;
    });
    const map=stage.querySelector('.map');
    if(map && !map.querySelector('.map-legend')){
      const legend=document.createElement('div');legend.className='map-legend';legend.textContent='✓ Acerto · ✕ Erro / tempo esgotado · ? Pendente';map.appendChild(legend);
    }
  }
  Game.answer=function(question,index,button){
    if(this.locked)return;
    this.treasureResults[this.index]=QE.validateAnswer(question,index);
    original.answer.call(this,question,index,button);paint();
  };
  Game.sync=function(){original.sync.call(this);paint();};
  Game.renderAdventure=function(){original.renderAdventure.call(this);paint();};
  Game.restart=function(){this.treasureResults=[];original.restart.call(this);};
}
