"""Offline presentation fixtures; no accounts, AI, or saved courses touched."""
import base64
import copy
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.single_page_exporter import generate_single_page_html
from services.html_exporter import generate_html_template
from services.scorm_exporter import export_scorm_package
from models import Project
from zipfile import ZipFile

def build(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    svg='''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><rect width="1280" height="720" fill="#dbeafe"/><rect x="8" y="8" width="1264" height="704" rx="20" fill="none" stroke="#0f172a" stroke-width="16"/><text x="55" y="100" font-size="40" font-family="Arial" fill="#0f172a">SLIDE INTEIRO — SEM CORTES</text><rect x="50" y="170" width="340" height="400" fill="#14b8a6"/><rect x="470" y="170" width="340" height="400" fill="#3b82f6"/><rect x="890" y="170" width="340" height="400" fill="#f59e0b"/><g fill="#0f172a" font-size="34" font-family="Arial"><text x="80" y="370">INÍCIO</text><text x="515" y="370">PROCESSO</text><text x="940" y="370">RESULTADO</text><text x="50" y="650">Borda esquerda</text><text x="940" y="650">Borda direita</text></g></svg>'''
    image='data:image/svg+xml;base64,'+base64.b64encode(svg.encode()).decode()
    questions=[{'id':'question','text':'O que deve ser preservado em retrato?','alternatives':[{'text':'A imagem inteira e as interações','isCorrect':True},{'text':'Somente o centro da imagem','isCorrect':False}],'explanation':'A imagem inteira mantém o contexto.'}]
    course={'metadata':{'title':'Verificação de retrato'},'slides':[
       {'id':'image','title':'Conteúdo visual preservado','order':0,'width':1280,'height':720,'gammaSource':True,'backgroundImage':image,'elements':[]},
       {'id':'quiz','title':'Quiz tradicional preservado','order':1,'width':1280,'height':720,'elements':[{'id':'q','type':'quiz','x':50,'y':80,'width':1180,'height':560,'quizConfig':{'title':'Conferência','questionIds':['question'],'passingScore':70}}]},
       {'id':'interactive','title':'Interação com imagem preservada','order':2,'width':1280,'height':720,'elements':[{'id':'i','type':'html','x':0,'y':0,'width':1280,'height':720,'htmlDisplayMode':'responsive','htmlContent':'<!DOCTYPE html><html lang="pt-BR"><meta name="viewport" content="width=device-width, initial-scale=1"><body style="font:18px system-ui;background:#e0f2fe;padding:16px"><h2>Avaliação com imagem</h2><img style="width:100%;height:auto" src="'+image+'" alt="Processo completo"><p>Selecione para confirmar que a interação funciona.</p><button style="min-height:44px" onclick="this.textContent=\'Resposta confirmada\'">Confirmar resposta</button></body></html>'}]}
    ]}
    project={'id':'portrait-offline','name':'Verificação de retrato','ownerId':'test','enableVlibras':False,'course':course}
    original=copy.deepcopy(project)
    for scorm,name in [(False,'single-page.html'),(True,'single-page-scorm.html')]:
        (destination/name).write_text(generate_single_page_html(project,str(destination),questions=questions,scorm_mode=scorm),encoding='utf-8')
    traditional=copy.deepcopy(course);traditional['questions']=questions
    (destination/'traditional.html').write_text(generate_html_template('Verificação de retrato',traditional,1280,720,False),encoding='utf-8')
    package=export_scorm_package(Project(**project),str(destination/'scorm'),str(destination),questions=questions)
    with ZipFile(package) as archive:archive.extractall(destination/'scorm-open')
    assert project==original
    (destination/'index.html').write_text('<html lang="pt-BR"><meta name="viewport" content="width=device-width,initial-scale=1"><h1>Verificação de retrato</h1>'+''.join('<p><a href="'+path+'">'+label+'</a></p>' for path,label in [('single-page.html','HTML Página Única'),('single-page-scorm.html','SCORM Página Única'),('traditional.html','HTML Slides'),('scorm-open/index.html','SCORM Slides')])+'</html>',encoding='utf-8')
    print(json.dumps({'output':str(destination),'sourcePreserved':project==original,'slides':len(course['slides'])}))

if __name__=='__main__':build(sys.argv[1])
