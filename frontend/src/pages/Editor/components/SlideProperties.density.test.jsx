import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import {SlideProperties} from './SlideProperties';
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
let mockDensity;
jest.mock('../../../components/DensitySuggestionsDialog',()=>props=>{mockDensity=props;return null;});
jest.mock('../dialogs/BrandLibraryPicker',()=>()=>null);
jest.mock('../../../components/editor/TextShadowControls',()=>()=>null);
jest.mock('sonner',()=>({toast:{success:jest.fn(),error:jest.fn()}}));
jest.mock('../../../components/ui/input',()=>({Input:props=><input {...props}/>}));
jest.mock('../../../components/ui/switch',()=>({Switch:()=>null}));
jest.mock('../../../components/ui/button',()=>({Button:({children,variant,size,...props})=><button {...props}>{children}</button>}));

let root,container;
beforeEach(()=>{container=document.createElement('div');document.body.appendChild(container);root=createRoot(container);global.fetch=jest.fn();});
afterEach(async()=>{await act(async()=>root.unmount());container.remove();});
const slide={id:'one',title:'Título',width:960,height:540,elements:[{id:'title',type:'title',content:'Preservar título',width:800,height:30},{id:'body',type:'html',htmlContent:'<p>Texto anterior</p>',x:40,y:70,width:800,height:400},{id:'image',type:'image',src:'/existing.png',width:20,height:20}]};
test('apply changes visible body, preserves title/image, and stores restorable snapshot',async()=>{
 const update=jest.fn();
 await act(async()=>root.render(<SlideProperties slide={slide} onUpdate={update} project={{id:'p'}}/>));
 await act(async()=>mockDensity.onApply({type:'bullets',transformedText:'Resumo',transformedBullets:['Passo 1','Passo 2']}));
 const change=update.mock.calls[0][0];
 expect(change.elements.find(e=>e.id==='title')).toEqual(slide.elements[0]);
 expect(change.elements.find(e=>e.id==='body').htmlContent).toContain('Passo 1');
 expect(change.elements.find(e=>e.id==='image')).toEqual(slide.elements[2]);
 expect(change.densityPreviousElements).toEqual(slide.elements);
 await act(async()=>root.render(<SlideProperties slide={{...slide,...change}} onUpdate={update} project={{id:'p'}}/>));
 const restore=[...container.querySelectorAll('button')].find(b=>b.textContent==='Restaurar antes da sugestão');
 await act(async()=>restore.click());
 expect(update.mock.calls[1][0].elements).toEqual(slide.elements);
});
test('comparison applies as renderable HTML, not a plain text promise',async()=>{
 const update=jest.fn();
 await act(async()=>root.render(<SlideProperties slide={slide} onUpdate={update} project={{id:'p'}}/>));
 await act(async()=>mockDensity.onApply({type:'comparison',table:{headers:['A','B'],rows:[['Um','Dois']]}}));
 expect(update.mock.calls[0][0].elements.find(e=>e.id==='body').htmlContent).toContain('<table');
});
test('simulation protection rejects mutation and image calls',async()=>{
 const update=jest.fn();
 await act(async()=>root.render(<SlideProperties slide={{...slide,elements:[{type:'html',htmlContent:'<script>rules()</script><p>Simulador</p>'}]}} onUpdate={update}/>));
 expect(mockDensity.protectedActivity).toBe(true);
 await expect(mockDensity.onApply({transformedText:'Novo'})).rejects.toThrow(/protegida/);
 expect(update).not.toHaveBeenCalled();expect(fetch).not.toHaveBeenCalled();
});
test('promised image failure leaves the slide unchanged and reports failure',async()=>{
 const update=jest.fn();global.fetch.mockResolvedValue({ok:false,status:503,json:async()=>({detail:'Gerador indisponível'})});
 await act(async()=>root.render(<SlideProperties slide={slide} onUpdate={update} project={{id:'p'}}/>));
 await expect(mockDensity.onApply({type:'infographic',transformedText:'Resumo',requiresImage:true,imagePrompt:'Ilustração'})).rejects.toThrow(/Gerador indisponível/);
 expect(update).not.toHaveBeenCalled();
});
