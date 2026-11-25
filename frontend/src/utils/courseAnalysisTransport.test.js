import {runCourseAnalysis, courseAnalysisError} from './courseAnalysisTransport';

const result = {overallScore:7,improvements:[]};
const reply = body => ({ok:true,json:async()=>body});
const base = {url:'/api/agent/courses/p/analyze',headers:{Authorization:'test'},delay:async()=>{}};

test('lost initial response is recovered without repeating start',async()=>{
  const fetchImpl=jest.fn().mockRejectedValueOnce(new TypeError('Failed to fetch')).mockResolvedValueOnce(reply(result));
  expect(await runCourseAnalysis({...base,fetchImpl})).toEqual(result);
  expect(fetchImpl.mock.calls.map(c=>c[0])).toEqual([base.url+'?resume_partial=true',base.url+'?status_only=true']);
});

test('transient polling failures reconnect and preserve successful result',async()=>{
  const fetchImpl=jest.fn().mockResolvedValueOnce(reply({status:'processing'}))
    .mockRejectedValueOnce(new TypeError('Failed to fetch'))
    .mockResolvedValueOnce({ok:false,status:503,json:async()=>({})})
    .mockResolvedValueOnce(reply(result));
  expect(await runCourseAnalysis({...base,fetchImpl})).toEqual(result);
  expect(fetchImpl.mock.calls.slice(1).every(c=>c[0].endsWith('?status_only=true'))).toBe(true);
});

test('permanent auth failure never retries or spends another generation',async()=>{
  const fetchImpl=jest.fn().mockResolvedValue({ok:false,status:401,json:async()=>({detail:'Sessão expirada'})});
  await expect(runCourseAnalysis({...base,fetchImpl})).rejects.toThrow('Sessão expirada');
  expect(fetchImpl).toHaveBeenCalledTimes(1);
});

test('missing task after network failure requires an explicit author retry',async()=>{
  const fetchImpl=jest.fn().mockRejectedValueOnce(new TypeError('Failed to fetch')).mockResolvedValueOnce(reply({status:'not_started'}));
  await expect(runCourseAnalysis({...base,fetchImpl})).rejects.toThrow('Failed to fetch');
  expect(fetchImpl).toHaveBeenCalledTimes(2);
  expect(courseAnalysisError(new TypeError('Failed to fetch'))).toContain('Retomar análise');
});

test('saved-only review never falls through into another paid analysis',async()=>{
  const fetchImpl=jest.fn().mockRejectedValue(new TypeError('Failed to fetch'));
  await expect(runCourseAnalysis({...base,fetchImpl,cachedOnly:true})).rejects.toThrow();
  expect(fetchImpl).toHaveBeenCalledTimes(1);
});

test('abort prevents a late poll from updating another course',async()=>{
  const controller=new AbortController();
  const fetchImpl=jest.fn().mockResolvedValue(reply({status:'processing'}));
  await expect(runCourseAnalysis({...base,fetchImpl,signal:controller.signal,delay:async()=>controller.abort()})).rejects.toHaveProperty('name','AbortError');
  expect(fetchImpl).toHaveBeenCalledTimes(1);
});
