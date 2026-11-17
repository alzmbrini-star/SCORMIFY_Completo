"""Defer large media expansion until the final file write (no player changes).

Tokens exist only during generation. The delivered HTML contains ordinary exact
data URIs, including inside base64 iframe documents. Context-local and export-
scoped: concurrent jobs never share media or change the saved project.
"""
import base64
import hashlib
from contextvars import ContextVar
import mimetypes
from pathlib import Path
import re
import uuid
from tempfile import TemporaryDirectory

CURRENT = ContextVar('export_media_stream', default=None)
CHUNK = 48 * 1024  # divisible by three for streaming base64
DATA_URI = re.compile(r'data:[\w.+/-]+(?:;[\w=.+-]+)*;base64,[A-Za-z0-9+/=]+')


class MediaStream:
    def __init__(self):
        self.prefix = '__SCORMIFY_' + uuid.uuid4().hex + '_'
        self.pattern = re.compile(re.escape(self.prefix) + r'(\d+)__')
        self.entries = []
        self.files = {}
        self.spool = TemporaryDirectory(prefix='scormify-media-')
        self.embedded = {}

    def close(self):
        self.spool.cleanup()

    def add(self, kind, value):
        token = self.prefix + str(len(self.entries)) + '__'
        self.entries.append((kind, value))
        return token

    def file(self, path):
        path = str(Path(path).resolve())
        if path not in self.files:
            mime = mimetypes.guess_type(path)[0] or 'application/octet-stream'
            self.files[path] = 'data:' + mime + ';base64,' + self.add('file', path)
        return self.files[path]

    def compact(self, value):
        """Copy structure, not media. Do this before any rendering/deepcopy."""
        if isinstance(value, dict):
            return {key: self.compact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.compact(item) for item in value]
        if isinstance(value, str) and 'data:' in value:
            def compact_uri(match):
                header, payload = match[0].split(',', 1)
                digest = hashlib.sha256(payload.encode('ascii')).hexdigest()
                if digest not in self.embedded:
                    path = Path(self.spool.name) / digest
                    with path.open('wb') as target:
                        for offset in range(0, len(payload), CHUNK):
                            target.write(payload[offset:offset + CHUNK].encode('ascii'))
                    self.embedded[digest] = self.add('literal_file', str(path))
                return header + ',' + self.embedded[digest]
            return DATA_URI.sub(compact_uri, value)
        return value

    def chunks(self, text):
        pos = 0
        for match in self.pattern.finditer(text):
            yield from self.literal(text, pos, match.start())
            kind, value = self.entries[int(match[1])]
            if kind in ('file', 'literal_file'):
                with open(value, 'rb') as source:
                    while block := source.read(CHUNK):
                        yield base64.b64encode(block) if kind == 'file' else block
            elif kind == 'base64':
                carry = b''
                for block in self.chunks(value):
                    block = carry + block
                    size = len(block) // 3 * 3
                    if size:
                        yield base64.b64encode(block[:size])
                    carry = block[size:]
                if carry:
                    yield base64.b64encode(carry)
            else:
                yield from self.chunks(value)
            pos = match.end()
        yield from self.literal(text, pos, len(text))

    @staticmethod
    def literal(text, start, end):
        for offset in range(start, end, CHUNK):
            yield text[offset:min(offset + CHUNK, end)].encode('utf-8')

    def write(self, path, text):
        # A failed expansion must never leave a seemingly complete download.
        path = Path(path)
        partial = path.with_name(path.name + '.partial-' + uuid.uuid4().hex)
        try:
            with partial.open('wb') as target:
                for block in self.chunks(text):
                    target.write(block)
            partial.replace(path)
        finally:
            partial.unlink(missing_ok=True)


def encode_document(text):
    stream = CURRENT.get()
    return stream.add('base64', text) if stream else base64.b64encode(text.encode('utf-8')).decode('ascii')
