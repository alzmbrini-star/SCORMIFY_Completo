import copy,json,unittest,asyncio
from unittest.mock import patch
from services.rule_simulators import validate_rules,PROCESS_DEMO
from services.rule_visuals import validate_visual,illustration_detail_issues,_color
from test_process_demo import process_demo
from test_rule_simulators import var,action,op,ref


def pump_model():
    """Compatible controls from the screenshot, not the unavailable saved source model."""
    model=process_demo();model['variables'].append(var('flow_rate','Vazão',50,100,'unidades ilustrativas'))
    model['actions'] += [action('aumentar','Aumentar vazão',op('le',ref('flow_rate'),90),{'flow_rate':op('add',ref('flow_rate'),10)}),
        action('diminuir','Diminuir vazão',op('ge',ref('flow_rate'),10),{'flow_rate':op('sub',ref('flow_rate'),10)})]
    model['experience']={'complexity':'guided','visualStyle':'illustrated'}
    return validate_rules(model)


def pump_scene():
    """Geometry and opacity-only binding of the failed scene; no author course prose."""
    def shape(ident,kind,attrs,**extra):return dict(id=ident,type=kind,attrs=attrs,**extra)
    return {'version':1,'title':'Bomba didática','description':'Esquema qualitativo de dois reservatórios e uma bomba.',
        'background':'#87CEEB','nodes':[
            shape('ground','rect',{'x':0,'y':350,'width':800,'height':100,'fill':'#8B4513'}),
            shape('reservoir1','rect',{'x':50,'y':200,'width':150,'height':150,'fill':'#4682B4','stroke':'#000','strokeWidth':2}),
            shape('reservoir2','rect',{'x':600,'y':200,'width':150,'height':150,'fill':'#4682B4','stroke':'#000','strokeWidth':2}),
            shape('pump','group',{'x':300,'y':250},nodes=[
                shape('pump_body','rect',{'x':0,'y':0,'width':100,'height':50,'fill':'#696969','stroke':'#000','strokeWidth':2}),
                shape('pump_pipe_left','rect',{'x':-50,'y':15,'width':50,'height':20,'fill':'#696969','stroke':'#000','strokeWidth':2}),
                shape('pump_pipe_right','rect',{'x':100,'y':15,'width':50,'height':20,'fill':'#696969','stroke':'#000','strokeWidth':2})]),
            shape('water_flow','path',{'d':'M150,275 C200,275 400,275 550,275','stroke':'#00BFFF','strokeWidth':10,'fill':'none','opacity':.5},
                  bindings=[{'property':'opacity','var':'flow_rate','input':[0,100],'output':[.1,1]}]),
            shape('label_reservoir1','text',{'x':125,'y':190,'text':'Reservatório 1','fontSize':28,'anchor':'middle','fill':'#000'}),
            shape('label_reservoir2','text',{'x':675,'y':190,'text':'Reservatório 2','fontSize':28,'anchor':'middle','fill':'#000'}),
            shape('label_pump','text',{'x':350,'y':240,'text':'Bomba','fontSize':28,'anchor':'middle','fill':'#000'}),
            shape('label_flow_rate','text',{'x':400,'y':100,'text':'Vazão: {flow_rate}','fontSize':28,'anchor':'middle','fill':'#000'})]}


class DemoVisualRefinement(unittest.TestCase):
    def test_shorthand_color_is_losslessly_expanded_without_accepting_css(self):
        self.assertEqual(_color('#000'),'#000000');self.assertEqual(_color('#aBc'),'#aaBBcc')
        for value in ('url(https://example.com)','red','#0000','rgba(0,0,0,.5)','var(--x)'):
            with self.assertRaises(ValueError):_color(value)

    def test_actual_scene_topology_accepts_optional_flow_control_without_geometric_motion_or_shape_quota(self):
        model=pump_model();raw=pump_scene();before=copy.deepcopy(raw)
        scene=validate_visual(raw,model)
        self.assertEqual(raw,before)
        self.assertEqual(len(scene['nodes']),12)
        self.assertEqual(illustration_detail_issues(scene,model),[])
        self.assertTrue(all(c['actions']==['avancar','avancar'] for c in model['checks']))
        self.assertEqual(scene['nodes'][1]['attrs']['stroke'],'#000000')
        self.assertEqual(next(n for n in scene['nodes'] if n['id']=='water_flow')['bindings'][0]['property'],'opacity')
        canonical=json.loads(json.dumps(raw).replace('"#000"','"#000000"'))
        self.assertEqual(validate_visual(canonical,model),scene)

    def test_demo_does_not_accept_text_only_or_unreachable_appearance(self):
        for mode in ('text_only','unreachable'):
            raw=pump_scene()
            if mode=='text_only':raw['nodes'][4].pop('bindings')
            else:raw['nodes'][4]['bindings'][0].update(input=[90,100])
            model=pump_model()
            if mode=='unreachable':next(a for a in model['actions'] if a['id']=='aumentar')['requires']=op('le',ref('flow_rate'),50)
            with self.assertRaises(ValueError) as caught:validate_visual(raw,model)
            if mode=='unreachable':self.assertIn('não reage aos controles',str(caught.exception))

    def test_refinement_keeps_rules_and_uses_supported_qualitative_scene(self):
        from services.simulator_visual_refinement import refine_visual
        from services.component_authoring import stored_model
        model=pump_model();messages=[]
        class Chat:
            def __init__(self,**kwargs):self.system=kwargs['system_message']
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):
                messages.append(json.loads(message.text))
                if 'FIDELIDADE VISUAL' in self.system:return json.dumps({'approved':True,'summary':'Objetos pertinentes ao processo.','issues':[]})
                return json.dumps(pump_scene())
        with patch('services.llm_config.simulator_generation_config',return_value=('openai','test','model')),patch('emergentintegrations.llm.chat.LlmChat',Chat):
            result=asyncio.run(refine_visual(json.dumps(model),'Refinar bomba','Curso','guided','illustrated'))
        final=stored_model(result['html'])
        for field in ('variables','actions','goal','failure','didacticMode'):self.assertEqual(final[field],model[field])
        self.assertEqual(len(messages),2);self.assertIn('processDemonstration',messages[0])
        self.assertIn('não a uma cota artificial',messages[0]['finishRequirements'])


if __name__=='__main__':unittest.main()
