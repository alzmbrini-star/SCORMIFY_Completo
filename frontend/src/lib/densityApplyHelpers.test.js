import {densityVisibleText,densityProtected,assertDensitySafe,densityBodyElements,buildSuggestionHtml,buildSuggestionPlainText,pickReadableTextColor} from './densityApplyHelpers';

test('counts prose, never code, comments, metadata or hidden content',()=>{
 const text=densityVisibleText({htmlContent:'<head><title>Meta</title><style>.red{color:red}</style></head><script>const state=1;</script><!--ignore--><p>Texto visível.</p><div hidden>Segredo</div><div style="display:none">Oculto</div>'});
 expect(text).toBe('Texto visível.');
});
test('protected activity cannot be rewritten, including encoded plans',()=>{
 for(const htmlContent of ['<script>run()</script>','<iframe src="x"></iframe>','<button onclick="go()">Ir</button>','__B64__:'+btoa('<script>run()</script>')]){
  const slide={elements:[{type:'html',htmlContent}]};
  expect(densityProtected(slide)).toBe(true);
  expect(()=>assertDensitySafe(slide,{transformedText:'Novo'})).toThrow(/protegida/);
 }
});
test('preserves title and thin header while selecting the body',()=>{
 const elements=[{type:'title',width:900,height:60},{type:'html',width:900,height:30},{type:'html',width:900,height:600},{type:'image',width:100,height:100}];
 expect(densityBodyElements(elements).map(e=>e.i)).toEqual([2]);
});
test('native text retains both introduction and bullets',()=>{
 expect(buildSuggestionPlainText({transformedText:'Introdução',transformedBullets:['Um','Dois']})).toBe('Introdução\n\n• Um\n• Dois');
});
test('comparison becomes an actual table and escapes model markup',()=>{
 const suggestion={type:'comparison',table:{headers:['Antes','Depois'],rows:[['<script>','Seguro']]}};
 expect(buildSuggestionHtml(suggestion,'#123456')).toContain('<table');
 expect(buildSuggestionHtml(suggestion)).not.toContain('<script>');
 expect(buildSuggestionPlainText(suggestion)).toContain('Antes | Depois');
 expect(()=>assertDensitySafe({elements:[]},suggestion)).not.toThrow();
});
test('empty or unsupported transformations cannot silently succeed',()=>{
 expect(()=>assertDensitySafe({elements:[]},{})).toThrow();
 expect(()=>assertDensitySafe({elements:[]},{type:'split',transformedText:'Novo'})).toThrow(/Divisão/);
 expect(pickReadableTextColor({background:'#ffffff'})).toBe('#0f172a');
});
