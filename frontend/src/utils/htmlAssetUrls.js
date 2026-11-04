import { getApiUrl } from './apiUrl';

// Display-only normalization. Controlled activities also keep media URLs in
// JSON/JS string values, not just HTML src attributes. Resolve those strings
// against the backend before an opaque srcdoc iframe interprets them.
export const resolveHtmlAssetUrls = (html, backend = getApiUrl()) => {
  if (typeof html !== 'string') return '';
  const base = (backend || '').replace(/\/+$/, '');
  if (!base) return html;
  const normalized = html.replace(
    /https?:\/\/[^/\s"']+(\/api\/(?:assets\/|projects\/))/g,
    '$1',
  );
  return normalized.replace(/(["'])\/api\//g, `$1${base}/api/`);
};
