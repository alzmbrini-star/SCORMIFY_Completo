import {prepareAstryxImages,prepareAssessmentImages} from './astryxImages';
import {upgradeAstryxViewport} from './astryxViewport';
const doc=src=>`<main data-astryx-lesson="1"><p>Texto integral</p><img src="${src}" alt="Captura original"></main>`;
test('assessment display copies preserve questions originals grades and manual captures',()=>{
 const image={kind:'image',url:'/api/projects/p1/assets/assessment_'+'a'.repeat(32)+'.png'};
 const config={questions:[{prompt:'Enunciado',points:3,media:image,options:[{id:'a',isCorrect:true,media:image}],
   capture:{kind:'image',url:'/api/projects/p1/assets/docx_capture.png'}}]};
 const before=JSON.stringify(config),updated=prepareAssessmentImages(config);
 expect(updated.questions[0].media.url).toContain('astryx_image=v1');
 expect(updated.questions[0].options[0].media.url).toContain('astryx_image=v1');
 expect(updated.questions[0].options[0].isCorrect).toBe(true);
 expect(updated.questions[0].capture).toEqual(config.questions[0].capture);
 expect(JSON.stringify(config)).toBe(before);
 expect(prepareAssessmentImages(updated)).toEqual(updated);
});
test('requests cached lightweight generated illustrations without altering originals or alt',()=>{
 const raw=doc('/api/projects/p1/assets/ai_img_abcdef123456.png');
 const result=prepareAstryxImages(raw);
 expect(result).toContain('astryx_image=v1');expect(result).toContain('decoding="async"');
 expect(result).toContain('alt="Captura original"');expect(prepareAstryxImages(result)).toBe(result);
 expect(raw).not.toContain('astryx_image');
});
test('leaves document screenshots, logos, unsupported and non-Astryx slides unchanged',()=>{
 for(const filename of ['docx_image_11.png','source_capture.png','logo.png','ai_img_abcdef123456.gif']){
  const raw=doc('/api/projects/p1/assets/'+filename);expect(prepareAstryxImages(raw)).toBe(raw);
 }
 const other=doc('/api/projects/p1/assets/ai_img_abcdef123456.png').replace('data-astryx-lesson','data-other');
 expect(prepareAstryxImages(other)).toBe(other);
});
test('upgrades compatible saved viewport and encoded documents idempotently',()=>{
 const raw=doc('/api/projects/p1/assets/ai_img_abcdef123456.png')+'<script id="astryx-viewport-v2">keep()</script>';
 expect(upgradeAstryxViewport(raw)).toContain('astryx_image=v1');
 expect(upgradeAstryxViewport(upgradeAstryxViewport(raw))).toBe(upgradeAstryxViewport(raw));
 expect(atob(upgradeAstryxViewport('__B64__:'+btoa(raw)).slice(8))).toContain('astryx_image=v1');
});
