# Gamma · first integration

Set `GAMMA_API_KEY` on the backend Render service only. Restart/deploy. No browser key, GPU or separate worker is required.

Dashboard → **Criar com Gamma**, for Editor/company admin/super admin. Quantity is freely editable from 1 to 100 (default 5). Gamma validates the account cap (10 on Free, up to 100 on paid plans). This integration requests PT-BR cards from Gamma 5, standard quality. Credits belong to the configured Gamma account; larger requests may cost more and no fixed price is promised. Request identifiers prevent duplicate paid submissions. An unknown submission is not retried automatically. Polling resumes when the dialog is reopened. Generation progress is not an SLA.

Every generation creates a NEW, empty project. No API accepts an existing course as target. PNG cards become durable WebP image bases; original text is not independently editable/searchable or accessible as native text. Add SCORMIFY overlays and interactions afterwards. Original PNG ZIP is retained in GridFS, with an authenticated download. Image assets are retained in the normal project asset store and included by the existing HTML/SCORM export pipeline. Deleting the new project removes its Gamma records/archive and its owned assets, not other courses.

Requested card count is a soft Gamma agent target. Persist `numCards` in the local job and show requested/actual counts; never silently pay for another run. Legacy jobs without numCards retain their original five-card target. Connectors are disabled; sharing is requested private but workspace policy can override it. Provider generation/export failure is distinct from a successful import; never report a failed export as imported. Private signed export URLs are server-only.

Limits: archive 80 MB, up to 102 imported images (100 requested + tolerance for provider variance), 160 MB uncompressed PNG total, 25 million pixels per image, WebP 2560 px longest edge/6 MB per card. Decode and persist one image at a time; never materialize a list of all converted images. No archive paths are extracted. No PDF/PPT import or native Gamma element editing is provided by this first phase.

Verification: backend `.venv/Scripts/python -m pytest tests/test_gamma.py tests/test_creator_tutor.py tests/test_creator_admin_guide.py tests/test_creator_faithful_guide.py tests/test_creator_scenario_guide.py`; frontend targeted Jest + production build.

Official contract: https://developers.gamma.app/agent-gamma-5/create-agent-generation and https://developers.gamma.app/agent-gamma-5/get-agent-generation-status .

## Theme and template selection

Dashboard → Criar com Gamma → Aparência da apresentação: automatic, theme OR template (mutually exclusive in Pydantic and transport). Read-only `/gamma/designs` proxies Gamma `/themes` (query/type/cursor, 50 items/page) or `/templates/search` (up to 25 hits per source). Authenticated creator roles only. Exposes names, textual color/style keywords and safe Gamma viewing links; no signed preview URLs or credentials. Catalogs use the server key workspace, not per-user Gamma accounts. Custom brand themes must be created in Gamma first. No new generation is needed to test discovery/selection; existing projects remain unchanged.

## Compact dialog UX

Content / Appearance / History tabs retain form state. Header and action footer remain outside the single scrollable body. Catalog cards paginate six at a time without nested scrolling; selected cards use both a green border and a text/check indicator. Swatches are explicitly **approximate**, derived locally from provider color keywords, never represented as official hex colors or exact previews. Unknown colors use a neutral palette. Only normal explicit Generate submits a paid request. Local Chrome QA: `python -m pytest tests/test_gamma_dialog_layout.py` after a frontend production build, using mocked API data and no external generation. Screenshots go to `artifacts/gamma-ui-desktop.png` and `artifacts/gamma-ui-mobile.png`.

Gamma opts into a native CompanySelector to avoid portal/layer conflicts. Other callers keep the existing Radix variant. Company lookup uses explicit auth headers, a bounded timeout and a visible retry on failure (no silent disabled field). Empty catalogs have a separate explanation. Super-admin and server-side tenant rules are unchanged. Selecting/retrying never creates a project or presentation.
