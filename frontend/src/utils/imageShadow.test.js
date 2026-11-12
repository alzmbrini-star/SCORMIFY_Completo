import { imageShadowStyle, imageShadowPreset } from './imageShadow';
test('legacy images stay unchanged and presets can be explicitly removed',()=>{
  expect(imageShadowStyle()).toEqual({});
  expect(imageShadowStyle(null)).toEqual({});
  expect(imageShadowStyle(imageShadowPreset('soft'))).toEqual({filter:'drop-shadow(0px 6px 16px rgba(0,0,0,0.18))',boxShadow:'none'});
  expect(imageShadowStyle(imageShadowPreset('none'))).toEqual({filter:'none',boxShadow:'none'});
});
test('contours and frame shadows use only validated values',()=>{
  expect(imageShadowStyle({...imageShadowPreset('medium'),mode:'frame'})).toEqual({boxShadow:'0px 10px 24px rgba(0,0,0,0.28)',filter:'none'});
  expect(imageShadowStyle({preset:'custom',x:999,y:-999,blur:999,opacity:999,color:'red; background:url(https://evil)'})).toEqual({filter:'drop-shadow(40px -40px 60px rgba(0,0,0,0.7))',boxShadow:'none'});
  expect(imageShadowStyle({preset:'custom',blur:NaN,opacity:Infinity,x:'10',color:'#123456'}).filter).toBe('drop-shadow(0px 6px 16px rgba(18,52,86,0.18))');
});
