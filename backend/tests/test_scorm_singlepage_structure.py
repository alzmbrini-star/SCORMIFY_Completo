"""SCORM 1.2 package structural validation tests for the single-page export.

Reproduces issues reported by user importing into LMS (Canvas/Blackboard/SCORM Cloud)
where the old structure had:
  - Identifier with hyphens (some strict LMS reject)
  - scorm-api.js at root instead of scripts/ subfolder convention
"""
import re
import zipfile
from pathlib import Path
from xml.dom.minidom import parseString

import pytest


def _latest_singlepage_zip() -> Path:
    exports = Path("/app/backend/storage/exports")
    zips = sorted(exports.glob("*_singlepage_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    assert zips, "No single-page SCORM zip found"
    return zips[0]


@pytest.fixture(scope="module")
def manifest_text():
    z = _latest_singlepage_zip()
    with zipfile.ZipFile(z) as zf:
        return zf.read("imsmanifest.xml").decode("utf-8")


@pytest.fixture(scope="module")
def zip_namelist():
    z = _latest_singlepage_zip()
    with zipfile.ZipFile(z) as zf:
        return zf.namelist()


def test_manifest_is_well_formed_xml(manifest_text):
    parseString(manifest_text)  # raises if malformed


def test_manifest_identifier_is_ncname_safe(manifest_text):
    """SCORM 1.2 requires identifier to be an XML NCName (no hyphens for some
    strict LMS like Canvas/Blackboard/SuccessFactors)."""
    m = re.search(r'identifier="([^"]+)"', manifest_text)
    assert m
    ident = m.group(1)
    assert re.match(r'^[A-Za-z_][A-Za-z0-9._]*$', ident), \
        f"Identifier '{ident}' is not NCName-safe (must match [A-Za-z_][A-Za-z0-9._]*)"
    assert "-" not in ident, "Identifier should not contain hyphens for LMS compat"


def test_manifest_resource_files_reference_existing_zip_entries(manifest_text, zip_namelist):
    """Every <file href="..."> must point to a real entry in the ZIP."""
    referenced = set(re.findall(r'<file href="([^"]+)"', manifest_text))
    in_zip = set(zip_namelist)
    missing = referenced - in_zip
    assert not missing, f"Manifest references files NOT in ZIP: {missing}"


def test_manifest_main_file_is_index_html(manifest_text):
    assert 'href="index.html"' in manifest_text
    # The <resource href="..."> attribute (entry point)
    assert re.search(r'<resource[^>]+href="index\.html"', manifest_text)


def test_scripts_folder_convention(zip_namelist):
    """scorm-api.js must live under scripts/ to match LMS convention used by
    the legacy traditional SCORM exporter (some LMS validate path patterns)."""
    assert "scripts/scorm-api.js" in zip_namelist
    assert "scorm-api.js" not in zip_namelist  # no loose copy at root


def test_index_html_references_scripts_subfolder():
    z = _latest_singlepage_zip()
    with zipfile.ZipFile(z) as zf:
        idx = zf.read("index.html").decode("utf-8")
    assert '<script src="scripts/scorm-api.js">' in idx
    assert '<script src="scorm-api.js">' not in idx


def test_required_xsd_files_present(zip_namelist):
    for xsd in ("adlcp_rootv1p2.xsd", "ims_xml.xsd",
                "imscp_rootv1p1p2.xsd", "imsmd_rootv1p2p1.xsd"):
        assert xsd in zip_namelist, f"Missing SCORM XSD: {xsd}"


def test_manifest_has_required_scorm_metadata(manifest_text):
    assert "<schema>ADL SCORM</schema>" in manifest_text
    assert "<schemaversion>1.2</schemaversion>" in manifest_text
    assert 'adlcp:scormtype="sco"' in manifest_text
    assert "<adlcp:masteryscore>" in manifest_text


def test_manifest_namespaces_correct(manifest_text):
    """SCORM 1.2 requires these exact namespace URIs."""
    assert 'xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"' in manifest_text
    assert 'xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"' in manifest_text
    assert 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' in manifest_text
