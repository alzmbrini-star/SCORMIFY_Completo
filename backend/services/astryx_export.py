"""Mobile host sizing, exclusively for independent all-Astryx prototype courses."""


def is_astryx_course(course):
    if hasattr(course, 'model_dump'):
        course = course.model_dump()
    slides = course.get('slides') or []
    return bool(slides) and all(len(s.get('elements') or []) == 1 and
                               s['elements'][0].get('astryxPrototype') is True for s in slides)


def is_astryx_agent_course(course):
    if hasattr(course, 'model_dump'):
        course = course.model_dump()
    return any(e.get('astryxDesign') is True for s in course.get('slides',[]) for e in s.get('elements',[]))


def install_astryx_host(document, enabled, agent=False):
    if not enabled and not agent:
        return document
    # Existing players fit a fixed landscape canvas. These responsive HTML
    # documents instead need the real mobile width; they own internal scrolling.
    css = '''<style id="astryx-mobile-host">
    @media(max-width:640px){
      #slide-container{width:100%!important;height:calc(100dvh - 150px)!important;
        transform:none!important;transform-origin:top left!important;margin:0!important;flex-shrink:1!important}
      #slide-wrapper{width:100%!important;height:calc(100dvh - 150px)!important;
        min-height:360px!important;display:block!important;padding:0!important;overflow:hidden!important}
      #slide-container>.html-element{left:0!important;top:0!important;width:100%!important;height:100%!important}
      #main-content{padding:0!important;min-width:0!important}
      #slide-container iframe{width:100%!important;height:100%!important}
      #course-title{font-size:13px!important;line-height:1.3!important}
      #slide-wrapper .swipe-zone{display:none!important}
      #mobile-nav-prev,#mobile-nav-next{top:auto!important;bottom:42px!important;transform:none!important;z-index:2001!important}
      #mobile-nav-menu{top:auto!important;bottom:86px!important;left:calc(50% - 20px)!important}
    }</style>'''
    if agent and not enabled:
        # Mixed courses keep native quizzes/scenarios on their original stage.
        # Only a currently visible Astryx lesson gets the real mobile viewport.
        css = css.replace('#slide-container', '#slide-container.astryx-mobile-stage').replace('#slide-wrapper', '#slide-wrapper.astryx-mobile-wrapper')
        css = css.replace('#main-content{', '#main-content:has(.astryx-mobile-stage){')
        css += '''<script id="astryx-agent-host">(function(){function start(){
        var stage=document.getElementById('slide-container');if(!stage)return;
        function sync(){var frames=stage.querySelectorAll('iframe'),on=false;
          for(var i=0;i<frames.length;i++){var raw=frames[i].getAttribute('srcdoc')||'';
            if(raw.indexOf('data-astryx-lesson=')>=0){on=true;break;}}
          stage.classList.toggle('astryx-mobile-stage',on);
          var wrap=document.getElementById('slide-wrapper');if(wrap)wrap.classList.toggle('astryx-mobile-wrapper',on);
        }new MutationObserver(sync).observe(stage,{childList:true,subtree:true,attributes:true,attributeFilter:['srcdoc']});sync();
        }if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();})();</script>'''
    return document.replace('</head>', css + '</head>', 1)
