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
test('unconfirmed speech timings are never converted into executable pauses',()=>{
 const draft={timingReviewRequired:true,checkpoints:[{...cp,at:null,pauseCue:'Antes de continuar, pense nesta situação.'}]};
 expect(prepareVideoQuizDraft(draft,30).errors.some(e=>e.message.includes('confirme'))).toBe(true);
 expect(prepareVideoQuizDraft({...draft,timingReviewConfirmed:true},30).errors.some(e=>e.label==='Tempo da pergunta 1')).toBe(true);
 const result=prepareVideoQuizDraft({...draft,timingReviewConfirmed:true,checkpoints:[{...draft.checkpoints[0],at:12}]},30);
 expect(result.errors).toEqual([]);expect(result.config.timingReviewRequired).toBeUndefined();
 expect(result.config.checkpoints[0].timingStatus).toBe('author-reviewed');
 expect(result.config.checkpoints[0].pauseCue).toBe(draft.checkpoints[0].pauseCue);
});
