import React from 'react';

export function GammaVisualLoading({provider='Gamma'}){
 return <p className="text-xs text-cyan-200 mt-3">Lendo as imagens dos slides {provider} e o texto/notas ou fonte original disponível. Usa créditos de IA; cursos extensos podem levar vários minutos. Nenhum slide é alterado pela análise.</p>;
}
export default function GammaVisualAnalysis({reading}){
 if(!reading)return null;
 return <section className="rounded-xl bg-cyan-950/30 border border-cyan-800/40 p-4 text-sm">
  <p className="font-semibold text-cyan-200" role="status">Leitura visual {reading.provider||'Gamma'}: {reading.readSlides} de {reading.totalSlides} slides lidos</p>
  {reading.provider==='PPT'&&<p className="text-cyan-100 mt-2">{reading.visualSlides||0} com leitura de imagem · {reading.textOnlySlides||0} somente texto/notas</p>}
  <p className="text-slate-300 mt-2">{reading.sourceAvailable?(reading.provider==='PPT'?'Texto extraído e notas do PPT considerados junto às imagens.':'Prompt/documento original considerado junto às imagens.'):reading.originalSourceStored?'A fonte disponível não pôde ser sintetizada; análise baseada nos slides legíveis.':'Fonte original indisponível nesta geração antiga; análise baseada nas imagens legíveis.'} As sugestões são complementos por slide. A imagem-base e as interações existentes serão preservadas; revise a prévia antes de aplicar.</p>
  <details className="mt-3"><summary className="cursor-pointer text-cyan-200">Conferir o conteúdo lido por slide</summary>
   {reading.slides?.map(row=><section key={row.slideId} className="mt-3 border-t border-slate-700 pt-2"><strong>Slide {row.slideIndex+1}</strong>{row.readingMode==='text'&&<p className="text-amber-200">Somente texto/notas; imagem não interpretada.</p>}<p className="text-slate-300 whitespace-pre-wrap">{row.status==='read'?row.summary:'Não foi possível ler a imagem; sem sugestões inventadas.'}</p>{row.status==='read'&&<details><summary className="cursor-pointer text-slate-400">Texto identificado</summary><p className="text-slate-300 whitespace-pre-wrap">{row.visibleText}</p></details>}</section>)}
  </details>
 </section>;
}
