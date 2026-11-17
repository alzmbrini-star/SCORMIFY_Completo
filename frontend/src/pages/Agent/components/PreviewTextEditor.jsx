import React,{useState} from 'react';
import {Button} from '../../../components/ui/button';

export default function PreviewTextEditor({slide,onSave,onCancel}){
 const [selected,setSelected]=useState('resource');
 const [draft,setDraft]=useState({title:slide.editor.title,scenario:slide.editor.scenario});
 const [saving,setSaving]=useState(false);
 const [error,setError]=useState('');
 const questions=slide.editor.questions||[];
 const choose=value=>{
  setSelected(value);setError('');
  const q=questions.find(q=>q.id===value);
  setDraft(q?{prompt:q.prompt,explanation:q.explanation,options:q.options.map(o=>({...o})),...(slide.type==='interactive_assessment'?{title:q.title}:{})}:{title:slide.editor.title,scenario:slide.editor.scenario});
 };
 const field=(label,value,onChange,empty=false)=><label className="block text-sm text-slate-200 mt-3">{label}<textarea aria-label={label} value={value||''} onChange={e=>onChange(e.target.value)} maxLength={8000} required={!empty} className="mt-1 block w-full rounded border border-slate-600 bg-slate-950 p-2" rows={label==='Enunciado'||label==='Explicação'?3:2}/></label>;
 const save=async e=>{
  e.preventDefault();setSaving(true);setError('');
  try{
   const changes={...draft};if(selected==='resource'&&!Object.keys(changes.scenario||{}).length)delete changes.scenario;
   await onSave({afterIndex:slide.afterIndex,type:slide.type,revision:slide.editor.revision,questionId:selected==='resource'?null:selected,changes});
  }catch(err){setError(err.message||'Não foi possível salvar a prévia.');}
  finally{setSaving(false);}
 };
 return <form onSubmit={save} className="rounded-lg border border-cyan-700 bg-slate-900 p-4 mb-3" aria-label="Editar textos da prévia">
  <p className="text-sm text-cyan-200">Salvar altera somente esta prévia. Não usa IA, não aplica mudanças ao curso e preserva imagens, IDs, pontos e correção das alternativas. Revise a coerência das imagens ao mudar o texto.</p>
  <label className="block mt-3 text-sm">Conteúdo a editar<select aria-label="Conteúdo a editar" value={selected} onChange={e=>choose(e.target.value)} disabled={saving} className="block w-full mt-1 bg-slate-950 border border-slate-600 p-2 rounded">
   <option value="resource">Título e roteiro do recurso</option>
   {questions.map((q,i)=><option key={q.id} value={q.id}>{i+1}. {q.prompt}</option>)}
  </select></label>
  <fieldset disabled={saving}>
   {selected==='resource'?<>
    {field('Título do recurso',draft.title,value=>setDraft(d=>({...d,title:value})))}
    {Object.keys(draft.scenario||{}).map(key=><React.Fragment key={key}>{field(key==='theme'?'Tema do cenário':'Objetivos do cenário',draft.scenario[key],value=>setDraft(d=>({...d,scenario:{...d.scenario,[key]:value}})))}</React.Fragment>)}
   </>:<>
    {slide.type==='interactive_assessment'&&field('Título da questão',draft.title,value=>setDraft(d=>({...d,title:value})))}
    {field('Enunciado',draft.prompt,value=>setDraft(d=>({...d,prompt:value})))}
    {draft.options?.map((option,i)=><React.Fragment key={option.id}>{field(`Alternativa ${i+1}`,option.text,value=>setDraft(d=>({...d,options:d.options.map(o=>o.id===option.id?{...o,text:value}:o)})))}{questions.find(q=>q.id===selected)?.correctOptionIds?.includes(option.id)&&<p className="text-xs text-emerald-300">Resposta correta — marcação preservada</p>}</React.Fragment>)}
    {field('Explicação',draft.explanation,value=>setDraft(d=>({...d,explanation:value})),true)}
   </>}
  </fieldset>
  {error&&<p role="alert" className="text-red-300 mt-2">{error}</p>}
  <div className="flex gap-2 mt-3"><Button type="submit" disabled={saving}>{saving?'Salvando…':'Salvar somente na prévia'}</Button><Button type="button" variant="outline" onClick={onCancel} disabled={saving}>Cancelar edição</Button></div>
 </form>;
}
