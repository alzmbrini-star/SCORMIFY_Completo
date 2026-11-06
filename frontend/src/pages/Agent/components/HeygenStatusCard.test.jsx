import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import HeygenStatusCard from './HeygenStatusCard';
jest.mock('../../../components/ui/card',()=>({Card:({children,...props})=><div {...props}>{children}</div>,CardContent:({children,...props})=><div {...props}>{children}</div>}));
jest.mock('../../../components/ui/button',()=>({Button:({children,variant,size,...props})=><button {...props}>{children}</button>}));
jest.mock('../../../components/ui/badge',()=>({Badge:({children,variant,...props})=><span {...props}>{children}</span>}));
global.IS_REACT_ACT_ENVIRONMENT=true;
let container,root;
beforeEach(()=>{container=document.createElement('div');document.body.append(container);root=createRoot(container);});
afterEach(async()=>{await act(async()=>root.unmount());container.remove();});
test('a failed avatar never shows a green all-generated message even with legacy all_done',async()=>{
 await act(async()=>root.render(<HeygenStatusCard enabled status={{status:'all_done',videos:[{slideId:'s1',title:'Aula',status:'failed',error:'Confira o vínculo.'}]}}/>));
 expect(container.textContent).toContain('Falhou');expect(container.textContent).toContain('curso foi preservado');
 expect(container.textContent).not.toContain('Todos os vídeos estão prontos');expect(container.querySelector('[role="alert"]').textContent).toContain('vínculo');
});
test('all completed is successful, refresh uses only the supplied status handler',async()=>{
 const refresh=jest.fn();await act(async()=>root.render(<HeygenStatusCard enabled onRefresh={refresh} status={{videos:[{slideId:'s1',title:'Aula',status:'completed'}]}}/>));
 expect(container.textContent).toContain('prontos e vinculados');expect(container.textContent).toContain('revise as perguntas');
 await act(async()=>container.querySelector('button').click());expect(refresh).toHaveBeenCalledTimes(1);
});
test('busy disables refresh and processing is not completion',async()=>{
 await act(async()=>root.render(<HeygenStatusCard enabled busy status={{videos:[{slideId:'s1',status:'processing'}]}}/>));
 expect(container.querySelector('button').disabled).toBe(true);expect(container.textContent).not.toContain('Todos os vídeos estão prontos');
});
