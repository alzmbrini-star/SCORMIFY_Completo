"""Read-time HUD presentation upgrade for canonical Editor and Agent games."""
import base64
import re

# Keep this CSS identical to frontend/src/utils/gameHud.js (covered by tests).
GAME_HUD_CSS = """
#playScreen{overflow-y:auto}
.screen .hud{display:grid;grid-template-columns:auto minmax(420px,1fr);gap:24px;align-items:center;height:auto;min-height:100px;flex-shrink:0;padding:8px 0 14px}
.hud .brand{font-size:13px;max-width:200px;line-height:1.4}
.hud .chips{display:grid;grid-template-columns:.85fr 1.2fr 1.3fr .85fr;gap:10px;width:100%;min-width:0}
.hud .chip.hud-metric{display:flex;flex-direction:column;justify-content:center;gap:4px;min-width:0;padding:10px 12px;border-radius:14px;border:1px solid #8195be;background:#142342;color:#f8fbff;box-shadow:0 4px 16px #0004;font-size:14px;line-height:1.1;text-align:left}
.hud .hud-label{font-size:clamp(10px,1vw,13px);font-weight:800;letter-spacing:.04em;white-space:nowrap}
.hud .hud-value{white-space:nowrap;font-size:12px;font-weight:800;font-variant-numeric:tabular-nums}
.hud .hud-value b{font-size:clamp(24px,2.7vw,36px);font-weight:950;line-height:1.05}
.hud .chip.hud-timer{background:#342613;border:2px solid #fbbf24;color:#fff4cc}
.hud .chip.hud-xp{background:#08344b;border:2px solid #22d3ee;color:#e0fbff}
.hud .hud-timer .hud-value b,.hud .hud-xp .hud-value b{font-size:clamp(30px,3.2vw,42px)}
@media(max-width:800px){.screen .hud{grid-template-columns:1fr;gap:8px;min-height:124px;padding-bottom:10px}.hud .brand{max-width:none;font-size:11px}.hud .chips{gap:7px}.hud .chip.hud-metric{padding:8px}.hud .hud-label{font-size:10px}.hud .hud-value b{font-size:24px}.hud .hud-timer .hud-value b,.hud .hud-xp .hud-value b{font-size:30px}}
@media(max-width:420px){.hud .chips{grid-template-columns:1fr 1fr}.screen .hud{min-height:190px}.hud .hud-label{font-size:11px}}
"""
METRICS = {'lives': ('❤️ Vidas', ''), 'timer': ('⏱ Tempo', ' s'), 'xp': ('⭐ Pontuação', ' XP'), 'coins': ('🪙 Moedas', '')}


def upgrade_game_hud(html):
    if not isinstance(html, str) or not html or 'scormify-game-hud-v1' in html:
        return html
    if html.startswith('__B64__:'):
        try:
            source = base64.b64decode(html[8:], validate=True).decode('utf-8')
            upgraded = upgrade_game_hud(source)
            return '__B64__:' + base64.b64encode(upgraded.encode()).decode() if upgraded != source else html
        except (ValueError, UnicodeError):
            return html
    if not re.search(r'SCORMIFY\s+(?:GAMES|ADVENTURES)|QuestionEngine', html) or not re.search(r'class=["\'][^"\']*\bhud\b', html):
        return html
    count = 0
    def replace(match):
        nonlocal count
        metric = re.search(r'(<b\b[^>]*\bid=["\'](lives|timer|xp|coins)["\'][^>]*>[\s\S]*?</b>)', match[2], re.I)
        if not metric:
            return match[0]
        key = metric[2].lower()
        label, unit = METRICS[key]
        attrs = re.sub(r'(\bclass=["\'])([^"\']*)', lambda m: m[1]+m[2]+' hud-metric hud-'+key, match[1], count=1)
        count += 1
        return f'<span{attrs}><span class="hud-label">{label}</span><span class="hud-value">{metric[1]}{unit}</span></span>'
    upgraded = re.sub(r'<span\b([^>]*\bclass=["\'][^"\']*\bchip\b[^"\']*["\'][^>]*)>([\s\S]*?)</span>', replace, html, flags=re.I)
    if not count:
        return html
    style = '<style id="scormify-game-hud-v1">'+GAME_HUD_CSS+'</style>'
    return re.sub(r'</head>', lambda _: style+'</head>', upgraded, count=1, flags=re.I) if re.search(r'</head>', upgraded, re.I) else upgraded+style


def refresh_game_huds(project):
    if project:
        for slide in (project.get('course') or {}).get('slides', []):
            for element in slide.get('elements', []):
                if element.get('type') == 'html' and isinstance(element.get('htmlContent'), str):
                    element['htmlContent'] = upgrade_game_hud(element['htmlContent'])
    return project
