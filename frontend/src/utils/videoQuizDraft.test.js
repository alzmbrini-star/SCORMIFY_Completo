import {absoluteVideoQuestions,nextVideoQuestionTime,prepareVideoQuizDraft} from './videoQuizDraft';
const cp={at:10,question:' Q ',options:['A','','B',''],correctIndex:2,explanation:' E ',maxAttempts:3};
test('unused options are removed and the correct answer is remapped',()=>{
 const {config,errors}=prepareVideoQuizDraft({checkpoints:[cp]},30);
 expect(errors).toEqual([]);expect(config.checkpoints[0]).toMatchObject({question:'Q',options:['A','B'],correctIndex:1,explanation:'E'});
});
test('new pause avoids duplicates after removal and fits short media',()=>{
 expect(nextVideoQuestionTime([{at:10},{at:30}],0).at).toBe(40);
 const next=nextVideoQuestionTime([{at:10}],15);expect(next.at).toBeGreaterThan(10);expect(next.at).toBeLessThan(15);
 expect(nextVideoQuestionTime([{at:.5,relative:true}],0)).toEqual({at:.75,relative:true});
});
test('relative AI pauses convert before adding manual pauses',()=>{
 const rows=absoluteVideoQuestions([{at:.5,relative:true}],20);
 expect(rows).toEqual([{at:10,relative:false}]);expect(nextVideoQuestionTime(rows,20).at).toBe(15);
});
test('duplicate times, out-of-video pauses and missing explanation are actionable',()=>{
 const {errors}=prepareVideoQuizDraft({checkpoints:[cp,{...cp,explanation:''},{...cp,at:40}]},30);
 expect(errors.some(e=>e.message.includes('momento diferente'))).toBe(true);
 expect(errors.some(e=>e.label==='Explicação 2')).toBe(true);
 expect(errors.some(e=>e.message.includes('antes do fim'))).toBe(true);
});
