import React from 'react';
import { Search, X } from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
export const emptyFilters={search:'',type:'',category:'',media:'',selection:''};
export default function AssessmentBankFilters({filters,onChange,questions,count,types}) {
  const set=patch=>onChange(previous=>({...previous,...patch}));
  const categories=[...new Set(questions.map(q=>q.category).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'pt-BR'));
  const select=(key,label,options)=><label className="text-xs font-medium">{label}<select className="mt-1 h-10 w-full rounded-md border bg-background px-2 text-sm" aria-label={label} value={filters[key]} onChange={e=>set({[key]:e.target.value})}><option value="">Todos</option>{options.map(([id,title])=><option key={id} value={id}>{title}</option>)}</select></label>;
  return <section aria-label="Filtros do Banco de Avaliações" className="my-3 space-y-3 rounded-lg border bg-muted/20 p-3">
    <label className="flex items-center gap-2"><Search className="h-4 w-4 shrink-0"/><Input aria-label="Buscar questões" value={filters.search} onChange={e=>set({search:e.target.value})} placeholder="Buscar no título, enunciado ou alternativas…"/></label>
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {select('type','Tipo de questão',Object.entries(types))}
      {select('category','Categoria da questão',categories.map(c=>[c,c]))}
      {select('media','Material de apoio',[['image','Imagem na pergunta'],['alternatives','Imagem nas alternativas'],['video','Vídeo'],['document','Documento'],['none','Sem material de apoio'],['failed','Imagem não gerada']])}
      {select('selection','Seleção',[['selected','Selecionadas'],['unselected','Não selecionadas']])}
    </div><div className="flex items-center justify-between gap-2"><p className="text-sm text-muted-foreground" role="status">{count} de {questions.length} questões</p><Button type="button" variant="ghost" size="sm" onClick={()=>onChange({...emptyFilters})} disabled={!Object.values(filters).some(Boolean)}><X className="mr-1 h-3 w-3"/>Limpar filtros</Button></div>
  </section>;
}
