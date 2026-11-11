import React from 'react';

export default function StoryboardLearningContext({slide}) {
  if(slide.guidedActivity) return <aside className="rounded-lg border border-teal-500/40 bg-teal-950/40 p-3 text-sm text-teal-100" data-testid="guided-storyboard-resource">
    <strong>{{practice:'Prática orientada com cartões de revisão',assessment:'Avaliação interativa da unidade',final:'Avaliação interativa final',project:'Projeto integrador com autoverificação'}[slide.guidedActivity.kind]}</strong>
    <p>{slide.guidedActivity.instructions}</p>
    {slide.guidedActivity.questions && <p>{slide.guidedActivity.questions.length} questões no mesmo player de Avaliações interativas do Editor. Imagens de apoio serão geradas na etapa Gerar curso, se habilitadas, consumindo créditos e ficando disponíveis na biblioteca.</p>}
    {slide.guidedActivity.deliverables && <p>{slide.guidedActivity.deliverables.length} entregas com critérios de revisão. Os textos não são avaliados automaticamente nem enviados ao instrutor pelo LMS.</p>}
  </aside>;
  if (slide.sourceImageOnly) return (
    <aside className="rounded-lg border border-sky-500/40 bg-sky-950/50 p-3 text-sm text-sky-100" data-testid="storyboard-original-image">
      <strong>Imagem original preservada</strong>
      <p>Captura da ementa, ligada a esta unidade. Será incluída no curso sem recriação por IA nem custo de geração de imagem.</p>
    </aside>
  );
  const image = slide.imageSuggestion;
  if (!slide.isComplement && !slide.sourceRequired && !image) return null;
  return (
    <aside className="space-y-2 rounded-lg border border-teal-500/40 bg-teal-950/40 p-3 text-sm text-teal-100" data-testid="storyboard-learning-context">
      {slide.sourceRequired && <p><strong>Ensino obrigatório da fonte</strong> — os complementos não substituem esta explicação.</p>}
      {slide.isComplement && <>
        <strong>Complemento didático</strong>
        <p>{slide.learningRationale}</p>
        {!!slide.reinforcesSourceRefs?.length && <details>
          <summary className="cursor-pointer">Assuntos da fonte reforçados por esta atividade</summary>
          <p className="mt-1 break-words text-xs">{slide.reinforcesSourceRefs.join(' · ')}</p>
        </details>}
      </>}
      {image && <details data-testid="storyboard-image-suggestion">
        <summary className="cursor-pointer font-medium">Imagem complementar sugerida — revisar em Mídia</summary>
        <p className="mt-2">{image.purpose}</p>
        <p className="mt-2 break-words text-xs text-teal-200">{image.prompt}</p>
        <p className="mt-2 text-xs">É uma proposta, não uma imagem já gerada. Escolha ou desative a mídia na próxima etapa; gerar uma nova imagem pode consumir créditos.</p>
      </details>}
    </aside>
  );
}
