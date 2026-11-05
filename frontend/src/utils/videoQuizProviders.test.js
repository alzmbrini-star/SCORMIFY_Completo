import {videoQuizSource,withVideoQuizProviders,videoQuizProviderRuntime} from './videoQuizProviders';
import {hostedVideoQuizConfig,trustedHostedVideoQuizDocument} from './videoQuizHostedDocument';

describe('hosted video sources',()=>{
  test('same-origin capability is limited to fully rebuilt trusted documents',()=>{
    const config={src:'https://vimeo.com/76979871',checkpoints:[{at:4,question:'</script><script>evil()</script>',options:['A','B']}],key:'k'};
    const html='<script id="video-quiz-data" type="application/json">'+JSON.stringify(config).replace(/</g,'\\u003c')+'</script><script>stealParentSecrets()</script>';
    const safe=trustedHostedVideoQuizDocument(html);
    expect(safe).not.toContain('stealParentSecrets()');expect(safe).not.toContain('<script>evil()');expect(safe).toContain('video-quiz-runtime-v2');
    expect(hostedVideoQuizConfig({htmlContent:'<script>stealParentSecrets()</script>',videoQuizConfig:config})).toBeNull();
  });
  test.each([
    ['https://youtu.be/M7lc1UVf-VE','youtube','https://www.youtube.com/embed/M7lc1UVf-VE'],
    ['https://www.youtube.com/watch?v=M7lc1UVf-VE&list=abc','youtube','https://www.youtube.com/embed/M7lc1UVf-VE'],
    ['https://vimeo.com/76979871/ab12cd','vimeo','https://player.vimeo.com/video/76979871?h=ab12cd'],
    ['<iframe src="https://player.vimeo.com/video/76979871?h=secret" onload="alert(1)"></iframe>','vimeo','https://player.vimeo.com/video/76979871?h=secret'],
    ['https://iframe.mediadelivery.net/play/123/11111111-2222-3333-4444-555555555555?token=a%2Bb&expires=99','bunny','https://iframe.mediadelivery.net/play/123/11111111-2222-3333-4444-555555555555?token=a%2Bb&expires=99'],
    ['/api/projects/p/assets/alpha.webm','direct','/api/projects/p/assets/alpha.webm']
  ])('normalizes %s without executing iframe markup',(url,provider,src)=>expect(videoQuizSource(url)).toEqual({provider,src}));
  test.each(['javascript:alert(1)','https://youtube.com.evil.test/video','<iframe src="https://evil.test/x"></iframe>','https://youtube.com/watch?v=bad','https://user:secret@vimeo.com/123'])('rejects unsafe/invalid embedding %s',url=>{
    if(url==='https://youtube.com.evil.test/video')expect(videoQuizSource(url).provider).toBe('direct');
    else expect(()=>videoQuizSource(url)).toThrow();
  });
  test('adapter is inserted before the existing engine once; data unchanged',()=>{
    const html='<body><video id="video"></video><script id="video-quiz-data">{"provider":"vimeo"}</script><script>core();</script></body>';
    const next=withVideoQuizProviders(html);
    expect(next.indexOf('id="video-quiz-providers-v1"')).toBeLessThan(next.indexOf('core();'));
    expect(next).toContain('{"provider":"vimeo"}');expect(withVideoQuizProviders(next)).toBe(next);
  });
  test('Vimeo adapter emits real metadata/time and delegates pause/seek to SDK',async()=>{
    document.body.innerHTML='<video id="video"></video><script id="video-quiz-data">{"provider":"vimeo","src":"https://player.vimeo.com/video/76979871"}</script>';
    const handlers={},play=jest.fn(),pause=jest.fn(),seek=jest.fn().mockResolvedValue(4),metadata=jest.fn();
    window.Vimeo={Player:jest.fn(()=>({on:(event,cb)=>handlers[event]=cb,ready:()=>Promise.resolve(),getDuration:()=>Promise.resolve(30),play,pause,setCurrentTime:seek}))};
    const video=document.getElementById('video');video.addEventListener('loadedmetadata',metadata);
    videoQuizProviderRuntime();document.querySelector('script[src="https://player.vimeo.com/api/player.js"]').onload();
    await new Promise(resolve=>setTimeout(resolve,0));
    expect(video.duration).toBe(30);expect(metadata).toHaveBeenCalledTimes(1);
    await video.play();handlers.play();expect(video.paused).toBe(false);
    handlers.timeupdate({seconds:5,duration:30});expect(video.currentTime).toBe(5);
    video.currentTime=4;expect(seek).toHaveBeenCalledWith(4);
    video.pause();expect(pause).toHaveBeenCalled();expect(video.paused).toBe(true);
    expect(video.hidden).toBe(true);expect(document.querySelector('iframe').getAttribute('src')).toContain('player.vimeo.com/video/76979871');
    window.dispatchEvent(new Event('pagehide'));document.body.innerHTML='';delete window.Vimeo;
  });
  test('connects to the existing Editor iframe without rewriting a Bunny signature',()=>{
    const src='https://iframe.mediadelivery.net/play/123/11111111-2222-3333-4444-555555555555?token=a%2Bb&expires=99&autoplay=true';
    document.body.innerHTML='<div id="preview"><video id="video"></video><iframe data-provider-frame></iframe></div>';
    const root=document.getElementById('preview'),frame=root.querySelector('iframe');frame.src=src;
    const navigate=jest.spyOn(frame,'src','set');
    const handlers={};window.playerjs={Player:jest.fn(()=>({on:(name,cb)=>handlers[name]=cb,getDuration:cb=>cb(30),pause:()=>{throw new Error('detached iframe contentWindow');}}))};
    const dispose=videoQuizProviderRuntime(root,{src,provider:'bunny'});
    expect(root.querySelector('iframe')).toBe(frame);expect(frame.getAttribute('src')).toBe(src);expect(frame.referrerPolicy).toBe('no-referrer');
    document.querySelector('script[src="https://cdn.embed.ly/player-0.1.0.min.js"]').onload();
    expect(navigate).toHaveBeenCalledWith(src);expect(handlers.ready).toBeDefined();handlers.ready();
    expect(root.querySelector('video').duration).toBe(30);expect(dispose).not.toThrow();
    expect(root.querySelector('iframe')).toBe(frame);expect(root.querySelector('[role="status"]')).toBeNull();
    document.body.innerHTML='';delete window.playerjs;navigate.mockRestore();
  });
});
