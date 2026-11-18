/* Shared audible-video policy for exported HTML and SCORM. No network or writes. */
(function(global){
 'use strict';
 function hasSound(course){
  return !!(course && ((course.globalAudio && course.globalAudio.src) || (course.slides || []).some(function(slide){
   return (slide.audio || []).some(function(a){return !!a.src;}) || (slide.elements || []).some(function(e){return String(e.type).toLowerCase()==='video';});
  })));
 }
 function create(options){
  var unlocked=false, muted=false, volume=0.7, intent=new WeakMap(), pending=new WeakSet();
  function videos(){return document.querySelectorAll(options.root+' video.local-video');}
  function apply(video){video.muted=muted || intent.get(video)===true;video.volume=volume;}
  function blocked(error){
   if(error && error.name==='NotAllowedError')options.showGate();
  }
  function prepare(video,explicitMuted){intent.set(video,explicitMuted===true);apply(video);}
  function play(video){
   apply(video);
   if(!unlocked){video.pause();return;}
   if(pending.has(video))return;
   try{
    var result=video.play();
    if(result && result.then){
     pending.add(video);
     result.then(function(){pending.delete(video);},function(error){
      pending.delete(video);
      // Never turn a blocked audible video into silent autoplay.
      if(error && error.name==='NotAllowedError'){
       video.controls=true;video.style.pointerEvents='auto';blocked(error);
      }
     });
    }
   }catch(error){blocked(error);}
  }
  function unlock(){unlocked=true;videos().forEach(play);}
  function setMuted(value){muted=!!value;videos().forEach(apply);return muted;}
  function setVolume(value){var number=Number(value);if(Number.isFinite(number))volume=Math.max(0,Math.min(1,number));videos().forEach(apply);}
  return {prepare:prepare,play:play,unlock:unlock,blocked:blocked,isUnlocked:function(){return unlocked;},
   isMuted:function(){return muted;},volume:function(){return volume;},setMuted:setMuted,setVolume:setVolume};
 }
 global.ScormifyMediaSound={hasSound:hasSound,create:create};
})(window);
