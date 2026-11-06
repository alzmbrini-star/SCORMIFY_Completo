import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import ScenarioPlayer from './ScenarioPlayer';
jest.mock('../../utils/apiUrl',()=>({getApiUrl:()=> 'https://api.example.invalid'}));

globalThis.IS_REACT_ACT_ENVIRONMENT=true;
test('React mounts the same runtime as exports and confirms before completing',()=>{
 const host=document.createElement('div');document.body.appendChild(host);
 const root=createRoot(host),complete=jest.fn();
 const scenario={title:'Dados da equipe',start_node_id:'first',nodes:[
  {id:'first',title:'Compartilhar',narrative:'Avalie as permissões.',imageUrl:'/api/projects/p/assets/art.png',choices:[{id:'safe',text:'Restringir acesso',feedback:'Dados protegidos.',is_optimal:true,next_node_id:'end'}]},
  {id:'end',title:'Conclusão',is_ending:true,narrative:'Reflita sobre sua decisão.',choices:[]}
 ]};
 try {
  act(()=>root.render(<ScenarioPlayer scenarioData={scenario} onComplete={complete}/>));
  expect(host.querySelector('img').src).toBe('https://api.example.invalid/api/projects/p/assets/art.png');
  act(()=>host.querySelector('[data-testid="scenario-choice-0"]').click());
  expect(complete).not.toHaveBeenCalled();
  act(()=>host.querySelector('[data-testid="scenario-confirm-btn"]').click());
  expect(host.textContent).toContain('Dados protegidos.');expect(complete).not.toHaveBeenCalled();
  act(()=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent==='Continuar').click());
  expect(complete).toHaveBeenCalledTimes(1);expect(complete.mock.calls[0][0].score).toBe(100);
 } finally {act(()=>root.unmount());host.remove();}
});
