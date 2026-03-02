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
        batch_info = [{"id": s.get("id",""), "title": s.get("title",""), "type": s.get("type","content"), "purpose": s.get("purpose","")} for s in batch]
        
        chat = _new_chat(f"agent-sb-{session_id}-{batch_start}")
        prompt = f"""Gere conteúdo para {len(batch)} slides do curso "{config.get('title', '')}".
Nível: {config.get('depth', 'intermediario')}
Conteúdo-base: {content_text[:2000]}

Slides: {json.dumps(batch_info, ensure_ascii=False)}

Retorne JSON:
```json
{{"slides":[{{"id":"id","title":"T","type":"content","background":"#FFFFFF","elements":[{{"type":"text","content":"<h2>T</h2><p>conteúdo</p>","position":"center","width":800,"height":400}}],"narrationScript":"narração","librasScript":"libras","notes":"","quizQuestions":[]}}]}}
```
Regras: title slides usam background #1e3a5f e texto branco. Quiz slides incluem 2 perguntas com 4 alternatives cada (uma isCorrect:true). Max 100 palavras/slide."""

        try:
            response = await chat.send_message(UserMessage(text=prompt))
            data = _extract_json(response)
            if data and "slides" in data:
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
                "background": "#1e3a5f" if sl.get("type") == "title" else "#FFFFFF",
                "elements": [{"type": "text", "content": f"<h2>{sl.get('title','')}</h2><p>{sl.get('purpose','')}</p>", "position": "center", "width": 800, "height": 400}],
                "narrationScript": sl.get("purpose", ""),
                "librasScript": sl.get("purpose", ""),
                "notes": "",
                "quizQuestions": [],
            })
    
    return {"slides": all_slides}


async def generate_course_from_storyboard(session_id: str, storyboard: dict, config: dict) -> dict:
    """Step 4: Convert storyboard into actual Scormfy project data."""
    from models import generate_id
    
    slides_data = storyboard.get("slides", [])
    project_slides = []
    quiz_questions = []
    
    for i, sb_slide in enumerate(slides_data):
        slide_elements = []
        
        for elem in sb_slide.get("elements", []):
            if elem.get("type") == "text":
                pos = elem.get("position", "center")
                x = 100 if pos == "left" else (960 if pos == "center" else 1100)
                w = elem.get("width", 800)
                h = elem.get("height", 400)
                y = 60 if sb_slide.get("type") == "title" else 40
                
                el = {
                    "id": generate_id(),
                    "type": "text",
                    "x": x - w // 2 if pos == "center" else x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "content": elem.get("content", ""),
                    "style": {
                        "fontSize": 28 if sb_slide.get("type") == "title" else 18,
                        "fontFamily": "Inter, sans-serif",
                        "fontColor": "#FFFFFF" if sb_slide.get("type") == "title" else "#333333",
                    },
                    "startTime": 0,
                    "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.3 * len(slide_elements)}],
                }
                slide_elements.append(el)
        
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
        
        bg = sb_slide.get("background", "#FFFFFF")
        if sb_slide.get("type") == "title" and bg == "#FFFFFF":
            bg = "#1e3a5f"
        
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
