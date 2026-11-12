import copy
from services.ai_agent import (_slide_plain_text, _fallback_content_parts,
    _build_infographic_fallback_html, _infographic_html_needs_repair,
    _normalize_interactive_storyboard_slide, _interactive_html_is_functional)
from services.teaching_copy import visible_teaching_text


def test_css_html_and_script_comments_never_become_visible_fallback_concepts():
    raw='<p>Compartilhar conhecimentos amplia o repertório da equipe.</p> /* Infographic structure and animations */ <!-- Production layout --> <style>.x{color:red}</style><script>const secret="production";</script><p>Responsabilidades claras ajudam a coordenar entregas.</p>'
    clean=visible_teaching_text(raw)
    assert 'Compartilhar conhecimentos' in clean and 'Responsabilidades claras' in clean
    for leaked in ('Infographic','Production','production','color:red','/*','<!--'):assert leaked not in clean
    slide={'title':'Benefícios da colaboração','type':'infographic','elements':[{'type':'html','htmlContent':raw}],
           'notes':'Encoraje-os a compartilhar experiências pessoais ou observações.',
           'narrationScript':'A comunicação permite compartilhar informações relevantes para o objetivo comum.'}
    before=copy.deepcopy(slide)
    parts=_fallback_content_parts(slide)
    assert not any('Encoraje-os' in part or 'Infographic' in part for part in parts)
    assert any('Compartilhar conhecimentos' in part for part in parts)
    html=_build_infographic_fallback_html(slide)
    assert 'Infographic structure and animations' not in html
    assert 'Encoraje-os' not in html
    assert _interactive_html_is_functional(html,'infographic')
    assert slide==before


def test_old_compiled_infographic_comment_is_detected_and_useful_cards_preserved():
    slide={'title':'Benefícios da colaboração','type':'infographic','body':
           'Compartilhar conhecimentos amplia o repertório da equipe. Responsabilidades claras ajudam a coordenar entregas. Perspectivas diferentes apoiam decisões mais fundamentadas.'}
    generated=_build_infographic_fallback_html(slide)
    bad=generated.replace('Compartilhar conhecimentos amplia o repertório da equipe.', '/* Infographic structure and animations */')
    assert _infographic_html_needs_repair(bad)
    repaired=_normalize_interactive_storyboard_slide({'title':slide['title'],'type':'infographic','elements':[{'type':'html','htmlContent':bad}]})['elements'][0]['htmlContent']
    assert '/* Infographic' not in repaired
    assert 'Responsabilidades claras ajudam' in repaired
    assert not _infographic_html_needs_repair(repaired)


def test_code_examples_are_not_executed_or_rewritten_in_the_original_slide():
    slide={'title':'Comentários CSS','elements':[{'type':'html','content':'<p>Use comentários para documentar o código.</p><pre><code>/* exemplo didático */</code></pre>'}]}
    before=copy.deepcopy(slide)
    assert 'exemplo didático' not in _slide_plain_text(slide)
    assert slide==before
