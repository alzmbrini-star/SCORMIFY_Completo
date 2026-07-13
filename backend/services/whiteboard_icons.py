"""Line-art icon catalog for the Whiteboard AI renderer.

Backed by the lucide-static SVG set (1995 stroke-based icons, ISC
license) shipped offline at assets/whiteboard/icons/. Each icon is a
24x24 viewBox of pure strokes — ideal for the "pen traces the drawing"
whiteboard animation: we sample every subpath into polylines and the
renderer draws them stroke by stroke.

Public API:
  resolve_icon_name(raw)          → canonical catalog name or None
  icon_strokes(name, cx, cy, size) → list[list[(x, y)]] canvas-space
"""
from __future__ import annotations

import difflib
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "whiteboard" / "icons"

# Common EN/PT-BR concept → catalog name. Keeps the LLM (and authors)
# from having to know lucide's exact naming.
ALIASES = {
    "tree": "tree-deciduous", "arvore": "tree-deciduous", "árvore": "tree-deciduous",
    "pinheiro": "tree-pine", "pine": "tree-pine", "floresta": "trees", "forest": "trees",
    "chair": "armchair", "cadeira": "armchair", "poltrona": "armchair",
    "person": "user", "pessoa": "user", "people": "users", "pessoas": "users",
    "casa": "house", "home": "house", "predio": "building", "prédio": "building",
    "carro": "car", "caminhao": "truck", "caminhão": "truck",
    "aviao": "plane", "avião": "plane", "foguete": "rocket", "barco": "sailboat",
    "bicicleta": "bike", "moto": "bike",
    "computador": "laptop", "computer": "laptop", "notebook": "laptop",
    "celular": "smartphone", "telefone": "phone", "monitor": "monitor",
    "ideia": "lightbulb", "idea": "lightbulb", "lampada": "lightbulb", "lâmpada": "lightbulb",
    "livro": "book-open", "book": "book-open", "caderno": "notebook-pen",
    "formatura": "graduation-cap", "diploma": "graduation-cap",
    "dinheiro": "banknote", "money": "banknote", "moedas": "coins", "moeda": "coins",
    "grafico": "chart-column", "gráfico": "chart-column", "chart": "chart-column",
    "crescimento": "trending-up", "queda": "trending-down",
    "alvo": "target", "meta": "target", "trofeu": "trophy", "troféu": "trophy",
    "medalha": "medal", "premio": "award", "prêmio": "award",
    "escudo": "shield", "seguranca": "shield", "segurança": "shield",
    "cerebro": "brain", "cérebro": "brain", "coracao": "heart", "coração": "heart",
    "engrenagem": "settings", "gear": "settings", "ferramenta": "wrench",
    "martelo": "hammer", "chave": "key", "cadeado": "lock",
    "email": "mail", "e-mail": "mail", "carta": "mail",
    "relogio": "clock", "relógio": "clock", "calendario": "calendar", "calendário": "calendar",
    "camera": "camera", "câmera": "camera", "musica": "music", "música": "music",
    "estrela": "star", "sol": "sun", "lua": "moon", "nuvem": "cloud",
    "chuva": "cloud-rain", "guarda-chuva": "umbrella",
    "folha": "leaf", "flor": "flower", "planta": "sprout",
    "maca": "apple", "maçã": "apple", "cafe": "coffee", "café": "coffee",
    "comida": "utensils", "pizza": "pizza",
    "carrinho": "shopping-cart", "compras": "shopping-cart", "presente": "gift",
    "mapa": "map", "localizacao": "map-pin", "localização": "map-pin",
    "mundo": "globe", "globo": "globe", "bandeira": "flag", "sino": "bell",
    "busca": "search", "lupa": "search", "curtir": "thumbs-up", "like": "thumbs-up",
    "sorriso": "smile", "olho": "eye", "mao": "hand", "mão": "hand",
    "cachorro": "dog", "gato": "cat", "passaro": "bird", "pássaro": "bird",
    "peixe": "fish", "medico": "stethoscope", "médico": "stethoscope",
    "hospital": "hospital", "remedio": "pill", "remédio": "pill",
    "professor": "graduation-cap", "aluno": "user", "equipe": "users",
    "microfone": "mic", "fone": "headphones", "video": "video", "vídeo": "video",
    "documento": "file-text", "pasta": "folder", "impressora": "printer",
    "maleta": "briefcase", "trabalho": "briefcase",
    "handshake": "handshake", "aperto-de-mao": "handshake", "acordo": "handshake",
}


@lru_cache(maxsize=1)
def list_icon_names() -> tuple:
    if not ICONS_DIR.exists():
        return ()
    return tuple(sorted(p.stem for p in ICONS_DIR.glob("*.svg")))


def resolve_icon_name(raw) -> str | None:
    """Map a (possibly loose) name to a catalog icon: exact → alias →
    prefix/word containment → fuzzy. None when nothing plausible."""
    n = str(raw or "").strip().lower().replace(" ", "-").replace("_", "-")
    if not n:
        return None
    names = list_icon_names()
    if not names:
        return None
    name_set = set(names)
    if n in name_set:
        return n
    if n in ALIASES and ALIASES[n] in name_set:
        return ALIASES[n]
    # word/prefix containment: "tree" → shortest of tree-*
    cands = [x for x in names if n in x.split("-") or x.startswith(n + "-")]
    if cands:
        return sorted(cands, key=len)[0]
    m = difflib.get_close_matches(n, names, n=1, cutoff=0.75)
    if m:
        return m[0]
    logger.warning("whiteboard-icons: no catalog match for %r", raw)
    return None


@lru_cache(maxsize=256)
def _unit_strokes(name: str) -> tuple:
    """Sampled subpath polylines in the icon's native 0..24 space."""
    from svgelements import SVG, Path as SvgPath, Shape, Move

    f = ICONS_DIR / f"{name}.svg"
    if not f.exists():
        return ()
    strokes: list[list[tuple[float, float]]] = []
    svg = SVG.parse(str(f))
    for element in svg.elements():
        if not isinstance(element, Shape):
            continue
        try:
            path = element if isinstance(element, SvgPath) else SvgPath(element)
        except Exception:
            continue
        cur: list[tuple[float, float]] = []
        for seg in path:
            if isinstance(seg, Move):
                if len(cur) >= 2:
                    strokes.append(cur)
                cur = [(seg.end.real, seg.end.imag)] if seg.end is not None else []
                continue
            try:
                slen = seg.length(error=1e-3)
            except Exception:
                slen = 1.0
            # ~1 point per 0.35 unit → smooth at typical 200-400px sizes.
            n = max(2, min(72, int(slen / 0.35)))
            for i in range(1, n + 1):
                p = seg.point(i / n)
                cur.append((p.real, p.imag))
        if len(cur) >= 2:
            strokes.append(cur)
    return tuple(tuple(s) for s in strokes)


def icon_strokes(name: str, cx: float, cy: float, size: float) -> list:
    """Catalog icon scaled to a size×size box centered at (cx, cy).
    `name` is resolved (alias/fuzzy) so loose names work even when the
    plan skipped normalization (e.g. direct render of a saved plan)."""
    resolved = name if (ICONS_DIR / f"{name}.svg").exists() else resolve_icon_name(name)
    if not resolved:
        return []
    unit = _unit_strokes(resolved)
    s = size / 24.0
    ox, oy = cx - size / 2.0, cy - size / 2.0
    return [[(ox + x * s, oy + y * s) for (x, y) in st] for st in unit]
