import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ImprovementHtmlPreview,{previewDocument} from './ImprovementHtmlPreview';
test('interactive preview allows scripts in opaque sandbox, never same-origin or blocked pointer events',()=>{
 const html=renderToStaticMarkup(<ImprovementHtmlPreview htmlParts={['<!DOCTYPE html><html><head></head><body><script>render()</script></body></html>']} label="Quiz"/>);
 expect(html).toContain('sandbox="allow-scripts"');expect(html).not.toContain('allow-same-origin');expect(html).not.toContain('pointer-events');
 expect(html).toContain('height:560px');expect(html).toContain('connect-src');
});
test('complete documents are not nested in another body and fragments get their own document',()=>{
 const full='<!DOCTYPE html><html><head></head><body>Quiz</body></html>';
 expect((previewDocument(full).match(/<html>/g)||[]).length).toBe(1);
 expect(previewDocument('<h2>Resumo</h2>')).toContain('<body><h2>Resumo</h2></body>');
});
