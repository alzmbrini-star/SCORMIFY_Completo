"""Regression test: vídeos com URL HeyGen no Single Page export devem ser
renderizados como `.sp-avatar-wrap` com fundo TRANSPARENTE — não como
`.sp-video sp-interactive` (que tem card amarelo + background:#000 no <video>).

Avatares HeyGen são entregues como WebM com canal alpha. Para que se
misturem com o background do slide (especialmente no Single Page mode), o
container e o <video> devem ter background transparente.
"""
from services.single_page_exporter import (
    _is_heygen_avatar_url,
    _render_video_element_inner,
    generate_single_page_html,
)


def test_heygen_url_detection():
    assert _is_heygen_avatar_url("https://resource2.heygen.ai/aws_pacific/avatar_tmp/abc.webm")
    assert _is_heygen_avatar_url("https://app.heygen.com/foo.mp4")
    assert _is_heygen_avatar_url("HEYGEN.AI/upper.mp4")  # case-insensitive
    assert not _is_heygen_avatar_url("")
    assert not _is_heygen_avatar_url("https://example.com/video.mp4")
    assert not _is_heygen_avatar_url("https://cdn.youtube.com/embed/x")


def test_heygen_video_renders_as_avatar_wrap():
    el = {"type": "video", "src": "https://resource2.heygen.ai/aws_pacific/avatar_tmp/abc.webm"}
    html = _render_video_element_inner(el, "p1", "/tmp", "/api/projects/p1/media", 0)
    assert "sp-avatar-wrap" in html
    assert "sp-video sp-interactive" not in html
    assert "background:transparent" in html
    assert "data-required=\"true\"" in html


def test_plain_video_keeps_yellow_card():
    el = {"type": "video", "src": "https://example.com/video.mp4"}
    html = _render_video_element_inner(el, "p1", "/tmp", "/api/projects/p1/media", 0)
    assert "sp-video sp-interactive" in html
    assert "sp-avatar-wrap" not in html


def test_heygen_avatar_in_full_export_has_transparent_css():
    """E2E: gera Single Page completo com slide contendo avatar HeyGen e
    valida que o CSS gerado override `background` do <video> com transparent."""
    project = {
        "id": "test-avatar",
        "name": "Test Avatar",
        "course": {
            "title": "Test",
            "slides": [
                {
                    "id": "s1",
                    "title": "Apresentação",
                    "background": "#ffffff",
                    "elements": [
                        {
                            "type": "video",
                            "src": "https://resource2.heygen.ai/avatar_tmp/x.webm",
                        }
                    ],
                }
            ],
        },
    }
    html = generate_single_page_html(project, assets_dir="/tmp", base_url="")
    # The avatar wrapper appears in DOM
    assert 'class="sp-avatar-wrap"' in html
    # CSS override for the avatar transparent background is in the generated style block
    assert ".sp-avatar-wrap video{background:transparent !important}" in html
    # Yellow card CSS for `.sp-interactive` should NOT be applied to the avatar wrap
    # (verify the avatar wrap doesn't get the sp-interactive class)
    avatar_block = html.split('class="sp-avatar-wrap"')[1].split("</div>")[0]
    assert "sp-interactive" not in avatar_block


def test_section_completion_includes_avatar_wrap():
    """A regra de gating (`isSectionComplete`) usa seletor [data-required="true"]
    — não `.sp-interactive[data-required="true"]` — para que o avatar
    (que NÃO usa sp-interactive) ainda gateie a próxima seção."""
    project = {
        "id": "test",
        "name": "Test",
        "course": {"slides": [{"id": "s1", "title": "x", "elements": []}]},
    }
    html = generate_single_page_html(project, assets_dir="/tmp", base_url="")
    # JS runtime selector should be the relaxed version
    assert "$$('[data-required=\"true\"]', sec)" in html
    # And NOT the old strict one
    assert ".sp-interactive[data-required=\"true\"]" not in html.split("<script")[1]
