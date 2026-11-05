import React, {useEffect,useState} from 'react';
import { Button } from '../ui/button';
import { applyEditorialTextColors, readEditorialTextColors } from '../../utils/editorialTextColors';
import {readEditorialColorSnapshot} from '../../utils/editorialColorProbe';

export default function EditorialTextColorControls({element,onUpdate}) {
  const html = element.htmlContent || '';
  // Structured conversations retain their dedicated regional controls.
  // All other HTML, including scripted activities, can receive CSS-only edits.
  const dedicated = !element.assessmentConfig && /data-human-simulator-version|data-case-study-version|class=["'][^"']*(?:conversation|dossier)/i.test(html);
  const [observed,setObserved]=useState(null),[choosing,setChoosing]=useState(null);
  useEffect(()=>{
    setObserved(null);setChoosing(null);
    if(dedicated)return;
    const requestId='colors-'+Math.random().toString(36).slice(2);
    let frame;
    const request=()=>{
      const canvas=document.querySelector('[data-testid="slide-canvas"]');
      const host=[...(canvas?.querySelectorAll('[data-testid]')||[])].find(n=>n.dataset.testid==='element-'+element.id);
      frame=host?.querySelector('iframe');
      frame?.contentWindow?.postMessage({type:'scormify-editorial-color-request',requestId},'*');
    };
    const receive=event=>{
      const groups=readEditorialColorSnapshot(event,frame,requestId);
      if(groups)setObserved(previous=>JSON.stringify(previous)===JSON.stringify(groups)?previous:groups);
    };
    window.addEventListener('message',receive);request();const poll=setInterval(request,900);
    return ()=>{clearInterval(poll);window.removeEventListener('message',receive);frame?.contentWindow?.postMessage({type:'scormify-editorial-color-request',requestId,action:'stop'},'*');};
  },[element.id,html,dedicated]);
  if(dedicated)return null;
  const colors = element.assessmentConfig?.textColors || readEditorialTextColors(html);
  const update = next => onUpdate({htmlContent:applyEditorialTextColors(html,next),
    ...(element.assessmentConfig ? {assessmentConfig:{...element.assessmentConfig,textColors:next}} : {})});
  return <div className="panel-section" data-testid="editorial-text-colors">
    <h4 className="text-sm font-medium mb-2">Cores dos textos</h4>
    <p className="text-xs text-muted-foreground mb-3">Ajuste títulos, texto geral e cartões/itens do bloco selecionado. As amostras mostram as cores da prévia; cores variadas são indicadas. Alterar uma cor unifica os itens correspondentes e vale para novos cartões e HTML/SCORM, sem mudar a lógica ou as imagens.</p>
    {[
      ['title','Títulos','#f4f4f5'], ['text','Texto geral','#e2e8f0'],
      ['card','Texto dos cartões e itens','#172c49'], ['cardBackground','Fundo dos cartões e itens','#ffffff'],
    ].map(([key,label,fallback]) => {
      const sample=observed?.[key], actual=sample?.colors?.[0];
      const mixed=sample&&(sample.colors.length>1||sample.complex);
      const mismatch=actual&&colors[key]&&colors[key].toLowerCase()!==actual.toLowerCase();
      return <div key={key} className="flex items-center justify-between gap-2 mb-3 text-xs">
        <div><span>{label}</span><small className="block text-muted-foreground">
          {!sample?'Aguardando leitura da prévia':!sample.count?'Nenhum item visível correspondente':mixed?'Cores variadas / fundo não sólido — a mudança unifica este grupo':actual?`Exibida: ${actual}`:'Transparente ou não identificada'}
          {mismatch?' · configuração antiga não refletida; reaplique a cor':''}
        </small></div>
        {actual||choosing===key ? <input aria-label={label} title={mixed?'Amostra de uma das cores exibidas; alterar unifica o grupo':choosing===key&&!actual?'Nova cor a aplicar':actual} type="color" value={actual||colors[key]||fallback} className="w-10 h-8 cursor-pointer rounded border"
          onChange={e => update({...colors,[key]:e.target.value})} />
          : <Button type="button" aria-label={`Definir cor: ${label}`} size="sm" variant="outline" onClick={()=>setChoosing(key)}>Definir cor</Button>}
      </div>;
    })}
    <div className="flex flex-wrap gap-2">
      <Button type="button" size="sm" variant="outline" onClick={() => update({title:'#f4f4f5',text:'#e2e8f0',card:'#172c49',cardBackground:'#ffffff'})}>Contraste para fundo escuro</Button>
      <Button type="button" size="sm" variant="outline" onClick={() => update({title:'#172c49',text:'#172c49',card:'#172c49',cardBackground:'#ffffff'})}>Contraste para fundo claro</Button>
      <Button type="button" size="sm" variant="outline" disabled={!Object.keys(colors).length} onClick={() => update({})}>Restaurar cores originais</Button>
    </div>
  </div>;
}
