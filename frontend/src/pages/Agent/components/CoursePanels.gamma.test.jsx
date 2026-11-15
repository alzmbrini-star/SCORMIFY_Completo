import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import GammaVisualAnalysis,{GammaVisualLoading} from './GammaVisualAnalysis';

const props={course:{id:'test',name:'Gamma',source:'gamma'},selectedImprovements:[],toggleImprovement:()=>{}};
test('Gamma loading explains image reading, credits and read-only analysis',()=>{
 const html=renderToStaticMarkup(<GammaVisualLoading/>);
 expect(html).toContain('Lendo as imagens');
 expect(html).toContain('créditos');
 expect(html).toContain('Nenhum slide é alterado');
});
test('visual evidence is readable per slide and safely escaped; legacy source absence is explicit',()=>{
 const analysis={overallScore:7,strengths:[],improvements:[],suggestedNewSlides:[],missingElements:[],visualAnalysis:{readSlides:1,totalSlides:2,sourceAvailable:false,slides:[{slideId:'a',slideIndex:0,status:'read',summary:'Conceito específico',visibleText:'<script>fonte</script>'},{slideId:'b',slideIndex:1,status:'unreadable'}]}};
 const html=renderToStaticMarkup(<GammaVisualAnalysis reading={analysis.visualAnalysis}/>);
 expect(html).toContain('1 de 2 slides lidos');
 expect(html).toContain('Fonte original indisponível');
 expect(html).toContain('interações existentes serão preservadas');
 expect(html).toContain('Conceito específico');
 expect(html).toContain('sem sugestões inventadas');
 expect(html).toContain('&lt;script&gt;fonte&lt;/script&gt;');
 expect(html).not.toContain('<script>');
});
