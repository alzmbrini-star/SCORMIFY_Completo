import React from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../../../components/ui/dialog';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { ScrollArea } from '../../../components/ui/scroll-area';
import {
  Loader2, Plus, RefreshCw, Video, Trash2, Clock, Film, FileText, Play, Check, X,
} from 'lucide-react';
import { formatDuration, formatDateTime, getStatusBadge } from '../utils';

export function VideoLibraryDialog({
  open, onOpenChange,
  videoLibraryItems, videoLibraryLoading, refreshingVideoId,
  loadVideoLibrary, refreshVideoStatus,
  handleAddLibraryVideoToSlide, handleDeleteLibraryVideo,
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Film className="w-5 h-5 text-cyan-500" />
            Biblioteca de Vídeos
          </DialogTitle>
          <DialogDescription>Vídeos gerados anteriormente. Clique em um vídeo para adicioná-lo ao slide.</DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-hidden">
          {videoLibraryLoading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="w-8 h-8 animate-spin text-cyan-500" />
            </div>
          ) : videoLibraryItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-center">
              <Film className="w-16 h-16 text-muted-foreground/30 mb-4" />
              <h3 className="text-lg font-medium text-muted-foreground">Nenhum vídeo encontrado</h3>
              <p className="text-sm text-muted-foreground/60 mt-1">Crie um vídeo com avatar usando o botão na barra de ferramentas</p>
            </div>
          ) : (
            <ScrollArea className="h-[calc(85vh-200px)]">
              <div className="space-y-3 p-1 pr-4">
                {videoLibraryItems.map((video) => (
                  <div key={video.video_id}
                    className={`group border rounded-lg overflow-hidden transition-all hover:border-cyan-500/50 hover:shadow-md ${video.status === 'completed' ? 'cursor-pointer' : 'opacity-80'}`}
                    onClick={() => video.status === 'completed' && handleAddLibraryVideoToSlide(video)}>
                    <div className="flex gap-4 p-4">
                      <div className="flex-shrink-0 w-32 h-20 bg-muted rounded overflow-hidden relative">
                        {video.thumbnail_url ? (
                          <img src={video.thumbnail_url} alt={video.title} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center"><Video className="w-8 h-8 text-muted-foreground/30" /></div>
                        )}
                        {video.duration && (
                          <div className="absolute bottom-1 right-1 px-1.5 py-0.5 bg-black/70 rounded text-[10px] text-white font-mono">{formatDuration(video.duration)}</div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <h4 className="font-medium truncate">{video.title || 'Sem título'}</h4>
                            <div className="flex items-center gap-2 mt-1">
                              {getStatusBadge(video.status)}
                              <span className="text-xs text-muted-foreground flex items-center gap-1"><Clock className="w-3 h-3" />{formatDateTime(video.created_at)}</span>
                            </div>
                          </div>
                          <div className="flex items-center gap-1">
                            {video.status !== 'completed' && (
                              <Button variant="ghost" size="sm" className="h-8 px-2"
                                onClick={(e) => { e.stopPropagation(); refreshVideoStatus(video.video_id); }}
                                disabled={refreshingVideoId === video.video_id} data-testid={`refresh-video-${video.video_id}`}>
                                {refreshingVideoId === video.video_id ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                                <span className="ml-1 text-xs">Atualizar</span>
                              </Button>
                            )}
                            {video.status === 'completed' && (
                              <Button variant="ghost" size="sm" className="h-8 px-2 text-cyan-600 hover:text-cyan-700 hover:bg-cyan-50"
                                onClick={(e) => { e.stopPropagation(); handleAddLibraryVideoToSlide(video); }} data-testid={`add-video-${video.video_id}`}>
                                <Plus className="w-4 h-4" /><span className="ml-1 text-xs">Adicionar</span>
                              </Button>
                            )}
                            <Button variant="ghost" size="sm" className="h-8 px-2 text-red-500 hover:text-red-600 hover:bg-red-50"
                              onClick={(e) => { e.stopPropagation(); handleDeleteLibraryVideo(video.video_id, video.title); }} data-testid={`delete-video-${video.video_id}`}>
                              <Trash2 className="w-4 h-4" /><span className="ml-1 text-xs">Excluir</span>
                            </Button>
                          </div>
                        </div>
                        {video.script && (
                          <div className="mt-2 p-2 bg-muted/50 rounded text-xs text-muted-foreground max-h-16 overflow-hidden relative">
                            <div className="flex items-start gap-1.5"><FileText className="w-3 h-3 flex-shrink-0 mt-0.5" /><p className="line-clamp-2">{video.script}</p></div>
                            <div className="absolute bottom-0 left-0 right-0 h-4 bg-gradient-to-t from-muted/50 to-transparent" />
                          </div>
                        )}
                      </div>
                    </div>
                    {video.status === 'completed' && video.video_url && (
                      <div className="hidden group-hover:block border-t bg-black" onClick={(e) => e.stopPropagation()}>
                        <video src={video.video_url} controls className="w-full max-h-48" preload="metadata" />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </div>

        <DialogFooter className="gap-2 mt-4">
          <Button variant="outline" onClick={loadVideoLibrary} disabled={videoLibraryLoading}>
            {videoLibraryLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
            Atualizar Lista
          </Button>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Fechar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
