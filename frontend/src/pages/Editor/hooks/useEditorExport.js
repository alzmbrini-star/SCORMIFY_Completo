import { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { getApiUrl } from '../../../utils/apiUrl';

export function useEditorExport({ currentProject, exportScorm, fetchProject }) {
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [videoExportJobId, setVideoExportJobId] = useState(null);
  const [videoExportProgress, setVideoExportProgress] = useState(0);
  const [videoExportMessage, setVideoExportMessage] = useState('');

  const API_URL = getApiUrl();

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
      const response = await axios.post(`${API_URL}/api/course/${currentProject.id}/export-video`, {
        format,
        default_duration: 5.0,
      });
      const jobId = response.data.jobId;
      setVideoExportJobId(jobId);
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await axios.get(`${API_URL}/api/job/${jobId}`);
          const job = statusRes.data;
          setVideoExportProgress(job.progress || 0);
          setVideoExportMessage(job.message || '');
          if (job.status === 'completed') {
            clearInterval(pollInterval);
            setDownloadUrl(`${API_URL}${job.result.downloadUrl}`);
            setVideoExportJobId(null);
            setExportLoading(false);
            toast.success(`Video ${format.toUpperCase()} exportado!`);
          } else if (job.status === 'failed') {
            clearInterval(pollInterval);
            setVideoExportJobId(null);
            setExportLoading(false);
            toast.error(job.message || 'Falha na exportacao');
          }
        } catch (pollErr) {
          console.error('Poll error:', pollErr);
        }
      }, 2000);
    } catch (err) {
      console.error('Video export error:', err);
      toast.error('Falha ao iniciar exportacao: ' + (err.response?.data?.detail || err.message));
      setExportLoading(false);
    }
  };

  const resetExportDialog = () => {
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
