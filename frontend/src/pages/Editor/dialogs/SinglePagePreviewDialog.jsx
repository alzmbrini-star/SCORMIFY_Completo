import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../../components/ui/dialog';
import { Button } from '../../../components/ui/button';
import { Loader2, RefreshCw, X, Smartphone, Monitor, Tablet, ExternalLink } from 'lucide-react';
import { getApiUrl } from '../../../utils/apiUrl';
import {prepareSinglePagePreview,previewError} from '../../../utils/singlePagePreview';

const API = getApiUrl();

const VIEWPORTS = {
  desktop: { width: '100%', label: 'Desktop', icon: Monitor },
  tablet: { width: '820px', label: 'Tablet', icon: Tablet },
  mobile: { width: '414px', label: 'Mobile', icon: Smartphone },
};

/**
 * Live preview of the Single Page export. Fetches the generated HTML from
 * a background preview job, wraps the completed HTML in a Blob URL, and
 * renders it inside a sandboxed iframe with viewport switcher.
 */
export default function SinglePagePreviewDialog({ open, onOpenChange, projectId, projectName }) {
  const [blobUrl, setBlobUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [viewport, setViewport] = useState('desktop');
  const [progress,setProgress]=useState({progress:0,message:'Preparando prévia…'});
  const requestRef=useRef(null);
  const urlRef=useRef(null);

  const loadPreview = useCallback(async () => {
    if (!projectId) return;
    requestRef.current?.abort();
    const controller=new AbortController();requestRef.current=controller;
    setLoading(true);
    setError('');
    setProgress({progress:0,message:'Preparando prévia em segundo plano…'});
    try {
      const html=await prepareSinglePagePreview(API,projectId,{signal:controller.signal,onProgress:value=>{if(!controller.signal.aborted)setProgress(value);}});
      if(controller.signal.aborted)return;
      const blob = new Blob([html], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      if(urlRef.current)URL.revokeObjectURL(urlRef.current);
      urlRef.current=url;setBlobUrl(url);
    } catch (e) {
      if(!controller.signal.aborted)setError(previewError(e));
    } finally {
      if(!controller.signal.aborted)setLoading(false);
    }
  }, [projectId]);

  // Auto-load when dialog opens
  useEffect(() => {
    if(open&&projectId)loadPreview();
    return ()=>{requestRef.current?.abort();if(urlRef.current){URL.revokeObjectURL(urlRef.current);urlRef.current=null;}setBlobUrl(null);setError('');};
  }, [open, projectId,loadPreview]);

  const openInNewTab = () => {
    if (blobUrl) window.open(blobUrl, '_blank', 'noopener,noreferrer');
  };

  const vpConfig = VIEWPORTS[viewport];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-[95vw] w-[95vw] h-[95vh] p-0 bg-slate-950 border-slate-700 flex flex-col"
        data-testid="singlepage-preview-dialog"
      >
        <DialogHeader className="px-4 py-3 border-b border-slate-800 bg-slate-900 flex-row flex-wrap gap-2 items-center justify-between space-y-0 pr-12">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <DialogTitle className="text-amber-400 text-sm font-semibold truncate">
              Preview Página Única — {projectName || 'Curso'}
            </DialogTitle>
          </div>
          <div className="flex items-center gap-2">
            {/* Viewport switcher */}
            <div className="flex items-center gap-1 bg-slate-800 rounded-md p-1" role="group" aria-label="Viewport">
              {Object.entries(VIEWPORTS).map(([key, v]) => {
                const Icon = v.icon;
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setViewport(key)}
                    aria-label={v.label}
                    aria-pressed={viewport === key}
                    className={`p-1.5 rounded transition-colors ${
                      viewport === key ? 'bg-amber-500/20 text-amber-300' : 'text-slate-400 hover:text-slate-200'
                    }`}
                    data-testid={`preview-viewport-${key}`}
                  >
                    <Icon className="w-4 h-4" />
                  </button>
                );
              })}
            </div>
            <Button
              variant="ghost" size="sm"
              onClick={loadPreview}
              disabled={loading}
              className="h-8 text-slate-300 hover:text-white"
              data-testid="preview-refresh-btn"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              <span className="ml-1.5 text-xs">Atualizar</span>
            </Button>
            <Button
              variant="ghost" size="sm"
              onClick={openInNewTab}
              disabled={!blobUrl}
              className="h-8 text-slate-300 hover:text-white"
              data-testid="preview-open-newtab-btn"
            >
              <ExternalLink className="w-4 h-4" />
              <span className="ml-1.5 text-xs">Nova aba</span>
            </Button>
            <Button
              variant="ghost" size="icon"
              onClick={() => onOpenChange(false)}
              className="h-8 w-8 text-slate-400 hover:text-white"
              data-testid="preview-close-btn"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </DialogHeader>

        {/* Iframe canvas */}
        <div className="flex-1 overflow-auto bg-slate-900 flex items-center justify-center p-4">
          {loading && (
            <div className="flex flex-col items-center gap-3 text-slate-400" data-testid="preview-loading">
              <Loader2 className="w-8 h-8 animate-spin text-amber-400" />
              <p className="text-sm" role="status">{progress.message||'Preparando prévia…'}</p>
              <progress max="100" value={progress.progress||0} className="w-64" aria-label="Preparação da prévia"/>
              <p className="text-xs max-w-md text-center">Prévia da versão salva. Imagens e interações estão sendo organizadas; cursos maiores podem levar alguns minutos. Nenhum slide é alterado.</p>
            </div>
          )}
          {error && !loading && (
            <div className="text-center max-w-md" data-testid="preview-error">
              <h3 className="font-semibold text-white mb-2">A prévia não ficou pronta</h3>
              <p className="text-red-300 text-sm mb-3" role="alert">{error}</p>
              <Button onClick={loadPreview} variant="outline" size="sm">
                <RefreshCw className="w-4 h-4 mr-1.5" /> Tentar novamente
              </Button>
            </div>
          )}
          {blobUrl && !loading && !error && (
            <iframe
              src={blobUrl}
              title="Preview Single Page"
              data-testid="preview-iframe"
              className="bg-white shadow-2xl border-0"
              style={{
                width: vpConfig.width,
                height: '100%',
                maxWidth: '100%',
                transition: 'width .2s ease',
              }}
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
