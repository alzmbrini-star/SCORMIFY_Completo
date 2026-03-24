import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getApiUrl } from '../utils/apiUrl';

const API_URL = getApiUrl();
const TOKEN_KEY = 'scormify_auth_token';

const AuthContext = createContext(null);

// Helper: build headers with token fallback
function authHeaders(extra = {}) {
  const headers = { ...extra };
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

// Helper: fetch with auth (cookies + token fallback)
async function authFetch(url, opts = {}) {
  const options = {
    ...opts,
    credentials: 'include',
    headers: authHeaders(opts.headers || {}),
  };
  return fetch(url, options);
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);

  // Check authentication status
  const checkAuth = useCallback(async () => {
    try {
      const response = await authFetch(`${API_URL}/api/auth/me`);

      if (response.ok) {
        let userData;
        try {
          userData = await response.json();
        } catch {
          setUser(null);
          localStorage.removeItem(TOKEN_KEY);
          return;
        }
        setUser(userData);
      } else {
        setUser(null);
        if (response.status === 401) {
          localStorage.removeItem(TOKEN_KEY);
        }
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
      setInitialized(true);
    }
  }, []);

  // Initial auth check
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Login with email/password
  const login = async (email, password) => {
    let response;
    try {
      response = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password })
      });
    } catch {
      throw new Error('Erro de conexao com o servidor. Verifique se o backend esta rodando e acessivel.');
    }

    let text;
    try {
      text = await response.text();
    } catch {
      throw new Error('Erro ao ler resposta do servidor.');
    }

    let data;
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(text || 'Resposta invalida do servidor');
    }

    if (!response.ok) {
      throw new Error(data.detail || 'Login failed');
    }

    // Save token to localStorage as fallback for blocked cookies
    if (data.token) {
      localStorage.setItem(TOKEN_KEY, data.token);
    }

    setUser(data.user);
    return data;
  };

  // Process Google OAuth callback
  const processGoogleAuth = async (sessionId) => {
    let response;
    try {
      response = await fetch(`${API_URL}/api/auth/google`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ session_id: sessionId })
      });
    } catch {
      throw new Error('Erro de conexao com o servidor.');
    }

    let text;
    try {
      text = await response.text();
    } catch {
      throw new Error('Erro ao ler resposta do servidor.');
    }

    let data;
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(text || 'Google authentication failed');
    }

    if (!response.ok) {
      throw new Error(data.detail || 'Google authentication failed');
    }

    if (data.token) {
      localStorage.setItem(TOKEN_KEY, data.token);
    }

    setUser(data.user);
    return data;
  };

  // Initiate Google login
  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  const loginWithGoogle = () => {
    const redirectUrl = window.location.origin + '/';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  // Logout
  const logout = async () => {
    try {
      await authFetch(`${API_URL}/api/auth/logout`, { method: 'POST' });
    } catch { /* ignore */ }
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
  };

  // Update user data locally
  const updateUser = (userData) => {
    setUser(prev => ({ ...prev, ...userData }));
  };

  // Check if user has permission for a feature
  const hasPermission = (permission) => {
    if (!user) return false;
    if (user.role === 'super_admin') return true;
    const company = user.company;
    if (!company) return false;
    return company.permissions?.[permission] === true;
  };

  // Check if user has a specific role
  const hasRole = (roles) => {
    if (!user) return false;
    if (typeof roles === 'string') roles = [roles];
    return roles.includes(user.role);
  };

  const value = {
    user,
    loading,
    initialized,
    login,
    loginWithGoogle,
    processGoogleAuth,
    logout,
    updateUser,
    hasPermission,
    hasRole,
    checkAuth,
    isAuthenticated: !!user,
    isSuperAdmin: user?.role === 'super_admin',
    isCompanyAdmin: user?.role === 'company_admin' || user?.role === 'super_admin',
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export { authFetch, authHeaders };

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;
