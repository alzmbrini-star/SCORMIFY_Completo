"""Agent games must never replace course questions with a tenant-wide sample."""
import copy
import json
import unittest
from unittest.mock import patch

from services import ai_agent

EVIDENCE = 'A autenticação multifator exige um segundo fator para reduzir acessos indevidos.'
CONTENT = {'type': 'content', 'title': 'Proteção de acesso', 'moduleName': 'Segurança',
           'elements': [{'type': 'html', 'content': '<p>' + EVIDENCE + ' Senhas únicas reduzem a reutilização de credenciais.</p>'}]}
GAME = {'type': 'game', 'title': 'Desafio de proteção de acesso', 'moduleName': 'Segurança',
        'gameMechanic': 'penalty_quest', 'elements': []}


def rows():
    return [{'question': f'No caso {i + 1}, como proteger o acesso usando autenticação multifator?',
             'alternatives': [{'id': 'A', 'text': 'Exigir um segundo fator'},
                              {'id': 'B', 'text': 'Compartilhar a senha'},
                              {'id': 'C', 'text': 'Desabilitar a verificação'},
                              {'id': 'D', 'text': 'Reutilizar credenciais'}],
             'correctAnswer': 'A', 'explanation': EVIDENCE, 'sourceEvidence': EVIDENCE}
            for i in range(6)]


class ContextualGameTests(unittest.IsolatedAsyncioTestCase):
    async def test_generated_questions_keep_course_and_company_ownership(self):
        calls = []
        async def reply(session, system, prompt):
            calls.append(prompt)
            return json.dumps({'questions': rows()})
        with patch.object(ai_agent, '_resilient_send', reply):
            result = await ai_agent._generate_course_game_questions(GAME, [CONTENT, GAME],
                {'title': 'Segurança corporativa'}, 'project-new', 'company-one', 'test')
        self.assertEqual(len(result), 6)
        self.assertEqual(len({item['id'] for item in result}), 6)
        self.assertTrue(all(item['projectId'] == 'project-new' and item['companyId'] == 'company-one' for item in result))
        self.assertTrue(all(item['sourceEvidence'] == EVIDENCE for item in result))
        self.assertIn(EVIDENCE, calls[0])

    async def test_unrelated_questions_and_invalid_answers_fail_without_fallback(self):
        for invalid in ('evidence', 'answer', 'duplicate'):
            generated = rows()
            if invalid == 'evidence': generated[0]['sourceEvidence'] = 'A bomba hidráulica deve elevar a água até o tanque.'
            if invalid == 'answer': generated[0]['correctAnswer'] = 'Z'
            if invalid == 'duplicate': generated[1] = copy.deepcopy(generated[0])
            async def reply(*args): return json.dumps({'questions': generated})
            with patch.object(ai_agent, '_resilient_send', reply):
                with self.assertRaises(ValueError):
                    await ai_agent._generate_course_game_questions(GAME, [CONTENT], {}, 'p', 'c', 'test')

    def test_reference_prioritizes_module_and_ignores_other_game_code(self):
        unrelated = {'type': 'content', 'moduleName': 'Vendas', 'title': 'SPIN', 'body': 'Negociação comercial fora do módulo.'}
        old_game = dict(GAME, elements=[{'htmlContent': '<script>const questionBank = ["PERGUNTA ANTIGA"]</script>'}])
        reference = ai_agent._game_question_reference(GAME, [unrelated, CONTENT, old_game], {})
        self.assertIn(EVIDENCE, reference)
        self.assertNotIn('Negociação comercial', reference)
        self.assertNotIn('PERGUNTA ANTIGA', reference)
        with self.assertRaises(ValueError):
            ai_agent._game_question_reference(GAME, [GAME], {})

    async def test_course_game_embeds_exact_generated_snapshot_without_reading_bank(self):
        async def reply(*args): return json.dumps({'questions': rows()})
        async def forbidden_bank(): raise AssertionError('Global bank must not be read')
        with patch.object(ai_agent, '_resilient_send', reply), patch.object(ai_agent, '_get_motor_db', forbidden_bank):
            result = await ai_agent.generate_course_from_storyboard('test',
                {'slides': [copy.deepcopy(CONTENT), copy.deepcopy(GAME)]}, {'title': 'Segurança corporativa'},
                project_id='project-new', company_id='company-one', media_config={'0': {'type': 'none'}})
        questions = result['gameQuestions']
        game = result['slides'][1]
        self.assertEqual(len(questions), 6)
        self.assertEqual(game['gameQuestionIds'], [q['id'] for q in questions])
        document = game['elements'][0]['htmlContent']
        for question in questions:
            self.assertIn(question['id'], document)
            self.assertIn(question['question'], document)
        self.assertNotIn('qual alternativa melhor representa o aprendizado central', document)


if __name__ == '__main__':
    unittest.main()
