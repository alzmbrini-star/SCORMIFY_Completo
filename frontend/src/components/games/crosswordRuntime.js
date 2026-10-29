// Serialized into offline game documents. Do not reference module scope.
export function crosswordRuntime(Game, BANK, QE, stage) {
  if (!Game || Game.crosswordVersion === 4) return;
  Game.crosswordVersion = 4;
  const originalStart=Game.start, originalRestart=Game.restart, originalEnd=Game.end, originalTimer=Game.resetTimer;
  let ended=false, successTimer=null;
  function resetReview() {
    ended=false;Game.locked=false;clearTimeout(successTimer);
    document.getElementById('crossword-review')?.remove();
    document.getElementById('crossword-reveal')?.remove();
  }
  Game.start=function(){resetReview();return originalStart.call(this);};
  Game.restart=function(){resetReview();return originalRestart.call(this);};
  Game.resetTimer=function(){
    originalTimer.call(this);clearInterval(this.tick);
    this.tick=setInterval(()=>{
      if(ended || this.locked)return;
      this.seconds=Math.max(0,this.seconds-1);this.sync();
      if(this.seconds===0)this.end();
    },1000);
  };
  Game.end=function(){
    if(ended)return;
    ended=true;this.locked=true;clearTimeout(successTimer);
    originalEnd.call(this);
    if(this.correct===BANK.length)return;
    const finish=document.querySelector('#finishScreen .finish');if(!finish || !this.cross)return;
    const reveal=document.createElement('button');reveal.id='crossword-reveal';reveal.className='cta';reveal.type='button';
    reveal.textContent='REVELAR RESPOSTAS PARA ESTUDAR';
    reveal.onclick=()=>{
      if(document.getElementById('crossword-review'))return;
      const review=document.createElement('section');review.id='crossword-review';
      const heading=document.createElement('h2');heading.textContent='Gabarito para aprendizagem';
      const note=document.createElement('p');note.textContent='Consulta sem pontos: revelar as respostas não altera o resultado desta tentativa.';
      review.append(heading,note);
      const board=stage.querySelector('.cross-board')?.cloneNode(true);
      if(board){board.querySelectorAll('input.cell').forEach(input=>{const wasCorrect=input.value.toUpperCase()===input.dataset.solution;input.value=input.dataset.solution;input.readOnly=true;input.style.background=wasCorrect?'#6ee7b7':'#fde68a';input.setAttribute('aria-label',input.getAttribute('aria-label')+': '+input.value);});review.appendChild(board);}
      const list=document.createElement('ol');
      this.cross.placements.slice().sort((a,b)=>a.number-b.number||Number(a.vertical)-Number(b.vertical)).forEach(p=>{
        const item=document.createElement('li');
        const answer=p.q.alternatives?.[QE.correct(p.q)]?.text || p.word;
        item.textContent='Dica '+p.number+' · '+(p.vertical?'Vertical':'Horizontal')+': '+p.clue+' — '+answer+(p.target ? ' · Palavra na grade: '+p.target : '');
        list.appendChild(item);
      });
      review.appendChild(list);finish.appendChild(review);reveal.disabled=true;reveal.textContent='RESPOSTAS REVELADAS';
    };
    finish.appendChild(reveal);
  };
  const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase().replace(/[^A-Z]/g, '');
  function entry(q) {
    const answer=String(q.alternatives?.[QE.correct(q)]?.text || q.correctAnswer || '').trim();
    const tokens=Array.from(answer.matchAll(/[A-Za-zÀ-ÖØ-öø-ÿ]+/g));
    // Short terms (including compound terms) fit intact. Long sentences become
    // an explicit completion clue, never an arbitrary prefix of the answer.
    if(normalize(answer).length>24 && tokens.length>1){
      const token=tokens.slice().sort((a,b)=>normalize(b[0]).length-normalize(a[0]).length)[0];
      const target=token[0];
      const completion=answer.slice(0,token.index)+'_____'+answer.slice(token.index+target.length);
      return {q,word:normalize(target),target,clue:q.question+' Complete a resposta: '+completion};
    }
    return {q,word:normalize(answer),target:'',clue:q.question};
  }
  Game.word=function(q){return entry(q).word;};
  if (!document.getElementById('crossword-style-v4')) {
    const style = document.createElement('style'); style.id = 'crossword-style-v4';
    style.textContent = `
      #playScreen{overflow-y:auto}
      .cross-wrap{width:min(100%,940px);display:grid;grid-template-columns:minmax(0,1.35fr) minmax(260px,1fr);gap:16px;align-items:start}
      .cross-board{min-width:0;overflow:auto;border-radius:20px}
      .cross-grid{width:max-content;grid-template-columns:repeat(var(--cross-size),28px);grid-template-rows:repeat(var(--cross-size),28px);gap:2px;padding:12px;margin:auto}
      .cross-cell{position:relative;width:28px;height:28px;background:#f8fafc;border-radius:4px;color:#0f172a}
      .cross-cell .cell{width:100%;height:100%;padding:7px 1px 0;border:1px solid #94a3b8;border-radius:4px;background:transparent;color:#0f172a;font-size:17px;line-height:1;font-weight:900;outline-offset:-2px}
      .cross-grid>.cell.block{width:28px;height:28px}
      .cross-number{position:absolute;left:3px;top:1px;font-size:9px;line-height:10px;font-weight:900;pointer-events:none;color:#0f172a;z-index:1}
      .cross-cell.word-active{background:#cffafe;box-shadow:inset 0 0 0 2px #0891b2}
      .cross-cell:focus-within{outline:3px solid #fbbf24;outline-offset:-2px;z-index:2}
      .cross-wrap .clues{display:block!important;min-width:0;max-height:412px;overflow:auto;padding:16px}
      .cross-instructions{font-size:12px;color:#cbd5e1;line-height:1.5;margin:0 0 12px}
      .cross-clue{display:block;width:100%;text-align:left;padding:10px;margin-bottom:8px;border:1px solid #64748b;border-radius:10px;background:#172440;color:#f8fafc;font:inherit;cursor:pointer}
      .cross-clue strong{display:block;font-size:13px;color:#a5f3fc;margin-bottom:5px}.cross-clue span{font-size:12px;line-height:1.4;display:block}
      .cross-clue[aria-pressed=true]{border:2px solid #22d3ee;background:#164e63}
      .cross-status{min-height:28px;font-size:12px;line-height:1.5;margin:10px 0;color:#e2e8f0}
      #finishScreen{overflow-y:auto;align-items:flex-start;padding:24px}#finishScreen .finish{margin:auto;max-height:none}
      #crossword-reveal{display:block;margin:16px auto}#crossword-review{text-align:left;color:#f8fafc;background:#172440;padding:16px;border-radius:16px;margin-top:16px}
      #crossword-review p,#crossword-review li{color:#f8fafc;line-height:1.6}#crossword-review .cross-board{overflow:auto}#crossword-review li{margin:12px 0}
      @media(max-width:800px){.cross-wrap{grid-template-columns:minmax(0,1fr);width:100%}.cross-wrap .clues{max-height:none}.cross-board{width:100%}.cross-grid{padding:10px}.cross-wrap .cta{width:100%}}
    `;
    document.head.appendChild(style);
  }
  Game.makeCross = function () {
    const words = BANK.slice(0,6).map(entry).filter(p => p.word);
    const size = words.reduce((max,p)=>Math.max(max,p.word.length+2),13), grid = Array(size * size).fill(''), placements = [], axes = Array.from({length:size*size}, () => new Set());
    function valid(word,row,col,vertical) {
      const dr = vertical ? 1 : 0, dc = vertical ? 0 : 1;
      const at = (r,c) => r >= 0 && c >= 0 && r < size && c < size ? grid[r*size+c] : '';
      if (row < 0 || col < 0 || row+dr*(word.length-1) >= size || col+dc*(word.length-1) >= size || at(row-dr,col-dc) || at(row+dr*word.length,col+dc*word.length)) return false;
      for (let k=0;k<word.length;k++) {
        const r=row+dr*k,c=col+dc*k,pos=r*size+c;
        if (grid[pos]) { if (grid[pos] !== word[k] || axes[pos].has(vertical)) return false; }
        else if (at(r-dc,c-dr) || at(r+dc,c+dr)) return false;
      }
      return true;
    }
    function place(p,row,col,vertical) {
      const cells = Array.from(p.word, (_,k) => (row+(vertical?k:0))*size+col+(vertical?0:k));
      cells.forEach((pos,k) => {grid[pos]=p.word[k];axes[pos].add(vertical);});
      placements.push(Object.assign({},p,{row,col,vertical,cells}));
    }
    for (const p of words) {
      let candidate = null;
      for (const previous of placements) {
        for (let a=0;a<p.word.length && !candidate;a++) for (let b=0;b<previous.word.length && !candidate;b++) {
          if (p.word[a] !== previous.word[b]) continue;
          const vertical=!previous.vertical, row=previous.row+(previous.vertical?b:0)-(vertical?a:0), col=previous.col+(previous.vertical?0:b)-(vertical?0:a);
          if (valid(p.word,row,col,vertical)) candidate={row,col,vertical};
        }
        if (candidate) break;
      }
      if (!placements.length) candidate={row:6,col:Math.floor((size-p.word.length)/2),vertical:false};
      if (!candidate) for (let r=0;r<size && !candidate;r++) for (let c=0;c<size && !candidate;c++) {
        if (valid(p.word,r,c,false)) candidate={row:r,col:c,vertical:false};
        else if (valid(p.word,r,c,true)) candidate={row:r,col:c,vertical:true};
      }
      if (candidate) place(p,candidate.row,candidate.col,candidate.vertical);
    }
    // If a crowded grid cannot fit every clue, retain all words in separate
    // rows instead of silently dropping a clue or overwriting a crossing.
    if (placements.length !== words.length) {
      grid.fill('');placements.length=0;axes.forEach(a=>a.clear());
      words.forEach((p,i)=>place(p,i*2,Math.floor((size-p.word.length)/2),false));
    }
    let number=0; const starts=new Map();
    placements.slice().sort((a,b)=>a.row-b.row||a.col-b.col).forEach(p=>{
      const start=p.row*size+p.col;
      if (!starts.has(start)) starts.set(start,++number);
      p.number=starts.get(start);
    });
    return {version:4,size,grid,placements,starts};
  };
  Game.renderCrossword = function () {
    if (!this.cross || this.cross.version !== 4) this.cross=this.makeCross();
    const c=this.cross; let active=null;
    stage.innerHTML='<div class="cross-wrap"><div class="cross-board glass"><div class="cross-grid"></div></div><div class="clues glass"><h3>Dicas numeradas</h3><p class="cross-instructions">Clique em uma dica para destacar a palavra. O número na primeira casa corresponde à dica. Digite sem acentos, espaços ou hífens: o cursor avança sozinho. Nas dicas com lacuna, digite somente a palavra que falta. Em cruzamentos, use Enter para trocar a direção.</p><div class="cross-clue-list"></div><p class="cross-status" role="status" aria-live="polite"></p></div></div>';
    const board=stage.querySelector('.cross-grid'), clues=stage.querySelector('.cross-clue-list'), status=stage.querySelector('.cross-status'), inputs=new Map(), buttons=new Map();
    board.style.setProperty('--cross-size',c.size);
    const wordsAt = pos => c.placements.filter(p=>p.cells.includes(pos));
    function activate(p) {
      active=p;
      inputs.forEach((input,pos)=>input.parentElement.classList.toggle('word-active',!!p && p.cells.includes(pos)));
      buttons.forEach((button,word)=>button.setAttribute('aria-pressed',String(word===p)));
      status.textContent=p ? 'Dica '+p.number+' · '+(p.vertical?'Vertical ↓':'Horizontal →')+' · '+p.word.length+' letras' : '';
    }
    function focus(pos) { const input=inputs.get(pos); if(input){input.focus();input.select();} }
    function move(pos,delta) {
      if(!active)return;
      const index=active.cells.indexOf(pos), next=index+delta;
      if(next>=0 && next<active.cells.length) focus(active.cells[next]);
    }
    c.grid.forEach((letter,pos)=>{
      if(!letter){const block=document.createElement('i');block.className='cell block';board.appendChild(block);return;}
      const wrapper=document.createElement('div');wrapper.className='cross-cell';
      if(c.starts.has(pos)){const number=document.createElement('span');number.className='cross-number';number.textContent=c.starts.get(pos);wrapper.appendChild(number);}
      const input=document.createElement('input');input.className='cell';input.maxLength=1;input.dataset.solution=letter;input.dataset.position=pos;
      input.autocomplete='off';input.spellcheck=false;input.setAttribute('autocapitalize','characters');
      input.setAttribute('aria-label',wordsAt(pos).map(p=>'Dica '+p.number+' '+(p.vertical?'vertical':'horizontal')+', letra '+(p.cells.indexOf(pos)+1)).join('; '));
      input.onfocus=()=>{if(!active || !active.cells.includes(pos))activate(wordsAt(pos)[0]);};
      input.oninput=event=>{if(event.isComposing)return;input.value=normalize(input.value).slice(-1);if(input.value)move(pos,1);};
      input.oncompositionend=()=>{input.value=normalize(input.value).slice(-1);if(input.value)move(pos,1);};
      input.addEventListener('paste',event=>{
        const text=normalize(event.clipboardData?.getData('text') || '');if(!text)return;
        event.preventDefault();if(!active)activate(wordsAt(pos)[0]);
        const start=active.cells.indexOf(pos);let last=pos;
        Array.from(text).slice(0,active.cells.length-start).forEach((ch,i)=>{last=active.cells[start+i];inputs.get(last).value=ch;});
        focus(last);move(last,1);
      });
      input.onkeydown=event=>{
        if(event.key==='Enter' || event.key===' '){event.preventDefault();const words=wordsAt(pos);activate(words[(words.indexOf(active)+1)%words.length]);return;}
        if(event.key.startsWith('Arrow')){
          event.preventDefault();const vertical=event.key==='ArrowUp'||event.key==='ArrowDown';
          const word=wordsAt(pos).find(p=>p.vertical===vertical);if(!word)return;activate(word);
          move(pos,event.key==='ArrowUp'||event.key==='ArrowLeft'?-1:1);return;
        }
        if(event.key==='Backspace'){event.preventDefault();if(input.value)input.value='';else{move(pos,-1);if(document.activeElement!==input)document.activeElement.value='';}return;}
        if(event.key==='Delete'){event.preventDefault();input.value='';return;}
        if(event.key==='Home'||event.key==='End'){event.preventDefault();if(active)focus(active.cells[event.key==='Home'?0:active.cells.length-1]);}
      };
      inputs.set(pos,input);wrapper.appendChild(input);board.appendChild(wrapper);
    });
    c.placements.slice().sort((a,b)=>a.number-b.number||Number(a.vertical)-Number(b.vertical)).forEach(p=>{
      const button=document.createElement('button');button.type='button';button.className='cross-clue';button.setAttribute('aria-pressed','false');
      const label=document.createElement('strong');label.textContent=p.number+'. '+(p.vertical?'Vertical ↓':'Horizontal →')+' · '+p.word.length+' letras';
      const question=document.createElement('span');question.textContent=p.clue;
      button.append(label,question);button.onclick=()=>{activate(p);focus(p.cells.find(pos=>!inputs.get(pos).value) ?? p.cells[0]);};
      buttons.set(p,button);clues.appendChild(button);
    });
    const validate=document.createElement('button');validate.className='cta';validate.textContent='VALIDAR CRUZADINHA';validate.onclick=()=>this.validateCross();
    stage.querySelector('.clues').appendChild(validate);
    activate(c.placements.slice().sort((a,b)=>a.number-b.number)[0]);
  };
  Game.validateCross = function () {
    if(this.locked)return;
    const cells=Array.from(stage.querySelectorAll('input.cell'));if(!cells.length)return;
    const ok=cells.every(cell=>cell.value.toUpperCase()===cell.dataset.solution);
    cells.forEach(cell=>cell.style.background=cell.value.toUpperCase()===cell.dataset.solution?'#6ee7b7':'#fca5a5');
    if(ok){this.locked=true;clearInterval(this.tick);this.correct=BANK.length;this.xp+=500;this.coins+=60;this.index=BANK.length;this.sync();this.burst();successTimer=setTimeout(()=>this.end(),700);}
    else{this.lives--;this.sync();stage.querySelector('.cross-status').textContent='Revise as casas em vermelho e tente novamente.';if(this.lives<=0)this.end();}
  };
}
