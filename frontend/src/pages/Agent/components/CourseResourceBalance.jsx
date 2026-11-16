import React from 'react';
export default function CourseResourceBalance({balance}){
 if(!balance)return null;
 return <section className="rounded-xl border border-emerald-800/40 bg-emerald-950/20 p-4 text-sm" aria-label="Equilíbrio didático">
  <p className="font-semibold text-emerald-200">Equilíbrio didático: até {balance.recommendedAdditions} novos complementos</p>
  <p className="text-slate-300 mt-2">{balance.explanatorySlides} slides explicativos · {balance.existingResourceSlides} slides de recursos já existentes. Recomendação: aproximadamente 1 complemento a cada 3 slides explicativos, considerando todos os tipos juntos.</p>
  <p className="text-slate-300 mt-2">{balance.selectedSuggestions} sugestões priorizadas e distribuídas pelo curso. O total de recursos não pode ultrapassar {balance.hardMaximumTotal} slides. Cada slide de origem recebe no máximo um novo complemento.</p>
  <p className="text-xs text-slate-400 mt-2">Os demais candidatos não viram slides automaticamente. Conteúdos, perguntas e interações existentes permanecem preservados.</p>
 </section>;
}
