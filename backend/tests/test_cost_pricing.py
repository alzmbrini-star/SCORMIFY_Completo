"""Tests for the cost-pricing endpoints + monetary fields in cost-report."""
from __future__ import annotations

import os
import requests


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


def _login():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@scormify.com", "password": "admin123"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["token"]


def _login_company():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@empresateste.com", "password": "empresa123"},
        timeout=10,
    )
    if r.status_code != 200:
        return None
    return r.json()["token"]


def test_get_pricing_super_admin():
    token = _login()
    r = requests.get(f"{BASE_URL}/api/admin/cost-pricing",
                       headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    # All standard rates exist
    for k in ("leonardo", "krea_default", "tutor", "elevenlabs", "heygen"):
        assert k in data["rates"]
        assert isinstance(data["rates"][k], (int, float))
    # Krea catalog has at least 10 items with effective price
    assert len(data["kreaCatalog"]) >= 10
    for m in data["kreaCatalog"]:
        assert "id" in m
        assert "default" in m
        assert "effective" in m
    # Defaults are returned for reference
    assert data["defaults"]["tutor"] == 0.005


def test_get_pricing_blocked_for_non_super_admin():
    other = _login_company()
    if not other:
        return
    r = requests.get(f"{BASE_URL}/api/admin/cost-pricing",
                       headers={"Authorization": f"Bearer {other}"}, timeout=10)
    assert r.status_code in (401, 403)


def test_put_pricing_overrides_rates():
    token = _login()
    # Set custom values
    r = requests.put(
        f"{BASE_URL}/api/admin/cost-pricing",
        headers={"Authorization": f"Bearer {token}"},
        json={"rates": {"tutor": 0.02}, "usdToBrl": 5.5,
              "kreaOverrides": {"flux-1-dev": 0.05}},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["rates"]["tutor"] == 0.02
    assert data["usdToBrl"] == 5.5
    assert data["kreaOverrides"]["flux-1-dev"] == 0.05
    # Other defaults are preserved
    assert data["rates"]["leonardo"] == 0.02

    # Reset to defaults so other tests don't break
    requests.put(
        f"{BASE_URL}/api/admin/cost-pricing",
        headers={"Authorization": f"Bearer {token}"},
        json={"rates": {"leonardo": 0.02, "krea_default": 0.04, "tutor": 0.005,
                          "elevenlabs": 0.05, "heygen": 0.5},
              "usdToBrl": 5.0, "kreaOverrides": {}},
        timeout=10,
    )


def test_put_pricing_rejects_negative():
    token = _login()
    r = requests.put(
        f"{BASE_URL}/api/admin/cost-pricing",
        headers={"Authorization": f"Bearer {token}"},
        json={"rates": {"tutor": -1}},
        timeout=10,
    )
    assert r.status_code == 400


def test_put_pricing_rejects_invalid_usd_brl():
    token = _login()
    r = requests.put(
        f"{BASE_URL}/api/admin/cost-pricing",
        headers={"Authorization": f"Bearer {token}"},
        json={"usdToBrl": 0},
        timeout=10,
    )
    assert r.status_code == 400


def test_put_pricing_blocked_for_non_super_admin():
    other = _login_company()
    if not other:
        return
    r = requests.put(
        f"{BASE_URL}/api/admin/cost-pricing",
        headers={"Authorization": f"Bearer {other}"},
        json={"rates": {"tutor": 0.99}},
        timeout=10,
    )
    assert r.status_code in (401, 403)


def test_cost_report_includes_monetary_fields():
    token = _login()
    r = requests.get(f"{BASE_URL}/api/admin/cost-report",
                       headers={"Authorization": f"Bearer {token}"}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    # Top-level pricing snapshot
    assert "pricing" in data
    assert "rates" in data["pricing"]
    assert "usdToBrl" in data["pricing"]
    # Each company has totalUsd + totalBrl
    for c in data["companies"]:
        assert "totalUsd" in c
        assert "totalBrl" in c
        assert isinstance(c["totalUsd"], (int, float))
        assert isinstance(c["totalBrl"], (int, float))
        # Each integration has usd + brl
        for k in ("krea", "leonardo", "tutor", "elevenlabs", "heygen"):
            assert "usd" in c[k]
            assert "brl" in c[k]


def test_cost_report_brl_is_usd_times_rate():
    token = _login()
    r = requests.get(f"{BASE_URL}/api/admin/cost-report",
                       headers={"Authorization": f"Bearer {token}"}, timeout=30)
    data = r.json()
    rate = data["pricing"]["usdToBrl"]
    assert rate > 0
    for c in data["companies"]:
        if c["totalUsd"] > 0:
            # Allow small rounding difference (0.05 BRL tolerance)
            expected = round(c["totalUsd"] * rate, 2)
            assert abs(c["totalBrl"] - expected) <= 0.05


def test_pricing_override_changes_report_totals():
    """Override the tutor rate, refresh the report, verify totals reflect it."""
    token = _login()
    # Take baseline
    base = requests.get(f"{BASE_URL}/api/admin/cost-report",
                          headers={"Authorization": f"Bearer {token}"}, timeout=30).json()
    base_total_tutor_usd = sum(c["tutor"]["usd"] for c in base["companies"])
    # Bump tutor to 10x
    requests.put(
        f"{BASE_URL}/api/admin/cost-pricing",
        headers={"Authorization": f"Bearer {token}"},
        json={"rates": {"tutor": 0.05}}, timeout=10,
    )
    bumped = requests.get(f"{BASE_URL}/api/admin/cost-report",
                            headers={"Authorization": f"Bearer {token}"}, timeout=30).json()
    bumped_total_tutor_usd = sum(c["tutor"]["usd"] for c in bumped["companies"])
    # Reset
    requests.put(
        f"{BASE_URL}/api/admin/cost-pricing",
        headers={"Authorization": f"Bearer {token}"},
        json={"rates": {"tutor": 0.005}}, timeout=10,
    )
    if base_total_tutor_usd > 0:
        # Ratio should be ~10x (allow rounding)
        ratio = bumped_total_tutor_usd / max(base_total_tutor_usd, 0.0001)
        assert ratio >= 9.5
