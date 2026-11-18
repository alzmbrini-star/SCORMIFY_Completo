import ast
from pathlib import Path


def test_dashboard_projection_retains_only_one_slide_and_inherited_geometry_without_writes():
    source=(Path(__file__).resolve().parents[1]/'routes/projects_crud.py').read_text(encoding='utf-8')
    tree=ast.parse(source)
    endpoint=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and any(
        isinstance(d,ast.Call) and d.args and isinstance(d.args[0],ast.Constant) and d.args[0].value=='/projects'
        and isinstance(d.func,ast.Attribute) and d.func.attr=='get' for d in n.decorator_list))
    text=ast.get_source_segment(source,endpoint)
    assert '"width": "$course.width"' in text and '"height": "$course.height"' in text
    assert '"$slice"' in text and '"$size"' in text
    assert 'has_role(user, "super_admin")' in text and '"$match": {"companyId": user_company}' in text
    assert not any(token in text for token in ('update_one(', 'insert_one(', 'delete_one('))


def test_tutor_documents_real_cover_static_limits_and_no_course_mutation():
    from services.creator_guide import GUIDE
    topic=next(t for t in GUIDE if t['id']=='dashboard-course-covers')
    text=' '.join(topic['steps'])
    for word in ('Gamma','Agente','primeiro slide','sem scripts','créditos','HTML/SCORM','não salva alterações'):
        assert word in text
    assert topic['target']=='dashboard'
