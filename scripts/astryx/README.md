# Optional static Astryx adapter

Run `npm ci --ignore-scripts`, then `npm run build` in this directory to
regenerate `backend/services/astryx_assets`. Node is only needed for generation,
not at server runtime or in a downloaded course. Dependencies are pinned in the
lockfile. The frontend dependency tree and its existing themes are unchanged.

The generated artifacts contain real server-rendered Astryx 0.7.16 Theme, Card
and Button markup, the corresponding precompiled CSS and MIT notice. Font assets
are deliberately omitted: the adapter uses the system font stack for offline
compatibility. No CDN, network call or AI generation is part of this adapter.
SCORM iframe sandbox does not allow form submissions; the activity therefore
uses an explicit button click handler and never navigates/submits a form.

Entry points: Editor -> Ferramentas -> Astryx, or Agent header -> Astryx.
Preview and exports are transient, not project mutations. Only explicit Create
uses an insert-only, owner-scoped idempotency key to create a separate project.
All existing-generation modes and assessment engines remain untouched.

`backend/tests/test_astryx_prototype.py` tests validation, escaping, tenant/role
checks, insert-only retries, real exporters, CSS preservation and Tutor guidance.
`scripts/build-astryx-qa.py` builds local demo artifacts with the real exporters,
including both classic and single-page HTML/SCORM. It never connects to MongoDB.

The mobile classic-player host override applies only when **every** slide has
one marked prototype element. Other courses retain their existing fixed-canvas
behavior. The prototype activity is **ungraded self-study**, not a replacement
for traditional Quiz or interactive image assessment; it does not send scores to
the LMS. Validate the final package in the customer's LMS before distributing.

Upstream: https://github.com/meta/astryx (MIT; see LICENSE.astryx.txt).

## New-course Agent design

Creation-scoped design templates (`?scope=creation`) additionally expose Astryx;
the default existing-course palette list remains the original six themes. The
Agent adapter (`services/astryx_agent.py`) renders approved semantic teaching
copy, not the laboratory's example text/questions. Protected activities, media
players and source-image slides retain their own builders. No existing course
is migrated on read or by applying a creation-only palette.

`lesson.css` is a parser-pruned Theme/Card stylesheet retaining the transitive
token dependencies. The full laboratory stylesheet is unchanged. This avoids
repeating all 150+ component styles in every lesson (which would exceed MongoDB's
document ceiling for long courses). The builder enforces a 45 KB stylesheet
budget; tests also bound the design overhead for 200 simple lessons.

`build-astryx-agent-qa.py` creates local fixtures for three subjects with classic
Quiz, an illustrated assessment and an original source-image slide. Run
`check-astryx-agent-browser.py` with the backend QA environment to check 390px and
desktop widths in an isolated headless Chrome, blocking all non-local requests.
No user browser profile, database, saved course or paid generation is used.
