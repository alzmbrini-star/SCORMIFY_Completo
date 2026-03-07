import React from 'react';
import { getApiUrl } from '../../utils/apiUrl';

// Helper to get full asset URL for thumbnails
export const getThumbAssetUrl = (src) => {
  if (!src) return '';
  const API_URL = getApiUrl();
  if (src.startsWith('http')) {
    const assetMatch = src.match(/https?:\/\/[^/]+\/api\/projects\/([^/]+)\/assets\/(.+)/);
    if (assetMatch) return `${API_URL}/api/projects/${assetMatch[1]}/assets/${assetMatch[2]}`;
    const globalAssetMatch = src.match(/https?:\/\/[^/]+\/api\/assets\/(.+)/);
    if (globalAssetMatch) return `${API_URL}/api/assets/${globalAssetMatch[1]}`;
    return src;
  }
  if (src.startsWith('/api/')) return `${API_URL}${src}`;
  return src;
};

export const formatTime = (seconds) => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

export const formatDuration = (seconds) => {
  if (!seconds) return '--:--';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

export const formatDateTime = (isoString) => {
  if (!isoString) return 'Data desconhecida';
  const date = new Date(isoString);
  return date.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

export const getStatusBadge = (status) => {
  switch (status) {
    case 'completed':
      return <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded-full">Concluido</span>;
    case 'processing':
      return <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 text-xs rounded-full animate-pulse">Processando</span>;
    case 'pending':
      return <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded-full">Pendente</span>;
    case 'failed':
      return <span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs rounded-full">Falhou</span>;
    default:
      return <span className="px-2 py-0.5 bg-gray-500/20 text-gray-400 text-xs rounded-full">{status}</span>;
  }
};
