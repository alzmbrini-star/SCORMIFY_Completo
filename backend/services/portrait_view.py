"""Read-time presentation enhancement shared by HTML and both SCORM players."""
from pathlib import Path

def install_portrait_view(document):
    if 'id="course-portrait-support"' in document:return document
    assets=Path(__file__).parent/'export_assets'
    css=(assets/'portrait-view.css').read_text(encoding='utf-8')
    js=(assets/'portrait-view.js').read_text(encoding='utf-8')
    document=document.replace('</head>','<style id="course-portrait-support">'+css+'</style></head>',1)
    # An authored HTML app can contain </body> inside the course JSON. Attach
    # our script to the outer document, never into that serialized content.
    before,closing,after=document.rpartition('</body>')
    return before+'<script>'+js+'</script>'+closing+after if closing else document
