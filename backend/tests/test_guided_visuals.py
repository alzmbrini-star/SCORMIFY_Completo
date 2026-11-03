"""Full guided pipeline with real rasterization and fake (uncharged) LLM calls."""
import asyncio,copy,json,unittest
from unittest.mock import patch
from PIL import Image
from services.rule_simulators import validate_rules
from services.rule_visuals import validate_visual,generate_visual
from services.guided_scene_frames import sample_states,inspect_frames,frame_svg
from services.guided_visuals import validate_plan,merge_repair,plan_schema
from test_process_demo import process_demo


def art(kind='rect'):
    attrs={'x':70,'y':180,'fill':'#3589bd','stroke':'#10243b','strokeWidth':3}
    attrs.update({'width':140,'height':85,'rx':10} if kind=='rect' else {'r':50})
    return {'version':1,'title':'Processo ilustrativo','description':'Observe o deslocamento qualitativo do objeto.',
            'background':'#e3eff4','nodes':[{'id':'subject','type':kind,'label':'Objeto principal','attrs':attrs,
            'bindings':[{'property':'x','var':'etapa','input':[0,2],'output':[70,600]}]}]}


def plan(samples):
    return {'setting':'Ambiente contextual do assunto.','focus':'Acompanhar o mecanismo visual.',
            'composition':'Objeto principal grande em camadas; detalhes legíveis.','artDirection':'Materiais, contornos e contraste coerentes.',
            'objects':[{'id':'subject','label':'Objeto principal','layer':'subject','features':['Contorno reconhecível','Deslocamento visível'],
                        'explanation':'Representa a transformação ilustrada.','alwaysVisible':True}],
            'moments':[{'sampleIndex':s['sampleIndex'],'visibleObjects':['subject'],'change':'Acompanhar a posição do objeto.'} for s in samples]}


class GuidedVisuals(unittest.TestCase):
    def setUp(self):self.data=validate_rules(process_demo());self.samples=sample_states(self.data)

    def test_plan_covers_every_actual_stage_and_does_not_invent_state(self):
        self.assertEqual([s['state']['etapa'] for s in self.samples],[0,1,2])
        p=plan(self.samples);before=copy.deepcopy(p);self.assertEqual(validate_plan(p,self.samples),p);self.assertEqual(p,before)
        for change in (lambda x:x['moments'].pop(),lambda x:x['moments'][0].update(sampleIndex=99),lambda x:x['moments'][0].update(visibleObjects=['invented'])):
            p=plan(self.samples);change(p)
            with self.assertRaises(ValueError):validate_plan(p,self.samples)
        self.assertEqual(plan_schema(self.samples)['properties']['moments']['minItems'],3)

    def test_pixels_detect_ancestor_opacity_occlusion_same_color_and_missing_object(self):
        valid=validate_visual(art(),self.data);p=plan(self.samples)
        report,png=inspect_frames(valid,p,self.samples)
        self.assertFalse(report['issues']);self.assertTrue(png.startswith(b'\x89PNG'))
        for mode in ('parent','occluded','same_color','missing'):
            raw=art()
            if mode=='parent':raw['nodes'].insert(0,{'id':'parent','type':'group','label':'Grupo oculto','attrs':{'opacity':0}});raw['nodes'][1]['parent']='parent'
            if mode=='occluded':raw['nodes'].append({'id':'cover','type':'rect','label':'Camada opaca','attrs':{'x':0,'y':0,'width':800,'height':450,'fill':'#e3eff4'}})
            if mode=='same_color':raw['nodes'][0]['attrs'].update(fill='#e3eff4',stroke='#e3eff4')
            if mode=='missing':p=plan(self.samples);p['objects'][0]['id']='missing';[m.update(visibleObjects=['missing']) for m in p['moments']]
            report,_=inspect_frames(validate_visual(raw,self.data),p,self.samples)
            self.assertTrue(report['issues'],mode)

    def test_layer_order_coordinates_alpha_and_xml_escape_are_rendered_without_external_markup(self):
        raw=art();raw['nodes'][0]['label']='Texto <script> não executável'
        v=validate_visual(raw,self.data);xml=frame_svg(v,{'etapa':0})
        self.assertNotIn('<script',xml);self.assertNotIn('href=',xml);self.assertNotIn('foreignObject',xml)
        self.assertIn('x="70"',xml)

    def test_permanent_objects_are_checked_at_continuous_motion_phases(self):
        raw=art('circle');raw['motions']=[{'node':'subject','kind':'orbit','cx':70,'cy':180,'dx':300,'dy':0,'cycles':1,'phase':0}]
        report,_=inspect_frames(validate_visual(raw,self.data),plan(self.samples),self.samples)
        self.assertTrue(any('movimento' in i['problem'] for i in report['issues']))

    def test_local_repair_preserves_unaffected_layers_and_adds_descendants(self):
        old=art();old['nodes'].insert(0,{'id':'background','type':'rect','label':'Fundo','attrs':{'x':0,'y':0,'width':800,'height':450,'fill':'#ffffff'}})
        proposed=copy.deepcopy(old);proposed['nodes'][0]['attrs']['fill']='#000000';proposed['nodes'][1]['attrs']['fill']='#ff0000'
        result=merge_repair(old,proposed,['subject'])
        self.assertEqual(result['nodes'][0],old['nodes'][0]);self.assertEqual(result['nodes'][1]['attrs']['fill'],'#ff0000')

    def run_pipeline(self,responses,prompt='Assunto inédito'):
        calls=[];data=copy.deepcopy(self.data)
        class Chat:
            def __init__(self,**kwargs):self.system=kwargs['system_message']
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):
                calls.append({'system':self.system,'message':message,'payload':json.loads(message.text)})
                value=responses[len(calls)-1]
                return json.dumps(value)
        with patch('emergentintegrations.llm.chat.LlmChat',Chat):result=asyncio.run(generate_visual(data,prompt,'Contexto','qa','openai','fake','model'))
        self.assertEqual(data,self.data)
        return result,calls

    def test_plan_draw_render_review_images_for_different_subjects_without_templates(self):
        for title,shape in [('Tempestade','rect'),('Engrenamento','circle'),('Comunicação','rect')]:
            p=plan(self.samples);p['setting']=title
            (v,notice),calls=self.run_pipeline([p,art(shape),{'approved':True,'summary':'Cena corresponde ao plano.','issues':[]}],title)
            self.assertIsNotNone(v);self.assertFalse(notice);self.assertEqual(len(calls),3)
            self.assertIn('PLANO VISUAL GUIADO',calls[0]['system']);self.assertEqual(calls[1]['payload']['compositionPlan']['setting'],title)
            self.assertIsNotNone(calls[2]['message'].file_contents);self.assertGreater(len(calls[2]['message'].file_contents[0].data),1000)
            self.assertEqual(len(calls[2]['payload']['executedSamples']),3)

    def test_empty_stage_is_repaired_before_review_not_accepted_with_warning(self):
        broken=art();broken['nodes'][0]['attrs']['opacity']=0
        p=plan(self.samples)
        (v,notice),calls=self.run_pipeline([p,broken,art(),{'approved':True,'summary':'Reparada.','issues':[]}])
        self.assertIsNotNone(v);self.assertFalse(notice)
        self.assertIn('Execução visual',calls[2]['payload']['repairError']);self.assertEqual(calls[2]['payload']['repairTargets'],['subject'])
        (v,notice),calls=self.run_pipeline([p,broken,broken])
        self.assertIsNone(v);self.assertIn('execução visual',notice);self.assertEqual(len(calls),3)


if __name__=='__main__':unittest.main()
