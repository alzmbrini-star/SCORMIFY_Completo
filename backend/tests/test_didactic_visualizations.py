import copy
import json
import unittest
from unittest.mock import AsyncMock,patch
from services.didactic_visualizations import validate,render,generate_visualization,ENGINE


def fixture():
    def node(key,kind,label,attrs):return {'id':key,'type':kind,'label':label,'explanation':label+'. Representação ilustrativa fora de escala.','attrs':attrs}
    return {'title':'Explorando um modelo de átomo','subtitle':'Observe o núcleo e o movimento ilustrativo do elétron.',
      'learningGoal':'Distinguir partículas do núcleo e uma representação simplificada de elétron.',
      'scientificNote':'Prótons e nêutrons ficam no núcleo. A trajetória do elétron é uma ilustração de Bohr, não uma órbita quântica real. Tamanhos, distâncias e velocidades não estão em escala.',
      'duration':12,'background':'#10243b','nodes':[
        node('track','ellipse','Trajetória ilustrativa',{'x':400,'y':225,'rx':240,'ry':120,'fill':'none','stroke':'#93c5fd','strokeWidth':3}),
        node('proton','circle','Próton no núcleo',{'x':385,'y':225,'r':24,'fill':'#fc7c76'}),
        node('neutron','circle','Nêutron no núcleo',{'x':418,'y':225,'r':24,'fill':'#bac7db'}),
        node('electron','circle','Elétron ilustrativo',{'x':400,'y':225,'r':12,'fill':'#5ce4d5'}),
        node('label','text','Núcleo',{'x':400,'y':315,'text':'Núcleo','anchor':'middle','fontSize':28,'fill':'#ffffff'})],
      'motions':[{'node':'electron','kind':'orbit','cx':400,'cy':225,'dx':240,'dy':120,'cycles':1,'phase':0}]}


class Visualizations(unittest.TestCase):
    def test_no_outcomes_or_rule_solver_required(self):
        data=validate(fixture())
        self.assertEqual(len(data['motions']),1)
        with patch('services.rule_simulators.validate_rules',side_effect=AssertionError('must not call')):
            document=render(data)
        self.assertIn(ENGINE,document);self.assertNotIn('LMSSetValue',document)
        self.assertNotIn('__stage',document);self.assertNotIn('postMessage',document)
        self.assertEqual(data,validate(data))

    def test_code_urls_and_arbitrary_attributes_rejected(self):
        for field,value in [('type','image'),('attrs',{'href':'https://example.com','onload':'alert(1)'})]:
            data=fixture();data['nodes'][0][field]=value
            with self.assertRaises(ValueError):validate(data)
        data=fixture();data['nodes'][0]['attrs']['fill']='url(https://example.com)'
        with self.assertRaises(ValueError):validate(data)

    def test_clip_bad_references_duplicate_and_nonfinite_rejected(self):
        for change in (lambda d:d['motions'][0].update(node='missing'),lambda d:d['nodes'][3]['attrs'].update(x=600),
                       lambda d:d['motions'].append(copy.deepcopy(d['motions'][0])),lambda d:d.update(duration=float('nan'))):
            data=fixture();change(data)
            with self.assertRaises(ValueError):validate(data)

    def test_payload_text_inert(self):
        data=fixture();data['title']='</script><script>alert(1)</script>'
        document=render(data)
        self.assertNotIn('</script><script>alert',document)
        self.assertIn('\\u003c/script',document)

    def test_export_keeps_responsive_animation_without_stage_shrinker(self):
        import base64,re
        from services.single_page_exporter import _render_html_element_inner
        original=render(fixture())
        outer=_render_html_element_inner({'type':'html','htmlContent':original,'height':540},'qa','','',0,0)
        payload=re.search(r'data:text/html;charset=utf-8;base64,([^\"]+)',outer).group(1)
        exported=base64.b64decode(payload).decode()
        self.assertIn('scormify-visualization-plan',exported)
        self.assertIn('grid-template-rows:auto minmax(0,1fr) auto',exported)
        self.assertNotIn('__stage',exported)
        self.assertNotIn('padding:0 !important',exported)


class Generation(unittest.IsolatedAsyncioTestCase):
    async def test_general_model_and_independent_review_no_scored_engine(self):
        chat=AsyncMock();chat.with_model.return_value=chat;chat.with_params.return_value=chat
        # chain methods must be synchronous, send only is asynchronous
        from unittest.mock import MagicMock
        chat=MagicMock();chat.with_model.return_value=chat;chat.with_params.return_value=chat
        chat.send_message=AsyncMock(side_effect=[json.dumps(fixture()),'{"approved":true,"issues":[]}'])
        with patch('emergentintegrations.llm.chat.LlmChat',return_value=chat):
            result=await generate_visualization('Represente um átomo','Curso de ciências','test','openai','fake','configured')
        self.assertEqual(result['spec']['mechanic'],ENGINE)
        self.assertEqual(chat.send_message.await_count,2)

    async def test_selection_survives_editor_and_agent_contexts(self):
        from services.simulator_experience import with_options,activity_type
        from services.simulator_diagnostics import simulator_request
        self.assertEqual(activity_type(with_options('Curso',{'activityType':'visualization'})),'visualization')
        _,context=simulator_request({'title':'Explorar'},'Ciências',{'simulatorActivityType':'visualization'})
        self.assertEqual(activity_type(context),'visualization')
        self.assertEqual(activity_type('legacy'),'simulation')


if __name__=='__main__':unittest.main()
