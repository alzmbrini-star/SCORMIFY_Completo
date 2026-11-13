from services.creator_guide import topics_for


def test_scenario_guide_documents_the_delivered_image_and_decision_workflows():
    topic = next(t for t in topics_for({'role': 'superadmin'}) if t['id'] == 'scenario')
    text = str(topic)
    for required in ('Confirmar decisão', 'Gerar imagem com IA', 'Usar esta imagem',
                     'biblioteca', 'créditos', 'reexporte HTML/SCORM',
                     'Imagens e falas das cenas', 'controla apenas a exibição, não as regras de aprovação',
                     'Contexto geral', 'Situação desta cena', 'Personagens envolvidos', 'fonte menor'):
        assert required in text
    assert topic['link']['href'] == '/'  # Choose a real course before opening its Editor.
