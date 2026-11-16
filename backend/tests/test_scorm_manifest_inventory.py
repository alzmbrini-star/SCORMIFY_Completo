import json
from pathlib import Path
import xml.etree.ElementTree as ET
from urllib.parse import unquote
from zipfile import ZipFile, ZIP_DEFLATED

import pytest
from services.scorm_manifest import manifest_file_entries
from scripts.repair_scorm_manifest import repair


def test_recursive_inventory_only_files_with_safe_xml_and_uris(tmp_path):
    (tmp_path/'assets/_companies/empresa').mkdir(parents=True)
    (tmp_path/'assets/empty').mkdir()
    names = ['index.html', 'assets/_companies/empresa/marca & azul #1.png', 'assets/ação.png']
    for name in names:
        (tmp_path/name).write_bytes(b'exact image bytes')
    (tmp_path/'imsmanifest.xml').write_text('old')
    xml = ET.fromstring('<resource>'+manifest_file_entries(tmp_path)+'</resource>')
    assert sorted(unquote(n.get('href')) for n in xml) == sorted(names)


def test_repair_changes_only_manifest_and_preserves_identity_and_launch(tmp_path):
    source, output = tmp_path/'original.zip', tmp_path/'corrected.zip'
    manifest = '''<manifest xmlns="urn:test" identifier="same-course"><organizations><organization><title>Curso</title></organization></organizations><resources><resource identifier="same-sco" href="index.html?v=same"><file href="assets/_companies"/></resource></resources></manifest>'''
    with ZipFile(source, 'w', ZIP_DEFLATED) as package:
        package.writestr('imsmanifest.xml', manifest)
        package.writestr('index.html', '<html>unchanged interactions</html>')
        package.writestr('course.json', json.dumps({'slides': list(range(26)), 'questions': [1,2,3]}))
        package.writestr('assets/_companies/logo.png', b'original-logo')
        for n in range(6):
            package.writestr(f'assets/assessment{n}.png', bytes([n])*100)
    report = repair(source, output)
    assert report['unchangedFiles'] == 9
    with ZipFile(output) as package:
        root = ET.fromstring(package.read('imsmanifest.xml'))
        resource = root.find('{urn:test}resources/{urn:test}resource')
        assert resource.get('href') == 'index.html?v=same'
        assert resource.get('identifier') == 'same-sco'
        assert root.get('identifier') == 'same-course'
        refs = [unquote(n.get('href')) for n in resource]
        assert 'assets/_companies' not in refs
        assert 'assets/_companies/logo.png' in refs
    with pytest.raises(ValueError):
        repair(source, output)


def test_exporter_inventories_nested_assets_and_all_runtime_scripts(tmp_path, monkeypatch):
    from models import Project
    from services.scorm_exporter import export_scorm_package
    import services.scorm_manifest as inventory
    original = inventory.manifest_file_entries
    def include_nested_fixture(package_dir):
        nested = package_dir/'assets/_companies/brand'
        nested.mkdir(parents=True)
        (nested/'logo.png').write_bytes(b'unchanged fixture')
        return original(package_dir)
    monkeypatch.setattr(inventory, 'manifest_file_entries', include_nested_fixture)
    project = Project(id='manifest-regression',name='Inventory',ownerId='u',enableVlibras=False,
                      course={'metadata':{'title':'Inventory'},'slides':[{'id':'s1','title':'Original','order':0,'elements':[]}]})
    result = export_scorm_package(project, str(tmp_path), str(tmp_path), gamification_config={'enabled': True})
    with ZipFile(result) as package:
        root = ET.fromstring(package.read('imsmanifest.xml'))
        refs = [unquote(n.get('href')) for n in root.findall('.//{*}file')]
        assert len(refs) == len(set(refs))
        assert 'assets/_companies/brand/logo.png' in refs
        assert 'scripts/gamification.js' in refs
        assert all(name in package.namelist() and not package.getinfo(name).is_dir() for name in refs)
        assert json.loads(package.read('course.json'))['slides'][0]['id'] == 's1'
