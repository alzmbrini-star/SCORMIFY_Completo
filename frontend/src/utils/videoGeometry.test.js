import {fitVideoRect, fitExportImage} from './videoGeometry';
test.each([[1920,820],[1920,1080],[1024,768],[600,900]])('slide %s x %s is never stretched or cut', (w,h)=>{
  const r=fitVideoRect(w,h,1280,720);
  expect(r.width/r.height).toBeCloseTo(w/h,10);
  expect(r.width).toBeLessThanOrEqual(1280);expect(r.height).toBeLessThanOrEqual(720);
  expect(r.x).toBeGreaterThanOrEqual(0);expect(r.y).toBeGreaterThanOrEqual(0);
  expect(r.x*2+r.width).toBeCloseTo(1280);expect(r.y*2+r.height).toBeCloseTo(720);
});
test('ultrawide slide has equal top/bottom bars, not unequal scales',()=>{
  const r=fitVideoRect(1920,820,1280,720);
  expect(r.scale).toBeCloseTo(2/3);expect(r.width).toBe(1280);expect(r.height).toBeCloseTo(546.6667,3);
  expect(r.y).toBeCloseTo(86.6667,3);
});
test('live video overlay uses the current slide transform',()=>{
  const a=fitVideoRect(1920,820,1280,720),b=fitVideoRect(600,900,1280,720);
  expect(a.x).not.toBe(b.x);expect(a.scale).not.toBe(b.scale);
  expect(b.x+600*b.scale).toBeCloseTo(880);
});
test('native image has explicit proportional dimensions for html2canvas',()=>{
  const img=document.createElement('img');Object.defineProperties(img,{naturalWidth:{value:960},naturalHeight:{value:540}});
  const r=fitExportImage(img,400,400);
  expect(r.width).toBe(400);expect(r.height).toBe(225);expect(img.style.top).toBe('87.5px');
  expect(img.style.width).toBe('400px');expect(img.style.height).toBe('225px');
});
test('cover crops equally but never changes image proportions',()=>{
  const r=fitVideoRect(960,540,400,400,'cover');
  expect(r.height).toBe(400);expect(r.width/r.height).toBeCloseTo(960/540);expect(r.x).toBeLessThan(0);
});
