from pathlib import Path
from services.creator_guide import topics_for


def test_retired_tutorial_action_is_not_mounted_or_imported():
    source=(Path(__file__).resolve().parents[2]/'frontend/src/pages/Dashboard.jsx').read_text(encoding='utf-8')
    for removed in ['TutorialImportDialog','showTutorialImport','tutorial-import-btn','Importar Tutorial']:
        assert removed not in source
    for retained in ['GammaCreateDialog','Import PPT','New Project','ai-agent-btn']:
        assert retained in source


def test_tutor_does_not_recommend_retired_tutorial_action():
    entry=next(item for item in topics_for({'roles':['editor']}) if item['id']=='import')
    text=' '.join(entry['steps'])
    assert 'foi retirada do painel' in text
    assert 'sem exclusão ou alteração' in text
    assert 'Importar PPT' in text
