import React from 'react';
import { imageShadowPreset } from '../../utils/imageShadow';

export default function ImageShadowControls({element,onUpdate}) {
  const shadow={...imageShadowPreset(element.imageShadow?.preset || 'none'),...element.imageShadow};
  const change=(key,value)=>onUpdate({imageShadow:{...shadow,preset:'custom',[key]:value}});
  const disabled=shadow.preset==='none';
  return <section className="panel-section space-y-3" aria-label="Sombra da imagem">
    <h4 className="text-sm font-medium">Sombra da imagem</h4>
    <label className="block text-xs">Intensidade predefinida
      <select aria-label="Sombra da imagem" className="w-full mt-1 rounded border bg-background p-2" value={shadow.preset} onChange={e=>onUpdate({imageShadow:{...imageShadowPreset(e.target.value),mode:shadow.mode}})}>
        <option value="none">Nenhuma</option><option value="soft">Suave</option><option value="medium">Média</option><option value="strong">Forte</option>
        {shadow.preset==='custom' && <option value="custom">Personalizada</option>}
      </select>
    </label>
    <label className="block text-xs">Tipo de sombra
      <select aria-label="Tipo de sombra" className="w-full mt-1 rounded border bg-background p-2" disabled={disabled} value={shadow.mode} onChange={e=>change('mode',e.target.value)}>
        <option value="contour">Contorno da imagem — inclui transparência</option><option value="frame">Moldura retangular</option>
      </select>
    </label>
    <details><summary className="cursor-pointer text-xs">Personalizar cor e posição</summary><div className="space-y-3 pt-3">
    <label className="flex items-center justify-between text-xs">Cor da sombra<input type="color" aria-label="Cor da sombra" disabled={disabled} value={shadow.color} onChange={e=>change('color',e.target.value)} /></label>
    {[['opacity','Intensidade',0,70,'%'],['blur','Suavidade',0,60,'px'],['x','Deslocamento horizontal',-40,40,'px'],['y','Deslocamento vertical',-40,40,'px']].map(([key,label,min,max,unit])=><label key={key} className="block text-xs">{label} · {shadow[key]}{unit}
      <input className="w-full" type="range" aria-label={label} disabled={disabled} min={min} max={max} step="1" value={shadow[key]} onChange={e=>change(key,Number(e.target.value))} />
    </label>)}
    </div></details>
    <p className="text-xs text-muted-foreground">Efeito reversível, sem alterar a imagem original. Aparece no Visualizar e em novas exportações HTML/SCORM. Nas bordas do slide, a sombra pode ser recortada.</p>
  </section>;
}
