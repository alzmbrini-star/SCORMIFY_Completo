import { assessmentFrameDocument } from './assessmentFrame';
jest.mock('./AssessmentBuilder', () => ({ buildAssessmentHtml: config => '<html><head></head><body><h1>'+config.title+'</h1></body></html>' }));

test.each([true,false])('controlled rebuild keeps colors (embedded questions: %s)', embedded => {
  const config = {title:'Prova',textColors:{text:'#112233'}};
  if (embedded) config.questions = [{id:'one'}];
  const html = assessmentFrameDocument({assessmentConfig:config,htmlContent:'<script id="assessment-data" type="application/json">{"questions":[{"id":"one"}]}</script>'});
  expect(html).toContain('color:#112233!important');
  expect(html).toContain('<h1>Prova</h1>');
});
