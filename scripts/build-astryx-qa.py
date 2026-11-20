"""Build only local demo artifacts with production exporters; never touches DB."""
import asyncio
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from models import Project
from services.astryx_prototype import AstryxContent, prototype_project
from services.html_exporter import generate_standalone_html
from services.scorm_exporter import export_scorm_package
from services.single_page_exporter import generate_single_page_html
from services.scorm_single_page_exporter import export_single_page_scorm_package


async def main():
    out = ROOT.parents[1] / 'outputs' / 'astryx-prototype'
    out.mkdir(parents=True, exist_ok=True)
    p = prototype_project(AstryxContent())
    (out / 'project.json').write_text(json.dumps(p, ensure_ascii=False), encoding='utf-8')
    for i, slide in enumerate(p['course']['slides']):
        (out / f'slide-{i}.html').write_text(slide['elements'][0]['htmlContent'], encoding='utf-8')
    await generate_standalone_html(p, str(out), output_path=str(out / 'Prototipo_Astryx.html'))
    for label, fn in [('scorm', export_scorm_package), ('scorm-single', export_single_page_scorm_package)]:
        folder = out / label
        folder.mkdir(exist_ok=True)
        archive = fn(Project(**p) if label == 'scorm' else p, str(out), str(folder))
        # Extract only our locally generated package, not a user archive.
        with zipfile.ZipFile(archive) as z:
            z.extractall(folder)
    (out / 'Pagina_Unica.html').write_text(generate_single_page_html(p, str(out)), encoding='utf-8')
    print(json.dumps({'path': str(out), 'slides': len(p['course']['slides']), 'dbWrites': 0, 'paidCalls': 0}))


if __name__ == '__main__':
    asyncio.run(main())
