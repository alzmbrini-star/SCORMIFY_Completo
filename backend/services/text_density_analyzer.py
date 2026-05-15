"""Text Density Analyzer — deterministic first-pass that scores how
text-heavy a slide / storyboard section is. Designed to run on every slide
in milliseconds without LLM cost so the UI can light up badges immediately.

The LLM-based suggestion generator (`density_suggester.py`) only runs on
slides flagged as `heavy` or `medium`, keeping cost predictable.

Scoring model (empirical, tuned against ~50 sample slides from real courses):
  - words: every 30 words beyond 20 adds 8 points (max +40)
  - sentences: every sentence beyond 4 adds 5 points (max +20)
  - bullets: every bullet beyond 5 adds 4 points (max +16)
  - paragraphs without breaks: +12 if any single block > 240 chars
  - no visual: +12 if there's no image element
  - long-block penalty: +8 if avg sentence length > 22 words

Labels:
  - score <  35  → "light"     (zero badge)
  - score 35-65  → "medium"    (info badge — improvement opcional)
  - score >  65  → "heavy"     (warning badge — agente sugere ativamente)
"""
from typing import Dict, List, Optional
import re


def _count_words(text: str) -> int:
    if not text:
        return 0
    return len(re.findall(r"\b[\wÀ-ÿ]+\b", text, flags=re.UNICODE))


def _count_sentences(text: str) -> int:
    if not text:
        return 0
    # Split on sentence terminators followed by space or EOL
    parts = re.split(r"[.!?]+(?:\s|$)", text.strip())
    return sum(1 for p in parts if p.strip())


def _longest_block_length(text: str) -> int:
    """Longest contiguous text block (no double-newline break)."""
    if not text:
        return 0
    blocks = re.split(r"\n\s*\n", text)
    return max((len(b) for b in blocks), default=0)


def analyze_text_density(
    text: str = "",
    bullets: Optional[List[str]] = None,
    has_image: bool = False,
    title: str = "",
) -> Dict:
    """Score a slide / section's text density.

    Args:
        text: free-form body text (excludes title).
        bullets: list of bullet point strings.
        has_image: True when the slide already has any image/video/avatar.
        title: slide title (counted lightly — long titles ARE a density signal).

    Returns:
        {
          "score": int,                    # 0..100
          "label": "light"|"medium"|"heavy",
          "reasons": [str, ...],           # human-readable diagnostics
          "metrics": {                     # raw measurements for the UI
              "words": int,
              "sentences": int,
              "bullets": int,
              "longestBlock": int,
              "hasImage": bool,
          },
        }
    """
    bullets = bullets or []
    bullet_text = "\n".join(bullets)

    # Aggregate text for word/sentence counting. Title contributes lightly.
    full_text = " ".join(filter(None, [text or "", bullet_text]))
    title_words = _count_words(title)
    words = _count_words(full_text)
    sentences = _count_sentences(full_text or title)
    longest_block = _longest_block_length(text or "")

    score = 0
    reasons: List[str] = []

    # --- Words ---
    if words > 20:
        word_pts = min(40, ((words - 20) // 30) * 8)
        score += word_pts
        if word_pts > 0:
            reasons.append(f"{words} palavras no corpo do slide")

    # --- Sentences ---
    if sentences > 4:
        sent_pts = min(20, (sentences - 4) * 5)
        score += sent_pts
        reasons.append(f"{sentences} frases (recomendado: ≤4)")

    # --- Bullets ---
    if len(bullets) > 5:
        b_pts = min(16, (len(bullets) - 5) * 4)
        score += b_pts
        reasons.append(f"{len(bullets)} bullet points (recomendado: ≤5)")

    # --- Long block ---
    if longest_block > 240:
        score += 12
        reasons.append(f"bloco de {longest_block} caracteres sem quebra")

    # --- No image ---
    if not has_image and words > 30:
        score += 12
        reasons.append("nenhuma imagem ou video acompanhando o texto")

    # --- Avg sentence length ---
    if sentences > 0 and words > 0:
        avg_words = words / sentences
        if avg_words > 22:
            score += 8
            reasons.append(f"frases longas (media: {avg_words:.0f} palavras)")

    # Long title (sometimes a paragraph crammed into a heading)
    if title_words > 14:
        score += 6
        reasons.append("titulo muito longo")

    score = min(100, score)
    label = "light" if score < 35 else ("medium" if score <= 65 else "heavy")

    return {
        "score": score,
        "label": label,
        "reasons": reasons,
        "metrics": {
            "words": words,
            "sentences": sentences,
            "bullets": len(bullets),
            "longestBlock": longest_block,
            "hasImage": has_image,
        },
    }


def analyze_slide(slide: Dict) -> Dict:
    """Convenience wrapper that pulls text/bullets/has_image out of a
    Scormify slide dict and runs the analyzer."""
    elements = slide.get("elements") or []
    text_parts: List[str] = []
    bullets: List[str] = []
    has_image = False
    for el in elements:
        etype = (el.get("type") or "").lower()
        # Skip the brand watermark logo — it's chrome, not content
        if el.get("isBrandLogo"):
            continue
        if etype == "text":
            content = el.get("content") or el.get("text") or ""
            # Treat lines starting with • / - / * as bullets
            lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
            detected_bullets = [ln.lstrip("•-* ").strip() for ln in lines if ln.startswith(("•", "-", "*"))]
            if detected_bullets:
                bullets.extend(detected_bullets)
            # Non-bullet lines go into the prose blob
            non_bullets = [ln for ln in lines if not ln.startswith(("•", "-", "*"))]
            if non_bullets:
                text_parts.append(" ".join(non_bullets))
        elif etype in ("image", "video", "avatar", "iframe", "flipbook"):
            has_image = True
    # Slide-level background image counts as a visual too
    if slide.get("backgroundImage"):
        has_image = True
    return analyze_text_density(
        text=" ".join(text_parts),
        bullets=bullets,
        has_image=has_image,
        title=slide.get("title") or "",
    )


def analyze_storyboard_section(section: Dict) -> Dict:
    """Score a storyboard section. Storyboard format is looser than slide:
    the body text is in `body` / `description` / `content`."""
    body = (
        section.get("body")
        or section.get("description")
        or section.get("content")
        or ""
    )
    raw_bullets = section.get("bullets") or section.get("keyPoints") or []
    # Normalize to strings
    bullets: List[str] = []
    for b in raw_bullets:
        if isinstance(b, dict):
            bullets.append(b.get("text") or b.get("title") or "")
        else:
            bullets.append(str(b))
    bullets = [b.strip() for b in bullets if b and b.strip()]
    return analyze_text_density(
        text=body,
        bullets=bullets,
        has_image=False,  # storyboard sections don't yet have visuals
        title=section.get("title") or section.get("sectionTitle") or "",
    )
