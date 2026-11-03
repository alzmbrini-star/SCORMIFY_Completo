"""Render bounded, typed scene projections; never load authored SVG/HTML/URLs.

These are SVG scene frames, not browser screenshots of the slide controls.
The browser's cosmetic soft-volume finish is intentionally not a visibility proof.
"""
import copy,io,math
from xml.etree.ElementTree import Element,SubElement,tostring

WIDTH,HEIGHT=400,225


def sample_states(spec,limit=8):
    from services.rule_simulators import trace_rules
    from services.visual_teaching import visual_transitions
    initial={v['id']:v['initial'] for v in spec['variables']};states=[initial]
    # Follow each executable witness, not only the first and last step.
    for check in spec.get('checks',[])[:2]:
        for length in range(1,min(24,len(check['actions']))+1):
            state=trace_rules(spec,check['actions'][:length])['expected']
            if state not in states:states.append(state)
    for before,after in visual_transitions(spec)[:48]:
        if after not in states:states.append(after)
    if len(states)>limit:states=[states[round(i*(len(states)-1)/(limit-1))] for i in range(limit)]
    return [{'sampleIndex':i,'state':s} for i,s in enumerate(states)]


def frame_svg(visual,state,seconds=0,omit=None):
    from services.rule_visuals import visual_state
    rows={n['id']:n for n in visual_state(visual,state)}
    motions={m['node']:m for m in visual.get('motions',[])}
    root=Element('svg',xmlns='http://www.w3.org/2000/svg',width='800',height='450',viewBox='0 0 800 450')
    SubElement(root,'rect',x='0',y='0',width='800',height='450',fill=visual['background'])
    elements={};skipped=set()
    shapes={'group':'g','rect':'rect','circle':'circle','ellipse':'ellipse','line':'line','path':'path','polygon':'polygon','text':'text'}
    names={'strokeWidth':'stroke-width','fontSize':'font-size','fontWeight':'font-weight','anchor':'text-anchor'}
    for n in visual['nodes']:
        key=n['id'];row=rows[key]
        if key==omit or n.get('parent') in skipped or not row['visible']:
            skipped.add(key);continue
        a=copy.deepcopy(row['attrs']);m=motions.get(key);angle=0
        if m:
            angle=2*math.pi*m['cycles']*seconds/12+m['phase']*math.pi/180
            if m['kind']=='orbit':a.update(x=m['cx']+m['dx']*math.cos(angle),y=m['cy']+m['dy']*math.sin(angle))
        parent=elements.get(n.get('parent'),root)
        el=SubElement(parent,shapes[n['type']]);elements[key]=el;kind=n['type']
        el.set('data-object',key)
        for k,v in a.items():
            if k=='rotation' or kind=='group' and k in ('x','y'):continue
            if k=='text':el.text=str(v);continue
            name=names.get(k,k)
            if kind in ('circle','ellipse') and k in ('x','y'):name='cx' if k=='x' else 'cy'
            if kind=='line' and k in ('x','y'):name='x1' if k=='x' else 'y1'
            if k=='points':v=' '.join(','.join(map(str,p)) for p in v)
            el.set(name,str(v))
        transform=('translate('+str(a.get('x',0))+' '+str(a.get('y',0))+') ' if kind=='group' else '')+'rotate('+str(a.get('rotation',0))+')'
        if m and m['kind']=='translate':transform='translate('+str(m['dx']*math.sin(angle))+' '+str(m['dy']*math.sin(angle))+') '+transform
        if m and m['kind']=='rotate':transform=('translate('+str(a.get('x',0))+' '+str(a.get('y',0))+') ' if kind=='group' else '')+'rotate('+str(a.get('rotation',0)+angle*180/math.pi)+' '+str(m['cx'])+' '+str(m['cy'])+')'
        el.set('transform',transform)
    return tostring(root,encoding='unicode')


def raster(visual,state,seconds=0,omit=None):
    import resvg_py
    from PIL import Image
    # The input is built above from the whitelist: no image/use/foreignObject,
    # CSS, href, scripts, arbitrary XML, file paths or external resources.
    content=frame_svg(visual,state,seconds,omit)
    if len(content)>300000:raise ValueError('Cena excede orçamento de renderização')
    png=resvg_py.svg_to_bytes(svg_string=content,width=WIDTH,height=HEIGHT,skip_system_fonts=True)
    return Image.open(io.BytesIO(png)).convert('RGB')


def _different(a,b):
    from PIL import ImageChops
    diff=ImageChops.difference(a,b).convert('RGB')
    # Ignore antialiasing noise; require a visible contribution to the final
    # composited frame, not just declared opacity or a bounding rectangle.
    mask=diff.convert('L').point(lambda v:255 if v>8 else 0)
    return sum(mask.histogram()[1:])


def inspect_frames(visual,plan,samples):
    from PIL import Image,ImageDraw
    definitions={n['id']:n for n in visual['nodes']};issues=[];reports=[];frames=[]
    objects={o['id']:o for o in plan['objects']}
    for key in objects:
        if key not in definitions:issues.append({'nodes':[],'problem':'Objeto planejado ausente: '+key,'correction':'Inclua o objeto com este ID e suas características previstas.'})
    moments={m['sampleIndex']:m for m in plan['moments']}
    for sample in samples:
        i=sample['sampleIndex'];moment=moments[i];full=raster(visual,sample['state']);frames.append((i,full))
        contributions={}
        expected=set(moment['visibleObjects'])|{o['id'] for o in plan['objects'] if o['alwaysVisible']}
        for key in expected:
            if key not in definitions:continue
            pixels=_different(full,raster(visual,sample['state'],omit=key));contributions[key]=pixels
            if pixels<12:issues.append({'nodes':[key],'problem':f'Objeto essencial {key} não aparece de forma perceptível na amostra {i} ({pixels} pixels úteis).','correction':'Corrija visibilidade, tamanho, contraste, posição ou oclusão nesta etapa; preserve as regras.'})
        reports.append({'sampleIndex':i,'state':sample['state'],'visiblePixels':contributions})
    # Also inspect authored continuous motion phases, without advancing rules.
    if visual.get('motions'):
        for sec in (3,6):
            full=raster(visual,samples[0]['state'],seconds=sec);frames.append(('movimento '+str(sec)+'s',full));contributions={}
            for key,o in objects.items():
                if not o['alwaysVisible'] or key not in definitions:continue
                pixels=_different(full,raster(visual,samples[0]['state'],seconds=sec,omit=key));contributions[key]=pixels
                if pixels<12:issues.append({'nodes':[key],'problem':f'Objeto permanente {key} desaparece no movimento em {sec}s.','correction':'Ajuste trajetória, pivô, posição ou contraste sem alterar as regras.'})
            reports.append({'sampleIndex':0,'timeSeconds':sec,'state':samples[0]['state'],'visiblePixels':contributions})
    if not issues and len(frames)>1 and not any(_different(frames[0][1],im)>=20 for _,im in frames[1:]):
        issues.append({'nodes':[],'problem':'As etapas e movimentos renderizados são visualmente indistinguíveis.','correction':'Mostre a mudança do processo nos objetos, não só no texto ou em números.'})
    # Labeled contact sheet is sent to the configured reviewer, never exposed
    # as a scientific/learning certificate and never persisted as base64 logs.
    sheet=Image.new('RGB',(WIDTH*2,(len(frames)+1)//2*(HEIGHT+24)),'#edf4fa');draw=ImageDraw.Draw(sheet)
    for index,(label,im) in enumerate(frames):
        x=index%2*WIDTH;y=index//2*(HEIGHT+24);draw.text((x+6,y+5),'Amostra '+str(label),fill='#10243b');sheet.paste(im,(x,y+24))
    output=io.BytesIO();sheet.save(output,format='PNG')
    return {'samples':reports,'issues':issues[:12],'frameCount':len(frames),'renderer':'typed-svg-resvg-v1'},output.getvalue()
