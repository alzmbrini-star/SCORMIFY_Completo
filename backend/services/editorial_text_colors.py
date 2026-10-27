"""Validated CSS-only author overrides; keep in sync with editorialTextColors.js."""
import re

STYLE_ID = 'scormify-editorial-text-colors'
BLOCK = re.compile(r'<style\b[^>]*\bid=["\']scormify-editorial-text-colors["\'][^>]*>[\s\S]*?</style>', re.I)
RULES = {
    'text': 'body,body :is(p,span,strong,b,em,div,blockquote,a,label,small,button,input,textarea,td,th,dt,dd,figcaption,summary,code,pre)',
    'title': 'body :is(h1,h2,h3,h4,h5,h6),body :is(h1,h2,h3,h4,h5,h6) *',
    'card': 'body li,body li *',
    'cardBackground': 'body li',
}


def apply_editorial_text_colors(html, colors=None):
    clean = BLOCK.sub('', html)
    colors = colors if isinstance(colors, dict) else {}
    entries = [(key, selector, colors[key]) for key, selector in RULES.items()
               if isinstance(colors.get(key), str) and re.fullmatch(r'#[0-9a-fA-F]{6}', colors[key])]
    if not entries:
        return clean
    attrs = ' '.join(f'data-{key}="{value}"' for key, _, value in entries)
    css = '\n'.join(f'{selector}{{{"background" if key == "cardBackground" else "color"}:{value}!important}}'
                    for key, selector, value in entries)
    block = f'<style id="{STYLE_ID}" {attrs}>{css}</style>'
    return re.sub(r'</head>', lambda _: block + '</head>', clean, count=1, flags=re.I) if re.search(r'</head>', clean, re.I) else clean + block
