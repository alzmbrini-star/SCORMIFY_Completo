"""Offline fixtures matching desktop sizes in the reported course; no AI or DB."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.single_page_exporter import generate_single_page_html

def build(destination):
    titles=['Conceito e Importância do Trabalho em Equipe','Dinâmica do Trabalho em Equipe','Aplicação e Crescimento no Trabalho em Equipe']
    cover='<div data-course-cover="2" style="height:100%;overflow:auto;padding:12px 16px 12px 0;color:#f4f4f5;font-family:Arial"><p style="margin:0 0 28px;font-size:19px;letter-spacing:3px;text-transform:uppercase;color:#34d399;font-weight:700">Aprenda • pratique • transforme</p><h1 style="font-size:77px;line-height:1.1;letter-spacing:-1.2px;margin:0 0 26px;overflow-wrap:anywhere">Introdução ao Trabalho em Equipe</h1><p style="font-size:30px;line-height:1.5;margin:0 0 32px">Este curso visa introduzir os conceitos e a importância do trabalho em equipe. Ao longo das lições, você aprenderá como a colaboração eficiente pode beneficiar tanto o seu desenvolvimento pessoal quanto profissional.</p><p style="font-size:22px">3 módulos</p><p style="font-size:25px;color:#34d399">Comece sua jornada →</p></div>'
    journey='<div data-course-journey="1" style="height:100%;overflow:auto;padding:20px;color:#f4f4f5"><h1 style="font-size:58px">Sua jornada de aprendizagem</h1><p style="font-size:29px">Explore os temas e avance para as atividades práticas.</p><ol style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;list-style:none;margin:0;padding:0">'+''.join('<li style="display:flex;gap:20px;align-items:baseline;padding:22px;border:1px solid #ffffff22;border-radius:16px;font-size:28px;line-height:1.4"><strong style="font-size:29px;color:#34d399">'+str(i+1).zfill(2)+'</strong><span>'+title+'</span></li>' for i,title in enumerate(titles))+'</ol></div>'
    label='<div style="width:100%;height:100%;display:flex;align-items:center"><div style="width:22px;height:3px;background:#34d399;margin-right:14px"></div><span style="color:#34d399;font-size:16px;letter-spacing:2.5px">CONCEITO E IMPORTÂNCIA DO TRABALHO EM EQUIPE</span><span style="font-size:14px;margin-left:auto">Importância do Trabalho em Equipe</span></div>'
    copy='<div data-agent-copy-version="2" style="height:100%;overflow:auto;overflow-wrap:anywhere;min-width:0;padding:6px 12px 6px 0;color:#f4f4f5"><span style="font-size:xx-large">Trabalhar em equipe permite reunir perspectivas e competências que uma pessoa sozinha pode não ter. A colaboração favorece o aprendizado, ajuda a identificar problemas e melhora a coordenação das entregas. Esses benefícios fortalecem o resultado coletivo.</span></div>'
    source={'id':'mobile-type','name':'Introdução ao Trabalho em Equipe','enableVlibras':False,'course':{'slides':[{'id':'s'+str(i),'title':title,'background':'#121417','elements':[{'id':'e'+str(i)+str(j),'type':'html','htmlContent':h} for j,h in enumerate(contents)]} for i,(title,contents) in enumerate([('Introdução ao Trabalho em Equipe',[cover]),('Sua jornada',[journey]),('Conceito e importância',[label,copy])])]}}
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    for scorm,name in [(False,'html.html'),(True,'scorm.html')]:
        (destination/name).write_text(generate_single_page_html(source,str(destination),scorm_mode=scorm),encoding='utf-8')
    print(str(destination.resolve()))

if __name__=='__main__':build(sys.argv[1])
