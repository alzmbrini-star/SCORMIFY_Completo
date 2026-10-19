"""Bounded editorial layouts; never rewrite interactive or arbitrary user HTML."""
from html import escape
from html.parser import HTMLParser


def content_boxes(layout):
    # All coordinates use the Agent's 1920 x 820 slide canvas.
    if layout == 'guided_observation':
        return ({'x': 1190, 'y': 110, 'width': 610, 'height': 640},
                {'x': 120, 'y': 110, 'width': 1010, 'height': 640})
    if layout == 'decision_split':
        return ({'x': 980, 'y': 110, 'width': 820, 'height': 640},
                {'x': 120, 'y': 110, 'width': 800, 'height': 640})
    if layout == 'workbench':
        return ({'x': 120, 'y': 110, 'width': 760, 'height': 640},
                {'x': 940, 'y': 110, 'width': 860, 'height': 640})
    if layout == 'reflection':
        return ({'x': 120, 'y': 110, 'width': 960, 'height': 640},
                {'x': 1140, 'y': 110, 'width': 660, 'height': 640})
    return ({'x': 120, 'y': 110, 'width': 760, 'height': 640},
            {'x': 940, 'y': 110, 'width': 860, 'height': 640})


class _CopyParser(HTMLParser):
    """Editorial copy is semantic content, not a second slide-layout engine."""
    def __init__(self, tokens, summary):
        super().__init__(convert_charrefs=True)
        self.parts, self.suppressed = [], 0
        text, muted = tokens['text'], tokens['muted']
        self.styles = {
            'h1': f'font-size:36px;line-height:1.2;margin:0 0 20px;color:{text}',
            'h2': f'font-size:30px;line-height:1.25;margin:0 0 18px;color:{text}',
            'h3': f'font-size:24px;line-height:1.3;margin:0 0 14px;color:{text}',
            'p': f'font-size:21px;line-height:1.55;margin:0 0 16px;color:{muted}',
            'ul': 'padding:0 0 0 26px;margin:12px 0',
            'ol': 'padding:0 0 0 30px;margin:12px 0',
            'li': f'font-size:20px;line-height:1.5;margin:0 0 12px;color:{muted}',
            'strong': f'font-weight:700;color:{text}',
            'b': f'font-weight:700;color:{text}',
            'div': 'min-width:0;max-width:100%',
            'span': '', 'em': '', 'i': '', 'br': '',
            'table': 'width:100%;border-collapse:collapse;table-layout:fixed',
            'thead': '', 'tbody': '', 'tr': '',
            'th': f'padding:10px;text-align:left;color:{text}',
            'td': f'padding:10px;text-align:left;color:{muted}',
        }
        if summary:
            self.styles['ul'] = 'list-style:none;padding:0;margin:18px 0'
            self.styles['li'] += (f';padding:16px 22px;background:{tokens["card_bg"]}'
                f';border:1px solid {tokens["card_border"]};border-left:3px solid {tokens["accent"]};border-radius:12px')
        for tag in ('h1', 'h2', 'h3'):
            self.styles[tag] += ';font-family:' + tokens['heading']
        for tag in ('p', 'li'):
            self.styles[tag] += ';font-family:' + tokens['body']

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.suppressed += 1
        if self.suppressed or tag not in self.styles:
            return
        style = escape(self.styles[tag], quote=True).replace('&#x27;', "'")
        self.parts.append(f'<{tag} style="{style}">')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.suppressed = max(0, self.suppressed - 1)
            return
        if not self.suppressed and tag in self.styles and tag != 'br':
            self.parts.append(f'</{tag}>')

    def handle_data(self, data):
        if not self.suppressed:
            self.parts.append(escape(data))


def style_editorial_copy(raw, tokens, summary=False):
    parser = _CopyParser(tokens, summary)
    parser.feed(raw or '')
    parser.close()
    body_font = escape(tokens['body'], quote=True).replace('&#x27;', "'")
    return ('<div data-agent-copy-version="2" style="box-sizing:border-box;width:100%;height:100%;'
        'overflow:auto;overscroll-behavior:contain;overflow-wrap:anywhere;min-width:0;'
        f'padding:6px 12px 6px 0;font-family:{body_font};color:{tokens["text"]};">'
        + ''.join(parser.parts) + '</div>')


def repair_legacy_agent_project(project):
    """In-memory compatibility repair for recognizable, unchanged Agent builders.

    No database write, no arbitrary user HTML, simulators, games or assessments.
    """
    if not project or not (project.get('createdByAgent') or project.get('agentSessionId')):
        return project
    from services.ai_agent import _tokens
    for slide in (project.get('course') or {}).get('slides', []):
        if slide.get('contentType') not in ('content', 'summary'):
            continue
        bg = str(slide.get('background', '#ffffff'))
        try:
            value = bg.lstrip('#')
            if len(value) == 3:
                value = ''.join(c*2 for c in value)
            rgb = [int(value[i:i+2], 16)/255 for i in (0,2,4)]
            linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb]
            dark = sum(v*w for v,w in zip(linear, (.2126,.7152,.0722))) < .18
        except (ValueError, IndexError):
            continue
        tokens = _tokens({'accent': '#34d399' if dark else '#1d4ed8',
                          'mode': 'dark' if dark else 'light',
                          'text': '#f4f4f5' if dark else '#1c1917'})
        elements = slide.get('elements', [])
        for element in elements:
            html = element.get('htmlContent') or ''
            if element.get('type') != 'html' or not isinstance(html, str):
                continue
            if html.startswith('<div style="padding:6px 0;font-family:') and 'data-agent-copy-version' not in html:
                element['htmlContent'] = style_editorial_copy(html, tokens, slide['contentType'] == 'summary')
        copies = [e for e in elements if e.get('journeyRole') == 'learning_copy']
        scenes = [e for e in elements if e.get('journeyRole') == 'evidence_scene']
        if len(copies) == len(scenes) == 1:
            copy, scene = copies[0], scenes[0]
            old_pairs = [((120,500,980,250),(120,105,1680,610)),
                         ((1250,145,520,560),(120,105,1050,610)),
                         ((980,125,790,600),(120,125,760,560)),
                         ((120,125,650,590),(850,105,950,620)),
                         ((180,500,1560,220),(360,115,1200,390))]
            bounds = lambda e: tuple(e.get(k) for k in ('x','y','width','height'))
            if (bounds(copy), bounds(scene)) in old_pairs:
                text_box, image_box = content_boxes(slide.get('journeyLayout'))
                copy.update(text_box)
                scene.update(image_box)
    return project
