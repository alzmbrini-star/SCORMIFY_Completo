import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createRoot} from 'react-dom/client';
import {act} from 'react';
import MediaAssessmentOptions,{assessmentMediaSettings,assessmentMediaSummary} from './MediaAssessmentOptions';

test('options preserve separate slide media and default to explicit opt-in',()=>{
 expect(assessmentMediaSettings({type:'content'},{type:'heygen'}).enabled).toBe(false);
 const media={type:'youtube',url:'https://example.test/video',interactiveAssessment:{enabled:true,questionCount:4,images:false}};
 expect(assessmentMediaSettings({type:'quiz'},media)).toEqual(media.interactiveAssessment);
 expect(media.type).toBe('youtube');
});

test('media displays additive and conversion choices with image credits and storage',()=>{
 const html=renderToStaticMarkup(<MediaAssessmentOptions slide={{type:'content'}} media={{interactiveAssessment:{enabled:true,questionCount:2,images:true}}} onChange={()=>{}}/>);
 expect(html).toContain('Acrescentar Avaliação interativa após este slide');
 expect(html).toContain('biblioteca');expect(html).toContain('créditos');
 const quiz=renderToStaticMarkup(<MediaAssessmentOptions slide={{type:'quiz'}} media={{}} onChange={()=>{}}/>);
 expect(quiz).toContain('Converter este Quiz');
});

test('guided counts and disabled images remain correct in Media',()=>{
 const storyboard={guidedPath:{assessmentImages:false},slides:[{guidedActivity:{questions:[{},{}]}},{assessmentRequest:{questionCount:3,images:true}},{type:'content'}]};
 expect(assessmentMediaSummary(storyboard,{})).toEqual({assessments:2,questions:5,images:3});
 expect(assessmentMediaSummary(storyboard,{'1':{interactiveAssessment:{enabled:false,questionCount:3,images:true}}})).toEqual({assessments:1,questions:2,images:0});
});

test('checkbox sends settings without changing other media fields',async()=>{
 global.IS_REACT_ACT_ENVIRONMENT=true;
 const host=document.createElement('div'); document.body.append(host);
 const root=createRoot(host);const changed=jest.fn();
 await act(async()=>root.render(<MediaAssessmentOptions slide={{type:'content'}} media={{type:'kling'}} onChange={changed}/>));
 await act(async()=>host.querySelector('input[type="checkbox"]').click());
 expect(changed).toHaveBeenCalledWith({enabled:true,questionCount:3,images:true});
 await act(async()=>root.unmount());host.remove();
});
