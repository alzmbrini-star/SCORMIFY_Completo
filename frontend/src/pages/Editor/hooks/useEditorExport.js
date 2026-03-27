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
