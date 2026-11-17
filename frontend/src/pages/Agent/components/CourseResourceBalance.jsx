import React from 'react';
export default function CourseResourceBalance({balance}){
 if(!balance)return null;
 return <section className="rounded-xl border border-emerald-800/40 bg-emerald-950/20 p-4 text-sm" aria-label="Equilíbrio didático">
  <p className="font-semibold text-emerald-200">Equilíbrio didático: sugestões para revisão</p>
  <p className="text-slate-300 mt-2">{balance.explanatorySlides} slides explicativos · {balance.existingResourceSlides} slides de recursos já existentes. Recomendação: aproximadamente 1 complemento a cada 3 slides explicativos, considerando todos os tipos juntos.</p>
  <p className="text-slate-300 mt-2">{balance.selectedSuggestions} sugestões priorizadas e distribuídas pelo curso, mesmo quando já existem recursos. Sugestões são opções, não adições automáticas. Revise possíveis redundâncias com os recursos existentes.</p>
  <p className="text-slate-300 mt-2">Faltam {balance.recommendedAdditions} recursos para atingir a recomendação; isso não bloqueia sugestões. Você pode aplicar até {balance.applicationLimit ?? balance.recommendedAdditions} novos complementos neste lote. O total de recursos não pode ultrapassar {balance.hardMaximumTotal} slides. Cada slide de origem recebe no máximo um novo complemento.</p>
  {balance.applicationLimit === 0 && <p className="text-amber-200 mt-2" role="status">O teto de recursos já foi atingido. As sugestões continuam disponíveis para revisão, mas novas adições estão bloqueadas. Nenhum recurso existente será removido automaticamente.</p>}
  <p className="text-xs text-slate-400 mt-2">Os demais candidatos não viram slides automaticamente. Conteúdos, perguntas e interações existentes permanecem preservados.</p>
 </section>;
}
