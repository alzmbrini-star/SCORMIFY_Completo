from pathlib import Path
import subprocess
import zipfile
from services.creator_guide import topics_for


def test_scorm_navigation_uses_real_assessment_completion():
    script = Path(__file__).with_name('scorm_navigation_completion.cjs')
    result = subprocess.run(['node', str(script)], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr


def test_tutor_explains_pending_quiz_indicator_and_export_limit():
    topic = next(t for t in topics_for({'role':'editor', 'user_id':'test'}) if t['id']=='export')
    instructions = ' '.join(topic['steps'])
    for phrase in ['Quiz pendente', 'Quiz concluído', 'não aprovação', 'Reexporte o ZIP', 'sem nota']:
        assert phrase in instructions
    for phrase in ['Somente pendentes', 'não avança slides', 'Página Única']:
        assert phrase in instructions


def test_exported_zip_ships_assessment_aware_navigation(tmp_path):
    from models import Project
    from services.scorm_exporter import export_scorm_package
    project = Project(name='Navegação de avaliações', enableVlibras=False, course={'slides':[
        {'id':'s1', 'title':'Quiz', 'elements':[{'id':'q1', 'type':'quiz', 'quizConfig':{'questionIds':[]}}]},
        {'id':'s2', 'title':'Conclusão', 'elements':[]},
    ]})
    output = export_scorm_package(project, str(tmp_path/'storage'), str(tmp_path/'exports'))
    with zipfile.ZipFile(output) as package:
        player = package.read('scripts/player.js').decode('utf-8')
        page = package.read('index.html').decode('utf-8')
    assert 'function slideCompletionState(index)' in player
    assert '⚠ Quiz pendente' in player
    assert 'applySidebarStatus(status, index)' in player
    assert '.sidebar-slide-status.quiz-pending' in page
    assert '.progress-dot.quiz-pending' in page
    assert 'id="sidebar-pending-only"' in page
    assert 'Somente pendentes' in page
    assert '.sidebar-slide-item[hidden]' in page
    assert 'function applyPendingSlideFilter()' in player
