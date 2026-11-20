"""Presentation-only repair of static SVG legends; no providers or rule rewrites."""
import json
import re
from services.component_authoring import stored_model

MARKER = 'scormify-readable-legend-v1'


def legend_rows(model):
    nodes = (model.get('visual') or {}).get('nodes') or []
    by_id = {n.get('id'): n for n in nodes}
    for group in nodes:
        if group.get('type') != 'group' or not re.match(r'^(legenda|legend)(?:\b|_)', str(group.get('id', '')), re.I):
            continue
        descendants = [group]
        for _ in range(len(nodes)):
            more = [n for n in nodes if n not in descendants and n.get('parent') in {x.get('id') for x in descendants}]
            if not more:
                break
            descendants += more
        ancestors, parent = [], group.get('parent')
        while parent:
            if parent not in by_id or by_id[parent] in ancestors:
                raise ValueError('Hierarquia da legenda inválida')
            ancestors.append(by_id[parent]); parent = by_id[parent].get('parent')
        if any(k in n and n[k] not in (None, [], {}) for n in descendants + ancestors for k in ('states', 'bindings', 'visibleWhen', 'action')):
            continue  # Never flatten a dynamic or interactive legend.
        protected = {n.get('id') for n in descendants + ancestors}
        if any(m.get('node') in protected for m in (model.get('visual') or {}).get('motions', [])):
            continue
        texts = [n for n in descendants[1:] if n.get('type') == 'text']
        if not 2 <= len(texts) <= 12 or any(n.get('type') != 'text' for n in descendants[1:]):
            continue
        rows = []
        for n in texts:
            attrs = n.get('attrs') or {}; text = attrs.get('text')
            if not isinstance(text, str) or not text.strip() or '{' in text or len(text) > 300:
                break
            color = attrs.get('fill', '#10243b')
            rows.append({'text': text, 'color': color if re.fullmatch(r'#[0-9a-fA-F]{6}', str(color)) else '#10243b'})
        else:
            return {'id': group['id'], 'rows': rows}
    raise ValueError('Não há uma legenda estática compatível. O cenário foi preservado.')


def repair_legend(source):
    model = stored_model(source)
    legend = legend_rows(model)
    if f'id="{MARKER}"' in source:
        return {'html': source, 'changed': False}
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', legend['id']) or not re.search(r'</body>', source, re.I):
        raise ValueError('Documento da legenda inválido')
    payload = json.dumps(legend, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    script = '''<script id="%s">(function(){
      'use strict';var data=%s;
      function mount(){
        var figure=document.getElementById('rule-visual');
        if(!figure||figure.querySelector('.sim-readable-legend'))return;
        var stage=figure.querySelector('.sim-visual-stage');if(!stage)return;
        var panel=document.createElement('section');panel.className='sim-readable-legend';
        panel.setAttribute('aria-label',data.rows[0].text);
        data.rows.forEach(function(row,index){
          var line=document.createElement(index?'div':'strong');
          if(index){var chip=document.createElement('span');chip.className='sim-legend-chip';chip.style.backgroundColor=row.color;chip.setAttribute('aria-hidden','true');line.appendChild(chip);}
          var text=document.createElement('span');text.textContent=row.text;line.appendChild(text);panel.appendChild(line);
        });
        var style=document.createElement('style');
        style.textContent='.sim-readable-legend{display:flex;flex-wrap:wrap;align-items:center;gap:4px 16px;flex-shrink:0;max-height:55%%;overflow:auto;background:#fff;color:#10243b;border:1px solid #9bb0c2;border-radius:9px;padding:7px 10px;margin:0 0 6px;font:16px/1.4 system-ui,sans-serif;min-width:0}.sim-readable-legend>strong{display:block;font-size:17px}.sim-readable-legend>div{display:flex;gap:6px;align-items:baseline;max-width:100%%}.sim-readable-legend span{overflow-wrap:break-word;min-width:0}.sim-legend-chip{display:inline-block;flex:0 0 14px;width:14px;height:14px;border:1px solid #52667a;border-radius:3px}.sim-rule-visual [data-visual-node="'+data.id+'"]{display:none!important}';
        document.head.appendChild(style);figure.insertBefore(panel,stage);
      }
      if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){setTimeout(mount,0);},{once:true});else setTimeout(mount,0);
    })();</script>''' % (MARKER, payload)
    # Model, original runtime, images, motions and authored HTML remain intact.
    result = re.sub(r'</body>', lambda match: script + match.group(), source, count=1, flags=re.I)
    assert stored_model(result) == model
    return {'html': result, 'changed': True}
