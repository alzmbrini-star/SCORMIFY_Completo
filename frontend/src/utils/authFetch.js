import { getApiUrl } from './apiUrl';

const TOKEN_KEY = 'scormify_auth_token';

/**
 * Fetch wrapper that includes auth credentials (cookies + token fallback)
 */
export async function authFetch(url, opts = {}) {
  const token = localStorage.getItem(TOKEN_KEY);
  const headers = { ...(opts.headers || {}) };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return fetch(url, {
    ...opts,
    credentials: 'include',
    headers,
  });
}

/**
 * Get the API base URL
 */
export const API_URL = getApiUrl();
