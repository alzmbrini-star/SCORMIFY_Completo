"""Maintained product guide. Links are generated here, never by the language model."""
import re,unicodedata
from services.simulator_permissions import can_create_simulators

def entry(ident,title,keywords,steps,target='editor',action='',access='author'):
    return dict(id=ident,title=title,keywords=keywords,steps=steps,target=target,action=action,access=access)

GUIDE=[
 entry('creator-help','Usar este Tutor do Criador','tutor criador ajuda modal ampliar reduzir fonte contraste leitura janela',[
  'Clique em Tutor IA no canto inferior direito para abrir o painel. Ele não abre sozinho.',
  'Use Ampliar para ler em uma janela central maior. A− e A+ ajustam a fonte; Contraste permite escolher claro, escuro ou alto contraste.',
  'Recolher preserva a conversa durante a navegação nesta sessão. Limpar conversa apaga o histórico visível. Preferências de leitura ficam neste navegador; a conversa não é gravada no curso.',
  'Guias rápidos não usam geração de IA. As perguntas digitadas usam a IA configurada quando disponível; caso contrário, o Tutor informa que está respondendo pelo guia.'],'here'),
 entry('start','Conhecer os modos de criação','começar recursos funcionalidades possibilidades misto tradicional manual',[
  'No painel de projetos, crie um projeto para trabalhar manualmente no Editor ou abra o Agente IA para construir um curso a partir de conteúdo.',
  'No Agente, revise análise, configuração, estrutura e storyboard antes de gerar o curso. Depois, use o Editor para ajustes finos.',
  'O Editor reúne slides, textos, imagens, vídeos, áudio, interações e exportação. Os recursos disponíveis dependem das permissões da sua conta.'],'dashboard'),
 entry('new-project','Criar um projeto no Editor','novo projeto curso criar manual vazio',[
  'No painel de projetos, clique em Novo Projeto, informe um nome e confirme a criação.',
  'No Editor, use a barra de ferramentas para adicionar elementos ao slide; selecione-os para ajustar propriedades.',
  'Salve o trabalho antes de sair do Editor. Abrir a janela de criação não cria nem salva um projeto automaticamente.'],'dashboard','new-project'),
 entry('agent','Criar um curso com o Agente IA','agente ia conteúdo arquivo análise configurar estrutura storyboard gerar curso',[
  'Abra o Agente IA e forneça o conteúdo de referência. Execute a análise e revise o resultado.',
  'Configure público, objetivos e recursos. Gere e revise a estrutura e, em seguida, aprove a geração do storyboard.',
  'Revise conteúdo e mídia antes de gerar o curso. As etapas que geram conteúdo podem consumir créditos das APIs configuradas.',
  'Após a geração, abra o curso no Editor para conferir diagramação, atividades e exportação.'],'agent','', 'agent'),
 entry('storyboard','Revisar o storyboard','storyboard revisar aprovação estrutura etapas erro geração',[
  'No Agente, acompanhe o progresso após aprovar a estrutura. Revise os slides do storyboard e as orientações de mídia.',
  'Use os controles de edição ou o chat da etapa para solicitar ajustes. Confira o resultado antes de aprovar ou gerar o curso.',
  'Se houver falha, registre a mensagem apresentada; não suponha que o curso foi gerado ou salvo. Para simuladores, o diagnóstico técnico ajuda a identificar a causa.'],'agent','', 'agent'),
 entry('slides','Organizar e editar slides','slides miniaturas canvas mover duplicar apagar número duração timeline camada',[
  'Abra um projeto e selecione a miniatura do slide na coluna esquerda. O slide ativo fica destacado e numerado.',
  'Use as opções da miniatura para organizar os slides e a linha do tempo para ajustar a apresentação dos elementos.',
  'Selecione um elemento para editar posição, tamanho e propriedades. As abas Properties e Layers ajudam a localizar e organizar o conteúdo.']),
 entry('text','Adicionar textos e corrigir contraste','texto fonte letras cor contraste tema resumo cores legibilidade',[
  'No Editor, adicione ou selecione um texto para ajustar conteúdo e propriedades, como fonte, tamanho e cor.',
  'O controle de cores dos textos permite corrigir contraste após aplicar um tema visual.',
  'Em uma atividade HTML, selecione o elemento e consulte os controles de cores disponíveis. Compare a prévia antes de aplicar e salvar.'],'editor','text-colors'),
 entry('images','Adicionar imagens','imagem imagens foto ilustração upload galeria leonardo krea',[
  'No Editor, use Adicionar imagem para incluir uma imagem. A Galeria e os painéis Leonardo/Krea oferecem outros caminhos de criação e seleção.',
  'Selecione a imagem para ajustar posição e tamanho. Confira se ela não cobre o texto e se está legível na prévia.',
  'Geração por serviços de IA depende das integrações e pode consumir créditos.'],'editor'),
 entry('video','Inserir vídeo por link ou criar com Kling','vídeo video bunny vimeo youtube kling iframe filmagem áudio português',[
  'No Editor, abra Adicionar vídeo. Você pode usar um link do YouTube, Vimeo ou Bunny Stream; o Bunny também aceita o iframe completo.',
  'Para Bunny protegido, preserve token e expires do endereço e autorize o domínio onde o conteúdo será exibido nas configurações do provedor. Um erro 403 também pode depender dessas permissões ou de um link expirado.',
  'A opção de criar com Kling depende da integração configurada e consome créditos. Descreva idioma e conteúdo desejados; o resultado precisa ser conferido.',
  'Vídeos por link exigem internet no HTML/SCORM e permissão de incorporação no provedor. O Tutor não garante a inclusão de uma imagem de referência ou uma voz específica sem conferir as opções disponíveis.'],'editor','video'),
 entry('audio','Adicionar narração e áudio','áudio audio narração narracao voz microfone gravação elevenlabs tts',[
  'No Editor, use o recurso de narração/TTS para gerar voz a partir do texto, ou as ferramentas de áudio e gravação para incluir áudio próprio.',
  'Confira a voz, o idioma, o texto e a duração antes de gerar; serviços de voz podem consumir créditos.',
  'Use a linha do tempo para ajustar quando o áudio toca. Verifique o resultado no player.'],'editor','tts'),
 entry('assessment','Criar avaliações interativas','avaliação avaliação interativa prova questões banco questão imagem apoio alternativas teste',[
  'No Editor, abra Avaliações interativas. Selecione questões do Banco, crie uma questão manualmente ou use Criar com IA.',
  'Revise enunciado, alternativas corretas, feedback e material de apoio. A geração com IA deve ser revisada antes de inserir a avaliação.',
  'No material de apoio, você pode usar os tipos de anexo oferecidos e links de vídeo. Confira a prévia do vídeo e as permissões do provedor.',
  'Selecione as questões e confirme a criação no slide. Valide o funcionamento na prévia.'],'editor','assessment'),
 entry('games','Criar jogos educativos','game jogos quiz show cruzadas batalha sudoku caça tesouro pontuação cronômetro',[
  'No Editor, abra Jogos educativos e escolha o tipo de jogo. No Agente, habilite Jogos Educativos na configuração do curso.',
  'Confira se as questões pertencem ao tema do curso e revise respostas e feedback antes de inserir.',
  'Teste pontuação, tempo, vidas, reinício e comportamento ao acertar e errar. As opções dependem do tipo de jogo.'],'editor','games'),
 entry('simulators','Criar e refinar simuladores','simulador simuladores simulação visualização didática refino cenário mecanismo',[
  'No Editor, abra Adicionar HTML Personalizado e a aba Gerar com IA. Escolha o tipo de atividade, a complexidade e a abordagem visual.',
  'Descreva o mecanismo, os objetos e o que o aluno deve observar. Guiado prioriza a demonstração; Aplicado e Avançado expõem desafios e controles mais completos.',
  'Revise a prévia antes de inserir. Para reabrir uma atividade compatível já inserida, dê duplo clique nela; Refinar cenário solicita uma nova geração da camada visual e pode consumir créditos.',
  'A criação e o refino dependem da permissão individual Permitir criar simuladores, definida pela Administração. Atividades existentes não são removidas ao desabilitá-la.'],'editor','html','simulator'),
 entry('simulator-access','Solicitar acesso aos simuladores','permissão simulador bloqueado desabilitado habilitar não autorizado',[
  'Peça à Administração para verificar a opção Permitir criar simuladores no seu cadastro.',
  'Essa opção controla geração e refino pelo Agente e Editor. Ela não remove os simuladores já existentes.',
  'As demais permissões, como acesso ao Agente IA da empresa, continuam sendo necessárias.'],'dashboard'),
 entry('case-study','Criar estudos de caso','estudo caso casos investigar decisão evidência',[
  'No Agente, habilite Estudos de Caso nos recursos do curso. Informe conteúdo e contexto que sustentem as decisões.',
  'No Editor, use a geração de HTML com IA para solicitar um estudo de caso contextualizado.',
  'Revise cenário, evidências, decisões e feedback. Confira ilustrações e contraste na prévia antes de inserir.'],'editor','html'),
 entry('scenario','Criar cenários de decisão','cenário desafio ramificação árvore decisão consequências',[
  'No Editor, abra Cenários para montar situações com escolhas e consequências. No Agente, habilite Cenários de Desafio na configuração.',
  'Revise cada caminho e seus resultados; teste também respostas inadequadas, retorno e reinício.'],'editor','scenario'),
 entry('html','Inserir HTML e interações próprias','html código personalizado javascript css colar desenvolvedor flashcard linha tempo infográfico',[
  'No Editor, abra Adicionar HTML Personalizado. Use Colar HTML para conteúdo próprio ou Gerar com IA para solicitar uma interação.',
  'Confira a prévia e o código antes de inserir. Interações podem usar HTML, CSS e JavaScript; recursos externos podem depender de internet e permissões.',
  'A permissão de simuladores também é aplicada às gerações e refinos desse tipo. Conteúdo já existente deve ser testado antes da exportação.'],'editor','html'),
 entry('brand','Aplicar tema e identidade visual','marca brand kit identidade tema template layout logo biblioteca cores fundo',[
  'No Editor, o recurso de tema/template visual permite aplicar um acabamento ao curso. Revise a prévia antes de confirmar mudanças.',
  'A Biblioteca de Marca da empresa reúne imagens e diretrizes visuais. Nas propriedades do slide, consulte as opções de uso ou herança dessa biblioteca.',
  'Após aplicar um tema, confira contraste dos textos, posição das imagens e legibilidade de atividades HTML.'],'editor','template'),
 entry('whiteboard','Criar animações Whiteboard','whiteboard desenho mão caneta pen traço animação',[
  'No Editor, abra Whiteboard para criar os conteúdos oferecidos por essa ferramenta.',
  'As ferramentas de caneta e formas do Editor permitem anotar o slide; escolha cor e espessura antes de desenhar.',
  'Confira o resultado e a duração na prévia antes de exportar.'],'editor','whiteboard'),
 entry('pdf','Adicionar PDF e flipbook','pdf flipbook documento páginas livro',[
  'No Editor, use Adicionar PDF ou Flipbook, conforme a apresentação desejada para o documento.',
  'Revise as páginas, o enquadramento e a leitura na prévia. Para documentos importados, confira também as imagens.'],'editor','pdf'),
 entry('import','Importar apresentação e tutoriais','importar powerpoint ppt pptx tutorial apresentação arquivo',[
  'No painel de projetos, use Importar PPT para trazer uma apresentação para edição.',
  'A opção de importar tutoriais usa a integração de tutoriais disponível no produto.',
  'Confira a diagramação, imagens e interações do conteúdo importado antes de exportar.'],'dashboard','import'),
 entry('preview','Visualizar o curso','prévia preview visualizar player responsivo testar singlepage',[
  'No Editor, abra Visualizar para testar o curso como participante. Há também a prévia Single Page quando apropriada.',
  'Teste navegação, áudio, vídeo, atividades, reinício e legibilidade. A prévia não substitui o teste do pacote no LMS.'],'editor','preview'),
 entry('export','Exportar HTML ou SCORM','exportar scorm html zip lms didaxis passed failed complete conclusão aprovação',[
  'No Editor, clique em Exportar e escolha o formato e as configurações disponíveis para seu curso.',
  'Gere o pacote e use o botão de download quando a exportação terminar. Abrir a janela não inicia a exportação.',
  'Teste o ZIP SCORM no LMS de destino: conclusão, nota, aprovação, retomada e nova tentativa dependem também da integração e das regras desse LMS.',
  'Se um aluno ficar preso em Failed, reúna o ZIP e os critérios usados para análise. O Tutor não altera matrículas nem garante corrigir um status já gravado no LMS.'],'editor','export'),
 entry('users','Administrar usuários e permissões','usuário usuários acesso permissão habilitar desabilitar empresa cadastro editor aprovador',[
  'Em Administração → Usuários, abra Novo Usuário ou Edite o cadastro existente.',
  'Defina os perfis e a opção Permitir criar simuladores conforme a necessidade. Novos usuários começam sem essa permissão; usuários anteriores mantêm o acesso até alteração.',
  'Salve somente após revisar o cadastro. Super Admin mantém acesso integral. Administradores de empresa gerenciam apenas usuários da própria empresa.'],'admin','users','admin'),
 entry('student-tutor','Configurar o Tutor dos alunos','tutor aluno curso exportado tutor ia feedback histórico treinamento',[
  'O Tutor para os autores, nesta conversa, é diferente do Tutor dos alunos nos cursos exportados.',
  'Em Administração → Tutor IA, confira as configurações do Tutor dos cursos. O Dashboard Tutor acompanha os registros e indicadores disponíveis.',
  'O Tutor dos cursos depende da conectividade e das configurações da integração. Este assistente de uso do produto não altera essas configurações.'],'admin','tutor','admin'),
 entry('costs','Consultar custos e integrações','custo créditos api chave configuração integração render saldo consumo',[
  'Em Administração, consulte Custos por Empresa para os registros disponíveis e Integrações para os diagnósticos das integrações.',
  'Créditos e limites dos provedores são gerenciados nos serviços correspondentes. Não envie chaves de API, senhas ou tokens ao Tutor.',
  'Este Tutor não compra créditos, altera segredos ou garante valores de cobrança.'],'admin','cost_report','super'),
 entry('approvals','Aprovar storyboards','aprovador aprovação fila revisar rejeitar',[
  'Abra o Agente com um perfil autorizado para acessar a fila de aprovação.',
  'Revise o storyboard e suas pendências antes de aprovar ou devolver para ajustes. Somente o usuário pode confirmar essas ações.'],'agent','','approval'),
]

def roles(user):return set(user.get('roles') or [])|{user.get('role','')}
def allowed(user,access):
    r=roles(user);admin=bool(r&{'super_admin','company_admin'})
    if access=='super':return 'super_admin' in r
    if access=='admin':return admin
    if access=='approval':return admin or 'aprovador' in r
    if access=='agent':return 'super_admin' in r or 'aprovador' in r or bool((user.get('company') or {}).get('permissions',{}).get('agentAccess'))
    if access=='simulator':return can_create_simulators(user) and ('aprovador' not in r or admin)
    return 'aprovador' not in r or admin

def normalize(value):return ''.join(c for c in unicodedata.normalize('NFKD',value.lower()) if not unicodedata.combining(c))
def current_editor(path):return path if re.fullmatch(r'/editor/[A-Za-z0-9_-]{1,100}',path or '') else None
def link(topic,path):
    target=topic['target'];action=topic['action']
    if target=='here':return None
    if target=='editor':
        base=current_editor(path)
        if not base:return {'label':'Escolher um curso no painel','href':'/'}
        return {'label':'Abrir '+topic['title'],'href':base+('?help='+action if action else '')}
    if target=='admin':return {'label':'Abrir Administração: '+topic['title'],'href':'/admin?tab='+action}
    return {'label':'Abrir '+('Agente IA' if target=='agent' else 'painel de projetos'),'href':('/agent' if target=='agent' else '/')+('?help='+action if action else '')}

def topics_for(user,path=''):
    return [dict(t,link=link(t,path)) for t in GUIDE if allowed(user,t['access'])]

def search_topics(question,topics,history=()):
    previous=' '.join(m['content'] for m in history[-3:] if m['role']=='user')
    stop={'como','para','uma','que','com','por','posso','quero','fazer','onde','tenho','preciso','produto','scormify','usar','criar'}
    words=set(re.findall(r'[a-z0-9]{3,}',normalize(question)))-stop
    context=set(re.findall(r'[a-z0-9]{3,}',normalize(previous)))-stop
    def score(t):
        keys=normalize(t['keywords']+' '+t['title']);text=normalize(' '.join(t['steps']))
        def weight(w):return 5 if w in keys else 1 if w in text else 0
        return sum(weight(w) for w in words)+.15*sum(weight(w) for w in context)
    ranked=sorted(topics,key=score,reverse=True)
    best=score(ranked[0]) if ranked else 0
    matches=[t for t in ranked if score(t)>0 and score(t)>=best*.55][:6]
    return matches or topics[:4]
