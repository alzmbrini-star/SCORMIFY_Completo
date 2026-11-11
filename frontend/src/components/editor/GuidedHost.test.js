import '../../utils/guidedCore';
import '../../utils/guidedHost';

test('preview receives only its own canonical frame result and never writes LMS scores',()=>{
 document.body.innerHTML='<div id="preview"></div><iframe data-guided-id="activity"></iframe>';
 const frame=document.querySelector('iframe');const setValue=jest.fn();
 window.ScormAPI={isInitialized:()=>true,getAPI:()=>({LMSGetValue:()=>'',LMSSetValue:setValue}),recordAssessment:setValue};
 const plan={version:1,id:'isolated-preview',fingerprint:'x',units:[],unitPassingScore:100,passingScore:80,slides:[{id:'slide',index:0,stage:'final',activity:{id:'activity',kind:'final'}}]};
 const host=window.mountScormifyGuided(plan,{preview:true,container:document.getElementById('preview')});
 const send=(source,score)=>window.dispatchEvent(new MessageEvent('message',{source,data:{type:'scormify-guided-assessment-result',id:'activity',score}}));
 send(window,100);expect(host.canComplete()).toBe(false);
 send(frame.contentWindow,NaN);expect(host.canComplete()).toBe(false);
 send(frame.contentWindow,100);expect(host.canComplete()).toBe(true);
 send(frame.contentWindow,0);expect(host.state().state.scores.activity).toBe(100);
 expect(setValue).not.toHaveBeenCalled();
 host.destroy();expect(document.getElementById('guided-toolbar')).toBeNull();delete window.ScormAPI;
});
