import {prepareSinglePagePreview,previewError,abortableDelay} from './singlePagePreview';
jest.mock('../contexts/AuthContext',()=>({authHeaders:()=>({Authorization:'test-only'})}));
const response=(body,status=200)=>({ok:status<400,status,json:async()=>body,text:async()=>body});
const ready={status:'completed',result:{downloadUrl:'/api/exports/preview.html'}};
const page='<!DOCTYPE html><html><body>Questões preservadas</body></html>';
const setup=(...responses)=>{const fetcher=jest.fn();responses.forEach(r=>fetcher.mockImplementationOnce(()=>r instanceof Error?Promise.reject(r):Promise.resolve(r)));return fetcher;};
test('starts once, polls progress and downloads complete HTML',async()=>{
 const fetcher=setup(response({jobId:'j'}),response({status:'processing',progress:50}),response(ready),response(page));
 const onProgress=jest.fn();expect(await prepareSinglePagePreview('', 'p',{fetcher,onProgress,delay:async()=>{}})).toBe(page);
 expect(fetcher.mock.calls[0][1].method).toBe('POST');expect(onProgress).toHaveBeenCalledWith(expect.objectContaining({progress:50}));
 expect(fetcher.mock.calls.filter(c=>c[1].method==='POST')).toHaveLength(1);
});
test('temporary polling failure resumes same task without duplicate generation',async()=>{
 const fetcher=setup(response({jobId:'j'}),response({},503),new TypeError('Failed to fetch'),response(ready),response(page));
 expect(await prepareSinglePagePreview('', 'p',{fetcher,delay:async()=>{}})).toBe(page);
 expect(fetcher.mock.calls.slice(1,4).map(c=>c[0])).toEqual(Array(3).fill('/api/job/j'));
});
test('manual retry resumes an existing job without another POST',async()=>{
 const fetcher=setup(response(ready),response(page));const onJobStarted=jest.fn();
 expect(await prepareSinglePagePreview('','p',{fetcher,jobId:'existing',onJobStarted})).toBe(page);
 expect(fetcher.mock.calls[0][0]).toBe('/api/job/existing');expect(fetcher.mock.calls.every(c=>!c[1].method)).toBe(true);
 expect(onJobStarted).toHaveBeenCalledWith('existing');
});
test('survives longer temporary server interruptions without restarting generation',async()=>{
 const fetcher=setup(response({jobId:'j'}),...Array(8).fill(response({},503)),response(ready),response(page));
 expect(await prepareSinglePagePreview('','p',{fetcher,delay:async()=>{}})).toBe(page);
 expect(fetcher.mock.calls.filter(c=>c[1].method==='POST')).toHaveLength(1);
});
test.each([401,403])('session failure is friendly (%i)',async status=>{
 const fetcher=setup(response({},status));await expect(prepareSinglePagePreview('','p',{fetcher})).rejects.toThrow('sessão');
});
test('does not expose internal worker error or fetch arbitrary result URL',async()=>{
 const failed=setup(response({jobId:'j'}),response({status:'failed',error:'secret traceback'}));
 await expect(prepareSinglePagePreview('','p',{fetcher:failed})).rejects.toThrow('Nenhum slide');
 const external=setup(response({jobId:'j'}),response({...ready,result:{downloadUrl:'https://elsewhere.invalid'}}));
 await expect(prepareSinglePagePreview('','p',{fetcher:external})).rejects.toThrow('arquivo válido');expect(external).toHaveBeenCalledTimes(2);
});
test('invalid document is rejected instead of blank iframe',async()=>{
 const fetcher=setup(response({jobId:'j'}),response(ready),response('{}'));
 await expect(prepareSinglePagePreview('','p',{fetcher})).rejects.toThrow('conteúdo inválido');
});
test('closing aborts delay; raw network failures receive a friendly message',async()=>{
 const controller=new AbortController();const pending=abortableDelay(10000,controller.signal);controller.abort();
 await expect(pending).rejects.toHaveProperty('name','AbortError');
 expect(previewError(new TypeError('Failed to fetch'))).toContain('curso não foi alterado');expect(previewError(new DOMException('','AbortError'))).toBe('');
});
test('bounded timeout preserves course and does not restart job',async()=>{
 let clock=0;const fetcher=setup(response({jobId:'j'}));
 await expect(prepareSinglePagePreview('','p',{fetcher,now:()=>{clock+=700000;return clock;}})).rejects.toThrow('demorou');expect(fetcher).toHaveBeenCalledTimes(1);
});
