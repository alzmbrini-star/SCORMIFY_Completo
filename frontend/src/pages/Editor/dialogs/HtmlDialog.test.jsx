import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import {HtmlDialog} from './MediaDialogs';
jest.mock('../../../components/RichTextEditor',()=>()=>null);
jest.mock('./KlingVideoForm',()=>()=>null);
jest.mock('../../../components/ComponentSceneReview',()=>()=>null);
jest.mock('../../../components/ui/button',()=>({Button:({variant,...p})=><button {...p}/>}));
jest.mock('../../../components/ui/input',()=>({Input:p=><input {...p}/>}));
jest.mock('../../../components/ui/dialog',()=>Object.fromEntries(['Dialog','DialogContent','DialogHeader','DialogTitle','DialogDescription','DialogFooter'].map(k=>[k,({children})=><div>{children}</div>])));
jest.mock('../../../components/ui/tabs',()=>Object.fromEntries(['Tabs','TabsContent','TabsList','TabsTrigger'].map(k=>[k,({children})=><div>{children}</div>])));
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
test('editing exposes export and save, never silently inserts, and cancel does not save',()=>{
 const host=document.createElement('div');document.body.appendChild(host);const root=createRoot(host),save=jest.fn(),download=jest.fn(),close=jest.fn();
 const html='<body data-sim-engine="finite-rules-v1">Scene</body>';
 act(()=>root.render(<HtmlDialog open editingSimulator onOpenChange={close} htmlConfig={{content:html}} setHtmlConfig={()=>{}}
  htmlDialogTab="ai" setHtmlDialogTab={()=>{}} aiHtmlPrompt="" setAiHtmlPrompt={()=>{}} aiHtmlResult={html} setAiHtmlResult={()=>{}}
  aiHtmlLoading={false} aiHtmlProgress="" handleAddHtml={save} handleGenerateHtmlAI={()=>{}} handleInsertAiHtml={save} onDownloadHtml={download}/>));
 expect(host.textContent).toContain('Editar simulador');expect(host.textContent).toContain('sem criar outro elemento');
 const buttons=[...host.querySelectorAll('button')];expect(buttons.some(b=>b.textContent==='Inserir no Slide')).toBe(false);
 act(()=>buttons.filter(b=>b.textContent==='Baixar HTML').at(-1).click());expect(download).toHaveBeenCalledWith(html);
 act(()=>buttons.find(b=>b.textContent==='Cancelar').click());expect(close).toHaveBeenCalledWith(false);expect(save).not.toHaveBeenCalled();
 act(()=>host.querySelector('[data-testid="ai-html-insert-btn"]').click());expect(save).toHaveBeenCalledTimes(1);
 act(()=>root.unmount());host.remove();
});
