"""PowerPoint shape flips must not mirror their independently laid-out text.

Keep shape geometry and the vendor player's animation transforms untouched.
Counter only the explicit per-shape flip on the direct text layout. Individual
CSS scale composes with, rather than overwrites, existing text transforms.
"""

TEXT_FLIP_CSS = '''<style id="sk-readable-text-flips-v1">
.shp[style*="scaleX(-1)"]>.txt-l{scale:-1 1!important}
.shp[style*="scaleY(-1)"]>.txt-l{scale:1 -1!important}
.shp[style*="scaleX(-1)"][style*="scaleY(-1)"]>.txt-l{scale:-1 -1!important}
</style>'''
