"""
AI Instructional Design Agent Service
Transforms raw content into complete Scormfy courses using Gemini 3 Flash
"""
import os
import json
import uuid
import asyncio
import logging
import base64
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

logger = logging.getLogger(__name__)

# Shared motor db connection for async asset persistence
_motor_db = None

async def _get_motor_db():
    """Get or create a shared motor db connection for asset persistence."""
    global _motor_db
    if _motor_db is not None:
        return _motor_db
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get('MONGO_URL', '')
        db_name = os.environ.get('DB_NAME', '')
        if mongo_url and db_name:
            _is_atlas = "mongodb.net" in mongo_url or "mongodb+srv" in mongo_url
            client = AsyncIOMotorClient(
                mongo_url,
                serverSelectionTimeoutMS=120000 if _is_atlas else 30000,
                connectTimeoutMS=120000 if _is_atlas else 30000,
                socketTimeoutMS=300000 if _is_atlas else 60000,
                maxPoolSize=3,
                retryWrites=True,
                retryReads=True,
            )
            _motor_db = client[db_name]
            return _motor_db
    except Exception as e:
        logger.warning(f"Failed to create motor db for asset persistence: {e}")
    return None

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

# Primary model: Gemini 3 Flash (fast + cheap), Fallback: GPT-4o
PRIMARY_MODEL = ("gemini", "gemini-3-flash-preview")
FALLBACK_MODEL = ("openai", "gpt-4o")
IMAGE_MODEL = ("gemini", "gemini-3-pro-image-preview")

SYSTEM_PROMPT = """Você é um Agente de Design Instrucional Sênior especializado em criar cursos digitais.

Você atua simultaneamente como:
- Designer Instrucional Sênior
- Especialista em Learning Experience (LX)
- Roteirista educacional
- Diretor criativo de conteúdo digital

Seu objetivo é criar cursos altamente eficazes, didáticos e visualmente envolventes.

REGRAS:
- Sempre responda em português brasileiro
- Use técnicas modernas: microlearning, storytelling educacional, aprendizagem ativa
- Seja conciso e objetivo nas respostas de chat
- Para dados estruturados, retorne JSON válido dentro de blocos ```json```
- Identifique conceitos críticos e sugira reforços visuais"""

def _new_chat(session_id: str, provider: str = None, model: str = None) -> LlmChat:
    p = provider or PRIMARY_MODEL[0]
    m = model or PRIMARY_MODEL[1]
    return LlmChat(
        api_key=EMERGENT_KEY,
        session_id=session_id,
        system_message=SYSTEM_PROMPT,
    ).with_model(p, m)


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from a text that may contain ```json blocks."""
    import re
    m = re.search(r"```json\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try parsing the whole text as JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


async def _resilient_send(session_id_prefix: str, system_msg: str, prompt: str) -> str:
    """Send message with retry + fallback (Gemini -> GPT-4o)."""
    import asyncio as aio
    models = [PRIMARY_MODEL, FALLBACK_MODEL]
    for attempt, (provider, model) in enumerate(models):
        for retry in range(2):
            try:
                chat = LlmChat(
                    api_key=EMERGENT_KEY,
                    session_id=f"{session_id_prefix}_r{attempt}_{retry}",
                    system_message=system_msg,
                ).with_model(provider, model)
                response = await chat.send_message(UserMessage(text=prompt))
                return response
            except Exception as e:
                err_str = str(e)[:120]
                logger.warning(f"LLM {provider}/{model} attempt {retry}: {err_str}")
                if retry == 0 and ("RateLimit" in err_str or "429" in err_str or "No deployments" in err_str):
                    await aio.sleep(3)
                    continue
                break
    raise Exception("All LLM models failed")


async def analyze_content(session_id: str, content_text: str, file_info: str = "") -> dict:
    """Step 1: Analyze uploaded content and extract key information."""
    prompt = f"""Analise o seguinte conteúdo educacional e retorne um JSON com:

1. "title": título sugerido para o curso
2. "summary": resumo do conteúdo (2-3 frases)
3. "mainTopics": lista dos tópicos principais identificados
4. "targetAudience": público-alvo sugerido
5. "difficulty": nível de dificuldade ("basico", "intermediario", "avancado")
6. "estimatedDuration": duração estimada em minutos
7. "suggestedModules": número sugerido de módulos
8. "gaps": lacunas ou pontos que precisam de mais conteúdo
9. "strengths": pontos fortes do conteúdo
10. "keywords": palavras-chave principais

{f'Informação do arquivo: {file_info}' if file_info else ''}

CONTEÚDO:
{content_text[:12000]}

Retorne APENAS o JSON dentro de ```json```."""

    models = [PRIMARY_MODEL, FALLBACK_MODEL]
    for provider, model in models:
        try:
            chat = _new_chat(f"agent-analyze-{session_id}", provider=provider, model=model)
            response = await chat.send_message(UserMessage(text=prompt))
            data = _extract_json(response)
            if data:
                return data
        except Exception as e:
            logger.warning(f"Analyze with {provider}/{model} failed: {str(e)[:80]}")
            continue

    return {
        "title": "Curso sem título",
        "summary": "Análise não pôde ser concluída",
        "mainTopics": [],
        "targetAudience": "Público geral",
        "difficulty": "intermediario",
        "estimatedDuration": 30,
        "suggestedModules": 3,
        "gaps": [],
        "strengths": [],
        "keywords": [],
    }


async def generate_structure(session_id: str, content_text: str, config: dict) -> dict:
    """Step 2: Generate course architecture based on content and configuration."""

    # ── Resource Balance Logic ──
    resource_balance = config.get('resourceBalance', 'media')
    enabled_resources = config.get('enabledResources', {})

    # Build the list of allowed types
    all_types = ['content', 'title', 'summary']  # always present
    resource_type_map = {
        'quiz': 'quiz',
        'simulator': 'simulator',
        'scenario': 'scenario',
        'avatar_scene': 'avatar_scene',
        'infographic': 'infographic',
        'flashcard': 'flashcard',
        'timeline': 'timeline',
        'case_study': 'case_study',
    }
    for key, slide_type in resource_type_map.items():
        if enabled_resources.get(key, False):
            all_types.append(slide_type)

    available_types = '|'.join(all_types)

    # Distribution instructions based on balance level
    dist_instructions = {
        'baixa': """DISTRIBUICAO DE RECURSOS (Nivel: Baixa Interatividade):
- ~70% dos slides devem ser de conteudo didatico (type="content")
- ~15% quizzes de fixacao (type="quiz") - 1 por modulo
- ~10% flashcards ou outro recurso leve habilitado
- ~5% resumo/titulo
- Priorize clareza e profundidade textual sobre interatividade.""",
        'media': """DISTRIBUICAO DE RECURSOS (Nivel: Media Interatividade - BALANCEADO):
- ~45% dos slides devem ser de conteudo didatico (type="content")
- ~12% quizzes de fixacao (type="quiz") - 1 por modulo
- ~13% simuladores/jogos educativos (type="simulator") - 1 por modulo
- ~8% cenarios de desafio (type="scenario") - decisoes interativas
- ~7% infograficos interativos (type="infographic") - dados visuais
- ~5% flashcards (type="flashcard") - revisao
- ~5% linhas do tempo (type="timeline") - cronologia
- ~5% estudos de caso (type="case_study") - casos reais
- VARIE os tipos de recursos entre os modulos para manter engajamento.""",
        'alta': """DISTRIBUICAO DE RECURSOS (Nivel: Alta Interatividade):
- ~30% dos slides devem ser de conteudo didatico (type="content")
- ~12% quizzes (type="quiz")
- ~15% simuladores/jogos educativos (type="simulator") - 1-2 por modulo, VARIE os tipos
- ~10% cenarios de desafio (type="scenario") - arvore de decisoes
- ~8% infograficos interativos (type="infographic")
- ~7% flashcards (type="flashcard")
- ~7% linhas do tempo (type="timeline")
- ~6% estudos de caso (type="case_study")
- ~5% cenas com avatar (type="avatar_scene") - max 2-3 no curso todo
- PRIORIZE diversidade: NUNCA coloque dois slides do mesmo tipo interativo seguidos.
- Cada modulo deve ter PELO MENOS 3 tipos diferentes de recursos interativos.""",
        'maxima': """DISTRIBUICAO DE RECURSOS (Nivel: Maxima Interatividade):
- ~20% dos slides devem ser de conteudo didatico (type="content") - breves e objetivos
- ~10% quizzes (type="quiz")
- ~16% simuladores/jogos educativos (type="simulator") - 2 por modulo, tipos DIFERENTES
- ~12% cenarios de desafio (type="scenario") - arvores complexas
- ~10% infograficos interativos (type="infographic")
- ~8% flashcards (type="flashcard")
- ~8% linhas do tempo (type="timeline")
- ~8% estudos de caso (type="case_study")
- ~8% cenas com avatar (type="avatar_scene") - max 3 no curso
- A MAIORIA dos slides deve ser interativa. Conteudo puro deve ser MINIMO.
- Cada modulo OBRIGATORIAMENTE tem pelo menos 4 tipos de recursos diferentes.
- VARIE ao maximo: nunca repita o mesmo tipo de recurso em sequencia.""",
    }

    balance_rules = dist_instructions.get(resource_balance, dist_instructions['media'])

    # Filter rules to only mention enabled resources
    disabled_types = [k for k, v in resource_type_map.items() if not enabled_resources.get(k, False)]
    if disabled_types:
        disabled_note = f"\nRECURSOS DESABILITADOS (NAO USE estes types): {', '.join(disabled_types)}. Redistribua a % deles para os recursos habilitados."
    else:
        disabled_note = ""

    prompt = f"""Crie a estrutura pedagógica completa para um curso digital baseado no conteúdo e configuração abaixo.

CONFIGURAÇÃO:
- Título: {config.get('title', 'Curso')}
- Nível: {config.get('depth', 'intermediario')}
- Duração alvo: {config.get('duration', 30)} minutos
- Módulos: {config.get('modules', 3)}
- Formato: {config.get('format', 'curso_completo')}

CONTEÚDO BASE:
{content_text[:10000]}

Retorne um JSON com a estrutura:
```json
{{
  "courseTitle": "Título do Curso",
  "courseDescription": "Descrição detalhada",
  "learningObjectives": ["objetivo 1", "objetivo 2"],
  "prerequisites": ["pré-requisito 1"],
  "competencies": ["competência 1"],
  "modules": [
    {{
      "id": "mod1",
      "title": "Título do Módulo",
      "description": "Descrição",
      "slides": [
        {{
          "id": "slide1",
          "title": "Título do Slide",
          "type": "{available_types}",
          "purpose": "Breve descrição do objetivo deste slide",
          "estimatedDuration": 30
        }}
      ]
    }}
  ],
  "totalSlides": 10,
  "totalDuration": 30
}}
```

{balance_rules}{disabled_note}

REGRAS GERAIS:
- Primeiro slide deve ser uma capa/título do curso
- Último slide deve ser um resumo/conclusão
- Aplique progressão de complexidade
- Use microlearning: máximo 3 conceitos por slide
- CUMPRA a distribuição acima com precisão. Conte os slides de cada tipo antes de finalizar.
- Distribua os recursos de forma INTERCALADA - não agrupe todos os quizzes no final, etc."""

    models = [PRIMARY_MODEL, FALLBACK_MODEL]
    for provider, model in models:
        try:
            chat = _new_chat(f"agent-structure-{session_id}", provider=provider, model=model)
            response = await chat.send_message(UserMessage(text=prompt))
            data = _extract_json(response)
            if data:
                return data
        except Exception as e:
            logger.warning(f"Structure with {provider}/{model} failed: {str(e)[:80]}")
            continue
    raise ValueError("Não foi possível gerar a estrutura do curso")


async def generate_storyboard(session_id: str, content_text: str, structure: dict, config: dict, progress_callback=None) -> dict:
    """Step 3: Generate detailed storyboard - processes slides in batches to avoid timeouts."""
    all_slides = []

    # Flatten all slides from structure
    flat_slides = []
    for mod in structure.get("modules", []):
        for sl in mod.get("slides", []):
            flat_slides.append({**sl, "moduleName": mod.get("title", "")})

    # Process in batches of 4 slides (smaller batches = richer content per slide)
    batch_size = 4
    total_batches = (len(flat_slides) + batch_size - 1) // batch_size
    batch_num = 0
    for batch_start in range(0, len(flat_slides), batch_size):
        batch = flat_slides[batch_start:batch_start + batch_size]
        batch_num += 1
        batch_info = [{"id": s.get("id",""), "title": s.get("title",""), "type": s.get("type","content"), "purpose": s.get("purpose",""), "moduleName": s.get("moduleName","")} for s in batch]

        # Report progress
        if progress_callback:
            try:
                await progress_callback(batch_num, total_batches, f"Gerando slides {batch_start+1}-{min(batch_start+batch_size, len(flat_slides))} de {len(flat_slides)}...")
            except Exception:
                pass

        prompt = f"""Você é um designer instrucional experiente. Gere conteúdo DETALHADO, APROFUNDADO e EDUCACIONAL para {len(batch)} slides do curso "{config.get('title', '')}".

Nível do curso: {config.get('depth', 'intermediario')}

CONTEÚDO-BASE COMPLETO para referência:
{content_text[:6000]}

IMPORTANTE SOBRE IMAGENS DO CONTEÚDO-BASE:
Se o CONTEÚDO-BASE acima contiver marcadores no formato `[IMG:filename.png]`, significa que o PDF/documento original possui imagens reais (diagramas, fotos, fluxogramas) já extraídas. Mantenha esses marcadores EXATAMENTE como estão dentro do HTML do slide apropriado (geralmente em um `<p>` ou no final do bloco) para preservar o material didático original. NÃO invente nomes novos de imagem, NÃO altere os nomes dos arquivos, e NÃO remova os marcadores — eles serão substituídos automaticamente por elementos de imagem reais depois da geração.

Slides a gerar: {json.dumps(batch_info, ensure_ascii=False)}

Retorne JSON:
```json
{{"slides":[{{
  "id":"id_do_slide",
  "title":"Título do Slide",
  "type":"content",
  "moduleName":"Nome do Módulo",
  "imageKeywords":"english keywords for relevant photo",
  "elements":[
    {{"type":"text","content":"<h2>Título Principal</h2><h3>Subtítulo da Seção</h3><p>Parágrafo introdutório detalhado explicando o conceito principal com contexto e relevância prática. Este parágrafo deve ter no mínimo 3-4 frases completas.</p><h3>Pontos-Chave</h3><ul><li><strong>Primeiro ponto:</strong> Explicação detalhada com exemplo prático do mundo real</li><li><strong>Segundo ponto:</strong> Descrição aprofundada com dados ou estatísticas quando relevante</li><li><strong>Terceiro ponto:</strong> Aplicação prática e como implementar no dia a dia</li></ul><h3>Na Prática</h3><p>Parágrafo explicando como aplicar este conhecimento no contexto profissional, com exemplos concretos e situações reais.</p>","position":"left","width":1050,"height":680}}
  ],
  "narrationScript":"Narração completa e detalhada para acompanhar este slide. Deve ser fluida, natural e cobrir todos os pontos do slide em pelo menos 5-6 frases.",
  "librasScript":"Versão simplificada para LIBRAS mantendo os conceitos essenciais",
  "notes":"Dicas para o instrutor sobre como apresentar este conteúdo",
  "quizQuestions":[]
}}]}}
```

REGRAS CRÍTICAS DE QUALIDADE:

SLIDES DE CONTEÚDO (type="content"):
- MÍNIMO 150 palavras de texto por slide, NUNCA menos que isso
- Use estrutura HTML rica: <h2> para título, <h3> para sub-seções, <p> para parágrafos, <ul><li> para listas
- Cada slide DEVE ter: 1 parágrafo introdutório (3-4 frases), 1 lista com 3-5 itens detalhados, 1 parágrafo de aplicação prática
- Use <strong> para termos importantes, <em> para ênfase
- Inclua exemplos reais, dados, estatísticas e casos práticos
- O conteúdo deve ser educacional, aprofundado e útil para o aluno

SLIDES DE TÍTULO (type="title"):
- Use <h1> para título principal grande e impactante
- Adicione <p> com descrição do que será abordado no módulo (2-3 frases)

SLIDES DE QUIZ (type="quiz"):
- OBRIGATÓRIO: inclua exatamente 3 perguntas no campo "quizQuestions"
- Cada pergunta DEVE ter: "text" (pergunta clara), "type": "multiple_choice", "alternatives" (4 opções, exatamente 1 com "isCorrect":true), "explanation" (explicação detalhada de por que a resposta está correta)
- As perguntas devem testar compreensão REAL do conteúdo, não memorização superficial
- Formato: {{"text":"Pergunta?","type":"multiple_choice","alternatives":[{{"text":"Opção A","isCorrect":false}},{{"text":"Opção B","isCorrect":true}},{{"text":"Opção C","isCorrect":false}},{{"text":"Opção D","isCorrect":false}}],"explanation":"A resposta correta é B porque..."}}

SLIDES DE RESUMO (type="summary"):
- Resuma TODOS os pontos-chave do módulo com <ul><li>
- Cada item deve ser uma frase completa, não apenas uma palavra
- Adicione um parágrafo final de conclusão

SLIDES DE CENÁRIO (type="scenario"):
- USE ESTE TIPO quando o tema envolver tomada de decisão, liderança, atendimento, ética ou situações práticas
- NÃO CONFUNDA com slide de conteúdo: type="scenario" gera simulação INTERATIVA com árvore de decisões
- NÃO gere conteúdo de texto para cenários, a IA gerará automaticamente
- Apenas forneça: "scenarioTheme" (tema do cenário relacionado ao módulo), "scenarioObjectives" (objetivos de aprendizagem que o cenário testará), "scenarioAudience" (público-alvo)
- Formato no elements: [{{"type":"scenario","scenarioTheme":"tema","scenarioObjectives":"objetivos","scenarioAudience":"público"}}]

SLIDES DE SIMULADOR/JOGO EDUCATIVO (type="simulator"):
- OBRIGATÓRIO em cada módulo: pelo menos 1 slide simulador/jogo educativo interativo
- Gere um documento HTML COMPLETO e FUNCIONAL com CSS e JavaScript embutidos
- O HTML será renderizado dentro de um iframe isolado de 960x540px
- O elemento deve ter: {{"type":"html","htmlContent":"<!DOCTYPE html><html>...</html>"}}
- TIPOS DE JOGOS/SIMULADORES que você DEVE criar (escolha o mais adequado ao conteúdo):

  JOGOS EDUCATIVOS (foco em fixação e engajamento):
  * Forca Educacional: Jogo de adivinhação de palavras/termos do curso com dicas pedagógicas. Ideal para memorizar termos, conceitos, siglas e vocabulários. Mostre um boneco sendo desenhado, letras clicáveis e dicas contextuais.
  * Bate-pênalti com perguntas: Quiz onde o aluno responde perguntas para determinar a força/direção do chute. Mostre um campo de futebol, goleiro e bola animada. Respostas corretas = gol, erradas = defesa. Placar e rodadas.
  * Jogo de acerto ao alvo: Conceitos corretos/incorretos aparecem na tela como alvos móveis. O aluno deve clicar apenas nas opções CORRETAS. Excelente para diferenciar certo x errado em compliance e operacional. Timer e pontuação.
  * Jogo da memória educativa: Cartas que combinam perguntas com respostas relacionadas ao conteúdo. Trabalha associação mental e retenção. Grade de cartas com animação de virar, contador de tentativas e pares encontrados.
  * Quiz gamificado com barra de energia: Sistema de perguntas com "vida" ou barra de energia que sobe com acertos e desce com erros. Feedback visual colorido, progresso, animações de sucesso/erro. Gera senso de desafio e progressão.

  SIMULADORES INTERATIVOS (foco em aplicação prática):
  * Calculadora temática (ex: ROI, risco, custo-benefício, dosagem)
  * Jogo de arrastar e soltar (drag-and-drop para classificação/ordenação)
  * Flashcards interativos (virar carta com conceito/definição, deck navegável)
  * Linha do tempo interativa (eventos/etapas clicáveis com detalhes)
  * Simulador de processo passo-a-passo com decisões
  * Painel de diagnóstico/avaliação com indicadores visuais
  * Jogo de ordenação (colocar etapas na ordem correta, drag ou clique)
  * Completar lacunas interativo (fill-in-the-blanks com validação)

- REGRAS DO HTML:
  1. Deve ser um documento HTML completo: <!DOCTYPE html><html><head><style>...</style></head><body>...<script>...</script></body></html>
  2. CSS: Design moderno e atraente com gradientes, sombras, border-radius, transições, animações CSS (keyframes para celebração, shake para erro, etc.)
  3. JavaScript: TODA interatividade deve funcionar - botões onclick, drag-and-drop, cliques, feedback visual dinâmico, sons visuais (animações que simulam feedback)
  4. Use cores vibrantes e profissionais, fonte legível (sans-serif)
  4.1 ⚠️ CONTRASTE OBRIGATÓRIO: Para CADA elemento com texto (cards, items arrastáveis, botões, opções, labels):
       - SE o background do elemento é claro (branco/pastel/cinza claro/azul claro), o `color` do texto DEVE ser escuro (#0f172a, #1e293b, #1f2937 ou similar)
       - SE o background é escuro (preto/azul-marinho/roxo escuro), o `color` DEVE ser claro (#ffffff, #f1f5f9)
       - NUNCA use `color: white` em background claro — produz texto invisível
       - NUNCA use `color: black` em background escuro
       - Em dúvida, declare EXPLICITAMENTE `color` E `background-color` no MESMO seletor CSS para evitar herança acidental
  5. Dimensões do conteúdo: 960x540 pixels (não use scroll, tudo deve caber na tela)
  6. Inclua: título do jogo, instruções breves, pontuação/progresso e feedback ao aluno
  7. NUNCA gere HTML vazio ou estático - todo jogo DEVE ter interação real via JavaScript
  8. Use emojis nos textos para tornar mais visual e engajante
  9. Inclua efeitos de celebração para acertos (confetti CSS, animação de estrelas) e feedback para erros (shake, cor vermelha)
  10. O conteúdo do jogo DEVE estar 100% relacionado ao tema do módulo/curso
  11. Ao final do jogo, mostre resultado/pontuação com mensagem motivacional
  12. Os jogos devem focar em: fixação de conteúdo, engajamento emocional, repetição ativa, aprendizagem baseada em desafio e feedback imediato
- NÃO inclua "narrationScript" detalhado para simuladores (o aluno interage diretamente)
- Formato: {{"type":"html","htmlContent":"<!DOCTYPE html><html lang='pt-BR'>..."}}

SLIDES DE CENA COM AVATAR (type="avatar_scene"):
- Use este tipo quando um apresentador/instrutor virtual agregaria valor pedagógico real
- Ideal para: explicar conceitos abstratos, dar boas-vindas, resumir módulos, demonstrar procedimentos
- Sugira NO MÁXIMO 2-3 slides deste tipo por curso (avatar consome créditos de API)
- O slide deve conter texto de apoio visual (bullet points, título) complementando o que o avatar fala
- Inclua campo "avatarScene" com metadados da cena:
  - "narrationScript": texto completo que o avatar falará (max 1500 chars, tom natural e didático)
  - "backgroundPrompt": prompt em inglês para gerar imagem de fundo (ex: "Modern classroom with digital whiteboard")
  - "avatarPosition": "left", "right" ou "center"
- Layout sugerido:
  - Avatar à esquerda: conteúdo textual ocupa a metade direita (x:960, width:900)
  - Avatar à direita: conteúdo textual ocupa a metade esquerda (x:60, width:900)
  - Avatar centralizado: conteúdo textual acima ou abaixo
- Formato: {{"type":"text","content":"<h2>Título</h2><ul><li>Ponto 1</li></ul>","width":900,"height":600,"x":960,"y":110}}
- avatarScene: {{"narrationScript":"Olá! Vou explicar...","backgroundPrompt":"Professional studio","avatarPosition":"left"}}

SLIDES DE INFOGRAFICO INTERATIVO (type="infographic"):
- Gere um documento HTML COMPLETO com visualização de dados interativa
- Ideal para: estatísticas, comparações, processos, hierarquias, dados quantitativos
- O HTML será renderizado dentro de um iframe isolado de 960x540px
- O elemento deve ter: {{"type":"html","htmlContent":"<!DOCTYPE html><html>...</html>"}}
- TIPOS DE INFOGRÁFICOS:
  * Gráfico de barras/pizza animado com dados do curso (CSS animations)
  * Diagrama de processo com etapas clicáveis que revelam detalhes
  * Comparativo visual (antes/depois, prós/contras) com hover effects
  * Painel de KPIs/métricas com contadores animados
  * Mapa mental/conceitual SVG com nós clicáveis
  * Pirâmide/funil interativo com camadas expansíveis
- REGRAS: Design moderno, cores vibrantes, animações de entrada (fade-in, slide-up), hover effects em cada elemento, tooltips com informações extras
- Os dados devem ser 100% baseados no conteúdo real do módulo
- NÃO inclua "narrationScript" detalhado (aluno interage diretamente)

SLIDES DE FLASHCARD (type="flashcard"):
- Gere um documento HTML COMPLETO com sistema de flashcards interativos
- Ideal para: revisão de termos, conceitos-chave, vocabulário técnico, definições
- O HTML será renderizado dentro de um iframe isolado de 960x540px
- O elemento deve ter: {{"type":"html","htmlContent":"<!DOCTYPE html><html>...</html>"}}
- FUNCIONALIDADES OBRIGATÓRIAS:
  * Mínimo 5 cartões com frente (pergunta/termo) e verso (resposta/definição)
  * Animação 3D de flip ao clicar no cartão (CSS transform: rotateY)
  * Navegação entre cartões (setas ou swipe)
  * Contador de progresso (cartão 3 de 8)
  * Botões "Sei" / "Não sei" para auto-avaliação
  * Resultado final com % de acertos
- Design: Cartões com bordas arredondadas, sombras, gradientes sutis, fonte clara
- O conteúdo deve cobrir os conceitos mais importantes do módulo

SLIDES DE LINHA DO TEMPO (type="timeline"):
- Gere um documento HTML COMPLETO com linha do tempo interativa
- Ideal para: evolução histórica, etapas de processo, cronologia, fases de projeto
- O HTML será renderizado dentro de um iframe isolado de 960x540px
- O elemento deve ter: {{"type":"html","htmlContent":"<!DOCTYPE html><html>...</html>"}}
- FUNCIONALIDADES OBRIGATÓRIAS:
  * Linha do tempo horizontal ou vertical com mínimo 5 marcos
  * Cada marco é clicável e expande detalhes (título, descrição, ícone)
  * Animação de scroll/navegação entre os marcos
  * Indicador visual de progresso na timeline
  * Destaque visual do marco ativo (cor, tamanho, brilho)
  * Transições suaves entre marcos (CSS transitions)
- Design: Linha conectora estilizada, nós circulares com ícones/números, cards de detalhes com sombra
- Conteúdo baseado na cronologia real do tema do módulo

SLIDES DE ESTUDO DE CASO (type="case_study"):
- Gere um documento HTML COMPLETO com estudo de caso interativo
- Ideal para: aplicação prática, análise de cenários reais, reflexão crítica
- O HTML será renderizado dentro de um iframe isolado de 960x540px
- O elemento deve ter: {{"type":"html","htmlContent":"<!DOCTYPE html><html>...</html>"}}
- ESTRUTURA OBRIGATÓRIA:
  * Apresentação do caso (contexto, empresa/situação fictícia mas realista)
  * Dados e evidências visuais (números, gráficos simples)
  * 3-4 perguntas de reflexão que o aluno pode clicar para ver sugestão de resposta
  * Seção "Lições Aprendidas" revelável ao final
  * Botão "Revelar Análise" que mostra a análise completa do caso
- Design: Layout de "documento" profissional, seções bem separadas, destaque em dados importantes, accordion para revelar conteúdo
- O caso deve ser relevante e aplicável ao tema do módulo

PARA TODOS OS SLIDES:
- imageKeywords: 2-3 palavras em INGLÊS descrevendo uma foto profissional relevante
- moduleName: SEMPRE inclua o nome do módulo
- narrationScript: MÍNIMO 5 frases completas e detalhadas
- NUNCA retorne conteúdo vazio ou com apenas 1-2 linhas"""

        retries = 0
        max_retries = 2
        batch_success = False
        models = [PRIMARY_MODEL, FALLBACK_MODEL, FALLBACK_MODEL]  # Fallback chain
        while retries <= max_retries:
            provider, model = models[min(retries, len(models)-1)]
            try:
                chat = _new_chat(f"{session_id}_story_b{batch_start}_r{retries}", provider=provider, model=model)
                response = await chat.send_message(UserMessage(text=prompt))
                data = _extract_json(response)
                if data and "slides" in data:
                    for j, slide_data in enumerate(data["slides"]):
                        if not slide_data.get("moduleName") and j < len(batch):
                            slide_data["moduleName"] = batch[j].get("moduleName", "")
                    all_slides.extend(data["slides"])
                    batch_success = True
                    if retries > 0:
                        logger.info(f"Storyboard batch {batch_start} succeeded with {provider}/{model}")
                    break
                retries += 1
                if retries <= max_retries:
                    await asyncio.sleep(2)
            except Exception as e:
                error_str = str(e)
                if "Budget has been exceeded" in error_str:
                    raise Exception("BUDGET_EXCEEDED: O orçamento da chave Universal foi excedido. Acesse Perfil > Universal Key > Adicionar Saldo para continuar.")
                retries += 1
                if retries <= max_retries:
                    next_provider, next_model = models[min(retries, len(models)-1)]
                    logger.warning(f"Storyboard batch {batch_start} failed with {provider}/{model}, trying {next_provider}/{next_model}: {error_str[:80]}")
                    await asyncio.sleep(2)
                else:
                    logger.warning(f"Storyboard batch {batch_start} failed all retries: {error_str[:100]}")
                    break

        # If batch failed, use fallback content
        if not batch_success:
            for sl in batch:
                if any(s.get("title") == sl.get("title") for s in all_slides):
                    continue
                purpose = sl.get("purpose", "")
                title_text = sl.get("title", "Slide")
                module_text = sl.get("moduleName", "Módulo")
                stype = sl.get("type", "content")

                if stype == "content":
                    fallback_html = f"""<h2>{title_text}</h2>
<p>{purpose if purpose else 'Este slide aborda conceitos fundamentais sobre ' + title_text.lower() + '.'} É importante compreender estes fundamentos para aplicar corretamente no ambiente profissional.</p>
<h3>Aspectos Principais</h3>
<ul>
<li><strong>Conceito base:</strong> {title_text} envolve uma série de práticas e conhecimentos essenciais para garantir resultados eficazes.</li>
<li><strong>Aplicação prática:</strong> No dia a dia, estes conceitos se traduzem em ações concretas que melhoram a qualidade e a segurança das operações.</li>
<li><strong>Importância:</strong> Dominar este tema é fundamental para profissionais que buscam excelência na sua área de atuação.</li>
</ul>
<h3>Considerações</h3>
<p>A aplicação destes conceitos requer atenção contínua e atualização constante, pois as melhores práticas evoluem com o tempo e novas regulamentações podem surgir.</p>"""
                elif stype == "quiz":
                    fallback_html = f"<h2>Quiz: {module_text}</h2><p>Teste seus conhecimentos sobre os conceitos apresentados neste módulo.</p>"
                elif stype == "summary":
                    fallback_html = f"<h2>Resumo: {module_text}</h2><ul><li>Revisamos os conceitos fundamentais de {title_text.lower()}</li><li>Aprendemos como aplicar na prática profissional</li><li>Identificamos os pontos-chave para implementação</li></ul><p>Continue praticando estes conceitos para consolidar o aprendizado.</p>"
                else:
                    fallback_html = f"<h1>{title_text}</h1><p>{purpose if purpose else 'Bem-vindo ao módulo ' + module_text}</p>"

                fallback_quiz = []
                if stype == "quiz":
                    fallback_quiz = [
                        {"text": f"Qual é o principal objetivo de {title_text.lower().replace('quiz do módulo', 'este módulo').replace('quiz -', '')}?",
                         "type": "multiple_choice",
                         "alternatives": [{"text": "Apenas cumprir requisitos formais", "isCorrect": False}, {"text": "Garantir a aplicação correta dos conceitos apresentados", "isCorrect": True}, {"text": "Substituir a prática profissional", "isCorrect": False}, {"text": "Apenas memorizar termos técnicos", "isCorrect": False}],
                         "explanation": "O objetivo principal é garantir a aplicação correta dos conceitos na prática profissional."},
                        {"text": f"Sobre o conteúdo de {module_text}, qual afirmação é correta?",
                         "type": "multiple_choice",
                         "alternatives": [{"text": "O conhecimento teórico é suficiente por si só", "isCorrect": False}, {"text": "A prática é irrelevante quando se domina a teoria", "isCorrect": False}, {"text": "A integração entre teoria e prática é essencial", "isCorrect": True}, {"text": "Não é necessário atualização contínua", "isCorrect": False}],
                         "explanation": "A integração entre teoria e prática é essencial para uma atuação profissional eficaz."},
                    ]

                all_slides.append({
                    "id": sl.get("id", ""),
                    "title": title_text,
                    "type": stype,
                    "moduleName": module_text,
                    "imageKeywords": title_text.split(" ")[0].lower() + " professional",
                    "elements": [{"type": "text", "content": fallback_html, "position": "left", "width": 1050, "height": 680}],
                    "narrationScript": purpose if purpose else f"Neste slide, vamos abordar {title_text.lower()}.",
                    "librasScript": purpose if purpose else title_text,
                    "notes": "",
                    "quizQuestions": fallback_quiz,
                })

    return {"slides": all_slides}


# ========== VISUAL COURSE GENERATION ==========

# ========== DESIGN TEMPLATES (Visual Themes) ==========

DESIGN_TEMPLATES = [
    {
        "id": "clean-light",
        "name": "Minimal Claro",
        "description": "Despoluído e moderno: fundo claro, tipografia grande e muito respiro",
        "preview": "linear-gradient(135deg, #fafaf9 0%, #e7e5e4 100%)",
        "mode": "light",
        "palette": {"primary": "#1c1917", "accent": "#2563eb", "accentLight": "#dbeafe", "contentBg": "#fafaf9", "coverBg": "#fafaf9", "text": "#1c1917"},
        "fonts": {"heading": "'Manrope', 'Segoe UI', sans-serif", "body": "'Source Sans 3', 'Segoe UI', sans-serif"},
        "headerStyle": "clean",
        "cornerRadius": "14px",
    },
    {
        "id": "clean-slate",
        "name": "Minimal Slate",
        "description": "Neutro e sofisticado com destaque teal, ideal para treinamentos corporativos",
        "preview": "linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)",
        "mode": "light",
        "palette": {"primary": "#0f172a", "accent": "#0d9488", "accentLight": "#ccfbf1", "contentBg": "#f8fafc", "coverBg": "#f8fafc", "text": "#0f172a"},
        "fonts": {"heading": "'Sora', 'Segoe UI', sans-serif", "body": "'Source Sans 3', sans-serif"},
        "headerStyle": "clean",
        "cornerRadius": "14px",
    },
    {
        "id": "editorial",
        "name": "Editorial",
        "description": "Tipografia serifada estilo revista, elegante e altamente legível",
        "preview": "linear-gradient(135deg, #fffef9 0%, #f5f0e4 100%)",
        "mode": "light",
        "palette": {"primary": "#292524", "accent": "#b45309", "accentLight": "#fef3c7", "contentBg": "#fffef9", "coverBg": "#fffef9", "text": "#292524"},
        "fonts": {"heading": "'Fraunces', 'Georgia', serif", "body": "'Source Serif 4', 'Georgia', serif"},
        "headerStyle": "clean",
        "cornerRadius": "10px",
    },
    {
        "id": "corporate-clean",
        "name": "Corporativo Clean",
        "description": "Branco puro com azul profundo: formal, direto e despoluído",
        "preview": "linear-gradient(135deg, #ffffff 0%, #dbeafe 100%)",
        "mode": "light",
        "palette": {"primary": "#1e293b", "accent": "#1d4ed8", "accentLight": "#dbeafe", "contentBg": "#ffffff", "coverBg": "#ffffff", "text": "#1e293b"},
        "fonts": {"heading": "'Archivo', 'Segoe UI', sans-serif", "body": "'Source Sans 3', sans-serif"},
        "headerStyle": "clean",
        "cornerRadius": "12px",
    },
    {
        "id": "clean-dark",
        "name": "Escuro Elegante",
        "description": "Escuro neutro sem neon, com verde-menta discreto",
        "preview": "linear-gradient(135deg, #121417 0%, #1f2937 100%)",
        "mode": "dark",
        "palette": {"primary": "#121417", "accent": "#34d399", "accentLight": "#064e3b", "contentBg": "#121417", "coverBg": "#121417", "text": "#f4f4f5"},
        "fonts": {"heading": "'Space Grotesk', 'Segoe UI', sans-serif", "body": "'IBM Plex Sans', sans-serif"},
        "headerStyle": "clean",
        "cornerRadius": "14px",
    },
    {
        "id": "clean-dark-blue",
        "name": "Escuro Profundo",
        "description": "Azul-noite com destaque celeste, moderno e confortável",
        "preview": "linear-gradient(135deg, #0f1524 0%, #1e293b 100%)",
        "mode": "dark",
        "palette": {"primary": "#0f1524", "accent": "#60a5fa", "accentLight": "#1e3a5f", "contentBg": "#0f1524", "coverBg": "#0f1524", "text": "#e2e8f0"},
        "fonts": {"heading": "'Manrope', sans-serif", "body": "'IBM Plex Sans', sans-serif"},
        "headerStyle": "clean",
        "cornerRadius": "14px",
    },
]

def get_design_templates():
    """Return available design templates for the frontend."""
    return DESIGN_TEMPLATES

def get_design_template_by_id(template_id: str) -> dict:
    """Get a specific design template, or return default (educacional)."""
    for t in DESIGN_TEMPLATES:
        if t["id"] == template_id:
            return t
    return DESIGN_TEMPLATES[0]  # default: clean-light

# Legacy palettes (kept for backward compatibility, mapped from design templates)
_COURSE_PALETTES = [t["palette"] for t in DESIGN_TEMPLATES]


async def _fetch_stock_image(keyword: str, project_dir: str, project_id: str) -> Optional[str]:
    """Generate an AI image using Gemini Nano Banana and save locally."""
    try:
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"img_{uuid.uuid4().hex[:8]}",
            system_message="You are an image generator.",
        ).with_model(IMAGE_MODEL[0], IMAGE_MODEL[1]).with_params(modalities=["image", "text"])

        prompt = f"Professional photorealistic image for an educational course slide about: {keyword}. High quality, clean composition, no text or watermarks, suitable for corporate training material."
        text_resp, images = await chat.send_message_multimodal_response(UserMessage(text=prompt))

        if images and len(images) > 0:
            import hashlib
            seed = hashlib.md5(keyword.encode(), usedforsecurity=False).hexdigest()[:10]
            fname = f"ai_img_{seed}.png"
            fpath = os.path.join(project_dir, project_id, "assets", fname)
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            img_bytes = base64.b64decode(images[0]['data'])
            with open(fpath, "wb") as f:
                f.write(img_bytes)
            logger.info(f"AI image generated (Gemini) for '{keyword}' -> {fname}")
            
            # Persist in MongoDB async for production environments with ephemeral storage
            try:
                from services.asset_store import store_asset_async
                _db = await _get_motor_db()
                if _db is not None:
                    await store_asset_async(_db, project_id, fname, fpath)
                    logger.info(f"AI image persisted in MongoDB: {project_id}/{fname}")
            except Exception as e:
                logger.warning(f"Failed to persist AI image in MongoDB (attempt 1): {e}")
                # Retry once after brief delay
                try:
                    import asyncio as _aio2
                    await _aio2.sleep(2)
                    _db = await _get_motor_db()
                    if _db is not None:
                        await store_asset_async(_db, project_id, fname, fpath)
                        logger.info(f"AI image persisted in MongoDB on retry: {project_id}/{fname}")
                except Exception as e2:
                    logger.error(f"Failed to persist AI image in MongoDB (attempt 2): {e2}")
            
            # Auto-save to image gallery
            img_url = f"/api/projects/{project_id}/assets/{fname}"
            import asyncio as _asyncio
            try:
                _asyncio.ensure_future(_auto_save_gallery(img_url, keyword, project_id))
            except Exception:
                pass
            
            return img_url
    except Exception as e:
        logger.warning(f"AI image generation failed for '{keyword}': {str(e)[:80]}")
    # Fallback to picsum
    return await _fetch_picsum_image(keyword, project_dir, project_id)


async def _auto_save_gallery(image_url: str, keywords: str, project_id: str):
    """Auto-save generated image to gallery (fire-and-forget)."""
    try:
        _db = await _get_motor_db()
        if _db is None:
            return
        existing = await _db.image_gallery.find_one({"imageUrl": image_url})
        if not existing:
            # Get project info for context
            project = await _db.projects.find_one({"id": project_id}, {"_id": 0, "name": 1, "userId": 1, "companyId": 1})
            doc = {
                "_id": str(uuid.uuid4()),
                "id": str(uuid.uuid4()),
                "imageUrl": image_url,
                "keywords": keywords,
                "projectId": project_id,
                "projectName": project.get("name", "") if project else "",
                "userId": project.get("userId", "") if project else "",
                "companyId": project.get("companyId", "") if project else "",
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
            await _db.image_gallery.insert_one(doc)
            logger.info(f"Image auto-saved to gallery: {image_url}")
    except Exception as e:
        logger.warning(f"Gallery auto-save failed (non-fatal): {e}")


async def _fetch_picsum_image(keyword: str, project_dir: str, project_id: str) -> Optional[str]:
    """Fallback: Download a stock image from picsum.photos."""
    import httpx
    import hashlib
    try:
        seed = hashlib.md5(keyword.encode(), usedforsecurity=False).hexdigest()[:10]
        url = f"https://picsum.photos/seed/{seed}/800/450"
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                fname = f"stock_{seed}.jpg"
                fpath = os.path.join(project_dir, project_id, "assets", fname)
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, "wb") as f:
                    f.write(resp.content)
                
                # Persist in MongoDB async for production environments with ephemeral storage
                try:
                    from services.asset_store import store_asset_async
                    _db = await _get_motor_db()
                    if _db is not None:
                        await store_asset_async(_db, project_id, fname, fpath)
                        logger.info(f"Stock image persisted in MongoDB: {project_id}/{fname}")
                except Exception as e:
                    logger.warning(f"Failed to persist stock image in MongoDB (attempt 1): {e}")
                    try:
                        import asyncio as _aio3
                        await _aio3.sleep(2)
                        _db = await _get_motor_db()
                        if _db is not None:
                            await store_asset_async(_db, project_id, fname, fpath)
                    except Exception:
                        pass
                
                return f"/api/projects/{project_id}/assets/{fname}"
    except Exception as e:
        logger.warning(f"Picsum fetch failed for '{keyword}': {e}")
    return None


def _tokens(palette: dict) -> dict:
    """Design tokens derived from the palette. All builders read colors
    from here so light/dark themes stay consistent everywhere."""
    mode = palette.get("mode", "light")
    accent = palette["accent"]
    if mode == "dark":
        return {
            "mode": "dark", "accent": accent,
            "text": palette.get("text", "#f4f4f5"),
            "muted": "rgba(244,244,245,0.62)",
            "faint": "rgba(244,244,245,0.38)",
            "card_bg": "rgba(255,255,255,0.045)",
            "card_border": "rgba(255,255,255,0.10)",
            "heading": palette.get("fontHeading", "'Manrope', sans-serif"),
            "body": palette.get("fontBody", "'Source Sans 3', sans-serif"),
            "radius": palette.get("cornerRadius", "14px"),
        }
    text = palette.get("text", "#1c1917")
    return {
        "mode": "light", "accent": accent,
        "text": text,
        "muted": f"{text}b3",   # ~70%
        "faint": f"{text}66",   # ~40%
        "card_bg": "#ffffff",
        "card_border": "rgba(0,0,0,0.08)",
        "heading": palette.get("fontHeading", "'Manrope', sans-serif"),
        "body": palette.get("fontBody", "'Source Sans 3', sans-serif"),
        "radius": palette.get("cornerRadius", "14px"),
    }


def _build_title_slide(sb_slide: dict, palette: dict, course_title: str, module_names: list) -> dict:
    """Clean, modern cover slide: big left-aligned typography, one accent
    detail, generous whitespace. Only 2 simple elements → easy to edit."""
    from models import generate_id
    tk = _tokens(palette)
    accent = tk["accent"]
    elements = []

    title_text = sb_slide.get("title", course_title)
    elements_html = sb_slide.get("elements", [])
    subtitle = ""
    for el in elements_html:
        c = el.get("content", "")
        if "<p>" in c:
            import re
            p_match = re.search(r"<p>(.*?)</p>", c, re.DOTALL)
            if p_match:
                subtitle = p_match.group(1).strip()
                break

    title_html = f'''<div style="text-align:left;padding:8px 0;">
<div style="width:52px;height:4px;background:{accent};border-radius:2px;margin-bottom:36px;"></div>
<h1 style="font-family:{tk["heading"]};font-size:62px;font-weight:700;letter-spacing:-1.5px;color:{tk["text"]};margin:0 0 24px 0;line-height:1.12;max-width:1240px;">{title_text}</h1>
{f'<p style="font-family:{tk["body"]};font-size:22px;color:{tk["muted"]};margin:0;max-width:880px;line-height:1.6;">{subtitle}</p>' if subtitle else ''}
</div>'''
    elements.append({
        "id": generate_id(), "type": "html", "x": 160, "y": 170, "width": 1600, "height": 380,
        "htmlContent": title_html,
        "style": {"fontFamily": tk["body"]}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.6, "delay": 0}],
    })

    # Module list — quiet numbered index, no chips/borders.
    if module_names:
        modules_html = f'<div style="text-align:left;"><p style="font-family:{tk["heading"]};font-size:13px;font-weight:600;color:{tk["faint"]};margin:0 0 18px 0;text-transform:uppercase;letter-spacing:2.5px;">Trilha do Curso</p>'
        modules_html += '<div style="display:flex;flex-wrap:wrap;gap:10px 44px;">'
        for idx, mn in enumerate(module_names):
            modules_html += f'<div style="display:flex;align-items:baseline;gap:10px;"><span style="font-family:{tk["heading"]};font-size:14px;font-weight:700;color:{accent};">{idx+1:02d}</span><span style="font-family:{tk["body"]};font-size:16px;color:{tk["muted"]};">{mn}</span></div>'
        modules_html += '</div></div>'
        elements.append({
            "id": generate_id(), "type": "html", "x": 160, "y": 580, "width": 1600, "height": 180,
            "htmlContent": modules_html,
            "style": {"fontFamily": tk["body"]}, "startTime": 0,
            "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.4}],
        })

    return elements


def _build_header_bar(palette: dict, left_text: str, right_text: str = "") -> str:
    """Minimal 'eyebrow' header: small uppercase module label with an
    accent tick — no bars, gradients or filled backgrounds."""
    tk = _tokens(palette)
    right_part = (
        f'<span style="color:{tk["faint"]};font-size:12px;margin-left:auto;'
        f'font-family:{tk["body"]};">{right_text}</span>'
    ) if right_text else ''
    return f'''<div style="width:100%;height:100%;display:flex;align-items:center;">
<div style="width:22px;height:3px;background:{tk["accent"]};border-radius:2px;margin-right:14px;"></div>
<span style="color:{tk["accent"]};font-size:13px;font-weight:600;letter-spacing:2.5px;text-transform:uppercase;font-family:{tk["heading"]};">{left_text}</span>
{right_part}</div>'''


def _build_content_slide(sb_slide: dict, palette: dict, module_name: str, image_url: Optional[str]) -> dict:
    """Build a visually rich content slide with header bar, text, and image."""
    from models import generate_id
    accent = palette["accent"]
    corner_radius = palette.get("cornerRadius", "12px")
    font_body = palette.get("fontBody", "'Inter', sans-serif")
    elements = []

    # Header bar (template-specific style)
    header_html = _build_header_bar(palette, module_name, sb_slide.get("title", ""))
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 36, "width": 1680, "height": 40,
        "htmlContent": header_html,
        "style": {}, "startTime": 0, "animations": [],
    })

    # Extract text content from storyboard elements
    text_content = ""
    for el in sb_slide.get("elements", []):
        c = el.get("content", "")
        if c:
            text_content = c

    # If we have an image, use two-column layout
    if image_url:
        styled_text = _style_content_html(text_content, palette["text"], palette)
        elements.append({
            "id": generate_id(), "type": "html", "x": 120, "y": 110, "width": 960, "height": 660,
            "htmlContent": styled_text,
            "style": {"fontFamily": font_body}, "startTime": 0,
            "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
        })
        # Image on the right — soft radius, no decorations
        elements.append({
            "id": generate_id(), "type": "image", "x": 1160, "y": 110, "width": 640, "height": 430,
            "src": image_url, "content": image_url,
            "style": {"borderRadius": corner_radius}, "startTime": 0,
            "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.3}],
        })
    else:
        # Comfortable reading column (not edge-to-edge)
        styled_text = _style_content_html(text_content, palette["text"], palette)
        elements.append({
            "id": generate_id(), "type": "html", "x": 120, "y": 110, "width": 1280, "height": 660,
            "htmlContent": styled_text,
            "style": {"fontFamily": font_body}, "startTime": 0,
            "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
        })

    return elements


def _build_quiz_slide(sb_slide: dict, palette: dict, module_name: str, question_ids: list) -> dict:
    """Build a quiz slide with actual Scormfy quiz element + visual header."""
    from models import generate_id
    accent = palette["accent"]
    font_heading = palette.get("fontHeading", "'Inter', sans-serif")
    font_body = palette.get("fontBody", "'Inter', sans-serif")
    elements = []

    # Header bar (template-specific)
    header_html = _build_header_bar(palette, f"QUIZ - {module_name}")
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 36, "width": 1680, "height": 40,
        "htmlContent": header_html,
        "style": {}, "startTime": 0, "animations": [],
    })

    # Quiz intro — clean, left-aligned, token colors (light/dark aware)
    tk = _tokens(palette)
    quiz_html = f'''<div style="text-align:left;padding:4px 0;">
<span style="display:inline-block;padding:6px 18px;border-radius:999px;background:{palette.get("accentLight", accent + "22")};color:{accent};font-size:13px;font-weight:600;letter-spacing:0.5px;font-family:{font_heading};">Hora de praticar</span>
<h2 style="font-family:{font_heading};font-size:34px;font-weight:700;letter-spacing:-0.5px;color:{tk["text"]};margin:18px 0 10px 0;">Teste seus conhecimentos</h2>
<p style="font-family:{font_body};font-size:19px;color:{tk["muted"]};margin:0;max-width:900px;line-height:1.6;">Responda às perguntas para verificar seu aprendizado sobre {module_name}.</p>
</div>'''
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 100, "width": 1500, "height": 190,
        "htmlContent": quiz_html,
        "style": {"fontFamily": palette.get("fontBody", "'Inter', sans-serif")}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
    })

    # Actual Scormfy quiz element
    if question_ids:
        quiz_config = {
            "id": generate_id(),
            "title": f"Quiz - {module_name}",
            "questionIds": question_ids,
            "questionCount": len(question_ids),
            "shuffleQuestions": True,
            "shuffleAlternatives": True,
            "showFeedback": True,
            "showExplanation": True,
            "passingScore": 60.0,
            "maxAttempts": 0,
        }
        elements.append({
            "id": generate_id(), "type": "quiz", "x": 260, "y": 280, "width": 1400, "height": 500,
            "content": "", "htmlContent": "",
            "quizConfig": quiz_config,
            "style": {"fontFamily": palette.get("fontBody", "'Inter', sans-serif")}, "startTime": 0,
            "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.3}],
        })

    return elements



def _build_scenario_slide(sb_slide: dict, palette: dict, module_name: str, scenario_data: dict) -> list:
    """Build a scenario slide with the interactive scenario element."""
    from models import generate_id
    accent = palette["accent"]
    font_heading = palette.get("fontHeading", "'Inter', sans-serif")
    font_body = palette.get("fontBody", "'Inter', sans-serif")
    elements = []

    # Header bar
    header_html = _build_header_bar(palette, f"CENÁRIO - {module_name}")
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 36, "width": 1680, "height": 40,
        "htmlContent": header_html,
        "style": {}, "startTime": 0, "animations": [],
    })

    # Scenario intro — clean, left-aligned, token colors
    tk = _tokens(palette)
    scenario_html = f'''<div style="text-align:left;padding:4px 0;">
<span style="display:inline-block;padding:6px 18px;border-radius:999px;background:{palette.get("accentLight", accent + "22")};color:{accent};font-size:13px;font-weight:600;letter-spacing:0.5px;font-family:{font_heading};">Simulação interativa</span>
<h2 style="font-family:{font_heading};font-size:34px;font-weight:700;letter-spacing:-0.5px;color:{tk["text"]};margin:18px 0 10px 0;">{scenario_data.get('title', 'Cenário de Aprendizagem')}</h2>
<p style="font-family:{font_body};font-size:19px;color:{tk["muted"]};margin:0;max-width:900px;line-height:1.6;">{scenario_data.get('description', 'Tome decisões e veja as consequências em uma simulação realista.')}</p>
</div>'''
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 100, "width": 1500, "height": 190,
        "htmlContent": scenario_html,
        "style": {}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
    })

    # Scenario interactive element
    elements.append({
        "id": generate_id(), "type": "scenario", "x": 160, "y": 270, "width": 1600, "height": 520,
        "content": scenario_data.get("id", ""),
        "scenarioData": scenario_data,
        "style": {}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.3}],
    })

    return elements


def _build_summary_slide(sb_slide: dict, palette: dict, module_name: str) -> dict:
    """Build a visually rich summary slide."""
    from models import generate_id
    accent = palette["accent"]
    font_body = palette.get("fontBody", "'Inter', sans-serif")
    elements = []

    # Header (template-specific)
    header_html = _build_header_bar(palette, f"RESUMO - {module_name}")
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 36, "width": 1680, "height": 40,
        "htmlContent": header_html,
        "style": {}, "startTime": 0, "animations": [],
    })

    # Summary content
    text_content = ""
    for el in sb_slide.get("elements", []):
        c = el.get("content", "")
        if c:
            text_content = c

    styled_text = _style_summary_html(text_content, accent, palette)
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 110, "width": 1440, "height": 660,
        "htmlContent": styled_text,
        "style": {"fontFamily": font_body}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
    })

    return elements


def _style_content_html(raw_html: str, text_color: str, palette: dict = None) -> str:
    """Clean typographic scale for content HTML (light/dark aware)."""
    import re
    tk = _tokens(palette or {"accent": "#2563eb", "text": text_color, "mode": "light"})
    text = text_color or tk["text"]
    muted = tk["muted"] if palette else f"{text}b3"
    styled = raw_html
    styled = re.sub(r'<h1([^>]*)>', f'<h1\\1 style="font-family:{tk["heading"]};font-size:40px;font-weight:700;letter-spacing:-0.5px;color:{text};margin:0 0 22px 0;line-height:1.2;">', styled)
    styled = re.sub(r'<h2([^>]*)>', f'<h2\\1 style="font-family:{tk["heading"]};font-size:32px;font-weight:700;letter-spacing:-0.3px;color:{text};margin:0 0 18px 0;line-height:1.25;">', styled)
    styled = re.sub(r'<h3([^>]*)>', f'<h3\\1 style="font-family:{tk["heading"]};font-size:24px;font-weight:600;color:{text};margin:0 0 14px 0;line-height:1.3;">', styled)
    styled = re.sub(r'<p([^>]*)>', f'<p\\1 style="font-family:{tk["body"]};font-size:21px;color:{muted};line-height:1.65;margin:0 0 16px 0;max-width:920px;">', styled)
    styled = re.sub(r'<ul([^>]*)>', '<ul\\1 style="list-style:none;padding:0;margin:12px 0;max-width:920px;">', styled)
    styled = re.sub(r'<li([^>]*)>', f'<li\\1 style="font-family:{tk["body"]};font-size:20px;color:{muted};line-height:1.6;margin-bottom:12px;padding-left:26px;position:relative;"><span style="position:absolute;left:0;top:0.62em;width:14px;height:3px;border-radius:2px;background:{tk["accent"]};"></span>', styled)
    styled = re.sub(r'<strong([^>]*)>', f'<strong\\1 style="color:{text};font-weight:600;">', styled)
    return f'<div style="padding:6px 0;font-family:{tk["body"]};">{styled}</div>'


def _style_summary_html(raw_html: str, accent: str, palette: dict = None) -> str:
    """Clean summary styling: left-aligned headings + light key-point cards."""
    import re
    tk = _tokens(palette or {"accent": accent, "text": "#1c1917", "mode": "light"})
    styled = raw_html
    styled = re.sub(r'<h1([^>]*)>', f'<h1\\1 style="font-family:{tk["heading"]};font-size:36px;font-weight:700;letter-spacing:-0.5px;color:{tk["text"]};margin:0 0 24px 0;text-align:left;">', styled)
    styled = re.sub(r'<h2([^>]*)>', f'<h2\\1 style="font-family:{tk["heading"]};font-size:28px;font-weight:700;color:{tk["text"]};margin:24px 0 16px 0;text-align:left;">', styled)
    styled = re.sub(r'<p([^>]*)>', f'<p\\1 style="font-family:{tk["body"]};font-size:20px;color:{tk["muted"]};line-height:1.65;margin:0 0 14px 0;text-align:left;max-width:920px;">', styled)
    styled = re.sub(r'<ul([^>]*)>', '<ul\\1 style="list-style:none;padding:0;margin:18px 0;max-width:980px;">', styled)
    styled = re.sub(r'<li([^>]*)>', f'<li\\1 style="font-family:{tk["body"]};font-size:19px;color:{tk["muted"]};line-height:1.55;padding:16px 22px;margin-bottom:12px;background:{tk["card_bg"]};border:1px solid {tk["card_border"]};border-left:3px solid {tk["accent"]};border-radius:12px;">', styled)
    styled = re.sub(r'<strong([^>]*)>', f'<strong\\1 style="color:{tk["text"]};font-weight:600;">', styled)
    return f'<div style="padding:6px 0;font-family:{tk["body"]};">{styled}</div>'


def _parse_video_url(url: str) -> Optional[dict]:
    """Parse YouTube or Vimeo URL and return embed info."""
    import re
    if not url:
        return None
    # YouTube
    yt_match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})', url)
    if yt_match:
        vid = yt_match.group(1)
        return {"type": "youtube", "videoId": vid, "embedUrl": f"https://www.youtube.com/embed/{vid}"}
    # Vimeo
    vm_match = re.search(r'(?:vimeo\.com/)(\d+)', url)
    if vm_match:
        vid = vm_match.group(1)
        return {"type": "vimeo", "videoId": vid, "embedUrl": f"https://player.vimeo.com/video/{vid}"}
    return None


def _build_video_element(video_info: dict, palette: dict) -> dict:
    """Build a video embed element for a content slide."""
    from models import generate_id
    embed_url = video_info["embedUrl"]
    video_type = video_info["type"]
    platform = "YouTube" if video_type == "youtube" else "Vimeo"

    return {
        "id": generate_id(), "type": "html", "x": 1120, "y": 110, "width": 740, "height": 440,
        "htmlContent": f'''<div style="width:100%;height:100%;border-radius:14px;overflow:hidden;background:#000;">
<iframe src="{embed_url}" title="{platform}" style="width:100%;height:100%;border:none;" allowfullscreen allow="autoplay; encrypted-media"></iframe>
</div>''',
        "style": {}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.3}],
    }


def _build_content_slide_with_video(sb_slide: dict, palette: dict, module_name: str, video_info: dict) -> list:
    """Build content slide with video embed instead of image."""
    from models import generate_id
    elements = []

    # Header bar (template-specific)
    header_html = _build_header_bar(palette, module_name, sb_slide.get("title", ""))
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 36, "width": 1680, "height": 40,
        "htmlContent": header_html, "style": {}, "startTime": 0, "animations": [],
    })

    # Text on the left
    text_content = ""
    for el in sb_slide.get("elements", []):
        if el.get("content"):
            text_content = el["content"]
    styled_text = _style_content_html(text_content, palette["text"], palette)
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 110, "width": 960, "height": 660,
        "htmlContent": styled_text,
        "style": {"fontFamily": palette.get("fontBody", "'Inter', sans-serif")}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
    })

    # Video embed on the right
    elements.append(_build_video_element(video_info, palette))

    return elements


def _build_heygen_processing_element(slide_id: str) -> dict:
    """Build an HTML element showing HeyGen video processing state."""
    from models import generate_id
    html = f'''<div data-heygen-slide="{slide_id}" style="width:100%;height:100%;border-radius:14px;background:rgba(127,127,127,0.06);display:flex;align-items:center;justify-content:center;border:1px dashed rgba(127,127,127,0.35);overflow:hidden;">
<div style="text-align:center;">
<div style="width:44px;height:44px;border:3px solid rgba(127,127,127,0.25);border-top-color:#8b5cf6;border-radius:50%;margin:0 auto 16px;animation:spin 1s linear infinite;"></div>
<p style="color:#8b5cf6;font-size:15px;font-weight:600;margin:0 0 6px;font-family:sans-serif;">Gerando vídeo com Avatar IA...</p>
<p style="color:rgba(127,127,127,0.7);font-size:12px;margin:0;font-family:sans-serif;">Isso pode levar 1-3 minutos</p>
</div>
<style>@keyframes spin{{from{{transform:rotate(0deg)}}to{{transform:rotate(360deg)}}}}</style>
</div>'''
    return {
        "id": generate_id(), "type": "html", "x": 1120, "y": 110, "width": 740, "height": 440,
        "htmlContent": html, "style": {}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.3}],
    }


def _build_content_slide_with_heygen(sb_slide: dict, palette: dict, module_name: str, slide_id: str) -> list:
    """Build content slide with HeyGen processing element on the right."""
    from models import generate_id
    elements = []

    # Header bar (template-specific)
    header_html = _build_header_bar(palette, module_name, sb_slide.get("title", ""))
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 36, "width": 1680, "height": 40,
        "htmlContent": header_html, "style": {}, "startTime": 0, "animations": [],
    })

    # Text on the left
    text_content = ""
    for el in sb_slide.get("elements", []):
        if el.get("content"):
            text_content = el["content"]
    styled_text = _style_content_html(text_content, palette["text"], palette)
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 110, "width": 960, "height": 660,
        "htmlContent": styled_text,
        "style": {"fontFamily": palette.get("fontBody", "'Inter', sans-serif")}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
    })

    # HeyGen processing element on the right
    elements.append(_build_heygen_processing_element(slide_id))

    return elements


def _build_kling_processing_element(slide_id: str) -> dict:
    """Build a durable placeholder while Kling renders the storyboard scene."""
    from models import generate_id
    html = f'''<div data-kling-slide="{slide_id}" style="width:100%;height:100%;border-radius:14px;background:linear-gradient(135deg,rgba(2,132,199,.12),rgba(99,102,241,.12));display:flex;align-items:center;justify-content:center;border:1px dashed rgba(56,189,248,.55);overflow:hidden;">
<div style="text-align:center;padding:24px;">
<div style="width:46px;height:46px;border:3px solid rgba(56,189,248,.22);border-top-color:#38bdf8;border-radius:50%;margin:0 auto 16px;animation:klingSpin 1s linear infinite;"></div>
<p style="color:#38bdf8;font-size:15px;font-weight:700;margin:0 0 6px;font-family:sans-serif;">Gerando cena educativa com Kling AI...</p>
<p style="color:rgba(148,163,184,.9);font-size:12px;margin:0;font-family:sans-serif;">O processamento continua em segundo plano</p>
</div>
<style>@keyframes klingSpin{{from{{transform:rotate(0deg)}}to{{transform:rotate(360deg)}}}}</style>
</div>'''
    return {
        "id": generate_id(), "type": "html", "x": 1120, "y": 110, "width": 740, "height": 440,
        "htmlContent": html, "style": {}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.3}],
    }


def _build_content_slide_with_kling(sb_slide: dict, palette: dict, module_name: str, slide_id: str) -> list:
    """Build a content slide whose right side will receive a Kling video."""
    elements = _build_content_slide_with_heygen(sb_slide, palette, module_name, slide_id)
    elements[-1] = _build_kling_processing_element(slide_id)
    return elements


def _build_content_slide_no_media(sb_slide: dict, palette: dict, module_name: str) -> list:
    """Build content slide without any media - full width text."""
    from models import generate_id
    elements = []

    # Header bar (template-specific)
    header_html = _build_header_bar(palette, module_name, sb_slide.get("title", ""))
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 36, "width": 1680, "height": 40,
        "htmlContent": header_html, "style": {}, "startTime": 0, "animations": [],
    })

    # Full-width text
    text_content = ""
    for el in sb_slide.get("elements", []):
        if el.get("content"):
            text_content = el["content"]
    styled_text = _style_content_html(text_content, palette["text"], palette)
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 110, "width": 1280, "height": 660,
        "htmlContent": styled_text,
        "style": {"fontFamily": palette.get("fontBody", "'Inter', sans-serif")}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
    })

    return elements

def _build_content_slide_with_embed(sb_slide: dict, palette: dict, module_name: str, media: dict, embed_type: str) -> list:
    """Build content slide with embedded content (flipbook or HTML) on the right."""
    from models import generate_id
    elements = []

    # Header bar (template-specific)
    header_html = _build_header_bar(palette, module_name, sb_slide.get("title", ""))
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 36, "width": 1680, "height": 40,
        "htmlContent": header_html, "style": {}, "startTime": 0, "animations": [],
    })

    # Text on the left
    text_content = ""
    for el in sb_slide.get("elements", []):
        if el.get("content"):
            text_content = el["content"]
    styled_text = _style_content_html(text_content, palette["text"], palette)
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 110, "width": 800, "height": 660,
        "htmlContent": styled_text,
        "style": {"fontFamily": palette.get("fontBody", "'Inter', sans-serif")}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
    })

    # Embedded content on the right
    if media.get("htmlSource") == "code" and media.get("htmlCode"):
        embed_html = media["htmlCode"]
    elif media.get("url"):
        url = media["url"]
        if embed_type == "flipbook":
            embed_html = f'<iframe src="{url}" style="width:100%;height:100%;border:none;border-radius:8px;" allowfullscreen></iframe>'
        else:
            embed_html = f'<iframe src="{url}" style="width:100%;height:100%;border:none;border-radius:8px;" sandbox="allow-scripts allow-same-origin" allowfullscreen></iframe>'
    else:
        label = "Flipbook" if embed_type == "flipbook" else "HTML"
        embed_html = f'<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,0.05);border-radius:8px;border:1px dashed rgba(255,255,255,0.2);"><span style="color:rgba(255,255,255,0.4);font-size:14px;">{label} não configurado</span></div>'

    element_type = "flipbook" if embed_type == "flipbook" else "html"
    elements.append({
        "id": generate_id(), "type": element_type, "x": 940, "y": 70, "width": 940, "height": 720,
        "htmlContent": embed_html,
        "style": {}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.2}],
    })

    return elements


def _build_content_slide_with_button(sb_slide: dict, palette: dict, module_name: str, media: dict) -> list:
    """Build content slide with an external link button."""
    from models import generate_id
    accent = palette["accent"]
    elements = []

    # Header bar (template-specific)
    header_html = _build_header_bar(palette, module_name, sb_slide.get("title", ""))
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 36, "width": 1680, "height": 40,
        "htmlContent": header_html, "style": {}, "startTime": 0, "animations": [],
    })

    # Full-width text
    text_content = ""
    for el in sb_slide.get("elements", []):
        if el.get("content"):
            text_content = el["content"]
    styled_text = _style_content_html(text_content, palette["text"], palette)
    elements.append({
        "id": generate_id(), "type": "html", "x": 120, "y": 110, "width": 1280, "height": 540,
        "htmlContent": styled_text,
        "style": {"fontFamily": palette.get("fontBody", "'Inter', sans-serif")}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
    })

    # Button element
    btn_text = media.get("buttonText", "Saiba Mais")
    btn_url = media.get("url", "#")
    btn_color = media.get("buttonColor", accent)
    button_html = f'''<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;">
<a href="{btn_url}" target="_blank" rel="noopener noreferrer"
   style="display:inline-flex;align-items:center;gap:10px;padding:14px 44px;background:{btn_color};color:#ffffff;
   font-size:17px;font-weight:600;border-radius:999px;text-decoration:none;
   box-shadow:0 1px 3px rgba(0,0,0,0.12);transition:transform 0.2s,box-shadow 0.2s;cursor:pointer;"
   onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 6px 16px rgba(0,0,0,0.18)'"
   onmouseout="this.style.transform='translateY(0)';this.style.boxShadow='0 1px 3px rgba(0,0,0,0.12)'">
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
{btn_text}
</a></div>'''
    elements.append({
        "id": generate_id(), "type": "html", "x": 580, "y": 660, "width": 760, "height": 80,
        "htmlContent": button_html,
        "style": {}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.3}],
    })

    return elements




def apply_brand_logo_to_slides(project_slides: list, brand_kit: dict) -> int:
    """Apply (or refresh) the brand-kit logo as a watermark on every slide.

    Returns the number of slides that got a logo element added or updated.
    Used by:
      - the initial generation pipeline (right after slide composition)
      - the new POST /api/projects/{pid}/apply-watermark-all endpoint
        (lets the author apply the watermark to an ALREADY-generated course
        without regenerating from scratch — the user explicitly asked for
        this control in the Editor)

    Idempotent: removes any existing `isBrandLogo=True` element before
    inserting the fresh one. This means re-running this function with a
    DIFFERENT logoUrl correctly swaps the watermark, AND running it
    repeatedly with the same logo doesn't pile up duplicates.
    """
    if not brand_kit or not isinstance(brand_kit, dict):
        return 0
    logo_url = (brand_kit.get("logoUrl") or "").strip()
    if not logo_url:
        return 0
    placement = (brand_kit.get("logoPlacement") or "bottom-right").lower().strip()
    if placement not in ("bottom-right", "bottom-left", "bottom-center", "intro-conclusion-only"):
        placement = "bottom-right"
    LOGO_W = 180
    LOGO_H = 70
    PAD_H = 36
    PAD_V = 24
    CANVAS_W = 1920
    CANVAS_H = 820
    if placement == "bottom-left":
        x = PAD_H
    elif placement == "bottom-center":
        x = (CANVAS_W - LOGO_W) // 2
    else:
        x = CANVAS_W - LOGO_W - PAD_H
    y = CANVAS_H - LOGO_H - PAD_V
    total = len(project_slides)
    applied = 0
    for idx, slide in enumerate(project_slides):
        if placement == "intro-conclusion-only":
            is_intro = idx == 0
            is_conclusion = idx == total - 1
            if not (is_intro or is_conclusion):
                # Make sure NO stale logo lingers when the placement is
                # restricted — if user previously chose bottom-right then
                # switched to intro-conclusion-only, the middle slides
                # would still have a logo otherwise.
                slide["elements"] = [e for e in (slide.get("elements") or []) if not e.get("isBrandLogo")]
                continue
        # Drop any pre-existing brand-logo element so re-applies are clean.
        slide["elements"] = [e for e in (slide.get("elements") or []) if not e.get("isBrandLogo")]
        slide["elements"].append({
            "id": f"brand-logo-{slide['id'][-6:]}",
            "type": "image",
            # Write both `src` (canonical name used by all 3 frontend
            # renderers — SlideCanvas, CoursePreview, SplitPreview)
            # and `imageUrl` (legacy name used by some exporters and
            # back-compat tooling). This avoids a 50% breakage rate
            # depending on which surface the slide is viewed from.
            "src": logo_url,
            "imageUrl": logo_url,
            "x": x,
            "y": y,
            "width": LOGO_W,
            "height": LOGO_H,
            "opacity": 0.9,
            "objectFit": "contain",
            "isBrandLogo": True,
            "zIndex": 50,
        })
        applied += 1
    return applied



# Auto-fit wrapper for interactive HTML slides (simulator, infographic,
# flashcard, timeline, case study). The LLM designs content for a 960x540
# stage; this snippet moves the body into a stage div, centers it and
# scales it to fill the slide viewport — content is always centered and
# sized to the slide, in the Editor, preview and every export.
_FIT_SNIPPET = (
    "<style>html,body{margin:0!important;padding:0!important;width:100%;height:100%;"
    "overflow:hidden!important;}body{display:flex!important;align-items:center!important;"
    "justify-content:center!important;}</style>"
    "<script>(function(){function b(){var bd=document.body;"
    "if(!bd||document.getElementById('__stage'))return;"
    "var st=document.createElement('div');st.id='__stage';"
    "st.style.cssText='width:960px;flex:0 0 auto;position:relative;transform-origin:center center;';"
    "while(bd.firstChild){st.appendChild(bd.firstChild);}bd.appendChild(st);"
    "function fit(){var ch=Math.max(st.scrollHeight,540);var cw=Math.max(st.scrollWidth,960);"
    "var s=Math.min(window.innerWidth/cw,window.innerHeight/ch);"
    "st.style.transform='scale('+s+')';}"
    "window.addEventListener('resize',fit);fit();setTimeout(fit,300);setTimeout(fit,1000);}"
    "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',b);}"
    "else{b();}})();</script>"
)


def _wrap_interactive_fullbleed(html_content: str) -> str:
    """Inject the auto-fit snippet into interactive HTML (idempotent)."""
    if "__stage" in html_content:
        return html_content
    if "</body>" in html_content:
        return html_content.replace("</body>", _FIT_SNIPPET + "</body>", 1)
    return html_content + _FIT_SNIPPET


def _hex_luminance(color: str) -> float:
    """Relative luminance (0..1) of a #rrggbb color. 1.0 on parse failure."""
    try:
        c = color.strip().lstrip("#")
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
    except Exception:
        return 1.0


def _palette_for_slide(base_palette: dict, custom_bg: dict, has_global_text: bool) -> dict:
    """Auto-contrast: when the author picked a custom solid/gradient
    background whose darkness conflicts with the template mode, flip the
    slide's tokens (and text color, unless explicitly chosen) so text is
    always readable. Fixes dark-on-dark / light-on-light covers."""
    hint = None
    btype = (custom_bg or {}).get("type")
    if btype == "solid" and custom_bg.get("color"):
        hint = custom_bg["color"]
    elif btype == "gradient":
        hint = custom_bg.get("color1", "#1e293b")
    if not hint or str(hint).startswith("linear"):
        return base_palette
    is_dark = _hex_luminance(hint) < 0.45
    mode = "dark" if is_dark else "light"
    if mode == base_palette.get("mode"):
        return base_palette
    adjusted = {**base_palette, "mode": mode}
    if not has_global_text:
        adjusted["text"] = "#f4f4f5" if is_dark else "#1c1917"
    return adjusted


async def generate_course_from_storyboard(session_id: str, storyboard: dict, config: dict, project_dir: str = "", project_id: str = "", media_config: dict = None, bg_config: dict = None, global_text_color: str = "", global_font_size: str = "", global_animation: str = "", design_template_id: str = "", company_id: str = "", use_brand_library: bool = False, brand_library_mode: str = "preferred") -> dict:
    """Convert storyboard into Scormfy project data with professional visuals and configurable media.

    Brand Library:
        When `use_brand_library` is True the picker tries the company's
        curated imagery BEFORE falling back to AI generation. `brand_library_mode`
        controls the fallback policy:
            - "preferred" (default): use library if a semantic match is found,
              otherwise call Leonardo / stock as usual.
            - "strict": use library or leave the slide without a background image.
    """
    from models import generate_id
    import hashlib

    if media_config is None:
        media_config = {}
    if bg_config is None:
        bg_config = {}

    slides_data = storyboard.get("slides", [])
    project_slides = []
    quiz_questions = []
    heygen_pending = []
    kling_pending = []

    # Get design template (new system) or fall back to legacy palette selection
    design_token = None
    if design_template_id:
        design_token = get_design_template_by_id(design_template_id)
    
    if design_token:
        palette = dict(design_token["palette"])  # copy: never mutate the module-level template
        font_heading = design_token["fonts"]["heading"]
        font_body = design_token["fonts"]["body"]
    else:
        # Legacy: select palette by title hash
        title_hash = int(hashlib.md5(config.get("title", "curso").encode(), usedforsecurity=False).hexdigest()[:8], 16)
        palette = dict(_COURSE_PALETTES[title_hash % len(_COURSE_PALETTES)])
        font_heading = "'Inter', sans-serif"
        font_body = "'Inter', sans-serif"

    # Override text color with user's global choice
    if global_text_color:
        palette = {**palette, "text": global_text_color}

    # Inject font info into palette for use by builder functions
    palette["fontHeading"] = font_heading
    palette["fontBody"] = font_body
    palette["headerStyle"] = design_token.get("headerStyle", "clean") if design_token else "clean"
    palette["cornerRadius"] = design_token.get("cornerRadius", "14px") if design_token else "14px"
    palette["mode"] = design_token.get("mode", "light") if design_token else "light"

    # Brand Kit: when the project opts into the company's brand library AND
    # the company has a configured BrandKit, override the palette colors and
    # font so all the `_build_*_slide` functions render in-brand without
    # needing per-builder changes. We only honor brandKit when the author
    # explicitly enabled `use_brand_library` — same opt-in as the imagery
    # picker — so users who only wanted library images don't get surprised
    # by color changes.
    # Brand Kit (colors + font + logo) — fetched once and reused. Logo is
    # applied as a watermark element later in the slide build loop; colors
    # and font flow through the palette here.
    brand_kit = None
    if use_brand_library and company_id:
        try:
            from services.brand_kit_applier import fetch_brand_kit, apply_brand_kit_to_palette
            _bk_db = await _get_motor_db()
            brand_kit = await fetch_brand_kit(_bk_db, company_id)
            if brand_kit:
                palette = apply_brand_kit_to_palette(palette, brand_kit)
                # Update font variables that are read independently below
                if palette.get("fontHeading"):
                    font_heading = palette["fontHeading"]
                if palette.get("fontBody"):
                    font_body = palette["fontBody"]
                logger.info(
                    f"BrandKit applied for company {company_id}: "
                    f"primary={palette.get('primary')}, accent={palette.get('accent')}, "
                    f"fontBody={palette.get('fontBody')}"
                )
        except Exception as _e:
            logger.warning(f"failed to apply brand kit for {company_id}: {_e}")

    # Font size scale factor
    font_scale = int(global_font_size) / 100.0 if global_font_size else 1.0

    # Collect module names for title slide
    module_names = []
    seen_modules = set()
    for sb_slide in slides_data:
        mn = sb_slide.get("moduleName", "")
        if mn and mn not in seen_modules:
            module_names.append(mn)
            seen_modules.add(mn)

    # Pre-generate media for content slides based on media_config
    slide_media = {}  # i -> {"type": "image"/"video"/"none", "url": "...", "video_info": {...}}
    
    # Collect AI image tasks for parallel generation
    ai_image_tasks = []
    for i, sb_slide in enumerate(slides_data):
        stype = sb_slide.get("type", "content")
        if stype != "content":
            continue
        mc = media_config.get(str(i), {})
        media_type = mc.get("type", "ai_image")  # default to ai_image

        if media_type == "ai_image":
            kw = sb_slide.get("imageKeywords", sb_slide.get("title", "education"))
            if project_dir and project_id:
                ai_image_tasks.append((i, kw, "gemini"))
        elif media_type == "gallery_image":
            gallery_url = mc.get("galleryImageUrl", "")
            if gallery_url:
                slide_media[i] = {"type": "image", "url": gallery_url}
        elif media_type == "brand_library_image":
            # Author hand-picked an image from the company's Brand Library
            # during the Wizard (different from `use_brand_library=True` which
            # asks the AI to pick automatically). This is the strongest signal
            # — the author committed to a specific asset, so we use it as-is.
            brand_url = mc.get("brandImageUrl", "")
            if brand_url:
                slide_media[i] = {
                    "type": "image",
                    "url": brand_url,
                    "source": "brand_library_manual",
                }
        elif media_type in ("youtube", "vimeo"):
            video_url = mc.get("url", "")
            video_info = _parse_video_url(video_url)
            if video_info:
                slide_media[i] = {"type": "video", "video_info": video_info}
        elif media_type == "heygen":
            slide_media[i] = {
                "type": "heygen",
                "avatar_id": mc.get("avatar_id", ""),
                "voice_id": mc.get("voice_id", ""),
            }
        elif media_type == "kling":
            slide_media[i] = {
                "type": "kling",
                "prompt": mc.get("klingPrompt", ""),
                "firstFrameUrl": mc.get("firstFrameUrl", ""),
                "lastFrameUrl": mc.get("lastFrameUrl", ""),
                "resolution": mc.get("resolution", "720p"),
                "aspectRatio": mc.get("aspectRatio", "16:9"),
                "duration": mc.get("duration", 5),
                "audio": mc.get("audio", "off"),
                "multiShot": bool(mc.get("multiShot", False)),
            }
        elif media_type == "leonardo":
            kw = mc.get("leonardoPrompt") or sb_slide.get("imageKeywords", sb_slide.get("title", "education"))
            if project_dir and project_id:
                ai_image_tasks.append((i, kw, "leonardo"))
        elif media_type == "none":
            slide_media[i] = {"type": "none"}

    # Generate AI images in parallel batches (max 5 concurrent)
    if ai_image_tasks:
        total_images = len(ai_image_tasks)
        logger.info(f"Generating {total_images} AI images in parallel batches...")
        
        # Update progress via shared motor db
        _pdb = await _get_motor_db()
        
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent image generations
        completed_count = 0
        
        async def _generate_one_image(slide_idx, keyword, source="gemini"):
            nonlocal completed_count
            async with semaphore:
                try:
                    # Brand Library hook: when the project opts in, try the
                    # company's curated imagery FIRST. If we find a semantic
                    # match the slide gets that asset and we skip Leonardo /
                    # stock altogether — keeping the visual identity on-brand
                    # and saving the generation cost.
                    sb_slide_ctx = slides_data[slide_idx] if slide_idx < len(slides_data) else {}
                    # Per-slide override of the project-wide preference. Three
                    # values: None → inherit; "force" → ALWAYS try library;
                    # "skip" → NEVER try library on this slide.
                    _override = sb_slide_ctx.get("brandLibraryOverride")
                    if _override == "skip":
                        _try_library = False
                    elif _override == "force":
                        _try_library = True
                    else:
                        _try_library = use_brand_library

                    if _try_library and company_id:
                        try:
                            from services.brand_library_picker import pick_asset_for_slide
                            chosen = await pick_asset_for_slide(
                                _pdb, company_id,
                                slide_title=sb_slide_ctx.get("title") or "",
                                slide_body=sb_slide_ctx.get("body") or sb_slide_ctx.get("text") or "",
                                desired_type="background",
                                keyword=keyword,
                            )
                            if chosen and chosen.get("url"):
                                slide_media[slide_idx] = {
                                    "type": "image", "url": chosen["url"], "source": "brand_library",
                                }
                                completed_count += 1
                                logger.info(f"Image {completed_count}/{total_images} from brand library for slide {slide_idx}")
                                return
                            # No match: in strict mode (or per-slide "force"),
                            # we leave the slide without an image. "force"
                            # opted in explicitly so a missing match means
                            # "leave it" rather than fall through to AI.
                            if brand_library_mode == "strict" or _override == "force":
                                slide_media[slide_idx] = {"type": "none", "source": "brand_library_strict"}
                                completed_count += 1
                                logger.info(f"Image {completed_count}/{total_images} skipped (strict brand library, no match) for slide {slide_idx}")
                                return
                        except Exception as _ble:
                            logger.warning(f"brand library picker failed for slide {slide_idx}: {_ble}")
                            # Falls through to the regular generation paths below

                    if source == "leonardo":
                        from services.leonardo_ai import generate_and_wait, download_image_to_disk
                        from services.asset_store import store_asset_async
                        import uuid as _uuid
                        leo_urls = await generate_and_wait(prompt=keyword, width=1024, height=576, num_images=1)
                        img_url = None
                        if leo_urls:
                            fname = f"leonardo_{_uuid.uuid4().hex[:10]}.png"
                            assets_dir = Path(project_dir) / project_id / "assets"
                            assets_dir.mkdir(parents=True, exist_ok=True)
                            dest = str(assets_dir / fname)
                            ok = await download_image_to_disk(leo_urls[0], dest)
                            if ok:
                                # CRITICAL: persist to MongoDB so the image survives
                                # K8s pod restarts (local disk is ephemeral in
                                # production). Without this, Leonardo images
                                # disappear after every rolling deploy.
                                try:
                                    persisted = await store_asset_async(_pdb, project_id, fname, dest)
                                    if not persisted:
                                        logger.error(f"Leonardo image {fname} failed to persist in MongoDB")
                                        ok = False
                                except Exception as persist_err:
                                    logger.error(f"Leonardo MongoDB persist error for {fname}: {persist_err}")
                                    ok = False
                            if ok:
                                img_url = f"/api/projects/{project_id}/assets/{fname}"
                                # Auto-save to gallery
                                try:
                                    import asyncio as _asyncio
                                    _asyncio.ensure_future(_auto_save_gallery(img_url, f"leonardo: {keyword}", project_id))
                                except Exception:
                                    pass
                    else:
                        img_url = await _fetch_stock_image(keyword, project_dir, project_id)
                    completed_count += 1
                    if img_url:
                        slide_media[slide_idx] = {"type": "image", "url": img_url}
                        logger.info(f"Image {completed_count}/{total_images} generated for slide {slide_idx} via {source}")
                    # Update progress
                    if _pdb:
                        try:
                            await _pdb.agent_sessions.update_one(
                                {"id": session_id},
                                {"$set": {
                                    "courseProgress": {"message": f"Gerando imagens IA: {completed_count}/{total_images}..."},
                                    "updatedAt": datetime.now(timezone.utc).isoformat()
                                }}
                            )
                        except Exception:
                            pass
                except Exception as e:
                    completed_count += 1
                    logger.warning(f"Image generation failed for slide {slide_idx}: {str(e)[:80]}")
        
        # Run all image tasks concurrently (semaphore limits concurrency to 5)
        await asyncio.gather(*[_generate_one_image(idx, kw, src) for idx, kw, src in ai_image_tasks])

    base_palette = palette
    for i, sb_slide in enumerate(slides_data):
        stype = sb_slide.get("type", "content")
        module_name = sb_slide.get("moduleName", "")

        # Slide-level auto-contrast: a custom background (bgConfig) may be
        # darker/lighter than the template — derive per-slide tokens.
        slide_custom_bg = bg_config.get(str(i), {})
        palette = _palette_for_slide(base_palette, slide_custom_bg, bool(global_text_color))

        # Process quiz questions FIRST (before building slide elements)
        slide_question_ids = []
        if stype == "quiz":
            for q in sb_slide.get("quizQuestions", []):
                qid = generate_id()
                alts = [{"id": generate_id(), "text": a["text"], "isCorrect": a.get("isCorrect", False)} for a in q.get("alternatives", [])]
                quiz_questions.append({
                    "id": qid,
                    "type": q.get("type", "multiple_choice"),
                    "text": q.get("text", ""),
                    "alternatives": alts,
                    "explanation": q.get("explanation", ""),
                    "points": 1.0,
                    "tags": [module_name] if module_name else [],
                })
                slide_question_ids.append(qid)

        if stype == "title":
            bg = palette.get("coverBg", palette["primary"])
            slide_elements = _build_title_slide(sb_slide, palette, config.get("title", ""), module_names)
        elif stype == "quiz":
            bg = palette.get("coverBg", palette["primary"])
            slide_elements = _build_quiz_slide(sb_slide, palette, module_name, slide_question_ids)
        elif stype == "scenario":
            bg = palette.get("coverBg", palette["primary"])
            # Generate scenario via AI - extract config from storyboard
            scenario_config = {}
            for el in sb_slide.get("elements", []):
                if el.get("type") == "scenario" or el.get("scenarioTheme"):
                    scenario_config = {
                        "theme": el.get("scenarioTheme", sb_slide.get("title", module_name)),
                        "objectives": el.get("scenarioObjectives", config.get("objectives", "")),
                        "audience": el.get("scenarioAudience", config.get("audience", "")),
                    }
                    break
            if not scenario_config:
                scenario_config = {
                    "theme": sb_slide.get("title", module_name),
                    "objectives": config.get("objectives", ""),
                    "audience": config.get("audience", ""),
                }
            # Generate the scenario
            try:
                from services.scenario_service import generate_scenario_with_ai
                scenario_ai_data = await generate_scenario_with_ai({
                    "theme": scenario_config["theme"],
                    "objectives": scenario_config["objectives"],
                    "audience": scenario_config.get("audience", ""),
                    "complexity": "intermediate",
                    "industry": "",
                    "duration_minutes": 10,
                    "language": "pt-BR",
                })
                # Save scenario to DB using pymongo (sync) to avoid event loop issues
                scenario_id = generate_id()
                now_str = datetime.now(timezone.utc).isoformat()
                scenario_doc = {
                    "id": scenario_id,
                    "project_id": project_id,
                    "title": scenario_ai_data.get("title", "Cenário"),
                    "description": scenario_ai_data.get("description", ""),
                    "context": scenario_ai_data.get("context", ""),
                    "characters": scenario_ai_data.get("characters", []),
                    "learning_objectives": scenario_ai_data.get("learning_objectives", []),
                    "competencies_evaluated": scenario_ai_data.get("competencies_evaluated", []),
                    "nodes": scenario_ai_data.get("nodes", []),
                    "start_node_id": scenario_ai_data["nodes"][0]["id"] if scenario_ai_data.get("nodes") else None,
                    "config": scenario_config,
                    "created_at": now_str,
                    "updated_at": now_str,
                }
                # Use shared sync client from agent module
                from routes.agent import _get_bg_db
                _bgdb = _get_bg_db()
                _bgdb.scenarios.insert_one(scenario_doc)
                scenario_doc.pop("_id", None)
                slide_elements = _build_scenario_slide(sb_slide, palette, module_name, scenario_doc)
                logger.info(f"Scenario generated for course slide {i}: {scenario_doc['title']}")
            except Exception as e:
                logger.error(f"Failed to generate scenario for slide {i}: {e}")
                # Fallback to content slide
                slide_elements = _build_content_slide_no_media(sb_slide, palette, module_name)
        elif stype == "summary":
            bg = palette.get("coverBg", palette["primary"])
            slide_elements = _build_summary_slide(sb_slide, palette, module_name)
        elif stype == "simulator":
            bg = palette.get("contentBg", "#ffffff")
            # Simulator slides contain full HTML+JS interactive content
            html_content = ""
            for el in sb_slide.get("elements", []):
                if el.get("type") == "html" and el.get("htmlContent"):
                    html_content = el["htmlContent"]
                    break
            if not html_content:
                # Fallback: look for text content that might be HTML
                for el in sb_slide.get("elements", []):
                    content = el.get("content", "")
                    if content and ("<!DOCTYPE" in content or "<html" in content or "<script" in content):
                        html_content = content
                        break
            if html_content:
                slide_elements = [{
                    "id": generate_id(),
                    "type": "html",
                    "htmlContent": _wrap_interactive_fullbleed(html_content),
                    "x": 0,
                    "y": 0,
                    "width": 1920,
                    "height": 820,
                    "zIndex": 1,
                }]
            else:
                # No HTML content generated, fallback to content slide
                slide_elements = _build_content_slide_no_media(sb_slide, palette, module_name)
        elif stype in ("infographic", "flashcard", "timeline", "case_study"):
            bg = palette.get("contentBg", "#ffffff")
            # These types use HTML+JS interactive content just like simulators
            html_content = ""
            for el in sb_slide.get("elements", []):
                if el.get("type") == "html" and el.get("htmlContent"):
                    html_content = el["htmlContent"]
                    break
            if not html_content:
                for el in sb_slide.get("elements", []):
                    content = el.get("content", "")
                    if content and ("<!DOCTYPE" in content or "<html" in content or "<script" in content):
                        html_content = content
                        break
            if html_content:
                slide_elements = [{
                    "id": generate_id(),
                    "type": "html",
                    "htmlContent": _wrap_interactive_fullbleed(html_content),
                    "x": 0,
                    "y": 0,
                    "width": 1920,
                    "height": 820,
                    "zIndex": 1,
                }]
            else:
                slide_elements = _build_content_slide_no_media(sb_slide, palette, module_name)
        else:
            bg = palette["contentBg"]
            media = slide_media.get(i, {"type": "image"})
            if media.get("type") == "video":
                slide_elements = _build_content_slide_with_video(sb_slide, palette, module_name, media["video_info"])
            elif media.get("type") == "none":
                slide_elements = _build_content_slide_no_media(sb_slide, palette, module_name)
            elif media.get("type") == "heygen":
                # Build with HeyGen processing element - video will be generated
                slide_id = generate_id()
                slide_elements = _build_content_slide_with_heygen(sb_slide, palette, module_name, slide_id)
                # Extract text for narration script
                import re
                text_content = ""
                for el in sb_slide.get("elements", []):
                    if el.get("content"):
                        text_content = el["content"]
                clean_text = re.sub(r'<[^>]+>', '', text_content)
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                heygen_pending.append({
                    "slideIndex": i,
                    "slideId": slide_id,
                    "script": clean_text[:2000],
                    "avatar_id": media.get("avatar_id", ""),
                    "voice_id": media.get("voice_id", ""),
                    "title": sb_slide.get("title", f"Slide {i+1}"),
                })
            elif media.get("type") == "kling":
                slide_id = generate_id()
                slide_elements = _build_content_slide_with_kling(sb_slide, palette, module_name, slide_id)
                raw_text = " ".join(
                    str(el.get("content") or "") for el in sb_slide.get("elements", [])
                    if el.get("content")
                )
                import re as _kling_re
                clean_text = _kling_re.sub(r'<[^>]+>', ' ', raw_text)
                clean_text = _kling_re.sub(r'\s+', ' ', clean_text).strip()
                prompt = (media.get("prompt") or "").strip()
                if not prompt:
                    prompt = (
                        "Educational cinematic scene for an online course. "
                        f"Topic: {sb_slide.get('title', '')}. "
                        f"Scene: {clean_text[:1800]}. "
                        "Clear visual storytelling, professional lighting, realistic motion, no captions, no logos."
                    )
                kling_pending.append({
                    "slideIndex": i,
                    "slideId": slide_id,
                    "title": sb_slide.get("title", f"Slide {i+1}"),
                    "prompt": prompt[:3072],
                    "firstFrameUrl": media.get("firstFrameUrl") or None,
                    "lastFrameUrl": media.get("lastFrameUrl") or None,
                    "resolution": media.get("resolution", "720p"),
                    "aspectRatio": media.get("aspectRatio", "16:9"),
                    "duration": max(3, min(15, int(media.get("duration") or 5))),
                    "audio": media.get("audio", "off"),
                    "multiShot": bool(media.get("multiShot", False)),
                    "status": "pending",
                })
            elif media.get("type") == "flipbook":
                slide_elements = _build_content_slide_with_embed(sb_slide, palette, module_name, media, "flipbook")
            elif media.get("type") == "html":
                slide_elements = _build_content_slide_with_embed(sb_slide, palette, module_name, media, "html")
            elif media.get("type") == "button":
                slide_elements = _build_content_slide_with_button(sb_slide, palette, module_name, media)
            else:
                img_url = media.get("url")
                slide_elements = _build_content_slide(sb_slide, palette, module_name, img_url)

        actual_slide_id = generate_id()
        # Update heygen pending with the actual slide id
        if stype == "content" and slide_media.get(i, {}).get("type") == "heygen":
            for hp in heygen_pending:
                if hp["slideIndex"] == i:
                    hp["slideId"] = actual_slide_id
                    break
        if stype == "content" and slide_media.get(i, {}).get("type") == "kling":
            for kp in kling_pending:
                if kp["slideIndex"] == i:
                    kp["slideId"] = actual_slide_id
                    break

        # Apply custom background from bgConfig (overrides palette defaults)
        custom_bg = bg_config.get(str(i), {})
        bg_image = None
        mongo_url = os.environ.get('MONGO_URL', '')
        db_name = os.environ.get('DB_NAME', '')
        if custom_bg.get("type") == "solid" and custom_bg.get("color"):
            bg = custom_bg["color"]
        elif custom_bg.get("type") == "gradient":
            c1 = custom_bg.get("color1", "#1e293b")
            c2 = custom_bg.get("color2", "#10b981")
            direction = custom_bg.get("direction", "to right")
            bg = f"linear-gradient({direction}, {c1}, {c2})"
        elif custom_bg.get("type") == "image":
            # For image backgrounds, we store both the image and an overlay color
            img_src = custom_bg.get("imageData") or custom_bg.get("imageUrl", "")
            if img_src:
                bg_image = img_src
                # Save base64 image to assets if it's a data URL
                if img_src.startswith("data:") and project_dir and project_id:
                    import base64 as b64mod
                    try:
                        header, data_part = img_src.split(",", 1)
                        ext = "png" if "png" in header else "jpg"
                        fname = f"bg_custom_{i}.{ext}"
                        fpath = os.path.join(project_dir, project_id, "assets", fname)
                        os.makedirs(os.path.dirname(fpath), exist_ok=True)
                        with open(fpath, "wb") as f:
                            f.write(b64mod.b64decode(data_part))
                        bg_image = f"/api/projects/{project_id}/assets/{fname}"
                        # Persist to MongoDB async for production (survives ephemeral storage)
                        try:
                            from services.asset_store import store_asset_async
                            _db = await _get_motor_db()
                            if _db is not None:
                                await store_asset_async(_db, project_id, fname, fpath)
                        except Exception as pe:
                            logger.warning(f"Failed to persist bg to MongoDB: {pe}")
                    except Exception as e:
                        logger.warning(f"Failed to save bg image for slide {i}: {e}")
                elif img_src.startswith("/api/") and project_dir and project_id:
                    # Already a URL path - persist the file to MongoDB if it exists on disk
                    try:
                        parts = img_src.replace("/api/projects/", "").split("/assets/")
                        if len(parts) == 2:
                            src_pid, src_fname = parts
                            src_path = os.path.join(project_dir, src_pid, "assets", src_fname)
                            if os.path.exists(src_path):
                                from services.asset_store import store_asset_async
                                _db = await _get_motor_db()
                                if _db is not None:
                                    await store_asset_async(_db, src_pid, src_fname, src_path)
                    except Exception:
                        pass
        elif custom_bg.get("type") == "brand":
            # Brand library background — `imageUrl` already points at the
            # public asset endpoint (`/api/companies/{cid}/assets/{aid}/file`),
            # which is served unauthenticated specifically so SCORM/HTML
            # exports can fetch it offline. No file copy needed.
            img_src = custom_bg.get("imageUrl", "")
            if img_src:
                bg_image = img_src

        slide = {
            "id": actual_slide_id,
            "title": sb_slide.get("title", f"Slide {i+1}"),
            "order": i,
            "width": 1920,
            "height": 820,
            "background": bg,
            "backgroundImage": bg_image if bg_image else None,
            "backgroundOpacity": custom_bg.get("opacity", 100) if bg_image else None,
            # Honour the picker's contrast hint: overlay scrim (dark/light)
            # is applied at render-time by the SinglePage + SCORM runtimes so
            # generated text stays readable even on busy brand imagery.
            "backgroundImageOverlay": custom_bg.get("overlay") if bg_image and custom_bg.get("overlay") in ("dark", "light") else None,
            "elements": slide_elements,
            "annotations": [],
            "transition": {"type": "fade", "duration": 0.5},
            "audio": [],
            "notes": sb_slide.get("notes", ""),
            "librasScript": sb_slide.get("librasScript", ""),
            "duration": float(
                slide_media.get(i, {}).get("duration", 5)
                if stype == "content" and slide_media.get(i, {}).get("type") == "kling"
                else 5
            ),
        }
        project_slides.append(slide)

    # Brand watermark: apply via shared helper so the same logic powers
    # both the initial generation AND the manual "apply to all" endpoint.
    apply_brand_logo_to_slides(project_slides, brand_kit)

    # Collect narration pending info from media config
    narration_pending = []
    for i, sb_slide in enumerate(slides_data):
        mc = media_config.get(str(i), {})
        narr = mc.get("narration", {})
        if narr.get("enabled") and narr.get("selectedScript") and narr.get("voiceId"):
            narration_pending.append({
                "slideIndex": i,
                "slideId": project_slides[i]["id"] if i < len(project_slides) else "",
                "script": narr["selectedScript"],
                "voiceId": narr["voiceId"],
            })

    # Apply global animation to all text elements
    if global_animation:
        for slide in project_slides:
            stagger_index = 0
            for el in slide.get("elements", []):
                if el.get("type") in ("html", "text"):
                    el["animation"] = {
                        "type": "entrance",
                        "effect": global_animation,
                        "duration": 0.5,
                        "delay": stagger_index * 0.2,
                    }
                    el["animations"] = [{
                        "type": "entrance",
                        "effect": global_animation,
                        "duration": 0.5,
                        "startTime": (el.get("startTime", 0) or 0) + stagger_index * 0.2,
                        "easing": "cubic-bezier(0.34, 1.56, 0.64, 1)" if global_animation == "bounce" else "ease",
                    }]
                    stagger_index += 1

    # Apply global font size scaling to all generated HTML content
    if font_scale != 1.0:
        import re as _re
        def _scale_font(m):
            return f"font-size:{round(float(m.group(1)) * font_scale)}px"
        for slide in project_slides:
            for el in slide.get("elements", []):
                if el.get("type") in ("html", "text") and el.get("htmlContent"):
                    el["htmlContent"] = _re.sub(r'font-size:\s*(\d+(?:\.\d+)?)px', _scale_font, el["htmlContent"])

    return {
        "slides": project_slides,
        "quizQuestions": quiz_questions,
        "heygenPending": heygen_pending,
        "klingPending": kling_pending,
        "narrationPending": narration_pending,
        "metadata": {
            "title": config.get("title", "Curso Gerado por IA"),
            "description": config.get("description", ""),
        },
    }


async def agent_chat(session_id: str, message: str, context: dict) -> str:
    """General chat with the agent for adjustments and questions."""
    chat = _new_chat(f"agent-chat-{session_id}")
    
    ctx = ""
    if context.get("structure"):
        ctx += f"\nEstrutura do curso atual: {json.dumps(context['structure'], ensure_ascii=False)[:3000]}"
    if context.get("config"):
        ctx += f"\nConfiguração: {json.dumps(context['config'], ensure_ascii=False)}"
    
    prompt = f"""Contexto da sessão:{ctx}

Mensagem do usuário: {message}

Você é um assistente de design instrucional. Responda de forma útil e concisa.

Se o usuário pedir para adicionar um cenário interativo/simulação, responda com:
[AÇÃO:CENÁRIO] seguido de uma breve confirmação. O sistema processará automaticamente.

Se o usuário pedir mudanças na estrutura ou conteúdo, sugira as alterações específicas."""
    
    response = await chat.send_message(UserMessage(text=prompt))
    return response


# ========== COURSE EDITING ==========

async def analyze_existing_course(session_id: str, project: dict) -> dict:
    """Analyze an existing Scormfy course and suggest improvements."""
    slides = project.get("course", {}).get("slides", [])
    slides_summary = []
    has_avatar = False
    has_narration_count = 0
    text_heavy_slides = []  # slides with lots of text but no image
    for i, s in enumerate(slides):
        texts = []
        has_image_element = False
        for el in s.get("elements", []):
            c = el.get("htmlContent") or el.get("content") or ""
            if c and isinstance(c, str):
                texts.append(c[:200])
            if el.get("type") == "video":
                has_avatar = True
            if el.get("type") == "image" and el.get("src"):
                has_image_element = True
        # Also count background image as visual support
        if s.get("backgroundImage"):
            has_image_element = True
        if s.get("audio") or s.get("librasScript"):
            has_narration_count += 1
        # Heuristic: a slide is "text-heavy" when its raw text length is > 350
        # chars AND it has NO image elements/background. These are prime
        # candidates for a Leonardo image to soften the reading.
        full_text = " ".join(texts)
        # Strip HTML tags for a fair length measurement
        import re as _re
        clean_text = _re.sub(r'<[^>]+>', '', full_text)
        text_length = len(clean_text)
        is_text_heavy = text_length > 350 and not has_image_element
        if is_text_heavy:
            text_heavy_slides.append(i)
        slides_summary.append({
            "index": i,
            "title": s.get("title", f"Slide {i+1}"),
            "hasAudio": bool(s.get("audio")),
            "hasNarration": bool(s.get("librasScript")),
            "hasVideo": any(el.get("type") == "video" for el in s.get("elements", [])),
            "hasImage": has_image_element,
            "textLength": text_length,
            "isTextHeavy": is_text_heavy,
            "elementCount": len(s.get("elements", [])),
            "textPreview": " | ".join(texts)[:300],
        })
    
    # Avatar scene settings
    avatar_settings = project.get("avatarSceneSettings", {})
    avatar_limit = avatar_settings.get("maxScenes", 3)
    
    prompt = f"""Analise este curso existente e sugira melhorias.

CURSO: {project.get('name', 'Sem nome')}
DESCRIÇÃO: {project.get('description', '')}
TOTAL DE SLIDES: {len(slides)}
JÁ TEM AVATAR: {"Sim" if has_avatar else "Não"}
SLIDES COM NARRAÇÃO: {has_narration_count}/{len(slides)}
SLIDES TEXTUAIS SEM IMAGEM: {text_heavy_slides if text_heavy_slides else "nenhum"} (>350 chars de texto e SEM imagem)

RESUMO DOS SLIDES:
{json.dumps(slides_summary, ensure_ascii=False)[:6000]}

TIPOS DE MELHORIA DISPONÍVEIS:
- "content": Melhorar o conteúdo textual do slide (reduzir texto, usar bullet points, conceitos-chave)
- "structure": Melhorar a estrutura/organização
- "quiz": Adicionar quiz/avaliação
- "narration": Adicionar ou melhorar narração
- "visual": Melhorar o design visual
- "simulator": Adicionar simulador/jogo educativo interativo (HTML+JS completo)
- "avatar_scene": Adicionar cena com avatar falante para explicar conceitos complexos
- "scenario": Adicionar cenário de decisão interativo (árvore de decisões com múltiplos caminhos e consequências). Cenários são excelentes para treinar tomada de decisão, liderança, atendimento ao cliente, ética.
- "visual_summary": Adicionar quadro de resumo visual (infográfico, mapa mental, timeline, diagrama) para sintetizar informações densas de forma visual e memorável
- "reinforcement": Adicionar reforço de aprendizagem (flashcards, destaque de conceito-chave, caixa "Sabia que?", dica prática, exemplo real, case study) para fixar o conteúdo sem poluir com mais texto
- "imagem_simples": Adicionar imagem ILUSTRATIVA gerada via Gemini Nano Banana para suavizar a leitura de slides textuais. Custo BAIXO. Use para a maioria dos slides text-heavy onde uma imagem genérica/ilustrativa já cumpre o papel de quebrar o texto.
- "imagem_premium": Gerar imagem profissional de ALTA QUALIDADE via Leonardo AI. Custo ALTO. Use APENAS em slides estratégicos: capa do curso, abertura de módulo, conteúdo emblemático ou onde a qualidade fotorrealista/artística faz diferença pedagógica real.

PRINCÍPIOS PEDAGÓGICOS IMPORTANTES:
- Slides com muito texto são INEFICAZES. Priorize sugestões que REDUZAM texto e AUMENTEM engajamento
- Use "visual_summary" quando um slide tem muita informação textual que poderia ser um infográfico ou diagrama
- Use "reinforcement" para adicionar elementos de fixação entre slides de conteúdo denso
- Use "scenario" quando o tema envolve tomada de decisão, análise de situações ou aplicação prática
- Prefira menos texto + mais interatividade do que paredes de texto
- Cada módulo deve ter pelo menos 1 elemento interativo (quiz, cenário, simulador ou jogo)

REGRAS PARA SUGESTÃO DE AVATAR_SCENE:
- Sugira cenas com avatar APENAS onde um apresentador/instrutor virtual agregaria valor pedagógico real
- Exemplos: explicar conceitos abstratos, dar boas-vindas, resumir módulos, demonstrar procedimentos
- Limite máximo de {avatar_limit} cenas com avatar para este curso
- Para cada sugestão de avatar_scene, inclua campos extras:
  - "narrationScript": O texto completo que o avatar vai falar (max 1500 chars)
  - "backgroundDescription": Descrição do cenário de fundo ideal (ex: "Escritório moderno com tela mostrando gráficos")
  - "avatarPosition": "left", "right" ou "center"

REGRAS PARA SUGESTÃO DE SCENARIO:
- Sugira cenários interativos onde o aluno precisa tomar decisões com consequências
- Para cada sugestão de scenario, inclua campos extras:
  - "scenarioTheme": Tema específico do cenário (ex: "Atendimento ao cliente insatisfeito")
  - "scenarioComplexity": "beginner", "intermediate" ou "advanced"
  - "scenarioObjectives": Lista de 2-3 objetivos de aprendizagem do cenário

REGRAS PARA VISUAL_SUMMARY:
- Use quando um slide ou módulo tem conteúdo denso que se beneficiaria de representação visual
- Tipos: infográfico, mapa mental, timeline, diagrama de processo, quadro comparativo, resumo em tópicos visuais
- Para cada sugestão, inclua "summaryFormat": tipo de resumo visual sugerido

REGRAS PARA REINFORCEMENT:
- Use para fixar conceitos-chave entre slides de conteúdo
- Tipos: flashcard, destaque de conceito, caixa "Sabia que?", dica prática, exemplo real, analogia, case study
- Para cada sugestão, inclua "reinforcementType": tipo de reforço sugerido

REGRAS PARA SUGESTÃO DE IMAGEM EM SLIDES TEXTUAIS — PRIORIDADE ALTA:
- 🔴 OBRIGATÓRIO: para CADA slide listado em "SLIDES TEXTUAIS SEM IMAGEM" acima, sugira UMA imagem (use `imagem_simples` por padrão). Isso NÃO é opcional — slides com >350 chars de texto e sem imagem produzem fadiga visual e queda na retenção.
- O objetivo da imagem é ILUSTRAR o conteúdo do slide, ajudar a SUAVIZAR a leitura e facilitar a compreensão. NÃO é decoração — é apoio pedagógico.
- A imagem deve representar diretamente o tema/conceito principal do slide (ex: slide sobre liderança → equipe diversa em reunião colaborativa; slide sobre saúde mental → pessoa em ambiente sereno).

QUANDO usar `imagem_simples` (BAIXO custo, padrão recomendado):
- Slides de conteúdo regular onde uma imagem ilustrativa genérica já quebra o texto suficiente
- Conceitos universais (trabalho em equipe, comunicação, processos, ferramentas)
- A maioria dos slides text-heavy deve usar este tipo

QUANDO usar `imagem_premium` (ALTO custo, somente quando faz diferença):
- Slide de capa do curso ou abertura de módulo
- Slides emblemáticos onde uma imagem fotorrealista/cinematográfica eleva muito o impacto
- Cenas complexas que exigem composição artística fina
- Limite máximo: 1-3 imagens premium em todo o curso

CAMPOS PARA AMBOS OS TIPOS (imagem_simples e imagem_premium):
- "imagePrompt": Prompt DETALHADO em INGLÊS descrevendo a cena que ilustra o conteúdo (ex: "Diverse corporate team collaborating in modern meeting room, warm natural lighting, photorealistic, professional atmosphere"). Use 15-30 palavras incluindo: sujeito principal + ambiente + iluminação + estilo visual.
- "imageStyle": Estilo: "PHOTOGRAPHY" (cenas reais), "ILLUSTRATION" (conceitos abstratos), "CINEMATIC" (cenas dramáticas), "DIGITAL_ART" (tecnologia/futurista), "RENDER_3D" (produtos), ou null para automático.
- "description": Em português, explique POR QUE a imagem ajuda (ex: "Slide tem 480 chars sobre comunicação assertiva — imagem de pessoas dialogando suavizará a leitura").

IMPORTANTE: o usuário poderá ESCOLHER entre imagem simples e premium para cada sugestão, mas sua sugestão padrão deve seguir as regras acima (simples para text-heavy, premium só em estratégicos).

Retorne JSON:
```json
{{
  "overallScore": 7,
  "strengths": ["ponto forte 1"],
  "improvements": [
    {{
      "slideIndex": 0,
      "type": "content|structure|quiz|narration|visual|simulator|avatar_scene|scenario|visual_summary|reinforcement|imagem_simples|imagem_premium|imagem_krea",
      "priority": "alta|media|baixa",
      "description": "descrição da melhoria",
      "suggestion": "sugestão concreta"
    }},
    {{
      "slideIndex": 2,
      "type": "avatar_scene",
      "priority": "media",
      "description": "Adicionar avatar para explicar o conceito X",
      "suggestion": "Um avatar apresentador explicaria este conceito complexo de forma mais envolvente",
      "narrationScript": "Olá! Vou explicar o conceito de X de forma simples...",
      "backgroundDescription": "Sala de aula moderna com quadro digital",
      "avatarPosition": "left"
    }},
    {{
      "slideIndex": 4,
      "type": "scenario",
      "priority": "alta",
      "description": "Cenário de tomada de decisão sobre atendimento",
      "suggestion": "Cenário interativo onde o aluno pratica atendimento ao cliente",
      "scenarioTheme": "Atendimento ao cliente insatisfeito",
      "scenarioComplexity": "intermediate",
      "scenarioObjectives": ["Praticar escuta ativa", "Aplicar técnicas de resolução"]
    }},
    {{
      "slideIndex": 6,
      "type": "visual_summary",
      "priority": "media",
      "description": "Substituir texto denso por infográfico visual",
      "suggestion": "Transformar os 8 tópicos em um diagrama de processo visual",
      "summaryFormat": "diagrama de processo"
    }},
    {{
      "slideIndex": 3,
      "type": "reinforcement",
      "priority": "baixa",
      "description": "Adicionar reforço de conceito-chave",
      "suggestion": "Inserir caixa 'Sabia que?' com dado estatístico relevante",
      "reinforcementType": "caixa 'Sabia que?'"
    }},
    {{
      "slideIndex": 0,
      "type": "imagem_premium",
      "priority": "media",
      "description": "Adicionar imagem profissional de capa",
      "suggestion": "Imagem cinematográfica de alta qualidade para o slide de abertura",
      "imagePrompt": "Modern professional training environment with warm lighting, corporate aesthetic, photorealistic",
      "imageStyle": "CINEMATIC"
    }}
  ],
  "missingElements": ["elemento faltante"],
  "suggestedNewSlides": [
    {{
      "position": "after_slide_2",
      "title": "Título sugerido",
      "type": "content|quiz|summary|avatar_scene|scenario|visual_summary|reinforcement|imagem_premium",
      "reason": "motivo"
    }}
  ]
}}
```"""
    
    response = await _resilient_send(
        f"agent-edit-analyze-{session_id}",
        SYSTEM_PROMPT,
        prompt
    )
    return _extract_json(response) or {"overallScore": 0, "strengths": [], "improvements": [], "missingElements": [], "suggestedNewSlides": []}


async def apply_course_improvements(session_id: str, project: dict, selected_improvements: list, selected_new_slides: list = None) -> dict:
    """Apply selected improvements to an existing course."""
    slides = project.get("course", {}).get("slides", [])
    
    # Group improvements by slide
    improvements_desc = json.dumps(selected_improvements, ensure_ascii=False)
    
    # Include selected new slides in the request
    new_slides_desc = ""
    if selected_new_slides:
        new_slides_desc = f"\n\nNOVOS SLIDES PARA CRIAR (o usuário selecionou estes novos slides sugeridos):\n{json.dumps(selected_new_slides, ensure_ascii=False)}\n\nVocê DEVE gerar o conteúdo completo para cada novo slide listado acima e incluí-los no array 'newSlides' da resposta."
    
    # Check if any avatar_scene improvements are selected
    has_avatar_scenes = any(imp.get("type") == "avatar_scene" for imp in selected_improvements)
    has_scenarios = any(imp.get("type") == "scenario" for imp in selected_improvements)
    has_visual_summaries = any(imp.get("type") == "visual_summary" for imp in selected_improvements)
    has_reinforcements = any(imp.get("type") == "reinforcement" for imp in selected_improvements)
    has_imagem_premium = any(imp.get("type") == "imagem_premium" for imp in selected_improvements)
    has_imagem_simples = any(imp.get("type") == "imagem_simples" for imp in selected_improvements)
    has_imagem_krea = any(imp.get("type") == "imagem_krea" for imp in selected_improvements)
    
    # Get current slide content for context
    slides_content = []
    for i, s in enumerate(slides):
        texts = []
        for el in s.get("elements", []):
            c = el.get("htmlContent") or el.get("content") or ""
            if c and isinstance(c, str):
                texts.append(c[:300])
        slides_content.append({
            "index": i,
            "title": s.get("title", ""),
            "text": " ".join(texts)[:500],
        })
    
    avatar_scene_instructions = ""
    if has_avatar_scenes:
        avatar_scene_instructions = """
REGRA PARA CENAS COM AVATAR (type "avatar_scene"):
- Slides de avatar_scene devem ter um layout que acomode o avatar de vídeo + conteúdo textual de apoio
- O conteúdo textual deve ser um resumo visual (bullet points, título) do que o avatar está explicando
- Inclua o campo "avatarScene" com os metadados da cena:
  - "narrationScript": texto completo que o avatar vai falar (max 1500 chars, natural e didático)
  - "backgroundPrompt": prompt em inglês para gerar imagem de fundo (ex: "Modern classroom with digital whiteboard showing charts")
  - "avatarPosition": "left", "right" ou "center" (onde o avatar aparecerá no slide)
- Layout sugerido:
  - Avatar à esquerda (avatarPosition: "left"): conteúdo textual ocupa a metade direita
  - Avatar à direita: conteúdo textual ocupa a metade esquerda
  - Avatar centralizado: conteúdo textual acima ou abaixo
- Exemplo de novo slide avatar_scene:
  {{"afterIndex":2,"title":"Explicação: Conceito X","type":"avatar_scene","background":"#0f172a",
    "elements":[{{"type":"text","content":"<h2>Conceito X</h2><ul><li>Ponto 1</li><li>Ponto 2</li></ul>","width":900,"height":600,"x":960,"y":110}}],
    "avatarScene":{{"narrationScript":"Olá! Agora vou explicar...","backgroundPrompt":"Professional studio with blue lighting","avatarPosition":"left"}},
    "narrationScript":"","librasScript":"","quizQuestions":[]}}
"""

    scenario_instructions = ""
    if has_scenarios:
        scenario_instructions = """
REGRA PARA CENÁRIOS INTERATIVOS (type "scenario"):
- Quando a melhoria pede um cenário interativo, NÃO gere a árvore de decisão completa.
- Gere APENAS um novo slide com as configurações do cenário para geração posterior.
- O slide deve ter type "scenario" e incluir o campo "scenarioConfig" com:
  - "theme": tema específico do cenário (baseado no conteúdo do slide/módulo)
  - "objectives": objetivos de aprendizagem relevantes ao contexto
  - "audience": público-alvo
  - "complexity": "beginner", "intermediate" ou "advanced"
  - "industry": setor/indústria se relevante
  - "duration_minutes": 10 ou 15
- Exemplo de novo slide cenário:
  {{"afterIndex":3,"title":"Cenário: Atendimento ao Cliente","type":"scenario",
    "scenarioConfig":{{"theme":"Atendimento ao cliente insatisfeito com produto defeituoso","objectives":"Praticar escuta ativa, técnicas de resolução de conflitos","audience":"Atendentes de suporte nível 1","complexity":"intermediate","industry":"Varejo","duration_minutes":10}}}}
- NÃO inclua "elements" para slides de cenário - eles serão gerados automaticamente
"""

    visual_summary_instructions = ""
    if has_visual_summaries:
        visual_summary_instructions = """
REGRA PARA RESUMOS VISUAIS (type "visual_summary"):
- Gere um elemento HTML completo que apresente a informação de forma VISUAL e MEMORÁVEL
- Formato: {{"type":"html","htmlContent":"<!DOCTYPE html>...","width":960,"height":540}}
- TIPOS DE RESUMO VISUAL:
  * Infográfico: dados em cards coloridos, ícones, números grandes, mini gráficos CSS
  * Mapa mental: nó central + ramificações com cores diferentes para cada categoria
  * Timeline: linha horizontal/vertical com marcos, datas, ícones
  * Diagrama de processo: boxes conectados por setas, etapas numeradas
  * Quadro comparativo: tabela visual com ícones de check/X, cores, categorias
  * Resumo em cards: conceitos-chave em cards coloridos com ícone + título + descrição curta
- CSS: Use cores vibrantes, gradientes sutis, ícones SVG inline, layout flexbox/grid, animações de entrada
- Objetivo: substituir TEXTO DENSO por representação visual que facilite a memorização
- Máximo de 6-8 conceitos/itens por resumo visual
"""

    reinforcement_instructions = ""
    if has_reinforcements:
        reinforcement_instructions = """
REGRA PARA REFORÇOS DE APRENDIZAGEM (type "reinforcement"):
- Gere um elemento HTML que reforce conceitos-chave de forma envolvente
- Formato: {{"type":"html","htmlContent":"<!DOCTYPE html>...","width":960,"height":540}}
- TIPOS DE REFORÇO:
  * Flashcard interativo: card que vira ao clicar (frente: pergunta, verso: resposta)
  * Destaque de conceito: card grande com ícone, conceito-chave e explicação curta
  * Caixa "Sabia que?": dado estatístico ou fato curioso relacionado ao tema
  * Dica prática: ação concreta que o aluno pode aplicar imediatamente
  * Exemplo real: case study mini com situação, ação e resultado
  * Analogia visual: comparação criativa para fixar conceito complexo
- CSS: Design chamativo mas limpo, cor de destaque, ícone grande, fonte legível
- JavaScript: Interatividade simples (virar card, revelar resposta, expandir detalhes)
- Objetivo: FIXAR conceitos sem adicionar mais texto longo
"""

    imagem_premium_instructions = ""
    if has_imagem_premium:
        imagem_premium_instructions = """
REGRA PARA IMAGEM PREMIUM (type "imagem_premium"):
- Para melhorias do tipo "imagem_premium", inclua o campo "_leonardoImage" no updatedSlide:
  - "_leonardoImage": {{"prompt": "prompt detalhado em inglês para Leonardo AI", "style": "CINEMATIC" ou "PHOTOGRAPHY" ou "ILLUSTRATION" ou "DIGITAL_ART" ou "RENDER_3D" ou null}}
- O prompt deve ser detalhado e descritivo (em inglês), adequado ao tema do slide
- A imagem será gerada automaticamente via Leonardo AI e inserida como elemento do slide
- Ao atualizar o slide, reorganize os elementos existentes para acomodar a imagem (layout duas colunas: texto à esquerda, imagem à direita)
- Exemplo de updatedSlide com imagem premium:
  {{"slideIndex":0,"title":"Título","elements":[{{"type":"text","content":"<h2>Título</h2><p>Conteúdo</p>","width":1050,"height":700,"x":60,"y":60}}],"_leonardoImage":{{"prompt":"Modern corporate training room with digital screens and professionals","style":"CINEMATIC"}}}}
"""

    imagem_simples_instructions = ""
    if has_imagem_simples:
        imagem_simples_instructions = """
REGRA PARA IMAGEM SIMPLES (type "imagem_simples"):
- Para melhorias do tipo "imagem_simples", inclua o campo "_geminiImage" no updatedSlide:
  - "_geminiImage": {{"prompt": "prompt detalhado em inglês para Gemini Nano Banana"}}
- O prompt deve ser claro e descritivo (em inglês), adequado ao tema do slide. Custo BAIXO — sem campo "style".
- A imagem será gerada automaticamente via Gemini Nano Banana e inserida como elemento do slide
- Ao atualizar o slide, reorganize os elementos existentes para acomodar a imagem (layout duas colunas: texto à esquerda, imagem à direita)
- Exemplo de updatedSlide com imagem simples:
  {{"slideIndex":0,"title":"Título","elements":[{{"type":"text","content":"<h2>Título</h2><p>Conteúdo</p>","width":1050,"height":700,"x":60,"y":60}}],"_geminiImage":{{"prompt":"Diverse corporate team collaborating in modern meeting room, warm lighting, illustrative style"}}}}
"""

    imagem_krea_instructions = ""
    if has_imagem_krea:
        imagem_krea_instructions = """
REGRA PARA IMAGEM KREA AI (type "imagem_krea"):
- Para melhorias do tipo "imagem_krea", inclua o campo "_kreaImage" no updatedSlide:
  - "_kreaImage": {{"prompt": "prompt detalhado em inglês para Krea AI", "modelId": "flux-1-dev", "width": 1024, "height": 576}}
- Campos obrigatórios: prompt (em inglês, 15-30 palavras descritivas) e modelId.
- O campo "modelId" virá da seleção do usuário no frontend (ex: "flux-1-dev", "flux-1.1-pro", "imagen-4", "krea-1", "nano-banana-2", "ideogram-3.0"). NÃO altere o modelId indicado pelo usuário.
- width/height default: 1024x576 (16:9). Campos opcionais — se omitidos, backend usa 1024x576.
- A imagem será gerada via Krea AI (REST API com 40+ modelos) e inserida no slide em layout duas colunas.
- Exemplo de updatedSlide com imagem Krea:
  {{"slideIndex":0,"title":"Título","elements":[{{"type":"text","content":"<h2>Título</h2><p>Conteúdo</p>","width":1050,"height":700,"x":60,"y":60}}],"_kreaImage":{{"prompt":"Professional leadership workshop with diverse team collaborating, cinematic lighting, photorealistic","modelId":"flux-1.1-pro"}}}}
"""
    
    prompt = f"""Aplique as seguintes melhorias ao curso. Gere o conteúdo atualizado para cada slide afetado.

CURSO: {project.get('name', '')}
SLIDES ATUAIS: {json.dumps(slides_content, ensure_ascii=False)[:4000]}

MELHORIAS SELECIONADAS:
{improvements_desc}
{new_slides_desc}

IMPORTANTE: Cada slide deve ter UM ÚNICO elemento com todo o conteúdo HTML combinado. NÃO divida o conteúdo em múltiplos elementos.
O slide tem dimensões 1920x820. O elemento principal deve usar width 1760 e height 700 para ocupar bem o espaço.

REGRA PARA SIMULADORES/INTERATIVOS: Se a melhoria pedir um simulador, calculadora, jogo educativo ou elemento interativo:
- OBRIGATÓRIO: gere um documento HTML COMPLETO dentro de um elemento com type "html" e campo "htmlContent"
- O HTML será renderizado dentro de um iframe isolado de 960x540px
- Formato do elemento: {{"type":"html","htmlContent":"<!DOCTYPE html><html lang='pt-BR'><head><style>CSS</style></head><body>CONTEUDO<script>JS</script></body></html>","width":960,"height":540}}
- JOGOS EDUCATIVOS disponíveis (escolha o mais adequado):
  * Forca Educacional: adivinhação de termos com dicas pedagógicas, boneco desenhado, letras clicáveis
  * Bate-pênalti com perguntas: quiz para determinar chute, campo de futebol animado, placar
  * Jogo de acerto ao alvo: conceitos corretos/incorretos como alvos móveis, timer, pontuação
  * Jogo da memória educativa: cartas que combinam perguntas+respostas, animação de virar
  * Quiz gamificado com barra de energia: vida/energia que varia com acertos/erros, progressão
  * Calculadora temática, flashcards, drag-and-drop, linha do tempo, jogo de ordenação
- CSS: Design moderno com gradientes, sombras, transições, animações (confetti para acertos, shake para erros)
- JavaScript: TODA interatividade DEVE funcionar - onclick, drag-and-drop, feedback visual dinâmico
- Use getElementById para manipular elementos, inclua pontuação, progresso e feedback motivacional
- NÃO gere botões estáticos sem funcionalidade
- Conteúdo 100% relacionado ao tema do curso
- Foco pedagógico: fixação de conteúdo, engajamento emocional, repetição ativa, feedback imediato
{avatar_scene_instructions}
{scenario_instructions}
{visual_summary_instructions}
{reinforcement_instructions}
{imagem_premium_instructions}
{imagem_simples_instructions}
{imagem_krea_instructions}
Retorne JSON com os slides a atualizar:
```json
{{
  "updatedSlides": [
    {{
      "slideIndex": 0,
      "title": "Novo título se mudou",
      "elements": [{{"type":"text","content":"<h2>Título</h2><p>Todo o conteúdo melhorado em um único bloco HTML</p>","width":1760,"height":700}}],
      "narrationScript": "Nova narração",
      "librasScript": "Novo script LIBRAS",
      "notes": "Notas atualizadas"
    }}
  ],
  "newSlides": [
    {{
      "afterIndex": 2,
      "title": "Novo slide",
      "type": "content",
      "background": "#FFFFFF",
      "elements": [{{"type":"text","content":"<h2>Título</h2><p>Conteúdo completo em um bloco</p>","width":1760,"height":700}}],
      "narrationScript": "",
      "librasScript": "",
      "quizQuestions": []
    }},
    {{
      "afterIndex": 3,
      "title": "Simulador Interativo",
      "type": "simulator",
      "background": "#FFFFFF",
      "elements": [{{"type":"html","htmlContent":"<!DOCTYPE html><html lang='pt-BR'><head><style>body{{margin:0;font-family:sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);display:flex;justify-content:center;align-items:center;min-height:100vh;color:#fff}}</style></head><body><div id='app'><h2>Simulador</h2><button onclick='start()'>Iniciar</button></div><script>function start(){{document.getElementById('app').innerHTML='<h2>Resultado</h2><p>Parabéns!</p>'}}</script></body></html>","width":960,"height":540}}],
      "narrationScript": "",
      "librasScript": "",
      "quizQuestions": []
    }}
  ]
}}
```"""
    
    response = await _resilient_send(
        f"agent-edit-apply-{session_id}",
        SYSTEM_PROMPT,
        prompt
    )
    return _extract_json(response) or {"updatedSlides": [], "newSlides": []}


# ========== TEMPLATES ==========

COURSE_TEMPLATES = [
    {
        "id": "onboarding",
        "name": "Onboarding",
        "description": "Integração de novos colaboradores",
        "icon": "users",
        "color": "#3b82f6",
        "defaultConfig": {
            "depth": "basico",
            "duration": 30,
            "modules": 4,
            "interactivity": "alta",
            "format": "curso_completo",
        },
        "structure_hint": "Boas-vindas > Cultura e Valores > Processos e Ferramentas > Políticas Internas > Quiz Final",
    },
    {
        "id": "compliance",
        "name": "Compliance",
        "description": "Conformidade e regulamentações",
        "icon": "shield",
        "color": "#ef4444",
        "defaultConfig": {
            "depth": "intermediario",
            "duration": 45,
            "modules": 5,
            "interactivity": "alta",
            "format": "curso_completo",
        },
        "structure_hint": "Introdução > Marco Legal > Situações Práticas > Estudo de Caso > Avaliação Obrigatória",
    },
    {
        "id": "technical",
        "name": "Técnico",
        "description": "Treinamento técnico e operacional",
        "icon": "wrench",
        "color": "#f59e0b",
        "defaultConfig": {
            "depth": "avancado",
            "duration": 60,
            "modules": 6,
            "interactivity": "media",
            "format": "curso_completo",
        },
        "structure_hint": "Fundamentos > Teoria > Procedimentos > Demonstração > Prática Guiada > Avaliação",
    },
    {
        "id": "soft_skills",
        "name": "Soft Skills",
        "description": "Habilidades interpessoais e liderança",
        "icon": "heart",
        "color": "#8b5cf6",
        "defaultConfig": {
            "depth": "intermediario",
            "duration": 25,
            "modules": 3,
            "interactivity": "alta",
            "format": "microlearning",
        },
        "structure_hint": "Conceito > Cenários Práticos > Autoavaliação > Plano de Ação",
    },
    {
        "id": "health_safety",
        "name": "Saúde e Segurança",
        "description": "Segurança do trabalho e saúde ocupacional",
        "icon": "hard-hat",
        "color": "#10b981",
        "defaultConfig": {
            "depth": "basico",
            "duration": 35,
            "modules": 4,
            "interactivity": "alta",
            "format": "curso_completo",
        },
        "structure_hint": "Normas e Legislação > Riscos e Prevenção > EPIs > Emergências > Quiz Obrigatório",
    },
    {
        "id": "sales",
        "name": "Vendas",
        "description": "Treinamento comercial e técnicas de vendas",
        "icon": "trending-up",
        "color": "#06b6d4",
        "defaultConfig": {
            "depth": "intermediario",
            "duration": 30,
            "modules": 4,
            "interactivity": "alta",
            "format": "microlearning",
        },
        "structure_hint": "Produto/Serviço > Técnicas de Abordagem > Objeções > Fechamento > Role Play",
    },
]


def get_templates():
    return COURSE_TEMPLATES


async def generate_structure_from_template(session_id: str, content_text: str, config: dict, template_id: str) -> dict:
    """Generate course structure using a template as base."""
    template = next((t for t in COURSE_TEMPLATES if t["id"] == template_id), None)
    if not template:
        from services.ai_agent import generate_structure
        return await generate_structure(session_id, content_text, config)
    
    chat = _new_chat(f"agent-template-{session_id}")
    
    prompt = f"""Crie a estrutura do curso usando o template "{template['name']}" como base.

TEMPLATE: {template['name']} - {template['description']}
ESTRUTURA SUGERIDA: {template['structure_hint']}

CONFIGURAÇÃO:
- Título: {config.get('title', 'Curso')}
- Nível: {config.get('depth', template['defaultConfig']['depth'])}
- Duração: {config.get('duration', template['defaultConfig']['duration'])} min
- Módulos: {config.get('modules', template['defaultConfig']['modules'])}
- Formato: {config.get('format', template['defaultConfig']['format'])}

CONTEÚDO BASE:
{content_text[:6000]}

Retorne JSON com a estrutura completa:
```json
{{
  "courseTitle": "Título",
  "courseDescription": "Descrição",
  "learningObjectives": ["objetivo"],
  "prerequisites": [],
  "competencies": [],
  "modules": [
    {{
      "id": "mod1",
      "title": "Módulo",
      "description": "Desc",
      "slides": [
        {{"id": "s1", "title": "Slide", "type": "content|title|quiz|summary|simulator", "purpose": "Objetivo", "estimatedDuration": 30}}
      ]
    }}
  ],
  "totalSlides": 10,
  "totalDuration": 30
}}
```

Siga a estrutura do template mas adapte ao conteúdo fornecido. Primeiro slide=capa, último=resumo, quizzes ao final de cada módulo.
OBRIGATÓRIO: Inclua pelo menos 1-2 slides tipo "simulator" por módulo. Simuladores são jogos/ferramentas HTML+JS interativos (calculadoras, quizzes gamificados, flashcards, jogos de memória, drag-and-drop, etc.) relacionados ao conteúdo do módulo."""
    
    response = await chat.send_message(UserMessage(text=prompt))
    return _extract_json(response) or {}


# ========== IMAGE SUGGESTIONS ==========

async def suggest_images_for_slides(session_id: str, slides: list) -> list:
    """Generate image search keywords for each slide."""
    chat = _new_chat(f"agent-images-{session_id}")
    
    slides_info = [{"index": i, "title": s.get("title", ""), "type": s.get("type", "content")} for i, s in enumerate(slides)]
    
    prompt = f"""Para cada slide, sugira 1-2 palavras-chave em inglês para buscar imagens relevantes no Unsplash/Pexels.

Slides: {json.dumps(slides_info, ensure_ascii=False)}

Retorne JSON:
```json
{{"suggestions": [{{"slideIndex": 0, "keywords": "keyword1 keyword2", "description": "Descrição da imagem ideal"}}]}}
```
Apenas slides de conteúdo e título. Ignore quizzes e resumos."""
    
    response = await chat.send_message(UserMessage(text=prompt))
    data = _extract_json(response)
    return data.get("suggestions", []) if data else []
