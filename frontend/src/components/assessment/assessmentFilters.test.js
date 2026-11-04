import { filterAssessmentQuestions } from './assessmentFilters';
const all={search:'',type:'',category:'',media:'',selection:''};
const questions=[
  {id:'a',title:'Segurança elétrica',category:'Proteção',type:'single_choice',options:[{text:'Luvas isolantes',media:{kind:'image'}}]},
  {id:'b',title:'Ordene o processo',category:'Procedimentos',type:'ordering',media:{kind:'image'}},
  {id:'c',title:'Risco',category:'Proteção',type:'categorization',imageGenerationStatus:'failed'},
];
test('accent-insensitive search includes alternatives and combines filters',()=>{
 expect(filterAssessmentQuestions(questions,{...all,search:'luvas',category:'Proteção',type:'single_choice'}).map(q=>q.id)).toEqual(['a']);
 expect(filterAssessmentQuestions(questions,{...all,search:'seguranca eletrica'})).toHaveLength(1);
 expect(filterAssessmentQuestions(questions,{...all,search:'inexistente'})).toEqual([]);
});
test('filters image roles, failed generation and selected without mutating the bank',()=>{
 expect(filterAssessmentQuestions(questions,{...all,media:'alternatives'}).map(q=>q.id)).toEqual(['a']);
 expect(filterAssessmentQuestions(questions,{...all,media:'image'}).map(q=>q.id)).toEqual(['b']);
 expect(filterAssessmentQuestions(questions,{...all,media:'failed'}).map(q=>q.id)).toEqual(['c']);
 expect(filterAssessmentQuestions(questions,{...all,selection:'selected'},['b']).map(q=>q.id)).toEqual(['b']);
 expect(filterAssessmentQuestions(questions,{...all,selection:'unselected'},['b'])).toHaveLength(2);
 expect(filterAssessmentQuestions(questions,all)).toHaveLength(3);
});
