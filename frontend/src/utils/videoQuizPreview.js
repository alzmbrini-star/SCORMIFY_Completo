import { videoQuizSnapshot } from './videoQuizDraft';

// Match the export player's isolated-activity rule. Never reflow a custom
// composition with overlays, annotations or other authored elements.
export function fluidVideoQuizSlide(slide) {
  const items=slide?.elements || [], item=items[0];
  return items.length===1 && item.type==='html' && Boolean(videoQuizSnapshot(item)) &&
    !(slide.annotations || []).length && (item.x || 0)<=20 && (item.y || 0)<=20 &&
    item.width >= (slide.width || 960)*.9 && item.height >= (slide.height || 540)*.9;
}

// Preview-only transport. The existing activity still owns seeking, question
// gates, retries and results. Commands operate its existing accessible controls.
export function videoQuizPreviewTimelineRuntime() {
  var video=document.getElementById('video'),snapshot=document.getElementById('video-quiz-data');
  if(!video||!snapshot||video.dataset.previewTimeline)return;
  var config;try{config=JSON.parse(snapshot.textContent);}catch(_){return;}
  video.dataset.previewTimeline='v1';
  function publish(){
    if(!Number.isFinite(video.duration)||video.duration<=0)return;
    window.parent.postMessage({type:'scormify-video-preview-clock',key:config.key,time:video.currentTime,duration:video.duration,playing:!video.paused&&!video.ended},'*');
  }
  ['loadedmetadata','timeupdate','play','pause','seeked','ended'].forEach(function(name){video.addEventListener(name,publish);});
  window.addEventListener('message',function(event){
    var msg=event.data;
    if(event.source!==window.parent||!msg||msg.type!=='scormify-video-preview-control'||msg.key!==config.key)return;
    var play=document.getElementById('play'),seek=document.getElementById('seek');
    if(msg.action==='play'&&video.paused&&play)play.click();
    else if(msg.action==='pause'&&!video.paused&&play)play.click();
    else if(msg.action==='seek'&&seek&&Number.isFinite(msg.time)&&Number.isFinite(video.duration)){
      seek.value=String(Math.max(0,Math.min(video.duration,msg.time)));
      seek.dispatchEvent(new Event('input',{bubbles:true}));
    }
    publish();
  });
  publish();
}

export function withVideoQuizPreviewTimeline(html) {
  if(typeof html!=='string'||!html.includes('video-quiz-data')||html.includes('id="video-quiz-preview-clock-v1"'))return html;
  const snippet='<script id="video-quiz-preview-clock-v1">('+videoQuizPreviewTimelineRuntime.toString()+')();</script>';
  return /<\/body>/i.test(html)?html.replace(/<\/body>/i,snippet+'</body>'):html+snippet;
}

export function readVideoQuizPreviewClock(event, root, slide) {
  const msg=event.data;
  if(!msg||msg.type!=='scormify-video-preview-clock'||!Number.isFinite(msg.duration)||msg.duration<=0||msg.duration>86400||!Number.isFinite(msg.time)||msg.time<0||msg.time>msg.duration+.1||typeof msg.playing!=='boolean')return null;
  const known=(slide?.elements||[]).some(el=>videoQuizSnapshot(el)?.key===msg.key);
  const frame=[...(root?.querySelectorAll('iframe[data-video-quiz-key]')||[])].find(f=>f.contentWindow===event.source&&f.dataset.videoQuizKey===msg.key);
  return known&&frame?{time:msg.time,duration:msg.duration,playing:msg.playing}:null;
}

export function controlVideoQuizPreview(root, action, time) {
  const frame=root?.querySelector('iframe[data-video-quiz-key]');
  if(frame)frame.contentWindow?.postMessage({type:'scormify-video-preview-control',key:frame.dataset.videoQuizKey,action,time},'*');
}
