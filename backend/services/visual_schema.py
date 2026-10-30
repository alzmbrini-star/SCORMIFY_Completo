"""Constrained visual vocabulary for supported OpenAI models; renderer unchanged."""
def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


def array(items,low=0,high=100):return {'type':'array','items':items,'minItems':low,'maxItems':high}
def string(limit=None):return {'type':'string',**({'minLength':1,'maxLength':limit} if limit else {})}
def nullable(schema):return {'anyOf':[schema,{'type':'null'}]}


def plan_schema(ids):
    mechanism=obj({'var':{'type':'string','enum':ids},'object':string(100),'change':string(180),'meaning':string(240)})
    return obj({'setting':string(600),'focus':string(220),'composition':string(800),'artDirection':string(1000),'mechanisms':array(mechanism,2,4)})


def review_schema(ids):
    issue=obj({'nodes':array({'type':'string','enum':ids},0,8),'problem':string(350),'correction':string(500)})
    return obj({'approved':{'type':'boolean'},'summary':string(600),'issues':array(issue,0,6)})


def scene_schema(ids,actions,demo=False):
    from services.rule_visuals import ALLOWED,NUMBERS
    color={'type':'string','pattern':'^(#[0-9a-fA-F]{6}|none)$'}
    point=array({'type':'number'},2,2)
    leaf={'anyOf':[{'type':'integer'},obj({'var':{'type':'string','enum':ids}})]}
    predicate={'anyOf':[{'type':'boolean'},
        obj({'op':{'type':'string','enum':['eq','ne','lt','le','gt','ge']},'args':array(leaf,2,2)}),
        obj({'op':{'type':'string','enum':['all','any']},'args':array({'$ref':'#/$defs/predicate'},2,10)}),
        obj({'op':{'type':'string','enum':['not']},'args':array({'$ref':'#/$defs/predicate'},1,1)})]}
    definitions={'predicate':predicate};variants=[]
    required={'rect':{'width','height'},'circle':{'r'},'ellipse':{'rx','ry'},'line':{'x2','y2'},'path':{'d'},'polygon':{'points'},'text':{'text'}}
    def attrs(kind,states=False):
        fields={}
        for key in sorted(ALLOWED[kind]):
            if key in NUMBERS:
                lo,hi=NUMBERS[key];value={'type':'number','minimum':lo,'maximum':hi}
            elif key in {'fill','stroke'}:value=color
            elif key=='points':value=array(point,3,40)
            elif key=='anchor':value={'type':'string','enum':['start','middle','end']}
            else:value=string({'d':1600,'text':100}.get(key))
            fields[key]=value if not states and key in required.get(kind,set()) else nullable(value)
        return obj(fields)
    for kind in sorted(ALLOWED):
        binding=obj({'property':{'type':'string','enum':sorted((ALLOWED[kind]&set(NUMBERS))-{'fontSize','fontWeight'})},
            'var':{'type':'string','enum':ids},'input':array({'type':'number'},2,2),'output':array({'type':'number'},2,2)})
        state=obj({'when':{'$ref':'#/$defs/predicate'},'set':attrs(kind,True)})
        node=obj({'id':{'type':'string','pattern':'^[a-z][a-z0-9_]{0,31}$'},'type':{'type':'string','enum':[kind]},
            'label':string(),'parent':nullable(string()),'attrs':attrs(kind),'bindings':array(binding,0,8),
            'states':array(state,0,8),'visibleWhen':nullable({'$ref':'#/$defs/predicate'}),
            'action':nullable({'type':'string','enum':actions})})
        definitions['node_'+kind]=node;variants.append({'$ref':'#/$defs/node_'+kind})
    link=obj({'node':string(),'var':{'type':'string','enum':ids},'whatChanges':string(180),'whyItMatters':string(240)})
    teaching=obj({'version':{'type':'integer','enum':[1]},'focus':string(220),'readScene':string(700),'links':array(link,2,4)})
    result=obj({'version':{'type':'integer','enum':[1]},'title':string(100),'description':string(600),
        'background':{'type':'string','pattern':'^#[0-9a-fA-F]{6}$'},'nodes':array({'anyOf':variants},6,100),'teaching':{'type':'null'} if demo else teaching})
    result['$defs']=definitions
    return result


def format_for_stage(provider,model,suffix,data,payload):
    name=model.split('/')[-1]
    if provider!='openai' or not name.startswith(('gpt-4o','gpt-4.1','gpt-5')):return None
    ids=[v['id'] for v in data['variables']]
    if 'composition' in suffix:schema=plan_schema(ids);stage='composition'
    elif 'review' in suffix:schema=review_schema([n['id'] for n in payload['scene']['nodes']]);stage='review'
    else:schema=scene_schema(ids,[a['id'] for a in data['actions']],data.get('didacticMode')=='process-demo-v1');stage='scene'
    return {'type':'json_schema','json_schema':{'name':'simulator_visual_'+stage,'strict':True,'schema':schema}}


def omit_null_fields(value):
    if isinstance(value,dict):return {key:omit_null_fields(item) for key,item in value.items() if item is not None}
    if isinstance(value,list):return [omit_null_fields(item) for item in value]
    return value
