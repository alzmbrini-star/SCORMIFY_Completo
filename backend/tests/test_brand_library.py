"""Tests for the Brand Library: company asset CRUD + brand kit + AI picker.

The Brand Library lets super-admins curate per-company imagery that the AI
Agent picks from when generating courses. This file validates:

  - Model normalization (asset type / category clamping to safe values)
  - The semantic picker's hard filters (type + category)
  - LLM-pick output parsing (handles quotes / 'none' / id-only responses)
  - Catalog cache invalidation
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from models import CompanyAsset, COMPANY_ASSET_TYPES, COMPANY_ASSET_CATEGORIES
from services.brand_library_picker import (
    pick_asset_for_slide,
    invalidate_catalog,
    _catalog_cache,
)


# ---------------------------------------------------------------------------
# Model normalization
# ---------------------------------------------------------------------------

class TestCompanyAssetModel:
    def test_default_type_is_background(self):
        a = CompanyAsset(companyId="c1", filename="x.png")
        assert a.type == "background"
        assert a.category == "generic"

    def test_invalid_type_falls_back_to_background(self):
        a = CompanyAsset(companyId="c1", filename="x.png", type="random-junk")
        assert a.type == "background"

    def test_invalid_category_falls_back_to_generic(self):
        a = CompanyAsset(companyId="c1", filename="x.png", category="not-a-category")
        assert a.category == "generic"

    def test_type_normalizes_case(self):
        a = CompanyAsset(companyId="c1", filename="x.png", type="ICON")
        assert a.type == "icon"

    def test_known_types_accepted(self):
        for t in COMPANY_ASSET_TYPES:
            a = CompanyAsset(companyId="c1", filename="x.png", type=t)
            assert a.type == t

    def test_known_categories_accepted(self):
        for c in COMPANY_ASSET_CATEGORIES:
            a = CompanyAsset(companyId="c1", filename="x.png", category=c)
            assert a.category == c


# ---------------------------------------------------------------------------
# Picker — filters + LLM call paths
# ---------------------------------------------------------------------------

def _fake_db_with_assets(rows):
    """Build a MagicMock that imitates `db.company_assets_meta.find(...).to_list()`."""
    db = MagicMock()
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=rows)
    db.company_assets_meta.find = MagicMock(return_value=cursor)
    return db


@pytest.fixture(autouse=True)
def _clear_picker_cache():
    """Reset the in-memory catalog cache before each test so cross-test
    pollution can't make a later test see stale data."""
    _catalog_cache.clear()
    yield
    _catalog_cache.clear()


@pytest.mark.asyncio
async def test_picker_returns_none_when_library_empty():
    db = _fake_db_with_assets([])
    out = await pick_asset_for_slide(
        db, "c1", slide_title="Intro", desired_type="background",
    )
    assert out is None


@pytest.mark.asyncio
async def test_picker_filters_by_type():
    """An icon must never be returned when caller asks for a background."""
    db = _fake_db_with_assets([
        {"id": "a1", "type": "icon", "category": "generic", "tags": [], "description": ""},
    ])
    out = await pick_asset_for_slide(
        db, "c1", slide_title="Intro", desired_type="background",
    )
    assert out is None


@pytest.mark.asyncio
async def test_picker_skips_llm_when_single_candidate():
    """One viable asset → no LLM call (saves cost + latency)."""
    db = _fake_db_with_assets([
        {"id": "a1", "type": "background", "category": "intro", "tags": ["industrial"], "description": "factory floor"},
    ])
    out = await pick_asset_for_slide(
        db, "c1", slide_title="Abertura", desired_type="background",
        desired_category="intro",
    )
    assert out is not None
    assert out["id"] == "a1"
    assert out["url"].endswith("/a1/file")
    assert out["source"] == "brand_library"


@pytest.mark.asyncio
async def test_picker_broadens_category_when_no_match():
    """If no asset is in the asked category, fall back to all-of-type
    instead of returning None (any branded image > generated)."""
    db = _fake_db_with_assets([
        {"id": "a1", "type": "background", "category": "content", "tags": [], "description": ""},
    ])
    out = await pick_asset_for_slide(
        db, "c1", slide_title="X", desired_type="background", desired_category="intro",
    )
    assert out is not None
    assert out["id"] == "a1"


@pytest.mark.asyncio
async def test_picker_uses_llm_when_multiple_candidates(monkeypatch):
    """With ≥2 candidates the LLM is consulted to pick one."""
    db = _fake_db_with_assets([
        {"id": "a1", "type": "background", "category": "intro", "tags": ["urbano"], "description": "rua"},
        {"id": "a2", "type": "background", "category": "intro", "tags": ["industrial"], "description": "fabrica"},
    ])
    # Mock the LLM picker to deterministically return a2
    async def _fake_llm(*_a, **_kw):
        return "a2"
    monkeypatch.setattr(
        "services.brand_library_picker._llm_pick_id", _fake_llm,
    )
    out = await pick_asset_for_slide(
        db, "c1", slide_title="Seguranca", desired_type="background",
        desired_category="intro",
    )
    assert out is not None
    assert out["id"] == "a2"


@pytest.mark.asyncio
async def test_picker_returns_none_when_llm_says_none(monkeypatch):
    """LLM's explicit 'none' must propagate — caller falls back to AI gen."""
    db = _fake_db_with_assets([
        {"id": "a1", "type": "background", "category": "generic", "tags": [], "description": ""},
        {"id": "a2", "type": "background", "category": "generic", "tags": [], "description": ""},
    ])
    async def _fake_llm(*_a, **_kw):
        return "none"
    monkeypatch.setattr(
        "services.brand_library_picker._llm_pick_id", _fake_llm,
    )
    out = await pick_asset_for_slide(
        db, "c1", slide_title="X", desired_type="background",
    )
    assert out is None


@pytest.mark.asyncio
async def test_picker_handles_llm_failure_gracefully(monkeypatch):
    """LLM down → return None (caller falls back to AI gen). No exception."""
    db = _fake_db_with_assets([
        {"id": "a1", "type": "background", "category": "generic", "tags": [], "description": ""},
        {"id": "a2", "type": "background", "category": "generic", "tags": [], "description": ""},
    ])
    async def _fake_llm(*_a, **_kw):
        return None
    monkeypatch.setattr(
        "services.brand_library_picker._llm_pick_id", _fake_llm,
    )
    out = await pick_asset_for_slide(
        db, "c1", slide_title="X", desired_type="background",
    )
    assert out is None


@pytest.mark.asyncio
async def test_picker_caches_catalog_per_company():
    """The catalog cache means subsequent picks for the same company don't
    re-query MongoDB — important when generating 20 slides in parallel."""
    db = _fake_db_with_assets([
        {"id": "a1", "type": "background", "category": "generic", "tags": [], "description": ""},
    ])
    # First call populates the cache
    await pick_asset_for_slide(db, "company_X", desired_type="background")
    # Reset the mock's call count
    db.company_assets_meta.find.reset_mock()
    # Second call must NOT hit the db
    await pick_asset_for_slide(db, "company_X", desired_type="background")
    assert db.company_assets_meta.find.call_count == 0


def test_invalidate_catalog_drops_only_target_company():
    _catalog_cache["company_A"] = [{"id": "a1"}]
    _catalog_cache["company_B"] = [{"id": "b1"}]
    invalidate_catalog("company_A")
    assert "company_A" not in _catalog_cache
    assert "company_B" in _catalog_cache  # other companies unaffected
