// Returns the correct API base URL.
//
// Production environments deploy the frontend and backend behind the
// SAME hostname (the K8s ingress routes /api/* to the backend service).
// So in the browser we ALWAYS prefer `window.location.origin` — that
// way, even if `REACT_APP_BACKEND_URL` was baked into the bundle with
// the wrong value (e.g. a stale URL from a previous deploy), we still
// hit the right backend.
//
// The env var is only used as a fallback for SSR / Node-side rendering
// where `window` isn't defined.
export const getApiUrl = () => {
  if (typeof window !== 'undefined' && window.location && window.location.origin) {
    return window.location.origin;
  }
  return process.env.REACT_APP_BACKEND_URL || '';
};
