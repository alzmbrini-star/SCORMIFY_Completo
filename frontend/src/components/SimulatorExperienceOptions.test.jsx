import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import SimulatorExperienceOptions from './SimulatorExperienceOptions';
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
test('author can choose level and visual approach independently, with accessible labels',()=>{
  const host=document.createElement('div');document.body.appendChild(host);const root=createRoot(host),change=jest.fn();
  act(()=>root.render(<SimulatorExperienceOptions complexity="guided" visualStyle="technical" onChange={change}/>));
  const fields=host.querySelectorAll('select');expect(fields[0].options.length).toBe(2);expect(fields[1].options.length).toBe(3);expect(fields[2].options.length).toBe(2);
  expect(host.querySelector(`label[for="${fields[0].id}"]`).textContent).toContain('Tipo de atividade');
  act(()=>{fields[1].value='advanced';fields[1].dispatchEvent(new Event('change',{bubbles:true}));});
  expect(change).toHaveBeenLastCalledWith({complexity:'advanced',visualStyle:'technical',activityType:'simulation'});
  act(()=>root.render(<SimulatorExperienceOptions complexity="advanced" visualStyle="technical" onChange={change} disabled/>));
  expect(host.querySelector('fieldset').disabled).toBe(true);
  expect(fields[1].value).toBe('advanced');expect(host.textContent).toContain('não a qualidade');
  act(()=>root.render(<SimulatorExperienceOptions activityType="visualization" onChange={change}/>));
  expect(host.querySelectorAll('select')[1].disabled).toBe(true);expect(host.textContent).toContain('Sem pontuação');
  act(()=>root.unmount());host.remove();
});
