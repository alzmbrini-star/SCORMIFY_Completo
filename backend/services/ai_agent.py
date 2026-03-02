"""
AI Instructional Design Agent Service
Transforms raw content into complete Scormfy courses using GPT-5.2
"""
import os
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

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

def _new_chat(session_id: str) -> LlmChat:
    return LlmChat(
        api_key=EMERGENT_KEY,
        session_id=session_id,
        system_message=SYSTEM_PROMPT,
    ).with_model("openai", "gpt-5.2")


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


async def analyze_content(session_id: str, content_text: str, file_info: str = "") -> dict:
    """Step 1: Analyze uploaded content and extract key information."""
    chat = _new_chat(f"agent-analyze-{session_id}")
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

    response = await chat.send_message(UserMessage(text=prompt))
    data = _extract_json(response)
    if not data:
        data = {
            "title": "Curso sem título",
            "summary": response[:200],
            "mainTopics": [],
            "targetAudience": "Público geral",
            "difficulty": "intermediario",
            "estimatedDuration": 30,
            "suggestedModules": 3,
            "gaps": [],
            "strengths": [],
            "keywords": [],
        }
    return data


async def generate_structure(session_id: str, content_text: str, config: dict) -> dict:
    """Step 2: Generate course architecture based on content and configuration."""
    chat = _new_chat(f"agent-structure-{session_id}")
    prompt = f"""Crie a estrutura pedagógica completa para um curso digital baseado no conteúdo e configuração abaixo.

CONFIGURAÇÃO:
- Título: {config.get('title', 'Curso')}
- Nível: {config.get('depth', 'intermediario')}
- Duração alvo: {config.get('duration', 30)} minutos
- Módulos: {config.get('modules', 3)}
- Interatividade: {config.get('interactivity', 'media')}
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
          "type": "content|title|quiz|summary",
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

REGRAS:
- Primeiro slide deve ser uma capa/título do curso
- Cada módulo deve ter 2-5 slides de conteúdo
- Inclua slides de quiz ao final de cada módulo
- Último slide deve ser um resumo/conclusão
- Aplique progressão de complexidade
- Use microlearning: máximo 3 conceitos por slide"""

    response = await chat.send_message(UserMessage(text=prompt))
    data = _extract_json(response)
    if not data:
        raise ValueError("Não foi possível gerar a estrutura do curso")
    return data


async def generate_storyboard(session_id: str, content_text: str, structure: dict, config: dict) -> dict:
    """Step 3: Generate detailed storyboard - processes slides in batches to avoid timeouts."""
    all_slides = []

    # Flatten all slides from structure
    flat_slides = []
    for mod in structure.get("modules", []):
        for sl in mod.get("slides", []):
            flat_slides.append({**sl, "moduleName": mod.get("title", "")})

    # Process in batches of 6 slides for speed
    batch_size = 6
    for batch_start in range(0, len(flat_slides), batch_size):
        batch = flat_slides[batch_start:batch_start + batch_size]
        batch_info = [{"id": s.get("id",""), "title": s.get("title",""), "type": s.get("type","content"), "purpose": s.get("purpose",""), "moduleName": s.get("moduleName","")} for s in batch]

        chat = _new_chat(f"agent-sb-{session_id}-{batch_start}")
        prompt = f"""Gere conteúdo DETALHADO e RICO para {len(batch)} slides do curso "{config.get('title', '')}".
Nível: {config.get('depth', 'intermediario')}
Conteúdo-base: {content_text[:3000]}

Slides: {json.dumps(batch_info, ensure_ascii=False)}

Retorne JSON:
```json
{{"slides":[{{
  "id":"id",
  "title":"Título do Slide",
  "type":"content",
  "moduleName":"Nome do Módulo",
  "imageKeywords":"english keywords for stock photo search",
  "elements":[
    {{"type":"text","content":"<h2>Título</h2><p>Conteúdo detalhado com <strong>destaques</strong> e explicações claras. Use listas com <ul><li>item</li></ul> quando apropriado.</p>","position":"left","width":1000,"height":550}}
  ],
  "narrationScript":"Texto completo da narração para este slide",
  "librasScript":"Texto simplificado para LIBRAS",
  "notes":"Notas do instrutor",
  "quizQuestions":[]
}}]}}
```
REGRAS IMPORTANTES:
- Slides de CONTEÚDO: texto detalhado com pelo menos 50 palavras, use HTML rico (<h2>, <h3>, <p>, <ul>, <li>, <strong>, <em>)
- Slides de TÍTULO: use <h1> para título principal e <p> para subtítulo/descrição
- Slides de QUIZ: inclua 2-3 perguntas com 4 alternativas cada (uma isCorrect:true), inclua "explanation" em cada pergunta
- Slides de SUMMARY: resuma os pontos-chave do módulo com <ul><li>
- imageKeywords: 2-3 palavras em INGLÊS que descrevem uma imagem adequada (ex: "teamwork office", "data analysis chart", "safety equipment")
- moduleName: inclua o nome do módulo para cada slide
- TODOS os slides devem ter conteúdo substantivo, nunca deixe elementos vazios"""

        try:
            response = await chat.send_message(UserMessage(text=prompt))
            data = _extract_json(response)
            if data and "slides" in data:
                # Ensure moduleName propagation from batch
                for j, slide_data in enumerate(data["slides"]):
                    if not slide_data.get("moduleName") and j < len(batch):
                        slide_data["moduleName"] = batch[j].get("moduleName", "")
                all_slides.extend(data["slides"])
                continue
        except Exception as e:
            logger.warning(f"Storyboard batch {batch_start} error: {e}")

        # Fallback: create basic slides from structure
        for sl in batch:
            all_slides.append({
                "id": sl.get("id", ""),
                "title": sl.get("title", "Slide"),
                "type": sl.get("type", "content"),
                "moduleName": sl.get("moduleName", ""),
                "imageKeywords": sl.get("title", "education").replace(" ", " "),
                "elements": [{"type": "text", "content": f"<h2>{sl.get('title','')}</h2><p>{sl.get('purpose','')}</p>", "position": "left", "width": 1000, "height": 550}],
                "narrationScript": sl.get("purpose", ""),
                "librasScript": sl.get("purpose", ""),
                "notes": "",
                "quizQuestions": [],
            })

    return {"slides": all_slides}


# ========== VISUAL COURSE GENERATION ==========

# Professional color palettes for course themes
_COURSE_PALETTES = [
    {"primary": "#0f172a", "accent": "#10b981", "accentLight": "#d1fae5", "contentBg": "#f0fdf4", "text": "#1e293b"},
    {"primary": "#1e1b4b", "accent": "#8b5cf6", "accentLight": "#ede9fe", "contentBg": "#f5f3ff", "text": "#1e293b"},
    {"primary": "#172554", "accent": "#3b82f6", "accentLight": "#dbeafe", "contentBg": "#eff6ff", "text": "#1e293b"},
    {"primary": "#14532d", "accent": "#22c55e", "accentLight": "#dcfce7", "contentBg": "#f0fdf4", "text": "#1e293b"},
    {"primary": "#7f1d1d", "accent": "#ef4444", "accentLight": "#fee2e2", "contentBg": "#fef2f2", "text": "#1e293b"},
    {"primary": "#78350f", "accent": "#f59e0b", "accentLight": "#fef3c7", "contentBg": "#fffbeb", "text": "#1e293b"},
]


async def _fetch_stock_image(keyword: str, project_dir: str, project_id: str) -> Optional[str]:
    """Download a stock image from picsum.photos and save locally."""
    import httpx
    import hashlib
    try:
        seed = hashlib.md5(keyword.encode()).hexdigest()[:10]
        url = f"https://picsum.photos/seed/{seed}/800/450"
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                import os
                fname = f"stock_{seed}.jpg"
                fpath = os.path.join(project_dir, project_id, "assets", fname)
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, "wb") as f:
                    f.write(resp.content)
                return f"/api/projects/{project_id}/assets/{fname}"
    except Exception as e:
        logger.warning(f"Stock image fetch failed for '{keyword}': {e}")
    return None


def _build_title_slide(sb_slide: dict, palette: dict, course_title: str, module_names: list) -> dict:
    """Build a visually rich title/cover slide."""
    from models import generate_id
    accent = palette["accent"]
    elements = []

    # Accent bar at top
    elements.append({
        "id": generate_id(), "type": "html", "x": 0, "y": 0, "width": 1920, "height": 8,
        "htmlContent": f'<div style="width:100%;height:100%;background:{accent};"></div>',
        "style": {}, "startTime": 0, "animations": [],
    })

    # Title text - large and centered
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

    title_html = f'''<div style="text-align:center;padding:20px;">
<h1 style="font-size:48px;font-weight:800;color:#ffffff;margin:0 0 20px 0;line-height:1.2;">{title_text}</h1>
{f'<p style="font-size:20px;color:rgba(255,255,255,0.75);margin:0 0 30px 0;max-width:900px;margin-left:auto;margin-right:auto;line-height:1.5;">{subtitle}</p>' if subtitle else ''}
<div style="width:80px;height:4px;background:{accent};margin:0 auto 30px auto;border-radius:2px;"></div>
</div>'''
    elements.append({
        "id": generate_id(), "type": "html", "x": 160, "y": 120, "width": 1600, "height": 400,
        "htmlContent": title_html,
        "style": {"fontFamily": "Inter, sans-serif"}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.6, "delay": 0}],
    })

    # Module list
    if module_names:
        modules_html = '<div style="text-align:center;"><p style="font-size:14px;color:rgba(255,255,255,0.5);margin-bottom:12px;text-transform:uppercase;letter-spacing:2px;">Trilha do Curso</p>'
        for idx, mn in enumerate(module_names):
            modules_html += f'<span style="display:inline-block;padding:6px 16px;margin:4px;border-radius:20px;background:rgba(255,255,255,0.08);color:rgba(255,255,255,0.7);font-size:13px;border:1px solid rgba(255,255,255,0.1);">{idx+1}. {mn}</span>'
        modules_html += '</div>'
        elements.append({
            "id": generate_id(), "type": "html", "x": 160, "y": 540, "width": 1600, "height": 200,
            "htmlContent": modules_html,
            "style": {"fontFamily": "Inter, sans-serif"}, "startTime": 0,
            "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.4}],
        })

    return elements


def _build_content_slide(sb_slide: dict, palette: dict, module_name: str, image_url: Optional[str]) -> dict:
    """Build a visually rich content slide with header bar, text, and image."""
    from models import generate_id
    accent = palette["accent"]
    content_bg = palette["contentBg"]
    elements = []

    # Header bar with module name
    header_html = f'''<div style="width:100%;height:100%;background:{accent};display:flex;align-items:center;padding:0 30px;">
<span style="color:#ffffff;font-size:13px;font-weight:600;letter-spacing:1px;text-transform:uppercase;">{module_name}</span>
<span style="color:rgba(255,255,255,0.6);font-size:12px;margin-left:auto;">{sb_slide.get("title","")}</span>
</div>'''
    elements.append({
        "id": generate_id(), "type": "html", "x": 0, "y": 0, "width": 1920, "height": 50,
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
        # Text on the left (55% width)
        styled_text = _style_content_html(text_content, palette["text"])
        elements.append({
            "id": generate_id(), "type": "html", "x": 60, "y": 80, "width": 1050, "height": 700,
            "htmlContent": styled_text,
            "style": {"fontFamily": "Inter, sans-serif"}, "startTime": 0,
            "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
        })
        # Image on the right
        elements.append({
            "id": generate_id(), "type": "image", "x": 1160, "y": 90, "width": 700, "height": 440,
            "src": image_url, "content": image_url,
            "style": {"borderRadius": "12px"}, "startTime": 0,
            "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.3}],
        })
        # Accent bar under image
        elements.append({
            "id": generate_id(), "type": "html", "x": 1160, "y": 545, "width": 700, "height": 4,
            "htmlContent": f'<div style="width:100%;height:100%;background:{accent};border-radius:2px;"></div>',
            "style": {}, "startTime": 0, "animations": [],
        })
    else:
        # Full-width text layout
        styled_text = _style_content_html(text_content, palette["text"])
        elements.append({
            "id": generate_id(), "type": "html", "x": 80, "y": 80, "width": 1760, "height": 700,
            "htmlContent": styled_text,
            "style": {"fontFamily": "Inter, sans-serif"}, "startTime": 0,
            "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
        })

    return elements


def _build_quiz_slide(sb_slide: dict, palette: dict, module_name: str) -> dict:
    """Build a visually styled quiz slide."""
    from models import generate_id
    accent = palette["accent"]
    elements = []

    # Header
    header_html = f'''<div style="width:100%;height:100%;background:{accent};display:flex;align-items:center;padding:0 30px;">
<span style="color:#ffffff;font-size:13px;font-weight:600;letter-spacing:1px;">QUIZ - {module_name}</span>
</div>'''
    elements.append({
        "id": generate_id(), "type": "html", "x": 0, "y": 0, "width": 1920, "height": 50,
        "htmlContent": header_html,
        "style": {}, "startTime": 0, "animations": [],
    })

    # Quiz indicator
    quiz_html = f'''<div style="text-align:center;padding:30px;">
<div style="display:inline-block;padding:8px 24px;border-radius:24px;background:{accent}22;border:1px solid {accent}44;">
<span style="color:{accent};font-size:14px;font-weight:600;">Hora de Praticar!</span>
</div>
<h2 style="font-size:28px;font-weight:700;color:#ffffff;margin:20px 0 10px 0;">Teste seus Conhecimentos</h2>
<p style="font-size:16px;color:rgba(255,255,255,0.6);">Responda as perguntas abaixo para verificar seu aprendizado</p>
</div>'''
    elements.append({
        "id": generate_id(), "type": "html", "x": 160, "y": 80, "width": 1600, "height": 250,
        "htmlContent": quiz_html,
        "style": {"fontFamily": "Inter, sans-serif"}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
    })

    # Show quiz questions as preview
    questions = sb_slide.get("quizQuestions", [])
    if questions:
        q_html = '<div style="padding:10px;">'
        for qi, q in enumerate(questions):
            q_html += '<div style="background:rgba(255,255,255,0.05);border-radius:12px;padding:16px;margin-bottom:12px;border:1px solid rgba(255,255,255,0.1);">'
            q_html += f'<p style="color:#ffffff;font-size:15px;font-weight:600;margin:0 0 8px 0;">{qi+1}. {q.get("text","")}</p>'
            for a in q.get("alternatives", []):
                icon = "&#9679;" if not a.get("isCorrect") else "&#10003;"
                color = "rgba(255,255,255,0.5)" if not a.get("isCorrect") else "#10b981"
                q_html += f'<p style="color:{color};font-size:13px;margin:4px 0 4px 16px;">{icon} {a.get("text","")}</p>'
            q_html += '</div>'
        q_html += '</div>'
        elements.append({
            "id": generate_id(), "type": "html", "x": 260, "y": 340, "width": 1400, "height": 440,
            "htmlContent": q_html,
            "style": {"fontFamily": "Inter, sans-serif"}, "startTime": 0,
            "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.3}],
        })

    return elements


def _build_summary_slide(sb_slide: dict, palette: dict, module_name: str) -> dict:
    """Build a visually rich summary slide."""
    from models import generate_id
    accent = palette["accent"]
    elements = []

    # Header
    header_html = f'''<div style="width:100%;height:100%;background:{accent};display:flex;align-items:center;padding:0 30px;">
<span style="color:#ffffff;font-size:13px;font-weight:600;letter-spacing:1px;">RESUMO - {module_name}</span>
</div>'''
    elements.append({
        "id": generate_id(), "type": "html", "x": 0, "y": 0, "width": 1920, "height": 50,
        "htmlContent": header_html,
        "style": {}, "startTime": 0, "animations": [],
    })

    # Summary content
    text_content = ""
    for el in sb_slide.get("elements", []):
        c = el.get("content", "")
        if c:
            text_content = c

    styled_text = _style_summary_html(text_content, accent)
    elements.append({
        "id": generate_id(), "type": "html", "x": 160, "y": 80, "width": 1600, "height": 700,
        "htmlContent": styled_text,
        "style": {"fontFamily": "Inter, sans-serif"}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
    })

    return elements


def _style_content_html(raw_html: str, text_color: str) -> str:
    """Apply professional styling to content HTML."""
    import re
    styled = raw_html
    # Style headings
    styled = re.sub(r'<h1([^>]*)>', f'<h1\\1 style="font-size:36px;font-weight:800;color:{text_color};margin:0 0 16px 0;line-height:1.2;">', styled)
    styled = re.sub(r'<h2([^>]*)>', f'<h2\\1 style="font-size:28px;font-weight:700;color:{text_color};margin:0 0 14px 0;line-height:1.3;">', styled)
    styled = re.sub(r'<h3([^>]*)>', f'<h3\\1 style="font-size:22px;font-weight:600;color:{text_color};margin:0 0 10px 0;line-height:1.3;">', styled)
    # Style paragraphs
    styled = re.sub(r'<p([^>]*)>', f'<p\\1 style="font-size:17px;color:{text_color}cc;line-height:1.7;margin:0 0 12px 0;">', styled)
    # Style lists
    styled = re.sub(r'<ul([^>]*)>', '<ul\\1 style="padding-left:20px;margin:8px 0;">', styled)
    styled = re.sub(r'<li([^>]*)>', f'<li\\1 style="font-size:16px;color:{text_color}cc;line-height:1.6;margin-bottom:6px;">', styled)
    # Style bold
    styled = re.sub(r'<strong([^>]*)>', f'<strong\\1 style="color:{text_color};font-weight:700;">', styled)
    return f'<div style="padding:10px;">{styled}</div>'


def _style_summary_html(raw_html: str, accent: str) -> str:
    """Apply professional styling to summary HTML."""
    import re
    styled = raw_html
    styled = re.sub(r'<h1([^>]*)>', '<h1\\1 style="font-size:32px;font-weight:800;color:#ffffff;margin:0 0 20px 0;text-align:center;">', styled)
    styled = re.sub(r'<h2([^>]*)>', '<h2\\1 style="font-size:26px;font-weight:700;color:#ffffff;margin:20px 0 14px 0;text-align:center;">', styled)
    styled = re.sub(r'<p([^>]*)>', '<p\\1 style="font-size:17px;color:rgba(255,255,255,0.75);line-height:1.7;margin:0 0 12px 0;text-align:center;">', styled)
    styled = re.sub(r'<ul([^>]*)>', '<ul\\1 style="list-style:none;padding:0;margin:16px auto;max-width:800px;">', styled)
    styled = re.sub(r'<li([^>]*)>', f'<li\\1 style="font-size:16px;color:rgba(255,255,255,0.8);padding:10px 16px;margin-bottom:8px;background:rgba(255,255,255,0.05);border-radius:8px;border-left:3px solid {accent};">', styled)
    styled = re.sub(r'<strong([^>]*)>', '<strong\\1 style="color:#ffffff;">', styled)
    return f'<div style="padding:20px;">{styled}</div>'


async def generate_course_from_storyboard(session_id: str, storyboard: dict, config: dict, project_dir: str = "", project_id: str = "") -> dict:
    """Step 4: Convert storyboard into actual Scormfy project data with professional visuals."""
    from models import generate_id
    import hashlib

    slides_data = storyboard.get("slides", [])
    project_slides = []
    quiz_questions = []

    # Select a color palette based on course title
    title_hash = int(hashlib.md5(config.get("title", "curso").encode()).hexdigest()[:8], 16)
    palette = _COURSE_PALETTES[title_hash % len(_COURSE_PALETTES)]

    # Collect module names for title slide
    module_names = []
    seen_modules = set()
    for sb_slide in slides_data:
        mn = sb_slide.get("moduleName", "")
        if mn and mn not in seen_modules:
            module_names.append(mn)
            seen_modules.add(mn)

    # Pre-fetch stock images for content slides
    image_urls = {}
    for i, sb_slide in enumerate(slides_data):
        stype = sb_slide.get("type", "content")
        if stype in ("content",) and sb_slide.get("imageKeywords"):
            kw = sb_slide["imageKeywords"]
            if project_dir and project_id:
                img_url = await _fetch_stock_image(kw, project_dir, project_id)
                if img_url:
                    image_urls[i] = img_url

    for i, sb_slide in enumerate(slides_data):
        stype = sb_slide.get("type", "content")
        module_name = sb_slide.get("moduleName", "")

        # Determine background based on slide type
        if stype == "title":
            bg = palette["primary"]
            slide_elements = _build_title_slide(sb_slide, palette, config.get("title", ""), module_names)
        elif stype == "quiz":
            bg = palette["primary"]
            slide_elements = _build_quiz_slide(sb_slide, palette, module_name)
        elif stype == "summary":
            bg = palette["primary"]
            slide_elements = _build_summary_slide(sb_slide, palette, module_name)
        else:
            bg = palette["contentBg"]
            img_url = image_urls.get(i)
            slide_elements = _build_content_slide(sb_slide, palette, module_name, img_url)

        # Collect quiz questions
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
                "tags": [],
            })

        slide = {
            "id": generate_id(),
            "title": sb_slide.get("title", f"Slide {i+1}"),
            "order": i,
            "width": 1920,
            "height": 820,
            "background": bg,
            "elements": slide_elements,
            "annotations": [],
            "transition": {"type": "fade", "duration": 0.5},
            "audio": [],
            "notes": sb_slide.get("notes", ""),
            "librasScript": sb_slide.get("librasScript", ""),
            "duration": 5.0,
        }
        project_slides.append(slide)

    return {
        "slides": project_slides,
        "quizQuestions": quiz_questions,
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

Responda de forma útil e concisa. Se o usuário pedir mudanças na estrutura ou conteúdo, sugira as alterações específicas."""
    
    response = await chat.send_message(UserMessage(text=prompt))
    return response


# ========== COURSE EDITING ==========

async def analyze_existing_course(session_id: str, project: dict) -> dict:
    """Analyze an existing Scormfy course and suggest improvements."""
    chat = _new_chat(f"agent-edit-analyze-{session_id}")
    
    slides = project.get("course", {}).get("slides", [])
    slides_summary = []
    for i, s in enumerate(slides):
        texts = []
        for el in s.get("elements", []):
            c = el.get("htmlContent") or el.get("content") or ""
            if c:
                texts.append(c[:200])
        slides_summary.append({
            "index": i,
            "title": s.get("title", f"Slide {i+1}"),
            "hasAudio": bool(s.get("audio")),
            "hasNarration": bool(s.get("librasScript")),
            "elementCount": len(s.get("elements", [])),
            "textPreview": " | ".join(texts)[:300],
        })
    
    prompt = f"""Analise este curso existente e sugira melhorias.

CURSO: {project.get('name', 'Sem nome')}
DESCRIÇÃO: {project.get('description', '')}
TOTAL DE SLIDES: {len(slides)}

RESUMO DOS SLIDES:
{json.dumps(slides_summary, ensure_ascii=False)[:6000]}

Retorne JSON:
```json
{{
  "overallScore": 7,
  "strengths": ["ponto forte 1"],
  "improvements": [
    {{
      "slideIndex": 0,
      "type": "content|structure|quiz|narration|visual",
      "priority": "alta|media|baixa",
      "description": "descrição da melhoria",
      "suggestion": "sugestão concreta"
    }}
  ],
  "missingElements": ["elemento faltante"],
  "suggestedNewSlides": [
    {{
      "position": "after_slide_2",
      "title": "Título sugerido",
      "type": "content|quiz|summary",
      "reason": "motivo"
    }}
  ]
}}
```"""
    
    response = await chat.send_message(UserMessage(text=prompt))
    return _extract_json(response) or {"overallScore": 0, "strengths": [], "improvements": [], "missingElements": [], "suggestedNewSlides": []}


async def apply_course_improvements(session_id: str, project: dict, selected_improvements: list) -> dict:
    """Apply selected improvements to an existing course."""
    chat = _new_chat(f"agent-edit-apply-{session_id}")
    
    slides = project.get("course", {}).get("slides", [])
    
    # Group improvements by slide
    improvements_desc = json.dumps(selected_improvements, ensure_ascii=False)
    
    # Get current slide content for context
    slides_content = []
    for i, s in enumerate(slides):
        texts = []
        for el in s.get("elements", []):
            c = el.get("htmlContent") or el.get("content") or ""
            if c:
                texts.append(c[:300])
        slides_content.append({
            "index": i,
            "title": s.get("title", ""),
            "text": " ".join(texts)[:500],
        })
    
    prompt = f"""Aplique as seguintes melhorias ao curso. Gere o conteúdo atualizado para cada slide afetado.

CURSO: {project.get('name', '')}
SLIDES ATUAIS: {json.dumps(slides_content, ensure_ascii=False)[:4000]}

MELHORIAS SELECIONADAS:
{improvements_desc}

Retorne JSON com os slides a atualizar:
```json
{{
  "updatedSlides": [
    {{
      "slideIndex": 0,
      "title": "Novo título se mudou",
      "elements": [{{"type":"text","content":"<h2>Novo conteúdo</h2><p>Texto melhorado</p>","position":"center","width":800,"height":400}}],
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
      "elements": [{{"type":"text","content":"<h2>T</h2><p>conteúdo</p>","position":"center","width":800,"height":400}}],
      "narrationScript": "",
      "librasScript": "",
      "quizQuestions": []
    }}
  ]
}}
```"""
    
    response = await chat.send_message(UserMessage(text=prompt))
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
        {{"id": "s1", "title": "Slide", "type": "content|title|quiz|summary", "purpose": "Objetivo", "estimatedDuration": 30}}
      ]
    }}
  ],
  "totalSlides": 10,
  "totalDuration": 30
}}
```

Siga a estrutura do template mas adapte ao conteúdo fornecido. Primeiro slide=capa, último=resumo, quizzes ao final de cada módulo."""
    
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

