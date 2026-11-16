"""Topic-independent layout contract for newly generated Agent study resources.

Never migrates saved courses or converts either assessment format. Content stays
as data; the server owns CSS/interaction instead of trusting arbitrary model CSS.
"""
import copy
import hashlib
import json
import re
from bs4 import BeautifulSoup

VERSION = 'study-resources-v1'
TYPES = {'flashcard', 'reinforcement', 'visual_summary', 'narration'}
PROMPT = '''CONTRATO DE LAYOUT DOS RECURSOS (qualquer tema): para flashcard,
reinforcement, visual_summary e narration, inclua resourceLayout no slide:
{"kind":"cards|flow|note","title":"título didático","intro":"orientação curta",
"items":[{"front":"conceito/pergunta/etapa","back":"explicação, resposta ou peso completo"}]}.
Use cards para flashcards/reforço, flow para resumo de processo e note para
transcrição de narração. Preserve TODOS os conceitos, números, pesos e exemplos,
sem reticências/truncamento e sem inserir instruções de produção como conteúdo.
Não invente conteúdo para preencher cartões. Não imponha limite de itens: o
renderizador pagina os cartões sem diminuir a fonte. Cada frente/verso é separado,
operável por clique, Enter ou Espaço, nunca por hover obrigatório ou texto espelhado.
O servidor monta o HTML responsivo em 1920x820, com tipografia legível, contraste,
espaçamento e rolagem para detalhes longos. Não use seletores amplos #flashcards div,
cartões de tamanho fixo minúsculo ou um parágrafo solto como slide final.
Este contrato NÃO se aplica a Quiz tradicional, Avaliação interativa com imagens,
simuladores, jogos ou cenários: preserve seus formatos e motores próprios.'''


def _text(value):
    if not isinstance(value, str):
        raise ValueError('O recurso deve conter texto completo, não objetos ou instruções de código.')
    return value.strip()


def validate_layout(raw):
    if not isinstance(raw, dict) or raw.get('kind') not in {'cards', 'flow', 'note'}:
        raise ValueError('Recurso sem composição visual estruturada. Gere resourceLayout completo.')
    title = _text(raw.get('title', ''))
    items = raw.get('items')
    if not title or not isinstance(items, list) or not items:
        raise ValueError('Recurso sem título ou conteúdo didático.')
    clean = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Cartão ou etapa inválido.')
        front, back = _text(item.get('front', '')), _text(item.get('back', ''))
        if not front or not back:
            raise ValueError('Cada cartão/etapa precisa de frente e explicação completas.')
        # No truncation, deduplication or artificial item limits: long details scroll.
        if any(re.search(r'/\*\s*(?:Infographic structure and animations|Flashcards HTML content here)\s*\*/|\[IMG:|lorem ipsum|CSS styles here', text, re.I) for text in (front, back)):
            raise ValueError('Instrução de produção encontrada no conteúdo do recurso.')
        clean.append({'front': front, 'back': back})
    return {'kind': raw['kind'], 'title': title, 'intro': _text(raw.get('intro', '')), 'items': clean}


def _legacy_layout(slide):
    """Recover simple provider variations without executing JS or guessing facts."""
    docs = [e.get('htmlContent') or e.get('content') or '' for e in slide.get('elements', []) if isinstance(e, dict)]
    if any(not isinstance(doc, str) for doc in docs):
        return None
    soup = BeautifulSoup('\n'.join(docs), 'html.parser')
    title = str(slide.get('title') or '')
    root = soup.select_one('#flashcards, #flowchart')
    items = []
    if root:
        for card in root.find_all(['div', 'button', 'article'], recursive=False):
            front = card.select_one('.front') or card.find(['h1', 'h2', 'h3'])
            back = card.select_one('.back') or card.find('p')
            if front and back:
                items.append({'front': front.get_text(' ', strip=True), 'back': back.get_text(' ', strip=True)})
        if items and len(items) == len(root.find_all(['div', 'button', 'article'], recursive=False)):
            return {'kind': 'flow' if root.get('id') == 'flowchart' else 'cards', 'title': title, 'items': items}
    # Existing safe fallback decks keep their entire content in JSON arrays.
    for script in soup.find_all('script'):
        match = re.search(r'(?:const|let|var)\s+(?:cards|flashcards)\s*=\s*(\[[\s\S]*?\])\s*;', script.get_text())
        if match:
            try:
                values = json.loads(match[1])
                if values and all(isinstance(v, dict) and v.get('front') and v.get('back') for v in values):
                    return {'kind': 'cards', 'title': title, 'items': values}
            except (ValueError, TypeError):
                pass
    if slide.get('type') == 'narration':
        paragraphs = [p.get_text(' ', strip=True) for p in soup.find_all('p') if p.get_text(strip=True)]
        if paragraphs:
            return {'kind': 'note', 'title': title, 'items': [{'front': title, 'back': '\n\n'.join(paragraphs)}]}
    return None


def render_layout(raw):
    data = validate_layout(raw)
    serialized = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    template = '''<!doctype html><html lang="pt-BR" data-resource-layout="study-resources-v1"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
*{box-sizing:border-box}html,body{margin:0;min-height:100%;font-family:Arial,sans-serif;color:#152b47;background:#f3f7fc}body{font-size:clamp(20px,1.65vw,32px)}main{height:100dvh;min-height:460px;padding:4vh 4vw;display:flex;flex-direction:column;gap:3vh}.eyebrow{color:#087484;font-size:clamp(17px,1.25vw,24px);letter-spacing:.12em;font-weight:700}h1{font-size:clamp(28px,2.7vw,52px);line-height:1.2;margin:.4em 0}header p{font-size:clamp(20px,1.5vw,29px);margin:0;color:#45617e}.cards{display:grid;grid-template-columns:repeat(var(--columns,1),minmax(0,1fr));gap:1.3vw;flex:1;min-height:180px;overflow:auto;padding:6px 6px 18px}.resource-card{font:inherit;color:inherit;text-align:left;border:1px solid #ccd9e9;border-top:7px solid var(--accent);background:white;border-radius:22px;padding:clamp(20px,1.8vw,36px);cursor:pointer;box-shadow:0 8px 20px #193b5b16;display:flex;flex-direction:column;gap:2vh;min-width:0;overflow:auto;overflow-wrap:anywhere}.resource-card>.number{font-weight:bold;color:var(--accent)}.resource-card>.front,.resource-card>.back,.flip>.front,.flip>.back{line-height:1.4;margin:auto 0;white-space:pre-wrap}.resource-card>.front,.flip>.front{font-weight:700}.resource-card>.back,.flip>.back{display:none}.flip[aria-expanded=true]>.front{display:none}.flip[aria-expanded=true]>.back{display:block}.flip>.hint{font-size:clamp(17px,1.1vw,22px);color:#51677d}.flip{border:0;background:transparent;color:inherit;font:inherit;display:flex;flex-direction:column;gap:2vh;text-align:left;min-height:210px;flex:1;cursor:pointer}.flip:focus-visible,footer button:focus-visible{outline:4px solid #2563eb;outline-offset:3px}.resource-flow .resource-card,.resource-note .resource-card{cursor:default}.resource-flow .back,.resource-note .back{display:block}.resource-flow .front,.resource-note .front{margin:0}.resource-flow .back,.resource-note .back{margin:0}.resource-note .cards{grid-template-columns:1fr}.resource-note .back{max-width:80ch}footer{display:flex;gap:16px;flex-wrap:wrap;align-items:center;justify-content:space-between;font-size:clamp(18px,1.2vw,24px);color:#45617e}footer button{font:inherit;border:1px solid #bdcde0;border-radius:10px;padding:10px 18px;background:white;color:#152b47;cursor:pointer}footer button:disabled{opacity:.45;cursor:default}#mastery{display:flex;gap:12px;flex-wrap:wrap}.resource-card>div>button{font:inherit;font-size:clamp(17px,1.1vw,22px);border:1px solid #bdcde0;padding:8px 12px;border-radius:8px;background:#edf3fb;color:#152b47;cursor:pointer}.resource-card>div>button:focus-visible{outline:3px solid #2563eb}.resource-flow #mastery,.resource-note #mastery{display:none}@media(max-width:700px){main{padding:22px;gap:18px;height:auto;min-height:100dvh}.cards{flex:none;min-height:0;gap:20px}.resource-card{height:clamp(300px,45dvh,430px);min-height:300px}.resource-note .resource-card{height:auto;max-height:65dvh}footer{gap:12px}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
</style></head><body><main><header><div class="eyebrow">RECURSO DE APRENDIZAGEM</div><h1 id="title"></h1><p id="intro"></p></header><section class="cards" id="cards" aria-label="Conteúdo do recurso"></section><footer><button id="prev" type="button">← Anterior</button><span id="progress" role="status" aria-live="polite"></span><div id="mastery"><button id="review" type="button">Revisar marcados</button><button id="restart" type="button">Reiniciar revisão</button></div><button id="next" type="button">Próximo →</button></footer></main><script id="resource-layout-data" type="application/json">__DATA__</script><script>
(()=>{const data=JSON.parse(document.getElementById('resource-layout-data').textContent),$=id=>document.getElementById(id),colors=['#2563eb','#7c3aed','#087e91','#05835e','#c04b08'];let page=0,capacity=1,reviewOnly=false;const known=new Set(),missed=new Set();document.querySelector('main').className='resource-'+data.kind;$('title').textContent=data.title;$('intro').textContent=data.intro||(data.kind==='cards'?'Selecione um cartão para revelar a explicação.':'Explore os conceitos e suas relações.');
function indices(){return data.items.map((_,i)=>i).filter(i=>!reviewOnly||missed.has(i))}
function render(){const list=indices();capacity=data.kind==='note'?1:Math.max(1,Math.min(5,Math.floor((innerWidth*.92)/280)));const total=Math.max(1,Math.ceil(list.length/capacity));page=Math.min(page,total-1);$('cards').style.setProperty('--columns',Math.min(capacity,Math.max(1,list.length)));$('cards').replaceChildren();for(const i of list.slice(page*capacity,(page+1)*capacity)){const item=data.items[i],card=document.createElement('article');card.className='resource-card';card.style.setProperty('--accent',colors[i%colors.length]);const face=data.kind==='cards'?document.createElement('button'):card;if(data.kind==='cards'){face.type='button';face.className='flip';face.setAttribute('aria-expanded','false');face.onclick=()=>{face.setAttribute('aria-expanded',face.getAttribute('aria-expanded')!=='true');};card.append(face);}for(const [cls,text]of [['number',String(i+1).padStart(2,'0')+(data.kind==='flow'&&i<data.items.length-1?' →':'')],['front',item.front],['back',item.back]]){const s=document.createElement('span');s.className=cls;s.textContent=text;face.append(s)}if(data.kind==='cards'){const hint=document.createElement('span');hint.className='hint';hint.textContent='Clique, Enter ou Espaço para virar';face.append(hint)}$('cards').append(card);if(data.kind==='cards'){const controls=document.createElement('div');controls.style.cssText='display:flex;gap:8px;flex-wrap:wrap';for(const [label,ok] of [['Sei',true],['Preciso revisar',false]]){const button=document.createElement('button');button.type='button';button.textContent=label;button.onclick=()=>{if(ok){known.add(i);missed.delete(i)}else{known.delete(i);missed.add(i)}updateProgress(list,total)};controls.append(button)}card.append(controls)}}$('prev').disabled=page===0;$('next').disabled=page>=total-1;$('review').disabled=missed.size===0;updateProgress(list,total)}
function updateProgress(list,total){if(reviewOnly&&!missed.size){reviewOnly=false;page=0;$('review').textContent='Revisar marcados';render();return;}$('progress').textContent=`Página ${page+1} de ${total} · ${data.items.length} itens`+(data.kind==='cards'?` · ${known.size} dominados · ${missed.size} para revisar`:'');$('review').disabled=missed.size===0}
$('prev').onclick=()=>{page=Math.max(0,page-1);render()};$('next').onclick=()=>{page++;render()};$('review').onclick=()=>{reviewOnly=!reviewOnly;page=0;$('review').textContent=reviewOnly?'Ver todos':'Revisar marcados';render()};$('restart').onclick=()=>{reviewOnly=false;known.clear();missed.clear();page=0;$('review').textContent='Revisar marcados';render()};addEventListener('resize',()=>{page=0;render()});render()})();
</script></body></html>'''
    return template.replace('__DATA__', serialized)


def prepare_resource_slide(slide):
    """Compile only future generated resources. Both Quiz formats are opaque."""
    out = copy.deepcopy(slide)
    if out.get('type') not in TYPES or any(e.get('assessmentConfig') or e.get('quizConfig') or e.get('type') == 'quiz' for e in out.get('elements', []) if isinstance(e, dict)):
        return out
    data = validate_layout(out.get('resourceLayout') or _legacy_layout(out))
    if out['type'] == 'flashcard' and data['kind'] != 'cards':
        raise ValueError('Flashcards exigem cartões de frente e verso.')
    document = render_layout(data)
    out['resourceLayout'] = data
    out['layoutValidation'] = {'version': VERSION, 'status': 'passed', 'method': 'controlled-template',
                               'items': len(data['items']), 'sha256': hashlib.sha256(document.encode()).hexdigest()}
    out['elements'] = [{'type': 'html', 'interactiveType': out['type'], 'htmlContent': document,
                        'x': 0, 'y': 0, 'width': 1920, 'height': 820, 'htmlDisplayMode': 'page',
                        'resourceLayoutVersion': VERSION}]
    return out


def layout_ready(slide):
    if slide.get('type') not in TYPES:
        return True
    try:
        expected = prepare_resource_slide(slide)
        return slide.get('layoutValidation') == expected['layoutValidation'] and slide.get('elements') == expected['elements']
    except (ValueError, TypeError, AttributeError, KeyError):
        return False
