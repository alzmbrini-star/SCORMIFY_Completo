"""Shared bounded navigation chrome for HTML and classic SCORM exports."""
from pathlib import Path


def install_navigation_window(html):
    if 'id="scormify-navigation-window"' in html:
        return html
    assets = Path(__file__).parent / 'export_assets'
    css = (assets / 'navigation-window.css').read_text(encoding='utf-8')
    script = (assets / 'navigation-window.js').read_text(encoding='utf-8')
    return html.replace('</head>', '<style id="scormify-navigation-window">'+css+'</style>\n<script>'+script+'</script>\n</head>', 1)
