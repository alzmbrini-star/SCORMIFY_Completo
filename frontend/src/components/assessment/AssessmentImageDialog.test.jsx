import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import AssessmentImageDialog from './AssessmentImageDialog';
import {generateAssessment} from './assessmentGeneration';
jest.mock('./assessmentGeneration',()=>({generateAssessment:jest.fn()}));
jest.mock('../../utils/apiUrl',()=>({getApiUrl:()=> 'http://test'}));
jest.mock('../../contexts/AuthContext',()=>({authHeaders:x=>x}));
jest.mock('../ui/button',()=>({Button:({variant,size,...props})=><button {...props}/>}));
jest.mock('../ui/textarea',()=>({Textarea:props=><textarea {...props}/>}));
jest.mock('../ui/dialog',()=>({Dialog:({children})=><div>{children}</div>,DialogContent:({children})=><div>{children}</div>,DialogHeader:({children})=><div>{children}</div>,DialogFooter:({children})=><div>{children}</div>,DialogTitle:({children})=><h2>{children}</h2>,DialogDescription:({children})=><p>{children}</p>}));
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
let host,root;
beforeEach(()=>{host=document.createElement('div');document.body.appendChild(host);root=createRoot(host);jest.clearAllMocks();});
afterEach(()=>{act(()=>root.unmount());host.remove();});
const click=async text=>{await act(async()=>[...host.querySelectorAll('button')].find(b=>b.textContent===text).click());};
test('generation previews stored asset; only explicit use associates the image',async()=>{
 const apply=jest.fn(),close=jest.fn(),media={kind:'image',url:'/api/projects/p/assets/a.png',name:'Luvas'};
 generateAssessment.mockResolvedValue({media});
 act(()=>root.render(<AssessmentImageDialog target={{key:'q:options:a',label:'Alternativa A',description:'Luvas',context:'Equipamento',category:'Segurança'}} projectId="p" onApply={apply} onClose={close}/>));
 expect(host.textContent).toContain('consome créditos');await click('Gerar imagem');
 expect(apply).not.toHaveBeenCalled();expect(host.querySelector('img').getAttribute('src')).toContain('/api/projects/p/assets/a.png');
 expect(generateAssessment.mock.calls[0][3].startPath).toBe('/images/jobs');
 await click('Usar esta imagem');expect(apply).toHaveBeenCalledWith(media);
});
test('failed generation leaves prior attachment untouched',async()=>{
 const apply=jest.fn();generateAssessment.mockRejectedValue(new Error('Serviço indisponível'));
 act(()=>root.render(<AssessmentImageDialog target={{key:'q:support',label:'Pergunta',description:'Cena'}} projectId="p" onApply={apply} onClose={()=>{}}/>));
 await click('Gerar imagem');expect(apply).not.toHaveBeenCalled();expect(host.querySelector('[role="alert"]').textContent).toContain('indisponível');
});
test('scenario images reuse persistence but require explicit application to the scene',async()=>{
 const apply=jest.fn(),media={kind:'image',url:'/api/projects/p/assets/cena.png',name:'Cena'};
 generateAssessment.mockResolvedValue({media});
 act(()=>root.render(<AssessmentImageDialog usage="scenario" target={{key:'scenario-s-n1',label:'Cena 1',description:'Conversa entre personagens',context:'Contexto'}} projectId="p" onApply={apply} onClose={()=>{}}/>));
 expect(host.textContent).toContain('somente à cena selecionada');
 expect(host.textContent).not.toContain('salve a questão no Banco');
 await click('Gerar imagem');expect(apply).not.toHaveBeenCalled();
 expect(generateAssessment.mock.calls[0][3].storageKey).toBe('scormify-scenario-image:p:scenario-s-n1');
 await click('Usar esta imagem');expect(apply).toHaveBeenCalledWith(media);
});
