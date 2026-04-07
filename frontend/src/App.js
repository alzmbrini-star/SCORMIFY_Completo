import React from 'react';
import { BrowserRouter, Routes, Route, useLocation, Navigate } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { ProjectProvider } from './contexts/ProjectContext';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Toaster } from './components/ui/sonner';
import Dashboard from './pages/Dashboard';
import Editor from './pages/Editor';
import Agent from './pages/Agent';
import Login from './pages/Login';
import Admin from './pages/Admin';
import AuthCallback from './pages/AuthCallback';
import './index.css';

// Protected Route component
function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

// Route guard for Aprovador role - only allows /agent access
function AprovadorGuard({ children }) {
  const { isAprovador, loading } = useAuth();
  
  if (loading) return null;
  
  if (isAprovador) {
    return <Navigate to="/agent" replace />;
  }

  return children;
}

// App Router - handles OAuth callback detection
function AppRouter() {
  const location = useLocation();

  // Check URL fragment for session_id (Google OAuth callback)
  // This MUST happen synchronously during render, NOT in useEffect
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/admin" element={
        <ProtectedRoute>
          <AprovadorGuard>
            <Admin />
          </AprovadorGuard>
        </ProtectedRoute>
      } />
      <Route path="/agent" element={
        <ProtectedRoute>
          <Agent />
        </ProtectedRoute>
      } />
      <Route path="/editor/:projectId" element={
        <ProtectedRoute>
          <AprovadorGuard>
            <Editor />
          </AprovadorGuard>
        </ProtectedRoute>
      } />
      <Route path="/" element={
        <ProtectedRoute>
          <AprovadorGuard>
            <Dashboard />
          </AprovadorGuard>
        </ProtectedRoute>
      } />
    </Routes>
  );
}

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ProjectProvider>
          <BrowserRouter>
            <AppRouter />
          </BrowserRouter>
          <Toaster position="top-right" />
        </ProjectProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
