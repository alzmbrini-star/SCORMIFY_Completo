"""
PDF Extractor with OCR and layout preservation.

Strategy (as specified by product):
  - 1 PDF page = 1 slide (grouped into chapters/modules)
  - Extract embedded images with their positions (bbox)
  - For scanned pages: render the page as an image (2b hybrid)
  - OCR: Tesseract first, Gemini 3 Flash multimodal as fallback (3c)
  - No hard page limit (4c) — caller decides; we log progress
  - Images are preserved intact; OCR'd text stays separate (5a)

Output structure (returned by `extract_pdf`):
{
  "chapters": [
    {
      "title": "Capitulo 1: Introducao",
      "pages": [
        {
          "page_num": 1,
          "text": "<markdown-like text with positional hints>",
          "images": [
            {"filename": "pdf_p1_img1.png", "bbox": [x0,y0,x1,y1], "caption": ""}
          ],
          "is_scanned": false,
          "rendered_image": null  # or filename when page is rendered whole
        }
      ]
    }
  ],
  "total_pages": 42,
  "scanned_pages": 3,
  "images_extracted": 18,
  "asset_filenames": ["pdf_p1_img1.png", ...]  # all filenames saved to assets_dir
}
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Minimum text length per page to consider it "native" (otherwise OCR).
MIN_NATIVE_TEXT_CHARS = 60
# Render DPI for OCR/fallback image.
RENDER_DPI = 180
# Max OCR concurrency (avoid CPU starvation).
OCR_CONCURRENCY = 3


@dataclass
class PdfImage:
    filename: str
    bbox: Tuple[float, float, float, float]
    caption: str = ""


@dataclass
class PdfPage:
    page_num: int
    text: str
    images: List[PdfImage] = field(default_factory=list)
    is_scanned: bool = False
    rendered_image: Optional[str] = None


@dataclass
class PdfChapter:
    title: str
    pages: List[PdfPage] = field(default_factory=list)


def _tesseract_available() -> bool:
    try:
        import pytesseract  # noqa
        return subprocess.run(
            ["tesseract", "--version"],
            capture_output=True, timeout=5
        ).returncode == 0
    except Exception:
        return False


def _extract_text_with_layout(page: fitz.Page) -> str:
    """Extract text preserving paragraph-level ordering.
    Uses PyMuPDF 'blocks' extraction which returns text grouped by visual block
    (paragraphs, headings) in reading order.
    """
    try:
        blocks = page.get_text("blocks")
        # Each block: (x0, y0, x1, y1, "text", block_no, block_type)
        # block_type == 0 means text; 1 means image.
        text_blocks = [b for b in blocks if b[6] == 0 and (b[4] or "").strip()]
        text_blocks.sort(key=lambda b: (round(b[1]), round(b[0])))
        parts = []
        for b in text_blocks:
            t = b[4].strip()
            if t:
                parts.append(t)
        return "\n\n".join(parts)
    except Exception:
        return page.get_text() or ""


def _detect_heading(text: str) -> Optional[str]:
    """Heuristic to identify a chapter heading at the top of a page.
    Returns the heading text if the first line looks like a chapter/section title.
    """
    if not text:
        return None
    first = text.strip().split("\n", 1)[0].strip()
    if not first or len(first) > 120:
        return None
    patterns = [
        r"^(cap[ií]tulo|chapter|m[óo]dulo|module|unidade|unit|se[cç][ãa]o|section|parte|part)\s+[\w\d]+",
        r"^\d{1,2}[\.\)]\s+\S",
        r"^[A-ZÁÂÃÀÉÊÍÓÔÕÚÇ][\wÁÂÃÀÉÊÍÓÔÕÚÇ\s-]{4,80}$",
    ]
    for pat in patterns:
        if re.match(pat, first, re.IGNORECASE):
            return first
    return None


def _extract_embedded_images(
    pdf: fitz.Document,
    page: fitz.Page,
    page_num: int,
    assets_dir: Path,
) -> List[PdfImage]:
    images: List[PdfImage] = []
    try:
        image_list = page.get_images(full=True)
    except Exception:
        return images

    seen_xrefs = set()
    for img_idx, img_info in enumerate(image_list, start=1):
        xref = img_info[0]
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)
        try:
            base = pdf.extract_image(xref)
            img_bytes = base.get("image")
            ext = base.get("ext", "png")
            if not img_bytes:
                continue
            # Filter out tiny images (logos, bullet glyphs, backgrounds)
            if len(img_bytes) < 3_000:
                continue
            # Normalize uncommon formats to PNG
            if ext not in ("png", "jpg", "jpeg", "webp"):
                try:
                    from PIL import Image
                    pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                    buf = io.BytesIO()
                    pil.save(buf, format="PNG")
                    img_bytes = buf.getvalue()
                    ext = "png"
                except Exception:
                    continue
            filename = f"pdf_p{page_num}_img{img_idx}.{ext}"
            target = assets_dir / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "wb") as f:
                f.write(img_bytes)

            # Try to resolve the image bbox on the page (if available)
            bbox = (0.0, 0.0, 0.0, 0.0)
            try:
                rects = page.get_image_rects(xref)
                if rects:
                    r = rects[0]
                    bbox = (float(r.x0), float(r.y0), float(r.x1), float(r.y1))
            except Exception:
                pass

            images.append(PdfImage(filename=filename, bbox=bbox))
        except Exception as e:
            logger.warning(f"[pdf_extractor] embedded image extract failed p{page_num} #{img_idx}: {e}")
    return images


def _render_page_as_image(
    page: fitz.Page,
    page_num: int,
    assets_dir: Path,
    dpi: int = RENDER_DPI,
) -> str:
    """Render the entire page as a PNG (used for scanned pages / OCR input).
    Returns the filename written into assets_dir.
    """
    filename = f"pdf_p{page_num}_full.png"
    try:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        target = assets_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(target))
        return filename
    except Exception as e:
        logger.error(f"[pdf_extractor] render page {page_num} failed: {e}")
        return ""


def _tesseract_ocr(image_path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
        with Image.open(image_path) as img:
            return pytesseract.image_to_string(img, lang="por+eng") or ""
    except Exception as e:
        logger.warning(f"[pdf_extractor] tesseract OCR failed on {image_path.name}: {e}")
        return ""


async def _gemini_ocr(image_path: Path) -> str:
    """Fallback OCR via Gemini 3 Flash multimodal (Emergent LLM key)."""
    try:
        emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not emergent_key:
            return ""
        from emergentintegrations.llm.chat import (
            LlmChat, UserMessage, FileContentWithMimeType,
        )
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"pdf-ocr-{image_path.name}",
            system_message=(
                "Voce e um extrator de texto de imagens (OCR). Transcreva TODO o texto visivel "
                "na imagem preservando quebras de paragrafo e titulos. Ignore artefatos graficos. "
                "Retorne apenas o texto transcrito, sem comentarios adicionais."
            ),
        ).with_model("gemini", "gemini-3-flash-preview")
        mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
        attachment = FileContentWithMimeType(file_path=str(image_path), mime_type=mime)
        msg = UserMessage(
            text="Transcreva o texto desta pagina preservando paragrafos e titulos.",
            file_contents=[attachment],
        )
        response = await chat.send_message(msg)
        if isinstance(response, str):
            return response.strip()
        return str(response).strip()
    except Exception as e:
        logger.warning(f"[pdf_extractor] gemini OCR failed on {image_path.name}: {e}")
        return ""


async def _ocr_page(image_path: Path, tesseract_ok: bool) -> str:
    """Run OCR: Tesseract first, Gemini fallback (strategy 3c)."""
    text = ""
    if tesseract_ok:
        # run blocking tesseract in threadpool
        text = await asyncio.to_thread(_tesseract_ocr, image_path)
    if len(text.strip()) < MIN_NATIVE_TEXT_CHARS:
        gemini_text = await _gemini_ocr(image_path)
        if len(gemini_text.strip()) > len(text.strip()):
            text = gemini_text
    return text.strip()


async def extract_pdf(
    pdf_bytes: bytes,
    assets_dir: Path,
    progress_cb=None,
) -> dict:
    """Main entry point: extract a PDF into a structured course-ready payload.

    Args:
        pdf_bytes: raw PDF file bytes
        assets_dir: directory where images will be saved (must be writable;
                    caller is responsible for persisting them to MongoDB)
        progress_cb: optional callable(progress_float, message) for UI updates

    Returns: dict with keys "chapters", "total_pages", "scanned_pages",
             "images_extracted", "asset_filenames".
    """
    assets_dir = Path(assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)

    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = pdf.page_count
    tesseract_ok = _tesseract_available()

    logger.info(
        f"[pdf_extractor] starting extraction: {total_pages} pages, "
        f"tesseract={'ok' if tesseract_ok else 'missing (gemini fallback)'}"
    )

    pages: List[PdfPage] = []
    scanned_pages_count = 0
    asset_filenames: List[str] = []

    ocr_semaphore = asyncio.Semaphore(OCR_CONCURRENCY)

    async def _process_page(page_idx: int) -> PdfPage:
        nonlocal scanned_pages_count
        page = pdf.load_page(page_idx)
        page_num = page_idx + 1
        text = _extract_text_with_layout(page)
        images = _extract_embedded_images(pdf, page, page_num, assets_dir)
        for img in images:
            asset_filenames.append(img.filename)

        is_scanned = len(text.strip()) < MIN_NATIVE_TEXT_CHARS
        rendered_image: Optional[str] = None

        if is_scanned:
            scanned_pages_count += 1
            rendered_filename = await asyncio.to_thread(
                _render_page_as_image, page, page_num, assets_dir
            )
            if rendered_filename:
                rendered_image = rendered_filename
                asset_filenames.append(rendered_filename)
                rendered_path = assets_dir / rendered_filename
                async with ocr_semaphore:
                    ocr_text = await _ocr_page(rendered_path, tesseract_ok)
                if ocr_text:
                    text = ocr_text

        if progress_cb:
            try:
                progress_cb((page_idx + 1) / total_pages, f"pagina {page_num}/{total_pages}")
            except Exception:
                pass

        return PdfPage(
            page_num=page_num,
            text=text,
            images=images,
            is_scanned=is_scanned,
            rendered_image=rendered_image,
        )

    # Process pages in batches to keep memory bounded on large PDFs.
    batch_size = 6
    for start in range(0, total_pages, batch_size):
        batch = [_process_page(i) for i in range(start, min(start + batch_size, total_pages))]
        results = await asyncio.gather(*batch, return_exceptions=True)
        for r in results:
            if isinstance(r, PdfPage):
                pages.append(r)
            else:
                logger.error(f"[pdf_extractor] page processing error: {r}")

    pages.sort(key=lambda p: p.page_num)
    pdf.close()

    # Group into chapters using heading heuristic.
    chapters: List[PdfChapter] = []
    current = PdfChapter(title="Conteudo")
    for p in pages:
        heading = _detect_heading(p.text)
        if heading and current.pages:
            chapters.append(current)
            current = PdfChapter(title=heading)
        elif heading and not current.pages:
            current.title = heading
        current.pages.append(p)
    if current.pages:
        chapters.append(current)

    result = {
        "chapters": [
            {
                "title": c.title,
                "pages": [
                    {
                        "page_num": pg.page_num,
                        "text": pg.text,
                        "images": [
                            {"filename": im.filename, "bbox": list(im.bbox), "caption": im.caption}
                            for im in pg.images
                        ],
                        "is_scanned": pg.is_scanned,
                        "rendered_image": pg.rendered_image,
                    }
                    for pg in c.pages
                ],
            }
            for c in chapters
        ],
        "total_pages": total_pages,
        "scanned_pages": scanned_pages_count,
        "images_extracted": sum(len(p.images) for p in pages),
        "asset_filenames": asset_filenames,
    }
    logger.info(
        f"[pdf_extractor] done: {total_pages} pages, "
        f"{scanned_pages_count} scanned (OCR), {result['images_extracted']} images extracted, "
        f"{len(chapters)} chapters"
    )
    return result


def payload_to_markdown(extract_result: dict) -> str:
    """Convert the structured extraction into a markdown-ish text for the LLM.

    The markdown embeds image markers like `[IMG:pdf_p3_img1.png]` so the LLM
    knows which images to reference in which slides (and the post-processor
    replaces them with proper <img> elements on the slide).
    """
    lines: List[str] = []
    for chapter in extract_result.get("chapters", []):
        lines.append(f"\n# {chapter.get('title', 'Conteudo')}\n")
        for page in chapter.get("pages", []):
            lines.append(f"\n## Pagina {page.get('page_num')}\n")
            text = (page.get("text") or "").strip()
            if text:
                lines.append(text)
            for img in page.get("images", []):
                fname = img.get("filename")
                if fname:
                    lines.append(f"\n[IMG:{fname}]")
            rendered = page.get("rendered_image")
            if rendered and not page.get("images"):
                lines.append(f"\n[IMG:{rendered}]")
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Post-processing: migrate tmp assets and replace [IMG:filename] markers
# ---------------------------------------------------------------------------
IMG_MARKER_RE = re.compile(r"\[IMG:([^\]]+?)\]")


async def migrate_pdf_assets(db, tmp_project_id: str, real_project_id: str,
                             projects_dir: Path) -> int:
    """Move images from the temporary pdfimport project to the real project.
    - Updates MongoDB: `project_assets.project_id` tmp -> real.
    - Copies physical files from the tmp folder to the real project folder.
    Returns the number of migrated assets.
    """
    projects_dir = Path(projects_dir)
    tmp_dir = projects_dir / tmp_project_id / "assets"
    real_dir = projects_dir / real_project_id / "assets"
    real_dir.mkdir(parents=True, exist_ok=True)

    # 1. MongoDB rename project_id
    try:
        result = await db.project_assets.update_many(
            {"project_id": tmp_project_id},
            {"$set": {"project_id": real_project_id}},
        )
        migrated = result.modified_count if hasattr(result, "modified_count") else 0
    except Exception as e:
        logger.warning(f"[pdf_extractor] MongoDB asset migration failed: {e}")
        migrated = 0

    # 2. Copy physical files
    if tmp_dir.exists():
        for src in tmp_dir.iterdir():
            if src.is_file():
                dst = real_dir / src.name
                try:
                    if not dst.exists():
                        dst.write_bytes(src.read_bytes())
                except Exception as e:
                    logger.warning(f"[pdf_extractor] copy {src.name} failed: {e}")
        # Clean up tmp folder
        try:
            import shutil as _sh
            _sh.rmtree(tmp_dir.parent, ignore_errors=True)
        except Exception:
            pass

    logger.info(f"[pdf_extractor] migrated {migrated} PDF assets to project {real_project_id}")
    return migrated


def _build_image_element(project_id: str, filename: str,
                         x: int = 1160, y: int = 90,
                         width: int = 700, height: int = 440) -> dict:
    """Build a Scormify image element referencing a project asset."""
    try:
        from models import generate_id
        elem_id = generate_id()
    except Exception:
        import uuid as _uuid
        elem_id = _uuid.uuid4().hex
    url = f"/api/projects/{project_id}/assets/{filename}"
    return {
        "id": elem_id,
        "type": "image",
        "x": x, "y": y, "width": width, "height": height,
        "src": url, "content": url,
        "style": {"borderRadius": "10px"},
        "startTime": 0,
    }


def _is_content_slide(slide: dict) -> bool:
    """Slides that accept an illustrative image (skip title/quiz/scenario/summary
    and skip the gallery slides we create ourselves so they don't get reused)."""
    t = (slide.get("type") or "content").lower()
    if t not in ("content", "image", "html", "default", ""):
        return False
    if slide.get("_pdfGallery"):
        return False
    return True


def _insert_image_on_slide(slide: dict, project_id: str, fname: str, caption: str,
                           slot_idx: int = 0) -> None:
    """Insert an extracted image + optional caption into a slide."""
    existing_srcs = {
        (el.get("src") or "") for el in slide.get("elements", [])
        if el.get("type") == "image"
    }
    url = f"/api/projects/{project_id}/assets/{fname}"
    if url in existing_srcs:
        return
    if slot_idx == 0:
        img_el = _build_image_element(project_id, fname,
                                      x=1160, y=90, width=700, height=440)
        # Rebalance text columns if needed
        for el in slide.get("elements", []):
            if el.get("type") in ("html", "text") and el.get("width", 0) > 1200:
                el["width"] = 1050
                el["x"] = 60
    else:
        img_el = _build_image_element(project_id, fname,
                                      x=1160, y=560, width=700, height=300)
    slide.setdefault("elements", []).append(img_el)

    if caption:
        try:
            from models import generate_id
            cap_id = generate_id()
        except Exception:
            import uuid as _uuid
            cap_id = _uuid.uuid4().hex
        slide["elements"].append({
            "id": cap_id,
            "type": "html",
            "x": img_el["x"], "y": img_el["y"] + img_el["height"] + 8,
            "width": img_el["width"], "height": 40,
            "content": f"<p style='font-size:12px;color:#cbd5e1;font-style:italic;margin:0;text-align:center'>{caption}</p>",
            "style": {},
            "startTime": 0,
        })


def _page_num_from_filename(fname: str) -> Optional[int]:
    """Extract page number from `pdf_pN_imgM.ext` or `pdf_pN_full.png`."""
    m = re.match(r"pdf_p(\d+)_", fname)
    return int(m.group(1)) if m else None


def _make_gallery_slide(project_id: str, page_num: int, filenames: list,
                        captions_map: dict, design_ref: Optional[dict] = None) -> dict:
    """Build a new slide containing a grid of 2-4 PDF images from the same page.
    Used when a page has more images than the anchor slide can hold, so the
    sequence is preserved by inserting overflow slides.
    """
    try:
        from models import generate_id
        sid = generate_id()
    except Exception:
        import uuid as _uuid
        sid = _uuid.uuid4().hex

    count = len(filenames)
    # Layout: 1 → full; 2 → side by side; 3-4 → 2×2 grid
    elements: list = []
    try:
        from models import generate_id as _gid
    except Exception:
        import uuid as _uuid_mod
        def _gid():
            return _uuid_mod.uuid4().hex

    # Title element
    elements.append({
        "id": _gid(),
        "type": "html",
        "x": 60, "y": 40, "width": 1800, "height": 60,
        "content": f"<h2 style='color:#fff;font-size:30px;margin:0;font-weight:700'>Ilustracoes da pagina {page_num}</h2>",
        "style": {}, "startTime": 0,
    })

    positions = {
        1: [(160, 140, 1600, 800)],
        2: [(100, 160, 850, 760), (970, 160, 850, 760)],
        3: [(100, 140, 850, 420), (970, 140, 850, 420), (540, 580, 840, 360)],
        4: [(100, 140, 850, 400), (970, 140, 850, 400),
            (100, 560, 850, 400), (970, 560, 850, 400)],
    }
    layout = positions.get(min(count, 4), positions[4])[:count]

    for (x, y, w, h), fname in zip(layout, filenames):
        url = f"/api/projects/{project_id}/assets/{fname}"
        elements.append({
            "id": _gid(),
            "type": "image",
            "x": x, "y": y, "width": w, "height": h,
            "src": url, "content": url,
            "style": {"borderRadius": "12px", "objectFit": "contain"},
            "startTime": 0,
        })
        cap = captions_map.get(fname, "").strip()
        if cap:
            elements.append({
                "id": _gid(),
                "type": "html",
                "x": x, "y": y + h + 4, "width": w, "height": 32,
                "content": f"<p style='font-size:12px;color:#cbd5e1;font-style:italic;margin:0;text-align:center'>{cap}</p>",
                "style": {}, "startTime": 0,
            })

    bg = {}
    if design_ref:
        bg = design_ref.get("background") or {}
    return {
        "id": sid,
        "type": "content",
        "title": f"Ilustracoes da pagina {page_num}",
        "elements": elements,
        "background": bg,
        "notes": f"Galeria automatica da pagina {page_num} do PDF original.",
        "_pdfGallery": True,
    }


def replace_img_markers_in_slides(slides: list, project_id: str,
                                  available_filenames: set,
                                  image_prefs: Optional[dict] = None,
                                  total_pdf_pages: Optional[int] = None) -> int:
    """Place PDF-extracted images into slides in the correct sequence.

    Strategy:
      1. Primary: honor `[IMG:filename]` markers the LLM kept.
      2. For each page, place its first 2 images on the mapped content slide
         (next to the relevant text).
      3. If a page has MORE images than fit on the mapped slide, insert extra
         "Ilustracoes da pagina N" gallery slides RIGHT AFTER the anchor,
         keeping 2-4 images per overflow slide. This preserves the PDF ->
         course sequence even for image-dense manuals.
      4. `total_pdf_pages` must be passed by the caller so the page -> slide
         proportional mapping is accurate even when not every page has images.
    """
    image_prefs = image_prefs or {}
    total = 0
    placed_filenames: set = set()

    # ── Primary path: markers left by the LLM ───────────────────────────
    for slide in slides:
        used_here: set = set()
        for el in slide.get("elements", []):
            for field_name in ("content", "htmlContent", "text"):
                val = el.get(field_name)
                if not isinstance(val, str) or "[IMG:" not in val:
                    continue
                for fname in IMG_MARKER_RE.findall(val):
                    if (fname in available_filenames
                            and image_prefs.get(fname, {}).get("included", True)):
                        used_here.add(fname)
                el[field_name] = IMG_MARKER_RE.sub("", val).strip()

        for slot_idx, fname in enumerate(list(used_here)[:2]):
            caption = image_prefs.get(fname, {}).get("caption", "").strip()
            _insert_image_on_slide(slide, project_id, fname, caption, slot_idx)
            placed_filenames.add(fname)
            total += 1

    # ── Fallback path: sequential page-by-page placement ────────────────
    remaining = [
        f for f in available_filenames
        if f not in placed_filenames
        and image_prefs.get(f, {}).get("included", True)
    ]
    if not remaining:
        return total

    # Group remaining images by source page
    by_page: dict = {}
    for fname in remaining:
        p = _page_num_from_filename(fname) or 1
        by_page.setdefault(p, []).append(fname)
    for p in by_page:
        by_page[p].sort()  # stable order within a page

    content_slide_indices = [i for i, s in enumerate(slides) if _is_content_slide(s)]
    if not content_slide_indices:
        logger.warning(
            f"[pdf_extractor] {len(remaining)} images could not be placed: "
            f"no content slides"
        )
        return total

    N = len(content_slide_indices)
    page_nums = [p for p in (_page_num_from_filename(f) for f in available_filenames) if p]
    max_page = total_pdf_pages or (max(page_nums) if page_nums else 1)
    max_page = max(max_page, 1)

    captions_map = {
        f: (image_prefs.get(f, {}).get("caption", "") or "")
        for f in remaining
    }

    # Reference design (background) to keep gallery slides consistent
    design_ref = slides[0] if slides else None

    # Walk pages in order, inserting gallery slides as needed. We process in
    # reverse order so inserting a gallery doesn't shift the anchor indices
    # of pages we haven't processed yet.
    sorted_pages = sorted(by_page.keys(), reverse=True)

    for page in sorted_pages:
        imgs = by_page[page]
        slot = min(((page - 1) * N) // max_page, N - 1)
        anchor_slide_idx = content_slide_indices[slot]
        anchor_slide = slides[anchor_slide_idx]
        current_imgs_on_anchor = sum(
            1 for el in anchor_slide.get("elements", [])
            if el.get("type") == "image"
        )
        capacity = max(0, 2 - current_imgs_on_anchor)

        # Fill anchor with up to `capacity` images
        first_batch = imgs[:capacity]
        overflow = imgs[capacity:]

        for idx, fname in enumerate(first_batch):
            cap = captions_map.get(fname, "").strip()
            _insert_image_on_slide(
                anchor_slide, project_id, fname, cap,
                slot_idx=current_imgs_on_anchor + idx,
            )
            total += 1

        # For overflow images, create gallery slides right after the anchor
        # (chunks of up to 4 images each).
        if overflow:
            chunk_size = 4
            chunks = [overflow[i:i + chunk_size]
                      for i in range(0, len(overflow), chunk_size)]
            insert_at = anchor_slide_idx + 1
            for chunk in chunks:
                gallery = _make_gallery_slide(
                    project_id, page, chunk, captions_map, design_ref=design_ref
                )
                slides.insert(insert_at, gallery)
                total += len(chunk)
                insert_at += 1

            # Rebuild content_slide_indices after insertion so future pages
            # (processed in reverse order so they are earlier in the list) map
            # correctly. But because we process in reverse, inserting AFTER
            # the current anchor does not affect earlier-page indices.
            content_slide_indices = [i for i, s in enumerate(slides) if _is_content_slide(s)]
            N = len(content_slide_indices)

    logger.info(
        f"[pdf_extractor] placed {total} images ({len(remaining)} via fallback) "
        f"across {max_page} pdf pages"
    )
    return total


# ---------------------------------------------------------------------------
# Faithful mode: 1 PDF page -> 1 slide (page rendered as full background)
# ---------------------------------------------------------------------------
SLIDE_WIDTH = 1920
SLIDE_HEIGHT = 820
FAITHFUL_DPI = 200


async def extract_pdf_faithful(pdf_bytes: bytes, assets_dir: Path,
                               progress_cb=None) -> dict:
    """Render each PDF page as a single 1920x820 background image so the
    course slide preserves the page's original layout, images, colors, logos
    and fonts verbatim.

    Returns:
        {
          "pages": [
            {"page_num": 1, "filename": "pdf_page_1.jpg", "text": "..."},
            ...
          ],
          "total_pages": N,
        }
    """
    assets_dir = Path(assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)
    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    tesseract_ok = _tesseract_available()
    total_pages = pdf.page_count
    logger.info(
        f"[pdf_extractor/faithful] rendering {total_pages} pages at "
        f"{SLIDE_WIDTH}x{SLIDE_HEIGHT} (DPI {FAITHFUL_DPI})"
    )

    pages_out: list = []
    sem = asyncio.Semaphore(OCR_CONCURRENCY)

    async def _render_page(i: int) -> dict:
        page = pdf.load_page(i)
        page_num = i + 1
        filename = f"pdf_page_{page_num}.jpg"
        target = assets_dir / filename

        # Render at high DPI for crisp detail, then fit to slide aspect 1920x820.
        # We render at the page's natural size then scale/pad to fit.
        mat = fitz.Matrix(FAITHFUL_DPI / 72, FAITHFUL_DPI / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        # Use PIL to fit into target aspect with white background (page margin)
        try:
            from PIL import Image
            import io as _io
            src_img = Image.open(_io.BytesIO(pix.tobytes("png"))).convert("RGB")
            # Fit-inside: keep aspect ratio, pad with white
            src_w, src_h = src_img.size
            target_ratio = SLIDE_WIDTH / SLIDE_HEIGHT
            src_ratio = src_w / src_h
            if src_ratio > target_ratio:
                # Source wider -> fit width
                new_w = SLIDE_WIDTH
                new_h = int(SLIDE_WIDTH / src_ratio)
            else:
                new_h = SLIDE_HEIGHT
                new_w = int(SLIDE_HEIGHT * src_ratio)
            resized = src_img.resize((new_w, new_h), Image.LANCZOS)
            canvas = Image.new("RGB", (SLIDE_WIDTH, SLIDE_HEIGHT), "white")
            canvas.paste(resized, ((SLIDE_WIDTH - new_w) // 2, (SLIDE_HEIGHT - new_h) // 2))
            canvas.save(target, "JPEG", quality=90, optimize=True)
        except Exception as e:
            logger.warning(f"[faithful] PIL fit failed on page {page_num}: {e}; using raw pixmap")
            pix.save(str(target))

        # Text (native extraction first, OCR fallback on blank pages)
        text = _extract_text_with_layout(page)
        if len(text.strip()) < MIN_NATIVE_TEXT_CHARS:
            async with sem:
                text = await _ocr_page(target, tesseract_ok)

        if progress_cb:
            try:
                progress_cb((i + 1) / total_pages, f"pagina {page_num}/{total_pages}")
            except Exception:
                pass

        return {"page_num": page_num, "filename": filename, "text": text.strip()}

    # Process pages in batches to keep memory bounded.
    batch_size = 4
    for start in range(0, total_pages, batch_size):
        batch = [_render_page(i) for i in range(start, min(start + batch_size, total_pages))]
        results = await asyncio.gather(*batch, return_exceptions=True)
        for r in results:
            if isinstance(r, dict):
                pages_out.append(r)
            else:
                logger.error(f"[pdf_extractor/faithful] page error: {r}")

    pages_out.sort(key=lambda p: p["page_num"])
    pdf.close()
    logger.info(f"[pdf_extractor/faithful] rendered {len(pages_out)} pages")
    return {"pages": pages_out, "total_pages": total_pages}


def build_faithful_slides(pages: list, project_id: str) -> list:
    """Turn each rendered page into a minimal slide preserving the original
    design. The page image is set as the slide's background so zero editable
    elements overlap the visual content. The OCR/extracted text stays in the
    slide `notes` for narration and search.
    """
    try:
        from models import generate_id
    except Exception:
        import uuid as _uuid
        def generate_id():
            return _uuid.uuid4().hex

    slides = []
    for i, p in enumerate(pages):
        url = f"/api/projects/{project_id}/assets/{p['filename']}"
        # Derive a slide title from the first line of the OCR'd text
        first_line = ""
        for line in (p.get("text") or "").split("\n"):
            line = line.strip()
            if 5 <= len(line) <= 80:
                first_line = line
                break
        title = first_line or f"Pagina {p['page_num']}"
        slides.append({
            "id": generate_id(),
            "title": title[:120],
            "order": i,
            "width": SLIDE_WIDTH,
            "height": SLIDE_HEIGHT,
            "background": "#ffffff",
            "backgroundImage": url,
            "backgroundOpacity": 100,
            "elements": [],
            "annotations": [],
            "transition": {"type": "fade", "duration": 0.5},
            "audio": [],
            "notes": p.get("text", ""),
            "type": "content",
            "_pdfFaithful": True,
            "_pdfPage": p["page_num"],
        })
    return slides
