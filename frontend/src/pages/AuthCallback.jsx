import React, { useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';

export default function AuthCallback() {
  const navigate = useNavigate();
  const location = useLocation();
  const { processGoogleAuth } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    // Prevent double processing in StrictMode
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processAuth = async () => {
      try {
        // Extract session_id from URL hash
        const hash = location.hash;
        const params = new URLSearchParams(hash.replace('#', ''));
        const sessionId = params.get('session_id');

        if (!sessionId) {
          toast.error('Sessão inválida');
          navigate('/login', { replace: true });
          return;
        }

        // Process the session with backend
        await processGoogleAuth(sessionId);
        toast.success('Login realizado com sucesso!');
        
        // Navigate to dashboard
        navigate('/', { replace: true });
      } catch (error) {
        console.error('Auth callback error:', error);
        toast.error(error.message || 'Erro na autenticação');
        navigate('/login', { replace: true });
      }
    };

    processAuth();
  }, [location, navigate, processGoogleAuth]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500 mx-auto mb-4"></div>
        <p className="text-white">Processando autenticação...</p>
      </div>
    </div>
  );
}
