import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {ExportDialog} from './ExportDialog';
jest.mock('../../../components/ui/dialog',()=>Object.fromEntries(['Dialog','DialogContent','DialogHeader','DialogTitle','DialogDescription','DialogFooter'].map(name=>[name,({children})=><div>{children}</div>])));
jest.mock('../../../components/ui/button',()=>({Button:({children,...props})=><button {...props}>{children}</button>}));
jest.mock('../../../components/ui/switch',()=>({Switch:({checked,onCheckedChange,...props})=><button role="switch" aria-checked={checked} onClick={()=>onCheckedChange(!checked)} {...props}/>}));
let div,root,props;
global.IS_REACT_ACT_ENVIRONMENT=true;
beforeEach(()=>{div=document.createElement('div');document.body.appendChild(div);root=createRoot(div);props={open:true,currentProject:{id:'p',singlePageMode:false,enableVlibras:true},handleExport:jest.fn(),handleExportHTML:jest.fn()};});
afterEach(()=>{act(()=>root.unmount());div.remove();});
test('local selection immediately reaches both exporters without mutating saved course',async()=>{
 const before=JSON.stringify(props.currentProject);
 await act(async()=>root.render(<ExportDialog {...props}/>));
 await act(async()=>div.querySelector('[data-testid=single-page-toggle]').click());
 await act(async()=>div.querySelector('[data-testid=vlibras-toggle]').click());
 await act(async()=>div.querySelector('[data-testid=generate-html-btn]').click());
 await act(async()=>div.querySelector('[data-testid=generate-scorm-btn]').click());
 expect(props.handleExportHTML).toHaveBeenCalledWith({singlePage:true,enableVlibras:false});
 expect(props.handleExport).toHaveBeenCalledWith({singlePage:true,enableVlibras:false});
 expect(JSON.stringify(props.currentProject)).toBe(before);
 await act(async()=>div.querySelector('[data-testid=single-page-toggle]').click());
 await act(async()=>div.querySelector('[data-testid=generate-html-btn]').click());
 expect(props.handleExportHTML).toHaveBeenLastCalledWith({singlePage:false,enableVlibras:false});
});
test('guided course stays in slides and loading shows progress with disabled controls',async()=>{
 props.currentProject={id:'p',singlePageMode:true,course:{metadata:{guidedPath:true}}};
 await act(async()=>root.render(<ExportDialog {...props}/>));
 expect(div.querySelector('[data-testid=single-page-toggle]').disabled).toBe(true);
 await act(async()=>div.querySelector('[data-testid=generate-scorm-btn]').click());
 expect(props.handleExport).toHaveBeenCalledWith({singlePage:false,enableVlibras:true});
 await act(async()=>root.render(<ExportDialog {...props} exportLoading videoExportProgress={42} videoExportMessage="Preparando · Tarefa abc"/>));
 expect(div.querySelector('[role=status]').textContent).toContain('Tarefa abc');
 expect(div.querySelector('progress').value).toBe(42);
 expect(div.querySelector('[data-testid=vlibras-toggle]').disabled).toBe(true);
});
test('failure remains visible after export stops',async()=>{
 await act(async()=>root.render(<ExportDialog {...props} exportLoading={false} videoExportMessage="Falha na exportação · Tarefa abc. O curso não foi alterado."/>));
 expect(div.querySelector('[role=alert]').textContent).toContain('Tarefa abc');
});
