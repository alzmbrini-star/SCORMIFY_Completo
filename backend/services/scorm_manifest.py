"""SCORM resource inventory: real files only, including nested dependencies."""
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import quoteattr


def manifest_file_entries(package_dir: Path) -> str:
    paths = sorted(
        path.relative_to(package_dir).as_posix()
        for path in package_dir.rglob('*')
        if path.is_file() and path.name != 'imsmanifest.xml'
    )
    return '\n            '.join(
        f'<file href={quoteattr(quote(path, safe="/"))}/>' for path in paths
    )
