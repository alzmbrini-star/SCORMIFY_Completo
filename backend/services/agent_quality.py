"""Deterministic presentation/copy corrections, never regenerates activities."""
import copy
import base64
import hashlib
import json
import re
from html import unescape, escape
from urllib.parse import urlsplit

VERSION = 'agent-quality-v1'


def alternative_text(text):
    return re.sub(r'^\s*[A-Ha-h][).:]\s+', '', str(text or ''), count=1)


def explanation_text(text):
    return re.sub(r'\b[Aa] resposta correta é\s+[A-Ha-h]\s+porque\s+', 'Justificativa: ', str(text or ''))


def _safe_image(src):
    if not isinstance(src, str) or len(src) > 5000000:
        return False
    try:
        return (src.startswith('/api/') or src.startswith('data:image/') or
                urlsplit(src).scheme == 'https' and bool(urlsplit(src).netloc))
    except ValueError:
        return False


def _media(slides):
    result = []
    for index, slide in enumerate(slides):
        for el in slide.get('elements', []):
            if el.get('type') == 'image' and _safe_image(el.get('src')):
                result.append((index, el['src']))
            raw = el.get('htmlContent') or ''
            # Only reuse already-associated course assets, never invented remote URLs.
            for src in re.findall(r'<img\b[^>]*\ssrc=["\']([^"\']+)["\']', raw, re.I):
                src = unescape(src)
                if _safe_image(src) and ('/api/' in src or src.startswith('data:image/')):
                    result.append((index, src))
    return result


def repair_html(source, fallback=''):
    if not isinstance(source, str) or not source:
        return source
    if source.startswith('__B64__:'):
        try:
            decoded = base64.b64decode(source[8:], validate=True).decode('utf-8')
        except (ValueError, UnicodeError):
            return source
        fixed = repair_html(decoded, fallback)
        return source if fixed == decoded else '__B64__:' + base64.b64encode(fixed.encode()).decode()
    # Restrict copy corrections to text nodes: no CSS, scripts, notes or data models.
    chunks = re.split(r'(<(?:script|style|pre|code)\b[^>]*>[\s\S]*?</(?:script|style|pre|code)\s*>)', source, flags=re.I)
    for index in range(0, len(chunks), 2):
        chunks[index] = re.sub(r'(?<=>)([^<>]+)(?=<)', lambda m: re.sub(
            r'\bSonegar metas realistas\b', 'Definir metas realistas', m[1]), chunks[index])
        chunks[index] = re.sub(r'<h([1-6])\b[^>]*>\s*(?:Subtítulo da Seção|Section subtitle|Título da seção|Lorem ipsum)\s*</h\1>', '', chunks[index], flags=re.I)
    result = ''.join(chunks)
    # Retire the v1 runtime fallback: a relative asset URL inside srcdoc can
    # resolve against the frontend instead of the configured backend. Valid
    # authored sources must never be replaced after a transient load error.
    result = re.sub(r"<script>\(function\(\)\{'use strict';var fallback=[\s\S]*?</script>", '', result)
    if _safe_image(fallback):
        def replace_unresolved(match):
            tag, src = match[0], unescape(match[2])
            # Bare filenames cannot resolve in a saved srcdoc activity. Actual
            # document assets (/api/, assets/, data:, remote URLs) remain opaque.
            if re.fullmatch(r'[A-Za-z0-9_-]+\.(?:png|jpe?g|webp|gif)', src, re.I):
                tag = tag.replace(match[1] + match[2] + match[1],
                                  match[1] + escape(fallback, quote=True) + match[1], 1)
                tag = re.sub(r'/?>$', lambda m: ' data-quality-original-src="'+escape(src, quote=True)+'"'+m[0], tag)
            return tag
        result = re.sub(r'<img\b[^>]*\ssrc=(["\'])([^"\']+)\1[^>]*>', replace_unresolved, result, flags=re.I)
    if 'data-resource-layout="study-resources-v1"' in result:
        result = result.replace('Math.min(5,Math.floor((innerWidth*.92)/280))', 'Math.min(3,Math.floor((innerWidth*.92)/410))')
    if f'id="{VERSION}"' in result:
        return result
    is_cards = 'data-resource-layout="study-resources-v1"' in result
    is_sim = 'id="scormify-simulator-plan"' in result
    is_timeline = bool(re.search(r'class=["\'][^"\']*\bmilestone\b', result))
    has_images = bool(re.search(r'<img\b', result, re.I)) and _safe_image(fallback)
    # A narrow opt-in stylesheet and trusted image recovery. No authored JS is replaced.
    styles = ''
    if is_cards:
        styles += '.resource-card{padding:18px!important;gap:12px!important}.resource-card .flip{min-height:0!important;overflow:auto;gap:12px!important;flex:1}.resource-card .front,.resource-card .back{font-size:clamp(18px,1.3vw,24px)!important;line-height:1.45!important;margin:0!important;overflow-wrap:break-word!important}.resource-card>div:last-child{flex-shrink:0}.resource-card .hint{font-size:14px!important}.resource-card .number{font-size:18px!important}'
    if is_sim:
        styles += '.sim-object-legend,.sim-object-legend h2,.sim-object-legend p{color:#10243b!important}.sim-object-legend h2{background:#f8fbff!important;font-size:18px!important}.sim-object-legend p{font-size:16px!important}.sim-object-legend .sim-object-list button{font-size:16px!important}'
    styles += '.step>strong,.step>h3,.infographic-step>strong,.infographic-step>h3{display:block!important;margin-bottom:.55em!important}.step,.infographic-step{line-height:1.45;overflow-wrap:break-word}'
    if re.search(r'id=["\']indicators["\']', result):
        styles += '#indicators .indicator p{text-align:left!important;line-height:1.5!important}#indicators .indicator img{aspect-ratio:16/9;object-fit:contain;background:#eef3f8}'
    if is_timeline:
        styles += '.timeline{height:auto!important;min-height:540px!important;overflow:visible!important}.milestone{display:block!important;text-align:left!important;transform:none!important;padding:14px 18px!important;line-height:1.45!important}.milestone h4{display:block!important;margin:0!important;font-size:18px!important}.milestone .description{width:100%!important;font-size:16px!important}.milestone.active .description{max-height:none!important;overflow:visible!important}.milestone.active .description p{margin:10px 0 0!important}.milestone:focus-visible{outline:3px solid #315ad1;outline-offset:3px}'
    payload = json.dumps(fallback if has_images else '', ensure_ascii=True).replace('<', '\\u003c')
    addition = '<style id="'+VERSION+'">'+styles+'</style>'
    if is_timeline:
        addition += '''<script>(function(){function mount(){document.querySelectorAll('.milestone').forEach(function(n){n.setAttribute('role','button');n.tabIndex=0;function sync(){n.setAttribute('aria-expanded',String(n.classList.contains('active')));}n.addEventListener('click',function(){document.querySelectorAll('.milestone').forEach(function(x){x.setAttribute('aria-expanded',String(x.classList.contains('active')));});});n.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();n.click();}});sync();});}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();})();</script>'''
    if is_sim:
        addition += '''<script>(function(){'use strict';function mount(){
          var figure=document.getElementById('rule-visual');if(!figure||figure.querySelector('.quality-pieces-button'))return;
          var nodes=Array.from(figure.querySelectorAll('[data-visual-node]')).filter(function(n){
            if(n.tagName.toLowerCase()==='text')return false;
            var b=n.getBBox();return b.width>0&&b.height>0&&b.width<=45&&b.height<=45;
          });nodes=nodes.filter(function(n){return !nodes.some(function(parent){return parent!==n&&parent.contains(n);});}).slice(0,8);if(!nodes.length)return;
          var button=document.createElement('button');button.type='button';button.className='quality-pieces-button';
          button.textContent='Ver peças ampliadas';button.style.cssText='font:600 16px system-ui;min-height:40px;flex-shrink:0';
          var dialog=document.createElement('dialog');dialog.style.cssText='background:#f8fbff;color:#10243b;border:1px solid #52667a;border-radius:12px;padding:18px;width:min(760px,92vw);max-height:85vh;overflow:auto';
          var title=document.createElement('h2');title.textContent='Peças ampliadas — estado atual';title.style.cssText='color:#10243b!important;font:700 20px system-ui';
          var close=document.createElement('button');close.type='button';close.textContent='Fechar peças ampliadas';
          close.style.cssText='background:#173750;color:white;font:600 16px system-ui;padding:10px;border:0;border-radius:8px';
          close.onclick=function(){dialog.close();button.focus();};
          var grid=document.createElement('div');grid.style.cssText='display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:16px;margin:16px 0';
          dialog.append(title,grid,close);document.body.appendChild(dialog);
          function render(){grid.replaceChildren();nodes.forEach(function(n){
            var card=document.createElement('figure');card.style.cssText='margin:0;background:#e6edf5;border:1px solid #8ca5bb;padding:12px;border-radius:9px;color:#10243b';
            var svg=document.createElementNS('http://www.w3.org/2000/svg','svg'),b=n.getBBox(),copy=n.cloneNode(true);
            copy.removeAttribute('transform');copy.querySelectorAll('[id]').forEach(function(x){x.removeAttribute('id');});
            copy.removeAttribute('id');copy.removeAttribute('role');copy.removeAttribute('tabindex');
            svg.setAttribute('viewBox',[b.x-4,b.y-4,b.width+8,b.height+8].join(' '));svg.style.cssText='width:100%;height:120px;display:block';
            svg.appendChild(copy);var label=document.createElement('figcaption');label.textContent=n.querySelector('title')?.textContent||n.dataset.visualNode;
            label.style.cssText='color:#10243b;font:600 16px/1.4 system-ui;margin-top:8px;overflow-wrap:break-word';
            card.append(svg,label);grid.appendChild(card);
          });}
          button.onclick=function(){render();dialog.showModal();close.focus();};
          document.addEventListener('scormify:rules-state',function(){if(dialog.open)setTimeout(render,450);});
          figure.insertBefore(button,figure.firstChild);
        }if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){setTimeout(mount,0);},{once:true});else setTimeout(mount,0);})();</script>'''
    if has_images:
        addition += '''<script>(function(){function mount(){document.querySelectorAll('img').forEach(function(img){img.addEventListener('load',function(){window.dispatchEvent(new Event('resize'));});});}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();})();</script>'''
    if not (is_cards or is_sim or is_timeline or has_images or re.search(r'class=["\'][^"\']*\b(?:step|infographic-step)\b', result)):
        return result
    return re.sub(r'</body>', lambda m: addition+m[0], result, count=1, flags=re.I) if re.search(r'</body>', result, re.I) else result+addition


def quality_plan(project):
    slides = project.get('course', {}).get('slides', [])
    media = _media(slides)
    patches, report = {}, []
    for i, slide in enumerate(slides):
        fallback = min(media, key=lambda pair: abs(pair[0]-i))[1] if media else ''
        fields = []
        for j, element in enumerate(slide.get('elements', [])):
            for key in ('htmlContent', 'content'):
                if element.get('type') != 'html' or not isinstance(element.get(key), str):
                    continue
                old = element[key]; new = repair_html(old, fallback)
                if new != old:
                    patches[f'course.slides.{i}.elements.{j}.{key}'] = new
                    fields.append(j)
        if fields:
            report.append({'slide': i+1, 'title': slide.get('title', ''), 'elements': sorted(set(fields))})
    return patches, report


def fingerprint(project):
    return hashlib.sha256(json.dumps(project.get('course'), sort_keys=True, default=str).encode()).hexdigest()


def prepare_new_course(slides, questions):
    """Only invoked by NEW Agent generation; never a load-time migration."""
    wrapper = {'course': {'slides': copy.deepcopy(slides)}}
    patches, _ = quality_plan(wrapper)
    for path, value in patches.items():
        parts = path.split('.')
        wrapper['course']['slides'][int(parts[2])]['elements'][int(parts[4])][parts[5]] = value
    clean_questions = copy.deepcopy(questions)
    for q in clean_questions:
        for alt in q.get('alternatives', []):
            alt['text'] = alternative_text(alt.get('text'))
        q['explanation'] = explanation_text(q.get('explanation'))
    return wrapper['course']['slides'], clean_questions
