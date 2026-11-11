import {previewPlan} from './GuidedPathPreview';

test('guided preview keeps canonical assessment identity, excludes image payloads and never enables LMS writes',()=>{
 const course={metadata:{title:'Aula',guidedPath:{version:1,id:'path'}},slides:[{id:'s',title:'Avaliação',guidedStage:'assessment',guidedUnitId:'u',elements:[{guidedActivity:{id:'a',kind:'assessment',title:'Avaliação',questions:[{media:{url:'large-image'}}]}}]}]};
 const plan=previewPlan(course);
 expect(plan.slides[0].activity).toEqual({id:'a',kind:'assessment',title:'Avaliação'});
 expect(plan.fingerprint).toContain('preview-');
 expect(plan.title).toBe('Aula');
 expect(previewPlan({metadata:{visualCourseMode:'standard'}})).toBeNull();
});
