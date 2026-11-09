import asyncio
import base64
import copy
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from PIL import Image
from services.simulator_object_images import candidates, validate_illustrations, image_scope, enrich
from test_didactic_visualizations import fixture
from services.didactic_visualizations import validate, render


def png():
    image=Image.new('RGBA',(40,40),(10,100,180,255)); image.putpixel((0,0),(0,0,0,0))
    out=io.BytesIO();image.save(out,format='PNG');return out.getvalue()


class ObjectImages(unittest.TestCase):
    def setUp(self):
        key=patch('services.llm_config.openai_api_key',return_value='test-key')
        key.start();self.addCleanup(key.stop)
    def test_rigid_pieces_only_never_replace_flow_or_outline(self):
        data=fixture();ids={n['id'] for n in candidates(data)}
        self.assertNotIn('track',ids);self.assertIn('proton',ids)
        data['nodes'][1]['bindings']=[{'property':'r'}]
        self.assertNotIn('proton',{n['id'] for n in candidates(data)})

    def test_embedded_raster_only_and_round_trip_offline(self):
        data=fixture();data['illustrations']=[{'node':'electron','src':'data:image/png;base64,'+base64.b64encode(png()).decode()}]
        clean=validate(data);self.assertEqual(clean['motions'],data['motions'])
        html=render(data);self.assertIn('scormify-object-images',html);self.assertIn(data['illustrations'][0]['src'],html)
        for bad in ['https://example.com/p.png','data:image/svg+xml;base64,PHN2Zz4=','data:image/png;base64,bad']:
            with self.assertRaises(ValueError):validate_illustrations([{'node':'electron','src':bad}],data['nodes'])

    def test_generation_persists_before_application_and_preserves_rules(self):
        from emergentintegrations.llm.chat import LlmChat
        data=fixture();spec=dict(data,mechanic='didactic-visualization-v1')
        db=SimpleNamespace(image_gallery=SimpleNamespace(update_one=AsyncMock(),find_one=AsyncMock(return_value=None)))
        async def run():
            with image_scope(db,{'user_id':'author','companyId':'company'}):
                return await enrich({'spec':spec,'html':'old'},'atom',json.dumps({'simulatorOptions':{'objectImages':True}}),'qa')
        chat=SimpleNamespace(send_message=AsyncMock(return_value=json.dumps({'pieces':[{'node':'electron','description':'blue particle'}]})))
        chat.with_model=lambda *args:chat;chat.with_params=lambda **args:chat
        with patch('emergentintegrations.llm.chat.LlmChat',return_value=chat),patch('services.llm_config.simulator_generation_config',return_value=('openai','fake','model')),patch('services.simulator_object_images.generate_piece',AsyncMock(return_value=png())):
            result=asyncio.run(run())
        self.assertEqual(result['spec']['motions'],data['motions']);self.assertNotIn('illustrations',spec)
        doc=db.image_gallery.update_one.call_args.args[1]['$setOnInsert']
        self.assertEqual(doc['userId'],'author');self.assertEqual(doc['companyId'],'company');self.assertTrue(doc['imageUrl'].startswith('data:image/png'))
        self.assertIn('scormify-object-images',result['html'])

    def test_library_reuse_does_not_generate_again(self):
        src='data:image/png;base64,'+base64.b64encode(png()).decode()
        db=SimpleNamespace(image_gallery=SimpleNamespace(find_one=AsyncMock(return_value={'imageUrl':src}),update_one=AsyncMock()))
        chat=SimpleNamespace(send_message=AsyncMock(return_value='{"pieces":[{"node":"electron","description":"particle"}]}'))
        chat.with_model=lambda *args:chat;chat.with_params=lambda **args:chat
        async def run():
            with image_scope(db,{'user_id':'owner'}):
                return await enrich({'spec':dict(fixture(),mechanic='didactic-visualization-v1'),'html':'old'},'topic','{"simulatorOptions":{"objectImages":true}}','qa')
        with patch('emergentintegrations.llm.chat.LlmChat',return_value=chat),patch('services.llm_config.simulator_generation_config',return_value=('openai','fake','model')),patch('services.simulator_object_images.generate_piece',AsyncMock()) as paid:
            result=asyncio.run(run())
        paid.assert_not_called();db.image_gallery.update_one.assert_not_called()
        self.assertEqual(result['spec']['illustrations'][0]['src'],src)

    def test_no_opt_in_or_owner_scope_never_calls_paid_service(self):
        with patch('services.simulator_object_images.generate_piece',AsyncMock()) as paid:
            original={'spec':fixture(),'html':'old'}
            self.assertIs(asyncio.run(enrich(original,'x','{}','qa')),original)
            with self.assertRaisesRegex(ValueError,'identificar o autor'):
                asyncio.run(enrich(original,'x','{"simulatorOptions":{"objectImages":true}}','qa'))
            paid.assert_not_called()

    def test_missing_image_key_is_explicit_before_any_planning_charge(self):
        with image_scope(SimpleNamespace(),{'user_id':'author'}),patch('services.llm_config.openai_api_key',return_value=''),patch('services.simulator_object_images.generate_piece',AsyncMock()) as paid:
            with self.assertRaisesRegex(ValueError,'configure a chave OpenAI'):
                asyncio.run(enrich({'spec':fixture(),'html':'old'},'x','{"simulatorOptions":{"objectImages":true}}','qa'))
            paid.assert_not_called()

    def test_images_only_keeps_scene_and_never_invokes_vector_refiner(self):
        from services.simulator_object_images import illustrate_existing
        from services.rule_simulators import validate_rules
        from test_process_visual_refinement import pump_model,pump_scene
        data=pump_model();data['visual']=pump_scene();data=validate_rules(data)
        piece={'node':'reservoir1','src':'data:image/png;base64,'+base64.b64encode(png()).decode()}
        async def enriched(result,*args):
            result['spec']['visual']['illustrations']=[piece]
            return result
        before=copy.deepcopy(data)
        with patch('services.simulator_object_images.enrich',side_effect=enriched),patch('services.rule_visuals.generate_visual',AsyncMock()) as vector:
            result=asyncio.run(illustrate_existing(json.dumps(data),'Peças','Curso'))
        vector.assert_not_called()
        for field in ('variables','actions','goal','failure'):self.assertEqual(result['spec'][field],before[field])
        self.assertEqual(result['spec']['visual']['nodes'],before['visual']['nodes'])

    def test_images_only_zero_result_is_not_a_success(self):
        from services.simulator_object_images import illustrate_existing
        from services.rule_simulators import validate_rules
        from test_process_visual_refinement import pump_model,pump_scene
        data=pump_model();data['visual']=pump_scene();data=validate_rules(data)
        async def unchanged(result,*args):return result
        with patch('services.simulator_object_images.enrich',side_effect=unchanged):
            with self.assertRaisesRegex(ValueError,'Nenhuma imagem foi gerada'):
                asyncio.run(illustrate_existing(json.dumps(data),'Peças','Curso'))

    def test_duplicates_or_nonexistent_target_rejected(self):
        row={'node':'electron','src':'data:image/png;base64,'+base64.b64encode(png()).decode()}
        with self.assertRaises(ValueError):validate_illustrations([row,row],fixture()['nodes'])
        with self.assertRaises(ValueError):validate_illustrations([dict(row,node='missing')],fixture()['nodes'])
