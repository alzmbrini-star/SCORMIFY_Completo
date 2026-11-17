import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import CourseResourceBalance from './CourseResourceBalance';
test('19 teaching slides show seven combined resources, hard ceiling and preservation',()=>{
 const html=renderToStaticMarkup(<CourseResourceBalance balance={{explanatorySlides:19,existingResourceSlides:0,recommendedAdditions:7,selectedSuggestions:7,hardMaximumTotal:19}}/>);
 expect(html).toContain('até 7 novos complementos neste lote');expect(html).toContain('19 slides explicativos');
 expect(html).toContain('todos os tipos juntos');expect(html).toContain('no máximo um');expect(html).toContain('preservados');
});

test('soft target met does not hide suggestions or block application below hard ceiling',()=>{
 const html=renderToStaticMarkup(<CourseResourceBalance balance={{explanatorySlides:19,existingResourceSlides:7,recommendedAdditions:0,applicationLimit:7,selectedSuggestions:7,hardMaximumTotal:19}}/>);
 expect(html).toContain('7 sugestões');expect(html).toContain('até 7 novos complementos neste lote');
 expect(html).toContain('não bloqueia sugestões');expect(html).toContain('redundâncias');
});

test('hard ceiling blocks additions but keeps advice visible',()=>{
 const html=renderToStaticMarkup(<CourseResourceBalance balance={{explanatorySlides:19,existingResourceSlides:19,recommendedAdditions:0,applicationLimit:0,selectedSuggestions:7,hardMaximumTotal:19}}/>);
 expect(html).toContain('7 sugestões');expect(html).toContain('novas adições estão bloqueadas');
 expect(html).toContain('Nenhum recurso existente será removido');
});
