import {coverAssetUrl,coverDimensions,coverElementRect,staticCoverDocument} from './courseCover';

test('asset URLs resolve once and preserve external image URLs',()=>{
 expect(coverAssetUrl('/api/projects/p/assets/capa.webp','https://api.test')).toBe('https://api.test/api/projects/p/assets/capa.webp');
 expect(coverAssetUrl('https://old.test/api/projects/p/assets/capa.webp','https://api.test')).toBe('https://api.test/api/projects/p/assets/capa.webp');
 expect(coverAssetUrl('https://images.test/capa.png','https://api.test')).toBe('https://images.test/capa.png');
 expect(coverAssetUrl('javascript:alert(1)')).toBe('');expect(coverAssetUrl('data:text/html,bad')).toBe('');
});

test('stage inherits valid dimensions without changing the source or stretching portrait slides',()=>{
 const slide={width:800,height:1200,elements:[]};const before=JSON.stringify(slide);
 expect(coverDimensions(slide)).toEqual({width:800,height:1200});
 expect(coverDimensions({width:0,height:-1},{width:1280,height:720})).toEqual({width:1280,height:720});
 expect(coverDimensions()).toEqual({width:1920,height:820});
 expect(coverElementRect({x:'10%',y:'20%',width:'50%',height:'40%'},{width:1000,height:500})).toEqual({left:100,top:100,width:500,height:200});
 expect(JSON.stringify(slide)).toBe(before);
});

test('HTML preserves cover styling and images but cannot run activities or send data',()=>{
 const source=`<!doctype html><html><head><style>.cover{background-image:url(/api/assets/bg.png);color:red}</style><script>fetch('/write')</script></head><body><h1>Minha capa</h1><img src="/api/projects/p/assets/cover.webp" onerror="alert(1)"><iframe src="https://other.test"></iframe><form action="/write"><input value="secret"></form><meta http-equiv="refresh" content="0;url=https://other.test"><a onclick="doSomething()">texto</a></body></html>`;
 const doc=staticCoverDocument(source,'https://api.test');
 expect(doc).toContain('Minha capa');expect(doc).toContain('color:red');
 expect(doc).toContain('https://api.test/api/projects/p/assets/cover.webp');
 expect(doc).toContain('https://api.test/api/assets/bg.png');
 expect(doc).not.toMatch(/<script|<iframe|<form|<input|onerror|onclick|http-equiv="refresh"/i);
 expect(doc).toContain("script-src 'none'");expect(doc).toContain("connect-src 'none'");
 expect(source).toContain("fetch('/write')"); // original authored HTML untouched
});

test('empty HTML and non-image data are safe',()=>{
 expect(staticCoverDocument(null)).toBe('');
 expect(staticCoverDocument('')).toBe('');
 expect(staticCoverDocument('<img src="javascript:alert(1)">')).not.toContain('javascript:');
});

test('offline SlideKiln covers retain embedded fonts but reject executable data URLs',()=>{
 const source='<style>@font-face{font-family:Carlito;src:url("data:application/octet-stream;base64,AAAA")}body{background:url("data:text/html;base64,AAAA")}</style><h1>Capa</h1>';
 const doc=staticCoverDocument(source,'https://api.test',{offline:true});
 expect(doc).toContain('data:application/octet-stream;base64,AAAA');
 expect(doc).not.toContain('data:text/html;base64,AAAA');
 expect(doc).toContain('font-src data:');expect(doc).toContain('img-src data:;');
});
