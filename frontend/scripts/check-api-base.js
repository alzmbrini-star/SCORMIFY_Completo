#!/usr/bin/env node
/**
 * Regression guard for production-deploy CORS bug.
 *
 * Background: React env vars are baked into the bundle at BUILD time. When
 * a deploy reuses an outdated `REACT_APP_BACKEND_URL` value (because the
 * Emergent deploy platform doesn't always pick up new defaults), every
 * fetch call that resolves the URL via `process.env.REACT_APP_BACKEND_URL`
 * starts hitting the wrong host → CORS errors. We solved this once by
 * routing all calls through `utils/apiUrl.js::getApiUrl()`, which returns
 * `window.location.origin` at runtime.
 *
 * This script ensures NO source file (outside the helper itself) ever
 * reads `process.env.REACT_APP_BACKEND_URL` again. Run from /app/frontend
 * with `node scripts/check-api-base.js`. Exits non-zero on violation.
 */
const fs = require('fs');
const path = require('path');

const SRC_DIR = path.join(__dirname, '..', 'src');
const HELPER_FILE = path.join(SRC_DIR, 'utils', 'apiUrl.js');
const NEEDLE = /process\.env\.REACT_APP_BACKEND_URL/;
const violations = [];

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full);
    } else if (/\.(jsx?|tsx?)$/.test(entry.name) && !entry.name.endsWith('.test.js')) {
      // The helper file is the ONLY legitimate place to read the env var
      // (used as fallback for SSR / Node environments where `window` is
      // undefined). Every other consumer must call `getApiUrl()`.
      if (full === HELPER_FILE) continue;
      const text = fs.readFileSync(full, 'utf8');
      if (NEEDLE.test(text)) {
        violations.push(path.relative(SRC_DIR, full));
      }
    }
  }
}

walk(SRC_DIR);

if (violations.length > 0) {
  console.error(`\n[check-api-base] FOUND ${violations.length} violation(s):\n`);
  for (const v of violations) console.error(`  - src/${v}`);
  console.error(
    `\nThese files must use getApiUrl() from utils/apiUrl.js instead.\n` +
    `See PRD changelog 2026-05-15: production deploy CORS fix.\n`,
  );
  process.exit(1);
}

console.log('[check-api-base] OK — no direct REACT_APP_BACKEND_URL reads outside the helper.');
process.exit(0);
