// Display-only: the saved document and its original image remain unchanged.
export function prepareAstryxImages(source) {
  if(!/data-astryx-lesson=["']/.test(source))return source;
  return source.replace(/<img\b[^>]*\bsrc=(["'])([^"']+)\1[^>]*>/gi,(tag,quote,src)=>{
    const raw=src.replace(/&amp;/g,'&');
    let url;
    try{url=new URL(raw,'https://astryx.local');}catch(_){return tag;}
    if(!/^\/api\/projects\/[A-Za-z0-9_-]+\/assets\/(?:ai_img|leonardo|gemini)_[a-f0-9]{8,32}\.(?:png|jpe?g|webp)$/i.test(url.pathname))return tag;
    url.searchParams.set('astryx_image','v1');
    const value=(raw.startsWith('/')?url.pathname+url.search+url.hash:url.href).replace(/&/g,'&amp;');
    tag=tag.replace(src,value);
    return /\bdecoding=/.test(tag)?tag:tag.replace(/<img/i,'<img decoding="async"');
  });
}

export function prepareAssessmentImages(value) {
  if(Array.isArray(value))return value.map(prepareAssessmentImages);
  if(!value||typeof value!=='object')return value;
  const result=Object.fromEntries(Object.entries(value).map(([k,v])=>[k,prepareAssessmentImages(v)]));
  if(result.kind==='image'&&typeof result.url==='string'){
    let url;
    try{url=new URL(result.url,'https://astryx.local');}catch(_){return result;}
    if(/^\/api\/projects\/[A-Za-z0-9_-]+\/assets\/(?:assessment|ai_img|leonardo|gemini)_[a-f0-9]{8,32}\.(?:png|jpe?g|webp)$/i.test(url.pathname)){
      url.searchParams.set('astryx_image','v1');
      result.url=result.url.startsWith('/')?url.pathname+url.search+url.hash:url.href;
    }
  }
  return result;
}
