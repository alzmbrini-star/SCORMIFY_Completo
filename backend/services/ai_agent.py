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
import html
import re
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

from services.llm_config import openai_api_key

OPENAI_KEY = openai_api_key()

# OpenAI is the canonical provider after the Emergent migration.
PRIMARY_MODEL = ("openai", os.environ.get("OPENAI_TEXT_MODEL", "gpt-4o"))
FALLBACK_MODEL = PRIMARY_MODEL
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
        api_key=OPENAI_KEY,
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


_RICH_INTERACTIVE_TYPES = {
    "simulator", "game", "infographic", "flashcard", "timeline", "case_study"
}


def _build_storyboard_batches(slides: list, regular_batch_size: int = 4) -> list:
    """Keep full-HTML interactives isolated so the model has output room.

    Asking for several complete HTML/CSS/JS documents in the same JSON answer
    makes even capable models aggressively shorten each simulator. Ordinary
    content slides still share a batch to preserve generation speed.
    """
    batches = []
    regular = []
    for slide in slides:
        if slide.get("type") in _RICH_INTERACTIVE_TYPES:
            if regular:
                batches.append(regular)
                regular = []
            batches.append([slide])
            continue
        regular.append(slide)
        if len(regular) >= regular_batch_size:
            batches.append(regular)
            regular = []
    if regular:
        batches.append(regular)
    return batches


_SIMULATOR_MECHANICS = (
    "drag_drop",
    "resource_allocation",
    "process_builder",
    "diagnostic_dashboard",
    "timed_challenge",
    "physics_controls",
    "tool_workspace",
    "network_explorer",
    "memory_match",
    "word_challenge",
)

_INTERACTIVE_VISUAL_DIRECTIONS = (
    "vibrant_sport: gradiente quente, campo/arena, placar em chips, movimento e celebracao",
    "technical_dark: painel grafite, neon moderado, telemetria, SVG animado e controles precisos",
    "editorial_light: fundo claro, cards elevados, tipografia forte, cores de status e muito espaco",
    "corporate_tool: aplicativo com menu lateral, abas, formulario funcional, resultado e historico",
    "playful_learning: cores vivas, ilustracoes CSS/SVG, progresso, vidas, recompensas e microanimacoes",
    "concept_map: fundo profundo, nos coloridos, conexoes SVG, painel de detalhes e exploracao livre",
)


def _required_simulator_mechanic(slide: dict) -> str:
    """Choose a stable, varied hands-on mechanic from the slide context."""
    identity = "|".join(str(slide.get(key, "")) for key in ("id", "title", "purpose", "moduleName"))
    checksum = sum((index + 1) * ord(char) for index, char in enumerate(identity))
    return _SIMULATOR_MECHANICS[checksum % len(_SIMULATOR_MECHANICS)]


def _interactive_visual_direction(slide: dict) -> str:
    """Assign a stable art direction so a course does not repeat one template."""
    identity = "|".join(str(slide.get(key, "")) for key in ("title", "purpose", "moduleName", "id"))
    checksum = sum((index + 3) * ord(char) for index, char in enumerate(identity))
    return _INTERACTIVE_VISUAL_DIRECTIONS[checksum % len(_INTERACTIVE_VISUAL_DIRECTIONS)]


def _simulator_mechanic_is_functional(html_content: str, mechanic: str = "") -> bool:
    """Require implementation evidence, not merely words in visible copy."""
    raw = html_content or ""
    lowered = raw.lower()
    script_match = re.search(r"<script[^>]*>([\s\S]*?)</script>", raw, re.IGNORECASE)
    script = (script_match.group(1) if script_match else "").lower()
    checks = {
        "drag_drop": (
            ("draggable" in lowered or "dragstart" in script)
            and "drop" in script
            and ("dragover" in script or "preventdefault" in script)
        ),
        "resource_allocation": (
            ('type="range"' in lowered or "type='range'" in lowered)
            and ("input" in script or "change" in script)
            and re.search(r"(?:budget|orcamento|orçamento|resource|recurso|allocate|alocar)", lowered) is not None
        ),
        "process_builder": (
            ("draggable" in lowered or "dragstart" in script or "sortable" in script)
            and ("order" in script or "ordem" in script or "sequence" in script or "sequencia" in script)
        ),
        "diagnostic_dashboard": (
            len(re.findall(r"<(?:input|select)\b", lowered)) >= 3
            and ("input" in script or "change" in script)
            and re.search(r"(?:risk|risco|score|indicador|metric|diagnost)", lowered) is not None
        ),
        "timed_challenge": (
            re.search(r"(?:setinterval|requestanimationframe|performance\.now|countdown|timer)", script) is not None
            and re.search(r"(?:score|pontos|lives|vidas|defesas|energia)", lowered) is not None
            and len(re.findall(r"<(?:button|input)\b", lowered)) >= 4
        ),
        "physics_controls": (
            len(re.findall(r"type=[\"']range[\"']", lowered)) >= 2
            and ("<svg" in lowered or "<canvas" in lowered or "requestanimationframe" in script)
            and re.search(r"(?:calcular|calculate|update|recalcular|render)", script) is not None
        ),
        "tool_workspace": (
            len(re.findall(r"<(?:input|select)\b", lowered)) >= 2
            and len(re.findall(r"<(?:button)\b", lowered)) >= 3
            and re.search(r"(?:tab|aba|mode|modo|history|historico|histórico|result|resultado)", lowered) is not None
        ),
        "network_explorer": (
            ("<svg" in lowered or "<canvas" in lowered or re.search(r"class=[\"'][^\"']*(?:node|no|nó)", lowered))
            and re.search(r"(?:line|path|edge|conexao|conexão|link)", lowered) is not None
            and re.search(r"(?:addeventlistener|onclick|showdetails|detalhes)", raw, re.IGNORECASE) is not None
        ),
        "memory_match": (
            re.search(r"(?:matched|pares|tentativas|attempts)", lowered) is not None
            and re.search(r"(?:flipped|rotatey|virar|flip)", lowered) is not None
            and re.search(r"(?:shuffle|sort\(.*random|embaralh)", script) is not None
        ),
        "word_challenge": (
            re.search(r"(?:alphabet|alfabeto|letters|letras)", lowered) is not None
            and re.search(r"(?:attempts|tentativas|lives|vidas|errors|erros)", lowered) is not None
            and len(re.findall(r"<(?:button)\b", lowered)) >= 8
        ),
    }
    if mechanic:
        return bool(checks.get(mechanic, False))
    return any(checks.values())


def _simulator_complexity_score(html_content: str, required_mechanic: str = "") -> int:
    """Return a conservative 0-10 richness score for generated simulators."""
    raw = html_content or ""
    lowered = raw.lower()
    score = 0
    script = re.search(r"<script[^>]*>([\s\S]*?)</script>", raw, re.IGNORECASE)
    script_text = script.group(1) if script else ""
    controls = len(re.findall(r"<(?:button|input|select|textarea)\b", lowered))
    if controls >= 4:
        score += 2
    elif controls >= 2:
        score += 1
    if re.search(r"\b(?:state|score|pontuacao|pontuação|progress|progresso)\b", lowered):
        score += 1
    if re.search(r"\b(?:round|rodada|phase|fase|level|nivel|nível|step|etapa)\b", lowered):
        score += 1
    if re.search(r"\b(?:decision|decisao|decisão|consequence|consequencia|consequência|trade.?off|impacto)\b", lowered):
        score += 1
    if any(token in lowered for token in ("draggable", "dragstart", "drop", "<canvas", 'type="range"', "type='range'", "<select")):
        score += 2
    if re.search(r"\b(?:feedback|explanation|explicacao|explicação|debrief)\b", lowered):
        score += 1
    if re.search(r"\b(?:restart|reset|reiniciar|tentar novamente)\b", lowered):
        score += 1
    if len(script_text) >= 1500:
        score += 1
    if ("linear-gradient" in lowered or "radial-gradient" in lowered) and ("@keyframes" in lowered or "transition:" in lowered):
        score += 1
    if ("<svg" in lowered or "<canvas" in lowered) and re.search(r"(?:requestanimationframe|transform|animate)", lowered):
        score += 1
    # A button-only quiz cannot be promoted to an advanced simulator merely by
    # containing the right vocabulary. Cap it below the acceptance threshold.
    if not _simulator_mechanic_is_functional(raw, required_mechanic):
        return min(score, 5)
    return min(score, 10)


def _game_complexity_score(html_content: str) -> int:
    """Score actual game loops separately from business simulators."""
    lowered = (html_content or "").lower()
    score = 0
    if "questionengine" in lowered and all(name.lower() in lowered for name in (
        "getQuestion", "getRandomQuestion", "validateAnswer", "saveResult"
    )): score += 3
    if all(token in lowered for token in ("xp", "lives", "combo", "coins")): score += 2
    if re.search(r"(?:round|rodada|level|nivel|nível)", lowered): score += 1
    if "@keyframes" in lowered and re.search(r"(?:particle|confetti|burst|firework)", lowered): score += 2
    if re.search(r"(?:achievement|conquista|victory|vitoria|vitória|defeat|derrota)", lowered): score += 1
    if re.search(r"(?:localstorage|postmessage|saveResult)", html_content or "", re.IGNORECASE): score += 1
    return min(score, 10)


def _flashcard_complexity_score(html_content: str) -> int:
    """Require a real study deck, not a single decorative flipping card."""
    raw = html_content or ""
    lowered = raw.lower()
    score = 0
    card_count = max(
        len(re.findall(r"\bfront\s*:", lowered)),
        len(re.findall(r"[\"']front[\"']\s*:", lowered)),
        len(re.findall(r"class=[\"'][^\"']*(?:flashcard|study-card)[^\"']*[\"']", lowered)),
    )
    if card_count >= 6: score += 2
    elif card_count >= 4: score += 1
    if "rotatey" in lowered and re.search(r"(?:onclick|addeventlistener)", lowered): score += 2
    if re.search(r"(?:próximo|proximo|next|anterior|previous)", lowered): score += 1
    if re.search(r"(?:sei|não sei|nao sei|known|unknown|mastery|domínio|dominio)", lowered): score += 2
    if re.search(r"(?:progress|progresso|cartão \$\{|cartao \$\{)", lowered): score += 1
    if re.search(r"(?:shuffle|embaralh|restart|reiniciar|revisar novamente)", lowered): score += 1
    if ("linear-gradient" in lowered or "radial-gradient" in lowered) and "transition:" in lowered: score += 1
    return min(score, 10)


def _timeline_complexity_score(html_content: str) -> int:
    """Measure whether a timeline is substantial, navigable and explanatory."""
    raw = html_content or ""
    lowered = raw.lower()
    score = 0
    # Count both semantic data entries and visible milestone-like nodes.
    milestone_count = max(
        len(re.findall(r"data-(?:year|date|event|step|index)=", lowered)),
        len(re.findall(r"class=[\"'][^\"']*(?:milestone|timeline-item|event|marco)[^\"']*[\"']", lowered)),
    )
    if milestone_count >= 5:
        score += 3
    elif milestone_count >= 3:
        score += 1
    if re.search(r"\b(?:next|previous|proximo|próximo|anterior|navigate|showevent|show\s*\()", lowered):
        score += 2
    if re.search(r"\b(?:active|selected|progress|progresso)\b", lowered):
        score += 1
    if re.search(r"(?:addEventListener|onclick|classList\.)", raw, re.IGNORECASE):
        score += 1
    if re.search(r"\b(?:details|detalhes|description|descricao|descrição|impacto|contexto)\b", lowered):
        score += 1
    if len(re.sub(r"<[^>]+>", " ", raw)) >= 700:
        score += 1
    if len(re.findall(r"<script[^>]*>[\s\S]*?</script>", raw, re.IGNORECASE)) and len(raw) >= 3000:
        score += 1
    return min(score, 10)


def _case_study_complexity_score(html_content: str) -> int:
    """Measure evidence, decisions, reflection and debrief in a case study."""
    raw = html_content or ""
    lowered = raw.lower()
    score = 0
    reflection_count = len(re.findall(
        r"class=[\"'][^\"']*(?:question|pergunta|reflection|reflexao|reflexão)[^\"']*[\"']",
        lowered,
    ))
    if reflection_count >= 3:
        score += 2
    elif reflection_count:
        score += 1
    if re.search(r"\b(?:dados|evidencias|evidências|metricas|métricas|indicadores|resultado|%)\b", lowered):
        score += 1
    if re.search(r"\b(?:decisao|decisão|alternativa|opcao|opção|trade.?off|impacto|consequencia|consequência)\b", lowered):
        score += 2
    if re.search(r"\b(?:revelar|reveal|toggle|accordion|expandir)\b", lowered):
        score += 1
    if re.search(r"\b(?:licoes aprendidas|lições aprendidas|debrief|analise final|análise final)\b", lowered):
        score += 2
    if re.search(r"(?:addEventListener|onclick|classList\.)", raw, re.IGNORECASE):
        score += 1
    if len(re.sub(r"<[^>]+>", " ", raw)) >= 1000:
        score += 1
    return min(score, 10)


def _rich_interactive_complexity_score(html_content: str, content_type: str) -> int:
    if content_type == "game":
        return _game_complexity_score(html_content)
    if content_type == "simulator":
        return _simulator_complexity_score(html_content)
    if content_type == "timeline":
        return _timeline_complexity_score(html_content)
    if content_type == "case_study":
        return _case_study_complexity_score(html_content)
    if content_type == "flashcard":
        return _flashcard_complexity_score(html_content)
    return 10


def _simulator_html_from_slide(slide: dict) -> str:
    for element in slide.get("elements", []) or []:
        if element.get("type") == "html" and element.get("htmlContent"):
            return element["htmlContent"]
    return ""


async def _resilient_send(session_id_prefix: str, system_msg: str, prompt: str) -> str:
    """Send message with retry + fallback (Gemini -> GPT-4o)."""
    import asyncio as aio
    models = [PRIMARY_MODEL, FALLBACK_MODEL]
    for attempt, (provider, model) in enumerate(models):
        for retry in range(2):
            try:
                chat = LlmChat(
                    api_key=OPENAI_KEY,
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

    fallback_title = _derive_fallback_course_title(content_text, file_info)
    fallback_parts = _fallback_content_topics(content_text)
    return {
        "title": fallback_title,
        "summary": (fallback_parts[0] if fallback_parts else f"Curso introdutório sobre {fallback_title}."),
        "mainTopics": fallback_parts[:6],
        "targetAudience": "Público geral",
        "difficulty": "intermediario",
        "estimatedDuration": 30,
        "suggestedModules": 3,
        "gaps": [],
        "strengths": [],
        "keywords": [word.lower() for word in re.findall(r"[A-Za-zÀ-ÿ]{5,}", fallback_title)[:6]],
        "fallbackUsed": True,
    }


def _derive_fallback_course_title(content_text: str, file_info: str = "") -> str:
    """Derive a useful title without requiring a second AI call."""
    file_name = Path(str(file_info or "")).name
    file_name = re.sub(r"\.(?:pdf|pptx?|docx?|txt|md|html?)$", "", file_name, flags=re.IGNORECASE)
    file_name = re.sub(r"^[0-9a-f-]{20,}[_-]?", "", file_name, flags=re.IGNORECASE)
    file_name = re.sub(r"[_-]+", " ", file_name).strip()
    if 4 <= len(file_name) <= 120 and not file_name.lower().startswith(("arquivo", "upload")):
        return file_name
    for line in str(content_text or "").splitlines():
        line = re.sub(r"\s+", " ", line).strip(" -•#\t")
        if 8 <= len(line) <= 120 and len(line.split()) >= 2:
            return line.rstrip(".:;")
    words = re.findall(r"[A-Za-zÀ-ÿ0-9]+", str(content_text or ""))[:8]
    return " ".join(words).strip() or "Curso de Formação"


def _fallback_content_topics(content_text: str) -> list[str]:
    """Extract readable topic labels from source text deterministically."""
    cleaned = re.sub(r"\s+", " ", str(content_text or "")).strip()
    topics = []
    for part in re.split(r"(?<=[.!?;:])\s+|\s+[•-]\s+", cleaned):
        part = part.strip(" -•")
        if 20 <= len(part) <= 180 and part.casefold() not in {item.casefold() for item in topics}:
            topics.append(part)
        if len(topics) >= 8:
            break
    return topics


def _build_fallback_structure(content_text: str, config: dict, reason: str = "") -> dict:
    """Create a complete course architecture when the LLM is unavailable."""
    configured_title = str(config.get("title") or "").strip()
    if not configured_title or configured_title.casefold() in {"curso sem título", "curso sem titulo"}:
        configured_title = _derive_fallback_course_title(content_text)
    try:
        module_count = max(1, min(8, int(config.get("modules") or 3)))
    except (TypeError, ValueError):
        module_count = 3
    try:
        duration = max(10, int(config.get("duration") or 30))
    except (TypeError, ValueError):
        duration = 30

    enabled = config.get("enabledResources") or {}
    interactive = [name for name in ("game", "simulator", "scenario", "infographic", "flashcard", "timeline", "case_study", "quiz") if enabled.get(name)]
    if not interactive:
        interactive = ["quiz"]
    topics = _fallback_content_topics(content_text)
    if not topics:
        topics = [
            f"Fundamentos de {configured_title}",
            "Aplicação prática dos conceitos",
            "Análise de situações e tomada de decisão",
            "Boas práticas e melhoria contínua",
        ]

    modules = []
    slide_number = 1
    for module_index in range(module_count):
        topic = topics[module_index % len(topics)]
        short_topic = topic[:72].rstrip(" ,.;:")
        module_title = f"Módulo {module_index + 1}: {short_topic}"
        slides = []
        if module_index == 0:
            slides.append({"id": f"slide{slide_number}", "title": configured_title, "type": "title", "purpose": "Apresentar o curso, seus objetivos e sua trilha de aprendizagem.", "estimatedDuration": 30})
            slide_number += 1
        slides.extend([
            {"id": f"slide{slide_number}", "title": f"Conceitos essenciais: {short_topic}", "type": "content", "purpose": topic, "estimatedDuration": 90},
            {"id": f"slide{slide_number + 1}", "title": f"Aplicação prática: {short_topic}", "type": interactive[module_index % len(interactive)], "purpose": f"Aplicar e avaliar os conceitos de {short_topic} em uma atividade prática.", "estimatedDuration": 120},
            {"id": f"slide{slide_number + 2}", "title": f"Verificação de aprendizagem: {short_topic}", "type": "quiz" if enabled.get("quiz", True) else "content", "purpose": f"Consolidar o aprendizado sobre {short_topic} com feedback imediato.", "estimatedDuration": 90},
        ])
        slide_number += 3
        modules.append({"id": f"mod{module_index + 1}", "title": module_title, "description": topic, "slides": slides})
    modules[-1]["slides"].append({"id": f"slide{slide_number}", "title": "Síntese e próximos passos", "type": "summary", "purpose": "Revisar os aprendizados e orientar sua aplicação após o curso.", "estimatedDuration": 60})
    total_slides = sum(len(module["slides"]) for module in modules)
    return {
        "courseTitle": configured_title,
        "courseDescription": f"Trilha estruturada sobre {configured_title}.",
        "learningObjectives": [f"Compreender os fundamentos de {configured_title}", "Aplicar os conceitos em situações práticas", "Avaliar decisões e resultados"],
        "prerequisites": [],
        "competencies": ["Compreensão", "Aplicação", "Análise"],
        "modules": modules,
        "totalSlides": total_slides,
        "totalDuration": duration,
        "fallbackUsed": True,
        "fallbackReason": str(reason or "Serviço de IA temporariamente indisponível")[:180],
    }


_PREMIUM_EXPERIENCE_SEQUENCE = (
    "infographic", "simulator", "flashcard", "case_study",
    "game", "timeline", "scenario", "quiz",
)


def _illustrated_story_bible(config: dict) -> dict:
    """Stable visual continuity shared by every slide/image prompt."""
    topic = str(config.get("title") or "curso profissional").strip()
    return {
        "seriesTitle": topic,
        "setting": "uma empresa brasileira contemporânea, com ambientes de trabalho realistas e coerentes",
        "cast": [
            "Marina, profissional brasileira de 38 anos, cabelo castanho cacheado na altura dos ombros, camisa azul-petróleo",
            "Rafael, profissional brasileiro de 42 anos, cabelo preto curto, camisa cinza e crachá discreto",
        ],
        "visualStyle": "fotografia editorial corporativa cinematográfica, realista, humana, luz natural, 16:9, sem texto, sem logotipos",
        "continuityRule": "repetir roupas, aparência, ambiente e objetos-chave ao longo das cenas",
    }


def _illustrated_image_prompt(slide: dict, config: dict, story_bible: dict) -> str:
    beat = str(slide.get("narrativeBeat") or "context")
    action_by_beat = {
        "context": "the two recurring professionals encounter the concrete workplace situation for the first time",
        "observe": "Marina points to observable evidence while Rafael carefully inspects the situation",
        "decide": "the recurring professionals compare two realistic courses of action before making a decision",
        "practice": "the recurring professionals perform the correct procedure with visible tools and body language",
        "reflect": "the recurring professionals review the consequence and identify what changed after the action",
    }
    cast = "; ".join(story_bible.get("cast") or [])
    return (
        f"Brazilian professional training scene about {slide.get('title') or config.get('title', 'the topic')}. "
        f"{cast}. {action_by_beat.get(beat, action_by_beat['context'])}. "
        f"Show concrete evidence related to: {slide.get('purpose') or slide.get('experienceIntent') or 'the learning objective'}. "
        "Medium-wide cinematic composition, clear foreground action, relevant workplace objects, realistic expressions, "
        "natural directional light, editorial corporate photography, visual continuity, 16:9, no written text, no logos, no watermark."
    )


def _premiumize_course_structure(structure: dict, config: dict) -> dict:
    """Turn an LLM outline into a varied learning-experience plan.

    Models tend to fall back to consecutive ``content`` slides even when the
    author selected an interactive course. This deterministic pass keeps the
    cover/conclusion, respects disabled resources and assigns both a learning
    experience and an art direction before storyboard generation.
    """
    if not isinstance(structure, dict):
        return structure

    balance = str(config.get("resourceBalance") or config.get("interactivity") or "media").lower()
    illustrated_journey = config.get("visualCourseMode") == "illustrated_journey"
    enabled = dict(config.get("enabledResources") or {})
    # Sessions saved before the dedicated game toggle used ``simulator`` for
    # the UI label "Jogos Educativos". Keep those resumable and ensure their
    # next structure regeneration can finally emit real type="game" slides.
    if "game" not in enabled and enabled.get("simulator"):
        enabled["game"] = True
    if illustrated_journey:
        for required_type in ("game", "simulator", "scenario", "infographic", "quiz"):
            enabled[required_type] = True
    enabled_types = [kind for kind in _PREMIUM_EXPERIENCE_SEQUENCE if enabled.get(kind, False)]
    if not enabled_types or balance == "baixa":
        enabled_types = [kind for kind in ("infographic", "quiz") if enabled.get(kind, False)]

    minimum_ratio = {"baixa": 0.20, "media": 0.45, "alta": 0.62, "maxima": 0.72}.get(balance, 0.45)
    if illustrated_journey:
        minimum_ratio = max(minimum_ratio, 0.55)
    global_cursor = 0
    visual_cursor = 0
    story_bible = _illustrated_story_bible(config) if illustrated_journey else None

    for module in structure.get("modules", []) or []:
        slides = module.get("slides", []) or []
        candidates = [slide for slide in slides if slide.get("type") not in ("title", "cover", "summary")]
        if not candidates:
            continue

        desired_interactives = min(
            len(candidates),
            max(1 if enabled_types else 0, int(round(len(candidates) * minimum_ratio))),
        )
        current_interactives = sum(
            slide.get("type") not in ("content", "title", "cover", "summary") for slide in candidates
        )

        for index, slide in enumerate(candidates):
            if current_interactives >= desired_interactives or not enabled_types:
                break
            if slide.get("type") != "content":
                continue
            previous_type = candidates[index - 1].get("type") if index else ""
            next_type = enabled_types[global_cursor % len(enabled_types)]
            global_cursor += 1
            if next_type == previous_type and len(enabled_types) > 1:
                next_type = enabled_types[global_cursor % len(enabled_types)]
                global_cursor += 1
            slide["type"] = next_type
            slide["purpose"] = (
                f"Aplicar ativamente {slide.get('title', 'o conceito')} por meio de uma "
                f"experiência {next_type} com feedback imediato e conclusão mensurável."
            )
            current_interactives += 1

        # A checked "Jogos Educativos" must be visible in the Structure step,
        # not silently represented as a simulator. For balanced+ courses place
        # one real game in every module that has enough instructional slides.
        if enabled.get("game") and balance != "baixa" and len(candidates) >= 2:
            if not any(slide.get("type") == "game" for slide in candidates):
                game_slide = next(
                    (slide for slide in reversed(candidates) if slide.get("type") not in ("quiz", "scenario")),
                    candidates[-1],
                )
                game_slide["type"] = "game"
                game_slide["purpose"] = (
                    f"Fixar {game_slide.get('title', 'os conceitos do módulo')} em um jogo educativo "
                    "com cinco rodadas, feedback imediato, XP, vidas, conquistas e debrief final."
                )

        if illustrated_journey:
            previous_scene = ""
            for position, slide in enumerate(candidates):
                slide["narrativeBeat"] = ("context", "observe", "decide", "practice", "reflect")[position % 5]
                slide["imageRole"] = "action_scene" if slide.get("type") == "content" else "exercise_context"
                slide["linkedSceneTitle"] = previous_scene
                if slide.get("type") == "content":
                    previous_scene = slide.get("title", "")
                slide["storyContext"] = {
                    "setting": story_bible["setting"],
                    "cast": story_bible["cast"],
                    "continuityRule": story_bible["continuityRule"],
                }
                slide["requiredImagePrompt"] = _illustrated_image_prompt(slide, config, story_bible)

        for slide in slides:
            stype = str(slide.get("type") or "content")
            slide["contentBudgetWords"] = 70 if stype == "content" else 45
            slide["experienceIntent"] = {
                "content": "explicar visualmente um conceito com uma ideia central e evidência",
                "infographic": "explorar relações, dados ou processo de forma visual",
                "simulator": "praticar decisões e observar consequências",
                "game": "fixar conhecimento por desafio, progressão e recompensa",
                "flashcard": "recuperar conceitos da memória e autoavaliar domínio",
                "timeline": "compreender sequência, evolução e impacto dos marcos",
                "case_study": "analisar evidências, decidir e realizar debrief",
                "scenario": "escolher caminhos e comparar consequências",
                "quiz": "verificar compreensão com feedback explicativo",
            }.get(stype, "sintetizar e orientar a próxima ação")
            if stype in _RICH_INTERACTIVE_TYPES:
                slide["visualDirection"] = _INTERACTIVE_VISUAL_DIRECTIONS[
                    visual_cursor % len(_INTERACTIVE_VISUAL_DIRECTIONS)
                ]
                visual_cursor += 1

    structure["experienceQuality"] = {
        "profile": "illustrated_journey" if illustrated_journey else "premium",
        "maxConsecutiveTextSlides": 1,
        "contentWordBudget": 70,
        "interactiveTarget": minimum_ratio,
    }
    if story_bible:
        structure["visualStoryBible"] = story_bible
        structure["experienceQuality"]["requiredJourneyPattern"] = [
            "context", "observe", "decide", "practice", "reflect"
        ]
    structure["totalSlides"] = sum(
        len(module.get("slides", []) or []) for module in structure.get("modules", []) or []
    )
    return structure


async def generate_structure(session_id: str, content_text: str, config: dict) -> dict:
    """Step 2: Generate course architecture based on content and configuration."""

    # ── Resource Balance Logic ──
    resource_balance = config.get('resourceBalance', 'media')
    enabled_resources = dict(config.get('enabledResources', {}) or {})
    if 'game' not in enabled_resources and enabled_resources.get('simulator'):
        enabled_resources['game'] = True
    if config.get('visualCourseMode') == 'illustrated_journey':
        for required_type in ('game', 'simulator', 'scenario', 'infographic', 'quiz'):
            enabled_resources[required_type] = True

    # Build the list of allowed types
    all_types = ['content', 'title', 'summary']  # always present
    resource_type_map = {
        'quiz': 'quiz',
        'game': 'game',
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
- ~40% dos slides devem ser de conteudo didatico (type="content")
- ~12% quizzes de fixacao (type="quiz") - 1 por modulo
- ~10% jogos educativos premium (type="game") - pelo menos 1 por modulo quando habilitado
- ~10% simuladores de aplicacao (type="simulator")
- ~8% cenarios de desafio (type="scenario") - decisoes interativas
- ~7% infograficos interativos (type="infographic") - dados visuais
- ~5% flashcards (type="flashcard") - revisao
- ~5% linhas do tempo (type="timeline") - cronologia
- ~5% estudos de caso (type="case_study") - casos reais
- VARIE os tipos de recursos entre os modulos para manter engajamento.""",
        'alta': """DISTRIBUICAO DE RECURSOS (Nivel: Alta Interatividade):
- ~25% dos slides devem ser de conteudo didatico (type="content")
- ~12% quizzes (type="quiz")
- ~14% jogos educativos premium (type="game") - 1 por modulo
- ~13% simuladores de aplicacao (type="simulator")
- ~10% cenarios de desafio (type="scenario") - arvore de decisoes
- ~8% infograficos interativos (type="infographic")
- ~7% flashcards (type="flashcard")
- ~7% linhas do tempo (type="timeline")
- ~6% estudos de caso (type="case_study")
- ~5% cenas com avatar (type="avatar_scene") - max 2-3 no curso todo
- PRIORIZE diversidade: NUNCA coloque dois slides do mesmo tipo interativo seguidos.
- Cada modulo deve ter PELO MENOS 3 tipos diferentes de recursos interativos.""",
        'maxima': """DISTRIBUICAO DE RECURSOS (Nivel: Maxima Interatividade):
- ~15% dos slides devem ser de conteudo didatico (type="content") - breves e objetivos
- ~10% quizzes (type="quiz")
- ~16% jogos educativos premium (type="game") - 1-2 por modulo, mecanicas DIFERENTES
- ~15% simuladores de aplicacao (type="simulator")
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
- Estilo da experiência: {config.get('visualCourseMode', 'standard')}

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

MODO JORNADA VISUAL ILUSTRADA:
{'''ATIVO. Estruture o curso como uma narrativa aplicada, não como uma apresentação. Defina um contexto realista, personagens recorrentes e um desafio que evolui entre os módulos. Intercale obrigatoriamente: cena visual de contexto -> observação guiada -> decisão/exercício -> consequência -> síntese. Os slides de conteúdo devem representar AÇÕES fotografáveis; os exercícios devem reutilizar a situação vista na cena. Priorize scenario, simulator, game, infographic e quiz, sem dois slides puramente expositivos consecutivos.''' if config.get('visualCourseMode') == 'illustrated_journey' else 'INATIVO. Use a composição premium variada padrão.'}

REGRAS GERAIS:
- Primeiro slide deve ser uma capa/título do curso
- Último slide deve ser um resumo/conclusão
- Aplique progressão de complexidade
- Use microlearning: máximo 3 conceitos por slide
- CUMPRA a distribuição acima com precisão. Conte os slides de cada tipo antes de finalizar.
- Distribua os recursos de forma INTERCALADA - não agrupe todos os quizzes no final, etc."""

    models = [PRIMARY_MODEL, FALLBACK_MODEL]
    last_error = ""
    for provider, model in models:
        try:
            chat = _new_chat(f"agent-structure-{session_id}", provider=provider, model=model)
            response = await chat.send_message(UserMessage(text=prompt))
            data = _extract_json(response)
            if data:
                return _premiumize_course_structure(data, config)
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Structure with {provider}/{model} failed: {str(e)[:80]}")
            continue
    logger.warning("Using deterministic structure fallback for session %s", session_id)
    return _premiumize_course_structure(_build_fallback_structure(content_text, config, last_error), config)


async def generate_storyboard(session_id: str, content_text: str, structure: dict, config: dict, progress_callback=None) -> dict:
    """Step 3: Generate detailed storyboard - processes slides in batches to avoid timeouts."""
    all_slides = []
    illustrated_journey = config.get("visualCourseMode") == "illustrated_journey"
    story_bible = structure.get("visualStoryBible") or (
        _illustrated_story_bible(config) if illustrated_journey else {}
    )

    # Flatten all slides from structure
    flat_slides = []
    for mod in structure.get("modules", []):
        for sl in mod.get("slides", []):
            flat_slides.append({**sl, "moduleName": mod.get("title", "")})

    # Full HTML interactives need a complete response budget of their own.
    # Regular slides remain grouped for speed and cost efficiency.
    storyboard_batches = _build_storyboard_batches(flat_slides, regular_batch_size=4)
    total_batches = len(storyboard_batches)
    processed_slides = 0
    for batch_num, batch in enumerate(storyboard_batches, start=1):
        batch_start = processed_slides
        processed_slides += len(batch)
        batch_info = [{
            "id": s.get("id", ""),
            "title": s.get("title", ""),
            "type": s.get("type", "content"),
            "purpose": s.get("purpose", ""),
            "moduleName": s.get("moduleName", ""),
            "experienceIntent": s.get("experienceIntent", ""),
            "contentBudgetWords": s.get("contentBudgetWords", 70),
            "narrativeBeat": s.get("narrativeBeat", ""),
            "imageRole": s.get("imageRole", ""),
            "linkedSceneTitle": s.get("linkedSceneTitle", ""),
            "storyContext": s.get("storyContext", {}),
            "requiredImagePrompt": s.get("requiredImagePrompt", ""),
            **({"requiredMechanic": _required_simulator_mechanic(s)} if s.get("type") in ("simulator", "game") else {}),
            **({"visualDirection": s.get("visualDirection") or _interactive_visual_direction(s)} if s.get("type") in _RICH_INTERACTIVE_TYPES else {}),
        } for s in batch]

        # Report progress
        if progress_callback:
            try:
                await progress_callback(batch_num, total_batches, f"Gerando slides {batch_start+1}-{processed_slides} de {len(flat_slides)}...")
            except Exception:
                pass

        prompt = f"""Você é um designer instrucional experiente. Gere conteúdo DETALHADO, APROFUNDADO e EDUCACIONAL para {len(batch)} slides do curso "{config.get('title', '')}".

Nível do curso: {config.get('depth', 'intermediario')}

CONTEÚDO-BASE COMPLETO para referência:
{content_text[:6000]}

INTERATIVIDADE CONFIGURADA: {config.get('resourceBalance', config.get('interactivity', 'media'))}
MODO VISUAL: {config.get('visualCourseMode', 'standard')}
CONTINUIDADE VISUAL OBRIGATÓRIA: {json.dumps(story_bible, ensure_ascii=False) if illustrated_journey else 'modo padrão'}

{'''DIREÇÃO ESPECIAL — JORNADA VISUAL ILUSTRADA:
- O curso deve parecer uma história profissional fotografada, com começo, tensão, escolhas e resolução.
- Crie uma pequena bíblia visual estável (ambiente, roupas, faixa etária e características dos personagens) e REPITA essa descrição em inglês em todos os imageKeywords relevantes para manter coerência.
- imageKeywords deve ser um prompt fotográfico detalhado de 35-70 palavras: ação observável, personagens, ambiente, enquadramento, iluminação, emoção, objetos importantes, 16:9, sem texto e sem marcas.
- Cada imagem precisa ensinar algo: mostrar um risco, procedimento, comportamento, decisão, contraste antes/depois ou consequência. É proibido pedir fotos genéricas de pessoas sorrindo/reunião sem ação.
- Depois de cada cena importante, inclua uma atividade diretamente ligada ao que o aluno observou: hotspot/identificação, decisão, classificação, ordenação, arrastar e soltar, diagnóstico ou quiz com feedback.
- Preserve continuidade narrativa nos títulos, propósitos, narração e exercícios.
- Para cada slide, copie requiredImagePrompt integralmente para imageKeywords; apenas complemente detalhes específicos sem trocar personagens, roupas ou ambiente.
- O campo narrativeBeat é obrigatório e determina a composição. Slides decide/practice devem transformar a cena ligada em uma ação do aluno, não em explicação textual.
- Não use imagem decorativa. A cena deve conter evidência observável necessária para responder ou executar a atividade seguinte.
''' if config.get('visualCourseMode') == 'illustrated_journey' else ''}

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
- LIMITE de 45 a 70 palavras visíveis por slide; a profundidade adicional pertence à narração
- Uma única mensagem central por slide, expressa por título curto + no máximo 3 pontos ou cards
- Transforme listas longas em composição visual: comparação, processo, diagrama, métrica, citação ou exemplo anotado
- Inclua pelo menos um artefato visual útil: número em destaque, ícone contextual, fluxo, escala, matriz, antes/depois ou imagem com legenda
- Varie a composição entre slides: hero assimétrico, cards, split image, processo horizontal, comparação e painel de métricas
- Evite parágrafos corridos, subtítulos repetitivos e aparência de apostila; use a narração para explicações detalhadas
- Use <strong> apenas nos termos essenciais e preserve contraste WCAG

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

SLIDES DE SIMULADOR/JOGO EDUCATIVO (type="simulator" ou type="game"):
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
  * Escalada do Conhecimento: personagem progride por uma montanha, perde energia ao errar e desbloqueia novos cenários.
  * Corrida do Saber: personagem avança com acertos e encontra obstáculos ao errar, com voltas, combo e chegada cinematográfica.
  * Batalha de Conhecimento: jogador versus IA, habilidades e ataques liberados por respostas corretas.
  * Caça ao Tesouro: mapa interativo por áreas, chaves, baús e perguntas que liberam o percurso.
  * Quiz Show: palco de programa de TV, cronômetro, multiplicadores, ajudas e rodadas progressivas.
  * Palavras Cruzadas e Sudoku Educacional: desafios construídos a partir dos termos do conteúdo, com validação por perguntas.

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
- PROFUNDIDADE OBRIGATORIA (nao gere apenas um quiz com botoes):
  * Modele pelo menos 3 variaveis de estado que mudam durante a atividade (ex.: prazo, custo, risco, qualidade, confianca, energia ou pontuacao)
  * Crie no minimo 3 rodadas/fases ou uma sequencia de 4 decisoes; cada escolha deve alterar o estado e produzir uma consequencia diferente
  * Inclua pelo menos 2 caminhos estrategicos viaveis, com trade-offs reais; evite uma unica resposta obviamente correta em todas as etapas
  * Exiba indicadores visuais atualizados em tempo real e um debrief final que explique os impactos das escolhas
  * Permita reiniciar e testar outra estrategia sem recarregar a pagina
  * Para curso avancado ou interatividade alta/maxima: use 5 ou mais variaveis, eventos condicionais, pelo menos 3 finais e dados contextualizados
  * O JavaScript deve possuir um modelo de estado explicito e separar funcoes de decisao, atualizacao da interface e feedback
  * Implemente OBRIGATORIAMENTE a `requiredMechanic` informada no slide:
    - drag_drop: objetos realmente arrastaveis entre zonas, usando dragstart, dragover/preventDefault e drop; validar posicao/classificacao e permitir corrigir
    - resource_allocation: pelo menos 3 sliders conectados e um orcamento/recurso limitado; alterar um valor recalcula custos, riscos e resultados
    - process_builder: etapas arrastaveis/reordenaveis; validar a sequencia e simular a execucao com consequencias por ordem
    - diagnostic_dashboard: pelo menos 3 controles de entrada/select; recalcular indicadores, diagnostico e recomendacoes em tempo real
    - timed_challenge: desafio com cronometro real, placar, vidas/energia, no minimo 5 rodadas e animacao de acerto/erro (pode ser penalti, alvo ou missao)
    - physics_controls: representacao visual em SVG/canvas, pelo menos 2 sliders, animacao e telemetria calculada em tempo real (engrenagens, motor, fluxo, bomba ou sistema equivalente)
    - tool_workspace: miniaplicativo com abas/modos, entradas reais, calculo/transformacao funcional, resultado e historico ou configuracoes
    - network_explorer: mapa conceitual com no minimo 7 nos e conexoes visuais; selecionar um no atualiza detalhes e progresso de exploracao
    - memory_match: pelo menos 6 pares contextualizados, embaralhamento, cartas viraveis, tentativas, pares encontrados e conclusao
    - word_challenge: forca educacional com palavra contextual, dica pedagogica, alfabeto clicavel, desenho progressivo, erros/vidas e niveis
  * Apenas escrever "arraste" ou "simulador" na tela NAO conta: os eventos e mutacoes correspondentes devem existir no JavaScript
- DIRECAO DE ARTE OBRIGATORIA: siga a `visualDirection` informada no slide. Ela deve ser perceptivel no layout, paleta, componentes e animacoes, nao apenas citada em texto.
- VARIEDADE ENTRE SLIDES: nao reutilize a mesma composicao visual ou a mesma mecanica em atividades vizinhas. Cada experiencia deve parecer um produto educacional proprio.
- PARA type="game": entregue uma experiencia de jogo completa, nunca um formulario ou quiz comum. Inclua tela inicial cinematografica, HUD com XP/moedas/vidas/combo, pelo menos 5 rodadas, personagem ou arena visual, animacoes de movimento, particulas/confete, estados de vitoria/derrota e tela final com conquistas.
- O JavaScript do jogo deve expor um QuestionEngine local com getQuestion(), getRandomQuestion(), getQuestionsByTopic(), getQuestionsByDifficulty(), validateAnswer() e saveResult(). Os dados ficam desacoplados da mecanica para futura troca pela API do banco de questoes.
- ESTADOS VISUAIS: implemente abertura/instrucoes, atividade em andamento, feedback imediato e conclusao/debrief.
- Use dados, perguntas, parametros, termos e consequencias extraidos do tema do slide; e proibido usar Lorem ipsum, "opcao 1" ou conteudo generico.
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
  * Mínimo 6 cartões com frente (pergunta/termo) e verso rico (definição + exemplo/aplicação)
  * Animação 3D de flip ao clicar no cartão (CSS transform: rotateY)
  * Navegação entre cartões (setas ou swipe)
  * Contador de progresso (cartão 3 de 8)
  * Botões "Sei" / "Não sei" para auto-avaliação
  * Resultado final com % de acertos
  * Embaralhar/reiniciar o deck e permitir revisar apenas os cartões marcados como "Não sei"
  * Exibir categoria do conceito, progresso visual e indicador de domínio
- Design: siga `visualDirection`; use cartões com bordas arredondadas, sombras, gradientes, transições e contraste WCAG. Não repita sempre o mesmo cartão azul centralizado.
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
- imageKeywords: no modo padrão, palavras-chave em inglês; na Jornada Visual Ilustrada, prompt fotográfico detalhado em inglês conforme a direção especial
- moduleName: SEMPRE inclua o nome do módulo
- narrationScript: MÍNIMO 5 frases completas e detalhadas
- NUNCA retorne conteúdo vazio ou com apenas 1-2 linhas"""

        retries = 0
        max_retries = 2
        batch_success = False
        quality_type = batch[0].get("type") if len(batch) == 1 else ""
        quality_checked = quality_type in {"simulator", "game", "flashcard", "timeline", "case_study"}
        required_simulator_mechanic = (
            _required_simulator_mechanic(batch[0]) if quality_type in ("simulator", "game") else ""
        )
        models = [PRIMARY_MODEL, FALLBACK_MODEL, FALLBACK_MODEL]  # Fallback chain
        while retries <= max_retries:
            provider, model = models[min(retries, len(models)-1)]
            try:
                chat = _new_chat(f"{session_id}_story_b{batch_start}_r{retries}", provider=provider, model=model)
                attempt_prompt = prompt
                if quality_checked and retries > 0:
                    if quality_type in ("simulator", "game"):
                        attempt_prompt += """

REVISAO OBRIGATORIA DO SIMULADOR:
A tentativa anterior ficou simples demais. Entregue agora uma simulacao de nivel profissional,
nao um quiz linear: use estado explicito, multiplas rodadas, indicadores que se influenciam,
consequencias acumuladas, caminhos alternativos, debrief por estrategia e botao para reiniciar.
O HTML/CSS/JS deve estar completo no JSON e funcionar sem bibliotecas externas.
MECANICA OBRIGATORIA DESTA GERACAO: """ + required_simulator_mechanic + """.
Implemente os eventos e alteracoes de estado reais dessa mecanica; texto ou botoes que apenas
simulem a acao nao serao aceitos."""
                    elif quality_type == "timeline":
                        attempt_prompt += """

REVISAO OBRIGATORIA DA LINHA DO TEMPO:
A tentativa anterior ficou vazia ou superficial. Entregue pelo menos 5 marcos contextualizados,
com navegacao anterior/proximo, marcador ativo, barra de progresso, detalhes explicativos e
impacto de cada evento. Todos os marcos devem ser clicaveis e o JavaScript deve funcionar sem
bibliotecas externas."""
                    elif quality_type == "flashcard":
                        attempt_prompt += """

REVISAO OBRIGATORIA DOS FLASHCARDS:
A tentativa anterior ficou simples ou repetitiva. Entregue no minimo 6 cartoes contextualizados,
com frente, definicao e exemplo/aplicacao no verso, flip 3D, navegacao, embaralhamento, progresso,
marcacao Sei/Nao sei, revisao dos nao dominados e resultado final. Siga rigorosamente a direcao
de arte do slide e use uma composicao visual distinta das demais atividades."""
                    else:
                        attempt_prompt += """

REVISAO OBRIGATORIA DO ESTUDO DE CASO:
A tentativa anterior ficou superficial. Entregue contexto realista, dados e evidencias,
pelo menos 3 perguntas de reflexao/decisao com consequencias, analise revelavel e debrief com
licoes aprendidas. A interacao deve funcionar em JavaScript sem bibliotecas externas."""
                response = await chat.send_message(UserMessage(text=attempt_prompt))
                data = _extract_json(response)
                if data and "slides" in data:
                    for j, slide_data in enumerate(data["slides"]):
                        if not slide_data.get("moduleName") and j < len(batch):
                            slide_data["moduleName"] = batch[j].get("moduleName", "")
                        if illustrated_journey and j < len(batch):
                            source_slide = batch[j]
                            slide_data["narrativeBeat"] = source_slide.get("narrativeBeat", "context")
                            slide_data["imageRole"] = source_slide.get("imageRole", "action_scene")
                            slide_data["linkedSceneTitle"] = source_slide.get("linkedSceneTitle", "")
                            slide_data["storyContext"] = source_slide.get("storyContext", {})
                            # Do not trust a provider's short/generic stock-photo keywords in this mode.
                            # The deterministic prompt carries the recurring cast, action and teaching evidence.
                            slide_data["imageKeywords"] = source_slide.get("requiredImagePrompt") or _illustrated_image_prompt(
                                source_slide, config, story_bible
                            )
                    if quality_checked and data["slides"]:
                        generated_html = _simulator_html_from_slide(data["slides"][0])
                        complexity = (
                            _simulator_complexity_score(generated_html, required_simulator_mechanic)
                            if quality_type == "simulator"
                            else _rich_interactive_complexity_score(generated_html, quality_type)
                        )
                        if complexity < 6:
                            logger.warning(
                                "%s storyboard batch %s scored %s/10; regenerating with richer constraints",
                                quality_type,
                                batch_start,
                                complexity,
                            )
                            retries += 1
                            if retries <= max_retries:
                                await asyncio.sleep(2)
                            continue
                        logger.info(
                            "%s storyboard batch %s accepted with complexity %s/10",
                            quality_type,
                            batch_start,
                            complexity,
                        )
                    # Older providers may return HTML in the
                    # legacy `content` field. Normalize every interactive
                    # slide before it reaches the storyboard UI.
                    for slide_data in data["slides"]:
                        _normalize_interactive_storyboard_slide(slide_data)
                        _normalize_visual_content_slide(slide_data)
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
                    fallback_html = _build_visual_content_fallback_html(sl)
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

                fallback_elements = [{
                    "type": "text", "content": fallback_html,
                    "position": "left", "width": 1050, "height": 680,
                }]
                fallback_source = {
                    **sl,
                    "title": title_text,
                    "moduleName": module_text,
                    "notes": purpose,
                    "elements": [{"type": "text", "content": fallback_html}],
                }
                if stype == "case_study":
                    fallback_elements = [{
                        "type": "html",
                        "htmlContent": _build_case_study_fallback_html(fallback_source),
                    }]
                elif stype == "infographic":
                    fallback_elements = [{
                        "type": "html",
                        "htmlContent": _build_infographic_fallback_html(fallback_source),
                    }]
                elif stype == "timeline":
                    fallback_elements = [{
                        "type": "html",
                        "htmlContent": _build_timeline_fallback_html(fallback_source),
                    }]
                elif stype == "flashcard":
                    fallback_elements = [{
                        "type": "html",
                        "htmlContent": _build_flashcard_fallback_html(fallback_source),
                    }]
                elif stype in ("simulator", "game"):
                    fallback_elements = [{
                        "type": "html",
                        "htmlContent": (
                            _build_game_fallback_html(fallback_source)
                            if stype == "game"
                            else _build_simulator_fallback_html(fallback_source)
                        ),
                    }]

                all_slides.append({
                    "id": sl.get("id", ""),
                    "title": title_text,
                    "type": stype,
                    "moduleName": module_text,
                    "imageKeywords": (
                        sl.get("requiredImagePrompt") or _illustrated_image_prompt(sl, config, story_bible)
                        if illustrated_journey
                        else title_text.split(" ")[0].lower() + " professional"
                    ),
                    "narrativeBeat": sl.get("narrativeBeat", "") if illustrated_journey else "",
                    "imageRole": sl.get("imageRole", "") if illustrated_journey else "",
                    "linkedSceneTitle": sl.get("linkedSceneTitle", "") if illustrated_journey else "",
                    "storyContext": sl.get("storyContext", {}) if illustrated_journey else {},
                    "elements": fallback_elements,
                    "narrationScript": purpose if purpose else f"Neste slide, vamos abordar {title_text.lower()}.",
                    "librasScript": purpose if purpose else title_text,
                    "notes": "",
                    "quizQuestions": fallback_quiz,
                })

    for slide in all_slides:
        _normalize_interactive_storyboard_slide(slide)
        _normalize_visual_content_slide(slide)
    return {
        "slides": all_slides,
        "qualityProfile": "illustrated_journey" if illustrated_journey else "premium",
        **({"visualStoryBible": story_bible} if illustrated_journey else {}),
    }


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
        "fonts": {"heading": "'Manrope', 'Segoe UI', sans-serif", "body": "'IBM Plex Sans', sans-serif"},
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


def _slide_plain_text(slide_context: Optional[dict]) -> str:
    """Extract useful, visible slide text for contextual media prompts."""
    if not slide_context:
        return ""
    parts = [
        str(slide_context.get("title") or ""),
        str(slide_context.get("moduleName") or ""),
        str(slide_context.get("body") or slide_context.get("text") or ""),
        str(slide_context.get("notes") or slide_context.get("narrationScript") or ""),
    ]
    for element in slide_context.get("elements", []):
        raw_element = str(element.get("content") or element.get("htmlContent") or "")
        # Only visible HTML may become pedagogical source text.  Removing tags
        # alone is insufficient because it leaves CSS and JavaScript behind,
        # which previously produced flashcards containing declarations such as
        # `justify-content: center`.
        raw_element = re.sub(
            r"<(?:style|script|template|noscript)\b[^>]*>[\s\S]*?</(?:style|script|template|noscript)>",
            " ",
            raw_element,
            flags=re.IGNORECASE,
        )
        parts.append(raw_element)
    combined = " ".join(parts)
    combined = re.sub(
        r"<(?:style|script|template|noscript)\b[^>]*>[\s\S]*?</(?:style|script|template|noscript)>",
        " ",
        combined,
        flags=re.IGNORECASE,
    )
    clean = re.sub(r"<[^>]+>", " ", combined)
    clean = html.unescape(re.sub(r"\s+", " ", clean)).strip()
    return clean[:1800]


def _build_contextual_image_prompt(keyword: str, slide_context: Optional[dict] = None) -> str:
    context = _slide_plain_text(slide_context)
    title = (slide_context or {}).get("title") or keyword
    module = (slide_context or {}).get("moduleName") or ""
    return (
        "Create one professional 16:9 visual for a Brazilian corporate e-learning slide. "
        f"Slide title: {title}. Module: {module}. Visual concepts: {keyword}. "
        f"Source content that the image must represent accurately: {context}. "
        "Show a concrete scene, objects or diagram-like composition that directly explains these concepts. "
        "Clean composition, realistic professional lighting, culturally neutral, no random landscape, "
        "no decorative stock-photo clichés, no written words, no captions, no logos and no watermark."
    )


async def _persist_generated_image(
    image_bytes: bytes, prompt: str, project_dir: str, project_id: str, provider: str
) -> Optional[str]:
    import hashlib
    seed = hashlib.md5(prompt.encode(), usedforsecurity=False).hexdigest()[:12]
    fname = f"ai_img_{seed}.png"
    fpath = os.path.join(project_dir, project_id, "assets", fname)
    os.makedirs(os.path.dirname(fpath), exist_ok=True)
    with open(fpath, "wb") as f:
        f.write(image_bytes)

    try:
        from services.asset_store import store_asset_async
        asset_db = await _get_motor_db()
        if asset_db is not None:
            persisted = await store_asset_async(asset_db, project_id, fname, fpath)
            if not persisted:
                logger.error("Generated image was not persisted: %s/%s", project_id, fname)
                return None
    except Exception as exc:
        logger.error("Generated image persistence failed: %s", exc)
        return None

    image_url = f"/api/projects/{project_id}/assets/{fname}"
    try:
        asyncio.ensure_future(_auto_save_gallery(image_url, prompt[:300], project_id))
    except Exception:
        pass
    logger.info("Contextual image generated via %s -> %s", provider, fname)
    return image_url


async def _openai_image_bytes(prompt: str) -> Optional[bytes]:
    """Generate one image through the official OpenAI Image API."""
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    import httpx
    payload = {
        "model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2"),
        "prompt": prompt,
        "size": os.environ.get("OPENAI_IMAGE_SIZE", "1536x1024"),
        "quality": os.environ.get("OPENAI_IMAGE_QUALITY", "medium"),
        "n": 1,
    }
    timeout = float(os.environ.get("OPENAI_IMAGE_TIMEOUT_SECONDS", "180"))
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
    response.raise_for_status()
    item = (response.json().get("data") or [{}])[0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            download = await client.get(item["url"])
        download.raise_for_status()
        return download.content
    return None


async def _legacy_gemini_image_bytes(prompt: str) -> Optional[bytes]:
    if not OPENAI_KEY:
        return None
    chat = LlmChat(
        api_key=OPENAI_KEY,
        session_id=f"img_{uuid.uuid4().hex[:8]}",
        system_message="You generate accurate educational images.",
    ).with_model(IMAGE_MODEL[0], IMAGE_MODEL[1]).with_params(modalities=["image", "text"])
    _, images = await chat.send_message_multimodal_response(UserMessage(text=prompt))
    if images:
        return base64.b64decode(images[0]["data"])
    return None


async def _leonardo_image_bytes(prompt: str) -> Optional[bytes]:
    """Generate and download an image through the configured Leonardo account.

    Leonardo used to be reachable only when the author explicitly selected the
    Leonardo media type for a slide.  The normal ``ai_image`` path therefore
    produced text-only slides whenever OpenAI/Gemini image generation was not
    available, even though Leonardo was healthy in the integrations panel.
    """
    if not (os.environ.get("LEONARDO_API_KEY") or "").strip():
        return None

    import httpx
    from services.leonardo_ai import generate_and_wait

    image_urls = await generate_and_wait(
        prompt=prompt,
        width=1024,
        height=576,
        num_images=1,
    )
    if not image_urls:
        return None

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        response = await client.get(image_urls[0])
    response.raise_for_status()
    return response.content


async def _fetch_stock_image(
    keyword: str, project_dir: str, project_id: str, slide_context: Optional[dict] = None
) -> Optional[str]:
    """Generate a contextual image. Never substitutes unrelated random photos."""
    prompt = _build_contextual_image_prompt(keyword, slide_context)
    providers = [
        ("openai", _openai_image_bytes),
        ("gemini", _legacy_gemini_image_bytes),
        ("leonardo", _leonardo_image_bytes),
    ]
    for provider, generate in providers:
        try:
            image_bytes = await generate(prompt)
            if image_bytes:
                return await _persist_generated_image(
                    image_bytes, prompt, project_dir, project_id, provider
                )
        except Exception as exc:
            logger.warning(
                "Contextual image generation via %s failed for '%s': %s",
                provider, keyword, str(exc)[:240],
            )
    logger.warning("No contextual image was generated for '%s'; slide will use a text layout", keyword)
    return None


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
    "<style id='__scormify_fit_v3'>html,body{margin:0!important;padding:0!important;width:100%;height:100%;"
    "overflow:hidden!important;}body{display:block!important;position:relative!important;}</style>"
    "<script>(function(){function b(){var bd=document.body;"
    "if(!bd||document.getElementById('__stage'))return;"
    "var st=document.createElement('div');st.id='__stage';"
    "st.style.cssText='width:960px;position:absolute;left:0;top:0;margin:0;transform-origin:0 0;';"
    "while(bd.firstChild){st.appendChild(bd.firstChild);}bd.appendChild(st);"
    "function fit(){st.style.transform='none';var sr=st.getBoundingClientRect(),minX=0,minY=0;"
    "var maxX=Math.max(960,st.scrollWidth,st.offsetWidth),maxY=Math.max(540,st.scrollHeight,st.offsetHeight);"
    "Array.prototype.forEach.call(st.querySelectorAll('*'),function(n){var cs=getComputedStyle(n);if(cs.display==='none'||cs.visibility==='hidden')return;var r=n.getBoundingClientRect();"
    "if(!r.width&&!r.height)return;minX=Math.min(minX,r.left-sr.left);minY=Math.min(minY,r.top-sr.top);maxX=Math.max(maxX,r.right-sr.left);maxY=Math.max(maxY,r.bottom-sr.top);});"
    "var cw=maxX-minX,ch=maxY-minY,pad=12,s=Math.min((innerWidth-pad*2)/cw,(innerHeight-pad*2)/ch,1);s=Math.max(.1,s);"
    "var tx=(innerWidth-cw*s)/2-minX*s,ty=(innerHeight-ch*s)/2-minY*s;st.style.transform='translate('+tx+'px,'+ty+'px) scale('+s+')';}"
    "window.addEventListener('resize',fit);fit();setTimeout(fit,300);setTimeout(fit,1000);}"
    "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',b);}"
    "else{b();}})();</script>"
)

_FIT_UPGRADE_SNIPPET = (
    "<style id='__scormify_fit_v3'>html,body{overflow:hidden!important;}"
    "body{display:block!important;position:relative!important;}</style>"
    "<script>(function(){function u(){var st=document.getElementById('__stage');if(!st)return;"
    "st.style.position='absolute';st.style.left='0';st.style.top='0';st.style.margin='0';"
    "st.style.transformOrigin='0 0';function fit(){st.style.transform='none';var sr=st.getBoundingClientRect(),minX=0,minY=0;"
    "var maxX=Math.max(960,st.scrollWidth,st.offsetWidth),maxY=Math.max(540,st.scrollHeight,st.offsetHeight);"
    "Array.prototype.forEach.call(st.querySelectorAll('*'),function(n){var cs=getComputedStyle(n);if(cs.display==='none'||cs.visibility==='hidden')return;var r=n.getBoundingClientRect();if(!r.width&&!r.height)return;"
    "minX=Math.min(minX,r.left-sr.left);minY=Math.min(minY,r.top-sr.top);maxX=Math.max(maxX,r.right-sr.left);maxY=Math.max(maxY,r.bottom-sr.top);});"
    "var cw=maxX-minX,ch=maxY-minY,pad=12,s=Math.min((innerWidth-pad*2)/cw,(innerHeight-pad*2)/ch,1);s=Math.max(.1,s);"
    "var tx=(innerWidth-cw*s)/2-minX*s,ty=(innerHeight-ch*s)/2-minY*s;st.style.transform='translate('+tx+'px,'+ty+'px) scale('+s+')';}"
    "addEventListener('resize',fit);fit();setTimeout(fit,300);setTimeout(fit,1000);}"
    "if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',u);else u();})();</script>"
)


def _wrap_interactive_fullbleed(html_content: str) -> str:
    """Inject the auto-fit snippet into interactive HTML (idempotent)."""
    if "__scormify_fit_v3" in html_content:
        return html_content
    if "__stage" in html_content:
        if "</body>" in html_content:
            return html_content.replace("</body>", _FIT_UPGRADE_SNIPPET + "</body>", 1)
        return html_content + _FIT_UPGRADE_SNIPPET
    if "</body>" in html_content:
        return html_content.replace("</body>", _FIT_SNIPPET + "</body>", 1)
    return html_content + _FIT_SNIPPET


_INTERACTIVE_PLACEHOLDERS = (
    "css styles here",
    "html content here",
    "javascript for",
    "flashcards html content",
    "todo: implement",
    "your content here",
    "conteúdo aqui",
)


def _interactive_html_is_functional(html_content: str, content_type: str = "") -> bool:
    """Reject empty LLM skeletons before they become blank course slides."""
    raw = (html_content or "").strip()
    lowered = raw.lower()
    if len(raw) < 500 or any(marker in lowered for marker in _INTERACTIVE_PLACEHOLDERS):
        return False
    if "<body" not in lowered or "<script" not in lowered:
        return False
    # A long stylesheet/script skeleton can pass the size checks while the
    # body has no visible content. Require meaningful text in the body.
    body_match = re.search(r"<body[^>]*>([\s\S]*?)</body>", raw, re.IGNORECASE)
    body_text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>|<[^>]+>", " ", body_match.group(1) if body_match else "", flags=re.IGNORECASE)
    body_text = html.unescape(re.sub(r"\s+", " ", body_text)).strip()
    if len(body_text) < 40:
        return False
    if content_type == "flashcard":
        # A flashcard must contain real card data plus an actual flip action.
        has_card_data = any(
            token in lowered for token in ("const cards", "let cards", "flashcards =", "data-front", "data-answer")
        )
        has_flip = "rotatey" in lowered or "classlist.toggle('flipped" in lowered or 'classlist.toggle("flipped' in lowered
        if not has_card_data or not has_flip:
            return False
        # Card data must be educational prose, never stylesheet fragments.
        # Inspect only the data declaration so legitimate CSS in <style> does
        # not trigger a false rejection.
        card_data_match = re.search(
            r"(?:const|let|var)\s+(?:cards|flashcards)\s*=\s*([\s\S]{1,12000}?\])\s*;",
            raw,
            re.IGNORECASE,
        )
        if card_data_match and re.search(
            r"(?i)(?:justify-content|align-items|grid-template|font-size|border-radius|"
            r"background-color|display\s*:\s*(?:flex|grid|block)|[.#][\w-]+\s*\{)",
            card_data_match.group(1),
        ):
            return False
    return True


def _build_simulator_fallback_html(sb_slide: dict) -> str:
    """Build a complete simulator when the model returns missing/broken HTML.

    A rejected simulator must never silently become a mostly empty text slide.
    This deterministic activity provides classification, scoring, feedback,
    keyboard/click alternatives and restart support without external assets.
    """
    raw_title = str(sb_slide.get("title") or "Simulação prática")
    title = re.sub(r"^simula(?:ção|cao)\s*:\s*", "", raw_title, flags=re.IGNORECASE).strip() or raw_title
    context = _slide_plain_text(sb_slide)
    context = re.sub(r"\s+", " ", context).strip()
    candidates = [
        part.strip(" -•")
        for part in re.split(r"(?<=[.!?;:])\s+|\s+[•-]\s+", context)
        if len(part.strip(" -•")) >= 24
    ]
    defaults = [
        f"Identificar os conceitos centrais de {title}",
        f"Relacionar {title} a uma situação prática",
        "Escolher uma resposta com base em evidências",
        "Analisar as consequências antes de decidir",
        "Revisar a estratégia a partir do feedback",
        "Transferir o aprendizado para um novo contexto",
    ]
    items = (candidates + defaults)[:6]
    while len(items) < 6:
        items.append(defaults[len(items) % len(defaults)])
    records = [
        {"text": text[:180], "category": index % 3}
        for index, text in enumerate(items)
    ]
    items_json = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    safe_title = html.escape(title)
    template = r'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>*{box-sizing:border-box}body{margin:0;min-height:540px;font-family:Inter,Arial,sans-serif;background:linear-gradient(135deg,#eef6ff,#f8fafc);color:#172033;display:grid;place-items:center}.app{width:920px;padding:22px}.top{display:flex;justify-content:space-between;gap:20px;align-items:end;margin-bottom:15px}.eyebrow{font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:#2563eb;font-weight:800}.title{font-size:27px;margin:5px 0 2px}.help{margin:0;color:#64748b}.score{background:#172033;color:#fff;padding:10px 15px;border-radius:14px;font-weight:800;white-space:nowrap}.board{display:grid;grid-template-columns:300px 1fr;gap:15px}.bank,.zones{border:1px solid #cbd5e1;background:#fff;border-radius:18px;padding:15px;box-shadow:0 12px 30px #0f172a12}.bank h2,.zones h2{font-size:15px;margin:0 0 10px}.item{padding:9px 11px;margin:7px 0;border-radius:10px;background:#263b55;color:#fff;font-size:13px;line-height:1.25;cursor:grab;border:2px solid transparent}.item.selected{border-color:#38bdf8;box-shadow:0 0 0 3px #38bdf833}.zone-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.zone{min-height:220px;border:2px dashed #93a4ba;border-radius:13px;padding:9px;background:#f8fafc}.zone.over{border-color:#2563eb;background:#eff6ff}.zone h3{font-size:13px;margin:0 0 8px;text-align:center}.zone .item{cursor:pointer}.feedback{min-height:24px;margin:12px 0 0;font-weight:700;text-align:center}.ok{color:#047857}.bad{color:#b91c1c}.actions{display:flex;justify-content:center;gap:10px;margin-top:10px}button{border:0;border-radius:10px;padding:10px 17px;background:#2563eb;color:#fff;font-weight:800;cursor:pointer}button.secondary{background:#475569}@media(max-width:720px){.app{width:100%;padding:12px}.board{grid-template-columns:1fr}.zone-grid{grid-template-columns:1fr}.zone{min-height:90px}}
</style></head><body><main class="app"><header class="top"><div><div class="eyebrow">Simulação interativa</div><h1 class="title">__TITLE__</h1><p class="help">Arraste os cartões para a categoria adequada. Você também pode selecionar um cartão e clicar numa categoria.</p></div><div id="score" class="score">0 / 6</div></header><section class="board"><div class="bank"><h2>Situações para analisar</h2><div id="bank"></div></div><div class="zones"><h2>Classifique cada situação</h2><div class="zone-grid"><div class="zone" data-cat="0"><h3>Compreender</h3></div><div class="zone" data-cat="1"><h3>Aplicar</h3></div><div class="zone" data-cat="2"><h3>Avaliar</h3></div></div><div id="feedback" class="feedback"></div><div class="actions"><button onclick="check()">Verificar estratégia</button><button class="secondary" onclick="restart()">Reiniciar</button></div></div></section></main>
<script>const data=__ITEMS__;let selected=null;const bank=document.getElementById('bank'),feedback=document.getElementById('feedback');function card(x,i){const e=document.createElement('div');e.className='item';e.textContent=x.text;e.draggable=true;e.dataset.i=i;e.onclick=()=>select(e);e.ondragstart=v=>v.dataTransfer.setData('text/plain',i);return e}function select(e){document.querySelectorAll('.item').forEach(x=>x.classList.remove('selected'));selected=e;e.classList.add('selected')}function place(i,z){const e=document.querySelector('[data-i="'+i+'"]');if(e){z.appendChild(e);e.classList.remove('selected');selected=null;feedback.textContent=''}}document.querySelectorAll('.zone').forEach(z=>{z.ondragover=e=>{e.preventDefault();z.classList.add('over')};z.ondragleave=()=>z.classList.remove('over');z.ondrop=e=>{e.preventDefault();z.classList.remove('over');place(e.dataTransfer.getData('text/plain'),z)};z.onclick=e=>{if(e.target===z||e.target.tagName==='H3'){if(selected)place(selected.dataset.i,z)}}});function check(){let right=0,placed=0;document.querySelectorAll('.zone .item').forEach(e=>{placed++;if(+e.parentElement.dataset.cat===data[+e.dataset.i].category)right++});score.textContent=right+' / '+data.length;if(placed<data.length){feedback.className='feedback bad';feedback.textContent='Classifique todos os cartões antes de verificar.'}else if(right===data.length){feedback.className='feedback ok';feedback.textContent='Excelente! Você relacionou compreensão, aplicação e avaliação.'}else{feedback.className='feedback bad';feedback.textContent='Você acertou '+right+'. Reavalie as escolhas usando o contexto e as consequências.'}}function restart(){bank.innerHTML='';data.forEach((x,i)=>bank.appendChild(card(x,i)));score.textContent='0 / '+data.length;feedback.textContent='';feedback.className='feedback'}restart();</script></body></html>'''
    return template.replace("__TITLE__", safe_title).replace("__ITEMS__", items_json)


def _build_game_fallback_html(sb_slide: dict, bank_questions: list | None = None) -> str:
    """Build a premium question-driven game when AI game HTML is unusable.

    Question data and game mechanics are deliberately separated by the local
    QuestionEngine contract, allowing an API-backed bank to replace the
    embedded questions without changing the penalty game.
    """
    title = re.sub(r"^(?:jogo|game)\s*:\s*", "", str(sb_slide.get("title") or "Desafio do Conhecimento"), flags=re.I)
    source = re.sub(r"\s+", " ", _slide_plain_text(sb_slide)).strip()
    facts = [p.strip(" -•") for p in re.split(r"(?<=[.!?;:])\s+|\s+[•-]\s+", source) if len(p.strip(" -•")) >= 24]
    defaults = [
        f"Aplicar corretamente os conceitos de {title}",
        f"Analisar evidências antes de decidir sobre {title}",
        "Relacionar teoria, contexto e consequências práticas",
        "Usar feedback para ajustar a estratégia adotada",
        "Transferir o aprendizado para uma nova situação",
    ]
    facts = (facts + defaults)[:5]
    while len(facts) < 5:
        facts.append(defaults[len(facts) % len(defaults)])
    questions = []
    for imported in (bank_questions or [])[:8]:
        alternatives = imported.get("alternatives") or []
        answer_id = str(imported.get("correctAnswer") or "").casefold()
        correct_index = next(
            (i for i, alt in enumerate(alternatives) if str(alt.get("id") or "").casefold() == answer_id),
            -1,
        )
        if imported.get("question") and len(alternatives) >= 2 and correct_index >= 0:
            questions.append({
                "id": imported.get("id") or f"bank{len(questions) + 1}",
                "topic": imported.get("topic") or str(sb_slide.get("moduleName") or title),
                "difficulty": imported.get("difficulty") or "medio",
                "question": imported["question"],
                "alternatives": [str(alt.get("text") or "") for alt in alternatives],
                "correct": correct_index,
                "explanation": imported.get("explanation") or "Revise o conceito e tente novamente.",
            })
    distractors = [
        "Ignorar o contexto e decidir por intuição",
        "Memorizar termos sem relacioná-los à prática",
        "Adiar qualquer análise até o problema desaparecer",
    ]
    for index, fact in enumerate(facts[len(questions):], start=len(questions)):
        if len(questions) >= 5:
            break
        questions.append({
            "id": f"q{index + 1}",
            "topic": str(sb_slide.get("moduleName") or title),
            "difficulty": ("facil", "medio", "dificil", "medio", "dificil")[index],
            "question": f"Na rodada {index + 1}, qual alternativa melhor representa o aprendizado central?",
            "alternatives": [fact[:190], *distractors],
            "correct": 0,
            "explanation": f"A resposta conecta diretamente o conteúdo do curso: {fact[:230]}",
        })
    questions = questions[:8]
    questions_json = json.dumps(questions, ensure_ascii=False).replace("</", "<\\/")
    safe_title = html.escape(title)
    template = r'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
*{box-sizing:border-box}body{margin:0;min-height:540px;overflow:hidden;font-family:Inter,system-ui,sans-serif;color:#fff;background:radial-gradient(circle at 50% 15%,#263d75 0,#101a39 42%,#070b19 100%)}button{font:inherit}.game{width:960px;height:540px;position:relative;overflow:hidden}.glow{position:absolute;width:420px;height:420px;border-radius:50%;filter:blur(80px);opacity:.28}.g1{background:#8b5cf6;left:-140px;top:-180px}.g2{background:#06b6d4;right:-170px;bottom:-210px}.screen{position:absolute;inset:0;display:grid;place-items:center;padding:30px;transition:.45s}.hidden{opacity:0;pointer-events:none;transform:scale(.96)}.start-card,.finish-card{width:620px;padding:38px;border:1px solid #ffffff26;border-radius:30px;background:linear-gradient(145deg,#172554e8,#111827e8);box-shadow:0 30px 90px #0009,inset 0 1px #fff3;text-align:center;backdrop-filter:blur(18px)}.logo{font-size:58px;filter:drop-shadow(0 0 22px #22d3ee)}h1{font-size:36px;margin:8px 0;background:linear-gradient(90deg,#fff,#67e8f9,#c4b5fd);-webkit-background-clip:text;color:transparent}.sub{color:#b8c6e6;line-height:1.5}.cta{border:0;border-radius:16px;padding:14px 30px;color:#06101f;font-weight:900;background:linear-gradient(90deg,#22d3ee,#a7f3d0);cursor:pointer;box-shadow:0 10px 35px #22d3ee55;transition:.2s}.cta:hover{transform:translateY(-3px) scale(1.03)}.play{display:block;padding:16px 22px}.hud{height:66px;display:flex;align-items:center;justify-content:space-between;gap:12px}.brand{font-weight:900;letter-spacing:.05em}.chips{display:flex;gap:8px}.chip{padding:8px 12px;border-radius:99px;background:#ffffff12;border:1px solid #ffffff20;font-weight:800;font-size:13px}.arena{height:250px;position:relative;border-radius:25px;overflow:hidden;background:linear-gradient(#176148 0 7%,#27aa68 7% 100%);border:3px solid #dffbf0;box-shadow:0 18px 50px #0007}.crowd{height:74px;background:repeating-linear-gradient(90deg,#35275d 0 8px,#593a80 8px 16px);position:relative}.crowd:after{content:'🙌  🎉  🙌  ⭐  🙌  🎉  🙌  ⭐  🙌';position:absolute;inset:19px 0;text-align:center;font-size:26px;letter-spacing:21px;animation:crowd .55s infinite alternate}.goal{position:absolute;width:310px;height:128px;left:325px;top:82px;border:7px solid white;border-bottom:0;box-shadow:inset 0 0 0 2px #ffffff55;background:repeating-linear-gradient(45deg,#ffffff18 0 2px,transparent 2px 17px)}.keeper{position:absolute;left:452px;top:132px;font-size:47px;transition:.6s cubic-bezier(.2,.8,.2,1);filter:drop-shadow(0 7px 5px #0005)}.ball{position:absolute;left:467px;bottom:18px;font-size:34px;z-index:3;filter:drop-shadow(0 7px 5px #0008)}.ball.shoot-left{animation:shootL .75s forwards}.ball.shoot-right{animation:shootR .75s forwards}.keeper.dive-left{transform:translate(-88px,-20px) rotate(-38deg)}.keeper.dive-right{transform:translate(88px,-20px) rotate(38deg)}.panel{margin-top:12px;border-radius:20px;padding:15px 18px;background:#101a34e8;border:1px solid #ffffff1e}.progress{height:6px;border-radius:8px;background:#ffffff13;overflow:hidden}.progress i{display:block;height:100%;width:0;background:linear-gradient(90deg,#22d3ee,#a78bfa);transition:.45s}.question{font-size:17px;font-weight:850;text-align:center;margin:10px 0}.answers{display:grid;grid-template-columns:1fr 1fr;gap:8px}.answer{min-height:42px;border:1px solid #ffffff1b;border-radius:12px;background:#ffffff0d;color:#edf6ff;padding:8px 12px;cursor:pointer;font-size:12px;font-weight:700;transition:.18s}.answer:hover{transform:translateY(-2px);border-color:#67e8f9;background:#164e6366}.answer.correct{background:#059669;border-color:#6ee7b7}.answer.wrong{background:#dc2626;border-color:#fca5a5;animation:shake .28s}.feedback{height:18px;margin-top:7px;text-align:center;font-size:12px;color:#a5f3fc}.particle{position:absolute;width:8px;height:8px;border-radius:50%;pointer-events:none;animation:burst 1s forwards}.achievement{display:inline-block;padding:8px 13px;border-radius:99px;background:#f59e0b22;border:1px solid #fbbf24;color:#fde68a;font-weight:900;margin:12px}.stats{display:flex;justify-content:center;gap:12px;margin:20px}.stats b{min-width:105px;padding:14px;border-radius:16px;background:#ffffff0d}.stats small{display:block;color:#94a3b8;margin-top:4px}@keyframes crowd{to{transform:translateY(-5px)}}@keyframes shootL{to{left:370px;bottom:125px;transform:scale(.55) rotate(420deg)}}@keyframes shootR{to{left:555px;bottom:125px;transform:scale(.55) rotate(420deg)}}@keyframes shake{25%{transform:translateX(-6px)}75%{transform:translateX(6px)}}@keyframes burst{to{transform:translate(var(--x),var(--y)) rotate(360deg);opacity:0}}@media(max-width:800px){.game{width:100vw}.play{padding:8px}.start-card,.finish-card{width:92%}.answers{grid-template-columns:1fr}.arena{height:220px}.goal{left:calc(50% - 155px)}.keeper{left:calc(50% - 24px)}.ball{left:calc(50% - 17px)}}
</style></head><body><main class="game"><div class="glow g1"></div><div class="glow g2"></div><section id="start" class="screen"><div class="start-card"><div class="logo">⚽</div><h1>Penalty Quest</h1><h2>__TITLE__</h2><p class="sub">Responda, construa seu combo e converta conhecimento em gols. Cinco rodadas, três vidas e uma conquista épica.</p><button class="cta" onclick="Game.start()">COMEÇAR CAMPEONATO</button></div></section><section id="play" class="screen hidden play"><header class="hud"><div class="brand">⚡ KNOWLEDGE LEAGUE</div><div class="chips"><span class="chip">❤️ <b id="lives">3</b></span><span class="chip">🔥 <b id="combo">0</b>x</span><span class="chip">⭐ <b id="xp">0</b> XP</span><span class="chip">🪙 <b id="coins">0</b></span></div></header><div class="arena" id="arena"><div class="crowd"></div><div class="goal"></div><div id="keeper" class="keeper">🧤</div><div id="ball" class="ball">⚽</div></div><div class="panel"><div class="progress"><i id="bar"></i></div><div id="question" class="question"></div><div id="answers" class="answers"></div><div id="feedback" class="feedback"></div></div></section><section id="finish" class="screen hidden"><div class="finish-card"><div class="logo">🏆</div><h1 id="finishTitle">Campeonato concluído!</h1><span id="achievement" class="achievement"></span><div class="stats"><b id="finalXp"></b><b id="finalCoins"></b><b id="finalAccuracy"></b></div><p class="sub">Seu progresso foi registrado localmente e está pronto para integração com o LMS.</p><button class="cta" onclick="Game.restart()">JOGAR NOVAMENTE</button></div></section></main><script>
const questionBank=__QUESTIONS__;
const QuestionEngine={questions:questionBank,results:[],getQuestion(id){return this.questions.find(q=>q.id===id)},getRandomQuestion(){return this.questions[Math.floor(Math.random()*this.questions.length)]},getQuestionsByTopic(topic){return this.questions.filter(q=>q.topic===topic)},getQuestionsByDifficulty(level){return this.questions.filter(q=>q.difficulty===level)},validateAnswer(question,index){return index===question.correct},saveResult(result){this.results.push(result);try{localStorage.setItem('scormify-game-results',JSON.stringify(this.results))}catch(e){}return result}};
const Game={round:0,xp:0,coins:0,lives:3,combo:0,correct:0,locked:false,start(){start.classList.add('hidden');play.classList.remove('hidden');this.next()},restart(){this.round=0;this.xp=0;this.coins=0;this.lives=3;this.combo=0;this.correct=0;finish.classList.add('hidden');play.classList.remove('hidden');this.sync();this.next()},sync(){lives.textContent=this.lives;combo.textContent=this.combo;xp.textContent=this.xp;coins.textContent=this.coins;bar.style.width=(this.round/questionBank.length*100)+'%'},next(){this.locked=false;ball.className='ball';keeper.className='keeper';feedback.textContent='';if(this.round>=questionBank.length||this.lives<=0)return this.end();this.sync();const q=questionBank[this.round];question.textContent=q.question;answers.innerHTML='';q.alternatives.map((text,index)=>({text,index,key:Math.random()})).sort((a,b)=>a.key-b.key).forEach(a=>{const b=document.createElement('button');b.className='answer';b.textContent=a.text;b.onclick=()=>this.answer(q,a.index,b);answers.appendChild(b)})},answer(q,index,button){if(this.locked)return;this.locked=true;const ok=QuestionEngine.validateAnswer(q,index),side=Math.random()>.5?'right':'left';ball.classList.add('shoot-'+side);if(ok){keeper.classList.add('dive-'+(side==='left'?'right':'left'));this.combo++;this.correct++;const gain=100+(this.combo*25);this.xp+=gain;this.coins+=10*this.combo;button.classList.add('correct');feedback.textContent='⚽ GOOOL! +'+gain+' XP · '+q.explanation;this.particles()}else{keeper.classList.add('dive-'+side);this.combo=0;this.lives--;button.classList.add('wrong');feedback.textContent='🧤 Defesa! '+q.explanation}QuestionEngine.saveResult({questionId:q.id,correct:ok,xp:this.xp,at:Date.now()});this.round++;this.sync();setTimeout(()=>this.next(),1600)},particles(){for(let i=0;i<32;i++){const p=document.createElement('i');p.className='particle';p.style.left='50%';p.style.top='40%';p.style.background=['#22d3ee','#a78bfa','#fbbf24','#34d399'][i%4];p.style.setProperty('--x',(Math.random()*420-210)+'px');p.style.setProperty('--y',(Math.random()*260-130)+'px');arena.appendChild(p);setTimeout(()=>p.remove(),1100)}},end(){play.classList.add('hidden');finish.classList.remove('hidden');const accuracy=Math.round(this.correct/questionBank.length*100);finishTitle.textContent=this.lives>0?'Campeonato concluído!':'Treino encerrado — tente de novo!';achievement.textContent=accuracy===100?'🌟 CONQUISTA: MESTRE INVICTO':accuracy>=60?'🥉 CONQUISTA: ARTILHEIRO DO SABER':'🎯 MISSÃO: TREINAR NOVAMENTE';finalXp.innerHTML=this.xp+'<small>XP total</small>';finalCoins.innerHTML=this.coins+'<small>moedas</small>';finalAccuracy.innerHTML=accuracy+'%<small>precisão</small>';QuestionEngine.saveResult({complete:true,xp:this.xp,coins:this.coins,accuracy})}};
</script></body></html>'''
    return template.replace("__TITLE__", safe_title).replace("__QUESTIONS__", questions_json)


def _build_flashcard_fallback_html(sb_slide: dict) -> str:
    """Build a deterministic, usable review activity from the slide context."""
    title = str(sb_slide.get("title") or "Revisão do conteúdo")
    module = str(sb_slide.get("moduleName") or "este módulo")
    source = _slide_plain_text(sb_slide)
    source = re.sub(r"\s+", " ", source).strip()
    sentences = []
    for candidate in re.split(r"(?<=[.!?;])\s+|\s+[\u2022\-]\s+", source):
        candidate = candidate.strip(" -\u2022")
        if 35 <= len(candidate) <= 360 and candidate.lower() not in {x.lower() for x in sentences}:
            sentences.append(candidate)
    summary = (sentences[0] if sentences else source[:320]) or f"O foco deste estudo é {title}."
    answers = sentences[:6]
    while len(answers) < 6:
        answers.append(summary)
    prompts = [
        f"Qual é o foco principal de {title}?",
        "Que ideia-chave deve ser lembrada?",
        "Como este conceito se relaciona ao contexto do curso?",
        "Qual aplicação prática pode ser reconhecida?",
        "Qual mensagem deve orientar a revisão?",
        "Que decisão ou prática demonstra domínio deste tema?",
    ]
    cards_json = json.dumps(
        [{"front": prompts[i], "back": answers[i], "category": ("Conceito", "Aplicação", "Decisão")[i % 3]} for i in range(6)],
        ensure_ascii=False,
    ).replace("</", "<\\/")
    safe_title = html.escape(title)
    safe_module = html.escape(module)
    template = r'''<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}body{margin:0;min-height:540px;font-family:Inter,Arial,sans-serif;color:#eaf2ff;background:linear-gradient(135deg,#071329,#13254b);display:grid;place-items:center}
.app{width:880px;padding:28px}.eyebrow{color:#67e8f9;font-size:13px;font-weight:800;text-transform:uppercase;letter-spacing:.12em}.title{font-size:28px;margin:8px 0 20px}.stage{perspective:1200px}.card{height:285px;position:relative;transform-style:preserve-3d;transition:transform .55s cubic-bezier(.2,.7,.2,1);cursor:pointer}.card.flipped{transform:rotateY(180deg)}
.face{position:absolute;inset:0;backface-visibility:hidden;border:1px solid rgba(125,211,252,.38);border-radius:24px;padding:42px;display:grid;place-items:center;text-align:center;font-size:25px;line-height:1.4;background:linear-gradient(145deg,#172d57,#0d1c38);box-shadow:0 24px 60px rgba(0,0,0,.3)}.face:before{content:attr(data-category);position:absolute;left:22px;top:18px;padding:6px 10px;border-radius:99px;background:#ffffff18;color:#a5f3fc;font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.back{transform:rotateY(180deg);background:linear-gradient(145deg,#174e63,#12334d)}
.hint{font-size:12px;color:#9fb6d8;margin-top:12px}.controls{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:18px}.buttons{display:flex;gap:9px}button{border:0;border-radius:11px;padding:11px 16px;font-weight:800;cursor:pointer;color:white;background:#2563eb}button.secondary{background:#334155}button.know{background:#059669}button.unknown{background:#dc2626}.progress{font-size:14px;color:#cbd5e1;font-weight:700}.result{display:none;text-align:center;padding:50px 20px;border-radius:22px;background:#122441}.result h2{font-size:34px;margin:0 0 12px}
</style></head><body><main class="app"><div class="eyebrow">__MODULE__</div><h1 class="title">__TITLE__</h1>
<section id="study"><div class="stage"><div id="card" class="card" role="button" tabindex="0" aria-label="Virar cartão"><div id="front" class="face"></div><div id="back" class="face back"></div></div></div><div class="hint">Clique no cartão para ver a resposta.</div>
<div class="controls"><button class="secondary" onclick="move(-1)">← Anterior</button><span id="progress" class="progress"></span><div class="buttons"><button class="unknown" onclick="mark(false)">Não sei</button><button class="know" onclick="mark(true)">Sei</button></div><button class="secondary" onclick="move(1)">Próximo →</button></div></section>
<section id="result" class="result"><h2 id="score"></h2><p>Você concluiu a revisão. Retome os cartões que ainda precisam de reforço.</p><div class="buttons" style="justify-content:center"><button id="review" class="unknown" onclick="reviewMissed()">Revisar não dominados</button><button onclick="restart(true)">Embaralhar e reiniciar</button></div></section></main>
<script>let cards=__CARDS__;let index=0,known=0,answered=new Set(),missed=new Set();const card=document.getElementById('card');
function render(){card.classList.remove('flipped');front.textContent=cards[index].front;back.textContent=cards[index].back;front.dataset.category=back.dataset.category=cards[index].category||'Revisão';progress.textContent=`Cartão ${index+1} de ${cards.length} · Domínio ${Math.round(known/Math.max(1,answered.size)*100)}%`}
function move(step){index=(index+step+cards.length)%cards.length;render()}function mark(ok){if(!answered.has(index)){answered.add(index);if(ok)known++;else missed.add(index)}if(answered.size===cards.length){study.style.display='none';result.style.display='block';score.textContent=`Resultado: ${Math.round(known/cards.length*100)}%`;review.style.display=missed.size?'inline-block':'none'}else{move(1)}}
function reviewMissed(){cards=cards.filter((_,i)=>missed.has(i));restart(false)}function restart(shuffle=false){if(shuffle)cards.sort(()=>Math.random()-.5);index=0;known=0;answered=new Set();missed=new Set();result.style.display='none';study.style.display='block';render()}card.onclick=()=>card.classList.toggle('flipped');card.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();card.classList.toggle('flipped')}};render();</script></body></html>'''
    return template.replace("__MODULE__", safe_module).replace("__TITLE__", safe_title).replace("__CARDS__", cards_json)


def _fallback_content_parts(sb_slide: dict, minimum: int = 5) -> list[str]:
    """Extract useful visible content even when the model returned bad HTML."""
    source = re.sub(r"\s+", " ", _slide_plain_text(sb_slide)).strip()
    parts = []
    for candidate in re.split(r"(?<=[.!?;:])\s+|\s+[\u2022\-]\s+", source):
        candidate = candidate.strip(" -\u2022")
        if 24 <= len(candidate) <= 360 and candidate.lower() not in {p.lower() for p in parts}:
            parts.append(candidate)
    title = str(sb_slide.get("title") or "Conteúdo do curso")
    defaults = [
        f"Contextualização de {title}",
        f"Conceitos essenciais relacionados a {title}",
        "Aplicação prática no contexto profissional",
        "Resultados, aprendizados e pontos de atenção",
        "Síntese e próximos passos recomendados",
    ]
    for item in defaults:
        if len(parts) >= minimum:
            break
        parts.append(item)
    return parts[:max(minimum, 7)]


def _build_timeline_fallback_html(sb_slide: dict) -> str:
    title = html.escape(str(sb_slide.get("title") or "Linha do tempo"))
    items = _fallback_content_parts(sb_slide, 5)[:6]
    events = json.dumps(
        [{"label": f"Etapa {i + 1}", "text": value} for i, value in enumerate(items)],
        ensure_ascii=False,
    ).replace("</", "<\\/")
    return r'''<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>*{box-sizing:border-box}body{margin:0;min-height:540px;font-family:Inter,Arial,sans-serif;background:linear-gradient(135deg,#f8fafc,#e0ecff);color:#10213f;display:grid;place-items:center}.app{width:900px;padding:34px}.eyebrow{font-size:12px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:#2563eb}.title{font-size:30px;margin:7px 0 30px}.track{height:5px;background:#bfdbfe;position:relative;margin:64px 36px 46px}.nodes{position:absolute;inset:0;display:flex;justify-content:space-between;align-items:center}.node{width:54px;height:54px;border-radius:50%;border:5px solid white;background:#2563eb;color:white;font-size:17px;font-weight:900;box-shadow:0 8px 25px #1d4ed844;cursor:pointer;transition:.25s}.node.active{background:#f97316;transform:scale(1.18)}.labels{display:flex;justify-content:space-between;margin:0 12px}.labels span{width:110px;text-align:center;font-size:12px;font-weight:800;color:#475569}.card{min-height:150px;border-radius:20px;background:white;padding:26px 30px;box-shadow:0 18px 45px #1e3a5f1f;border:1px solid #dbeafe}.card h2{font-size:21px;margin:0 0 10px;color:#1d4ed8}.card p{font-size:17px;line-height:1.55;margin:0}.hint{text-align:center;margin-top:14px;font-size:12px;color:#64748b}</style></head><body><main class="app"><div class="eyebrow">Cronologia interativa</div><h1 class="title">__TITLE__</h1><div class="track"><div id="nodes" class="nodes"></div></div><div id="labels" class="labels"></div><section class="card"><h2 id="eventTitle"></h2><p id="eventText"></p></section><div class="hint">Selecione os marcos para explorar cada etapa.</div></main><script>const events=__EVENTS__;const nodes=document.getElementById('nodes'),labels=document.getElementById('labels');function show(i){document.querySelectorAll('.node').forEach((n,x)=>n.classList.toggle('active',x===i));eventTitle.textContent=events[i].label;eventText.textContent=events[i].text}events.forEach((e,i)=>{const b=document.createElement('button');b.className='node';b.textContent=i+1;b.onclick=()=>show(i);nodes.appendChild(b);const l=document.createElement('span');l.textContent=e.label;labels.appendChild(l)});show(0);</script></body></html>'''.replace("__TITLE__", title).replace("__EVENTS__", events)


def _build_infographic_fallback_html(sb_slide: dict) -> str:
    """Build a contextual interactive infographic instead of a blank iframe."""
    title = html.escape(str(sb_slide.get("title") or "Infográfico do módulo"))
    parts = _fallback_content_parts(sb_slide, 5)[:5]
    colors = ["#2563eb", "#7c3aed", "#0891b2", "#059669", "#ea580c"]
    items = json.dumps([
        {
            "number": f"0{i + 1}",
            "title": (value[:58] + "…") if len(value) > 58 else value,
            "text": value,
            "value": 58 + i * 8,
            "color": colors[i],
        }
        for i, value in enumerate(parts)
    ], ensure_ascii=False).replace("</", "<\\/")
    return r'''<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>*{box-sizing:border-box}body{margin:0;min-height:540px;font-family:Inter,Arial,sans-serif;background:radial-gradient(circle at 12% 10%,#dbeafe 0,transparent 32%),#f8fafc;color:#172033;display:grid;place-items:center}.app{width:920px;padding:27px}.eyebrow{font-size:12px;font-weight:900;letter-spacing:.14em;text-transform:uppercase;color:#2563eb}.title{font-size:29px;margin:6px 0 20px}.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:11px}.item{min-height:210px;border:1px solid #dbe3ef;border-top:6px solid var(--c);border-radius:17px;background:#fff;padding:17px 14px;text-align:left;cursor:pointer;box-shadow:0 12px 28px #0f172a12;transition:.22s}.item:hover,.item.active{transform:translateY(-7px);box-shadow:0 18px 36px #0f172a24}.num{font-size:29px;font-weight:900;color:var(--c)}.item h2{font-size:14px;line-height:1.3;margin:9px 0;color:#24324a}.bar{height:7px;border-radius:9px;background:#e2e8f0;overflow:hidden;margin-top:15px}.fill{height:100%;width:var(--v);background:var(--c);border-radius:9px}.detail{margin-top:15px;min-height:92px;border-radius:16px;padding:18px 21px;background:#172033;color:#fff;display:grid;grid-template-columns:auto 1fr;gap:17px;align-items:center}.detail strong{font-size:28px;color:#93c5fd}.detail p{font-size:16px;line-height:1.45;margin:0}.hint{text-align:center;font-size:12px;color:#64748b;margin-top:10px}@media(max-width:720px){.app{width:100%;padding:14px}.grid{grid-template-columns:1fr 1fr}.item{min-height:150px}.detail{grid-template-columns:1fr}}</style></head><body><main class="app"><div class="eyebrow">Síntese visual interativa</div><h1 class="title">__TITLE__</h1><section id="grid" class="grid"></section><section class="detail"><strong id="detailNum"></strong><p id="detailText"></p></section><div class="hint">Selecione os blocos para explorar cada conceito.</div></main><script>const items=__ITEMS__,grid=document.getElementById('grid');function show(i){document.querySelectorAll('.item').forEach((x,n)=>x.classList.toggle('active',n===i));detailNum.textContent=items[i].number;detailText.textContent=items[i].text}items.forEach((x,i)=>{const b=document.createElement('button');b.className='item';b.style.setProperty('--c',x.color);b.style.setProperty('--v',x.value+'%');b.innerHTML='<div class="num">'+x.number+'</div><h2></h2><div class="bar"><div class="fill"></div></div>';b.querySelector('h2').textContent=x.title;b.onclick=()=>show(i);grid.appendChild(b)});show(0);</script></body></html>'''.replace("__TITLE__", title).replace("__ITEMS__", items)


def _build_case_study_fallback_html(sb_slide: dict) -> str:
    title = html.escape(str(sb_slide.get("title") or "Estudo de caso"))
    parts = _fallback_content_parts(sb_slide, 5)
    sections = json.dumps([
        {"title": "Contexto", "text": parts[0]},
        {"title": "Desafio", "text": parts[1]},
        {"title": "Decisão", "text": parts[2]},
        {"title": "Resultados", "text": parts[3]},
        {"title": "Reflexão", "text": parts[4]},
    ], ensure_ascii=False).replace("</", "<\\/")
    return r'''<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>*{box-sizing:border-box}body{margin:0;min-height:540px;font-family:Inter,Arial,sans-serif;background:linear-gradient(145deg,#fff7ed,#ffedd5);color:#292524;display:grid;place-items:center}.app{width:900px;padding:32px}.eyebrow{font-size:12px;font-weight:900;letter-spacing:.14em;text-transform:uppercase;color:#ea580c}.title{font-size:30px;margin:7px 0 22px}.layout{display:grid;grid-template-columns:220px 1fr;gap:20px}.tabs{display:flex;flex-direction:column;gap:9px}.tab{border:1px solid #fed7aa;background:#fff;border-radius:12px;padding:14px 16px;text-align:left;font-weight:800;color:#7c2d12;cursor:pointer}.tab.active{background:#ea580c;color:#fff;border-color:#ea580c}.panel{min-height:285px;background:white;border:1px solid #fed7aa;border-radius:20px;padding:30px;box-shadow:0 18px 45px #9a34121c}.panel h2{font-size:24px;color:#c2410c;margin:0 0 14px}.panel p{font-size:18px;line-height:1.62;margin:0}.question{margin-top:20px;padding:15px 18px;border-radius:12px;background:#fff7ed;color:#9a3412;font-weight:700}</style></head><body><main class="app"><div class="eyebrow">Análise aplicada</div><h1 class="title">__TITLE__</h1><div class="layout"><nav id="tabs" class="tabs"></nav><section class="panel"><h2 id="sectionTitle"></h2><p id="sectionText"></p><div class="question">Que decisão você tomaria nesta etapa e por quê?</div></section></div></main><script>const sections=__SECTIONS__,tabs=document.getElementById('tabs');function show(i){document.querySelectorAll('.tab').forEach((b,x)=>b.classList.toggle('active',x===i));sectionTitle.textContent=sections[i].title;sectionText.textContent=sections[i].text}sections.forEach((s,i)=>{const b=document.createElement('button');b.className='tab';b.textContent=`${i+1}. ${s.title}`;b.onclick=()=>show(i);tabs.appendChild(b)});show(0);</script></body></html>'''.replace("__TITLE__", title).replace("__SECTIONS__", sections)


def _normalize_interactive_storyboard_slide(slide: dict) -> dict:
    """Guarantee a visible, functional HTML element for interactive types.

    Some provider responses use the legacy ``content`` field and some return
    an empty element array while still labelling the slide as interactive.
    Normalize the former and replace the latter with the safe deterministic
    activity so neither the storyboard nor the generated course is blank.
    """
    stype = str((slide or {}).get("type") or "")
    builders = {
        "simulator": _build_simulator_fallback_html,
        "game": _build_game_fallback_html,
        "infographic": _build_infographic_fallback_html,
        "flashcard": _build_flashcard_fallback_html,
        "timeline": _build_timeline_fallback_html,
        "case_study": _build_case_study_fallback_html,
    }
    if stype not in builders:
        return slide

    html_content = _simulator_html_from_slide(slide)
    if not html_content:
        for element in slide.get("elements", []) or []:
            legacy = element.get("content") or ""
            if re.search(r"<(?:!doctype|html|script)\b", legacy, re.IGNORECASE):
                html_content = legacy
                break
    if not _interactive_html_is_functional(html_content, stype):
        html_content = builders[stype](slide)

    slide["elements"] = [{"type": "html", "htmlContent": html_content}]
    return slide


def _visible_words(html_content: str) -> list[str]:
    """Extract visible words while ignoring CSS/JS and HTML declarations."""
    clean = re.sub(r"<(?:style|script)[^>]*>[\s\S]*?</(?:style|script)>", " ", html_content or "", flags=re.I)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = re.sub(r"&(?:nbsp|amp|lt|gt|quot);", " ", clean, flags=re.I)
    return re.findall(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9'’–-]*", clean)


def _build_visual_content_fallback_html(slide: dict) -> str:
    """Create a concise visual composition instead of a text-heavy handout."""
    import html as html_module
    title = html_module.escape(str(slide.get("title") or "Conceito essencial"))
    purpose = str(slide.get("purpose") or slide.get("notes") or "").strip()
    sentences = [part.strip(" •-\n\t") for part in re.split(r"(?<=[.!?])\s+|\n+", purpose) if part.strip()]
    defaults = [
        f"Compreenda a ideia central de {title}",
        "Conecte o conceito a uma situação real",
        "Escolha uma ação prática para aplicar agora",
    ]
    points = (sentences + defaults)[:3]
    cards = "".join(
        f'<article class="visual-card"><span>{index:02d}</span><p>{html_module.escape(text[:170])}</p></article>'
        for index, text in enumerate(points, start=1)
    )
    return f'''<section class="premium-concept" data-visual-pattern="insight-cards">
<style>.premium-concept{{font-family:Inter,Arial,sans-serif;color:#172033}}.premium-concept h2{{font-size:38px;line-height:1.08;margin:0 0 26px;max-width:880px}}.visual-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}}.visual-card{{min-height:190px;padding:25px;border-radius:22px;background:linear-gradient(145deg,#fff,#eef4ff);border:1px solid #dbe7ff;box-shadow:0 16px 35px #1e3a5f16}}.visual-card span{{display:grid;place-items:center;width:42px;height:42px;border-radius:14px;background:#2563eb;color:#fff;font-weight:900;box-shadow:0 8px 22px #2563eb55}}.visual-card p{{font-size:19px;line-height:1.45;margin:22px 0 0}}</style>
<h2>{title}</h2><div class="visual-grid">{cards}</div></section>'''


def _normalize_visual_content_slide(slide: dict) -> dict:
    """Reject blank or handout-like content slides before persistence."""
    if str((slide or {}).get("type") or "") != "content":
        return slide
    elements = slide.get("elements", []) or []
    text_elements = [element for element in elements if element.get("type") in ("text", "html")]
    visible_count = sum(
        len(_visible_words(element.get("content") or element.get("htmlContent") or ""))
        for element in text_elements
    )
    if not text_elements or visible_count < 12 or visible_count > 85:
        slide["elements"] = [{
            "type": "text",
            "content": _build_visual_content_fallback_html(slide),
            "position": "left",
            "width": 1100,
            "height": 620,
        }]
        slide["qualityAdjusted"] = "visual-density"
    slide["contentBudgetWords"] = 70
    return slide


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
                ai_image_tasks.append((i, kw, "contextual_ai"))
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
        progress_lock = asyncio.Lock()
        image_task_timeout = max(
            30.0, float(os.environ.get("AI_IMAGE_TASK_TIMEOUT_SECONDS", "150"))
        )
        completed_count = 0

        async def _mark_image_complete(slide_idx, outcome):
            """Advance progress for success, fallback and timeout alike."""
            nonlocal completed_count
            async with progress_lock:
                completed_count += 1
                current = completed_count
            logger.info(
                "Image task %s/%s finished for slide %s (%s)",
                current, total_images, slide_idx, outcome,
            )
            if _pdb is not None:
                try:
                    await _pdb.agent_sessions.update_one(
                        {"id": session_id},
                        {"$set": {
                            "courseProgress": {
                                "message": f"Gerando imagens IA: {current}/{total_images}..."
                            },
                            "updatedAt": datetime.now(timezone.utc).isoformat(),
                        }},
                    )
                except Exception as progress_err:
                    logger.warning(
                        "Could not persist image progress for slide %s: %s",
                        slide_idx, str(progress_err)[:160],
                    )
        
        async def _generate_one_image(slide_idx, keyword, source="gemini"):
            async with semaphore:
                outcome = "unavailable"
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
                                outcome = "brand_library"
                                return
                            # No match: in strict mode (or per-slide "force"),
                            # we leave the slide without an image. "force"
                            # opted in explicitly so a missing match means
                            # "leave it" rather than fall through to AI.
                            if brand_library_mode == "strict" or _override == "force":
                                slide_media[slide_idx] = {"type": "none", "source": "brand_library_strict"}
                                outcome = "brand_library_strict"
                                return
                        except Exception as _ble:
                            logger.warning(f"brand library picker failed for slide {slide_idx}: {_ble}")
                            # Falls through to the regular generation paths below

                    if source == "leonardo":
                        from services.leonardo_ai import generate_and_wait, download_image_to_disk
                        from services.asset_store import store_asset_async
                        import uuid as _uuid
                        leo_urls = await asyncio.wait_for(
                            generate_and_wait(prompt=keyword, width=1024, height=576, num_images=1),
                            timeout=image_task_timeout,
                        )
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
                        img_url = await asyncio.wait_for(
                            _fetch_stock_image(
                                keyword, project_dir, project_id, slide_context=sb_slide_ctx
                            ),
                            timeout=image_task_timeout,
                        )
                    if img_url:
                        slide_media[slide_idx] = {"type": "image", "url": img_url}
                        outcome = source
                    else:
                        # Do not replace a failed contextual generation with a
                        # random stock photo. A full-width text layout keeps
                        # the course semantically correct and readable.
                        slide_media[slide_idx] = {"type": "none", "source": "ai_unavailable"}
                except asyncio.TimeoutError:
                    outcome = "timeout"
                    slide_media[slide_idx] = {"type": "none", "source": "ai_timeout"}
                    logger.warning(
                        "Image generation timed out after %.0fs for slide %s",
                        image_task_timeout, slide_idx,
                    )
                except Exception as e:
                    outcome = "error"
                    slide_media[slide_idx] = {"type": "none", "source": "ai_error"}
                    logger.warning(f"Image generation failed for slide {slide_idx}: {str(e)[:80]}")
                finally:
                    await _mark_image_complete(slide_idx, outcome)
        
        # Run all image tasks concurrently (semaphore limits concurrency to 5)
        await asyncio.gather(
            *[_generate_one_image(idx, kw, src) for idx, kw, src in ai_image_tasks],
            return_exceptions=True,
        )

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
        elif stype in ("simulator", "game"):
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
            # Games consume the company's central question bank through a
            # snapshot embedded in the course. This keeps SCORM/HTML fully
            # functional offline while the source remains replaceable via the
            # QuestionEngine administration API.
            if stype == "game" and company_id:
                try:
                    game_db = await _get_motor_db()
                    if game_db is not None:
                        bank_questions = await game_db.game_questions.aggregate([
                            {"$match": {"companyId": company_id, "active": {"$ne": False}}},
                            {"$sample": {"size": 8}},
                            {"$project": {"_id": 0}},
                        ]).to_list(8)
                        if bank_questions:
                            html_content = _build_game_fallback_html(sb_slide, bank_questions)
                            logger.info("Embedded %s company-bank questions in game slide %s", len(bank_questions), i)
                except Exception as exc:
                    logger.warning("Could not sample game question bank for slide %s: %s", i, exc)
            if _interactive_html_is_functional(html_content, "simulator"):
                slide_elements = [{
                    "id": generate_id(),
                    "type": "html",
                    "htmlContent": _wrap_interactive_fullbleed(html_content),
                    "x": 0,
                    "y": 0,
                    "width": 1920,
                    "height": 820,
                    "htmlDisplayMode": "fit",
                    "zIndex": 1,
                }]
            else:
                if html_content:
                    logger.warning("Rejected non-functional simulator HTML on slide %s", i)
                # Never turn a failed simulator into a blank text slide. Use a
                # deterministic, fully interactive activity instead.
                fallback_html = (
                    _build_game_fallback_html(sb_slide)
                    if stype == "game"
                    else _build_simulator_fallback_html(sb_slide)
                )
                slide_elements = [{
                    "id": generate_id(),
                    "type": "html",
                    "htmlContent": _wrap_interactive_fullbleed(fallback_html),
                    "x": 0,
                    "y": 0,
                    "width": 1920,
                    "height": 820,
                    "htmlDisplayMode": "fit",
                    "zIndex": 1,
                }]
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
            if stype == "flashcard" and not _interactive_html_is_functional(html_content, stype):
                if html_content:
                    logger.warning("Rejected placeholder flashcard HTML on slide %s; using safe fallback", i)
                html_content = _build_flashcard_fallback_html(sb_slide)
            elif stype == "infographic" and not _interactive_html_is_functional(html_content, stype):
                if html_content:
                    logger.warning("Rejected blank infographic HTML on slide %s; using safe fallback", i)
                html_content = _build_infographic_fallback_html(sb_slide)
            elif stype == "timeline" and not _interactive_html_is_functional(html_content, stype):
                if html_content:
                    logger.warning("Rejected blank timeline HTML on slide %s; using safe fallback", i)
                html_content = _build_timeline_fallback_html(sb_slide)
            elif stype == "case_study" and not _interactive_html_is_functional(html_content, stype):
                if html_content:
                    logger.warning("Rejected blank case-study HTML on slide %s; using safe fallback", i)
                html_content = _build_case_study_fallback_html(sb_slide)
            if _interactive_html_is_functional(html_content, stype):
                slide_elements = [{
                    "id": generate_id(),
                    "type": "html",
                    "htmlContent": _wrap_interactive_fullbleed(html_content),
                    "x": 0,
                    "y": 0,
                    "width": 1920,
                    "height": 820,
                    "htmlDisplayMode": "fit",
                    "zIndex": 1,
                }]
            else:
                if html_content:
                    logger.warning("Rejected non-functional %s HTML on slide %s", stype, i)
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
        {{"id": "s1", "title": "Slide", "type": "content|title|quiz|summary|game|simulator|scenario|infographic|flashcard|timeline|case_study", "purpose": "Objetivo", "estimatedDuration": 30}}
      ]
    }}
  ],
  "totalSlides": 10,
  "totalDuration": 30
}}
```

Siga a estrutura do template mas adapte ao conteúdo fornecido. Primeiro slide=capa, último=resumo, quizzes ao final de cada módulo.
Quando Jogos Educativos estiver habilitado, inclua pelo menos 1 slide type="game" por módulo; game é uma experiência gamificada completa com missão, HUD, XP, vidas, rodadas, vitória/derrota e conquista.
Quando Simuladores estiver habilitado, inclua pelo menos 1 slide type="simulator" por módulo; simulator é uma ferramenta de prática e tomada de decisão, não um quiz comum."""
    
    response = await chat.send_message(UserMessage(text=prompt))
    return _premiumize_course_structure(_extract_json(response) or {}, config)


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
