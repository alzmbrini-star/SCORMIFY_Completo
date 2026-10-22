import React from 'react';
import { Button } from '../ui/button';
import { applyEditorialTextColors, readEditorialTextColors } from '../../utils/editorialTextColors';

export default function EditorialTextColorControls({element,onUpdate}) {
  const html = element.htmlContent || '';
  // Only editorial text blocks, never interactive players or arbitrary scripts.
  if (element.assessmentConfig || /<script\b|data-human-simulator-version|data-case-study-version/i.test(html) || !/<(?:h[1-4]|p|li)\b/i.test(html)) return null;
  const colors = readEditorialTextColors(html);
  const update = next => onUpdate({htmlContent:applyEditorialTextColors(html,next)});
  return <div className="panel-section" data-testid="editorial-text-colors">
    <h4 className="text-sm font-medium mb-2">Cores do resumo / texto</h4>
    <p className="text-xs text-muted-foreground mb-3">Ajuste o bloco selecionado. Os cartões são os itens da lista do resumo. As alterações ficam salvas e acompanham HTML/SCORM.</p>
    {[
      ['title','Títulos','#f4f4f5'], ['text','Texto geral','#e2e8f0'],
      ['card','Texto dos cartões','#172c49'], ['cardBackground','Fundo dos cartões','#ffffff'],
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
