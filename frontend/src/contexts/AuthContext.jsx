import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);

  // Check authentication status
  const checkAuth = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/auth/me`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
      } else {
        setUser(null);
      }
    } catch (error) {
      console.error('Auth check failed:', error);
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
    const response = await fetch(`${API_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password })
    });

    // Clone response to safely read it (prevents "body stream already read" error)
    const responseClone = response.clone();
    
    if (!response.ok) {
      try {
        const error = await response.json();
        throw new Error(error.detail || 'Login failed');
      } catch (e) {
        // If JSON parsing fails, try to get text
        if (e.name === 'SyntaxError') {
          const text = await responseClone.text();
          throw new Error(text || 'Login failed');
        }
        throw e;
      }
    }

    const data = await response.json();
    setUser(data.user);
    return data;
  };

  // Process Google OAuth callback
  const processGoogleAuth = async (sessionId) => {
    const response = await fetch(`${API_URL}/api/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ session_id: sessionId })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Google authentication failed');
    }

    const data = await response.json();
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
      await fetch(`${API_URL}/api/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      });
    } catch (error) {
      console.error('Logout error:', error);
    }
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
    
    // Check company permissions
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

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;
