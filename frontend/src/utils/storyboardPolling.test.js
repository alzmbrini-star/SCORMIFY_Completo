import {waitForStoryboard} from './storyboardPolling';
const complete={step:'storyboarded',storyboard:{slides:[{id:'s'}]}};
const active={step:'storyboarding',storyboardProgress:{batch:0,total:4,message:'Gerando o primeiro lote'}};

test('polls sequentially and reports only completed batches',async()=>{
 const read=jest.fn().mockResolvedValueOnce(active).mockResolvedValueOnce(complete),delay=jest.fn().mockResolvedValue(),progress=jest.fn();
 expect(await waitForStoryboard(read,{delay,onProgress:progress})).toBe(complete);
 expect(read).toHaveBeenCalledTimes(2);expect(delay).toHaveBeenCalledTimes(1);
 expect(progress).toHaveBeenCalledWith('Gerando o primeiro lote (0%)');
});

test('expired worker enables a clear manual recovery without restarting anything',async()=>{
 const read=jest.fn().mockResolvedValue({step:'structured',error:'Retome os lotes salvos.',storyboardProgress:null});
 await expect(waitForStoryboard(read,{delay:jest.fn()})).rejects.toThrow('Retome os lotes salvos.');
 expect(read).toHaveBeenCalledTimes(1);
});

test('passing fifteen minutes is informational and does not abandon a live run',async()=>{
 const read=jest.fn().mockResolvedValueOnce(active).mockResolvedValueOnce(active).mockResolvedValueOnce(complete);
 const times=[0,900001,900002],notice=jest.fn();
 expect(await waitForStoryboard(read,{now:()=>times.shift()??900003,delay:()=>Promise.resolve(),onLongWait:notice})).toBe(complete);
 expect(notice).toHaveBeenCalledTimes(1);
});

test('temporary network failure reconnects; authentication failure stops cleanly',async()=>{
 const read=jest.fn().mockRejectedValueOnce(new Error('network')).mockResolvedValueOnce(complete),delay=jest.fn().mockResolvedValue();
 expect(await waitForStoryboard(read,{delay})).toBe(complete);expect(delay).toHaveBeenCalledTimes(1);
 const denied=new Error('Sua sessão expirou.');denied.permanent=true;
 await expect(waitForStoryboard(()=>Promise.reject(denied),{delay})).rejects.toThrow('sessão expirou');
 expect(delay).toHaveBeenCalledTimes(1);
});

test('closing the session aborts polling without a delayed timeout error',async()=>{
 const controller=new AbortController(),read=jest.fn().mockResolvedValue(active);
 await expect(waitForStoryboard(read,{signal:controller.signal,delay:async()=>controller.abort()})).rejects.toMatchObject({name:'AbortError'});
 expect(read).toHaveBeenCalledTimes(1);
});
