import { useState, useRef, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { getApiUrl } from '../../../utils/apiUrl';
import { generateVideoClientSide } from '../../../utils/clientVideoExport';

export function useEditorExport({ currentProject, exportScorm, fetchProject }) {
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [downloadFilename, setDownloadFilename] = useState('export');
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

  /**
   * Poll a job until it completes or fails. Returns the final result object.
   * Used by SCORM/HTML async-export endpoints which now return `{jobId}`
   * immediately and do the heavy work in the background. Polling keeps the
   * gateway/proxy timeout (~100s) from killing the user's request.
   */
  const pollJobUntilDone = useCallback(async (jobId, { intervalMs = 2000, timeoutMs = 600000, onProgress } = {}) => {
    const start = Date.now();
    return new Promise((resolve, reject) => {
      const tick = async () => {
        if (Date.now() - start > timeoutMs) {
          reject(new Error('Timeout aguardando exportacao'));
          return;
        }
        try {
          const r = await axios.get(`${API_URL}/api/job/${jobId}`);
          const data = r.data || {};
          if (typeof onProgress === 'function') onProgress(data);
          if (data.status === 'completed' || data.status === 'done') {
            resolve(data);
            return;
          }
          if (data.status === 'failed' || data.status === 'error') {
            reject(new Error(data.message || 'Falha na exportacao'));
            return;
          }
          // Still processing — schedule another poll.
          setTimeout(tick, intervalMs);
        } catch (e) {
          // Tolerate transient errors (proxy 502, network blips) for a few rounds.
          setTimeout(tick, intervalMs);
        }
      };
      tick();
    });
  }, [API_URL]);

  const handleExport = async () => {
    try {
      setExportLoading(true);
      setVideoExportProgress(0);
      setVideoExportMessage('Iniciando exportacao SCORM...');
      const singlePage = !!currentProject?.singlePageMode;
      const startResp = await exportScorm({ singlePage });
      // Backwards compat: legacy synchronous response with downloadUrl
      if (startResp?.downloadUrl && !startResp.jobId) {
        setDownloadUrl(`${API_URL}${startResp.downloadUrl}`);
        const modeLabel = startResp?.mode === 'single_page' ? 'Página Única' : 'Tradicional';
        toast.success(`SCORM (${modeLabel}) pronto!`);
        return;
      }
      // New async-job pattern
      if (!startResp?.jobId) throw new Error('Resposta inesperada do servidor');
      const finalJob = await pollJobUntilDone(startResp.jobId, {
        onProgress: (j) => {
          if (j.progress != null) setVideoExportProgress(j.progress);
          if (j.message) setVideoExportMessage(j.message);
        },
      });
      const result = finalJob.result || {};
      if (!result.downloadUrl) throw new Error('Download URL ausente na resposta');
      setDownloadUrl(`${API_URL}${result.downloadUrl}`);
      const modeLabel = result?.mode === 'single_page' ? 'Página Única' : 'Tradicional';
      toast.success(`SCORM (${modeLabel}) pronto!`);
    } catch (err) {
      console.error('SCORM export error:', err);
      toast.error('Falha na exportacao: ' + (err.message || 'Erro desconhecido'));
    } finally {
      setExportLoading(false);
      setVideoExportProgress(0);
      setVideoExportMessage('');
    }
  };

  const handleExportHTML = async () => {
    try {
      setExportLoading(true);
      setVideoExportProgress(0);
      setVideoExportMessage('Iniciando exportacao HTML...');
      const singlePage = !!currentProject?.singlePageMode;
      const response = await axios.post(
        `${API_URL}/api/course/${currentProject.id}/export-html`,
        { singlePage },
      );
      const startResp = response.data || {};
      // Backwards compat
      if (startResp.downloadUrl && !startResp.jobId) {
        setDownloadUrl(`${API_URL}${startResp.downloadUrl}`);
        const modeLabel = startResp?.mode === 'single_page' ? 'Página Única' : 'Tradicional';
        toast.success(`HTML (${modeLabel}) pronto!`);
        return;
      }
      if (!startResp.jobId) throw new Error('Resposta inesperada do servidor');
      const finalJob = await pollJobUntilDone(startResp.jobId, {
        onProgress: (j) => {
          if (j.progress != null) setVideoExportProgress(j.progress);
          if (j.message) setVideoExportMessage(j.message);
        },
      });
      const result = finalJob.result || {};
      if (!result.downloadUrl) throw new Error('Download URL ausente na resposta');
      setDownloadUrl(`${API_URL}${result.downloadUrl}`);
      const modeLabel = result?.mode === 'single_page' ? 'Página Única' : 'Tradicional';
      toast.success(`HTML (${modeLabel}) pronto!`);
    } catch (err) {
      console.error('HTML export error:', err);
      toast.error('Falha na exportacao: ' + (err.response?.data?.detail || err.message));
    } finally {
      setExportLoading(false);
      setVideoExportProgress(0);
      setVideoExportMessage('');
    }
  };

  const handleExportVideo = async () => {
    try {
      setExportLoading(true);
      setVideoExportProgress(0);
      setVideoExportMessage('Preparando exportacao de video...');
      setVideoExportJobId('client-side');

      const { blob, filename } = await generateVideoClientSide({
        apiUrl: API_URL,
        projectId: currentProject.id,
        defaultDuration: 5.0,
        onProgress: (progress, message) => {
          setVideoExportProgress(progress);
          setVideoExportMessage(message);
        },
      });

      const blobUrl = URL.createObjectURL(blob);
      setDownloadUrl(blobUrl);
      setDownloadFilename(filename);
      setVideoExportJobId(null);
      setExportLoading(false);
      const ext = filename.split('.').pop()?.toUpperCase() || 'Video';
      toast.success(`Video ${ext} exportado com sucesso!`);

      // Auto-trigger download
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

    } catch (err) {
      console.error('Video export error:', err);
      toast.error('Falha na exportacao: ' + (err.message || 'Erro desconhecido'));
      setVideoExportJobId(null);
      setExportLoading(false);
    }
  };

  const resetExportDialog = () => {
    stopPolling();
    if (downloadUrl && downloadUrl.startsWith('blob:')) {
      URL.revokeObjectURL(downloadUrl);
    }
    setDownloadUrl(null);
    setDownloadFilename('export');
    setVideoExportJobId(null);
    setVideoExportProgress(0);
    setVideoExportMessage('');
  };

  return {
    showExportDialog, setShowExportDialog,
    exportLoading, downloadUrl, downloadFilename,
    videoExportJobId, videoExportProgress, videoExportMessage,
    handleExport, handleExportHTML, handleExportVideo,
    resetExportDialog,
  };
}
