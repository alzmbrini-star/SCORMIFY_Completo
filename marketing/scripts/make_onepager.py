"""Gera o one-pager A4 com co-branding Didaxis."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Paragraph, Spacer, Image, Table, TableStyle, Frame,
    PageTemplate, BaseDocTemplate,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from PIL import Image as PILImage

OUT = "/app/marketing/SCORMIFY_OnePager.pdf"
SHOTS = "/app/marketing/screenshots"
DIDAXIS_LOGO = "/app/marketing/assets/didaxis_logo.png"

BG = HexColor("#0A0E1A")
BG2 = HexColor("#131A33")
FG = HexColor("#E8EDF8")
MUTED = HexColor("#8C96B2")
ACCENT = HexColor("#7C5CFA")
ACCENT2 = HexColor("#22D3EE")
SUCCESS = HexColor("#22C55E")
PAGE_W, PAGE_H = A4


def draw_background(canvas, doc):
    c = canvas
    c.saveState()
    c.setFillColor(BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(ACCENT)
    c.rect(0, PAGE_H - 8, PAGE_W * 0.55, 8, fill=1, stroke=0)
    c.setFillColor(ACCENT2)
    c.rect(PAGE_W * 0.55, PAGE_H - 8, PAGE_W * 0.45, 8, fill=1, stroke=0)
    for radius, alpha in [(180, 0.05), (120, 0.08), (60, 0.12)]:
        c.setFillColorRGB(0.49, 0.36, 0.98, alpha=alpha)
        c.circle(80, PAGE_H - 80, radius, fill=1, stroke=0)

    # Co-branding "BY didaxis" top-right
    if os.path.exists(DIDAXIS_LOGO):
        reader = ImageReader(DIDAXIS_LOGO)
        iw, ih = reader.getSize()
        target_h = 16
        target_w = iw * (target_h / ih)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7)
        # "POR" label with line above logo
        x_logo_right = PAGE_W - 2 * cm
        y_logo_bottom = PAGE_H - 1.4 * cm
        c.drawRightString(x_logo_right - target_w - 6, y_logo_bottom + 4, "POR")
        c.drawImage(DIDAXIS_LOGO,
                   x_logo_right - target_w, y_logo_bottom,
                   width=target_w, height=target_h, mask='auto')

    c.setFillColor(ACCENT2)
    c.rect(0, 0, PAGE_W, 4, fill=1, stroke=0)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(2 * cm, 0.8 * cm,
                "SCORMIFY • Plataforma brasileira de autoria de cursos com IA • por Didaxis")
    c.setFillColor(ACCENT2)
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(PAGE_W - 2 * cm, 0.8 * cm, "comercial@scormify.com.br")
    c.restoreState()


def S(name, **kw):
    base = dict(name=name, fontName="Helvetica", fontSize=9, leading=12,
                textColor=FG, alignment=TA_LEFT, spaceAfter=4)
    base.update(kw)
    return ParagraphStyle(**base)


s_brand = S("Brand", fontName="Helvetica-Bold", fontSize=12, textColor=ACCENT2,
           leading=14, spaceAfter=0)
s_title = S("Title", fontName="Helvetica-Bold", fontSize=26, leading=28,
           textColor=FG, spaceAfter=6, spaceBefore=4)
s_lede = S("Lede", fontSize=10.5, leading=14.5, textColor=MUTED, spaceAfter=12)
s_h3 = S("H3", fontName="Helvetica-Bold", fontSize=11, textColor=ACCENT2,
        leading=14, spaceBefore=0, spaceAfter=4)
s_body = S("Body", fontSize=8.5, leading=11.5, textColor=FG, spaceAfter=3)
s_body_muted = S("BodyM", fontSize=8.5, leading=11.5, textColor=MUTED, spaceAfter=3)
s_metric_n = S("MetN", fontName="Helvetica-Bold", fontSize=20, leading=22,
              textColor=ACCENT, alignment=TA_CENTER, spaceAfter=0)
s_metric_l = S("MetL", fontSize=7.5, leading=10, textColor=MUTED,
              alignment=TA_CENTER, spaceAfter=0)
s_cta_h = S("CtaH", fontName="Helvetica-Bold", fontSize=13, leading=16,
           textColor=white, alignment=TA_CENTER, spaceAfter=4)
s_cta_b = S("CtaB", fontSize=9.5, leading=13, textColor=white,
           alignment=TA_CENTER, spaceAfter=6)


def fit_image(path, max_w, max_h):
    if not os.path.exists(path):
        return None
    img = PILImage.open(path)
    w, h = img.size
    ratio = w / h
    if max_w / ratio <= max_h:
        fw, fh = max_w, max_w / ratio
    else:
        fw, fh = max_h * ratio, max_h
    return Image(path, width=fw, height=fh)


story = []
story.append(Paragraph("SCORMIFY", s_brand))
story.append(Paragraph(
    '<font color="#E8EDF8">Do PDF ao </font>'
    '<font color="#7C5CFA">curso SCORM profissional</font>'
    '<font color="#E8EDF8"> em 15 minutos.</font>',
    s_title,
))
story.append(Paragraph(
    "Plataforma brasileira de autoria de cursos corporativos com IA. "
    "Gera slides, imagens, narração e avatar falante automaticamente. "
    "Exporta SCORM 1.2, xAPI, HTML e vídeo.",
    s_lede,
))

metrics_row = Table([[
    [Paragraph("53", s_metric_n), Paragraph("CURSOS CRIADOS", s_metric_l)],
    [Paragraph("719", s_metric_n), Paragraph("SLIDES GERADOS", s_metric_l)],
    [Paragraph("~95%", s_metric_n), Paragraph("MENOS TEMPO", s_metric_l)],
    [Paragraph("7", s_metric_n), Paragraph("IAs INTEGRADAS", s_metric_l)],
]], colWidths=[4.0 * cm] * 4)
metrics_row.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ("BACKGROUND", (0, 0), (-1, -1), BG2),
    ("BOX", (0, 0), (-1, -1), 0.6, ACCENT),
    ("INNERGRID", (0, 0), (-1, -1), 0.4, HexColor("#2A3450")),
    ("TOPPADDING", (0, 0), (-1, -1), 10),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
]))
story.append(metrics_row)
story.append(Spacer(1, 8))

feat_items = [
    ("[IA]", "Agente IA", "PDF/PPT ⇒ curso completo em 3-5 min. GPT-4o + Gemini + Claude."),
    ("[IMG]", "Leonardo AI", "Imagens corporativas sob medida para cada slide."),
    ("[AV]", "HeyGen", "Avatares falantes em mais de 2.300 vozes (PT-BR)."),
    ("[TTS]", "ElevenLabs", "Narração TTS de qualidade estúdio, sincronizada."),
    ("[ED]", "Editor visual", "Drag-and-drop + timeline + remover fundo em 1 clique."),
    ("[TUT]", "Tutor IA", "Chat no curso responde dúvidas. +40% na conclusão."),
    ("[EXP]", "SCORM/xAPI/HTML/MP4", "Roda em Moodle, TalentLMS, SAP SuccessFactors etc."),
    ("[ORG]", "Multi-tenant RBAC", "4 papéis. Isolamento 100% por empresa. 76+ testes."),
]


def feat_cell(tag, title, desc):
    return [
        Paragraph(
            f'<font color="#22D3EE"><b>{tag}</b></font> '
            f'<font color="#E8EDF8"><b>{title}</b></font>',
            s_body),
        Paragraph(f'<font color="#8C96B2">{desc}</font>', s_body_muted),
    ]


feat_rows = []
for i in range(0, len(feat_items), 2):
    a = feat_cell(*feat_items[i])
    b = feat_cell(*feat_items[i + 1]) if i + 1 < len(feat_items) else [""]
    feat_rows.append([a, b])

feat_table = Table(feat_rows, colWidths=[5.1 * cm, 5.1 * cm])
feat_table.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
]))

shot = fit_image(f"{SHOTS}/02_dashboard.png", max_w=7.3 * cm, max_h=5.0 * cm)

content_row = Table([
    [
        [Paragraph("<b>O QUE A PLATAFORMA FAZ</b>", s_h3), feat_table],
        [
            Paragraph("<b>DASHBOARD AO VIVO</b>", s_h3),
            shot if shot else Paragraph("[screenshot]", s_body_muted),
            Spacer(1, 4),
            Paragraph(
                "<font color='#8C96B2'>Métricas em tempo real + grid de cursos + atalhos "
                "para o Agente IA. Tudo em um workflow.</font>",
                s_body_muted,
            ),
        ]
    ]
], colWidths=[10.4 * cm, 7.6 * cm])
content_row.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ("TOPPADDING", (0, 0), (-1, -1), 0),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
]))
story.append(content_row)
story.append(Spacer(1, 8))

story.append(Paragraph("<b>O QUE NINGUÉM MAIS OFERECE</b>", s_h3))

compare_data = [
    ["", "SCORMIFY", "Articulate 360", "Adobe Captivate", "iSpring"],
    ["PDF → curso com IA", "✓", "—", "—", "—"],
    ["Modo Fiel pixel-perfect", "✓", "—", "—", "—"],
    ["Avatar falante nativo", "✓", "—", "—", "—"],
    ["Imagens geradas por IA", "✓", "—", "—", "—"],
    ["Tutor IA dentro do curso", "✓", "—", "—", "—"],
    ["Multi-tenancy B2B", "✓", "—", "—", "—"],
    ["Suporte PT-BR", "✓", "—", "—", "parcial"],
]
compare_tbl = Table(compare_data, colWidths=[5.2 * cm, 2.6 * cm, 3.2 * cm,
                                             3.2 * cm, 2.6 * cm])
compare_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
    ("TEXTCOLOR", (0, 0), (-1, 0), white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, 0), 8),
    ("FONTSIZE", (0, 1), (-1, -1), 8),
    ("TEXTCOLOR", (0, 1), (0, -1), FG),
    ("TEXTCOLOR", (1, 1), (1, -1), ACCENT2),
    ("FONTNAME", (1, 1), (1, -1), "Helvetica-Bold"),
    ("TEXTCOLOR", (2, 1), (-1, -1), MUTED),
    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("BACKGROUND", (0, 1), (-1, -1), BG2),
    ("INNERGRID", (0, 0), (-1, -1), 0.2, HexColor("#2A3450")),
    ("BOX", (0, 0), (-1, -1), 0.6, ACCENT),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]))
story.append(compare_tbl)
story.append(Spacer(1, 10))

cta = Table([[
    [
        Paragraph(
            '<font color="#FFFFFF"><b>'
            'Agende uma demo e ganhe 1 curso SCORM completo de presente.'
            '</b></font>',
            s_cta_h,
        ),
        Paragraph(
            '<font color="#E8EDF8">30 minutos com nosso time — mostramos a plataforma '
            'com o <b>SEU PDF</b> e entregamos o curso gerado ao fim da chamada.</font>',
            s_cta_b,
        ),
        Paragraph(
            '<font color="#FFFFFF" size="11"><b>comercial@scormify.com.br</b></font>',
            ParagraphStyle(name="cta3", fontSize=11, leading=13, alignment=TA_CENTER),
        ),
    ]
]], colWidths=[17.8 * cm])
cta.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 12),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ("LEFTPADDING", (0, 0), (-1, -1), 16),
    ("RIGHTPADDING", (0, 0), (-1, -1), 16),
]))
story.append(cta)


class OnePagerDoc(BaseDocTemplate):
    def __init__(self, *args, **kw):
        BaseDocTemplate.__init__(self, *args, **kw)
        frame = Frame(1.4 * cm, 1.4 * cm,
                     PAGE_W - 2.8 * cm, PAGE_H - 2.8 * cm,
                     leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
                     id="main")
        self.addPageTemplates([
            PageTemplate(id="onepager", frames=frame, onPage=draw_background),
        ])


doc = OnePagerDoc(OUT, pagesize=A4)
doc.build(story)
print(f"One-pager: {OUT}")
print(f"Size: {os.path.getsize(OUT):,} bytes")
