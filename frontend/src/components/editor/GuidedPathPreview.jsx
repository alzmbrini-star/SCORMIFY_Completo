import React, {useEffect, useMemo, useRef} from 'react';
import '../../utils/guidedCore';
import '../../utils/guidedHost';
import './guidedHost.css';

export function previewPlan(course) {
  const cfg=course?.metadata?.guidedPath;
  if(cfg?.version!==1)return null;
  const slides=(course.slides||[]).flatMap((s,index)=>{
    if(!s.guidedStage)return [];
    let activity=(s.elements||[]).find(e=>e.guidedActivity)?.guidedActivity||null;
    if(['assessment','final'].includes(activity?.kind))activity={id:activity.id,kind:activity.kind,title:activity.title};
    return [{id:s.id,index,title:s.title,unitId:s.guidedUnitId,stage:s.guidedStage,activity}];
  });
  const text=JSON.stringify(slides);let hash=0;for(let i=0;i<text.length;i++)hash=((hash<<5)-hash+text.charCodeAt(i))|0;
  return {...cfg,title:course.metadata.title,slides,fingerprint:'preview-'+hash};
}

export default function GuidedPathPreview({course,index,onNavigate}) {
  const container=useRef(null),instance=useRef(null),navigate=useRef(onNavigate);
  navigate.current=onNavigate;
  const plan=useMemo(()=>previewPlan(course),[course]);
  useEffect(()=>{
    if(!plan||!container.current)return;
    instance.current=window.mountScormifyGuided(plan,{preview:true,container:container.current,navigate:i=>navigate.current?.(i)});
    instance.current.slide(index);
    return ()=>{instance.current?.destroy();instance.current=null;};
    // Navigation changes update the instance without resetting the preview.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[plan]);
  useEffect(()=>{instance.current?.slide(index);},[index,plan]);
  return plan?<div ref={container} className="shrink-0" data-testid="guided-path-preview"/>:null;
}
