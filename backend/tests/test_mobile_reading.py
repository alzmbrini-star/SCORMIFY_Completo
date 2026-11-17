import copy
from pathlib import Path
from services.single_page_exporter import generate_single_page_html

def project():
    return {'id':'reading','name':'Leitura mobile','enableVlibras':False,'course':{'slides':[
      {'id':'cover','title':'Introdução ao Trabalho em Equipe','background':'#121417','elements':[{'type':'html','htmlContent':'<div data-course-cover="2"><p style="font-size:19px">Aprenda • pratique • transforme</p><h1 style="font-size:77px;overflow-wrap:anywhere">Introdução ao Trabalho em Equipe</h1><p style="font-size:30px">O conteúdo original continua completo.</p></div>'}]},
      {'id':'journey','title':'Sua jornada','background':'#121417','elements':[{'type':'html','htmlContent':'<div data-course-journey="1"><ol style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr))"><li style="display:flex;font-size:28px"><strong>01</strong><span>Conceito e Importância do Trabalho em Equipe</span></li></ol></div>'}]},
      {'id':'lesson','title':'Conceito','background':'#121417','elements':[{'type':'html','htmlContent':'<div data-agent-copy-version="2"><span style="font-size:xx-large">Trabalhar em equipe permite reunir perspectivas e competências.</span></div>'}]},
      {'id':'native','title':'Texto nativo','elements':[{'type':'text','content':'Título grande','style':{'fontSize':77}},{'type':'text','content':'Explicação completa','style':{'fontSize':30}}]},
      {'id':'app','title':'Atividade preservada','elements':[{'type':'html','htmlContent':'<html><body><button onclick="this.textContent=\'ok\'">Responder</button></body></html>'}]}
    ]}}

def test_reading_classes_keep_source_and_desktop_sizes_in_both_exports():
    source=project();before=copy.deepcopy(source)
    for scorm in [False,True]:
        html=generate_single_page_html(source,'/none',scorm_mode=scorm)
        assert 'sp-html sp-reading-block' in html
        assert 'font-size:77px' in html and 'font-size:30px' in html
        assert 'data-reading-role="heading"' in html and 'data-reading-role="body"' in html
        assert 'Conceito e Importância do Trabalho em Equipe' in html
        assert 'data:text/html;charset=utf-8;base64' in html
    assert source==before

def test_mobile_rules_are_scoped_to_flowing_teaching_blocks_not_apps_or_overlays():
    css=(Path(__file__).resolve().parents[1]/'services/export_assets/portrait-view.css').read_text(encoding='utf-8')
    mobile=css.split('@media(max-width:768px) and (orientation:portrait){')[1]
    assert '.sp-section-body>.sp-reading-block h1{font-size:clamp(26px,7vw,32px)!important}' in mobile
    assert 'grid-template-columns:minmax(0,1fr)!important' in mobile
    assert 'white-space:nowrap!important;font-size:20px' in mobile
    assert 'word-break:normal!important;overflow-wrap:break-word!important' in mobile
    assert '.sp-bg-element h1' not in mobile and '.sp-quiz h1' not in mobile

def test_header_label_remains_distinct_from_body_copy():
    source={'id':'p','course':{'slides':[{'id':'s','elements':[{'type':'html','htmlContent':'<div style="display:flex;align-items:center"><span>Conceito e Importância do Trabalho em Equipe</span><span>Contexto</span></div>'}]}]}}
    result=generate_single_page_html(source,'/none')
    assert 'sp-reading-block sp-reading-label' in result
