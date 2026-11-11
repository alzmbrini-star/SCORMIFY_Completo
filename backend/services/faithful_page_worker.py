"""Trusted one-page renderer. A fresh process frees all MuPDF caches on exit."""
import json
import math
import sys

MAX_EDGE = 2560
MAX_PIXELS = 3_000_000


def page_scale(width, height, max_edge=MAX_EDGE, max_pixels=MAX_PIXELS):
    if not math.isfinite(width) or not math.isfinite(height) or min(width,height) <= 0:
        raise ValueError('Dimensões inválidas na página PDF.')
    return min((max_edge-2)/max(width,height), math.sqrt((max_pixels-10000)/(width*height)))


def main():
    # Linux production: fail the child, not the web service, on extreme native
    # allocations. Windows local tests still use per-page process isolation.
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
    except (ImportError, ValueError, OSError):
        pass
    try:
        import fitz
        source,index,target,budget=sys.argv[1:]
        with fitz.open(source) as doc:
            page=doc.load_page(int(index))
            scale=page_scale(page.rect.width,page.rect.height,max_pixels=int(budget))
            pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),colorspace=fitz.csRGB,alpha=False)
            pix.save(target)
            width,height=pix.width,pix.height
            del pix
            fitz.TOOLS.store_shrink(100)
            try: text=page.get_text('text',sort=True)[:10000]
            except Exception: text=''
        print(json.dumps({'text':text,'width':width,'height':height},ensure_ascii=True))
    except Exception as exc:
        # No document contents or paths in the parent-facing error contract.
        memory=isinstance(exc,MemoryError) or any(s in (type(exc).__name__+' '+str(exc)).lower() for s in ('memory','malloc','allocat'))
        sys.exit(2 if memory else 3)


if __name__=='__main__':
    main()
