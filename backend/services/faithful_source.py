"""Stream the original PDF to disk; never allocate a whole large PDF in RAM."""
import os
import tempfile
import inspect
from pathlib import Path

MAX_SOURCE_BYTES = 300 * 1024 * 1024
CHUNK_BYTES = 256 * 1024


def validate_source_size(size):
    if size > MAX_SOURCE_BYTES:
        raise ValueError('O Modo Fiel suporta PDFs de até 300 MB. Divida o arquivo em partes menores; o original enviado permanece preservado.')


async def close_source(stream):
    # Motor GridOut.close delegates to a synchronous PyMongo method.
    result = stream.close()
    if inspect.isawaitable(result):
        await result


async def download_source(stream):
    path = None
    try:
        validate_source_size(stream.length)
        fd, name = tempfile.mkstemp(prefix='scormify-faithful-', suffix='.pdf')
        path = Path(name)
        total = 0
        with os.fdopen(fd, 'wb') as output:
            while True:
                chunk = await stream.read(CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                validate_source_size(total)
                output.write(chunk)
        if not total:
            raise ValueError('O PDF salvo está vazio. Reenvie o arquivo original.')
        return path
    except BaseException:
        if path is not None:
            path.unlink(missing_ok=True)
        raise
    finally:
        await close_source(stream)
