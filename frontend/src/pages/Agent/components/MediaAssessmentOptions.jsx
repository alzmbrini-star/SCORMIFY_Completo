import React from 'react';

export function assessmentMediaSettings(slide, media = {}, defaultImages = true) {
  const planned = slide.assessmentRequest || (slide.guidedActivity?.questions ? {questionCount:slide.guidedActivity.questions.length,images:defaultImages} : null);
  return media.interactiveAssessment || {enabled: !!planned,
    questionCount: planned?.questionCount || 3, images: planned?.images !== false};
}

export function assessmentMediaSummary(storyboard, mediaConfig) {
  return (storyboard?.slides || []).reduce((total,slide,index)=>{
    const settings=assessmentMediaSettings(slide,mediaConfig[String(index)] || {},storyboard.guidedPath?.assessmentImages !== false);
    if (settings.enabled) {
      const count=slide.guidedActivity?.questions?.length || settings.questionCount;
      total.assessments+=1; total.questions+=count;
      if(settings.images)total.images+=count;
    }
    return total;
  },{assessments:0,questions:0,images:0});
}

export default function MediaAssessmentOptions({slide, media, onChange, defaultImages=true}) {
  const guided = !!slide.guidedActivity?.questions;
  if (!guided && !slide.assessmentRequest && !['content','quiz'].includes(slide.type)) return null;
  const settings = assessmentMediaSettings(slide, media, defaultImages);
  const update = values => onChange({...settings, ...values});
  return <section className="rounded-lg border border-teal-500/40 bg-teal-950/30 p-3 space-y-3" aria-label="Avaliações interativas com imagens">
    {guided ? <strong className="text-sm text-teal-200">Avaliação interativa do percurso</strong> : <label className="flex gap-2 items-center text-sm text-teal-100"><input type="checkbox" checked={settings.enabled} onChange={e=>update({enabled:e.target.checked})}/>{slide.type === 'quiz' ? 'Converter este Quiz em Avaliação interativa' : slide.assessmentRequest ? 'Incluir esta Avaliação interativa' : 'Acrescentar Avaliação interativa após este slide'}</label>}
    {(guided || settings.enabled) && <>
      {!guided && <label className="block text-sm">Quantidade de questões<input aria-label="Quantidade de questões da avaliação" type="number" min="1" max="10" value={settings.questionCount} onChange={e=>update({questionCount:Number(e.target.value)})} className="ml-3 w-20 rounded border border-slate-600 bg-slate-900 p-1"/></label>}
      <label className="flex gap-2 items-center text-sm"><input type="checkbox" checked={settings.images} onChange={e=>update({images:e.target.checked})}/>Gerar imagem IA para cada questão</label>
      <p className="text-xs text-amber-200">Usa créditos na geração do curso, não ao marcar esta opção. Imagens no material de apoio e na biblioteca; questões no Banco. Falhas de imagem não apagam as questões. Conteúdo e capturas originais são preservados.</p>
      {!slide.assessmentRequest && !guided && <p className="text-xs text-slate-300">As questões serão geradas com base no conteúdo desta tela ao confirmar Mídia. Revise a avaliação no Editor antes de distribuir.</p>}
    </>}
  </section>;
}
