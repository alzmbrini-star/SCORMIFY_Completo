"""Exercise the endpoint's error response without starting the API or database."""
import ast
import logging
import re
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class ResponseError(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class EditorSimulatorErrors(unittest.IsolatedAsyncioTestCase):
    async def test_editor_receives_validation_reason_instead_of_generic_html_error(self):
        route = Path(__file__).resolve().parents[1] / 'routes' / 'agent.py'
        tree = ast.parse(route.read_text(encoding='utf-8'))
        function = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'generate_html_with_ai')
        function.decorator_list = []
        scope = {'Depends': lambda value: None, 'require_auth': lambda: None,
                 'GenerateHtmlRequest': object, 'HTTPException': ResponseError,
                 '_html_generation_credentials': lambda: ('test', 'test'),
                 're': re, 'uuid': uuid, 'logger': logging.getLogger('editor-test')}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(route), 'exec'), scope)
        async def rejected(*args):
            raise ValueError('Falta implementar o controle planejado: Escolher Unidades')
        with patch('services.llm_config.simulator_generation_config', return_value=('openai','test','test')), patch('services.visual_simulators.generate_visual_simulator', rejected):
            with self.assertRaises(ResponseError) as result:
                await scope['generate_html_with_ai'](SimpleNamespace(prompt='Crie um simulador de unidades', courseContext='Curso de medidas.'))
        self.assertEqual(result.exception.status_code, 422)
        self.assertIn('Escolher Unidades', result.exception.detail)
        self.assertIn('Seu curso não foi alterado', result.exception.detail)
        self.assertNotIn('HTML inválido ou inseguro', result.exception.detail)


if __name__ == '__main__': unittest.main()
