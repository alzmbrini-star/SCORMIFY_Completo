import React,{useState} from 'react';
import {Button} from './ui/button';

export default function FilmGuidedReview({film,board,locked,busy,dirty,change,sceneChange,save,voices,voiceNotice,loadVoices,suggest,inputClass}){
 const [selected,setSelected]=useState(0);const index=Math.min(selected,board.scenes.length-1),scene=board.scenes[index],review=film.planningReview;
 const ready=board.scenes.every(s=>s.visual.trim()&&s.narration.trim());
 return <section className="rounded-xl border border-cyan-800 p-4 space-y-4" aria-label="Revisão guiada do storyboard">
  <div><h3 className="text-lg font-semibold">2. Veja como o filme será contado</h3><p className="text-sm text-cyan-200">{board.title} · {board.scenes.reduce((n,s)=>n+s.duration,0)}s · {board.style==='3d'?'Animação 3D':'Desenho 2D'} · {board.characters.map(c=>c.name).join(' e ')}</p><p className="text-xs text-slate-300 mt-1">Narração PT-BR sobre as cenas, sem sincronização labial automática. Modelo e ajustes técnicos ficam no Modo avançado.</p></div>
  {film.sourceName&&<details className="rounded bg-slate-950 p-3"><summary className="cursor-pointer text-sm">Fonte: {film.sourceName} — texto utilizado</summary><p className="text-xs text-amber-200 my-2">{film.sourceWarning}</p><pre className="whitespace-pre-wrap break-words max-h-52 overflow-y-auto text-xs">{film.sourceText}</pre></details>}
  {review&&<div className="rounded bg-teal-950/50 border border-teal-800 p-3 text-sm space-y-2"><strong>Resumo e cobertura do conteúdo</strong><p>{review.summary}</p>
   {review.revision!==film.revision&&<p className="text-xs text-amber-200">A versão foi editada após esta análise. Se houve mudança de conteúdo, confira novamente a cobertura antes de aprovar.</p>}
   <details><summary className="cursor-pointer">Tópicos contemplados ({review.coveredTopics?.length||0})</summary><ul className="list-disc pl-5 mt-2">{review.coveredTopics?.map((t,i)=><li key={i}>{t}</li>)}</ul></details>
   {!!review.notCoveredTopics?.length&&<div className="text-amber-200"><strong>Ficou fora deste filme:</strong><ul className="list-disc pl-5">{review.notCoveredTopics.map((t,i)=><li key={i}>{t}</li>)}</ul></div>}
   {review.warnings?.map((t,i)=><p key={i} className="text-amber-200">{t}</p>)}
  </div>}
  {!ready&&<div className="rounded border border-amber-700 p-3"><p className="text-sm mb-2">As cenas ainda precisam de conteúdo. O rascunho está preservado; preparar com IA usa somente créditos de texto.</p><Button disabled={locked||dirty||Object.keys(film.operations||{}).length>0} onClick={suggest}>Preparar cenas com IA — créditos de texto</Button></div>}
  <div className="grid sm:grid-cols-2 gap-2" aria-label="Sequência de cenas">{board.scenes.map((s,i)=><button type="button" key={i} onClick={()=>setSelected(i)} aria-pressed={index===i} className={'text-left rounded border p-3 text-sm '+(index===i?'border-cyan-400 bg-cyan-950':'border-slate-700 bg-slate-950')}><span className="text-xs text-cyan-300">Cena {i+1} · {s.duration}s</span><strong className="block">{s.title}</strong></button>)}</div>
  <fieldset disabled={locked} className="rounded border border-slate-600 p-3 space-y-3"><legend className="px-2 text-sm">Revisar cena {index+1}</legend>
   <label className="block text-sm">Título<input aria-label="Título da cena em revisão" className={inputClass} maxLength={100} value={scene.title} onChange={e=>sceneChange(index,{title:e.target.value})}/></label>
   <label className="block text-sm">O que será mostrado<textarea aria-label="Visual da cena em revisão" className={inputClass} maxLength={600} rows={3} value={scene.visual} onChange={e=>sceneChange(index,{visual:e.target.value})}/></label>
   <label className="block text-sm">O que será falado<textarea aria-label="Narração da cena em revisão" className={inputClass} maxLength={scene.duration===5?55:110} rows={3} value={scene.narration} onChange={e=>sceneChange(index,{narration:e.target.value})}/></label>
   <p className="text-xs text-slate-300">Quem fala: {scene.speaker==='narrator'?'Narrador':board.characters[Number(scene.speaker.slice(-1))-1]?.name} · {scene.narration.length}/{scene.duration===5?55:110} caracteres. O áudio será medido antes de gerar o vídeo.</p>
   <Button variant="outline" disabled={busy} onClick={loadVoices}>Carregar vozes PT-BR — sem síntese</Button>
   {voiceNotice&&<p role="status" className="text-xs text-cyan-200">{voiceNotice}</p>}
   <label className="block text-sm">Voz da narração<select aria-label="Voz da narração guiada" className={inputClass} value={board.narratorVoice} onChange={e=>change({narratorVoice:e.target.value})}><option value="">Selecione uma voz PT-BR</option>{board.narratorVoice&&!voices.some(v=>v.id===board.narratorVoice)&&<option value={board.narratorVoice}>Voz salva — verificar no catálogo</option>}{voices.filter(v=>v.brazilian).map(v=><option key={v.id} value={v.id}>{v.name} · PT-BR</option>)}</select></label>
   <label className="flex gap-2 text-sm"><input type="checkbox" checked={board.music} onChange={e=>change({music:e.target.checked})}/>Incluir trilha instrumental suave, reduzida durante as falas</label>
   <Button disabled={!dirty||locked} onClick={save}>Salvar revisão — invalida aprovações anteriores</Button>
  </fieldset>
  <p className="text-xs text-slate-300">Só depois de revisar e salvar: aprove o storyboard, confira o orçamento e autorize as mídias. Nenhuma dessas ações substitui seu curso original.</p>
 </section>;
}
