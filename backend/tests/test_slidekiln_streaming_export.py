import base64
import re
from services.slidekiln import inline_module_assets, module_html, runtime_document
from services.export_media_stream import CURRENT, MediaStream


def test_large_nested_module_stays_compact_and_expands_exact_bytes(tmp_path):
    project_id='150826df-0a9a-4b16-acaa-d675b7fffbe9'
    filename='a'*32+'.sk.html'
    payload=base64.b64encode(b'original image bytes'*200000).decode('ascii')
    document='<html><head></head><body><img src="data:image/png;base64,'+payload+'"><p>Âncora 🎓</p></body></html>'
    path=tmp_path/filename
    path.write_text(document,encoding='utf-8')
    stream=MediaStream();token=CURRENT.set(stream)
    try:
        host=inline_module_assets(module_html(project_id,filename),str(tmp_path))
        assert len(host)<5000
        output=tmp_path/'offline.html'
        stream.write(output,host)
        expanded=output.read_text(encoding='utf-8')
        encoded=re.search(r'data-sk-src="data:text/html;base64,([A-Za-z0-9+/=]+)"',expanded)[1]
        assert base64.b64decode(encoded).decode('utf-8')==runtime_document(document)
        assert path.read_text(encoding='utf-8')==document
    finally:
        CURRENT.reset(token);stream.close()


def test_non_streaming_export_keeps_offline_package(tmp_path):
    filename='b'*32+'.sk.html'
    (tmp_path/filename).write_text('<html><body>Original</body></html>',encoding='utf-8')
    result=inline_module_assets(module_html('150826df-0a9a-4b16-acaa-d675b7fffbe9',filename),str(tmp_path))
    assert 'data-sk-src="data:text/html;base64,' in result
    assert '/assets/'+filename not in result
