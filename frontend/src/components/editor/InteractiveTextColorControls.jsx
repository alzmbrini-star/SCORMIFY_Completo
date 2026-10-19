import React from 'react';
import { Button } from '../ui/button';
import { applyInteractiveTextColors, readInteractiveTextColors } from '../../utils/interactiveTextColors';

export default function InteractiveTextColorControls({ element, onUpdate }) {
  const html = element.htmlContent || '';
  if (element.assessmentConfig || !/data-human-simulator-version|data-case-study-version|class=["'][^"']*(?:conversation|dossier)/i.test(html)) return null;
  const colors = readInteractiveTextColors(html);
  const update = next => onUpdate({ htmlContent: applyInteractiveTextColors(html, next) });
  return <div className="panel-section" data-testid="interactive-text-colors">
    <h4 className="text-sm font-medium mb-2">Cores dos textos da atividade</h4>
    <p className="text-xs text-muted-foreground mb-3">Ajuste cada área sem alterar as imagens ou o funcionamento. A mudança também vale para novas falas e para HTML/SCORM exportado.</p>
    {[
      ['title', 'Título e subtítulo', '#f4f4f5'],
      ['scene', 'Conversa / dossiê (área escura)', '#eaf1ff'],
      ['panel', 'Decisões e respostas (área clara)', '#172c49'],
    ].map(([key, label, fallback]) => <label key={key} className="flex items-center justify-between gap-2 mb-3 text-xs">
      <span>{label}{colors[key] ? '' : ' · original'}</span>
      <input type="color" aria-label={label} value={colors[key] || fallback}
        onChange={e => update({ ...colors, [key]: e.target.value })}
        className="w-10 h-8 cursor-pointer rounded border" />
    </label>)}
    <div className="flex flex-wrap gap-2">
      <Button type="button" size="sm" variant="outline" onClick={() => update({ title:'#f4f4f5', scene:'#eaf1ff', panel:'#172c49' })}>Aplicar contraste recomendado</Button>
      <Button type="button" size="sm" variant="outline" disabled={!Object.keys(colors).length} onClick={() => update({})}>Restaurar cores originais</Button>
    </div>
  </div>;
}
