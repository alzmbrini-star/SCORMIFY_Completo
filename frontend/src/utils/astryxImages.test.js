import {prepareAstryxImages} from './astryxImages';
import {upgradeAstryxViewport} from './astryxViewport';
const doc=src=>`<main data-astryx-lesson="1"><p>Texto integral</p><img src="${src}" alt="Captura original"></main>`;
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
