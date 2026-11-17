(function(){
 'use strict';
 var viewer,pan,picture,lastFocus;
 function openImage(src,label){
  if(!src)return;
  if(!viewer){
   viewer=document.createElement('dialog');viewer.className='course-image-dialog';viewer.setAttribute('aria-label','Imagem ampliada');
   var tools=document.createElement('div');tools.className='course-image-tools';
   var title=document.createElement('strong');title.textContent='Imagem inteira — amplie para ler os detalhes';tools.appendChild(title);
   var zoom=document.createElement('button');zoom.type='button';zoom.className='course-image-enlarge';zoom.textContent='Ampliar 2×';zoom.onclick=function(){var big=picture.dataset.zoom!=='true';picture.dataset.zoom=String(big);picture.style.width=big?(pan.clientWidth*2)+'px':'100%';picture.style.height=big?'auto':'100%';zoom.textContent=big?'Ver imagem inteira':'Ampliar 2×';};tools.appendChild(zoom);
   var close=document.createElement('button');close.type='button';close.className='course-image-enlarge';close.textContent='Fechar imagem';close.onclick=function(){viewer.close();};tools.appendChild(close);
   pan=document.createElement('div');pan.className='course-image-pan';pan.tabIndex=0;pan.setAttribute('aria-label','Área da imagem; role para explorar quando ampliada');picture=document.createElement('img');pan.appendChild(picture);viewer.appendChild(tools);viewer.appendChild(pan);document.body.appendChild(viewer);
   viewer.addEventListener('close',function(){if(lastFocus&&lastFocus.isConnected)lastFocus.focus();});
  }
  lastFocus=document.activeElement;picture.src=src;picture.alt=label||'Slide do curso';picture.dataset.zoom='false';picture.style.width='100%';picture.style.height='100%';viewer.querySelector('button').textContent='Ampliar 2×';pan.scrollTop=pan.scrollLeft=0;viewer.showModal();
 }
 function attach(parent,source,label){
  if(!parent||parent.querySelector(':scope > .course-image-enlarge'))return;
  var button=document.createElement('button');button.type='button';button.className='course-image-enlarge';button.textContent='Ampliar imagem';button.setAttribute('aria-label','Ampliar imagem: '+(label||'slide'));
  button.onclick=function(e){e.preventDefault();e.stopPropagation();openImage(source(),label);};parent.appendChild(button);
 }
 function scan(){
  document.querySelectorAll('.sp-visual-canvas[data-course-visual]').forEach(function(stage){if(!stage.closest('[data-locked="true"]'))attach(stage.parentElement,function(){var bg=getComputedStyle(stage).backgroundImage;return /^url\(["']?(.*?)["']?\)$/.exec(bg)?.[1];},stage.dataset.imageLabel);});
  document.querySelectorAll('.sp-image:not(.sp-clickable):not(.sp-interactive),.sp-pdf-pages,.sp-evidence').forEach(function(frame){var img=frame.querySelector('img');if(img&&!frame.closest('[data-locked="true"]')){frame.style.flexWrap='wrap';attach(frame,function(){return img.currentSrc||img.src;},img.alt);}});
  var bg=document.querySelector('#slide-container .slide-background,#slide-container .course-slide-image');
  var wrapper=document.getElementById('slide-wrapper');
  if(bg){attach(wrapper||bg.parentElement,function(){var current=document.querySelector('#slide-container .slide-background,#slide-container .course-slide-image');return current&&(current.currentSrc||current.src);},'Slide atual');}
  var control=wrapper&&wrapper.querySelector(':scope > .course-image-enlarge');
  if(control){control.classList.add('course-slide-enlarge');control.hidden=!bg;}
 }
 var pending=false;function schedule(){if(pending)return;pending=true;requestAnimationFrame(function(){pending=false;scan();});}
 function start(){scan();new MutationObserver(schedule).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['data-locked']});}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
