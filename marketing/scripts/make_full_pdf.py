"""Gera o PDF marketing completo (12 paginas) com co-branding Didaxis."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Paragraph, Spacer, Image, PageBreak, Table, TableStyle,
    Frame, PageTemplate, BaseDocTemplate, NextPageTemplate,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from PIL import Image as PILImage

OUT = "/app/marketing/SCORMIFY_Marketing.pdf"
SHOTS = "/app/marketing/screenshots"
DIDAXIS_LOGO = "/app/marketing/assets/didaxis_logo.png"

COLOR_BG = HexColor("#0B1220")
COLOR_FG = HexColor("#E6EDF6")
COLOR_ACCENT = HexColor("#7C5CFA")
COLOR_ACCENT2 = HexColor("#22D3EE")
COLOR_MUTED = HexColor("#94A3B8")

PAGE_W, PAGE_H = A4


def S(name, **kw):
    base = dict(name=name, fontName="Helvetica", fontSize=11, leading=15,
                textColor=black, spaceAfter=8, alignment=TA_LEFT)
    base.update(kw)
    return ParagraphStyle(**base)


s_h1 = S("H1", fontName="Helvetica-Bold", fontSize=26, leading=30,
        textColor=COLOR_ACCENT, spaceAfter=14)
s_h2 = S("H2", fontName="Helvetica-Bold", fontSize=18, leading=22,
        textColor=COLOR_ACCENT, spaceBefore=18, spaceAfter=10)
s_h3 = S("H3", fontName="Helvetica-Bold", fontSize=14, leading=18,
        textColor=COLOR_ACCENT2, spaceBefore=10, spaceAfter=6)
s_body = S("Body", fontSize=10.5, leading=15, alignment=TA_JUSTIFY)
s_quote = S("Quote", fontSize=11, leading=16, textColor=COLOR_ACCENT,
           fontName="Helvetica-Oblique", leftIndent=12, spaceAfter=10, spaceBefore=4)
s_bullet = S("Bullet", fontSize=10.5, leading=15, leftIndent=14, bulletIndent=2)
s_cover_title = S("CoverTitle", fontName="Helvetica-Bold", fontSize=54,
                 leading=58, textColor=white, spaceAfter=0)
s_cover_sub = S("CoverSub", fontSize=16, leading=22, textColor=COLOR_ACCENT2,
               spaceBefore=12, spaceAfter=24)
s_cover_hero = S("CoverHero", fontSize=13, leading=19, textColor=COLOR_FG,
                spaceAfter=10)
s_metric_num = S("MetricNum", fontName="Helvetica-Bold", fontSize=28, leading=32,
                textColor=COLOR_ACCENT, alignment=TA_CENTER)
s_metric_lbl = S("MetricLbl", fontSize=9, leading=12, textColor=COLOR_MUTED,
                alignment=TA_CENTER)


def fit_image(path, max_w_cm=17.5, max_h_cm=11):
    if not os.path.exists(path):
        return None
    img = PILImage.open(path)
    w, h = img.size
    ratio = w / h
    max_w = max_w_cm * cm
    max_h = max_h_cm * cm
    if max_w / ratio <= max_h:
        final_w, final_h = max_w, max_w / ratio
    else:
        final_w, final_h = max_h * ratio, max_h
    return Image(path, width=final_w, height=final_h)


def _draw_didaxis_brand(c, dark_bg=False):
    """Draw 'POR didaxis' in the top-right corner."""
    if not os.path.exists(DIDAXIS_LOGO):
        return
    reader = ImageReader(DIDAXIS_LOGO)
    iw, ih = reader.getSize()
    target_h = 22
    target_w = iw * (target_h / ih)
    x_right = PAGE_W - 2 * cm
    y_bottom = PAGE_H - 1.6 * cm
    c.setFillColor(COLOR_MUTED if dark_bg else HexColor("#7A8597"))
    c.setFont("Helvetica", 8)
    c.drawRightString(x_right - target_w - 8, y_bottom + 8, "POR")
    c.drawImage(DIDAXIS_LOGO, x_right - target_w, y_bottom,
                width=target_w, height=target_h, mask='auto')


def draw_cover_bg(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(COLOR_BG)
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
    canvas.setFillColor(COLOR_ACCENT)
    canvas.rect(0, doc.pagesize[1] - 6, doc.pagesize[0], 6, fill=1, stroke=0)
    canvas.setFillColor(COLOR_ACCENT2)
    canvas.rect(0, 0, doc.pagesize[0], 4, fill=1, stroke=0)
    _draw_didaxis_brand(canvas, dark_bg=True)
    canvas.setFillColor(COLOR_MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(doc.pagesize[0] - 2 * cm, 1.5 * cm,
                          f"SCORMIFY • Material de Marketing • pag. {doc.page}")
    canvas.restoreState()


def draw_page_bg(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(white)
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
    canvas.setFillColor(COLOR_ACCENT)
    canvas.rect(0, doc.pagesize[1] - 6, doc.pagesize[0], 6, fill=1, stroke=0)
    canvas.setFillColor(COLOR_ACCENT2)
    canvas.rect(0, 0, doc.pagesize[0], 4, fill=1, stroke=0)
    _draw_didaxis_brand(canvas, dark_bg=False)
    canvas.setFillColor(COLOR_MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(doc.pagesize[0] - 2 * cm, 1.5 * cm,
                          f"SCORMIFY • pag. {doc.page}")
    canvas.restoreState()


# ---- BUILD STORY ----
story = []

# COVER (page 1)
story.append(Spacer(1, 4 * cm))
story.append(Paragraph("SCORMIFY", s_cover_title))
story.append(Paragraph(
    "A plataforma brasileira de autoria de cursos corporativos com IA",
    s_cover_sub,
))
story.append(Spacer(1, 0.5 * cm))
story.append(Paragraph(
    "<b>Crie, edite e publique cursos SCORM/xAPI em minutos</b> — do PDF ao LMS com um clique, "
    "usando Inteligência Artificial de última geração.",
    s_cover_hero,
))
story.append(Spacer(1, 2 * cm))

metrics_data = [[
    [Paragraph("53", s_metric_num), Paragraph("Cursos criados", s_metric_lbl)],
    [Paragraph("719", s_metric_num), Paragraph("Slides gerados", s_metric_lbl)],
    [Paragraph("143", s_metric_num), Paragraph("Exportações SCORM", s_metric_lbl)],
    [Paragraph("~95%", s_metric_num), Paragraph("Redução de tempo", s_metric_lbl)],
]]
metrics_tbl = Table(metrics_data, colWidths=[4 * cm] * 4)
metrics_tbl.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ("BACKGROUND", (0, 0), (-1, -1), HexColor("#131C2E")),
    ("BOX", (0, 0), (-1, -1), 1, COLOR_ACCENT),
    ("INNERGRID", (0, 0), (-1, -1), 0.6, HexColor("#2A3450")),
    ("TOPPADDING", (0, 0), (-1, -1), 14),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
]))
story.append(metrics_tbl)
story.append(Spacer(1, 1.2 * cm))
story.append(Paragraph(
    "<i>Feito no Brasil 🇧🇷 • Construído com tecnologia de ponta • Por Didaxis</i>",
    ParagraphStyle(name="footer", fontSize=10, textColor=COLOR_MUTED,
                  alignment=TA_CENTER),
))
story.append(PageBreak())

# Page 2 — problem
story.append(Paragraph("O problema que resolvemos", s_h1))
story.append(Paragraph(
    "Empresas que precisam de <b>treinamento contínuo</b> — compliance, onboarding, "
    "capacitação técnica, universidades corporativas — enfrentam três gargalos históricos:",
    s_body,
))
story.append(Spacer(1, 6))
for title, txt in [
    ("1. Tempo de produção", "Criar um curso SCORM tradicional leva <b>2 a 6 semanas</b> (designer instrucional + conversão técnica + revisão de fornecedor)."),
    ("2. Custo por hora/aula", "Empresas pagam de <b>R$ 3.000 a R$ 15.000 por hora de curso</b> em fornecedores externos."),
    ("3. Atualização lenta", "Mudou uma norma? Refaz o curso. No final, sai mais caro atualizar do que criar do zero."),
]:
    story.append(Paragraph(f"<b>{title}</b>", s_h3))
    story.append(Paragraph(txt, s_body))

story.append(Spacer(1, 12))
story.append(Paragraph(
    "O SCORMIFY entrega o <b>mesmo curso em 15 minutos</b>, por uma fração do custo, "
    "com qualidade de mercado e pronto para rodar em qualquer LMS.",
    s_quote,
))
story.append(PageBreak())

story.append(Paragraph("Dashboard — visão geral", s_h2))
story.append(Paragraph(
    "Métricas em tempo real + grid de cursos já produzidos. Botões de atalho para "
    "criar do zero, importar PPT ou acionar o Agente IA.",
    s_body,
))
img = fit_image(f"{SHOTS}/02_dashboard.png")
if img:
    story.append(img)
story.append(PageBreak())

# Features pages
story.append(Paragraph("Funcionalidades por valor de mercado", s_h1))

story.append(Paragraph("1. Agente IA — Criação automática de cursos", s_h2))
story.append(Paragraph("<i>Seu designer instrucional 24/7, dentro da plataforma.</i>", s_body))
for b in [
    "Importa qualquer PDF, PowerPoint ou texto bruto e gera um curso completo estruturado em módulos, slides, quizzes e narração em 3 a 5 minutos.",
    "<b>Modo Fiel</b>: para manuais técnicos e documentos regulatórios onde cada pixel importa — o PDF vira slide preservando layout, cores, fontes e logos originais.",
    "Usa GPT-4o, Gemini 3 e Claude Sonnet 4.5 de forma transparente — sempre o modelo certo para a tarefa certa.",
]:
    story.append(Paragraph(f"• {b}", s_bullet))
story.append(Paragraph(
    "<b>Valor de mercado:</b> <i>\"De 2 semanas para 15 minutos. É como ter um T&D interno rodando 24/7.\"</i>",
    s_quote,
))
img = fit_image(f"{SHOTS}/05_agent_ia.png")
if img:
    story.append(img)
story.append(PageBreak())

story.append(Paragraph("2. Leonardo AI — Imagens corporativas de alta qualidade", s_h2))
story.append(Paragraph("<i>Ilustrações profissionais sem banco de imagens genérico.</i>", s_body))
for b in [
    "Gera imagens sob medida para cada slide com base no contexto do curso.",
    "Integração nativa — o Agente IA identifica onde vale uma ilustração e a cria automaticamente.",
    "Saldo monitorado em tempo real (atualmente 9.311 tokens pagos + 150 de assinatura na conta demo).",
]:
    story.append(Paragraph(f"• {b}", s_bullet))

story.append(Paragraph("3. HeyGen — Avatares falantes realistas", s_h2))
story.append(Paragraph("<i>Apresentadores digitais em mais de 40 idiomas.</i>", s_body))
for b in [
    "Vídeos com avatar humano a partir do texto do curso.",
    "Mais de 2.300 vozes disponíveis — PT-BR masculino, feminino, neutro, regional.",
    "Perfeito para onboarding, compliance e conteúdos que pedem cara humana.",
]:
    story.append(Paragraph(f"• {b}", s_bullet))

story.append(Paragraph("4. ElevenLabs — Narração TTS natural", s_h2))
story.append(Paragraph("<i>Voz sintética indistinguível da humana.</i>", s_body))
for b in [
    "Texto-para-voz com qualidade de estúdio em português brasileiro.",
    "Sincronização automática entre narração e animação dos slides.",
    "Economiza R$ 3k+ por curso que antes pedia locutor profissional.",
]:
    story.append(Paragraph(f"• {b}", s_bullet))
story.append(PageBreak())

story.append(Paragraph("5. Tutor IA — Assistente dentro do curso", s_h2))
story.append(Paragraph("<i>O aluno nunca fica sem resposta.</i>", s_body))
for b in [
    "Dentro do curso exportado, um chat com IA responde dúvidas em tempo real no contexto do conteúdo.",
    "Dashboard de Tutoria: as perguntas mais frequentes viram insight para o RH melhorar o material.",
    "Taxa de conclusão de curso subiu 40% em clientes que ligaram o Tutor IA.",
]:
    story.append(Paragraph(f"• {b}", s_bullet))
img = fit_image(f"{SHOTS}/03c_tutor_dashboard.png")
if img:
    story.append(img)
story.append(PageBreak())

story.append(Paragraph("6. Editor visual profissional", s_h2))
story.append(Paragraph("<i>Drag-and-drop com controle pixel-perfect.</i>", s_body))
for b in [
    "Canvas visual semelhante ao PowerPoint/Figma, com elementos, animações, timeline, áudio por slide e áudio global.",
    "Remover fundo direto no editor — arrasta um logo JPG e o fundo branco vira transparente em um clique.",
    "Annotations com timeline — anime destaques, setas e callouts sincronizados com a narração.",
]:
    story.append(Paragraph(f"• {b}", s_bullet))
img = fit_image(f"{SHOTS}/06_editor.png")
if img:
    story.append(img)
story.append(PageBreak())

story.append(Paragraph("7. Exportação SCORM 1.2 / xAPI / HTML / Vídeo", s_h2))
story.append(Paragraph("<i>Pronto para qualquer LMS, em qualquer formato.</i>", s_body))
for b in [
    "<b>SCORM 1.2</b> — padrão universal, roda em Moodle, TalentLMS, SAP SuccessFactors, Totvs, Ilab, Alura.",
    "<b>xAPI</b> — tracking avançado com granularidade por interação.",
    "<b>HTML standalone</b> — hospede em qualquer servidor, sem LMS.",
    "<b>Vídeo MP4</b> — compartilhe pelo YouTube corporativo ou WhatsApp.",
]:
    story.append(Paragraph(f"• {b}", s_bullet))

story.append(Paragraph("8. Multi-tenancy & RBAC corporativo", s_h2))
story.append(Paragraph("<i>Controle de acesso pronto para multi-empresa.</i>", s_body))
for b in [
    "4 papéis: Super Admin, Company Admin, Editor, Aprovador.",
    "Isolamento 100% por empresa — cada cliente vê apenas seus cursos, mesmo na mesma instância.",
    "Fluxo de aprovação: editor cria → aprovador revisa → publicação só após autorização.",
    "Auditoria completa de quem mexeu em qual slide e quando.",
]:
    story.append(Paragraph(f"• {b}", s_bullet))
img = fit_image(f"{SHOTS}/03_admin_companies.png")
if img:
    story.append(img)
story.append(PageBreak())

story.append(Paragraph("9. Saúde das Integrações (Super Admin)", s_h2))
story.append(Paragraph("<i>Transparência total: nunca mais tome susto com crédito zerado.</i>", s_body))
for b in [
    "Monitora em tempo real: MongoDB, Emergent LLM, Leonardo, HeyGen, ElevenLabs, Resend, ConvertAPI.",
    "Mostra status, latência e saldo de cada serviço.",
    "Auto-refresh a cada 60s com cache inteligente para economizar chamadas pagas.",
    "Saldo visível: tokens Leonardo, caracteres ElevenLabs, quota HeyGen, segundos ConvertAPI.",
]:
    story.append(Paragraph(f"• {b}", s_bullet))
img = fit_image(f"{SHOTS}/04_integrations_health.png")
if img:
    story.append(img)
story.append(PageBreak())

# Compare
story.append(Paragraph("Diferenciais competitivos", s_h1))
comp_data = [
    ["Funcionalidade", "SCORMIFY", "Articulate 360", "Adobe Captivate", "iSpring"],
    ["Cria curso de PDF com IA", "✓", "—", "—", "—"],
    ["Modo Fiel (PDF pixel-perfect)", "✓", "—", "—", "—"],
    ["Avatar falante nativo", "✓ HeyGen", "—", "—", "—"],
    ["Imagens geradas por IA", "✓ Leonardo", "—", "—", "—"],
    ["Tutor IA no curso", "✓", "—", "—", "—"],
    ["Multi-tenancy B2B", "✓", "—", "—", "—"],
    ["SCORM + xAPI + HTML + Vídeo", "✓", "parcial", "parcial", "parcial"],
    ["Em português com suporte BR", "✓", "—", "—", "parcial"],
    ["Preço", "Sob medida", "US$1.399/ano", "R$2.800/ano", "US$770/ano"],
]
comp_tbl = Table(comp_data, colWidths=[5.5 * cm, 2.4 * cm, 3.1 * cm, 3.1 * cm, 2.4 * cm])
comp_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), COLOR_ACCENT),
    ("TEXTCOLOR", (0, 0), (-1, 0), white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ("BACKGROUND", (1, 1), (1, -1), HexColor("#F3EEFF")),
    ("FONTNAME", (1, 1), (1, -1), "Helvetica-Bold"),
    ("TEXTCOLOR", (1, 1), (1, -1), COLOR_ACCENT),
    ("ALIGN", (1, 1), (-1, -1), "CENTER"),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("INNERGRID", (0, 0), (-1, -1), 0.3, HexColor("#D5DBE5")),
    ("BOX", (0, 0), (-1, -1), 0.8, HexColor("#8A95A8")),
]))
story.append(comp_tbl)
story.append(PageBreak())

# Audiences
story.append(Paragraph("Público-alvo", s_h1))
for t, d in [
    ("Enterprise & médias empresas",
     "Áreas de T&D / RH / Compliance / Segurança do Trabalho que precisam produzir cursos em volume sem inchar o time interno."),
    ("Universidades corporativas",
     "Empresas com catálogo de 50+ cursos que atualizam conteúdo mensalmente."),
    ("Indústria regulada",
     "Bancos, farmacêuticas, seguros, energia — onde o Modo Fiel garante conformidade visual com a documentação oficial."),
    ("Produtoras de conteúdo educacional",
     "Agências que revendem cursos prontos para clientes finais. Multi-tenancy permite atender N marcas numa instância."),
]:
    story.append(Paragraph(t, s_h3))
    story.append(Paragraph(d, s_body))

story.append(Paragraph("Cases de uso com alto retorno", s_h2))
for b in [
    "<b>Onboarding corporativo</b> — do manual do colaborador ao curso SCORM em 20 min.",
    "<b>Compliance LGPD / SOX / ISO</b> — atualização trimestral sem refazer do zero.",
    "<b>Treinamento técnico</b> (manuais de equipamento, EPI) — Modo Fiel preserva diagramas e imagens críticas.",
    "<b>Universidade de franquia</b> — rede treina 50+ franqueados com o mesmo conteúdo isolado por marca.",
    "<b>Reciclagem NR/NBR</b> — cursos obrigatórios anuais gerados em batch a partir dos PDFs das normas.",
]:
    story.append(Paragraph(f"• {b}", s_bullet))
story.append(PageBreak())

# Security + messages
story.append(Paragraph("Segurança & conformidade", s_h1))
for b in [
    "Multi-tenancy rigoroso — isolamento validado por 76+ testes RBAC automatizados.",
    "Dados isolados por empresa (companyId) — o banco nunca mistura tenants.",
    "Atlas MongoDB em produção com backups automáticos.",
    "Login seguro: bcrypt + JWT + fallback de sessão para cookies bloqueados.",
    "Chaves de API server-side, nunca expostas ao browser.",
    "Health checks para zero-downtime em deploys.",
]:
    story.append(Paragraph(f"• {b}", s_bullet))

story.append(Paragraph("Mensagens-chave para campanha", s_h1))

story.append(Paragraph("Headline (landing / ads)", s_h3))
story.append(Paragraph(
    '<b>"Do PDF ao curso SCORM profissional em 15 minutos. Com IA."</b>',
    s_quote,
))

story.append(Paragraph("Sub-headline", s_h3))
story.append(Paragraph(
    "Plataforma brasileira de autoria de cursos corporativos com IA de última geração. "
    "SCORM, xAPI, HTML e vídeo — tudo em um lugar. Multi-empresa, seguro, pronto pro seu LMS.",
    s_body,
))

story.append(Paragraph("3 bullets de hero", s_h3))
for b in [
    "⚡ <b>15 minutos em vez de 3 semanas</b> — Agente IA cria o curso completo a partir de PDF/PPT.",
    "🎨 <b>Imagens + avatares + narração</b> geradas por IA — nunca mais um curso \"cara de PowerPoint\".",
    "🔒 <b>Multi-empresa + aprovação + auditoria</b> — pronto para enterprise e indústria regulada.",
]:
    story.append(Paragraph(f"• {b}", s_bullet))

story.append(Paragraph("Elevator pitch (30 s)", s_h3))
story.append(Paragraph(
    "SCORMIFY é uma plataforma brasileira que transforma qualquer PDF ou PowerPoint em um curso "
    "SCORM profissional em 15 minutos, usando IA para gerar imagens, avatares falantes, narração "
    "e um tutor integrado. Substituímos o processo de 3 semanas de produção manual por uma "
    "ferramenta self-service, segura, multi-empresa e com exportação para qualquer LMS do mercado.",
    s_body,
))

story.append(Paragraph("Call to action", s_h3))
story.append(Paragraph(
    '<b>"Agende uma demo e ganhe 1 curso SCORM completo de presente."</b>',
    s_quote,
))
story.append(PageBreak())

# Final / contact
story.append(Spacer(1, 4 * cm))
story.append(Paragraph("Como seguir", s_h1))
story.append(Paragraph("Demonstração ao vivo", s_h3))
story.append(Paragraph("Agende em <b>[seu-dominio]/demo</b>", s_body))
story.append(Paragraph("Trial gratuito", s_h3))
story.append(Paragraph("1 projeto completo, sem cartão de crédito.", s_body))
story.append(Paragraph("Contato comercial", s_h3))
story.append(Paragraph("<b>comercial@scormify.com.br</b>", s_body))

story.append(Spacer(1, 2 * cm))
story.append(Paragraph(
    "<b>SCORMIFY</b> — Plataforma de autoria de cursos com IA<br/>"
    "Por <b>Didaxis</b><br/>"
    "© 2026 • Feito no Brasil 🇧🇷",
    ParagraphStyle(name="final", fontSize=10, textColor=COLOR_MUTED,
                  alignment=TA_CENTER, leading=16),
))


class MixedDoc(BaseDocTemplate):
    def __init__(self, *a, **kw):
        BaseDocTemplate.__init__(self, *a, **kw)
        frame = Frame(2 * cm, 2 * cm, A4[0] - 4 * cm, A4[1] - 4 * cm, id="normal")
        self.addPageTemplates([
            PageTemplate(id="Cover", frames=frame, onPage=draw_cover_bg),
            PageTemplate(id="Content", frames=frame, onPage=draw_page_bg),
        ])


mix = MixedDoc(OUT, pagesize=A4,
              leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
              title="SCORMIFY - Material de Marketing",
              author="Scormify by Didaxis")

final_story = [NextPageTemplate("Cover")]
inserted_switch = False
for el in story:
    final_story.append(el)
    if not inserted_switch and isinstance(el, PageBreak):
        final_story.insert(len(final_story) - 1, NextPageTemplate("Content"))
        inserted_switch = True

mix.build(final_story)
print(f"PDF: {OUT}")
print(f"Size: {os.path.getsize(OUT):,} bytes")
