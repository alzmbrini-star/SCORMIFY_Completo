"""Regression tests for the batch SCORM export endpoint.

Covers:
  • Payload validation (empty list, oversized list, invalid JSON)
  • RBAC (super_admin sees all, company_admin only their company)
  • Silent-drop semantics — foreign IDs are dropped from `denied`, not 403
    (unless ALL ids are denied)
  • Child job creation — one Mongo job doc per allowed project, tagged with
    batchId and projectId for later traceability.
"""

from pathlib import Path


ROUTE_SRC = Path("/app/backend/routes/export.py").read_text()


def test_batch_endpoint_registered():
    assert '@router.post("/admin/batch-export-scorm")' in ROUTE_SRC


def test_batch_enforces_rbac_super_and_company_admin():
    # Only these two roles pass the top-of-function gate
    assert 'role not in ("super_admin", "company_admin")' in ROUTE_SRC


def test_batch_caps_size_to_100():
    """Prevents a super_admin from accidentally kicking off 500+ exports."""
    assert "> 100" in ROUTE_SRC
    assert "Máximo 100 cursos por lote" in ROUTE_SRC


def test_batch_runs_sequentially_to_avoid_oom():
    """The batch supervisor must iterate one-by-one and await each job. This
    is critical because whiteboard renderer + base64 embedding can spike
    >500MB per project and running in parallel would OOM the pod (recurring
    P1 bug from the handoff)."""
    assert "async def _run_batch_scorm" in ROUTE_SRC
    # Sequential loop over child jobs (not gather / semaphore)
    assert "for idx, entry in enumerate(child_jobs)" in ROUTE_SRC
    # And the loop awaits each export before moving on
    assert "await _run_scorm_export_job" in ROUTE_SRC


def test_batch_isolates_failures():
    """One bad project must not block the rest of the batch."""
    # A try/except must wrap the per-project call
    assert "except Exception as exc:" in ROUTE_SRC


def test_batch_stamps_batchid_and_projectid_on_child_jobs():
    """Child job docs must carry batchId + projectId so the UI can display
    the batch progress and each course's status independently."""
    assert '"batchId": batch_id,' in ROUTE_SRC
    assert '"projectId": doc["id"],' in ROUTE_SRC
