"""Offline QA only: build synthetic slides and a fake LMS, never call an AI API."""
import asyncio
import base64
import json
import runpy
import sys
import zipfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parents[1]))
from services.html_exporter import generate_standalone_html
from services.scorm_exporter import export_scorm_package
from models import Project


def main():
    root=Path(__file__).parents[1]/'storage/guided_qa_20261111'
    root.mkdir(parents=True,exist_ok=True)
    course=runpy.run_path(str(Path(__file__).parents[1]/'tests/test_guided_path.py'))['sample_course']()
    illustration='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 450"><rect width="800" height="450" fill="#dcefeb"/><circle cx="650" cy="95" r="48" fill="#c1e1d7"/><rect x="110" y="85" width="580" height="280" rx="24" fill="#fff"/><rect x="310" y="65" width="180" height="40" rx="12" fill="#19675b"/><path d="M180 175h210M180 240h350M180 305h270" stroke="#99c4b8" stroke-width="16" stroke-linecap="round"/><circle cx="600" cy="290" r="38" fill="#d99b46"/></svg>'
    url='data:image/svg+xml;base64,'+base64.b64encode(illustration.encode()).decode()
    for s in course['slides']:
        if s['id']=='original':s['elements']=[{'id':'original-image','type':'image','src':url,'x':160,'y':80,'width':1600,'height':660}]
        if s['id']=='lesson':s['elements'][0].update(content='<h1>Planejar antes de executar</h1><p>A preparação permite reconhecer condições e organizar recursos. Execute o plano e confira os resultados antes de dar a atividade por concluída.</p>',style={'fontSize':40,'fontColor':'#153e35'})
        for e in s['elements']:
            if e.get('assessmentConfig'):
                for q in e['assessmentConfig']['questions']:q.update(media={'kind':'image','url':url,'name':'Imagem de teste: ambiente de planejamento'},imageGenerationStatus='ready')
    from services.assessment_renderer import refresh_assessment_documents
    refresh_assessment_documents({'course':course})
    project={'id':'guided-offline-demo','name':'Percurso guiado — teste local','enableVlibras':False,'course':course}
    asyncio.run(generate_standalone_html(project,str(root),output_path=str(root/'percurso.html')))
    package=export_scorm_package(Project(**project),str(root/'storage'),str(root/'exports'))
    with zipfile.ZipFile(package) as archive:archive.extractall(root/'scorm')
    harness='''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>SCORMIFY · teste local do percurso</title><style>body{margin:0;font:14px system-ui;background:#f3f8f5}#result{padding:8px 16px}iframe{border:0;width:100%;height:calc(100vh - 38px)}</style></head><body><div id="result">LMS de teste · aguardando aluno</div><script>var values={'cmi.student_data.mastery_score':'80','cmi.core.student_id':'offline-student','cmi.core.lesson_status':'not attempted'};window.API={LMSInitialize:()=> 'true',LMSGetValue:k=>values[k]||'',LMSSetValue:(k,v)=>{values[k]=v;document.getElementById('result').textContent='LMS de teste · '+values['cmi.core.lesson_status']+' · Nota: '+(values['cmi.core.score.raw']||'não enviada');return 'true';},LMSCommit:()=> 'true',LMSFinish:()=> 'true',LMSGetLastError:()=> '0',LMSGetErrorString:()=>'',LMSGetDiagnostic:()=>''};</script><iframe src="scorm/index.html" title="Percurso em teste"></iframe></body></html>'''
    (root/'teste-scorm.html').write_text(harness,encoding='utf-8')
    print(root)


if __name__=='__main__':main()
