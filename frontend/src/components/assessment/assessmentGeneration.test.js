import { generateAssessment } from './assessmentGeneration';

const storage=()=>{const values=new Map();return {getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};};
const response=data=>({ok:true,status:200,json:async()=>data});
const payload={projectId:'p1',prompt:'Feedback',count:5};
let originalFetch, originalCrypto;
beforeEach(()=>{originalFetch=global.fetch;originalCrypto=global.crypto;global.crypto={randomUUID:()=> 'request-1234567890'};});
afterEach(()=>{global.fetch=originalFetch;global.crypto=originalCrypto;});

test('returns questions with their images and reports progress through short polls',async()=>{
  const result={status:'done',items:[{id:'q',media:{kind:'image',url:'/support.png'}}],imagesGenerated:1};
  global.fetch=jest.fn().mockResolvedValueOnce(response({jobId:'j1',status:'queued'}))
    .mockResolvedValueOnce(response({jobId:'j1',status:'running',imagesCompleted:1,imagesTotal:5}))
    .mockResolvedValueOnce(response(result));
  const progress=jest.fn();const state=storage();
  expect(await generateAssessment('',payload,{}, {storage:state,wait:async()=>{},onProgress:progress})).toEqual(result);
  expect(global.fetch.mock.calls.filter(([,init])=>init.method==='POST')).toHaveLength(1);
  expect(progress.mock.calls.flat().join(' ')).toContain('1 de 5');
  expect(state.getItem('scormify-assessment-job:p1')).toBeUndefined();
});

test('lost connection resumes saved job without another generation POST',async()=>{
  const state=storage();state.setItem('scormify-assessment-job:p1',JSON.stringify({signature:JSON.stringify(payload),jobId:'same-job',requestId:'request-1234567890'}));
  global.fetch=jest.fn().mockRejectedValueOnce(new TypeError('network')).mockResolvedValueOnce(response({status:'done',items:[],imagesGenerated:0,warnings:['image unavailable']}));
  const result=await generateAssessment('',payload,{}, {storage:state,wait:async()=>{}});
  expect(global.fetch.mock.calls.every(([url])=>url.endsWith('/same-job'))).toBe(true);
  expect(result.warnings).toEqual(['image unavailable']);
});

test('server error is surfaced and releases pending request',async()=>{
  const state=storage();global.fetch=jest.fn().mockResolvedValueOnce(response({jobId:'j',status:'error',error:'Questões preservadas no Banco'}));
  await expect(generateAssessment('',payload,{}, {storage:state,wait:async()=>{}})).rejects.toThrow('preservadas');
  expect(state.getItem('scormify-assessment-job:p1')).toBeUndefined();
});

test('individual image uses isolated resumable job and leaves batch key untouched',async()=>{
 const state=storage();state.setItem('scormify-assessment-job:p1','batch');
 global.fetch=jest.fn().mockResolvedValueOnce(response({jobId:'image-job',status:'queued'})).mockResolvedValueOnce(response({status:'done',media:{kind:'image',url:'/api/projects/p1/assets/image.png'}}));
 const result=await generateAssessment('',{projectId:'p1',prompt:'Luvas'},{},{storage:state,wait:async()=>{},startPath:'/images/jobs',storageKey:'single-image:p1:a'});
 expect(global.fetch.mock.calls[0][0]).toBe('/api/assessment-questions/images/jobs');
 expect(result.media.kind).toBe('image');expect(state.getItem('scormify-assessment-job:p1')).toBe('batch');
 expect(state.getItem('single-image:p1:a')).toBeUndefined();
});
