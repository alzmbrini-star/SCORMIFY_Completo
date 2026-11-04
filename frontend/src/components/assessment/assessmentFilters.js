const normalize=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
export function filterAssessmentQuestions(questions,filters,selected=[]) {
  const words=normalize(filters.search).split(/\s+/).filter(Boolean);
  return questions.filter(q=>{
    const text=normalize([q.title,q.prompt,q.category,q.instructions,q.explanation,...(q.options||[]).map(x=>x.text),...(q.items||[]).map(x=>x.text)].join(' '));
    const media=q.media?.kind || 'none';
    return words.every(word=>text.includes(word))&&(!filters.type||q.type===filters.type)&&(!filters.category||q.category===filters.category)&&
      (!filters.media||(filters.media==='alternatives'?[...(q.options||[]),...(q.items||[])].some(x=>x.media?.kind==='image'):filters.media==='failed'?q.imageGenerationStatus==='failed'&&!q.media:media===filters.media))&&
      (!filters.selection||(filters.selection==='selected'?selected.includes(q.id):!selected.includes(q.id)));
  });
}
