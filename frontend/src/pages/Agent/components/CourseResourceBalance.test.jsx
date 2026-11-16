import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import CourseResourceBalance from './CourseResourceBalance';
test('19 teaching slides show seven combined resources, hard ceiling and preservation',()=>{
 const html=renderToStaticMarkup(<CourseResourceBalance balance={{explanatorySlides:19,existingResourceSlides:0,recommendedAdditions:7,selectedSuggestions:7,hardMaximumTotal:19}}/>);
 expect(html).toContain('até 7 novos complementos');expect(html).toContain('19 slides explicativos');
 expect(html).toContain('todos os tipos juntos');expect(html).toContain('no máximo um');expect(html).toContain('preservados');
});
