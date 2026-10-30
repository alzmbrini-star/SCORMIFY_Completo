import {fetchHtmlDiagnostic} from './htmlDiagnostic';

const diagnostic={jobId:'html_example',status:'error',diagnostic:{attempts:[{document:'{"actions":[]}',error:'Regra inválida'}]}};
const reply=(status,data)=>({ok:status>=200&&status<300,status,json:async()=>data});
afterEach(()=>jest.restoreAllMocks());

test('downloads existing owned data using bearer auth and no cross-site cookies or paid generation',async()=>{
  global.fetch=jest.fn().mockResolvedValue(reply(200,diagnostic));
  expect(await fetchHtmlDiagnostic('https://api.example','project/a & b',{Authorization:'Bearer test-only'})).toEqual(diagnostic);
  expect(fetch).toHaveBeenCalledTimes(1);
  const [url,init]=fetch.mock.calls[0];
  expect(url).toBe('https://api.example/api/generate-html/jobs/diagnostics/latest?projectId=project%2Fa%20%26%20b');
  expect(init).toMatchObject({method:'GET',credentials:'omit',headers:{Authorization:'Bearer test-only'}});
  expect(init.body).toBeUndefined();
});

test.each([[401,'sessão expirou'],[403,'permissão'],[404,'Diagnóstico expirado']])('keeps actionable HTTP %s errors',async(status,message)=>{
  global.fetch=jest.fn().mockResolvedValue(reply(status,{detail:'Diagnóstico expirado'}));
  await expect(fetchHtmlDiagnostic('','p',{})).rejects.toThrow(message);
});

test('network failure asks to retry download, never regenerate',async()=>{
  global.fetch=jest.fn().mockRejectedValue(new TypeError('Failed to fetch'));
  await expect(fetchHtmlDiagnostic('','p',{})).rejects.toThrow('Tente somente o download novamente');
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('invalid payload is not saved as a purported diagnostic',async()=>{
  global.fetch=jest.fn().mockResolvedValue(reply(200,{html:'not a diagnostic'}));
  await expect(fetchHtmlDiagnostic('','p',{})).rejects.toThrow('diagnóstico válido');
});
