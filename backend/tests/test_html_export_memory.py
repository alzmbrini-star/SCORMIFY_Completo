import ast
import asyncio
import base64
import copy
import io
import json
import logging
import os
from pathlib import Path
import sys
import tracemalloc
import zipfile
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.html_exporter import generate_standalone_html, generate_html_template, file_to_base64, url_to_base64
from services.streaming_html import JsonArraySpool, write_json, write_html_file, COURSE_MARKER
from services.video_quiz import build_video_quiz


def payload(document):
    raw = document.split('var courseData = ', 1)[1]
    return json.JSONDecoder().raw_decode(raw)[0]


def test_streaming_json_preserves_unicode_scripts_and_chunk_boundaries():
    value={'x':('ç😀"\\\n' * 15000) + '</sCrIpT><script>bad()</script>\u2028', 'array':[True,None,3.5]}
    target=io.StringIO();write_json(target,value)
    assert json.loads(target.getvalue()) == value
    assert '<' not in target.getvalue()


def test_file_encoding_preserves_chunk_boundaries(tmp_path):
    data=bytes(range(256))*2001
    path=tmp_path/'asset.webm';path.write_bytes(data)
    assert base64.b64decode(file_to_base64(str(path)).split(',',1)[1]) == data


def test_remote_encoding_streams_instead_of_buffering_response(monkeypatch):
    data=b'abcdefghijk'*30001
    class Response:
        status_code=200
        headers={'content-type':'video/webm; charset=binary'}
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def aiter_bytes(self,chunk_size):
            for offset in range(0,len(data),10001): yield data[offset:offset+10001]
    class Client:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        def stream(self,*args): return Response()
    monkeypatch.setattr('services.html_exporter.httpx.AsyncClient',Client)
    result=asyncio.run(url_to_base64('https://example.org/video.webm'))
    assert result.startswith('data:video/webm;base64,')
    assert base64.b64decode(result.split(',',1)[1]) == data


def test_streamed_export_preserves_both_questions_transparency_and_input(tmp_path):
    config, widget=build_video_quiz({'title':'Vídeo','src':'https://example.org/alpha.webm','preserveTransparency':True,
      'checkpoints':[{'at':n,'question':f'Pergunta {n}?','options':['Sim','Não'],'correctIndex':0,'explanation':'Por isso.','maxAttempts':2} for n in (5,12)]})
    project={'id':'p','name':'Teste','enableVlibras':False,'course':{'metadata':{'title':'Curso'},'slides':[
      {'id':'s','width':960,'height':540,'elements':[{'id':'e','type':'html','htmlContent':widget,'videoQuizConfig':config,'x':12,'startTime':2}]}]}}
    before=copy.deepcopy(project)
    path=tmp_path/'course.html'
    result=asyncio.run(generate_standalone_html(project,str(tmp_path),output_path=str(path)))
    assert result == str(path)
    data=payload(path.read_text(encoding='utf-8'))
    element=data['slides'][0]['elements'][0]
    assert len(element['videoQuizConfig']['checkpoints']) == 2
    assert element['videoQuizConfig']['preserveTransparency'] is True
    assert 'video-quiz-playback-v2' in element['htmlContent']
    assert element['x'] == 12 and element['startTime'] == 2
    assert '</script>' in element['htmlContent']
    assert project == before
    legacy=payload(asyncio.run(generate_standalone_html(project,str(tmp_path))))
    assert base64.b64decode(legacy['slides'][0]['elements'][0]['htmlContent'][8:]).decode() == element['htmlContent']


def test_embedded_images_stay_offline_and_slides_spool_to_disk(tmp_path):
    image=tmp_path/'figure.png';image.write_bytes(b'png-fixture')
    project={'id':'p','enableVlibras':False,'course':{'slides':[
      {'id':str(i),'elements':[{'type':'image','src':'/api/projects/p/assets/figure.png'}]} for i in range(3)]}}
    target=tmp_path/'images.html'
    asyncio.run(generate_standalone_html(project,str(tmp_path),output_path=str(target)))
    data=payload(target.read_text(encoding='utf-8'))
    for slide in data['slides']:
        assert base64.b64decode(slide['elements'][0]['src'].split(',',1)[1]) == b'png-fixture'


def test_large_payload_serialization_has_bounded_extra_memory(tmp_path):
    # Input allocated before tracing: measure *additional* memory during export.
    document='<p>'+('x'* (24*1024*1024))+'</p>'
    course={'metadata':{},'slides':[{'elements':[{'type':'html','htmlContent':document}]}]}
    tracemalloc.start()
    try:
        generate_html_template('Large',course,960,540,False,output_path=str(tmp_path/'large.html'))
        _,peak=tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 8*1024*1024, f'Unexpected extra allocation: {peak}'
    assert (tmp_path/'large.html').stat().st_size > 24*1024*1024
    assert course['slides'][0]['elements'][0]['htmlContent'] is document


def test_spool_and_atomic_output_cleanup_on_failure(tmp_path):
    with JsonArraySpool() as slides:
        slides.append({'x':'a'});slides.append({'x':'b'})
        target=io.StringIO();write_json(target,slides)
        assert json.loads(target.getvalue()) == [{'x':'a'},{'x':'b'}]
    assert slides.file.closed
    destination=tmp_path/'safe.html';destination.write_text('original')
    with pytest.raises(TypeError):
        write_html_file(destination,COURSE_MARKER,{'unsupported':object()})
    assert destination.read_text() == 'original'
    assert not list(tmp_path.glob('*.part'))


def test_gridfs_upload_receives_file_not_a_full_bytes_copy(tmp_path):
    # Execute the exact route helper without booting app/database integrations.
    source=Path(__file__).resolve().parents[1]/'routes/export.py'
    tree=ast.parse(source.read_text(encoding='utf-8'))
    function=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='save_export_to_gridfs')
    class Cursor:
        def __aiter__(self): return self
        async def __anext__(self): raise StopAsyncIteration
    class Bucket:
        def find(self, query): return Cursor()
        async def upload_from_stream(self,name,stream):
            assert hasattr(stream,'fileno') and not isinstance(stream,io.BytesIO)
            assert stream.read(4)==b'data'
            self.stream=stream
    bucket=Bucket();namespace={'exports_bucket':bucket,'logger':logging.getLogger('test'),'os':os,'io':io}
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),namespace)
    path=tmp_path/'file.html';path.write_bytes(b'data')
    asyncio.run(namespace['save_export_to_gridfs'](str(path),'file.html'))
    assert bucket.stream.closed


def test_scorm_zip_streams_video_and_keeps_question_config(tmp_path,monkeypatch):
    from models import Project
    from services.scorm_exporter import export_scorm_package
    config,widget=build_video_quiz({'src':'https://example.org/alpha.webm','preserveTransparency':True,
       'checkpoints':[{'at':n,'question':f'Pergunta {n}','options':['A','B'],'correctIndex':0,'explanation':'A','maxAttempts':2} for n in (3,8)]})
    original=b'original-transparent-webm\x00'*20000
    class Response:
        status_code=200
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def iter_bytes(self,chunk_size):
            for i in range(0,len(original),chunk_size): yield original[i:i+chunk_size]
    class Client:
        def __init__(self,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def stream(self,*args): return Response()
    monkeypatch.setattr('services.scorm_exporter.httpx.Client',Client)
    project=Project(id='memory-scorm',name='Test',ownerId='u',enableVlibras=False,course={'metadata':{'title':'Test'},'slides':[
       {'id':'s','title':'Slide','order':0,'elements':[
           {'id':'v','type':'video','src':'https://resource2.heygen.ai/fixture.webm','x':0,'y':0,'width':500,'height':400},
           {'id':'q','type':'html','htmlContent':widget,'videoQuizConfig':config,'x':0,'y':0,'width':960,'height':540}]}]})
    result=export_scorm_package(project,str(tmp_path),str(tmp_path))
    with zipfile.ZipFile(result) as package:
        assert package.testzip() is None
        assert 'imsmanifest.xml' in package.namelist()
        course=json.loads(package.read('course.json'))
        video,quiz=course['slides'][0]['elements']
        assert package.read(video['src']) == original
        assert quiz['videoQuizConfig']['preserveTransparency'] is True
        assert len(quiz['videoQuizConfig']['checkpoints']) == 2
        assert not any(name.endswith('.part') for name in package.namelist())


def test_scorm_large_json_serializes_with_bounded_extra_memory(tmp_path):
    from models import Project
    from services.scorm_exporter import export_scorm_package
    project=Project(id='scorm-large',name='Large',ownerId='u',enableVlibras=False,course={'metadata':{'title':'Large'},'slides':[
       {'id':'s','title':'Slide','order':0,'elements':[{'id':'h','type':'html','htmlContent':'<p>'+'x'*(24*1024*1024)+'</p>','x':0,'y':0,'width':960,'height':540}]}]})
    tracemalloc.start()
    try:
        result=export_scorm_package(project,str(tmp_path),str(tmp_path))
        _,peak=tracemalloc.get_traced_memory()
    finally: tracemalloc.stop()
    assert peak < 40*1024*1024, f'Unexpected SCORM extra allocation: {peak}'
    with zipfile.ZipFile(result) as package:
        assert package.getinfo('course.json').file_size > 24*1024*1024
        assert package.testzip() is None
