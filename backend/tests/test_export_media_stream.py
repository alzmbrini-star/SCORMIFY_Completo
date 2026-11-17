import base64
import copy
import hashlib
import tracemalloc
from pathlib import Path
import pytest
from services.export_media_stream import CURRENT, MediaStream, encode_document
from services.single_page_exporter import generate_single_page_html


def test_nested_base64_is_byte_exact_and_bounded(tmp_path):
    raw = bytes(range(256)) * 8192
    asset = tmp_path / 'original.png'
    asset.write_bytes(raw)
    stream = MediaStream()
    token = CURRENT.set(stream)
    try:
        media = stream.file(asset)
        frame = encode_document('<h1>Prática ação</h1><img src="' + media + '">')
        text = '<iframe src="data:text/html;base64,' + frame + '"></iframe>'
        tracemalloc.start()
        stream.write(tmp_path / 'large.html', text * 40)
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        assert peak < 4 * 1024 * 1024
        expected = '<iframe src="data:text/html;base64,' + base64.b64encode(('<h1>Prática ação</h1><img src="data:image/png;base64,' + base64.b64encode(raw).decode() + '">').encode()).decode() + '"></iframe>'
        assert hashlib.sha256((tmp_path / 'large.html').read_bytes()).digest() == hashlib.sha256((expected * 40).encode()).digest()
    finally:
        CURRENT.reset(token)
    assert CURRENT.get() is None


@pytest.mark.parametrize('scorm', [False, True])
def test_output_path_preserves_scenarios_questions_frames_and_media(tmp_path, scorm):
    uri = 'data:image/png;base64,' + base64.b64encode(b'original image bytes').decode()
    local = tmp_path / 'scene.png'
    local.write_bytes(b'original scene bytes')
    url = '/api/projects/p/assets/scene.png'
    data = {'title': 'Decisão', 'context': 'Contexto original', 'imageUrl': url,
            'nodes': [{'id': str(i), 'narrative': 'Etapa ' + str(i), 'imageUrl': url, 'choices': [{'id': 'c', 'text': 'Decidir', 'next_node_id': str(i+1)}]} for i in range(7)]}
    project = {'id':'p','name':'Curso','enableVlibras':False,'course':{'slides':[
        {'id':'s1','title':'Imagem','elements':[{'type':'image','src':uri}]},
        {'id':'s2','title':'Cenário','elements':[{'type':'scenario','scenarioData':data}]},
        {'id':'s3','title':'Aplicativo','elements':[{'type':'html','htmlContent':'<html><body><img src="'+uri+'"><button>Responder</button></body></html>'}]},
        {'id':'s4','title':'Quiz','elements':[{'type':'quiz','quizConfig':{'title':'Verificação','questionIds':['q1']}}]},
    ]}}
    questions=[{'id':'q1','text':'Pergunta original','options':[{'text':'Sim','correct':True},{'text':'Não','correct':False}]}]
    before=copy.deepcopy(project)
    expected=generate_single_page_html(project,str(tmp_path),questions=questions,scorm_mode=scorm)
    path=tmp_path / 'actual.html'
    assert generate_single_page_html(project,str(tmp_path),questions=questions,scorm_mode=scorm,output_path=path)==str(path)
    assert path.read_text(encoding='utf-8')==expected
    assert project==before and CURRENT.get() is None
    assert '__SCORMIFY_' not in path.read_text(encoding='utf-8')


def test_failure_cleans_partial_and_resets_context(tmp_path):
    stream=MediaStream()
    token=stream.file(tmp_path/'missing.png')
    with pytest.raises(FileNotFoundError):
        stream.write(tmp_path/'output.html',token)
    assert not list(tmp_path.glob('*.partial-*'))
    assert not (tmp_path/'output.html').exists()


def test_assessment_and_pdf_remain_exact_with_streaming(tmp_path):
    import json
    from services.assessment_assets import inline_assessment_assets
    (tmp_path/'figure.png').write_bytes(b'figure original')
    (tmp_path/'doc.pdf').write_bytes(b'%PDF-original')
    widget='<head></head><script id="assessment-data">'+json.dumps({'questions':[{'text':'Original','image':{'url':'/api/projects/p/assets/figure.png'}}]})+'</script>'
    project={'id':'p','course':{'slides':[{'id':'s','elements':[
        {'type':'html','htmlContent':widget},
        {'type':'flipbook','flipbookType':'pdf','flipbookUrl':'/api/projects/p/assets/doc.pdf'},
    ]}]}}
    expected=generate_single_page_html(project,str(tmp_path))
    path=tmp_path/'actual.html'
    generate_single_page_html(project,str(tmp_path),output_path=path)
    assert path.read_text(encoding='utf-8')==expected


def test_concurrent_exports_are_isolated(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    def export(number):
        uri='data:image/png;base64,'+base64.b64encode(bytes([number])*100).decode()
        project={'id':'p','course':{'slides':[{'id':'s','elements':[{'type':'image','src':uri}]}]}}
        path=tmp_path/f'{number}.html'
        generate_single_page_html(project,str(tmp_path),output_path=path)
        assert uri in path.read_text(encoding='utf-8')
        assert CURRENT.get() is None
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(export,[1,2]))


def test_scorm_package_uses_streamed_file_and_valid_launch(tmp_path):
    from services.scorm_single_page_exporter import export_single_page_scorm_package
    import zipfile
    import xml.etree.ElementTree as ET
    project={'id':'p','name':'Curso','course':{'slides':[{'id':'s','title':'Original','elements':[]}]}}
    package=export_single_page_scorm_package(project,str(tmp_path),str(tmp_path))
    with zipfile.ZipFile(package) as archive:
        root=ET.fromstring(archive.read('imsmanifest.xml'))
        resource=root.find('.//{*}resource')
        assert resource.get('href')=='index.html'
        assert all(node.get('href') in archive.namelist() for node in resource.findall('{*}file'))
        document=archive.read('index.html').decode()
        assert 'scripts/scorm-api.js' in document and 'Original' in document
        assert '__SCORMIFY_' not in document
