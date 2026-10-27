import React from 'react';
import { Button } from '../ui/button';
import { applyEditorialTextColors, readEditorialTextColors } from '../../utils/editorialTextColors';

export default function EditorialTextColorControls({element,onUpdate}) {
  const html = element.htmlContent || '';
  // Structured conversations retain their dedicated regional controls.
  // All other HTML, including scripted activities, can receive CSS-only edits.
  if (!element.assessmentConfig && /data-human-simulator-version|data-case-study-version|class=["'][^"']*(?:conversation|dossier)/i.test(html)) return null;
  const colors = element.assessmentConfig?.textColors || readEditorialTextColors(html);
  const update = next => onUpdate({htmlContent:applyEditorialTextColors(html,next),
    ...(element.assessmentConfig ? {assessmentConfig:{...element.assessmentConfig,textColors:next}} : {})});
  return <div className="panel-section" data-testid="editorial-text-colors">
    <h4 className="text-sm font-medium mb-2">Cores dos textos</h4>
    <p className="text-xs text-muted-foreground mb-3">Ajuste títulos, textos e listas do bloco selecionado, em qualquer slide. As cores ficam salvas e acompanham HTML/SCORM, sem alterar imagens, pontuação ou funcionamento. Textos dentro de imagens e vídeos não são alterados.</p>
    {[
      ['title','Títulos','#f4f4f5'], ['text','Texto geral','#e2e8f0'],
      ['card','Texto dos itens de lista','#172c49'], ['cardBackground','Fundo dos itens de lista','#ffffff'],
    ].map(([key,label,fallback]) => <label key={key} className="flex items-center justify-between gap-2 mb-3 text-xs">
      <span>{label}{colors[key] ? '' : ' · original'}</span>
      <input aria-label={label} type="color" value={colors[key] || fallback} className="w-10 h-8 cursor-pointer rounded border"
        onChange={e => update({...colors,[key]:e.target.value})} />
    </label>)}
    <div className="flex flex-wrap gap-2">
      <Button type="button" size="sm" variant="outline" onClick={() => update({title:'#f4f4f5',text:'#e2e8f0',card:'#172c49',cardBackground:'#ffffff'})}>Contraste para fundo escuro</Button>
      <Button type="button" size="sm" variant="outline" onClick={() => update({title:'#172c49',text:'#172c49',card:'#172c49',cardBackground:'#ffffff'})}>Contraste para fundo claro</Button>
      <Button type="button" size="sm" variant="outline" disabled={!Object.keys(colors).length} onClick={() => update({})}>Restaurar cores originais</Button>
    </div>
  </div>;
}
