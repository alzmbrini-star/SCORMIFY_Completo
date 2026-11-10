import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {VideoLibraryDialog} from './VideoLibraryDialog';
jest.mock('../../../components/ui/dialog',()=>Object.fromEntries(['Dialog','DialogContent','DialogHeader','DialogTitle','DialogDescription','DialogFooter'].map(name=>[name,({children})=><div>{children}</div>])));
jest.mock('../../../components/ui/button',()=>({Button:({children,variant,size,...props})=><button {...props}>{children}</button>}));
jest.mock('../../../components/ui/input',()=>({Input:props=><input {...props}/>}));
jest.mock('../../../components/ui/scroll-area',()=>({ScrollArea:({children})=><div>{children}</div>}));
jest.mock('../utils',()=>({formatDuration:v=>v+'s',formatDateTime:v=>v,getStatusBadge:v=><span>{v}</span>}));
test('unifies providers, filters, and reuses a completed narrated/music video',async()=>{
  global.IS_REACT_ACT_ENVIRONMENT=true;
  const container=document.createElement('div');document.body.append(container);const root=createRoot(container);
  const add=jest.fn();
  const items=['heygen','runway','kling','heygem'].map(p=>({library_id:p+':id',video_id:'id',provider:p,title:p+' clip',status:'completed',video_url:'https://backend.test/'+p+'.mp4',narrated:p==='runway',music:p==='runway'}));
  try {
    await act(async()=>root.render(<VideoLibraryDialog open onOpenChange={()=>{}} videoLibraryItems={items} loadVideoLibrary={()=>{}} handleAddLibraryVideoToSlide={add}/>));
    expect(container.querySelectorAll('video').length).toBe(4);
    expect(container.textContent).toContain('Narração PT-BR');
    await act(async()=>{const select=container.querySelector('[aria-label="Provedor de vídeo"]');select.value='runway';select.dispatchEvent(new Event('change',{bubbles:true}));});
    expect(container.querySelectorAll('video').length).toBe(1);
    expect(container.textContent).toContain('Trilha sonora');
    await act(async()=>container.querySelector('[data-testid="add-video-id"]').click());
    expect(add).toHaveBeenCalledWith(items[1]);
    expect(container.querySelector('[data-testid="delete-video-id"]')).toBeNull();
  } finally {await act(async()=>root.unmount());container.remove();}
});
