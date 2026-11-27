import React,{useEffect,useMemo,useRef,useState} from 'react';
import {coverAssetUrl,coverDimensions,coverElementRect,staticCoverDocument} from '../utils/courseCover';
import {imageShadowStyle} from '../utils/imageShadow';
import SlideKilnCover from './SlideKilnCover';

function PassiveHtml({html,title}) {
  const document=useMemo(()=>staticCoverDocument(html),[html]);
  return document ? <iframe title={title} srcDoc={document} sandbox="" tabIndex={-1} aria-hidden="true"
    referrerPolicy="no-referrer" style={{width:'100%',height:'100%',border:0,background:'transparent',pointerEvents:'none'}}/> : null;
}

export default function CourseCoverPreview({project}) {
  const slide=project.course?.slides?.[0];
  const title=project.title || project.name || slide?.title || 'Curso';
  const host=useRef(null);
  const [size,setSize]=useState({width:240,height:135});
  const [visible,setVisible]=useState(typeof IntersectionObserver === 'undefined');
  const [failed,setFailed]=useState({});
  const stage=coverDimensions(slide,project.course);
  useEffect(()=>{setFailed({});},[project.id,slide]);
  useEffect(()=>{
    const node=host.current;
    const measure=()=>{const r=node.getBoundingClientRect();if(r.width>0&&r.height>0)setSize({width:r.width,height:r.height});};
    measure();
    const resize=typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
    resize?.observe(node);
    const intersection=typeof IntersectionObserver !== 'undefined' ? new IntersectionObserver(entries=>setVisible(entries[0].isIntersecting),{rootMargin:'240px'}) : null;
    intersection?.observe(node);
    return ()=>{resize?.disconnect();intersection?.disconnect();};
  },[]);
  const scale=Math.min(size.width/stage.width,size.height/stage.height);
  const elements=(slide?.elements || []).filter(e=>e.visible!==false && e.style?.opacity!==0);
  const background=slide?.background || '#f1f5f9';
  const fail=key=>()=>setFailed(prev=>({...prev,[key]:true}));
  const source=coverAssetUrl(slide?.backgroundImage);
  const saved=coverAssetUrl(project.thumbnail || slide?.thumbnail);
  const empty=!slide || (!source && !elements.length);
  const slidekiln=elements.find(e=>e.type==='html'&&e.source==='slidekiln');
  const fallback=<div style={{position:'absolute',inset:0,display:'flex',alignItems:'center',justifyContent:'center',padding:16,textAlign:'center',background:'#e2e8f0',color:'#334155',fontSize:12}}>{title}</div>;
  return <div ref={host} data-testid="course-cover-preview" role="img" aria-label={`Capa do curso ${title}`}
    style={{width:'100%',height:'100%',position:'relative',overflow:'hidden',background,pointerEvents:'none'}}>
    {visible && <>
      {slidekiln ? <SlideKilnCover projectId={project.id} revision={slidekiln.htmlContent} visible={visible} size={size} title={title}/> : empty ? (saved && !failed.saved ? <img src={saved} alt="" onError={fail('saved')} style={{width:'100%',height:'100%',objectFit:'contain'}}/> : fallback) :
      <div data-testid="course-cover-stage" style={{position:'absolute',width:stage.width,height:stage.height,
        left:(size.width-stage.width*scale)/2,top:(size.height-stage.height*scale)/2,transform:`scale(${scale})`,transformOrigin:'0 0',background,overflow:'hidden'}}>
        {source && !failed.background && <img src={source} alt="" onError={fail('background')} style={{position:'absolute',inset:0,width:'100%',height:'100%',objectFit:slide.backgroundImageFit==='cover'?'cover':'contain'}}/>}
        {failed.background && !elements.length && <div style={{fontSize:48,padding:60,color:'#334155',background:'#e2e8f0'}}>{title} — Imagem da capa indisponível</div>}
        {elements.map((element,index)=>{
          const style={position:'absolute',...coverElementRect(element,stage),zIndex:element.zIndex || 0,
            transform:element.rotation?`rotate(${element.rotation}deg)`:undefined,opacity:element.style?.opacity ?? 1,
            overflow:element.type==='image'?'visible':'hidden'};
          const key=element.id || index;
          const html=element.htmlContent;
          if(element.type==='html' || element.type==='text' && /<[a-z][\s\S]*>/i.test(element.content || '')) {
            return <div key={key} style={style}><PassiveHtml html={html || element.content} title={`Capa ${title}, bloco ${index+1}`}/></div>;
          }
          if(element.type==='image') return <div key={key} style={style}>{!failed[key] && coverAssetUrl(element.src) ? <img src={coverAssetUrl(element.src)} alt="" onError={fail(key)}
            style={{width:'100%',height:'100%',objectFit:element.objectFit || 'contain',display:'block',...imageShadowStyle(element.imageShadow)}}/> :
            <div style={{height:'100%',display:'grid',placeItems:'center',background:'#e2e8f0',color:'#475569',fontSize:32}}>Imagem indisponível</div>}</div>;
          if(element.type==='text' || element.type==='shape' || element.type==='button') {
            const s=element.style || {};
            return <div key={key} style={{...style,fontSize:s.fontSize || 16,fontFamily:s.fontFamily || 'Arial, sans-serif',
              fontWeight:s.fontWeight || 'normal',color:s.fontColor || s.color || '#000',textAlign:s.textAlign || 'left',
              background:element.type==='shape'?(s.fill || '#7c3aed'):(s.transparentBackground?'transparent':s.backgroundColor || 'transparent'),
              border:s.stroke?`2px solid ${s.stroke}`:undefined,borderRadius:['ellipse','oval'].includes(element.shapeType)?'50%':s.borderRadius || 0,
              whiteSpace:'pre-wrap',overflowWrap:'break-word',padding:element.type==='text'?8:0,boxSizing:'border-box',lineHeight:s.lineHeight || 1.2}}>
              {element.buttonText || element.content || ''}</div>;
          }
          const poster=coverAssetUrl(element.poster || element.thumbnail);
          return <div key={key} style={{...style,display:'grid',placeItems:'center',background:'#1e293b',color:'#fff',fontSize:32}}>
            {poster ? <img src={poster} alt="" style={{width:'100%',height:'100%',objectFit:'contain'}}/> : element.quizConfig?.title || (element.type==='video'?'▶ Vídeo':element.type==='quiz'?'Quiz':'Conteúdo interativo')}
          </div>;
        })}
      </div>}
    </>}
  </div>;
}
