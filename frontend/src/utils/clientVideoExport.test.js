jest.mock('html2canvas',()=>jest.fn());
import {embeddableImageUrl} from './clientVideoExport';
const OriginalRequest=global.Request;
beforeEach(()=>{
  global.Request=class {constructor(url,options){this.url=url;Object.assign(this,options)}};
  global.fetch=jest.fn(async()=>({ok:true,blob:async()=>new Blob(['original image'],{type:'image/png'})}));
  localStorage.setItem('scormify_auth_token','test-only-token');
});
afterEach(()=>{global.Request=OriginalRequest;localStorage.clear();jest.restoreAllMocks()});
test('public project image omits cookies and bearer and bypasses thumbnail cache',async()=>{
  const result=await embeddableImageUrl('https://api.example','/api/projects/p/assets/a.png');
  expect(result.startsWith('data:image/png;base64,')).toBe(true);
  expect(fetch.mock.calls[0][0]).toMatchObject({url:'https://api.example/api/projects/p/assets/a.png',credentials:'omit',mode:'cors',cache:'no-store',headers:{}});
});
test('protected API images retain bearer authentication without cookies',async()=>{
  await embeddableImageUrl('https://api.example','/api/private/image.png');
  expect(fetch.mock.calls[0][0].headers).toEqual({Authorization:'Bearer test-only-token'});
});
test('external images never receive the API bearer even with /api/ in their path',async()=>{
  await embeddableImageUrl('https://api.example','https://images.example/api/image.png');
  expect(fetch.mock.calls[0][0].headers).toEqual({});
});
test('data and blob media require no network request',async()=>{
  expect(await embeddableImageUrl('https://api.example','data:image/png;base64,YQ==')).toBe('data:image/png;base64,YQ==');
  expect(fetch).not.toHaveBeenCalled();
});
test('network and HTTP failures stop instead of silently replacing missing images',async()=>{
  fetch.mockRejectedValue(new TypeError('Failed to fetch'));
  await expect(embeddableImageUrl('https://api.example','/api/a.png')).rejects.toThrow('carregar uma imagem');
  fetch.mockResolvedValue({ok:false,status:404});
  await expect(embeddableImageUrl('https://api.example','/api/missing.png')).rejects.toThrow('404');
});
test('one transient network failure retries the same image, not a substitute',async()=>{
  fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
  expect(await embeddableImageUrl('https://api.example','/api/projects/p/assets/a.png')).toMatch(/^data:image\/png/);
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(fetch.mock.calls[0][0].url).toBe(fetch.mock.calls[1][0].url);
});
