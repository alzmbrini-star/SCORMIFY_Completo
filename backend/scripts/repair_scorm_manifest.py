"""Repair only the manifest inventory, preserving every other ZIP member byte-for-byte."""
import argparse
import copy
import hashlib
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET
from urllib.parse import quote, unquote, urlsplit
from zipfile import ZipFile


def repair(source: Path, output: Path):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve() or output.exists():
        raise ValueError('Use a new output path; originals are never overwritten')
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    with ZipFile(source) as original:
        if original.testzip():
            raise ValueError('Source ZIP is corrupt')
        names = [entry.filename for entry in original.infolist() if not entry.is_dir()]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP entries')
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name:
                raise ValueError('Unsafe package path')
        root = ET.fromstring(original.read('imsmanifest.xml'))
        ns = root.tag.split('}')[0][1:]
        ET.register_namespace('', ns)
        ET.register_namespace('adlcp', 'http://www.adlnet.org/xsd/adlcp_rootv1p2')
        ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        resources = root.findall(f'{{{ns}}}resources/{{{ns}}}resource')
        if len(resources) != 1:
            raise ValueError('Expected one SCO resource; refusing ambiguous repair')
        resource = resources[0]
        for node in list(resource):
            if node.tag == f'{{{ns}}}file':
                resource.remove(node)
        for name in sorted(set(names) - {'imsmanifest.xml'}):
            ET.SubElement(resource, f'{{{ns}}}file', href=quote(name, safe='/'))
        manifest = ET.tostring(root, encoding='utf-8', xml_declaration=True)
        with ZipFile(output, 'x') as fixed:
            fixed.comment = original.comment
            for entry in original.infolist():
                fixed.writestr(copy.copy(entry), manifest if entry.filename == 'imsmanifest.xml' else original.read(entry))
        with ZipFile(output) as fixed:
            assert fixed.testzip() is None
            assert original.namelist() == fixed.namelist()
            unchanged = [name for name in names if name != 'imsmanifest.xml']
            assert all(original.read(name) == fixed.read(name) for name in unchanged)
            parsed = ET.fromstring(fixed.read('imsmanifest.xml'))
            for node in parsed.findall(f'.//{{{ns}}}file'):
                assert unquote(urlsplit(node.get('href')).path) in names
            assert parsed.get('identifier') == root.get('identifier')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    return {'unchangedFiles': len(unchanged), 'changedFiles': ['imsmanifest.xml'], 'originalUnchanged': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(repair(args.source, args.output))
