import React,{useEffect,useState} from 'react';
import axios from 'axios';
import {getApiUrl} from '../utils/apiUrl';
import {staticCoverDocument} from '../utils/courseCover';

export default function SlideKilnCover({projectId,revision,visible,size,title}) {
  const [cover,setCover]=useState(null);
  const [failed,setFailed]=useState(false);
  useEffect(()=>{
    if(!visible)return;
    let active=true;const controller=new AbortController();
    setCover(null);setFailed(false);
    axios.get(`${getApiUrl()}/api/projects/${encodeURIComponent(projectId)}/slidekiln-cover`,{signal:controller.signal})
      .then(({data})=>{
        if(!active)return;
        if(!data?.html||!(data.width>0&&data.height>0))throw new Error('Capa indisponível');
        setCover({...data,html:staticCoverDocument(data.html,undefined,{offline:true})});
      }).catch(()=>{if(active)setFailed(true);});
    return ()=>{active=false;controller.abort();};
  },[projectId,revision,visible]);
  if(!cover)return <div role="status" style={{position:'absolute',inset:0,display:'grid',placeItems:'center',padding:16,textAlign:'center',background:'#e2e8f0',color:'#334155',fontSize:12}}>{failed?`${title} — Capa indisponível`:'Preparando capa…'}</div>;
  const scale=Math.min(size.width/cover.width,size.height/cover.height);
  return <iframe title={`Capa estática de ${title}`} srcDoc={cover.html} sandbox="" tabIndex={-1} aria-hidden="true" referrerPolicy="no-referrer"
    style={{position:'absolute',border:0,width:cover.width,height:cover.height,left:(size.width-cover.width*scale)/2,top:(size.height-cover.height*scale)/2,transform:`scale(${scale})`,transformOrigin:'0 0',pointerEvents:'none'}}/>;
}
