jest.mock('html2canvas',()=>jest.fn());
import {embeddableImageUrl} from './clientVideoExport';
const OriginalRequest=global.Request;
beforeEach(()=>{
  global.Request=class {constructor(url,options){this.url=url;Object.assign(this,options)}};
  global.fetch=jest.fn(async()=>({ok:true,blob:async()=>new Blob(['original image'],{type:'image/png'})}));
  localStorage.setItem('scormify_auth_token','test-only-token');
});
afterEach(()=>{global.Request=OriginalRequest;localStorage.clear();jest.restoreAllMocks()});
test('API image uses bearer with cookies omitted across origins',async()=>{
  const result=await embeddableImageUrl('https://api.example','/api/projects/p/assets/a.png');
  expect(result.startsWith('data:image/png;base64,')).toBe(true);
  expect(fetch.mock.calls[0][0]).toMatchObject({url:'https://api.example/api/projects/p/assets/a.png',credentials:'omit',mode:'cors',headers:{Authorization:'Bearer test-only-token'}});
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
  fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
  await expect(embeddableImageUrl('https://api.example','/api/a.png')).rejects.toThrow('carregar uma imagem');
  fetch.mockResolvedValueOnce({ok:false,status:404});
  await expect(embeddableImageUrl('https://api.example','/api/missing.png')).rejects.toThrow('404');
});
