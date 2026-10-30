import { componentLibraryFilter as filter } from './componentLibraryFilter';

const catalog={components:{
  liquid_vessel:{searchTerms:['água','bomba','reservatório']},
  lift_gate:{searchTerms:['comporta']},
  conversation_person:{searchTerms:['feedback','pessoa']},
  time_budget:{searchTerms:['tempo']},
}};
const ids=result=>result.entries.map(([id])=>id);

test('saved and draft membership takes precedence over contextual suggestions',()=>{
  const model={title:'Bomba de água',visualProject:{instances:[{component:'lift_gate'}]}};
  expect(ids(filter(catalog,model,{instances:[]}))).toEqual(['lift_gate']);
  expect(ids(filter(catalog,model,{instances:[{component:'conversation_person'}]}))).toEqual(['lift_gate','conversation_person']);
});
test('custom artwork gets clearly distinguished contextual suggestions',()=>{
  const result=filter(catalog,{title:"Simulador de Bomba d’Água",visual:{nodes:[{id:'reservatorio_superior'}]}},{});
  expect(result.basis).toBe('context');
  expect(ids(result)).toEqual(['liquid_vessel']);
  expect(filter(catalog,{title:'atemporal'},{}).basis).toBe('none');
});
test('no match never silently shows the whole catalog; opt-in does',()=>{
  expect(ids(filter(catalog,{},{}))).toEqual([]);
  expect(filter(catalog,{}, {},true).basis).toBe('all');
  expect(ids(filter(catalog,{}, {},true))).toHaveLength(4);
  expect(ids(filter(null,null,null))).toEqual([]);
});
test('unknown saved parts are preserved and filtering does not mutate inputs',()=>{
  const model={visualProject:{instances:[{component:'custom_part'}]}};
  const project={instances:[{component:'custom_part'}]};
  const before=JSON.stringify({catalog,model,project});
  expect(filter(catalog,model,project).basis).toBe('used');
  expect(ids(filter(catalog,model,project))).toEqual([]);
  expect(JSON.stringify({catalog,model,project})).toBe(before);
});
