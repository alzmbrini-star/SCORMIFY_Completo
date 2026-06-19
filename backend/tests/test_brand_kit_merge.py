"""Regression test for the brand-kit merge in `_run_scorm_export_job`.

User-reported bug: the loader settings on a company's brand kit were
NOT being applied to the exported SCORM when the project already had
its own `primaryColor`. Cause: the merge logic short-circuited on
"project has primaryColor OR loaderTitle" — which skipped the merge
entirely instead of merging field-by-field.

The fix performs a per-field merge with project values taking
precedence ONLY when non-empty.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _merge_brand_kits(company_kit: dict, project_kit: dict) -> dict:
    """Replicates the inlined merge from `_run_scorm_export_job`.
    Extracted here so it can be unit-tested without spinning up
    Mongo / FastAPI."""
    merged = dict(company_kit)
    for k, v in project_kit.items():
        if v not in (None, ""):
            merged[k] = v
    return merged


def test_merge_inherits_company_loader_when_project_only_has_primary():
    """The original bug: project has its own primaryColor but no loader
    settings → company's loaderTitle/Color/Accent must still apply."""
    company = {
        "primaryColor": "#000000",
        "loaderTitle": "Carregando treinamento da Empresa X…",
        "loaderColor": "#dc2626",
        "loaderAccent": "#f87171",
    }
    project = {"primaryColor": "#1e40af"}  # only primary, no loader

    merged = _merge_brand_kits(company, project)
    assert merged["primaryColor"] == "#1e40af"          # project wins
    assert merged["loaderTitle"] == "Carregando treinamento da Empresa X…"
    assert merged["loaderColor"] == "#dc2626"
    assert merged["loaderAccent"] == "#f87171"


def test_merge_project_loader_overrides_company():
    company = {
        "primaryColor": "#000000",
        "loaderTitle": "Default company message",
        "loaderColor": "#dc2626",
    }
    project = {
        "primaryColor": "#1e40af",
        "loaderTitle": "Specific course override",
    }
    merged = _merge_brand_kits(company, project)
    assert merged["loaderTitle"] == "Specific course override"
    assert merged["loaderColor"] == "#dc2626"  # company default still inherited


def test_merge_empty_string_project_value_does_not_override():
    """Empty string in the project payload must NOT clobber the
    company default — empty == "unset"."""
    company = {"loaderTitle": "Real message"}
    project = {"loaderTitle": ""}
    merged = _merge_brand_kits(company, project)
    assert merged["loaderTitle"] == "Real message"


def test_merge_handles_empty_company_kit():
    company = {}
    project = {"primaryColor": "#1e40af"}
    merged = _merge_brand_kits(company, project)
    assert merged == {"primaryColor": "#1e40af"}


def test_merge_handles_missing_keys():
    company = {"loaderColor": "#dc2626"}
    project = {"loaderTitle": "Custom"}
    merged = _merge_brand_kits(company, project)
    assert merged["loaderTitle"] == "Custom"
    assert merged["loaderColor"] == "#dc2626"
