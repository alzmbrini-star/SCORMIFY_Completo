import { applyEditorialTextColors, readEditorialTextColors } from './editorialTextColors';
const source='<div><h2>Resumo</h2><ul><li style="color:white;background:white"><strong>Aplicar</strong> feedback.</li></ul><p>Conclusão</p></div>';
test('summary preserves content and stores independent text/surface colors',()=>{
  const colors={title:'#ffffff',text:'#e2e8f0',card:'#172c49',cardBackground:'#ffffff'};
  const html=applyEditorialTextColors(source,colors);
  expect(html).toContain(source);
  expect(readEditorialTextColors(html)).toEqual(colors);
  const doc=new DOMParser().parseFromString(html,'text/html');
  const rules=Array.from(doc.querySelector('style').sheet?.cssRules || []);
  // Styles are ordered so card foreground overrides general nested text.
  expect(html.indexOf('body li,body li *')).toBeGreaterThan(html.indexOf('body,body :is'));
  expect(html).toContain('background:#ffffff!important');
  expect(html).toContain('color:#172c49!important');
  expect(rules).toBeDefined();
});
test('updates are idempotent and reset restores original HTML exactly',()=>{
  const html=applyEditorialTextColors(source,{card:'#123456'});
  expect(applyEditorialTextColors(html,{card:'#123456'})).toBe(html);
  expect(applyEditorialTextColors(html,{})).toBe(source);
});
test('rejects CSS injection and unknown settings',()=>{
  expect(applyEditorialTextColors(source,{card:'red;}body{display:none',unknown:'#ffffff'})).toBe(source);
});
test('complete documents keep override inside head',()=>{
  const html=applyEditorialTextColors('<html><head></head><body><h1>Resumo</h1></body></html>',{title:'#112233'});
  expect(html.indexOf('scormify-editorial-text-colors')).toBeLessThan(html.indexOf('</head>'));
});
