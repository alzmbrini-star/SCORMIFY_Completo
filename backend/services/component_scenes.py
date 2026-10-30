"""Opt-in component project contract; compiles to the unchanged SVG runtime."""
import copy
import json
import math
import re
from services.component_catalog import COMPONENTS,SUPPORTED_CATALOGS,V1_COMPONENTS,draw_component

VERSION=1


def project_schema():
    """Portable draft-07 authoring schema; semantic checks still run at compile."""
    def obj(properties,required=None):
        return {'type':'object','properties':properties,'required':list(properties) if required is None else required,'additionalProperties':False}
    def text(limit):return {'type':'string','minLength':1,'maxLength':limit}
    ident={'type':'string','pattern':'^[a-z][a-z0-9_]{0,15}$'}
    span={'type':'array','items':{'type':'number','minimum':-100,'maximum':100},'minItems':2,'maxItems':2}
    source={'oneOf':[obj({'var':{'type':'string','pattern':'^[a-z][a-z0-9_]{0,31}$'},'range':span}),
                     obj({'value':{'type':'number','minimum':-100,'maximum':100},'range':span})]}
    variants=[]
    for kind,definition in COMPONENTS.items():
        properties={'id':ident,'component':{'const':kind},'version':{'type':'integer','const':definition['version']},
            'label':text(80),'position':obj({'x':{'type':'number','minimum':20,'maximum':780-definition['size'][0]},
                                            'y':{'type':'number','minimum':20,'maximum':430-definition['size'][1]}}),
            'inputs':obj({port:source for port in definition['inputs']}),
            'actions':obj({port:{'type':'string','pattern':'^[a-z][a-z0-9_]{0,31}$'} for port in definition['actions']},[])}
        required=list(properties)
        if definition.get('variants'):properties['variant']={'enum':definition['variants']}
        variants.append(obj(properties,required))
    link=obj({'instance':ident,'input':text(32),'whatChanges':text(180),'whyItMatters':text(240)})
    result=obj({'version':{'type':'integer','const':VERSION},'catalogVersion':{'type':'integer','enum':list(SUPPORTED_CATALOGS)},
        'renderer':{'const':'svg-v1'},'title':text(100),'description':text(600),'style':{'enum':['blueprint','studio']},
        'instances':{'type':'array','items':{'oneOf':variants},'minItems':2,'maxItems':6},
        'teaching':obj({'focus':text(220),'readScene':text(700),'links':{'type':'array','items':link,'minItems':2,'maxItems':4}})})
    result['$schema']='http://json-schema.org/draft-07/schema#'
    result['allOf']=[{'if':{'properties':{'catalogVersion':{'const':1}}},
                     'then':{'properties':{'instances':{'items':{'properties':{'component':{'enum':sorted(V1_COMPONENTS)}}}}}}}]
    return result


def _object(value,allowed,required):
    if not isinstance(value,dict) or set(value)-set(allowed) or set(required)-set(value):
        raise ValueError('Campos inválidos no projeto de componentes')


def _text(value,limit):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:
        raise ValueError('Texto de componente obrigatório até '+str(limit)+' caracteres')
    return value.strip()


def _id(value):
    if not isinstance(value,str) or not re.fullmatch('[a-z][a-z0-9_]{0,15}',value):
        raise ValueError('ID de instância: letra inicial e até 16 caracteres alfanuméricos ou underscore')
    return value


def _number(value,low,high):
    if type(value) not in (float,int) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError('Número de componente fora dos limites')
    return value


def compile_project(raw,spec):
    """Validate and return (canonical project, safe visual), without logical writes.

    A new project is explicit. No heuristic by subject, network, user SVG/JS,
    unregistered component, generated equation or arbitrary effect is accepted.
    """
    from services.rule_visuals import validate_visual
    if not isinstance(raw,dict) or len(json.dumps(raw,ensure_ascii=True,allow_nan=False))>24000:
        raise ValueError('Projeto de componentes inválido ou maior que 24 KB')
    _object(raw,{'version','catalogVersion','renderer','title','description','style','instances','teaching'},
            {'version','catalogVersion','renderer','title','description','style','instances','teaching'})
    if type(raw['version']) is not int or raw['version']!=VERSION or type(raw['catalogVersion']) is not int or raw['catalogVersion'] not in SUPPORTED_CATALOGS or raw['renderer']!='svg-v1':
        raise ValueError('Versão de projeto, catálogo ou renderizador não suportada')
    if not isinstance(raw['style'],str) or raw['style'] not in {'blueprint','studio'}:raise ValueError('Estilo de componentes não registrado')
    variables={v['id']:v for v in spec['variables']};actions={a['id'] for a in spec['actions']}
    rows=raw['instances']
    if not isinstance(rows,list) or not 2<=len(rows)<=6:raise ValueError('Use de 2 a 6 instâncias de componentes')
    instances=[];seen=set();nodes=[];targets={};changes={}
    for row in rows:
        _object(row,{'id','component','version','label','position','inputs','actions','variant'},
                {'id','component','version','label','position','inputs','actions'})
        ident=_id(row['id']);kind=row['component']
        if ident in seen:raise ValueError('ID de instância duplicado')
        if not isinstance(kind,str) or kind not in COMPONENTS:raise ValueError('Componente não registrado; extensão explícita necessária')
        definition=COMPONENTS[kind]
        if definition.get('introducedIn',1)>raw['catalogVersion']:raise ValueError('Componente exige catálogo de versão mais recente')
        if 'variant' in row and (not isinstance(row['variant'],str) or row['variant'] not in definition.get('variants',[])):
            raise ValueError('Variante de componente não registrada')
        if type(row['version']) is not int or row['version']!=definition['version']:raise ValueError('Versão do componente não suportada')
        seen.add(ident);_object(row['position'],{'x','y'},{'x','y'})
        x=_number(row['position']['x'],20,780-definition['size'][0]);y=_number(row['position']['y'],20,430-definition['size'][1])
        _object(row['inputs'],definition['inputs'],definition['inputs'])
        inputs={}
        for port,source in row['inputs'].items():
            if not isinstance(source,dict) or ('var' in source)==('value' in source):raise ValueError('Entrada exige variável OU constante')
            _object(source,{'var','value','range'},{'range','var' if 'var' in source else 'value'})
            span=source['range']
            if not isinstance(span,list) or len(span)!=2:raise ValueError('Entrada exige dois limites')
            lo=_number(span[0],-100,100);hi=_number(span[1],-100,100)
            if lo>=hi:raise ValueError('Intervalo da entrada precisa crescer')
            if 'var' in source:
                key=source['var']
                if not isinstance(key,str) or key not in variables:raise ValueError('Variável de componente inexistente')
                variable=variables[key]
                if lo<variable['min'] or hi>variable['max']:raise ValueError('Intervalo excede a variável existente')
                inputs[port]={'var':key,'range':[lo,hi]}
            else:inputs[port]={'value':_number(source['value'],lo,hi),'range':[lo,hi]}
        _object(row['actions'],definition['actions'],set())
        if any(not isinstance(a,str) or a not in actions for a in row['actions'].values()):raise ValueError('Ação de componente inexistente')
        for slot,action_id in row['actions'].items():
            ports=definition.get('actionInputs',{}).get(slot,[])
            if ports:
                effects=next(a for a in spec['actions'] if a['id']==action_id)['effects']
                if not any(inputs[port].get('var') in effects for port in ports):
                    raise ValueError('Ação da peça não altera a entrada esperada: '+ident+'/'+slot)
        instance={'id':ident,'component':kind,'version':row['version'],'label':_text(row['label'],80),
                  'position':{'x':x,'y':y},'inputs':inputs,'actions':copy.deepcopy(row['actions'])}
        if 'variant' in row:instance['variant']=row['variant']
        instances.append(instance);new,ports=draw_component(instance,raw['style']);nodes.extend(new)
        targets[ident]=ports;changes[ident]=inputs
    teaching=raw['teaching'];_object(teaching,{'focus','readScene','links'},{'focus','readScene','links'})
    links=teaching['links']
    if not isinstance(links,list) or not 2<=len(links)<=4:raise ValueError('Defina 2 a 4 relações didáticas')
    normalized=[];compiled=[];seen_links=set()
    for link in links:
        _object(link,{'instance','input','whatChanges','whyItMatters'},{'instance','input','whatChanges','whyItMatters'})
        ident=link['instance'];port=link['input']
        if not isinstance(ident,str) or not isinstance(port,str) or ident not in targets or port not in targets[ident] or 'var' not in changes[ident][port]:
            raise ValueError('Relação didática exige entrada de variável de uma instância existente')
        if (ident,port) in seen_links:raise ValueError('Relação didática duplicada')
        seen_links.add((ident,port))
        item={'instance':ident,'input':port,'whatChanges':_text(link['whatChanges'],180),'whyItMatters':_text(link['whyItMatters'],240)}
        normalized.append(item);compiled.append({'node':targets[ident][port],'var':changes[ident][port]['var'],
                                               'whatChanges':item['whatChanges'],'whyItMatters':item['whyItMatters']})
    plan={key:raw[key] for key in ('version','catalogVersion','renderer','style')}
    plan.update(title=_text(raw['title'],100),description=_text(raw['description'],600),instances=instances,
                teaching={'focus':_text(teaching['focus'],220),'readScene':_text(teaching['readScene'],700),'links':normalized})
    visual={'version':1,'title':plan['title'],'description':plan['description'],
            'background':'#102a43' if raw['style']=='blueprint' else '#eaf1f6','nodes':nodes,
            'teaching':{'version':1,**plan['teaching'],'links':compiled}}
    # The same limits, accessible runtime, projections and perceptibility tests
    # as all other scenes, never a bypass for catalog-authored graphics.
    return plan,validate_visual(visual,spec)
