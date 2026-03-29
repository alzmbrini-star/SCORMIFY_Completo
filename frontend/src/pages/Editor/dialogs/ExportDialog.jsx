import React from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../../../components/ui/dialog';
import { Button } from '../../../components/ui/button';
import { Switch } from '../../../components/ui/switch';
import { Download, Film } from 'lucide-react';
import { getApiUrl } from '../../../utils/apiUrl';

export function ExportDialog({
  open, onOpenChange, resetExportDialog,
  downloadUrl, downloadFilename, exportLoading,
  videoExportJobId, videoExportProgress, videoExportMessage,
  handleExport, handleExportHTML, handleExportVideo,
  currentProject, fetchProject,
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => {
      onOpenChange(o);
      if (!o) resetExportDialog();
    }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Exportar Curso</DialogTitle>
          <DialogDescription>Escolha o formato de exportação do seu curso.</DialogDescription>
        </DialogHeader>
        <div className="py-4 space-y-4">
          {downloadUrl ? (
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4">
                <Download className="w-8 h-8 text-green-500" />
              </div>
              <p className="mb-4">Seu arquivo está pronto!</p>
              <Button
                className="w-full"
                data-testid="download-export-btn"
                onClick={async () => {
                  try {
                    if (downloadUrl.startsWith('blob:')) {
                      const link = document.createElement('a');
                      link.href = downloadUrl;
                      link.download = downloadFilename || 'video.webm';
                      document.body.appendChild(link);
                      link.click();
                      document.body.removeChild(link);
                    } else {
                      const response = await fetch(downloadUrl);
                      const blob = await response.blob();
                      const filename = downloadUrl.split('/').pop() || 'export';
                      const url = window.URL.createObjectURL(blob);
                      const link = document.createElement('a');
                      link.href = url;
                      link.download = filename;
                      document.body.appendChild(link);
                      link.click();
                      document.body.removeChild(link);
                      window.URL.revokeObjectURL(url);
                    }
                  } catch (error) {
                    console.error('Download error:', error);
                    window.open(downloadUrl, '_blank');
                  }
                }}
              >
                Baixar Arquivo
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 border rounded-lg bg-muted/30">
                <div className="flex items-center gap-2">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 11v8a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-8"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/><path d="M14 11h3a1 1 0 0 1 1 1v1a2 2 0 0 1-2 2h-2"/><path d="M14 15v5a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1v-5"/></svg>
                  <div>
                    <span className="text-sm font-medium">Plugin LIBRAS (VLibras)</span>
                    <p className="text-[10px] text-muted-foreground">Avatar de acessibilidade em Língua de Sinais</p>
                  </div>
                </div>
                <Switch
                  data-testid="vlibras-toggle"
                  key={`vlibras-${currentProject?.enableVlibras}`}
                  defaultChecked={currentProject?.enableVlibras !== false}
                  onCheckedChange={(newVal) => {
                    fetch(`${getApiUrl()}/api/projects/${currentProject.id}`, {
                      method: 'PUT',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ enableVlibras: newVal })
                    }).then(() => fetchProject(currentProject.id))
                      .catch(err => console.error('VLibras toggle error:', err));
                  }}
                />
              </div>

              <div className="p-4 border rounded-lg hover:border-primary/50 transition-colors">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center shrink-0">
                    <span className="text-xl">📦</span>
                  </div>
                  <div className="flex-1">
                    <h4 className="font-medium mb-1">SCORM 1.2</h4>
                    <p className="text-sm text-muted-foreground mb-3">Pacote compatível com LMS (Moodle, Blackboard, etc.)</p>
                    <Button onClick={handleExport} disabled={exportLoading} className="w-full gap-2" size="sm" data-testid="generate-scorm-btn">
                      <Download className="w-4 h-4" /> Gerar SCORM
                    </Button>
                  </div>
                </div>
              </div>

              <div className="p-4 border rounded-lg hover:border-primary/50 transition-colors">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center shrink-0">
                    <span className="text-xl">🌐</span>
                  </div>
                  <div className="flex-1">
                    <h4 className="font-medium mb-1">HTML Standalone</h4>
                    <p className="text-sm text-muted-foreground mb-3">Arquivo único para visualizar em qualquer navegador</p>
                    <Button onClick={handleExportHTML} disabled={exportLoading} variant="outline" className="w-full gap-2" size="sm" data-testid="generate-html-btn">
                      <Download className="w-4 h-4" /> Gerar HTML
                    </Button>
                  </div>
                </div>
              </div>

              <div className="p-4 border rounded-lg hover:border-primary/50 transition-colors">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center shrink-0">
                    <Film className="w-5 h-5 text-red-400" />
                  </div>
                  <div className="flex-1">
                    <h4 className="font-medium mb-1">Vídeo</h4>
                    <p className="text-sm text-muted-foreground mb-3">Exportar como vídeo com narrações e vídeos HeyGen/YouTube</p>
                    {videoExportJobId ? (
                      <div data-testid="video-export-progress">
                        <div className="w-full bg-muted rounded-full h-2 mb-2">
                          <div className="bg-red-500 h-2 rounded-full transition-all duration-500" style={{ width: `${videoExportProgress}%` }} />
                        </div>
                        <p className="text-xs text-muted-foreground">{videoExportMessage}</p>
                      </div>
                    ) : (
                      <div>
                        <Button onClick={() => handleExportVideo()} disabled={exportLoading} variant="outline" className="w-full gap-2 border-red-500/30 text-red-400 hover:bg-red-500/10" size="sm" data-testid="generate-video-btn">
                          <Film className="w-4 h-4" /> Gerar Video
                        </Button>
                        <p className="text-[10px] text-muted-foreground mt-1.5 text-center">MP4 ou WebM — gerado no navegador</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
