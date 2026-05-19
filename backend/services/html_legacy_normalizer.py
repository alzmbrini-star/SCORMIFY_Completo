"""Legacy HTML normalization helper.

Converts HTML4-style `<font color/face/size>` wrappers into modern inline
CSS so downstream WCAG analyzers, the Aesthetic Analyzer, and the
SCORM/HTML exporters can reason about a single style representation.

Used by:
  - `routes/admin_migrations.py` for one-shot DB backfills
  - The frontend `RichTextEditor` also does the same conversion in JS so
    new edits stay clean.
"""
from __future__ import annotations

import re
from typing import Optional
from bs4 import BeautifulSoup


# HTML4 `size` attribute (1..7) → roughly equivalent px values.
_SIZE_MAP = {
    "1": "10px",
    "2": "13px",
    "3": "16px",
    "4": "18px",
    "5": "24px",
    "6": "32px",
    "7": "48px",
}


def has_legacy_font(html: Optional[str]) -> bool:
    if not html:
        return False
    return bool(re.search(r"<font[\s>]", html, re.IGNORECASE))


def normalize_legacy_html(html: Optional[str]) -> str:
    """Return `html` with every `<font>` element replaced by `<span style=…>`.

    Preserves text children, nested tags, and any attributes other than
    color/face/size (those are folded into the span style). Idempotent —
    a second call on already-clean HTML is a no-op.
    """
    if not html:
        return ""
    if not has_legacy_font(html):
        return html

    soup = BeautifulSoup(html, "html.parser")
    for font_tag in soup.find_all("font"):
        decls = []
        color = font_tag.get("color")
        face = font_tag.get("face")
        size = font_tag.get("size")
        if color:
            decls.append(f"color:{str(color).strip()}")
        if face:
            decls.append(f"font-family:{str(face).strip()}")
        if size and str(size).strip() in _SIZE_MAP:
            decls.append(f"font-size:{_SIZE_MAP[str(size).strip()]}")

        new_tag = soup.new_tag("span")
        if decls:
            new_tag["style"] = ";".join(decls)
        # Move children into the span (preserves structure)
        for child in list(font_tag.children):
            new_tag.append(child.extract())
        font_tag.replace_with(new_tag)

    return str(soup)
