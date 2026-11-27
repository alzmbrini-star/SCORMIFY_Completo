import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import axios from 'axios';
import {useEditorExport} from './useEditorExport';
jest.mock('axios',()=>({get:jest.fn(),post:jest.fn()}));
jest.mock('sonner',()=>({toast:{success:jest.fn(),warning:jest.fn(),error:jest.fn()}}));
jest.mock('../../../utils/apiUrl',()=>({getApiUrl:()=> 'https://backend.invalid'}));
jest.mock('../../../utils/clientVideoExport',()=>({generateVideoClientSide:jest.fn()}));
let div,root,api,exportScorm;
global.IS_REACT_ACT_ENVIRONMENT=true;
function Harness(){api=useEditorExport({currentProject:{id:'p',singlePageMode:false},exportScorm});return null;}
beforeEach(()=>{jest.clearAllMocks();div=document.createElement('div');root=createRoot(div);exportScorm=jest.fn();act(()=>root.render(<Harness/>));});
afterEach(()=>{act(()=>root.unmount());});
test('HTML uses explicit local options and retains failed task diagnostics',async()=>{
 axios.post.mockResolvedValue({data:{jobId:'html-job'}});
 axios.get.mockResolvedValue({data:{status:'failed',message:'Falha no pacote',progress:25}});
 const log=jest.spyOn(console,'error').mockImplementation(()=>{});
 await act(async()=>api.handleExportHTML({singlePage:true,enableVlibras:false}));
 expect(axios.post).toHaveBeenCalledWith('https://backend.invalid/api/course/p/export-html',{singlePage:true,enableVlibras:false});
 expect(api.exportLoading).toBe(false);
 expect(api.videoExportMessage).toContain('html-job');
 expect(api.videoExportMessage).toContain('O curso não foi alterado');
 log.mockRestore();
});
test('SCORM forwards both options and completes async download',async()=>{
 exportScorm.mockResolvedValue({jobId:'scorm-job'});
 axios.get.mockResolvedValue({data:{status:'completed',result:{downloadUrl:'/download/file.zip',mode:'single_page'}}});
 await act(async()=>api.handleExport({singlePage:true,enableVlibras:false}));
 expect(exportScorm).toHaveBeenCalledWith({singlePage:true,enableVlibras:false});
 expect(api.downloadUrl).toBe('https://backend.invalid/download/file.zip');
 expect(api.exportLoading).toBe(false);
});
