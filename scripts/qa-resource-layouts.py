"""Local-only visual fixture: uses the real renderer, no API calls or course writes."""
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from services.resource_layouts import prepare_resource_slide

CASES={
 '/cards.html':('flashcard','cards','Critérios de avaliação e seus pesos',[
  ('Coerência LNT, plano e ações','25%'),('Prática, validação e eficácia','25%'),
  ('Consistência BU e público','20%'),('Matrizes e rastreabilidade','15%'),('PDI','15%'),
  ('Rastreabilidade da aprendizagem','Conserve as evidências para permitir acompanhamento e revisão.'),
  ('Revisão de detalhes longos','Um detalhe longo continua legível: '+('Mantenha a explicação completa e permita consultar cada informação. '*35)),
  ('Conclusão da revisão','Todos os oito itens continuam disponíveis, sem truncamento.')]),
 '/culinary.html':('flashcard','cards','Panificação artesanal — revisão',[
  ('Mistura','Integre os ingredientes conforme a receita.'),('Fermentação','Observe o desenvolvimento da massa e as condições da receita.'),
  ('Modelagem','Dê forma à massa antes da etapa seguinte.'),('Assamento','Acompanhe o processo conforme o equipamento e a receita.'),
  ('Resfriamento','Aguarde o resfriamento apropriado antes de embalar.'),('Revisão','Compare o resultado com os critérios definidos na receita.')]),
 '/flow.html':('visual_summary','flow','Manutenção de automóveis — fluxo de atendimento',[
  ('Receber','Registre a solicitação e os sintomas relatados.'),('Inspecionar','Verifique os pontos previstos no procedimento.'),
  ('Planejar','Defina a intervenção com base no diagnóstico.'),('Executar','Siga o procedimento técnico aplicável.'),('Conferir','Verifique e registre o resultado do serviço.')]),
 '/note.html':('narration','note','Comunicação em equipe — explicação',[
  ('Escuta e clareza','Uma comunicação eficaz combina escuta atenta e mensagens claras.\n\nAo receber uma orientação, confirme o entendimento antes de executar a tarefa.\n\nA documentação do combinado ajuda a equipe a acompanhar o trabalho e esclarecer dúvidas.')]),
}

class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path=='/':
   body='<h1>Conferência local — motor de layouts</h1><p>Sem IA, créditos ou alterações em cursos.</p>'+''.join(f'<p><a href="{path}">{data[2]}</a></p>' for path,data in CASES.items())
  elif self.path in CASES:
   stype,kind,title,items=CASES[self.path]
   slide=prepare_resource_slide({'type':stype,'resourceLayout':{'kind':kind,'title':title,'items':[{'front':a,'back':b} for a,b in items]}})
   body=slide['elements'][0]['htmlContent']
  else:
   self.send_error(404);return
  self.send_response(200);self.send_header('Content-Type','text/html;charset=utf-8');self.end_headers();self.wfile.write(body.encode())

ThreadingHTTPServer(('127.0.0.1',8783),Handler).serve_forever()
