import React, { act, useState } from 'react';
import { createRoot } from 'react-dom/client';
import ImageShadowControls from './ImageShadowControls';
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
test('presets, custom controls and None patch only the selected image metadata',async()=>{
  const container=document.createElement('div');document.body.append(container);const root=createRoot(container),update=jest.fn();
  function Host(){const [element,set]=useState({id:'image-1',src:'original.png',x:30,width:400});return <ImageShadowControls element={element} onUpdate={patch=>{update(patch);set(e=>({...e,...patch}));}}/>;}
  const change=async(selector,value)=>act(async()=>{const el=container.querySelector(selector);const proto=el.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(el,value);el.dispatchEvent(new Event('change',{bubbles:true}));el.dispatchEvent(new Event('input',{bubbles:true}));});
  try{
    await act(async()=>root.render(<Host/>));
    expect(container.querySelector('input[type="color"]').disabled).toBe(true);
    await change('select[aria-label="Sombra da imagem"]','soft');
    expect(update.mock.lastCall[0].imageShadow.preset).toBe('soft');
    expect(container.querySelector('input[type="color"]').disabled).toBe(false);
    await change('select[aria-label="Tipo de sombra"]','frame');
    expect(update.mock.lastCall[0].imageShadow).toMatchObject({preset:'custom',mode:'frame'});
    await change('select[aria-label="Sombra da imagem"]','none');
    expect(update.mock.lastCall[0].imageShadow.preset).toBe('none');
    expect(update.mock.calls.every(([patch])=>Object.keys(patch).join(',')==='imageShadow')).toBe(true);
  }finally{await act(async()=>root.unmount());container.remove();}
});
