import copy
import json
import unittest
import asyncio
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from services.component_authoring import compose, stored_model, same_rules
from services.rule_simulators import render_rules
from component_pilots import feedback_pilot, planning_pilot, technical_pilot


class Authoring(unittest.TestCase):
    def test_composition_preserves_every_rule_and_roundtrips(self):
        for pilot in (feedback_pilot, planning_pilot, technical_pilot):
            model = stored_model(render_rules(pilot('studio')))
            before = copy.deepcopy(model)
            project = copy.deepcopy(model['visualProject'])
            project['style'] = 'blueprint'
            result = stored_model(compose(json.dumps(model), project)['html'])
            self.assertTrue(same_rules(model, result))
            self.assertEqual(result['visualProject']['style'], 'blueprint')
            self.assertEqual(model, before)
            self.assertNotIn('checks', result)
            self.assertNotIn('verification', result)

    def test_unsafe_project_and_logic_rejected(self):
        model = stored_model(render_rules(feedback_pilot('studio')))
        project = copy.deepcopy(model['visualProject'])
        project['instances'][0]['component'] = '<script>'
        with self.assertRaises(ValueError): compose(json.dumps(model), project)
        model['actions'][0]['effects'] = {'invented': 99}
        with self.assertRaises(ValueError): compose(json.dumps(model), model['visualProject'])

    def test_no_html_execution_or_ambiguous_model(self):
        with self.assertRaises(ValueError): stored_model('<script>alert(1)</script>')
        html = render_rules(feedback_pilot('studio'))
        with self.assertRaises(ValueError): stored_model(html + html)
        with self.assertRaises(ValueError): compose('x' * 120001, {})

    def test_modified_effects_not_same_rules(self):
        model = stored_model(render_rules(feedback_pilot('studio')))
        changed = copy.deepcopy(model)
        changed['actions'][0]['feedback'] = 'Changed'
        self.assertFalse(same_rules(model, changed))


if __name__ == '__main__': unittest.main()


class HttpError(Exception):
    def __init__(self, status_code, detail): self.status_code, self.detail = status_code, detail


class Routes(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.html = render_rules(feedback_pilot('studio'))
        model = stored_model(self.html)
        project = copy.deepcopy(model['visualProject']); project['style'] = 'blueprint'
        self.body = SimpleNamespace(sourceSimulator=json.dumps(model), visualProject=project, slideIndex=0, elementIndex=0)
        self.collection = SimpleNamespace(find_one=AsyncMock(return_value={'storyboard': {'slides': [{'elements': [{'type': 'html', 'htmlContent': self.html}]}]}}),
                                          update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)))
        from datetime import datetime, timezone
        self.scope = dict(asyncio=asyncio, HTTPException=HttpError, Depends=lambda _: None, require_auth=None,
                          db=SimpleNamespace(agent_sessions=self.collection), datetime=datetime, timezone=timezone)
        path = Path(__file__).resolve().parents[1] / 'routes/html_generation_jobs.py'
        for node in ast.parse(path.read_text(encoding='utf-8')).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {'_owner','save_components','preview_components'}:
                node.decorator_list = []
                exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), self.scope)

    async def save(self): return await self.scope['save_components']('session', self.body, {'user_id': 'owner'})

    async def test_owner_scope_atomic_element_only_write(self):
        result = await self.save()
        self.assertIn('html', result)
        self.collection.find_one.assert_awaited_with({'id':'session','userId':'owner'})
        query, update = self.collection.update_one.call_args.args
        path = 'storyboard.slides.0.elements.0.htmlContent'
        self.assertEqual(query[path], self.html)
        self.assertEqual(query['userId'], 'owner')
        self.assertEqual(set(update['$set']), {path, 'updatedAt'})

    async def test_other_owner_and_concurrent_updates_rejected(self):
        self.collection.find_one.return_value = None
        with self.assertRaises(HttpError) as err: await self.save()
        self.assertEqual(err.exception.status_code,404)
        self.collection.update_one.assert_not_awaited()
        self.setUp()
        self.collection.update_one.return_value = SimpleNamespace(modified_count=0)
        session = self.collection.find_one.return_value
        self.collection.find_one.side_effect = [session, None]
        with self.assertRaises(HttpError) as err: await self.save()
        self.assertEqual(err.exception.status_code,409)

    async def test_changed_rules_and_stale_visual_rejected(self):
        for key, value in [('mission','different goal'),('visual',{})]:
            model = stored_model(self.html); model[key] = value
            self.body.sourceSimulator = json.dumps(model)
            with self.assertRaises(HttpError) as err: await self.save()
            self.assertEqual(err.exception.status_code,409)
        self.collection.update_one.assert_not_awaited()
