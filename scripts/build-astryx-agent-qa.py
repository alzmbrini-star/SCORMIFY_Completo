"""Local-only mixed-course QA. No database, paid AI or saved course writes."""
import asyncio
import json
import runpy
import sys
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from PIL import Image
from models import Project
from services.html_exporter import generate_standalone_html
from services.scorm_exporter import export_scorm_package
from services.single_page_exporter import generate_single_page_html
from services.scorm_single_page_exporter import export_single_page_scorm_package


async def main():
    fixture=runpy.run_path(str(ROOT/'backend/tests/test_astryx_agent.py'))
    out=ROOT.parents[1]/'outputs'/'astryx-agent'
    out.mkdir(parents=True,exist_ok=True)
    for index,title in enumerate(fixture['THEMES']):
        folder=out/str(index)
        assets=folder/'astryx-local-only'/'assets'
        assets.mkdir(parents=True,exist_ok=True)
        Image.new('RGB',(400,220),(60,100,190)).save(assets/'docx_001_0123456789abcdef.png')
        course=await fixture['compile_course'](title)
        p={'id':'astryx-local-only','name':title,'enableVlibras':False,'course':course}
        (folder/'project.json').write_text(json.dumps(p,ensure_ascii=False),encoding='utf-8')
        for n,slide in enumerate(course['slides']):
            if len(slide['elements'])==1 and slide['elements'][0].get('astryxDesign'):
                (folder/f'slide-{n}.html').write_text(slide['elements'][0]['htmlContent'],encoding='utf-8')
        await generate_standalone_html(p,str(assets),questions=course['quizQuestions'],output_path=str(folder/'HTML.html'))
        (folder/'Pagina_Unica.html').write_text(generate_single_page_html(p,str(assets),questions=course['quizQuestions']),encoding='utf-8')
        for label,fn in [('scorm',export_scorm_package),('scorm-single',export_single_page_scorm_package)]:
            target=folder/label
            target.mkdir(exist_ok=True)
            package=fn(Project(**p) if label=='scorm' else p,str(folder),str(target),questions=course['quizQuestions'])
            with zipfile.ZipFile(package) as z:z.extractall(target)
    print(json.dumps({'output':str(out),'themes':fixture['THEMES'],'paidCalls':0,'databaseWrites':0}))


if __name__=='__main__':asyncio.run(main())
