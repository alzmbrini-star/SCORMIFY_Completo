"""Validated presentation-only image shadow for server-rendered flow exports."""
import math
import re


def image_shadow_style(shadow):
    if not isinstance(shadow, dict):
        return {}
    presets = {'soft': (16, 6, 18), 'medium': (24, 10, 28), 'strong': (32, 14, 40)}
    preset = shadow.get('preset')
    if preset not in (*presets, 'custom'):
        return {'filter': 'none', 'boxShadow': 'none'}
    defaults = presets.get(preset, presets['soft'])

    def number(value, fallback, low, high):
        return min(high, max(low, value)) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else fallback

    blur = number(shadow.get('blur'), defaults[0], 0, 60)
    x = number(shadow.get('x'), 0, -40, 40)
    y = number(shadow.get('y'), defaults[1], -40, 40)
    opacity = number(shadow.get('opacity'), defaults[2], 0, 70) / 100
    color = shadow.get('color')
    if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        color = '#000000'
    rgb = ','.join(str(int(color[i:i+2], 16)) for i in (1, 3, 5))
    css = f'{x:g}px {y:g}px {blur:g}px rgba({rgb},{opacity:g})'
    return {'boxShadow': css, 'filter': 'none'} if shadow.get('mode') == 'frame' else {'filter': f'drop-shadow({css})', 'boxShadow': 'none'}


def image_shadow_css(shadow):
    return ''.join(f'{"box-shadow" if key == "boxShadow" else key}:{value} !important;' for key, value in image_shadow_style(shadow).items())
