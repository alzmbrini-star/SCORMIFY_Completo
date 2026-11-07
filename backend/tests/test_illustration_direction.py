import copy
from services.illustration_direction import ART_DIRECTION, illustration_brief
from services.guided_visuals import PLAN_PROMPT
from services.rule_visuals import VISUAL_PROMPT
from services.didactic_visualizations import PROMPT


def test_all_generator_contracts_share_mechanism_first_art_direction():
    for prompt in (PLAN_PROMPT, VISUAL_PROMPT, PROMPT):
        assert ART_DIRECTION in prompt
    assert 'Não há cota' in ART_DIRECTION
    assert 'vista ampliada' in ART_DIRECTION
    assert 'Nunca invente precisão' in ART_DIRECTION


def test_brief_is_subject_independent_and_never_changes_rule_data():
    for subject in ('Pilares protéticos', 'Engrenagens', 'Tempestades', 'Negociação'):
        data = {'title': subject, 'experience': {'complexity': 'advanced', 'visualStyle': 'illustrated', 'learningFocus': subject},
                'variables': [{'id': 'stage', 'initial': 0}], 'actions': [{'id': 'next', 'effects': {'stage': 1}}]}
        plan = {'focus': subject, 'objects': [
            {'id': 'subject', 'label': subject, 'layer': 'subject', 'features': ['Silhueta e partes'], 'explanation': 'Relação visível'},
            {'id': 'background', 'label': 'Ambiente', 'layer': 'background'}]}
        before = copy.deepcopy((data, plan))
        brief = illustration_brief(data, subject, plan)
        assert brief['learningFocus'] == subject
        assert brief['semanticObjects'][0]['label'] == subject
        assert len(brief['semanticObjects']) == 1
        assert (data, plan) == before
        assert not {'actions', 'variables', 'template'} & brief.keys()


def test_technical_style_is_preserved_and_missing_optional_fields_are_safe():
    assert illustration_brief({'experience': {'visualStyle': 'technical'}}, 'Circuito')['visualStyle'] == 'technical'
    assert illustration_brief({}, 'Assunto novo')['version'] == 'mechanism-first-v1'
