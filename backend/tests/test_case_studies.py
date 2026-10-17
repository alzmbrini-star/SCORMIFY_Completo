import copy
import json
import unittest
from services.case_studies import validate_case, render_case, generate_case_study

REFERENCE = 'O feedback deve descrever comportamentos observáveis e seus impactos. O acordo de acompanhamento deve definir responsabilidades e prazos claros.'


def fixture():
    return dict(title='Feedback corretivo com evidências', context='Uma líder precisa tratar atrasos recorrentes sem desmotivar a equipe.',
        mission='Investigue os fatos e conduza a conversa até um acordo verificável.',
        metrics=['Clareza', 'Confiança', 'Compromisso'], debrief='Compare suas decisões com os fatos e planeje o acompanhamento.',
        evidence=[dict(id=f'e{i}', title=f'Registro {i}', text=f'Situação fictícia {i}: o prazo foi perdido após uma mudança de prioridade.',
                       sourceEvidence='O feedback deve descrever comportamentos observáveis e seus impactos.') for i in range(3)],
        decisions=[dict(title=f'Etapa {i}', question='Qual ação é mais fundamentada pelos fatos do caso?', evidenceIds=['e0','e1'],
            choices=[dict(label=f'Ação {i}.{j}', feedback=f'Consequência {j}: compare o impacto com os registros.',
                          quality=j, effects=[j*5,-j*2,j*3]) for j in range(3)]) for i in range(3)])


class CaseStudyTests(unittest.IsolatedAsyncioTestCase):
    def test_grounding_and_decision_validation(self):
        self.assertEqual(len(validate_case(fixture(), REFERENCE)['decisions']), 3)
        for field in ('source', 'answer', 'link'):
            bad = fixture()
            if field == 'source': bad['evidence'][0]['sourceEvidence'] = 'Este texto foi inventado fora do conteúdo do curso.'
            if field == 'answer': bad['decisions'][0]['choices'][0]['quality'] = 2
            if field == 'link': bad['decisions'][0]['evidenceIds'] = ['inexistente']
            with self.assertRaises(ValueError): validate_case(bad, REFERENCE)

    def test_offline_and_safe_data_rendering(self):
        spec = validate_case(fixture(), REFERENCE)
        spec['context'] = '</script><img src="https://invalid.example/image.png">'
        rendered = render_case(spec)
        self.assertNotIn(spec['context'], rendered)
        self.assertNotIn('<img ', rendered)
        self.assertNotIn('<script src=', rendered)
        self.assertNotIn('__CASE_DATA__', rendered)
        self.assertIn('data-case-study-version="2"', rendered)
        self.assertIn('createElementNS', rendered)

    async def test_repair_and_context_are_required(self):
        calls = []
        async def send(session, system, request):
            calls.append(request)
            return '{}' if len(calls) == 1 else json.dumps(fixture())
        result = await generate_case_study('Feedback corretivo', REFERENCE, send, 'test')
        self.assertEqual(len(calls), 2)
        self.assertIn(REFERENCE, calls[0])
        self.assertIn('case-data', result['html'])
        with self.assertRaises(ValueError):
            await generate_case_study('Caso', '', send, 'test')

    async def test_agent_replaces_broken_images_and_storyboard_uses_structured_case(self):
        from services import ai_agent
        from unittest.mock import patch
        async def send(*args): return json.dumps(fixture())
        case = {'type': 'case_study', 'title': 'Feedback corretivo', 'moduleName': 'Liderança',
                'elements': [{'type': 'html', 'htmlContent': '<html><body><img src="imagem-inexistente.jpg"></body></html>'}]}
        content = {'type': 'content', 'title': 'Princípios de feedback', 'moduleName': 'Liderança',
                   'elements': [{'content': '<p>' + REFERENCE + '</p>'}]}
        with patch.object(ai_agent, '_resilient_send', send):
            result = await ai_agent.generate_course_from_storyboard('test', {'slides': [content, case]},
                {'title': 'Liderança'}, media_config={'0': {'type': 'none'}})
            document = result['slides'][1]['elements'][0]['htmlContent']
            self.assertIn('data-case-study-version="2"', document)
            self.assertNotIn('imagem-inexistente.jpg', document)
            self.assertNotIn('__scormify_fit_v3', document)
            storyboard = await ai_agent.generate_storyboard('test', REFERENCE,
                {'modules': [{'title': 'Liderança', 'slides': [case]}]}, {'title': 'Liderança'})
            self.assertIn('data-case-study-version="2"', storyboard['slides'][0]['elements'][0]['htmlContent'])


if __name__ == '__main__': unittest.main()
