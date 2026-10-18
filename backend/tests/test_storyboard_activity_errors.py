import unittest
from unittest.mock import patch

from services.generation_errors import StoryboardActivityError, storyboard_error_message
from services import ai_agent


class StoryboardErrorTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_simulator_reports_slide_and_preserves_original_cause(self):
        async def rejected(*args):
            raise ValueError('Falta implementar o controle planejado: Escolher Resposta')
        structure = {'modules': [{'title': 'Feedback', 'slides': [
            {'type': 'simulator', 'title': 'Exercícios Práticos', 'purpose': 'Praticar feedback'}]}]}
        with patch('services.visual_simulators.generate_visual_simulator', rejected):
            with self.assertRaises(StoryboardActivityError) as captured:
                await ai_agent.generate_storyboard('test', 'Conteúdo do curso de feedback.', structure, {})
        message = storyboard_error_message(captured.exception)
        self.assertIn('Exercícios Práticos', message)
        self.assertIn('Escolher Resposta', message)
        self.assertIsInstance(captured.exception.cause, ValueError)

    def test_timeouts_and_provider_errors_have_actionable_safe_messages(self):
        self.assertIn('tempo de resposta', storyboard_error_message(StoryboardActivityError('simulador', 'Conversa', TimeoutError())))
        self.assertIn('cota', storyboard_error_message(RuntimeError('insufficient_quota billing')))
        self.assertIn('temporariamente indisponível', storyboard_error_message(RuntimeError('502 BadGateway')))
        self.assertNotIn('sk-test-private', storyboard_error_message(RuntimeError('invalid key sk-test-private')))


if __name__ == '__main__': unittest.main()
