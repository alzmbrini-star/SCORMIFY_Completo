import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import StoryboardLearningContext from './StoryboardLearningContext';

test('native screenshot is preserved, not offered as a paid AI image',()=>{
  const html=renderToStaticMarkup(<StoryboardLearningContext slide={{sourceImageOnly:true,imageSuggestion:{prompt:'Do not redraw'}}}/>);
  expect(html).toContain('Imagem original preservada');
  expect(html).not.toContain('Do not redraw');
});
test('complement shows rationale and links separately from mandatory instruction',()=>{
  const html=renderToStaticMarkup(<StoryboardLearningContext slide={{isComplement:true,learningRationale:'Praticar decisões com feedback',reinforcesSourceRefs:['SRC001.I001']}}/>);
  expect(html).toContain('Complemento didático');expect(html).toContain('Praticar decisões');
  expect(html).toContain('SRC001.I001');expect(html).not.toContain('Ensino obrigatório da fonte');
});
test('image suggestion is reviewable in media, escaped and not an image generation action',()=>{
  const html=renderToStaticMarkup(<StoryboardLearningContext slide={{sourceRequired:true,imageSuggestion:{purpose:'Mostrar mecanismo',prompt:'<script>bad</script>'}}}/>);
  expect(html).toContain('Ensino obrigatório da fonte');expect(html).toContain('revisar em Mídia');
  expect(html).toContain('pode consumir créditos');expect(html).not.toContain('<script>');
  expect(html).not.toContain('<img');expect(html).not.toContain('<button');
});
test('legacy slides without metadata have no invented recommendation',()=>{
  expect(renderToStaticMarkup(<StoryboardLearningContext slide={{title:'Antigo'}}/>)).toBe('');
});
