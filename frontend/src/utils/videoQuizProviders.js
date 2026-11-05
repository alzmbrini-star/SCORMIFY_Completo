export function videoQuizProviderRuntime(scope, settings) {
  'use strict';
  var area=scope||document,video=area.querySelector('#video'),data=area.querySelector('#video-quiz-data'),config;
  try{config=settings||JSON.parse(data.textContent);}catch(_){return;}
  if(!video||video.dataset.providerAdapter||['youtube','vimeo','bunny'].indexOf(config.provider)<0)return;
  var source;try{source=new URL(config.src);}catch(_){return;}
  var expected={youtube:'www.youtube.com',vimeo:'player.vimeo.com',bunny:'iframe.mediadelivery.net'};
  if(source.protocol!=='https:'||source.hostname!==expected[config.provider])return;
  video.dataset.providerAdapter=config.provider;
  var current=0,duration=NaN,paused=true,ended=false,ready=false,disposed=false,player=null,poll=null,pending=null;
  var host=document.createElement('div');host.id='hosted-video';host.style.cssText='position:relative;flex:1;min-height:0;width:100%;background:#080f1c;border-radius:9px;overflow:hidden';
  video.hidden=true;video.parentNode.insertBefore(host,video);
  var frame=document.createElement('iframe');frame.id='provider-player';frame.title='Vídeo '+config.provider;
  frame.allow='autoplay; fullscreen; encrypted-media; picture-in-picture';frame.allowFullscreen=true;
  frame.referrerPolicy='strict-origin-when-cross-origin';frame.style.cssText='border:0;width:100%;height:100%;display:block;min-height:170px';
  var barrier=document.createElement('p');barrier.setAttribute('role','status');barrier.textContent='Carregando player externo…';
  barrier.style.cssText='position:absolute;bottom:8px;left:8px;right:8px;margin:0;padding:8px;background:#142a43;color:#fff;font:14px system-ui;pointer-events:none';host.appendChild(barrier);
  function emit(name){video.dispatchEvent(new Event(name));}
  function fail(){if(disposed)return;barrier.hidden=false;barrier.textContent='Não foi possível conectar ao player. Verifique a internet, permissão de incorporação, domínio autorizado e validade do link. YouTube também exige uma origem HTTPS válida.';emit('error');}
  var timeout=setTimeout(function(){if(!ready)fail();},25000);
  function script(url,done){var s=document.createElement('script');s.src=url;s.onload=function(){if(!disposed)done();};s.onerror=fail;document.head.appendChild(s);}
  function metadata(value){
    value=Number(value);if(disposed||!Number.isFinite(value)||value<=0)return;
    duration=value;
    if(!ready){ready=true;clearTimeout(timeout);barrier.hidden=true;emit('loadedmetadata');}
  }
  function tick(value){
    if(disposed)return;value=Number(value);if(!Number.isFinite(value)||value<0)return;
    if(pending&&Math.abs(value-pending.time)>.6&&Date.now()-pending.at<1800)return;
    pending=null;current=value;emit('timeupdate');
  }
  function playing(){
    ended=false;if(!paused)return;paused=false;emit('play');
    // A pending question can synchronously pause the player in its play event.
    if(!paused)emit('playing');
  }
  function stopped(){if(paused)return;paused=true;emit('pause');}
  function finish(){ended=true;stopped();if(Number.isFinite(duration))current=duration;emit('timeupdate');emit('ended');}
  function seek(value){
    value=Number(value);if(!Number.isFinite(value))return;
    current=Math.max(0,Number.isFinite(duration)?Math.min(duration,value):value);ended=false;pending={time:current,at:Date.now()};
    if(ready&&player)player.seek(current);
    emit('seeking');emit('seeked');emit('timeupdate');
  }
  Object.defineProperties(video,{
    src:{configurable:true,get:function(){return config.src;},set:function(){}},
    currentTime:{configurable:true,get:function(){return current;},set:seek},
    duration:{configurable:true,get:function(){return duration;}},
    paused:{configurable:true,get:function(){return paused;}},
    ended:{configurable:true,get:function(){return ended;}},
    readyState:{configurable:true,get:function(){return ready?4:0;}}
  });
  video.play=function(){if(!ready||!player)return Promise.reject(new Error('Player externo carregando'));return Promise.resolve(player.play()).catch(function(e){fail();throw e;});};
  video.pause=function(){if(player&&ready)player.pause();stopped();};
  function safe(promise){if(promise&&promise.catch)promise.catch(fail);}
  if(config.provider==='youtube'){
    var id=source.pathname.split('/').pop(),mount=document.createElement('div');mount.id='youtube-mount';host.insertBefore(mount,barrier);
    function start(){
      if(disposed)return;
      var yt=new window.YT.Player(mount,{videoId:id,width:'100%',height:'100%',playerVars:{playsinline:1,rel:0,autoplay:0},events:{
        onReady:function(){frame=yt.getIframe();frame.style.cssText='border:0;width:100%;height:100%;display:block;min-height:170px';player={play:function(){yt.playVideo();},pause:function(){yt.pauseVideo();},seek:function(t){yt.seekTo(t,true);}};
          metadata(yt.getDuration());poll=setInterval(function(){metadata(yt.getDuration());tick(yt.getCurrentTime());},150);},
        onStateChange:function(e){if(e.data===1)playing();else if(e.data===2)stopped();else if(e.data===0)finish();else if(e.data===3)emit('waiting');},
        onError:fail
      }});
    }
    if(window.YT&&window.YT.Player)start();else {window.onYouTubeIframeAPIReady=start;script('https://www.youtube.com/iframe_api',function(){});}
  }else{
    source.searchParams.set('autoplay','false');source.searchParams.set('loop','false');
    frame.src=source.href;host.insertBefore(frame,barrier);
    if(config.provider==='vimeo'){
      script('https://player.vimeo.com/api/player.js',function(){
        var v=new window.Vimeo.Player(frame);
        player={play:function(){return v.play();},pause:function(){safe(v.pause());},seek:function(t){safe(v.setCurrentTime(t));}};
        v.on('play',playing);v.on('pause',stopped);v.on('ended',finish);v.on('error',fail);
        v.on('bufferstart',function(){emit('waiting');});v.on('bufferend',function(){if(!paused)emit('playing');});
        v.on('timeupdate',function(e){metadata(e.duration);tick(e.seconds);});
        v.on('seeked',function(e){tick(e.seconds);emit('seeking');});
        safe(v.ready().then(function(){return v.getDuration();}).then(metadata));
      });
    }else{
      script('https://cdn.embed.ly/player-0.1.0.min.js',function(){
        var b=new window.playerjs.Player(frame);
        b.on('ready',function(){
          player={play:function(){b.play();},pause:function(){b.pause();},seek:function(t){b.setCurrentTime(t);}};
          b.on('play',playing);b.on('pause',stopped);b.on('ended',finish);b.on('error',fail);
          b.on('timeupdate',function(e){metadata(e.duration);tick(e.seconds);});
          b.on('seeked',function(){b.getCurrentTime(function(t){tick(t);emit('seeking');});});
          b.getDuration(metadata);poll=setInterval(function(){if(!ready)b.getDuration(metadata);},500);
        });
      });
    }
  }
  function dispose(){disposed=true;clearTimeout(timeout);clearInterval(poll);if(player)player.pause();window.removeEventListener('pagehide',dispose);}
  window.addEventListener('pagehide',dispose);
  return dispose;
}

export function videoQuizSource(value) {
  let src=String(value||'').trim(), markup=src.startsWith('<');
  if(src.length>12000)throw new Error('Link de vídeo muito longo.');
  if(markup){const doc=new DOMParser().parseFromString(src,'text/html'),frames=doc.querySelectorAll('iframe');if(frames.length!==1)throw new Error('Cole uma URL ou um único iframe.');src=frames[0].getAttribute('src')||'';}
  if(src.startsWith('/api/')&&!markup)return {src,provider:'direct'};
  let u;try{u=new URL(src);}catch(_){throw new Error('Informe uma URL de vídeo válida.');}
  if(!['https:','http:'].includes(u.protocol)||u.username||u.password)throw new Error('Informe uma URL de vídeo válida.');
  const h=u.hostname.toLowerCase(),p=u.pathname.replace(/^\/+|\/+$/g,'').split('/');
  if(['youtube.com','www.youtube.com','m.youtube.com','youtube-nocookie.com','www.youtube-nocookie.com','youtu.be','www.youtu.be'].includes(h)){
    const id=h.endsWith('youtu.be')?p[0]:u.pathname==='/watch'?u.searchParams.get('v'):p.length===2&&['embed','shorts','live'].includes(p[0])?p[1]:'';
    if(!/^[A-Za-z0-9_-]{11}$/.test(id||''))throw new Error('Use o endereço de um vídeo do YouTube, não de uma lista.');
    return {src:'https://www.youtube.com/embed/'+id,provider:'youtube'};
  }
  if(['vimeo.com','www.vimeo.com','player.vimeo.com'].includes(h)){
    const id=p[0]==='video'?p[1]:p[0],hash=u.searchParams.get('h')||(p.length===2&&/^\d+$/.test(p[0])?p[1]:'');
    if(!/^\d+$/.test(id||'')||hash&&!/^[A-Za-z0-9]+$/.test(hash))throw new Error('Use o link do vídeo Vimeo ou o iframe do player.');
    return {src:'https://player.vimeo.com/video/'+id+(hash?'?h='+encodeURIComponent(hash):''),provider:'vimeo'};
  }
  if(h==='iframe.mediadelivery.net'){
    if(p.length!==3||!['embed','play'].includes(p[0])||!/^\d+$/.test(p[1])||!/^[a-fA-F0-9-]{36}$/.test(p[2]))throw new Error('Use o link Embed ou iframe completo do Bunny Stream.');
    return {src:'https://iframe.mediadelivery.net/embed/'+p.slice(1).join('/')+u.search,provider:'bunny'};
  }
  if(markup)throw new Error('Iframe permitido somente para Bunny, Vimeo ou YouTube.');
  return {src,provider:'direct'};
}

export function withVideoQuizProviders(html) {
  if(typeof html!=='string'||html.includes('id="video-quiz-providers-v1"'))return html;
  return html.replace(/(<script\b[^>]*\bid=["']video-quiz-data["'][^>]*>[\s\S]*?<\/script>)/i,
    match=>match+'<script id="video-quiz-providers-v1">('+videoQuizProviderRuntime.toString()+')();</script>');
}

