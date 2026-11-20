"""Mobile host sizing, exclusively for independent all-Astryx prototype courses."""


def is_astryx_course(course):
    if hasattr(course, 'model_dump'):
        course = course.model_dump()
    slides = course.get('slides') or []
    return bool(slides) and all(len(s.get('elements') or []) == 1 and
                               s['elements'][0].get('astryxPrototype') is True for s in slides)


def install_astryx_host(document, enabled):
    if not enabled:
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
      #mobile-nav-prev,#mobile-nav-next{top:auto!important;bottom:42px!important;transform:none!important}
      #mobile-nav-menu{top:auto!important;bottom:86px!important;left:calc(50% - 20px)!important}
    }</style>'''
    return document.replace('</head>', css + '</head>', 1)
