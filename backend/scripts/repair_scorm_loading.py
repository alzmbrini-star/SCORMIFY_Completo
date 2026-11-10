"""Create a new lossless SCORM copy; never overwrite input or learning rules."""
import argparse
import copy
import hashlib
import json
import re
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET

from services.scorm_initial_loading import install_initial_loader, externalize_scorm_images


def repair(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or destination.exists():
        raise ValueError('Use a new output filename. The original and existing outputs are never overwritten.')
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as original, tempfile.TemporaryDirectory(prefix='scorm-loading-') as directory:
        paths = [entry.filename for entry in original.infolist()]
        if len(paths) != len(set(paths)):
            raise ValueError('Duplicate archive paths are not supported.')
        for name in paths:
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
                raise ValueError('Unsafe archive path.')
        assets = Path(directory) / 'assets'
        assets.mkdir()
        for name in paths:
            if name.startswith('assets/') and len(PurePosixPath(name).parts) == 2 and not name.endswith('/'):
                (assets / PurePosixPath(name).name).write_bytes(original.read(name))
        raw_course = original.read('course.json')
        course = json.loads(raw_course)
        before = copy.deepcopy(course)
        stats = externalize_scorm_images(course, assets)
        # Compare every original leaf: only exact-byte raster data URLs may change.
        changes = []
        def verify(left, right):
            if isinstance(left, dict):
                assert left.keys() == right.keys()
                for key in left: verify(left[key], right[key])
            elif isinstance(left, list):
                assert len(left) == len(right)
                for a, b in zip(left, right): verify(a, b)
            elif left != right:
                import base64
                assert isinstance(left, str) and left.startswith('data:image/')
                assert isinstance(right, str) and right.startswith('assets/')
                raw = base64.b64decode(left.split(',', 1)[1], validate=True)
                assert raw == (assets / right.split('/', 1)[1]).read_bytes()
                changes.append(right)
        verify(before, course)
        html = install_initial_loader(original.read('index.html').decode('utf-8'))
        token = uuid.uuid4().hex
        html = re.sub(r'(window\.__SCORMIFY_EXPORT_TOKEN__\s*=\s*)["\'][^"\']*["\']',
                      lambda match: match.group(1) + json.dumps(token), html)
        manifest = ET.fromstring(original.read('imsmanifest.xml'))
        ns = manifest.tag.split('}')[0][1:]
        ET.register_namespace('', ns)
        ET.register_namespace('adlcp', 'http://www.adlnet.org/xsd/adlcp_rootv1p2')
        ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        resource = next((item for item in manifest.iter('{' + ns + '}resource')
                         if (item.get('href') or '').split('?', 1)[0] == 'index.html'), None)
        if resource is None:
            raise ValueError('Launch resource not found.')
        existing = {element.get('href') for element in resource.findall('{' + ns + '}file')}
        for name in sorted(set(changes)):
            if name not in existing: ET.SubElement(resource, '{' + ns + '}file', href=name)
        rewritten = {'index.html': html.encode('utf-8'),
                     'course.json': json.dumps(course, ensure_ascii=False, separators=(',', ':')).encode('utf-8'),
                     'imsmanifest.xml': ET.tostring(manifest, encoding='utf-8', xml_declaration=True)}
        with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
            for entry in original.infolist():
                output.writestr(copy.copy(entry), rewritten[entry.filename] if entry.filename in rewritten else original.read(entry.filename))
            for name in sorted(set(changes)):
                if name not in paths: output.write(assets / name.split('/', 1)[1], name)
        with zipfile.ZipFile(destination) as output:
            assert output.testzip() is None
            assert ET.fromstring(output.read('imsmanifest.xml')).get('identifier') == manifest.get('identifier')
            for name in paths:
                if name not in rewritten: assert output.read(name) == original.read(name)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
        return {**stats, 'slides': len(course.get('slides', [])), 'oldJsonBytes': len(raw_course),
                'newJsonBytes': len(rewritten['course.json']), 'zipBytes': destination.stat().st_size,
                'sourceSHA256': original_hash, 'output': str(destination)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source'); parser.add_argument('destination')
    args = parser.parse_args()
    print(json.dumps(repair(args.source, args.destination), ensure_ascii=False))
