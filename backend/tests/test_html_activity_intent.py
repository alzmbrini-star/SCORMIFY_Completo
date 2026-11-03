import unittest
from services.html_activity_intent import html_activity_kind


class HtmlIntent(unittest.TestCase):
    def test_demonstrations_reach_guided_engine_across_subjects(self):
        for prompt in ('Crie uma demonstração visual guiada da formação de tempestades.',
                       'Crie uma demonstracao didatica de engrenagens.',
                       'Uma demonstração guiada do atendimento a clientes.',
                       'Animação didática do fluxo de documentos.',
                       'Create a guided visual demonstration of a process.',
                       'Crie um simulador sobre um assunto novo.', 'Simuladores de negociação','A simulation of resource allocation'):
            self.assertEqual(html_activity_kind(prompt),'simulation',prompt)

    def test_html_quiz_and_case_study_keep_their_routes(self):
        for prompt in ('Crie um quiz de aprendizagem.','Crie um painel HTML com cartões.','Uma página HTML com texto e imagens.'):
            self.assertEqual(html_activity_kind(prompt),'html')
        self.assertEqual(html_activity_kind('Estudo de caso com simulação de diálogo'),'case-study')
        self.assertEqual(html_activity_kind('Case studies on teamwork'),'case-study')
        self.assertEqual(html_activity_kind('Demonstração visual','visualization'),'visualization')


if __name__=='__main__':unittest.main()
