import { analysisMessage, updateAnalysisStatus } from './courseAnalysisUI';

test('analysis progress is replaced, not left waiting after completion', () => {
  const original = [{ role:'user', text:'Meu curso' }];
  const pending = updateAnalysisStatus(original,'p','Aguarde','pending');
  const done = updateAnalysisStatus(pending,'p',analysisMessage({overallScore:7,improvements:[{}]}),'done');
  expect(done).toHaveLength(2);
  expect(done[1].status).toBe('done');
  expect(done[1].text).toContain('nada foi aplicado');
  expect(done.some(m => m.text === 'Aguarde')).toBe(false);
  expect(original).toHaveLength(1);
});

test('incomplete readings are explicit and failures replace pending status', () => {
  expect(analysisMessage({visualAnalysis:{readSlides:1,totalSlides:19}})).toContain('1 de 19');
  const pending = updateAnalysisStatus([],'p','Lendo','pending');
  const error = updateAnalysisStatus(pending,'p','Falhou','error');
  expect(error).toEqual([{role:'agent',text:'Falhou',analysisProjectId:'p',status:'error'}]);
  expect(updateAnalysisStatus(error,'other','Concluído','done')).toHaveLength(2);
});
