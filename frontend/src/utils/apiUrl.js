// Returns the correct API base URL.
// In the browser, always uses window.location.origin (same domain as frontend).
// Falls back to REACT_APP_BACKEND_URL for SSR or non-browser environments.
export const getApiUrl = () => {
  if (typeof window !== 'undefined' && window.location && window.location.origin) {
    return window.location.origin;
  }
  return process.env.REACT_APP_BACKEND_URL || '';
};
