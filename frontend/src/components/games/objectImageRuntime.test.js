import {objectImageRuntime} from './objectImageRuntime';

test('raster follows trusted shape without replacing its logical target',async()=>{
  const model={nodes:[{id:'piece',type:'circle',attrs:{x:100,y:80,r:25}}],illustrations:[{node:'piece',src:'data:image/png;base64,iVBORw0KGgo='}]};
  document.body.innerHTML='<script id="scormify-simulator-plan" type="application/json">'+JSON.stringify({visual:model})+'</script><svg><circle data-visual-node="piece" cx="100" cy="80" r="25" /></svg>';
  objectImageRuntime();document.dispatchEvent(new Event('DOMContentLoaded'));
  const shape=document.querySelector('circle'),sprite=document.querySelector('image');
  expect(sprite.getAttribute('x')).toBe('75');expect(sprite.getAttribute('width')).toBe('50');
  sprite.dispatchEvent(new Event('load'));expect(shape.style.fillOpacity).toBe('0');expect(shape.style.visibility).not.toBe('hidden');
  shape.setAttribute('transform','rotate(30)');shape.setAttribute('cx','150');
  await Promise.resolve();expect(sprite.getAttribute('transform')).toBe('rotate(30)');expect(sprite.getAttribute('x')).toBe('125');
  sprite.dispatchEvent(new Event('error'));expect(shape.style.fillOpacity).toBe('');expect(document.querySelector('image')).toBeNull();
  window.dispatchEvent(new Event('pagehide'));
});

test('remote images are never loaded by the sprite layer',()=>{
  document.body.innerHTML='<script id="scormify-simulator-plan">'+JSON.stringify({visual:{nodes:[],illustrations:[{node:'piece',src:'https://external/image.png'}]}})+'</script>';
  objectImageRuntime();document.dispatchEvent(new Event('DOMContentLoaded'));expect(document.querySelector('image')).toBeNull();
});
