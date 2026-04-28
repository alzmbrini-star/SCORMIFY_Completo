"""SCORM 1.2 package exporter for the Single-Page (Página Única) presentation mode.

Wraps the single-page HTML produced by `single_page_exporter` in a SCORM 1.2
content package (imsmanifest.xml + XSDs + scorm-api.js + index.html) inside
a ZIP. The SCORM JS bridge:

  - On LMSInitialize:
      * Reads cmi.core.lesson_status; if "not attempted" sets to "incomplete"
      * Reads cmi.suspend_data + cmi.core.lesson_location to RESUME state
        (unlocked sections, completed interactives, quiz scores, scroll pos)
  - On every interactive completion:
      * cmi.suspend_data = JSON({unlocked, completed, quizScores, currentIndex})
      * cmi.core.lesson_location = String(currentSectionIndex)
      * LMSCommit("")
  - On every quiz answer:
      * cmi.interactions.{n}.id = "<quizId>:q<idx>"
      * cmi.interactions.{n}.type = "choice"
      * cmi.interactions.{n}.student_response = "<chosen index>"
      * cmi.interactions.{n}.result = "correct" | "wrong"
      * cmi.interactions.{n}.description = first 250 chars of question text
  - On every quiz finish:
      * cmi.core.score.raw = running pct across ALL quizzes
      * cmi.core.score.min = 0, .max = 100
  - On end-card reach:
      * cmi.core.lesson_status = "completed"
      * cmi.core.success_status (SCORM 2004) / cmi.core.lesson_status = "passed"
        when ALL sections unlocked AND every quiz scored >= 80%
      * LMSCommit("") + LMSFinish("") on beforeunload
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from .single_page_exporter import generate_single_page_html

logger = logging.getLogger(__name__)


# ----- SCORM 1.2 JS API bridge (exposed as window.SCORM)
_SCORM_API_JS = r"""// scorm-api.js — SCORM 1.2 runtime bridge for single-page courses
(function(){
  function findAPI(win, hops){
    hops = hops || 0;
    while (win && hops < 500) {
      if (win.API) return win.API;
      if (win === win.parent) break;
      win = win.parent;
      hops++;
    }
    return null;
  }

  var SCORM = {
    api: null,
    initialized: false,

    init: function(){
      this.api = findAPI(window) || (window.opener && findAPI(window.opener)) || null;
      if (!this.api) {
        console.warn('[SCORM] No LMS API found — running standalone');
        return false;
      }
      try {
        this.api.LMSInitialize('');
        this.initialized = true;
        var status = this.api.LMSGetValue('cmi.core.lesson_status');
        if (status === 'not attempted' || status === '') {
          this.api.LMSSetValue('cmi.core.lesson_status', 'incomplete');
        }
        this.api.LMSCommit('');
        return true;
      } catch (e) {
        console.error('[SCORM] init error', e);
        return false;
      }
    },

    setLocation: function(loc){
      if (!this.api || !this.initialized) return;
      try { this.api.LMSSetValue('cmi.core.lesson_location', String(loc).substring(0, 255)); } catch(e){}
    },

    saveSuspend: function(state){
      if (!this.api || !this.initialized) return;
      try {
        var s = JSON.stringify(state);
        // SCORM 1.2 cmi.suspend_data has a 4096 char limit
        if (s.length > 4000) s = s.substring(0, 4000);
        this.api.LMSSetValue('cmi.suspend_data', s);
      } catch(e){}
    },

    getSuspend: function(){
      if (!this.api || !this.initialized) return null;
      try {
        var raw = this.api.LMSGetValue('cmi.suspend_data');
        if (!raw) return null;
        return JSON.parse(raw);
      } catch(e){ return null; }
    },

    _interactionCount: 0,
    recordInteraction: function(id, description, response, correct){
      if (!this.api || !this.initialized) return;
      var n = this._interactionCount++;
      try {
        this.api.LMSSetValue('cmi.interactions.' + n + '.id', String(id).substring(0, 254));
        this.api.LMSSetValue('cmi.interactions.' + n + '.type', 'choice');
        if (description) {
          this.api.LMSSetValue('cmi.interactions.' + n + '.description', String(description).substring(0, 250));
        }
        this.api.LMSSetValue('cmi.interactions.' + n + '.student_response', String(response).substring(0, 254));
        this.api.LMSSetValue('cmi.interactions.' + n + '.result', correct ? 'correct' : 'wrong');
        this.api.LMSSetValue('cmi.interactions.' + n + '.time', new Date().toISOString().replace('T', ' ').substring(0, 19));
      } catch(e){}
    },

    setScore: function(raw, max, min){
      if (!this.api || !this.initialized) return;
      try {
        this.api.LMSSetValue('cmi.core.score.raw', String(Math.round(raw)));
        this.api.LMSSetValue('cmi.core.score.max', String(Math.round(max != null ? max : 100)));
        this.api.LMSSetValue('cmi.core.score.min', String(Math.round(min != null ? min : 0)));
      } catch(e){}
    },

    complete: function(passed){
      if (!this.api || !this.initialized) return;
      try {
        this.api.LMSSetValue('cmi.core.lesson_status', passed ? 'passed' : 'completed');
      } catch(e){}
    },

    commit: function(){
      if (!this.api || !this.initialized) return;
      try { this.api.LMSCommit(''); } catch(e){}
    },

    finish: function(){
      if (!this.api || !this.initialized) return;
      try {
        this.api.LMSCommit('');
        this.api.LMSFinish('');
        this.initialized = false;
      } catch(e){}
    }
  };

  window.SCORM = SCORM;
})();
"""

# ----- Manifest template (SCORM 1.2)
_MANIFEST = """<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="{identifier}" version="1.0"
    xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
    xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd
                        http://www.imsglobal.org/xsd/imsmd_rootv1p2p1 imsmd_rootv1p2p1.xsd
                        http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
    <metadata>
        <schema>ADL SCORM</schema>
        <schemaversion>1.2</schemaversion>
    </metadata>
    <organizations default="org1">
        <organization identifier="org1">
            <title>{title}</title>
            <item identifier="item1" identifierref="resource1">
                <title>{title}</title>
                <adlcp:masteryscore>80</adlcp:masteryscore>
            </item>
        </organization>
    </organizations>
    <resources>
        <resource identifier="resource1" type="webcontent" adlcp:scormtype="sco" href="index.html">
            <file href="index.html"/>
            <file href="scorm-api.js"/>
        </resource>
    </resources>
</manifest>
"""


def _safe_filename(project_name: str) -> str:
    name = re.sub(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}_?", "",
                  project_name, flags=re.IGNORECASE)
    name = re.sub(r"[^\w\s-]", "", name)
    name = name.replace(" ", "_").strip("_")
    return name or "course"


def export_single_page_scorm_package(
    project_doc: dict,
    storage_dir: str,
    output_dir: str,
    questions: Optional[list] = None,
    tutor_config: Optional[dict] = None,
    backend_url: str = "",
) -> str:
    """Build a SCORM 1.2 zip for the project's single-page mode and return
    the absolute path to the generated zip.
    """
    project_id = project_doc.get("id", "")
    project_name = project_doc.get("name", "course")
    course = project_doc.get("course") or {}
    course_title = (course.get("metadata") or {}).get("title") or project_name
    clean_title = re.sub(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}_?", "",
                          course_title, flags=re.IGNORECASE)

    assets_dir = os.path.join(storage_dir, project_id, "assets")
    if not os.path.exists(assets_dir):
        assets_dir = os.path.join(storage_dir, project_id)

    # Generate single-page HTML in SCORM mode (injects scorm-api hooks)
    html_content = generate_single_page_html(
        project_doc,
        assets_dir,
        base_url=backend_url,
        questions=questions,
        tutor_config=tutor_config,
        scorm_mode=True,
    )

    # Build package in a temp dir
    package_dir = Path(tempfile.mkdtemp(prefix="scorm_sp_"))
    try:
        (package_dir / "index.html").write_text(html_content, encoding="utf-8")
        (package_dir / "scorm-api.js").write_text(_SCORM_API_JS, encoding="utf-8")

        manifest = _MANIFEST.format(
            identifier=f"SCORM_SP_{project_id}",
            title=clean_title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
        )
        (package_dir / "imsmanifest.xml").write_text(manifest, encoding="utf-8")

        # Reuse XSDs from the legacy scorm exporter
        from .scorm_exporter import ADLCP_XSD, IMS_XML_XSD, IMSCP_XSD, IMSMD_XSD
        (package_dir / "adlcp_rootv1p2.xsd").write_text(ADLCP_XSD, encoding="utf-8")
        (package_dir / "ims_xml.xsd").write_text(IMS_XML_XSD, encoding="utf-8")
        (package_dir / "imscp_rootv1p1p2.xsd").write_text(IMSCP_XSD, encoding="utf-8")
        (package_dir / "imsmd_rootv1p2p1.xsd").write_text(IMSMD_XSD, encoding="utf-8")

        # ZIP
        clean_name = _safe_filename(project_name)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"{clean_name}_singlepage_{ts}.zip"
        zip_path = Path(output_dir) / zip_filename
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _dirs, files in os.walk(package_dir):
                for f in files:
                    fp = Path(root) / f
                    z.write(fp, fp.relative_to(package_dir))
        logger.info(f"SCORM single-page package created: {zip_path}")
        return str(zip_path)
    finally:
        shutil.rmtree(package_dir, ignore_errors=True)
