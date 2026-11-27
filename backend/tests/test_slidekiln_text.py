import base64
import re
from services.slidekiln import runtime_document,inline_module_assets,module_html,MEDIA_KEYS
from services.slidekiln_text import TEXT_FLIP_CSS
from services.slidekiln_cover import build_cover


def sample():
    return '<html><head>'+MEDIA_KEYS+'</head><body><div id="stage" data-w="1280" data-h="720"><section class="slide active"><div id="text" class="shp" style="left:942px;width:173px;transform:scaleX(-1)"><div class="txt-l" style="transform:rotate(4deg)">ALVOS CERTOS</div><svg><path d="M0 0L10 10"/></svg></div><div class="shp" style="transform:rotate(30deg)"><div class="txt-l">Normal</div></div></section></div><script>window.__DECK__={"slides":[{"timeline":[{"target":"text","effect":"fade"}]}]}</script><img src="data:image/png;base64,AAAA"></body></html>'


def test_legacy_keyboard_patched_document_receives_text_fix_once():
    source=sample();fixed=runtime_document(source)
    assert fixed.count('id="sk-readable-text-flips-v1"')==1
    assert fixed.count('id="sk-media-keyboard-v1"')==1
    assert runtime_document(fixed)==fixed
    # Every shape, rotation, text run, media payload and animation remains exact.
    assert fixed.replace(TEXT_FLIP_CSS,'')==source
    assert 'scale:-1 1!important' in TEXT_FLIP_CSS
    assert 'scale:1 -1!important' in TEXT_FLIP_CSS
    assert 'scale:-1 -1!important' in TEXT_FLIP_CSS
    assert '>.txt-l' in TEXT_FLIP_CSS and 'transform:' not in TEXT_FLIP_CSS


def test_offline_export_copy_has_fix_but_asset_is_not_rewritten(tmp_path):
    filename='a'*32+'.sk.html';asset=tmp_path/filename
    source=sample();asset.write_text(source,encoding='utf-8')
    host=inline_module_assets(module_html('150826df-0a9a-4b16-acaa-d675b7fffbe9',filename),str(tmp_path))
    encoded=re.search('data:text/html;base64,([A-Za-z0-9+/=]+)',host)[1]
    assert TEXT_FLIP_CSS in base64.b64decode(encoded).decode('utf-8')
    assert asset.read_text(encoding='utf-8')==source


def test_passive_cover_also_keeps_readable_text_without_scripts(tmp_path):
    asset=tmp_path/'module.html';asset.write_text(sample(),encoding='utf-8')
    cover=build_cover(asset)['html']
    assert 'scale:-1 1!important' in cover and 'ALVOS CERTOS' in cover
    assert '<script' not in cover
    assert 'transform:scaleX(-1)' in cover and 'transform:rotate(4deg)' in cover
