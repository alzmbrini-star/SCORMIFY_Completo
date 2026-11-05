import base64
from services.text_density_analyzer import analyze_slide, _plain_element_text

def test_code_metadata_hidden_text_do_not_inflate_density():
    body='<h2>Riscos</h2><p>Use proteção individual adequada.</p>'
    noise='<head><title>Metadados</title><style>'+(' .x {color:blue} '*1000)+'</style></head><script>'+('const state=1; '*2000)+'</script><template>não visível</template><div hidden>Oculto</div><div style="display:none">Oculto</div>'
    plain=analyze_slide({'elements':[{'type':'html','htmlContent':body}]})
    full=analyze_slide({'elements':[{'type':'html','htmlContent':noise+body}]})
    assert plain['metrics']['words']==full['metrics']['words']==5
    assert plain['score']==full['score']

def test_base64_unicode_entities_comments_and_visible_svg_labels():
    html='<!--secret--><p>Água &amp; segurança</p><svg><text>Bomba</text></svg>'
    encoded='__B64__:'+base64.b64encode(html.encode()).decode()
    assert _plain_element_text({'htmlContent':encoded})==_plain_element_text({'htmlContent':html})
    assert 'secret' not in _plain_element_text({'htmlContent':html})
    assert analyze_slide({'elements':[{'type':'html','htmlContent':encoded}]})['metrics']['words']==3

def test_invalid_encoded_html_is_not_counted_as_thousands_of_words():
    assert _plain_element_text({'htmlContent':'__B64__:invalid!'})==''
