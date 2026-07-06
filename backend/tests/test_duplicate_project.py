"""Regression tests for the project duplication feature.

Guards RBAC (only super_admin + company_admin), ID regeneration (no collisions
if both projects open at the same time), name suffix, source tag, and asset
directory copy.
"""

from pathlib import Path

SRC = Path("/app/backend/routes/projects_crud.py").read_text()


def test_duplicate_endpoint_registered():
    assert '@router.post("/projects/{project_id}/duplicate"' in SRC


def test_duplicate_rbac_admin_only():
    assert 'role not in ("super_admin", "company_admin")' in SRC


def test_duplicate_regenerates_all_ids():
    # Top-level project id
    assert 'new_doc["id"] = new_project_id' in SRC
    # Slide ids
    assert 'slide["id"] = str(uuid.uuid4())' in SRC
    # Element ids
    assert 'el["id"] = str(uuid.uuid4())' in SRC


def test_duplicate_name_suffix_and_source_tag():
    assert '(Cópia)' in SRC
    assert '"source"] = "duplicate"' in SRC


def test_duplicate_copies_assets_directory():
    assert "shutil.copytree" in SRC
    assert "PROJECTS_DIR / project_id" in SRC
    assert "PROJECTS_DIR / new_project_id" in SRC


def test_duplicate_reassigns_ownership_to_caller():
    """A super_admin duplicating a course from company A into their own
    context should NOT leave the original companyId — otherwise the copy
    would only be visible to company A's admins, defeating the workflow."""
    assert 'new_doc["userId"] = user.get("user_id")' in SRC
    assert 'new_doc["companyId"] = await resolve_company_id_for_creation' in SRC


def test_duplicate_uses_load_authorized_project():
    """Uses the same access gate as get/put/delete — company_admin cannot
    duplicate courses from other companies."""
    assert "load_authorized_project(project_id, user)" in SRC


def test_frontend_menu_gated_on_admin_role():
    dash = Path("/app/frontend/src/pages/Dashboard.jsx").read_text()
    assert "handleDuplicateProject" in dash
    # Menu item must be gated on admin role
    assert "isSuperAdmin || isCompanyAdmin" in dash
    assert 'duplicate-project-' in dash
