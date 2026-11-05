import {withEditorialColorProbe,readEditorialColorSnapshot} from './editorialColorProbe';
test('probe is preview-only and does not remove or change activity code',()=>{
 const raw='<html><body><script>restart()</script></body></html>';
 const probe=withEditorialColorProbe(raw);
 expect(probe).toContain('<script>restart()</script>');
 expect(withEditorialColorProbe(probe)).toBe(probe);
 expect(probe).not.toContain('allow-same-origin');
});
test('only the selected iframe and current request can report validated colors',()=>{
 const source={},frame={contentWindow:source},groups={};
 ['title','text','card','cardBackground'].forEach(k=>groups[k]={count:2,colors:['#263b55','#ffffff'],complex:false});
 const event={source,data:{type:'scormify-editorial-color-snapshot',requestId:'test',groups}};
 expect(readEditorialColorSnapshot(event,frame,'test')).toEqual(groups);
 expect(readEditorialColorSnapshot({...event,source:{}},frame,'test')).toBeNull();
 expect(readEditorialColorSnapshot(event,frame,'old')).toBeNull();
 groups.card.colors=['red;display:none'];
 expect(readEditorialColorSnapshot(event,frame,'test')).toBeNull();
});
