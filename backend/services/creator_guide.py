"""Maintained product guide. Links are generated here, never by the language model."""
import re,unicodedata
from services.simulator_permissions import can_create_simulators

def entry(ident,title,keywords,steps,target='editor',action='',access='author'):
    return dict(id=ident,title=title,keywords=keywords,steps=steps,target=target,action=action,access=access)

GUIDE=[
 entry('agent-faithful','Converter PDF pelo Agente em Modo Fiel','modo fiel faithful converter conversão conversao pdf páginas paginas apresentação preservar layout original sem reescrever',[
  'Sim, o Agente permite converter um PDF em curso usando o Modo Fiel. Abra o Agente IA, crie ou abra a sessão de trabalho e envie o PDF na etapa Conteúdo.',
  'No painel do PDF enviado, clique em Gerar em Modo Fiel. Acompanhe o processamento; cada página do PDF gera um slide. Esse caminho pula a geração por IA de análise, estrutura e storyboard: não exige reescrever o material para converter.',
  'O Modo Fiel preserva a aparência das páginas — textos, cores, imagens, diagramas e logotipos — como imagem de fundo de cada slide. Não promete transformar os textos ou desenhos do PDF em objetos editáveis separados. Texto extraído, quando disponível, fica nas notas.',
  'Ao concluir, o fluxo abre o Editor. Confira o enquadramento e a leitura; você pode acrescentar textos, áudio, perguntas e outros elementos sobre o fundo, sem que isso torne editável o texto original da página.',
  'Depois, no Editor, use Exportar para gerar HTML ou SCORM e teste o resultado. Vídeos, animações e interações do documento original não são recriados automaticamente pela imagem da página.',
  'Esse Modo Fiel é para PDF. Para uma apresentação PowerPoint, você pode exportá-la para PDF e usar este caminho para preservar o visual; para importar a apresentação para edição, existe também Importar PPT no painel de projetos, com revisão da conversão.',
  'A conversão fiel não usa geração de texto por IA, mas requer processamento e acesso autorizado ao Agente. Se o PDF não estiver mais disponível na sessão, pode ser necessário reenviá-lo. Abrir o Agente pelo atalho apenas navega; o Tutor não envia arquivos nem inicia a conversão.'],'agent','','agent'),
 entry('agent-faithful-access','Solicitar acesso ao Modo Fiel','modo fiel faithful converter conversão conversao pdf preservar layout original',[
  'O SCORMIFY possui Modo Fiel no Agente: após enviar um PDF na etapa Conteúdo, Gerar em Modo Fiel cria um slide por página, preservando o visual como imagem de fundo, sem reescrita por IA.',
  'Seu perfil não tem acesso autorizado ao Agente. Peça à Administração que verifique o acesso ao Agente IA da sua empresa. O Tutor não altera permissões nem contorna esse bloqueio.',
  'A página preservada não se transforma em textos ou desenhos editáveis separados. Após a conversão por um usuário autorizado, o curso pode ser revisado e exportado no Editor conforme suas permissões.'],'here','','agent-denied'),
 entry('batch-export','Exportar cursos SCORM em lote','exportação exportacao exportar cursos lote massa vários varios múltiplos multiplos bulk pacotes zip administração',[
  'Sim, existe exportação em lote: abra Administração → Exportação em Lote. Está disponível para Super Admin e Admin da Empresa; não é necessário exportar cada curso individualmente no Editor.',
  'Busque os cursos pelo nome e marque os desejados. Selecionar todos marca os cursos da lista filtrada. Confira a seleção e clique em Exportar SCORM (quantidade). O limite é 100 cursos por lote.',
  'Os cursos são processados sequencialmente para controlar o uso de memória. Acompanhe o progresso e o resultado de cada curso no painel; uma falha não interrompe os demais.',
  'Cada curso concluído tem seu próprio ZIP para download. Não é um único ZIP reunindo todos os cursos. Aguarde o lote ativo terminar antes de iniciar outro.',
  'Admin da Empresa só pode exportar cursos autorizados da própria empresa; Super Admin pode trabalhar com os cursos disponíveis de todas as empresas. O Tutor apenas orienta: não seleciona, inicia exportações nem baixa arquivos por você.',
  'Este painel exporta SCORM. Para HTML ou outros formatos, use Exportar no Editor do curso. Teste os pacotes no LMS após o download.'],'admin','batch_export','admin'),
 entry('batch-export-access','Solicitar exportação em lote','exportação exportacao exportar cursos lote massa vários varios múltiplos multiplos bulk administração',[
  'O SCORMIFY possui exportação SCORM em lote em Administração → Exportação em Lote. Ela exige perfil Super Admin ou Admin da Empresa.',
  'Seu perfil não tem esse acesso administrativo. Solicite a um administrador autorizado a exportação dos cursos. A exportação individual continua disponível no Editor conforme suas permissões.',
  'A função em lote processa até 100 cursos sequencialmente e disponibiliza um ZIP SCORM por curso. O Tutor não altera perfis nem contorna permissões.'],'here','','nonadmin'),
 entry('admin-overview','Conhecer as opções de Administração','administração administracao painel administrativo menus opções opcoes recursos gestão',[
  'Na Administração, Admin da Empresa e Super Admin encontram Usuários, Questões dos Jogos, Tutor IA, Relatórios, Dashboard Tutor e Exportação em Lote.',
  'Usuários reúne cadastros, perfis e permissões; Questões dos Jogos reúne o banco administrativo de jogos; Tutor IA configura o Tutor dos alunos e Dashboard Tutor acompanha seus registros. Relatórios apresenta os registros disponíveis.',
  'Exportação em Lote gera um ZIP SCORM por curso selecionado. Os dados e ações disponíveis respeitam sua empresa e as permissões do servidor.',
  'Alguns menus adicionais exigem Super Admin. Abrir uma aba pelo Tutor só navega: não salva cadastros, altera permissões, inicia exportação nem executa manutenção.'],'admin','users','admin'),
 entry('companies','Administrar empresas e Biblioteca de Marca','empresa empresas organização limites biblioteca marca brand permissões',[
  'Como Super Admin, abra Administração → Empresas para consultar ou gerenciar cadastros e limites de empresas.',
  'Nas ações da empresa, confira as opções disponíveis, como Biblioteca de Marca e permissões. Revise o cadastro antes de salvar. Administradores de empresa não têm acesso à gestão global de empresas.'],'admin','companies','super'),
 entry('admin-game-bank','Administrar Questões dos Jogos','questões questoes jogos banco administração importar planilha filtrar exportar',[
  'Em Administração → Questões dos Jogos, consulte e filtre o banco administrativo de jogos. Super Admin pode selecionar a empresa; os demais administradores trabalham no escopo autorizado.',
  'Use os controles disponíveis de importação, modelo de planilha e atualização do banco. Revise os dados antes de confirmar importações ou remoções. Este banco não é o mesmo fluxo de montar Avaliações interativas no Editor.'],'admin','game_questions','admin'),
 entry('admin-reports','Consultar Relatórios administrativos','relatórios relatorios administração registros relatórios administrativos',[
  'Abra Administração → Relatórios e use Atualizar para carregar os registros disponíveis. A aba apresenta os relatórios de geração disponíveis na plataforma; não é uma garantia de notas ou conclusão de alunos no LMS.',
  'Para dados de alunos, notas e matrículas, confira os relatórios do LMS de destino. O Tutor não altera nem inventa esses resultados.'],'admin','reports','admin'),
 entry('admin-tutor-dashboard','Consultar Dashboard Tutor','dashboard tutor alunos conversas registros indicadores feedback histórico historico',[
  'Abra Administração → Dashboard Tutor para acompanhar os registros e indicadores disponíveis do Tutor dos cursos.',
  'Para alterar a configuração do Tutor dos alunos, use a aba Tutor IA. Este Tutor do Criador apenas orienta o uso e não é o mesmo assistente dos cursos exportados.'],'admin','tutor_dashboard','admin'),
 entry('admin-integrations','Verificar integrações administrativas','integrações integracoes diagnóstico diagnostico api conexão provedores',[
  'Como Super Admin, abra Administração → Integrações para consultar o diagnóstico das integrações e provedores disponíveis.',
  'Disponibilidade depende da configuração do serviço. Não envie chaves, senhas ou tokens ao Tutor. Para consumo e custos, consulte Custos por Empresa; créditos são gerenciados no provedor correspondente.'],'admin','integrations_health','super'),
 entry('admin-migration','Revisar Migração de dados','migração migracao dados campos manutenção manutencao scan dry run',[
  'Como Super Admin, abra Administração → Migração. Execute primeiro Scan (Dry Run) e revise o relatório sem aplicar mudanças.',
  'Aplicar Migração grava correções nos projetos e pede confirmação. Faça backup e avalie o impacto antes de confirmar; o Tutor não executa essa operação.'],'admin','data_migration','super'),
 entry('admin-cleanup','Revisar Limpeza de metadados antigos','limpeza metadados antigos manutenção manutencao placas fundos scan dry run',[
  'Como Super Admin, abra Administração → Limpeza para revisar a limpeza de metadados visuais antigos. Não é a exclusão geral de cursos ou imagens.',
  'Comece pelo Scan (Dry Run), confira o que será afetado e mantenha backup antes de aplicar qualquer correção. O Tutor não executa a limpeza nem confirma ações por você.'],'admin','plates_cleanup','super'),
 entry('video-quiz','Criar perguntas durante o vídeo do avatar','heygen avatar vídeo video quiz pausa pergunta tentativas feedback continuar',[
  'No Editor, selecione um vídeo direto já inserido (por exemplo HeyGen). Em Properties, abra Perguntas durante o vídeo. A mesma opção reabre uma atividade de vídeo interativo já salva.',
  'Preservar fundo transparente do vídeo mantém o canal alfa do arquivo original e remove o fundo pintado pelo player na área do avatar. Não remove um fundo gravado em vídeos opacos. O arquivo não é convertido e o painel de perguntas mantém contraste.',
  'Informe os momentos em segundos, enunciados, alternativas, resposta correta, explicação final e limite de tentativas. Você pode importar questões de escolha simples do Banco do projeto ou gerar duas perguntas com IA a partir do roteiro; a geração usa créditos e substitui as perguntas do rascunho.',
  'No Agente, na etapa Mídia, escolha HeyGen e habilite Criar perguntas durante o vídeo do avatar. Com acesso ao Agente, o roteiro e duas perguntas são planejados juntos antes da geração de imagens, com frases faladas de transição que preparam cada pergunta e até três tentativas. Usa os créditos de IA e HeyGen configurados. Planos válidos são reaproveitados se a geração do mesmo conteúdo for tentada novamente.',
  'O Agente só alinha a pausa automaticamente quando a frase é localizada de forma única nas legendas fornecidas pelo HeyGen e existe silêncio medido no áudio após a fala. Não usa percentuais estimados. Quando não consegue comprovar, preserva vídeo, roteiro e perguntas como rascunho sem aplicação de nota. No Editor, abra Perguntas durante o vídeo, confira o Roteiro falado e transições, pause após cada frase e use Usar tempo atual do vídeo ou informe os segundos. Confirme a revisão das pausas e clique em Aplicar ao vídeo. HTML/SCORM exigem essa revisão antes da exportação. Vídeos já existentes não ganham novas falas automaticamente.',
  'Se o vídeo estiver concluído na Biblioteca, mas aparecer como falha no Agente, salve e feche o Editor antes de recuperar. No resultado do Agente, em Vídeos Avatar HeyGen, clique em Atualizar: o sistema procura o registro exato do mesmo projeto e slide e tenta reconectar o vídeo existente, preservando as perguntas. Essa consulta/reconexão não solicita outro vídeo nem créditos de geração. Se houver mais de um candidato ou o bloco original tiver sido alterado, não substitui edições e informa a pendência. Após recuperar, reabra o Editor para carregar o vínculo atualizado. Adicionar pela biblioteca insere um vídeo simples, não recupera automaticamente a atividade com perguntas.',
  'Ao acertar, o aluno pode continuar; ao esgotar as tentativas, lê a explicação no painel à direita e continua. Sem nota, pode Rever vídeo e perguntas; com Vale nota, os acertos compõem o resultado SCORM. HTML e SCORM mantêm as interações; MP4 não.',
  'O Editor aceita arquivo ou link direto de HeyGen, MP4 e WebM, e também URL ou iframe de Bunny, Vimeo e YouTube. Links externos exigem internet no HTML/SCORM e permissão de incorporação; prefira arquivos persistidos para uso offline. Gerar perguntas para um vídeo já pronto não altera sua fala: revise os momentos sugeridos.'],'editor'),
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
 entry('agent','Criar um curso com o Agente IA','agente ia conteúdo arquivo análise configurar estrutura storyboard gerar curso idioma português espanhol títulos',[
  'Se o objetivo é converter um PDF preservando o visual, envie o PDF em Conteúdo e use Gerar em Modo Fiel no painel do arquivo. Cada página vira um slide com imagem de fundo, sem reescrita por IA; é um caminho diferente da criação pedagógica abaixo.',
  'Abra o Agente IA e forneça o conteúdo de referência. Execute a análise e revise o resultado.',
  'Configure público, objetivos e recursos. Gere e revise a estrutura e, em seguida, aprove a geração do storyboard.',
  'Na Estrutura, os tipos de slide aparecem com rótulos em português, como Conteúdo, Jogo e Questionário. Os textos gerados recebem orientação de pt-BR e correção local de desvios conhecidos do espanhol, sem uma nova chamada de IA. Ao retomar a sessão, essa correção é exibida sem regravar ou regenerar o rascunho. Revise os títulos antes de aprovar; nomes próprios e termos técnicos são preservados.',
  'Revise conteúdo e mídia antes de gerar o curso. As etapas que geram conteúdo podem consumir créditos das APIs configuradas.',
  'Após a geração, abra o curso no Editor para conferir diagramação, atividades e exportação.'],'agent','', 'agent'),
 entry('storyboard','Revisar o storyboard','storyboard revisar aprovação estrutura etapas erro geração',[
  'No Agente, acompanhe o progresso após aprovar a estrutura. Revise os slides do storyboard e as orientações de mídia.',
  'Os lotes concluídos do Storyboard são salvos no servidor. Se a execução perder sua reserva após reinício ou falha de conexão, o Agente informa a interrupção e libera Aprovar e Gerar Storyboard para retomar. A retomada exige esse clique; não há reinício automático nem gasto de créditos apenas por consultar o status.',
  'Na criação de um curso, o endereço do Agente passa a incluir draft= com o identificador da sessão. Guarde esse link para reabrir o rascunho mesmo antes de gerar o curso; é necessário entrar com o mesmo usuário. Abrir o link não gera conteúdo nem consome créditos. Arquivos ainda não enviados e alterações locais não salvas não são recuperados por esse link.',
  'Com o mesmo conteúdo, estrutura e configuração, os lotes salvos são reutilizados sem nova geração. O lote que estava em execução pode precisar ser refeito e consumir créditos novamente. Alterar entradas ou pedir regeneração completa inicia outro conjunto de lotes; execuções antigas anteriores a esse recurso não têm lotes recuperáveis.',
  'O progresso conta lotes concluídos. Cursos extensos podem ultrapassar 15 minutos: o acompanhamento continua enquanto houver execução ativa, sem acusar falha apenas pelo tempo. Em falha persistente de conexão ou sessão expirada, reentre e retome o acompanhamento.',
  'No Storyboard, os jogos apresentam uma prévia do planejamento pedagógico. O jogo final é montado na etapa Gerar Curso com a mecânica existente e perguntas vinculadas ao conteúdo do curso; não é necessário gerar e descartar HTML de jogos nesta etapa.',
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
 entry('layout-recovery','Recuperar elementos pequenos ou sem enquadramento','recuperar restauração restaurar slides pequenos tamanho dimensões zeradas enquadramento',[
  'Se o Editor detectar identificadores ou dimensões ausentes, mostra um aviso de enquadramento incompleto. Não significa necessariamente perda do conteúdo.',
  'Para layouts personalizados, use Restaurar de HTML anterior no aviso e selecione uma exportação anterior do mesmo curso, de até 50 MB. Os slides precisam ter a mesma estrutura e os conteúdos dos elementos precisam corresponder; slides alterados ou não correspondentes ficam intactos.',
  'A restauração guarda uma cópia de segurança no servidor e recupera apenas metadados ausentes ou dimensões inválidas. Não importa o conteúdo antigo por cima do atual, não consome créditos de IA e recusa aplicação se o curso mudou durante a recuperação. A comparação reconhece o HTML codificado pelo exportador sem alterar scripts ou conteúdo para forçar correspondências.',
  'Se não houver referência compatível, não adivinhe posições. Criar cópia completa do HTML anterior importa o curso completo da exportação em um NOVO projeto com sufixo (Recuperado), mantendo o atual intacto. Essa cópia usa textos, perguntas, configurações e enquadramento antigos, não incorpora edições posteriores. Mídias embutidas são preservadas; links externos antigos podem exigir atualização. Não consome IA; exige acesso ao projeto de origem e referência de até 14 MB de dados de curso.',
  'Baixar diagnóstico do enquadramento gera um JSON local com o conteúdo atual para investigação, sem IA. O arquivo contém o conteúdo do curso: revise antes de compartilhar. Guarde o HTML anterior e salve antes de editar novamente.'],'editor'),
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
  'No material de apoio, você pode anexar arquivos, usar links de vídeo ou Gerar imagem da pergunta com IA. Nas alternativas, etapas e cartões, use Imagem IA. Edite a descrição, gere, confira a prévia e clique em Usar esta imagem; depois salve a questão no Banco. As imagens geradas também ficam na galeria reutilizável e usam créditos.',
  'No Banco, localize questões pela busca no título, enunciado e alternativas, e pelos filtros de tipo, categoria, material de apoio e seleção. Limpar filtros restaura a lista sem remover as questões selecionadas.',
  'Selecione as questões e confirme a criação no slide. Valide o funcionamento na prévia.'],'editor','assessment'),
 entry('games','Criar jogos educativos','game jogos quiz show cruzadas batalha sudoku caça tesouro pontuação cronômetro',[
  'No Editor, abra Jogos educativos e escolha o tipo de jogo. No Agente, habilite Jogos Educativos na configuração do curso.',
  'Confira se as questões pertencem ao tema do curso e revise respostas e feedback antes de inserir.',
  'Teste pontuação, tempo, vidas, reinício e comportamento ao acertar e errar. As opções dependem do tipo de jogo.'],'editor','games'),
 entry('simulators','Criar e refinar simuladores','simulador simuladores simulação visualização didática refino cenário mecanismo',[
   'Na confirmação de Gerar imagens das peças, escolha a quantidade máxima de 1 a 4. Use 1 imagem — testar uma peça para uma validação menor com créditos. O limite é imposto também no servidor; salvar no curso continua sendo uma ação separada.',
   'O catálogo em Revisar projeto visual contém componentes vetoriais pré-existentes, não as imagens geradas por IA. Um filtro vazio nesse catálogo não bloqueia Gerar imagens das peças. As imagens geradas são salvas na Biblioteca de Imagens. Se ocorrer falha, a mensagem informa o motivo seguro (acesso, configuração, limite ou transparência); erros globais interrompem os demais pedidos para não repetir a mesma recusa. O modelo padrão das imagens das peças usa gpt-image-2.5-sunburst; OPENAI_OBJECT_IMAGE_MODEL permite configuração específica. O antigo gpt-image-1 é redirecionado ao substituto suportado, sem alterar os modelos de outras funcionalidades.',
   'Para acrescentar imagens em um simulador existente do motor de regras, dê duplo clique no slide, abra Gerar com IA (ou Preparar refino visual) e use Gerar imagens das peças. Confirme o aviso de créditos OpenAI. Essa ação preserva o cenário e as regras, salva imagens na biblioteca e atualiza a prévia; salve alterações para aplicar no slide. Refinar cenário sozinho é refino vetorial, não geração de imagens, a menos que Ilustrar objetos com imagens IA esteja marcado. A interface informa a quantidade aplicada; zero imagens não deve ser anunciado como sucesso. Se o botão não aparecer, salve seu trabalho antes de recarregar a interface atualizada.',
   'Para gerar imagens individuais das peças, marque Ilustrar objetos com imagens IA nas opções de simuladores do Editor ou na Configuração do Agente antes de gerar. É opcional e consome créditos OpenAI: até quatro peças rígidas por atividade, sem modelo temático fixo. Exige chave OpenAI e a permissão de simuladores. As imagens transparentes são salvas na biblioteca da empresa/autor e incorporadas no HTML/SCORM para uso offline. Fluxos e partes deformáveis continuam vetoriais; falhas preservam a peça anterior. Revise o resultado. Em atividades existentes do motor de regras, reabra por duplo clique, marque a opção e use Refinar cenário; salve e reexporte. Publicar não redesenha cursos existentes.',
  'No Editor, abra Adicionar HTML Personalizado e a aba Gerar com IA. Escolha o tipo de atividade, a complexidade e a abordagem visual.',
  'Descreva o mecanismo, os objetos e o que o aluno deve observar. Guiado prioriza a demonstração; Aplicado e Avançado expõem desafios e controles mais completos.',
  'O planejamento visual das novas gerações escolhe o enquadramento pelo mecanismo: vista ampliada de componentes, ambiente ou interação, conforme o tema. Não há um cenário fixo para todos os assuntos. O acabamento ilustrado usa luz e volume suaves também nos níveis Aplicado e Avançado; a abordagem técnica mantém leitura de esquema.',
  'O resultado depende da geração de IA e precisa de revisão: não há garantia de acabamento idêntico em qualquer assunto. Os objetos têm legendas consultáveis. Para melhorar atividades antigas use Refinar cenário; publicar uma atualização não redesenha automaticamente os simuladores nem os arquivos HTML/SCORM já exportados. Reexporte após salvar a alteração.',
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
  'O player apresenta cena, contexto e decisões lado a lado. O aluno seleciona uma alternativa e usa Confirmar decisão; somente a confirmação registra a decisão e apresenta a consequência. Continuar leva à próxima cena.',
  'No Editor, a opção Gerar ilustração contextualizada com IA pode consumir créditos adicionais. Uma imagem do tema é reutilizada nas cenas para manter continuidade e salva na biblioteca; se a imagem falhar, o cenário continua utilizável sem ela.',
  'Selecione o cenário no canvas e abra Imagens e falas das cenas nas propriedades. Escolher na biblioteca permite trocar a imagem de cada cena sem alterar as decisões. Também há campos de descrição acessível e fala em destaque.',
  'Nas propriedades de cada cena, Gerar imagem com IA abre a descrição do visual desejado. Revise a prévia e confirme Usar esta imagem para aplicá-la; gerar não substitui a imagem atual automaticamente. A imagem é persistida no projeto e na biblioteca, e a geração pode consumir créditos.',
  'A+, A−, Contraste, Consultar contexto e Histórico das decisões ajudam a leitura. Mostrar pontuação no desfecho controla apenas a exibição, não as regras de aprovação. Teste em Visualizar e reexporte HTML/SCORM para atualizar arquivos anteriores.',
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
  'No Editor, abra Whiteboard. O modo IA + Formas escreve por traços como o modo normal, desenha objetos do catálogo e aceita polígonos e linhas livres. Após gerar o plano, abra Desenhos, cores e preenchimentos para buscar objetos e ajustar traço, preenchimento, opacidade e posição dos desenhos.',
  'As cores preenchem apenas regiões fechadas, depois do contorno, preservando textos. Ajustar o plano manualmente não usa IA; gerar um novo plano usa a integração configurada. Renderize uma nova versão para atualizar vídeos já inseridos: arquivos antigos não mudam automaticamente.',
  'As ferramentas de caneta e formas do Editor permitem anotar o slide; escolha cor e espessura antes de desenhar.',
  'Confira o resultado e a duração na prévia antes de exportar.'],'editor','whiteboard'),
 entry('pdf','Adicionar PDF e flipbook','pdf flipbook documento páginas livro',[
  'No Editor, use Adicionar PDF ou Flipbook, conforme a apresentação desejada para o documento.',
  'Revise as páginas, o enquadramento e a leitura na prévia. Para documentos importados, confira também as imagens.'],'editor','pdf'),
 entry('import','Importar apresentação e tutoriais','importar powerpoint ppt pptx tutorial apresentação arquivo',[
  'No painel de projetos, use Importar PPT para trazer uma apresentação para edição.',
  'Outra opção para preservar a aparência de uma apresentação é exportá-la para PDF, enviá-la ao Agente e escolher Gerar em Modo Fiel. Cada página fica como imagem de fundo de um slide, não como objetos editáveis separados.',
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
    if access=='nonadmin':return not admin
    if access=='approval':return admin or 'aprovador' in r
    if access=='agent':return 'super_admin' in r or 'aprovador' in r or bool((user.get('company') or {}).get('permissions',{}).get('agentAccess'))
    if access=='agent-denied':return not allowed(user,'agent')
    if access=='simulator':return can_create_simulators(user) and ('aprovador' not in r or admin)
    return 'aprovador' not in r or admin

def normalize(value):return ''.join(c for c in unicodedata.normalize('NFKD',value.lower()) if not unicodedata.combining(c))

def batch_export_question(question):
    text=normalize(question)
    return bool(re.search(r'export|scorm',text) and re.search(r'\blote\b|\bmassa\b|\bvarios\b|\bmultipl\w*|\bbulk\b|\btodos\b|de uma (?:so |unica )?vez|simultane',text))

def faithful_question(question):
    text=normalize(question)
    return bool(re.search(r'\b(?:modo\s+)?fiel\b|\bfaithful\b',text) or ('pdf' in text and re.search(r'preserv\w*.*(?:visual|layout|original)|sem reescrev',text)))
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
        priority=50 if batch_export_question(question) and t['id'] in ('batch-export','batch-export-access') or faithful_question(question) and t['id'] in ('agent-faithful','agent-faithful-access') else 0
        return priority+sum(weight(w) for w in words)+.15*sum(weight(w) for w in context)
    ranked=sorted(topics,key=score,reverse=True)
    best=score(ranked[0]) if ranked else 0
    matches=[t for t in ranked if score(t)>0 and score(t)>=best*.55][:6]
    return matches or topics[:4]
