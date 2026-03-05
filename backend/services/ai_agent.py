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
from datetime import datetime, timezone
from typing import Optional
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

logger = logging.getLogger(__name__)

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
        "id": "corporativo",
        "name": "Corporativo Clássico",
        "description": "Profissional e elegante, ideal para treinamentos empresariais",
        "preview": "linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%)",
        "palette": {"primary": "#0f172a", "accent": "#c9a227", "accentLight": "#fef3c7", "contentBg": "#f8fafc", "text": "#1e293b"},
        "fonts": {"heading": "'Georgia', 'Times New Roman', serif", "body": "'Inter', sans-serif"},
        "headerStyle": "solid",
        "cornerRadius": "4px",
    },
    {
        "id": "educacional",
        "name": "Educacional Moderno",
        "description": "Acolhedor e didático, perfeito para cursos de capacitação",
        "preview": "linear-gradient(135deg, #065f46 0%, #10b981 100%)",
        "palette": {"primary": "#065f46", "accent": "#10b981", "accentLight": "#d1fae5", "contentBg": "#f0fdf4", "text": "#1e293b"},
        "fonts": {"heading": "'Nunito', 'Segoe UI', sans-serif", "body": "'Nunito', sans-serif"},
        "headerStyle": "rounded",
        "cornerRadius": "12px",
    },
    {
        "id": "minimalista",
        "name": "Minimalista",
        "description": "Limpo e focado, com bastante espaço em branco",
        "preview": "linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)",
        "palette": {"primary": "#334155", "accent": "#64748b", "accentLight": "#f1f5f9", "contentBg": "#ffffff", "text": "#334155"},
        "fonts": {"heading": "'Outfit', 'Helvetica Neue', sans-serif", "body": "'Outfit', sans-serif"},
        "headerStyle": "minimal",
        "cornerRadius": "2px",
    },
    {
        "id": "tech",
        "name": "Tech & Inovação",
        "description": "Moderno e futurista, ideal para TI e tecnologia",
        "preview": "linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%)",
        "palette": {"primary": "#0a0a0a", "accent": "#06b6d4", "accentLight": "#164e63", "contentBg": "#111827", "text": "#e2e8f0"},
        "fonts": {"heading": "'JetBrains Mono', 'Fira Code', monospace", "body": "'Inter', sans-serif"},
        "headerStyle": "neon",
        "cornerRadius": "8px",
    },
    {
        "id": "criativo",
        "name": "Criativo Bold",
        "description": "Ousado e vibrante, para conteúdos dinâmicos",
        "preview": "linear-gradient(135deg, #4c1d95 0%, #ec4899 100%)",
        "palette": {"primary": "#4c1d95", "accent": "#ec4899", "accentLight": "#fce7f3", "contentBg": "#fdf4ff", "text": "#1e293b"},
        "fonts": {"heading": "'Poppins', 'Montserrat', sans-serif", "body": "'Poppins', sans-serif"},
        "headerStyle": "gradient",
        "cornerRadius": "16px",
    },
    {
        "id": "elegante",
        "name": "Elegante Premium",
        "description": "Sofisticado e refinado, para apresentações de alto nível",
        "preview": "linear-gradient(135deg, #1c1917 0%, #78350f 100%)",
        "palette": {"primary": "#1c1917", "accent": "#d97706", "accentLight": "#fef3c7", "contentBg": "#fefce8", "text": "#292524"},
        "fonts": {"heading": "'Playfair Display', 'Georgia', serif", "body": "'Lato', 'Helvetica', sans-serif"},
        "headerStyle": "elegant",
        "cornerRadius": "6px",
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
    return DESIGN_TEMPLATES[1]  # default: educacional

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
            seed = hashlib.md5(keyword.encode()).hexdigest()[:10]
            fname = f"ai_img_{seed}.png"
            fpath = os.path.join(project_dir, project_id, "assets", fname)
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            img_bytes = base64.b64decode(images[0]['data'])
            with open(fpath, "wb") as f:
                f.write(img_bytes)
            logger.info(f"AI image generated (Gemini) for '{keyword}' -> {fname}")
            
            # Persist in MongoDB for production environments with ephemeral storage (non-blocking)
            import threading
            try:
                from services.asset_store import store_asset_sync
                mongo_url = os.environ.get('MONGO_URL', '')
                db_name = os.environ.get('DB_NAME', '')
                if mongo_url and db_name:
                    threading.Thread(
                        target=store_asset_sync,
                        args=(mongo_url, db_name, project_id, fname, fpath),
                        daemon=True
                    ).start()
                    logger.info(f"AI image persisting to MongoDB: {project_id}/{fname}")
            except Exception as e:
                logger.warning(f"Failed to persist AI image in MongoDB (non-fatal): {e}")
            
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
        from motor.motor_asyncio import AsyncIOMotorClient
        _mongo_url = os.environ.get('MONGO_URL', '')
        _db_name = os.environ.get('DB_NAME', '')
        if not _mongo_url or not _db_name:
            return
        _client = AsyncIOMotorClient(_mongo_url)
        _db = _client[_db_name]
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
        _client.close()
    except Exception as e:
        logger.warning(f"Gallery auto-save failed (non-fatal): {e}")


async def _fetch_picsum_image(keyword: str, project_dir: str, project_id: str) -> Optional[str]:
    """Fallback: Download a stock image from picsum.photos."""
    import httpx
    import hashlib
    try:
        seed = hashlib.md5(keyword.encode()).hexdigest()[:10]
        url = f"https://picsum.photos/seed/{seed}/800/450"
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                fname = f"stock_{seed}.jpg"
                fpath = os.path.join(project_dir, project_id, "assets", fname)
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, "wb") as f:
                    f.write(resp.content)
                
                # Persist in MongoDB for production environments with ephemeral storage (non-blocking)
                import threading
                try:
                    from services.asset_store import store_asset_sync
                    mongo_url = os.environ.get('MONGO_URL', '')
                    db_name = os.environ.get('DB_NAME', '')
                    if mongo_url and db_name:
                        threading.Thread(
                            target=store_asset_sync,
                            args=(mongo_url, db_name, project_id, fname, fpath),
                            daemon=True
                        ).start()
                        logger.info(f"Stock image persisting to MongoDB: {project_id}/{fname}")
                except Exception as e:
                    logger.warning(f"Failed to persist stock image in MongoDB (non-fatal): {e}")
                
                return f"/api/projects/{project_id}/assets/{fname}"
    except Exception as e:
        logger.warning(f"Picsum fetch failed for '{keyword}': {e}")
    return None


def _build_title_slide(sb_slide: dict, palette: dict, course_title: str, module_names: list) -> dict:
    """Build a visually rich title/cover slide with template-specific styling."""
    from models import generate_id
    accent = palette["accent"]
    primary = palette.get("primary", "#0f172a")
    header_style = palette.get("headerStyle", "solid")
    font_heading = palette.get("fontHeading", "'Inter', sans-serif")
    font_body = palette.get("fontBody", "'Inter', sans-serif")
    elements = []

    # Top decorative element - varies by template
    if header_style == "neon":
        elements.append({
            "id": generate_id(), "type": "html", "x": 0, "y": 0, "width": 1920, "height": 8,
            "htmlContent": f'<div style="width:100%;height:100%;background:{accent};box-shadow:0 0 20px {accent}66;"></div>',
            "style": {}, "startTime": 0, "animations": [],
        })
    elif header_style == "gradient":
        elements.append({
            "id": generate_id(), "type": "html", "x": 0, "y": 0, "width": 1920, "height": 12,
            "htmlContent": f'<div style="width:100%;height:100%;background:linear-gradient(90deg, {primary}, {accent}, {primary});"></div>',
            "style": {}, "startTime": 0, "animations": [],
        })
    elif header_style == "minimal":
        pass  # No top bar for minimal
    elif header_style == "elegant":
        elements.append({
            "id": generate_id(), "type": "html", "x": 0, "y": 0, "width": 1920, "height": 6,
            "htmlContent": f'<div style="width:100%;height:100%;background:linear-gradient(90deg, transparent, {accent}, transparent);"></div>',
            "style": {}, "startTime": 0, "animations": [],
        })
    else:
        elements.append({
            "id": generate_id(), "type": "html", "x": 0, "y": 0, "width": 1920, "height": 8,
            "htmlContent": f'<div style="width:100%;height:100%;background:{accent};"></div>',
            "style": {}, "startTime": 0, "animations": [],
        })

    # Title text
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

    # Style-specific title alignment and decoration
    title_align = "center" if header_style not in ("minimal",) else "left"
    divider_html = ""
    if header_style == "neon":
        divider_html = f'<div style="width:120px;height:3px;background:{accent};margin:{"0 auto" if title_align=="center" else "0"} 30px {"auto" if title_align=="center" else "0"};box-shadow:0 0 10px {accent};border-radius:2px;"></div>'
    elif header_style == "elegant":
        divider_html = f'<div style="display:flex;align-items:center;justify-content:center;gap:12px;margin-bottom:30px;"><div style="width:60px;height:1px;background:{accent}88;"></div><div style="width:8px;height:8px;border:1px solid {accent};transform:rotate(45deg);"></div><div style="width:60px;height:1px;background:{accent}88;"></div></div>'
    elif header_style == "minimal":
        divider_html = f'<div style="width:40px;height:2px;background:{accent};margin-bottom:30px;"></div>'
    else:
        divider_html = f'<div style="width:80px;height:4px;background:{accent};margin:{"0 auto" if title_align=="center" else "0"} 30px {"auto" if title_align=="center" else "0"};border-radius:2px;"></div>'

    title_html = f'''<div style="text-align:{title_align};padding:20px;">
<h1 style="font-family:{font_heading};font-size:48px;font-weight:800;color:#ffffff;margin:0 0 20px 0;line-height:1.2;">{title_text}</h1>
{f'<p style="font-family:{font_body};font-size:20px;color:rgba(255,255,255,0.75);margin:0 0 30px 0;max-width:900px;{"margin-left:auto;margin-right:auto;" if title_align=="center" else ""}line-height:1.5;">{subtitle}</p>' if subtitle else ''}
{divider_html}
</div>'''
    elements.append({
        "id": generate_id(), "type": "html", "x": 160, "y": 120, "width": 1600, "height": 400,
        "htmlContent": title_html,
        "style": {"fontFamily": font_body}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.6, "delay": 0}],
    })

    # Module list
    if module_names:
        modules_html = f'<div style="text-align:{title_align};"><p style="font-family:{font_heading};font-size:14px;color:rgba(255,255,255,0.5);margin-bottom:12px;text-transform:uppercase;letter-spacing:2px;">Trilha do Curso</p>'
        for idx, mn in enumerate(module_names):
            if header_style == "neon":
                modules_html += f'<span style="display:inline-block;padding:6px 16px;margin:4px;border-radius:4px;background:rgba(255,255,255,0.03);color:{accent};font-size:13px;border:1px solid {accent}44;font-family:{font_body};">{idx+1}. {mn}</span>'
            elif header_style == "elegant":
                modules_html += f'<span style="display:inline-block;padding:6px 16px;margin:4px;border-radius:2px;background:rgba(255,255,255,0.05);color:rgba(255,255,255,0.7);font-size:13px;border-bottom:1px solid {accent}44;font-family:{font_body};">{idx+1}. {mn}</span>'
            else:
                modules_html += f'<span style="display:inline-block;padding:6px 16px;margin:4px;border-radius:20px;background:rgba(255,255,255,0.08);color:rgba(255,255,255,0.7);font-size:13px;border:1px solid rgba(255,255,255,0.1);font-family:{font_body};">{idx+1}. {mn}</span>'
        modules_html += '</div>'
        elements.append({
            "id": generate_id(), "type": "html", "x": 160, "y": 540, "width": 1600, "height": 200,
            "htmlContent": modules_html,
            "style": {"fontFamily": font_body}, "startTime": 0,
            "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.4}],
        })

    return elements


def _build_header_bar(palette: dict, left_text: str, right_text: str = "") -> str:
    """Build a header bar HTML with style variation based on design template."""
    accent = palette["accent"]
    primary = palette.get("primary", "#0f172a")
    font_heading = palette.get("fontHeading", "'Inter', sans-serif")
    style = palette.get("headerStyle", "solid")
    right_part = f'<span style="color:rgba(255,255,255,0.6);font-size:12px;margin-left:auto;font-family:{font_heading};">{right_text}</span>' if right_text else ''

    if style == "rounded":
        return f'''<div style="width:calc(100% - 40px);height:100%;margin:0 20px;background:{accent};border-radius:0 0 16px 16px;display:flex;align-items:center;padding:0 30px;">
<span style="color:#ffffff;font-size:13px;font-weight:600;letter-spacing:1px;text-transform:uppercase;font-family:{font_heading};">{left_text}</span>
{right_part}</div>'''
    elif style == "minimal":
        return f'''<div style="width:100%;height:100%;display:flex;align-items:flex-end;padding:0 30px 8px 30px;border-bottom:2px solid {accent}40;">
<span style="color:{accent};font-size:13px;font-weight:600;letter-spacing:2px;text-transform:uppercase;font-family:{font_heading};">{left_text}</span>
{right_part.replace("rgba(255,255,255,0.6)", accent+"99") if right_part else ''}</div>'''
    elif style == "neon":
        return f'''<div style="width:100%;height:100%;background:{primary};display:flex;align-items:center;padding:0 30px;border-bottom:2px solid {accent};box-shadow:0 2px 12px {accent}44;">
<span style="color:{accent};font-size:13px;font-weight:700;letter-spacing:2px;text-transform:uppercase;font-family:{font_heading};text-shadow:0 0 8px {accent}66;">{left_text}</span>
{right_part.replace("rgba(255,255,255,0.6)", accent+"88") if right_part else ''}</div>'''
    elif style == "gradient":
        return f'''<div style="width:100%;height:100%;background:linear-gradient(90deg, {primary}, {accent});display:flex;align-items:center;padding:0 30px;">
<span style="color:#ffffff;font-size:13px;font-weight:700;letter-spacing:1px;text-transform:uppercase;font-family:{font_heading};">{left_text}</span>
{right_part}</div>'''
    elif style == "elegant":
        return f'''<div style="width:100%;height:100%;background:{primary};display:flex;align-items:center;padding:0 30px;border-bottom:3px solid {accent};">
<div style="width:4px;height:24px;background:{accent};border-radius:2px;margin-right:12px;"></div>
<span style="color:#ffffff;font-size:13px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;font-family:{font_heading};">{left_text}</span>
{right_part}</div>'''
    else:  # solid (default)
        return f'''<div style="width:100%;height:100%;background:{accent};display:flex;align-items:center;padding:0 30px;">
<span style="color:#ffffff;font-size:13px;font-weight:600;letter-spacing:1px;text-transform:uppercase;font-family:{font_heading};">{left_text}</span>
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
        styled_text = _style_content_html(text_content, palette["text"], palette)
        elements.append({
            "id": generate_id(), "type": "html", "x": 60, "y": 80, "width": 1050, "height": 700,
            "htmlContent": styled_text,
            "style": {"fontFamily": font_body}, "startTime": 0,
            "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
        })
        # Image on the right
        elements.append({
            "id": generate_id(), "type": "image", "x": 1160, "y": 90, "width": 700, "height": 440,
            "src": image_url, "content": image_url,
            "style": {"borderRadius": corner_radius}, "startTime": 0,
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
        styled_text = _style_content_html(text_content, palette["text"], palette)
        elements.append({
            "id": generate_id(), "type": "html", "x": 80, "y": 80, "width": 1760, "height": 700,
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
        "id": generate_id(), "type": "html", "x": 0, "y": 0, "width": 1920, "height": 50,
        "htmlContent": header_html,
        "style": {}, "startTime": 0, "animations": [],
    })

    # Quiz intro text
    quiz_html = f'''<div style="text-align:center;padding:20px;">
<div style="display:inline-block;padding:8px 24px;border-radius:24px;background:{accent}22;border:1px solid {accent}44;">
<span style="color:{accent};font-size:14px;font-weight:600;font-family:{font_heading};">Hora de Praticar!</span>
</div>
<h2 style="font-family:{font_heading};font-size:28px;font-weight:700;color:#ffffff;margin:20px 0 10px 0;">Teste seus Conhecimentos</h2>
<p style="font-family:{font_body};font-size:16px;color:rgba(255,255,255,0.6);">Responda as perguntas para verificar seu aprendizado sobre {module_name}</p>
</div>'''
    elements.append({
        "id": generate_id(), "type": "html", "x": 160, "y": 60, "width": 1600, "height": 200,
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


def _build_summary_slide(sb_slide: dict, palette: dict, module_name: str) -> dict:
    """Build a visually rich summary slide."""
    from models import generate_id
    accent = palette["accent"]
    font_body = palette.get("fontBody", "'Inter', sans-serif")
    elements = []

    # Header (template-specific)
    header_html = _build_header_bar(palette, f"RESUMO - {module_name}")
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

    styled_text = _style_summary_html(text_content, accent, palette)
    elements.append({
        "id": generate_id(), "type": "html", "x": 160, "y": 80, "width": 1600, "height": 700,
        "htmlContent": styled_text,
        "style": {"fontFamily": font_body}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
    })

    return elements


def _style_content_html(raw_html: str, text_color: str, palette: dict = None) -> str:
    """Apply professional styling to content HTML with template fonts."""
    import re
    font_heading = palette.get("fontHeading", "'Inter', sans-serif") if palette else "'Inter', sans-serif"
    font_body = palette.get("fontBody", "'Inter', sans-serif") if palette else "'Inter', sans-serif"
    styled = raw_html
    # Style headings with heading font
    styled = re.sub(r'<h1([^>]*)>', f'<h1\\1 style="font-family:{font_heading};font-size:36px;font-weight:800;color:{text_color};margin:0 0 16px 0;line-height:1.2;">', styled)
    styled = re.sub(r'<h2([^>]*)>', f'<h2\\1 style="font-family:{font_heading};font-size:28px;font-weight:700;color:{text_color};margin:0 0 14px 0;line-height:1.3;">', styled)
    styled = re.sub(r'<h3([^>]*)>', f'<h3\\1 style="font-family:{font_heading};font-size:22px;font-weight:600;color:{text_color};margin:0 0 10px 0;line-height:1.3;">', styled)
    # Style paragraphs with body font
    styled = re.sub(r'<p([^>]*)>', f'<p\\1 style="font-family:{font_body};font-size:17px;color:{text_color}cc;line-height:1.7;margin:0 0 12px 0;">', styled)
    # Style lists
    styled = re.sub(r'<ul([^>]*)>', '<ul\\1 style="padding-left:20px;margin:8px 0;">', styled)
    styled = re.sub(r'<li([^>]*)>', f'<li\\1 style="font-family:{font_body};font-size:16px;color:{text_color}cc;line-height:1.6;margin-bottom:6px;">', styled)
    # Style bold
    styled = re.sub(r'<strong([^>]*)>', f'<strong\\1 style="color:{text_color};font-weight:700;">', styled)
    return f'<div style="padding:10px;font-family:{font_body};">{styled}</div>'


def _style_summary_html(raw_html: str, accent: str, palette: dict = None) -> str:
    """Apply professional styling to summary HTML with template fonts."""
    import re
    font_heading = palette.get("fontHeading", "'Inter', sans-serif") if palette else "'Inter', sans-serif"
    font_body = palette.get("fontBody", "'Inter', sans-serif") if palette else "'Inter', sans-serif"
    styled = raw_html
    styled = re.sub(r'<h1([^>]*)>', f'<h1\\1 style="font-family:{font_heading};font-size:32px;font-weight:800;color:#ffffff;margin:0 0 20px 0;text-align:center;">', styled)
    styled = re.sub(r'<h2([^>]*)>', f'<h2\\1 style="font-family:{font_heading};font-size:26px;font-weight:700;color:#ffffff;margin:20px 0 14px 0;text-align:center;">', styled)
    styled = re.sub(r'<p([^>]*)>', f'<p\\1 style="font-family:{font_body};font-size:17px;color:rgba(255,255,255,0.75);line-height:1.7;margin:0 0 12px 0;text-align:center;">', styled)
    styled = re.sub(r'<ul([^>]*)>', '<ul\\1 style="list-style:none;padding:0;margin:16px auto;max-width:800px;">', styled)
    styled = re.sub(r'<li([^>]*)>', f'<li\\1 style="font-family:{font_body};font-size:16px;color:rgba(255,255,255,0.8);padding:10px 16px;margin-bottom:8px;background:rgba(255,255,255,0.05);border-radius:8px;border-left:3px solid {accent};">', styled)
    styled = re.sub(r'<strong([^>]*)>', '<strong\\1 style="color:#ffffff;">', styled)
    return f'<div style="padding:20px;font-family:{font_body};">{styled}</div>'


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
        "id": generate_id(), "type": "html", "x": 1120, "y": 80, "width": 740, "height": 460,
        "htmlContent": f'''<div style="width:100%;height:100%;border-radius:12px;overflow:hidden;background:#000;position:relative;">
<iframe src="{embed_url}" style="width:100%;height:100%;border:none;" allowfullscreen allow="autoplay; encrypted-media"></iframe>
<div style="position:absolute;bottom:0;left:0;right:0;padding:6px 12px;background:linear-gradient(transparent,rgba(0,0,0,0.7));">
<span style="color:rgba(255,255,255,0.6);font-size:11px;">{platform}</span>
</div>
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
        "id": generate_id(), "type": "html", "x": 0, "y": 0, "width": 1920, "height": 50,
        "htmlContent": header_html, "style": {}, "startTime": 0, "animations": [],
    })

    # Text on the left
    text_content = ""
    for el in sb_slide.get("elements", []):
        if el.get("content"):
            text_content = el["content"]
    styled_text = _style_content_html(text_content, palette["text"], palette)
    elements.append({
        "id": generate_id(), "type": "html", "x": 60, "y": 80, "width": 1010, "height": 700,
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
    html = f'''<div data-heygen-slide="{slide_id}" style="width:100%;height:100%;border-radius:12px;background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);display:flex;align-items:center;justify-content:center;border:1px solid rgba(139,92,246,0.3);overflow:hidden;position:relative;">
<div style="position:absolute;inset:0;background:radial-gradient(circle at 50% 50%,rgba(139,92,246,0.08) 0%,transparent 70%);"></div>
<div style="text-align:center;position:relative;z-index:1;">
<div style="width:48px;height:48px;border:3px solid rgba(139,92,246,0.3);border-top-color:#8b5cf6;border-radius:50%;margin:0 auto 16px;animation:spin 1s linear infinite;"></div>
<p style="color:#c4b5fd;font-size:15px;font-weight:600;margin:0 0 6px;">Gerando vídeo com Avatar IA...</p>
<p style="color:rgba(196,181,253,0.5);font-size:12px;margin:0;">Isso pode levar 1-3 minutos</p>
</div>
<style>@keyframes spin{{from{{transform:rotate(0deg)}}to{{transform:rotate(360deg)}}}}</style>
</div>'''
    return {
        "id": generate_id(), "type": "html", "x": 1120, "y": 80, "width": 740, "height": 460,
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
        "id": generate_id(), "type": "html", "x": 0, "y": 0, "width": 1920, "height": 50,
        "htmlContent": header_html, "style": {}, "startTime": 0, "animations": [],
    })

    # Text on the left
    text_content = ""
    for el in sb_slide.get("elements", []):
        if el.get("content"):
            text_content = el["content"]
    styled_text = _style_content_html(text_content, palette["text"], palette)
    elements.append({
        "id": generate_id(), "type": "html", "x": 60, "y": 80, "width": 1010, "height": 700,
        "htmlContent": styled_text,
        "style": {"fontFamily": palette.get("fontBody", "'Inter', sans-serif")}, "startTime": 0,
        "animations": [{"id": generate_id(), "type": "entrance", "effect": "fade", "trigger": "withPrevious", "duration": 0.5, "delay": 0.1}],
    })

    # HeyGen processing element on the right
    elements.append(_build_heygen_processing_element(slide_id))

    return elements


def _build_content_slide_no_media(sb_slide: dict, palette: dict, module_name: str) -> list:
    """Build content slide without any media - full width text."""
    from models import generate_id
    elements = []

    # Header bar (template-specific)
    header_html = _build_header_bar(palette, module_name, sb_slide.get("title", ""))
    elements.append({
        "id": generate_id(), "type": "html", "x": 0, "y": 0, "width": 1920, "height": 50,
        "htmlContent": header_html, "style": {}, "startTime": 0, "animations": [],
    })

    # Full-width text
    text_content = ""
    for el in sb_slide.get("elements", []):
        if el.get("content"):
            text_content = el["content"]
    styled_text = _style_content_html(text_content, palette["text"], palette)
    elements.append({
        "id": generate_id(), "type": "html", "x": 80, "y": 80, "width": 1760, "height": 700,
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
        "id": generate_id(), "type": "html", "x": 0, "y": 0, "width": 1920, "height": 50,
        "htmlContent": header_html, "style": {}, "startTime": 0, "animations": [],
    })

    # Text on the left
    text_content = ""
    for el in sb_slide.get("elements", []):
        if el.get("content"):
            text_content = el["content"]
    styled_text = _style_content_html(text_content, palette["text"], palette)
    elements.append({
        "id": generate_id(), "type": "html", "x": 60, "y": 80, "width": 850, "height": 700,
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
        "id": generate_id(), "type": "html", "x": 0, "y": 0, "width": 1920, "height": 50,
        "htmlContent": header_html, "style": {}, "startTime": 0, "animations": [],
    })

    # Full-width text
    text_content = ""
    for el in sb_slide.get("elements", []):
        if el.get("content"):
            text_content = el["content"]
    styled_text = _style_content_html(text_content, palette["text"], palette)
    elements.append({
        "id": generate_id(), "type": "html", "x": 80, "y": 80, "width": 1760, "height": 560,
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
   style="display:inline-flex;align-items:center;gap:8px;padding:14px 40px;background:{btn_color};color:#ffffff;
   font-size:16px;font-weight:600;border-radius:8px;text-decoration:none;
   box-shadow:0 4px 15px rgba(0,0,0,0.3);transition:transform 0.2s,box-shadow 0.2s;cursor:pointer;"
   onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 6px 20px rgba(0,0,0,0.4)'"
   onmouseout="this.style.transform='translateY(0)';this.style.boxShadow='0 4px 15px rgba(0,0,0,0.3)'">
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




async def generate_course_from_storyboard(session_id: str, storyboard: dict, config: dict, project_dir: str = "", project_id: str = "", media_config: dict = None, bg_config: dict = None, global_text_color: str = "", global_font_size: str = "", global_animation: str = "", design_template_id: str = "") -> dict:
    """Convert storyboard into Scormfy project data with professional visuals and configurable media."""
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

    # Get design template (new system) or fall back to legacy palette selection
    design_token = None
    if design_template_id:
        design_token = get_design_template_by_id(design_template_id)
    
    if design_token:
        palette = design_token["palette"]
        font_heading = design_token["fonts"]["heading"]
        font_body = design_token["fonts"]["body"]
    else:
        # Legacy: select palette by title hash
        title_hash = int(hashlib.md5(config.get("title", "curso").encode()).hexdigest()[:8], 16)
        palette = _COURSE_PALETTES[title_hash % len(_COURSE_PALETTES)]
        font_heading = "'Inter', sans-serif"
        font_body = "'Inter', sans-serif"

    # Override text color with user's global choice
    if global_text_color:
        palette = {**palette, "text": global_text_color}

    # Inject font info into palette for use by builder functions
    palette["fontHeading"] = font_heading
    palette["fontBody"] = font_body
    palette["headerStyle"] = design_token.get("headerStyle", "solid") if design_token else "solid"
    palette["cornerRadius"] = design_token.get("cornerRadius", "12px") if design_token else "12px"

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
    for i, sb_slide in enumerate(slides_data):
        stype = sb_slide.get("type", "content")
        if stype != "content":
            continue
        mc = media_config.get(str(i), {})
        media_type = mc.get("type", "ai_image")  # default to ai_image

        if media_type == "ai_image":
            kw = sb_slide.get("imageKeywords", sb_slide.get("title", "education"))
            if project_dir and project_id:
                img_url = await _fetch_stock_image(kw, project_dir, project_id)
                if img_url:
                    slide_media[i] = {"type": "image", "url": img_url}
        elif media_type == "gallery_image":
            gallery_url = mc.get("galleryImageUrl", "")
            if gallery_url:
                slide_media[i] = {"type": "image", "url": gallery_url}
        elif media_type in ("youtube", "vimeo"):
            video_url = mc.get("url", "")
            video_info = _parse_video_url(video_url)
            if video_info:
                slide_media[i] = {"type": "video", "video_info": video_info}
        elif media_type == "heygen":
            # HeyGen with avatar/voice config - will trigger video generation
            slide_media[i] = {
                "type": "heygen",
                "avatar_id": mc.get("avatar_id", ""),
                "voice_id": mc.get("voice_id", ""),
            }
        elif media_type == "none":
            slide_media[i] = {"type": "none"}

    for i, sb_slide in enumerate(slides_data):
        stype = sb_slide.get("type", "content")
        module_name = sb_slide.get("moduleName", "")

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
            bg = palette["primary"]
            slide_elements = _build_title_slide(sb_slide, palette, config.get("title", ""), module_names)
        elif stype == "quiz":
            bg = palette["primary"]
            slide_elements = _build_quiz_slide(sb_slide, palette, module_name, slide_question_ids)
        elif stype == "summary":
            bg = palette["primary"]
            slide_elements = _build_summary_slide(sb_slide, palette, module_name)
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

        # Apply custom background from bgConfig (overrides palette defaults)
        custom_bg = bg_config.get(str(i), {})
        bg_image = None
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
                    except Exception as e:
                        logger.warning(f"Failed to save bg image for slide {i}: {e}")

        slide = {
            "id": actual_slide_id,
            "title": sb_slide.get("title", f"Slide {i+1}"),
            "order": i,
            "width": 1920,
            "height": 820,
            "background": bg,
            "backgroundImage": bg_image if bg_image else None,
            "backgroundOpacity": custom_bg.get("opacity", 100) if bg_image else None,
            "elements": slide_elements,
            "annotations": [],
            "transition": {"type": "fade", "duration": 0.5},
            "audio": [],
            "notes": sb_slide.get("notes", ""),
            "librasScript": sb_slide.get("librasScript", ""),
            "duration": 5.0,
        }
        project_slides.append(slide)

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

