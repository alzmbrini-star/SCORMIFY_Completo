"""Bounded-memory JSON emission for self-contained HTML exports.

Media remains embedded/offline. Only intermediate serialization moves to disk.
"""
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

CHUNK = 64 * 1024
COURSE_MARKER = '__SCORMIFY_STREAMED_COURSE_JSON__'


def write_json(target, value):
    if isinstance(value, JsonArraySpool):
        value.copy_to(target)
    elif isinstance(value, str):
        target.write('"')
        for offset in range(0, len(value), CHUNK):
            # Escape '<' for ALL script end-tag casings, including mixed case.
            encoded = json.dumps(value[offset:offset + CHUNK], ensure_ascii=False)[1:-1]
            target.write(encoded.replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029'))
        target.write('"')
    elif isinstance(value, dict):
        target.write('{')
        for i, (key, item) in enumerate(value.items()):
            if i: target.write(',')
            write_json(target, str(key)); target.write(':'); write_json(target, item)
        target.write('}')
    elif isinstance(value, (list, tuple)):
        target.write('[')
        for i, item in enumerate(value):
            if i: target.write(',')
            write_json(target, item)
        target.write(']')
    elif isinstance(value, datetime):
        write_json(target, value.isoformat())
    else:
        target.write(json.dumps(value, ensure_ascii=False))


class JsonArraySpool:
    """Release each prepared slide instead of retaining all embedded slides."""
    def __init__(self):
        self.file = tempfile.TemporaryFile(mode='w+', encoding='utf-8', newline='')
        self.count = 0

    def append(self, value):
        if self.count: self.file.write(',')
        write_json(self.file, value)
        self.count += 1

    def copy_to(self, target):
        self.file.seek(0)
        target.write('[')
        while chunk := self.file.read(CHUNK): target.write(chunk)
        target.write(']')

    def __enter__(self): return self
    def __exit__(self, *args): self.file.close()


def write_html_file(path, template, course):
    """Atomically publish a small template + streamed payload, never a giant str."""
    before, marker, after = template.partition(COURSE_MARKER)
    if not marker: raise ValueError('Marcador do HTML não encontrado.')
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='', dir=destination.parent, suffix='.part', delete=False) as target:
            temporary = target.name
            target.write(before); write_json(target, course); target.write(after)
        os.replace(temporary, destination)
    finally:
        if temporary and os.path.exists(temporary): os.unlink(temporary)
    return str(destination)
