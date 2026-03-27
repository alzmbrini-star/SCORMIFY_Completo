import { useState, useRef, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { getApiUrl } from '../../../utils/apiUrl';

const MAX_POLL_DURATION_MS = 10 * 60 * 1000; // 10 minutes max polling
const POLL_INTERVAL_MS = 3000; // 3s between polls
const MAX_CONSECUTIVE_ERRORS = 60; // Allow up to 3 min of 502s (60 * 3s = 180s)
const INITIAL_POST_RETRIES = 3;

export function useEditorExport({ currentProject, exportScorm, fetchProject }) {
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [videoExportJobId, setVideoExportJobId] = useState(null);
  const [videoExportProgress, setVideoExportProgress] = useState(0);
  const [videoExportMessage, setVideoExportMessage] = useState('');
  const pollTimerRef = useRef(null);

  const API_URL = getApiUrl();

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const handleExport = async () => {
    try {
      setExportLoading(true);
      const result = await exportScorm();
      setDownloadUrl(`${API_URL}${result.downloadUrl}`);
      toast.success('SCORM package ready!');
    } catch (err) {
      toast.error('Export failed');
    } finally {
      setExportLoading(false);
    }
  };

  const handleExportHTML = async () => {
    try {
      setExportLoading(true);
      const response = await axios.post(`${API_URL}/api/course/${currentProject.id}/export-html`);
      setDownloadUrl(`${API_URL}${response.data.downloadUrl}`);
      toast.success('HTML file ready!');
    } catch (err) {
      console.error('HTML export error:', err);
      toast.error('Export failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setExportLoading(false);
    }
  };

  const handleExportVideo = async (format = 'mp4') => {
    try {
      setExportLoading(true);
      setVideoExportProgress(0);
      setVideoExportMessage('Iniciando exportacao...');

      // Retry the initial POST with exponential backoff to handle proxy 502/504
      let response = null;
      let lastError = null;
      for (let attempt = 1; attempt <= INITIAL_POST_RETRIES; attempt++) {
        try {
          response = await axios.post(
            `${API_URL}/api/course/${currentProject.id}/export-video`,
            { format, default_duration: 5.0 },
            { timeout: 15000 } // 15s timeout per attempt
          );
          break; // Success
        } catch (err) {
          lastError = err;
          const status = err.response?.status;
          // Only retry on proxy/network errors (502, 503, 504, timeout)
          if (attempt < INITIAL_POST_RETRIES && (!status || status >= 502)) {
            const delay = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
            console.warn(`Export POST attempt ${attempt} failed (${status || 'network'}), retrying in ${delay}ms...`);
            setVideoExportMessage(`Tentativa ${attempt}/${INITIAL_POST_RETRIES}... reconectando`);
            await new Promise(r => setTimeout(r, delay));
          } else {
            throw err;
          }
        }
      }
      if (!response) throw lastError;

      const jobId = response.data.jobId;
      setVideoExportJobId(jobId);

      // Poll with resilience to intermittent 502/504 errors
      const pollStartTime = Date.now();
      let consecutiveErrors = 0;

      stopPolling(); // Clear any previous poll
      pollTimerRef.current = setInterval(async () => {
        // Safety: stop after max duration
        if (Date.now() - pollStartTime > MAX_POLL_DURATION_MS) {
          stopPolling();
          setVideoExportJobId(null);
          setExportLoading(false);
          toast.error('Exportacao excedeu o tempo limite (10 min).');
          return;
        }

        try {
          const statusRes = await axios.get(`${API_URL}/api/job/${jobId}`, { timeout: 10000 });
          if (consecutiveErrors > 0) {
            console.log(`Poll recovered after ${consecutiveErrors} errors`);
          }
          consecutiveErrors = 0; // Reset on success
          const job = statusRes.data;
          setVideoExportProgress(job.progress || 0);
          setVideoExportMessage(job.message || '');

          if (job.status === 'completed') {
            stopPolling();
            setDownloadUrl(`${API_URL}${job.result.downloadUrl}`);
            setVideoExportJobId(null);
            setExportLoading(false);
            toast.success(`Video ${format.toUpperCase()} exportado!`);
          } else if (job.status === 'failed') {
            stopPolling();
            setVideoExportJobId(null);
            setExportLoading(false);
            toast.error(job.message || 'Falha na exportacao');
          }
        } catch (pollErr) {
          consecutiveErrors++;
          const status = pollErr.response?.status;
          console.warn(`Poll error #${consecutiveErrors} (${status || 'network'}):`, pollErr.message);
          // 502/520 during video processing is EXPECTED in production (K8s Ingress timeout)
          // The backend is still processing - keep polling until it comes back
          if (consecutiveErrors >= 2) {
            setVideoExportMessage(
              consecutiveErrors < 10
                ? `Processando video no servidor... aguarde (${consecutiveErrors})`
                : `Servidor ocupado encodando video... aguarde, a exportacao continua em segundo plano (${consecutiveErrors})`
            );
          }
          if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
            stopPolling();
            setVideoExportJobId(null);
            setExportLoading(false);
            toast.error('Timeout de conexao. O video pode ter sido gerado - recarregue a pagina e verifique.');
          }
        }
      }, POLL_INTERVAL_MS);
    } catch (err) {
      console.error('Video export error:', err);
      toast.error('Falha ao iniciar exportacao: ' + (err.response?.data?.detail || err.message));
      setExportLoading(false);
    }
  };

  const resetExportDialog = () => {
    stopPolling();
    setDownloadUrl(null);
    setVideoExportJobId(null);
    setVideoExportProgress(0);
    setVideoExportMessage('');
  };

  return {
    showExportDialog, setShowExportDialog,
    exportLoading, downloadUrl,
    videoExportJobId, videoExportProgress, videoExportMessage,
    handleExport, handleExportHTML, handleExportVideo,
    resetExportDialog,
  };
}
