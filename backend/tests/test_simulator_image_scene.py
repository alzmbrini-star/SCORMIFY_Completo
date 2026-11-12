import asyncio
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from test_process_visual_refinement import pump_model, pump_scene
from test_simulator_object_images import png
from services.simulator_image_scene import prepare_scene, check_image_slots
from services.simulator_object_images import enrich, image_scope, storyboard_status, illustrate_existing


def scene():
    value=pump_scene()
    value['nodes'][1]['artwork']={'bounds':[50,200,150,150], 'description':'Reservatório inteiro, vista coerente com a bomba.'}
    return value


class ImageSceneTests(unittest.TestCase):
    def test_group_paint_defaults_do_not_block_actual_image_opacity_changes(self):
        from services.simulator_object_images import candidates
        node={'id':'team','type':'group','label':'Equipe','attrs':{'x':100,'y':100,'opacity':1,'fill':'none'},
              'artwork':{'bounds':[0,0,220,180],'description':'Equipe colaborando'},
              'states':[{'when':True,'set':{'x':100,'y':100,'opacity':0,'fill':'#FFD700','stroke':'none','strokeWidth':0}}]}
        self.assertEqual([p['id'] for p in candidates({'nodes':[node]})],['team'])
        node['states'][0]['set']['opacity']=1
        self.assertEqual(candidates({'nodes':[node]}),[])

    def test_empty_or_initially_hidden_slots_require_repair_before_image_charge(self):
        from services.rule_visuals import validate_visual
        value=validate_visual(scene(),pump_model())
        # A structurally valid empty group must not be confused with a drawing.
        value['nodes'].append({'id':'team','type':'group','label':'Equipe','attrs':{'x':300,'y':100},'bindings':[],'states':[],
                              'artwork':{'bounds':[0,0,220,180],'description':'Equipe colaborando'}})
        with self.assertRaisesRegex(ValueError,'sem desenho'):check_image_slots(value,pump_model())
    def test_prepares_subject_specific_typed_scene_without_changing_rules(self):
        model=pump_model();before=copy.deepcopy(model)
        raw=scene()
        raw['nodes'][-1]['attrs']['opacity']=1
        raw['nodes'][-1]['bindings']=[{'property':'opacity','var':'etapa','input':[0,2],'output':[1,1]}]
        chat=SimpleNamespace(send_message=AsyncMock(return_value=json.dumps(raw)))
        chat.with_model=lambda *a:chat
        chat.with_params=lambda **kw:chat
        with patch('emergentintegrations.llm.chat.LlmChat',return_value=chat),patch('services.llm_config.simulator_generation_config',return_value=('openai','fake','model')):
            result=asyncio.run(prepare_scene(model,'Processo da bomba','{}','qa'))
        self.assertEqual(model,before)
        self.assertEqual(result['nodes'][1]['artwork']['bounds'],[50,200,150,150])

    def test_missing_scene_is_prepared_then_images_persist_and_render(self):
        model=pump_model();before=copy.deepcopy(model)
        from services.rule_visuals import validate_visual
        prepared=validate_visual(scene(),model)
        chat=SimpleNamespace(send_message=AsyncMock(return_value='{"pieces":[{"node":"reservoir1","description":"Reservatório"}]}'))
        chat.with_model=lambda *a:chat
        chat.with_params=lambda **kw:chat
        db=SimpleNamespace(image_gallery=SimpleNamespace(find_one=AsyncMock(return_value=None),update_one=AsyncMock()))
        async def run():
            with image_scope(db,{'user_id':'owner','companyId':'company'}):
                return await enrich({'spec':model,'html':'old'},'bomba','{"simulatorOptions":{"objectImages":true}}','qa')
        with patch('services.simulator_image_scene.prepare_scene',AsyncMock(return_value=prepared)) as prepare,patch('services.llm_config.openai_api_key',return_value='fake'),patch('services.llm_config.simulator_generation_config',return_value=('openai','fake','model')),patch('emergentintegrations.llm.chat.LlmChat',return_value=chat),patch('services.simulator_object_images.generate_piece',AsyncMock(return_value=png())):
            result=asyncio.run(run())
        prepare.assert_awaited_once();db.image_gallery.update_one.assert_awaited_once()
        self.assertEqual(model,before)
        for k in ('variables','actions','goal','failure','checks'):self.assertEqual(result['spec'][k],before[k])
        self.assertIn('data:image/png;base64,',result['html'])
        self.assertEqual(storyboard_status(result['spec'],'{"simulatorOptions":{"objectImages":true}}')['imageCount'],1)

    def test_existing_editor_activity_without_scene_reaches_image_pipeline(self):
        model=pump_model()
        async def enriched(result,*args,**kw):
            result['spec']['visual']={'illustrations':[{'node':'piece','src':'mock'}]}
            return result
        with patch('services.simulator_object_images.enrich',side_effect=enriched) as mocked:
            result=asyncio.run(illustrate_existing(json.dumps(model),'topic','{}'))
        self.assertEqual(result['spec']['actions'],model['actions']);self.assertEqual(mocked.call_count,1)

    def test_status_distinguishes_no_opt_in_from_failed_scene(self):
        model=pump_model()
        status=storyboard_status(model,'{}')
        self.assertFalse(status['imagesRequested']);self.assertFalse(status['sceneAvailable'])

    def test_invalid_composition_has_two_bounded_attempts_and_no_image_call(self):
        chat=SimpleNamespace(send_message=AsyncMock(return_value='{}'))
        chat.with_model=lambda *a:chat
        chat.with_params=lambda **kw:chat
        with patch('emergentintegrations.llm.chat.LlmChat',return_value=chat),patch('services.llm_config.simulator_generation_config',return_value=('openai','fake','model')),patch('services.simulator_object_images.generate_piece',AsyncMock()) as paid:
            with self.assertRaisesRegex(ValueError,'preparar as peças'):
                asyncio.run(prepare_scene(pump_model(),'topic','{}','qa'))
        self.assertEqual(chat.send_message.await_count,2);paid.assert_not_called()
