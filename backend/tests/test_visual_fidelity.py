"""Fidelity review routing, not a gear template or automated pixel recognition."""
import asyncio,copy,json,math,unittest
from unittest.mock import patch
from services.rule_visuals import generate_visual,validate_visual
from services.rule_simulators import validate_rules
from test_process_demo import process_demo


def scene(teeth):
    nodes=[]
    for i,(x,r,color) in enumerate(zip([120,280,400,490],[90,70,50,40],['#e34b54','#398bd5','#38a87e','#e8b547'])):
        name='part_'+str(i)
        nodes.append({'id':name,'type':'group','label':'Peça '+str(i+1),'attrs':{'x':x,'y':225},
            'bindings':[{'property':'rotation','var':'etapa','input':[0,2],'output':[0,(-1 if i%2 else 1)*60]}]})
        attrs={'fill':color,'stroke':'#16304a','strokeWidth':2}
        if teeth:
            points=[]
            for k in range(40):
                angle=2*math.pi*k/40
                radius=r if k%4 in (1,2) else r*.83
                points.append([round(radius*math.cos(angle),2),round(radius*math.sin(angle),2)])
            attrs['points']=points
        else:attrs.update(x=0,y=0,r=r)
        nodes.append({'id':name+'_body','parent':name,'type':'polygon' if teeth else 'circle','label':'Corpo da peça','attrs':attrs})
        nodes.append({'id':name+'_hub','parent':name,'type':'circle','label':'Eixo','attrs':{'x':0,'y':0,'r':r*.16,'fill':'#16304a'}})
        if teeth:nodes.append({'id':name+'_mark','parent':name,'type':'circle','label':'Marca de rotação','attrs':{'x':r*.45,'y':0,'r':5,'fill':'#ffffff'}})
    return {'version':1,'title':'Transmissão de movimento','description':'Peças de tamanhos diferentes transmitem movimento. Representação ilustrativa.',
        'background':'#edf4fa','nodes':nodes}


def approval():return {'approved':True,'summary':'Identidade e relação visual representadas.','issues':[]}
def rejection():return {'approved':False,'summary':'Silhueta não representa a peça pedida.','issues':[{'nodes':['part_0_body'],
    'problem':'Círculos lisos não têm dentes reconhecíveis.','correction':'Desenhe contornos dentados em contato e marcas solidárias à rotação.'}]}


class VisualFidelity(unittest.TestCase):
    def run_generation(self,responses,prompt='Quatro engrenagens de tamanhos e cores diferentes'):
        calls=[];data=validate_rules(process_demo());before=copy.deepcopy(data)
        class Chat:
            def __init__(self,**kwargs):self.system=kwargs['system_message']
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):
                calls.append({'system':self.system,'payload':json.loads(message.text)})
                result=responses[len(calls)-1]
                return result if isinstance(result,str) else json.dumps(result)
        with patch('emergentintegrations.llm.chat.LlmChat',Chat):result=asyncio.run(generate_visual(data,prompt,'Curso','qa','openai','fake','model'))
        self.assertEqual(data,before)
        return result,calls

    def test_geometry_not_only_labels_is_reviewed_and_only_art_is_repaired(self):
        (visual,notice),calls=self.run_generation([scene(False),rejection(),scene(True),approval()])
        self.assertFalse(notice);self.assertTrue(any(n['type']=='polygon' for n in visual['nodes']))
        self.assertEqual(len(calls),4)
        self.assertIn('FIDELIDADE VISUAL',calls[1]['system'])
        self.assertEqual(calls[1]['payload']['scene']['nodes'][1]['type'],'circle')
        self.assertTrue(calls[1]['payload']['executedSamples'])
        self.assertNotEqual(calls[1]['payload']['executedSamples'][0]['state'],calls[1]['payload']['executedSamples'][-1]['state'])
        self.assertIn('dentes',calls[2]['payload']['repairError'])
        self.assertEqual(calls[0]['payload']['model'],calls[2]['payload']['model'])

    def test_circles_can_be_correct_when_the_requested_objects_are_particles(self):
        (visual,notice),calls=self.run_generation([scene(False),approval()],'Partículas circulares com eixos ilustrativos')
        self.assertIsNotNone(visual);self.assertFalse(notice);self.assertEqual(len(calls),2)

    def test_cut_off_repetitive_path_has_compact_repair_guidance(self):
        broken='{"version":1,"nodes":[{"attrs":{"d":"M 0 0 '+'M 10 -60 l 10 10 '*1000
        (visual,notice),calls=self.run_generation([broken,scene(True),approval()])
        self.assertIsNotNone(visual);self.assertFalse(notice)
        self.assertIn('Unterminated string',calls[1]['payload']['repairError'])
        self.assertIn('até40 pontos',calls[1]['payload']['geometryBudget'])
        self.assertEqual(len(calls),3)

    def test_guided_structured_schema_bounds_paths_and_allows_no_teaching_panel(self):
        from services.visual_schema import format_for_stage,omit_null_fields
        data=validate_rules(process_demo())
        fmt=format_for_stage('openai','gpt-4o','-scene',data,{})
        schema=fmt['json_schema']['schema']
        path=schema['$defs']['node_path']['properties']['attrs']['properties']['d']
        self.assertEqual(path['maxLength'],1600)
        self.assertEqual(schema['properties']['teaching'],{'type':'null'})
        self.assertEqual(omit_null_fields({'teaching':None}),{})
        review=format_for_stage('openai','gpt-4o','-review',data,{'scene':scene(True)})
        self.assertTrue(review['json_schema']['strict'])
        self.assertIsNone(format_for_stage('other','model','-scene',data,{}))

    def test_failed_review_is_never_silently_approved_as_an_illustration(self):
        (visual,notice),calls=self.run_generation([scene(False),rejection(),scene(False),rejection()])
        self.assertIsNone(visual);self.assertIn('diagrama conceitual',notice)
        self.assertEqual(len(calls),4)

    def test_artwork_fixture_has_supported_geometry_without_new_theme_primitives(self):
        visual=validate_visual(scene(True),validate_rules(process_demo()))
        self.assertEqual(sum(n['type']=='polygon' for n in visual['nodes']),4)
        self.assertEqual(sum(n['type']=='group' for n in visual['nodes']),4)

    def test_reported_scene_geometry_requires_semantic_review_despite_valid_schema(self):
        # Exact topology/coordinates from the supplied HTML: a shared translated
        # group with four displaced circles, all rotating around that group origin.
        raw=scene(False);raw['nodes']=[{'id':'gear_system','type':'group','label':'Sistema de Engrenagens','attrs':{'x':400,'y':225}}]
        for i,(name,x,r,c) in enumerate(zip(['red','blue','green','yellow'],[-150,0,150,300],[60,50,40,30],['#FF0000','#0000FF','#00FF00','#FFFF00'])):
            raw['nodes'].append({'id':'gear_'+name,'type':'circle','parent':'gear_system','label':'Engrenagem '+name,
                'attrs':{'x':x,'y':0,'r':r,'fill':c,'stroke':'#000000','strokeWidth':4},
                'bindings':[{'property':'rotation','var':'etapa','input':[0,2],'output':[0,360 if i%2==0 else -360]}]})
            raw['nodes'].append({'id':'label_'+name,'type':'text','label':name,'attrs':{'x':400+x,'y':150,'text':name,'fontSize':28,'anchor':'middle','fill':c}})
        self.assertEqual(len(validate_visual(raw,validate_rules(process_demo()))['nodes']),9)
        # Structural validation alone cannot certify recognizable silhouettes.
        (visual,notice),calls=self.run_generation([raw,dict(rejection(),issues=[dict(rejection()['issues'][0],nodes=['gear_red'])]),scene(True),approval()])
        self.assertIsNotNone(visual);self.assertFalse(notice)
        self.assertIn('pivô',calls[1]['system'])


if __name__=='__main__':unittest.main()
