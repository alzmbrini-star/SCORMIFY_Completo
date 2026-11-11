import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ConfigPanel from './ConfigPanel';
jest.mock('@/lib/utils',()=>({cn:(...values)=>values.filter(Boolean).join(' ')}),{virtual:true});
jest.mock('../../../components/ui/select',()=>{const Box=({children})=><div>{children}</div>;return {Select:Box,SelectTrigger:Box,SelectValue:()=>null,SelectContent:Box,SelectItem:Box};});
jest.mock('../../../components/ui/slider',()=>({Slider:()=>null}));
jest.mock('../../../components/ui/scroll-area',()=>({ScrollArea:({children})=><div>{children}</div>}));
jest.mock('../../../components/ui/checkbox',()=>({Checkbox:()=>null}));
jest.mock('../../../components/ui/tabs',()=>{const Box=({children})=><div>{children}</div>;return {Tabs:Box,TabsList:Box,TabsTrigger:Box,TabsContent:Box};});
jest.mock('../../../components/AnimPreviewButton',()=>({AnimPreviewButton:()=>null}));
jest.mock('../../../components/SimulatorExperienceOptions',()=>()=>null);
jest.mock('../../../contexts/AuthContext',()=>({authHeaders:()=>({}),useAuth:()=>({canCreateSimulators:false})}));

test('guided mode uses interactive assessments and exposes image-credit notice without replacing existing options',()=>{
 const html=renderToStaticMarkup(<ConfigPanel config={{title:'Planejamento',visualCourseMode:'guided_practice_project',enabledResources:{}}} setConfig={()=>{}} loading={false} templates={[]} designTemplates={[]}/>);
 expect(html).toContain('Avaliações interativas');expect(html).toContain('sem o Quiz tradicional');
 expect(html).toContain('Gerar imagem IA para cada questão e salvar na biblioteca');
 expect(html).toContain('Imagens das avaliações consomem créditos');
 expect(html).toMatch(/data-testid="guidedQuestionsPerUnit"[^>]*value="3"/);
 expect(html).toMatch(/data-testid="guidedPassingScore"[^>]*value="80"/);
});
