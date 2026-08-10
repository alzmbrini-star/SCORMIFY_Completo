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
# Keep this low so pages with sparse-but-real text (titles, captions) don't
# trigger expensive OCR unnecessarily.
MIN_NATIVE_TEXT_CHARS = 25
# Render DPI for OCR/fallback image.
RENDER_DPI = 180
# Max OCR concurrency (avoid CPU starvation; Tesseract is CPU-bound and
# competes with uvicorn event loop threads for cores).
OCR_CONCURRENCY = 1

# Dedicated thread pool so PyMuPDF/Tesseract work doesn't starve the default
# asyncio pool (which is also used by motor/MongoDB). Keep it small (2) to
# avoid cpu thrashing on 2-core production pods.
_PDF_EXECUTOR = None


def _get_pdf_executor():
    global _PDF_EXECUTOR
    if _PDF_EXECUTOR is None:
        from concurrent.futures import ThreadPoolExecutor
        _PDF_EXECUTOR = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="pdf-extract"
        )
    return _PDF_EXECUTOR


async def _run_blocking(func, *args, **kwargs):
    """Run a CPU-bound function in the dedicated PDF executor so the default
    asyncio pool (used by motor/mongo) stays responsive."""
    loop = asyncio.get_event_loop()
    import functools as _ft
    call = _ft.partial(func, *args, **kwargs) if kwargs else (lambda: func(*args))
    return await loop.run_in_executor(_get_pdf_executor(), call)


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
    max_per_page: int = 8,
) -> List[PdfImage]:
    """Extract embedded images from a page. Caps at `max_per_page` to avoid
    blowup on PDFs where every letter is embedded as a tiny image."""
    images: List[PdfImage] = []
    try:
        image_list = page.get_images(full=True)
    except Exception:
        return images

    seen_xrefs = set()
    for img_idx, img_info in enumerate(image_list, start=1):
        if len(images) >= max_per_page:
            break
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
            # Skip ridiculously large images (>20MB decompressed) — they're
            # usually full-page scans and would bloat the course.
            if len(img_bytes) > 20_000_000:
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
    """Run tesseract as a subprocess with a hard 20s timeout.

    Using subprocess (instead of pytesseract's in-process call) lets us kill
    the Tesseract process if it gets stuck on a malformed image, preventing
    the thread worker from being held forever and freezing the event loop.
    """
    try:
        result = subprocess.run(
            ["tesseract", str(image_path), "-", "-l", "por+eng"],
            capture_output=True,
            timeout=20,
            check=False,
        )
        if result.returncode == 0:
            return (result.stdout or b"").decode("utf-8", errors="ignore")
        return ""
    except subprocess.TimeoutExpired:
        logger.warning(f"[pdf_extractor] tesseract timed out on {image_path.name}")
        return ""
    except FileNotFoundError:
        # Tesseract binary not installed
        return ""
    except Exception as e:
        logger.warning(f"[pdf_extractor] tesseract failed on {image_path.name}: {e}")
        return ""


async def _gemini_ocr(image_path: Path) -> str:
    """Fallback OCR via an OpenAI multimodal model."""
    try:
        emergent_key = os.environ.get("OPENAI_API_KEY", "").strip() or os.environ.get("EMERGENT_LLM_KEY", "").strip()
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
        ).with_model("openai", os.environ.get("OPENAI_VISION_MODEL", "gpt-4o"))
        mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
        attachment = FileContentWithMimeType(file_path=str(image_path), mime_type=mime)
        msg = UserMessage(
            text="Transcreva o texto desta pagina preservando paragrafos e titulos.",
            file_contents=[attachment],
        )
        # Hard cap: if Gemini takes >25s on one page, give up and return empty
        # so the overall extraction keeps moving.
        response = await asyncio.wait_for(chat.send_message(msg), timeout=25.0)
        if isinstance(response, str):
            return response.strip()
        return str(response).strip()
    except asyncio.TimeoutError:
        logger.warning(f"[pdf_extractor] gemini OCR timed out on {image_path.name}")
        return ""
    except Exception as e:
        logger.warning(f"[pdf_extractor] gemini OCR failed on {image_path.name}: {e}")
        return ""


async def _ocr_page(image_path: Path, tesseract_ok: bool) -> str:
    """Run OCR: Tesseract first, Gemini fallback (strategy 3c)."""
    text = ""
    if tesseract_ok:
        # Run tesseract in the dedicated PDF executor so motor/mongo calls
        # are not blocked by OCR work.
        text = await _run_blocking(_tesseract_ocr, image_path)
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
        text = await _run_blocking(_extract_text_with_layout, page)
        images = await _run_blocking(
            _extract_embedded_images, pdf, page, page_num, assets_dir
        )
        for img in images:
            asset_filenames.append(img.filename)

        is_scanned = len(text.strip()) < MIN_NATIVE_TEXT_CHARS
        rendered_image: Optional[str] = None

        # If the page has extractable images, assume it's a visual page (cover,
        # infographic, diagram). Skip the expensive OCR — we already have the
        # images, and the LLM/post-processor will know what to do with them.
        if is_scanned and not images:
            scanned_pages_count += 1
            rendered_filename = await _run_blocking(
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

    # Process pages ONE AT A TIME with explicit yields to the event loop.
    # Each page has a hard timeout so a single corrupt/huge page never
    # freezes the whole extraction.
    PAGE_TIMEOUT = 90.0  # seconds
    t_extract_start = asyncio.get_event_loop().time()
    for i in range(total_pages):
        page_num = i + 1
        t_page = asyncio.get_event_loop().time()
        try:
            page = await asyncio.wait_for(_process_page(i), timeout=PAGE_TIMEOUT)
            if isinstance(page, PdfPage):
                pages.append(page)
            elapsed_page = asyncio.get_event_loop().time() - t_page
            if elapsed_page > 5.0:
                logger.info(
                    f"[pdf_extractor] page {page_num}/{total_pages} took "
                    f"{elapsed_page:.1f}s (scanned={getattr(page, 'is_scanned', False)})"
                )
        except asyncio.TimeoutError:
            logger.warning(
                f"[pdf_extractor] page {page_num} timed out after {PAGE_TIMEOUT}s; skipping"
            )
            pages.append(PdfPage(page_num=page_num, text="", images=[], is_scanned=False))
        except Exception as e:
            logger.error(f"[pdf_extractor] page {page_num} error: {e}", exc_info=True)
            pages.append(PdfPage(page_num=page_num, text="", images=[], is_scanned=False))
        # Yield control so other HTTP requests on the same worker can be served.
        await asyncio.sleep(0)
    logger.info(
        f"[pdf_extractor] all {total_pages} pages processed in "
        f"{asyncio.get_event_loop().time() - t_extract_start:.1f}s"
    )

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
# Canvas kept at slide aspect but with reduced resolution/DPI to keep the
# JPEG small enough that production pods (250m CPU) can render each page
# in under ~1 second, avoiding Cloudflare 520s during polling.
SLIDE_WIDTH = 1280
SLIDE_HEIGHT = 546
FAITHFUL_DPI = 110
FAITHFUL_JPEG_QUALITY = 80
# Sleep between pages so the OS scheduler gives CPU time to the uvicorn
# event loop handling /faithful-status polling requests.
FAITHFUL_PAGE_COOLDOWN = 0.30  # seconds

# Adaptive quality thresholds (2026-05-25). For large PDFs we render at a
# lower resolution / lower quality to keep peak memory under the production
# pod's ~512Mi limit. PyMuPDF pixmaps are width*height*3 bytes; halving
# both axes cuts the peak by 4x.
ADAPTIVE_LARGE_PDF_BYTES = 10 * 1024 * 1024     # 10 MB
ADAPTIVE_HUGE_PDF_BYTES = 25 * 1024 * 1024      # 25 MB


def _pick_render_params(pdf_bytes_len: int) -> tuple:
    """Return (width, height, jpeg_quality) tuned for the PDF size."""
    if pdf_bytes_len > ADAPTIVE_HUGE_PDF_BYTES:
        return 960, 410, 65   # ~60% less peak memory than default
    if pdf_bytes_len > ADAPTIVE_LARGE_PDF_BYTES:
        return 1120, 478, 72  # ~30% less peak memory
    return SLIDE_WIDTH, SLIDE_HEIGHT, FAITHFUL_JPEG_QUALITY


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
    total_pages = pdf.page_count
    # Adaptive sizing: shrink the render target for large PDFs to avoid
    # OOM on small production pods (~512Mi). Each MuPDF pixmap is
    # width*height*3 bytes; halving both axes cuts peak RAM by ~4x.
    eff_w, eff_h, eff_q = _pick_render_params(len(pdf_bytes))
    logger.info(
        f"[pdf_extractor/faithful] rendering {total_pages} pages at "
        f"{eff_w}x{eff_h} q={eff_q} (PDF {len(pdf_bytes) / (1024*1024):.1f} MB)"
    )

    pages_out: list = []

    async def _render_page(i: int) -> dict:
        page = pdf.load_page(i)
        page_num = i + 1
        filename = f"pdf_page_{page_num}.jpg"
        target = assets_dir / filename

        # Memory-efficient render: use fitz.Matrix to scale directly to final
        # size in a single pass (no PIL intermediate canvas), and release the
        # pixmap explicitly so the MuPDF C memory is freed before the next
        # page. This is essential on low-memory production pods.
        def _do_render():
            # Compute scale so the page FITS inside eff_w x eff_h
            page_rect = page.rect
            src_w = page_rect.width
            src_h = page_rect.height
            scale_w = eff_w / src_w
            scale_h = eff_h / src_h
            scale = min(scale_w, scale_h)
            matrix = fitz.Matrix(scale, scale)
            pix = None
            try:
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                # Save directly as JPEG via pixmap (no PIL needed).
                pix.save(str(target), jpg_quality=eff_q)
            finally:
                # Explicit release of MuPDF memory before the next page.
                if pix is not None:
                    try:
                        pix = None
                    except Exception:
                        pass
            # Extract text AFTER pixmap is released to reduce peak memory.
            return _extract_text_with_layout(page)

        text = await _run_blocking(_do_render)

        if progress_cb:
            try:
                progress_cb((i + 1) / total_pages, f"pagina {page_num}/{total_pages}")
            except Exception:
                pass

        return {"page_num": page_num, "filename": filename, "text": text.strip()}

    # Serial processing with batching + explicit GC between batches. Running
    # gc.collect() periodically reclaims MuPDF/Python memory and prevents OOM
    # on low-memory production pods (~512Mi RAM).
    import gc as _gc
    BATCH_SIZE = 3
    for i in range(total_pages):
        try:
            result = await asyncio.wait_for(_render_page(i), timeout=30.0)
            pages_out.append(result)
        except asyncio.TimeoutError:
            logger.warning(f"[faithful] page {i+1} render timed out; skipping")
            pages_out.append({"page_num": i + 1, "filename": f"pdf_page_{i+1}.jpg", "text": ""})
        except Exception as r:
            logger.error(f"[faithful] page error: {r}")
            pages_out.append({"page_num": i + 1, "filename": f"pdf_page_{i+1}.jpg", "text": ""})

        # After each batch: give CPU back to uvicorn event loop AND free memory
        if (i + 1) % BATCH_SIZE == 0:
            _gc.collect()
            await asyncio.sleep(1.0)
        else:
            await asyncio.sleep(FAITHFUL_PAGE_COOLDOWN)

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
            # 2026-05-25: Modo Fiel renders the PDF page AS the slide bg.
            # Default `cover` crops top/sides when aspect ratios differ
            # (Letter PDF ~2.59 vs slide ~2.34) — exactly what made the
            # title and side logos disappear in production SCORM exports.
            # `contain` letter-boxes instead, preserving the WHOLE page.
            "backgroundImageFit": "contain",
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
