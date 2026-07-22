import React, { useState, useCallback } from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../../../components/ui/dialog';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../components/ui/tabs';
import { Loader2, Sparkles, Plus, Check, Code, Image, Palette, Music, Mic, Trash2, FileText, Upload } from 'lucide-react';
import RichTextEditor from '../../../components/RichTextEditor';

// Gallery image with auto-retry on load failure
function GalleryImage({ src, alt }) {
  const [retries, setRetries] = useState(0);
  const [failed, setFailed] = useState(false);

  const handleError = useCallback(() => {
    if (retries < 2) {
      setTimeout(() => setRetries(r => r + 1), 1500 * (retries + 1));
    } else {
      setFailed(true);
    }
  }, [retries]);

  if (failed) {
    return (
      <div className="w-full h-full bg-slate-800 flex items-center justify-center">
        <div className="text-center p-2">
          <Image className="w-6 h-6 text-slate-500 mx-auto mb-1" />
          <p className="text-[9px] text-slate-500 leading-tight">{alt?.slice(0, 60) || 'Imagem'}</p>
        </div>
      </div>
    );
  }

  return <img src={`${src}${retries > 0 ? `?r=${retries}` : ''}`} alt={alt} className="w-full h-full object-cover" loading="lazy" onError={handleError} />;
}

export function MediaDialog({ open, onOpenChange, videoUrl, setVideoUrl, handleAddMedia }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Adicionar Vídeo</DialogTitle></DialogHeader>
        <div className="py-4">
          <Input placeholder="YouTube, Vimeo ou Bunny Stream (URL ou iframe)" value={videoUrl} onChange={(e) => setVideoUrl(e.target.value)} data-testid="video-url-input" />
          <p className="text-xs text-muted-foreground mt-2">
            Cole uma URL do YouTube, Vimeo ou Bunny Stream. Para o Bunny, também aceitamos o snippet <code>&lt;iframe&gt;</code> completo copiado do painel.
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={handleAddMedia} data-testid="add-video-confirm-btn">Add Video</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function AudioDialog({
  open, onOpenChange,
  audioFile, setAudioFile, audioTarget, setAudioTarget,
  audioType = 'narration', setAudioType,
  handleAudioUpload,
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => {
      onOpenChange(o);
      if (!o) { setAudioFile(null); setAudioTarget('slide'); if (setAudioType) setAudioType('narration'); }
    }}>
      <DialogContent>
        <DialogHeader><DialogTitle>Adicionar Áudio</DialogTitle></DialogHeader>
        <div className="py-4 space-y-4">
          {audioFile && (
            <div className="flex items-center gap-3 p-3 bg-muted rounded-lg">
              <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center"><Music className="w-5 h-5 text-primary" /></div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{audioFile.name}</p>
                <p className="text-xs text-muted-foreground">{(audioFile.size / 1024 / 1024).toFixed(2)} MB</p>
              </div>
            </div>
          )}
          <div className="space-y-2">
            <label className="text-sm font-medium">Aplicar áudio em:</label>
            <div className="grid grid-cols-2 gap-2">
              <Button type="button" variant={audioTarget === 'slide' ? 'default' : 'outline'} className="h-auto py-3 flex flex-col gap-1"
                onClick={() => setAudioTarget('slide')} data-testid="audio-target-slide"><Mic className="w-5 h-5" /><span className="text-xs">Slide Atual</span></Button>
              <Button type="button" variant={audioTarget === 'global' ? 'default' : 'outline'} className="h-auto py-3 flex flex-col gap-1"
                onClick={() => setAudioTarget('global')} data-testid="audio-target-global"><Music className="w-5 h-5" /><span className="text-xs">Todos os Slides</span></Button>
            </div>
            <p className="text-xs text-muted-foreground">{audioTarget === 'slide' ? 'O áudio será reproduzido apenas neste slide.' : 'O áudio será a trilha sonora de fundo para todo o curso.'}</p>
          </div>

          {/* Per-slide audio type picker — only when target is "slide" */}
          {audioTarget === 'slide' && setAudioType && (
            <div className="space-y-2" data-testid="audio-type-picker">
              <label className="text-sm font-medium">Tipo de áudio:</label>
              <div className="grid grid-cols-3 gap-2">
                <Button type="button" variant={audioType === 'narration' ? 'default' : 'outline'}
                  className="h-auto py-2.5 flex flex-col gap-1" onClick={() => setAudioType('narration')}
                  data-testid="audio-type-narration">
                  <Mic className="w-4 h-4" />
                  <span className="text-[11px] font-semibold">Narração</span>
                </Button>
                <Button type="button" variant={audioType === 'sfx' ? 'default' : 'outline'}
                  className="h-auto py-2.5 flex flex-col gap-1" onClick={() => setAudioType('sfx')}
                  data-testid="audio-type-sfx">
                  <span className="text-lg leading-none">💥</span>
                  <span className="text-[11px] font-semibold">Efeito (SFX)</span>
                </Button>
                <Button type="button" variant={audioType === 'background' ? 'default' : 'outline'}
                  className="h-auto py-2.5 flex flex-col gap-1" onClick={() => setAudioType('background')}
                  data-testid="audio-type-background">
                  <Music className="w-4 h-4" />
                  <span className="text-[11px] font-semibold">Ambiente</span>
                </Button>
              </div>
              <p className="text-[11px] text-muted-foreground" data-testid="audio-type-hint">
                {audioType === 'narration' && '🎙️ Auto-play quando o slide ficar ativo, com controles (pausa/reiniciar). Ideal para voiceovers.'}
                {audioType === 'sfx' && '💥 Som curto, toca UMA vez ao entrar no slide. Sem controles visuais. Ex: ding de conquista, whoosh de transição.'}
                {audioType === 'background' && '🎵 Música ambiente que toca em LOOP durante o curso inteiro (o primeiro áudio deste tipo vence). Volume recomendado: baixo.'}
              </p>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => { onOpenChange(false); setAudioFile(null); setAudioTarget('slide'); if (setAudioType) setAudioType('narration'); }}>Cancelar</Button>
          <Button onClick={handleAudioUpload} disabled={!audioFile} data-testid="confirm-audio-upload">Adicionar Áudio</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ButtonDialog({ open, onOpenChange, buttonConfig, setButtonConfig, handleAddButton }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader><DialogTitle>Adicionar Botão/Link</DialogTitle></DialogHeader>
        <div className="space-y-4 py-4">
          <div><label className="text-sm font-medium">Texto do Botão</label><Input placeholder="Clique aqui" value={buttonConfig.text} onChange={(e) => setButtonConfig({ ...buttonConfig, text: e.target.value })} data-testid="button-text-input" /></div>
          <div><label className="text-sm font-medium">URL de Destino *</label><Input placeholder="https://exemplo.com" value={buttonConfig.url} onChange={(e) => setButtonConfig({ ...buttonConfig, url: e.target.value })} data-testid="button-url-input" /></div>
          <div><label className="text-sm font-medium">Ícone (emoji ou texto)</label><Input placeholder="🔗 ou →" value={buttonConfig.icon} onChange={(e) => setButtonConfig({ ...buttonConfig, icon: e.target.value })} data-testid="button-icon-input" /></div>
          <div>
            <label className="text-sm font-medium">Estilo do Botão</label>
            <select className="w-full h-10 px-3 rounded-md border bg-background" value={buttonConfig.style} onChange={(e) => setButtonConfig({ ...buttonConfig, style: e.target.value })} data-testid="button-style-select">
              <option value="primary">Primário (Colorido)</option><option value="secondary">Secundário (Cinza)</option><option value="outline">Contorno</option><option value="ghost">Transparente</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" id="openNewTab" checked={buttonConfig.openInNewTab} onChange={(e) => setButtonConfig({ ...buttonConfig, openInNewTab: e.target.checked })} className="rounded" />
            <label htmlFor="openNewTab" className="text-sm">Abrir em nova aba</label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button onClick={handleAddButton} data-testid="confirm-add-button">Adicionar Botão</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function HtmlDialog({
  open, onOpenChange,
  htmlConfig, setHtmlConfig,
  htmlDialogTab, setHtmlDialogTab,
  aiHtmlPrompt, setAiHtmlPrompt,
  aiHtmlResult, setAiHtmlResult,
  aiHtmlLoading,
  handleAddHtml, handleGenerateHtmlAI, handleInsertAiHtml,
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => {
      onOpenChange(o);
      if (!o) { setAiHtmlResult(''); setAiHtmlPrompt(''); setHtmlDialogTab('paste'); }
    }}>
      <DialogContent className="sm:max-w-3xl max-h-[85vh] flex flex-col">
        <DialogHeader><DialogTitle>Adicionar HTML Personalizado</DialogTitle></DialogHeader>
        <Tabs value={htmlDialogTab} onValueChange={setHtmlDialogTab} className="flex-1 flex flex-col min-h-0">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="paste" data-testid="html-tab-paste"><Code className="w-4 h-4 mr-2" />Colar HTML</TabsTrigger>
            <TabsTrigger value="ai" data-testid="html-tab-ai"><Sparkles className="w-4 h-4 mr-2" />Gerar com IA</TabsTrigger>
          </TabsList>
          <TabsContent value="paste" className="flex-1 flex flex-col min-h-0 mt-4">
            <div className="flex-1 flex flex-col min-h-0">
              <label className="text-sm font-medium mb-1">Código HTML</label>
              <textarea className="flex-1 min-h-[240px] p-3 rounded-md border bg-background font-mono text-sm resize-none" placeholder="<div>Seu código HTML aqui...</div>"
                value={htmlConfig.content} onChange={(e) => setHtmlConfig({ ...htmlConfig, content: e.target.value })} data-testid="html-content-input" />
              <p className="text-xs text-muted-foreground mt-1">Suporta HTML, CSS inline e JavaScript básico.</p>
            </div>
            <DialogFooter className="mt-4">
              <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
              <Button onClick={handleAddHtml} data-testid="confirm-add-html">Adicionar HTML</Button>
            </DialogFooter>
          </TabsContent>
          <TabsContent value="ai" className="flex-1 flex flex-col min-h-0 mt-4">
            <div className="flex-1 flex flex-col gap-3 min-h-0">
              <div>
                <label className="text-sm font-medium mb-1 block">Descreva o que deseja criar</label>
                <textarea className="w-full h-24 p-3 rounded-md border bg-background text-sm resize-none"
                  placeholder="Ex: Um quiz interativo sobre segurança do trabalho..."
                  value={aiHtmlPrompt} onChange={(e) => setAiHtmlPrompt(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && e.ctrlKey && !aiHtmlLoading) handleGenerateHtmlAI(); }}
                  data-testid="ai-html-prompt" />
                <div className="flex items-center justify-between mt-1">
                  <p className="text-xs text-muted-foreground">Ctrl+Enter para gerar.</p>
                  <Button size="sm" onClick={handleGenerateHtmlAI} disabled={aiHtmlLoading || !aiHtmlPrompt.trim()} data-testid="ai-html-generate-btn">
                    {aiHtmlLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
                    {aiHtmlLoading ? 'Gerando...' : 'Gerar HTML'}
                  </Button>
                </div>
              </div>
              {aiHtmlResult && (
                <div className="flex-1 flex flex-col min-h-0 border rounded-lg overflow-hidden">
                  <Tabs defaultValue="preview" className="flex-1 flex flex-col min-h-0">
                    <TabsList className="w-fit mx-2 mt-2">
                      <TabsTrigger value="preview" data-testid="ai-html-preview-tab">Preview</TabsTrigger>
                      <TabsTrigger value="code" data-testid="ai-html-code-tab">Editar Código</TabsTrigger>
                    </TabsList>
                    <TabsContent value="preview" className="flex-1 min-h-0 p-2">
                      <iframe srcDoc={aiHtmlResult} className="w-full h-full min-h-[200px] rounded border bg-white" sandbox="allow-scripts" title="AI HTML Preview" data-testid="ai-html-preview-iframe" />
                    </TabsContent>
                    <TabsContent value="code" className="flex-1 min-h-0 p-2">
                      <textarea className="w-full h-full min-h-[200px] p-3 rounded border bg-background font-mono text-xs resize-none"
                        value={aiHtmlResult} onChange={(e) => setAiHtmlResult(e.target.value)} data-testid="ai-html-code-editor" />
                    </TabsContent>
                  </Tabs>
                </div>
              )}
            </div>
            <DialogFooter className="mt-4">
              <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
              {aiHtmlResult && <Button onClick={handleInsertAiHtml} data-testid="ai-html-insert-btn">Inserir no Slide</Button>}
            </DialogFooter>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}

export function BulkTextColorDialog({ open, onOpenChange, bulkTextColor, setBulkTextColor, bulkFontFamily, setBulkFontFamily, bulkFontSize, setBulkFontSize, slides, handleBulkTextColorChange }) {
  const fonts = [
    'Arial', 'Helvetica', 'Verdana', 'Tahoma', 'Trebuchet MS', 'Georgia',
    'Times New Roman', 'Courier New', 'Roboto', 'Open Sans', 'Lato',
    'Montserrat', 'Poppins', 'Inter', 'Raleway', 'Nunito', 'Oswald',
    'Playfair Display', 'Source Sans Pro', 'PT Sans',
  ];
  const sizes = ['12px', '14px', '16px', '18px', '20px', '22px', '24px', '28px', '32px', '36px', '40px', '48px', '56px', '64px', '72px'];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader><DialogTitle>Alterar Texto — Todos os Slides</DialogTitle></DialogHeader>
        <div className="space-y-5 py-4">
          <p className="text-sm text-muted-foreground">As alterações serão aplicadas a todos os textos em todos os {slides.length} slides. Deixe campos vazios para manter o valor atual.</p>

          {/* Color */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-slate-300">Cor do Texto</label>
            <div className="flex items-center gap-3">
              <input type="color" value={bulkTextColor || '#ffffff'} onChange={e => setBulkTextColor(e.target.value)} className="w-10 h-10 rounded cursor-pointer border-0 bg-transparent" data-testid="bulk-text-color-picker" />
              <Input value={bulkTextColor} onChange={e => setBulkTextColor(e.target.value)} placeholder="#ffffff" className="flex-1" data-testid="bulk-text-color-hex" />
              <button onClick={() => setBulkTextColor('')} className="text-[10px] text-slate-500 hover:text-slate-300 shrink-0">Limpar</button>
            </div>
            <div className="flex gap-1.5 flex-wrap">
              {['#ffffff', '#f1f5f9', '#e2e8f0', '#1e293b', '#0f172a', '#000000', '#fbbf24', '#34d399', '#60a5fa', '#f472b6'].map(c => (
                <button key={c} onClick={() => setBulkTextColor(c)}
                  className={`w-7 h-7 rounded-full border-2 transition-transform hover:scale-110 ${bulkTextColor === c ? 'border-cyan-400 ring-2 ring-cyan-400/30' : 'border-slate-600'}`}
                  style={{ background: c }} title={c} />
              ))}
            </div>
          </div>

          {/* Font Family */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-slate-300">Fonte</label>
            <select
              value={bulkFontFamily}
              onChange={e => setBulkFontFamily(e.target.value)}
              className="w-full h-9 rounded-md border border-slate-700 bg-slate-900 px-3 text-sm text-slate-200"
              data-testid="bulk-font-family-select"
            >
              <option value="">— Manter fonte atual —</option>
              {fonts.map(f => (
                <option key={f} value={f} style={{ fontFamily: f }}>{f}</option>
              ))}
            </select>
            {bulkFontFamily && (
              <p className="text-sm text-slate-300 px-2 py-1 rounded bg-slate-800/50" style={{ fontFamily: bulkFontFamily }}>
                Preview: O rápido rapaz pula sobre o cão preguiçoso.
              </p>
            )}
          </div>

          {/* Font Size */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-slate-300">Tamanho do Texto</label>
            <select
              value={bulkFontSize}
              onChange={e => setBulkFontSize(e.target.value)}
              className="w-full h-9 rounded-md border border-slate-700 bg-slate-900 px-3 text-sm text-slate-200"
              data-testid="bulk-font-size-select"
            >
              <option value="">— Manter tamanho atual —</option>
              {sizes.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          {/* Preview */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">Preview</label>
            <div className="flex gap-2">
              {(slides.slice(0, 3)).map((s, i) => (
                <div key={i} className="flex-1 h-14 rounded border border-slate-700 flex items-center justify-center text-xs font-medium overflow-hidden px-1 text-center"
                  style={{
                    background: s.background || '#1e293b',
                    color: bulkTextColor || (s.elements?.find(e => e.type === 'text')?.style?.color) || '#fff',
                    fontFamily: bulkFontFamily || undefined,
                    fontSize: bulkFontSize || '12px',
                  }}>
                  Slide {i + 1}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="flex gap-3 justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button onClick={handleBulkTextColorChange} disabled={!bulkTextColor && !bulkFontFamily && !bulkFontSize} className="bg-amber-600 hover:bg-amber-700" data-testid="apply-bulk-text-style">Aplicar a Todos os Slides</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function DesignTemplateDialog({ open, onOpenChange, designTemplates, applyingTemplate, handleApplyDesignTemplate }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Palette className="w-5 h-5 text-amber-400" /> Aplicar Tema Visual</DialogTitle>
        </DialogHeader>
        <div className="py-4">
          <p className="text-sm text-slate-400 mb-4">Selecione um tema para aplicar cores, fontes e estilos a todos os slides do curso</p>
          <div className="grid grid-cols-3 gap-3" data-testid="editor-design-template-grid">
            {designTemplates.map(dt => {
              const p = dt.palette || {};
              return (
                <button key={dt.id} disabled={applyingTemplate} onClick={() => handleApplyDesignTemplate(dt.id)}
                  className="relative overflow-hidden rounded-xl border border-slate-700 hover:border-amber-500 transition-all text-left group disabled:opacity-50"
                  data-testid={`editor-design-template-${dt.id}`}>
                  <div className="aspect-[16/9] relative" style={{ background: p.primary || '#0f172a' }}>
                    <div className="absolute top-0 left-0 right-0 h-[6px]" style={{ background: p.accent || '#10b981' }} />
                    <div className="absolute bottom-0 left-0 right-0 h-[55%] mx-2 mb-1 rounded-t-sm" style={{ background: p.contentBg || '#f0fdf4' }}>
                      <div className="p-2 space-y-1">
                        <div className="h-1 rounded-full w-[60%]" style={{ background: (p.text || '#1e293b') + '88' }} />
                        <div className="h-0.5 rounded-full w-[80%]" style={{ background: (p.text || '#1e293b') + '44' }} />
                      </div>
                    </div>
                    <div className="absolute top-2 left-2 right-2 text-center">
                      <span style={{ fontFamily: dt.fonts?.heading, color: '#fff', fontSize: '11px', fontWeight: 700 }}>Aa</span>
                    </div>
                    <div className="absolute inset-0 bg-amber-500/0 group-hover:bg-amber-500/10 transition-colors flex items-center justify-center">
                      <span className="opacity-0 group-hover:opacity-100 transition-opacity text-xs text-white font-semibold bg-amber-600/80 px-3 py-1 rounded-full">Aplicar</span>
                    </div>
                  </div>
                  <div className="p-2 bg-slate-900/80">
                    <p className="font-medium text-xs" style={{ fontFamily: dt.fonts?.heading }}>{dt.name}</p>
                    <p className="text-[10px] text-slate-500 truncate">{dt.description}</p>
                  </div>
                </button>
              );
            })}
          </div>
          {applyingTemplate && (
            <div className="flex items-center justify-center gap-2 mt-4 text-amber-400">
              <div className="w-4 h-4 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm">Aplicando tema...</span>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function ImageGalleryDialog({ open, onOpenChange, galleryImages, galleryLoading, gallerySearch, setGallerySearch, handleSelectGalleryImage, API_URL, onRefreshGallery }) {
  const [cleaning, setCleaning] = useState(false);
  const [deleting, setDeleting] = useState(null);

  const handleDeleteImage = async (e, imgId) => {
    e.stopPropagation();
    if (deleting) return;
    setDeleting(imgId);
    try {
      const { authHeaders } = await import('../../../contexts/AuthContext');
      const { getApiUrl } = await import('../../../utils/apiUrl');
      const { toast } = await import('sonner');
      const res = await fetch(`${getApiUrl()}/api/gallery/images/${imgId}`, {
        method: 'DELETE',
        headers: authHeaders(),
        credentials: 'include',
      });
      if (!res.ok) throw new Error();
      toast.success('Imagem removida');
      if (onRefreshGallery) onRefreshGallery();
    } catch {
      const { toast } = await import('sonner');
      toast.error('Erro ao remover imagem');
    }
    setDeleting(null);
  };

  const handleCleanup = async () => {
    setCleaning(true);
    try {
      const { authHeaders } = await import('../../../contexts/AuthContext');
      const { getApiUrl } = await import('../../../utils/apiUrl');
      const res = await fetch(`${getApiUrl()}/api/gallery/cleanup`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ deep: true }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      const { toast } = await import('sonner');
      if (data.removed > 0) {
        toast.success(`${data.removed} imagens quebradas removidas!`);
        if (onRefreshGallery) onRefreshGallery();
      } else {
        toast.info('Nenhuma imagem quebrada encontrada.');
      }
    } catch {
      const { toast } = await import('sonner');
      toast.error('Erro ao limpar galeria');
    }
    setCleaning(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Image className="w-5 h-5 text-amber-400" /> Galeria de Imagens IA</DialogTitle>
        </DialogHeader>
        <div className="py-2">
          <Input value={gallerySearch} onChange={e => setGallerySearch(e.target.value)} placeholder="Buscar por palavras-chave ou projeto..." className="mb-3" data-testid="editor-gallery-search" />
          {galleryLoading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              <div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />Carregando...
            </div>
          ) : galleryImages.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Image className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">Nenhuma imagem na galeria ainda.</p>
              <p className="text-xs mt-1 opacity-60">As imagens geradas por IA serão salvas aqui automaticamente.</p>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-3 max-h-[50vh] overflow-y-auto">
              {galleryImages
                .filter(img => !gallerySearch || (img.keywords || '').toLowerCase().includes(gallerySearch.toLowerCase()) || (img.projectName || '').toLowerCase().includes(gallerySearch.toLowerCase()))
                .map(img => (
                  <button key={img.id} onClick={() => handleSelectGalleryImage(img)}
                    className="group relative rounded-lg overflow-hidden border border-border hover:border-amber-500 transition-all aspect-[4/3]"
                    data-testid={`editor-gallery-img-${img.id}`}>
                    <GalleryImage src={img.imageUrl.startsWith('/') ? `${API_URL}${img.imageUrl}` : img.imageUrl} alt={img.keywords || ''} />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-2">
                      <p className="text-[10px] text-white/90 truncate">{img.keywords || 'Sem palavras-chave'}</p>
                    </div>
                    <div className="absolute top-1 right-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <div
                        role="button"
                        onClick={(e) => handleDeleteImage(e, img.id)}
                        className="bg-red-600 hover:bg-red-500 text-white rounded-full p-1 cursor-pointer"
                        data-testid={`gallery-delete-${img.id}`}
                      >
                        {deleting === img.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                      </div>
                      <div className="bg-amber-500 text-black rounded-full p-1"><Plus className="w-3 h-3" /></div>
                    </div>
                  </button>
                ))}
            </div>
          )}
          <div className="flex items-center justify-between mt-2">
            <p className="text-[10px] text-muted-foreground">
              {galleryImages.filter(img => !gallerySearch || (img.keywords || '').toLowerCase().includes(gallerySearch.toLowerCase()) || (img.projectName || '').toLowerCase().includes(gallerySearch.toLowerCase())).length} de {galleryImages.length} imagens
            </p>
            <button
              onClick={handleCleanup}
              disabled={cleaning}
              className="text-[10px] text-red-400/70 hover:text-red-300 underline disabled:opacity-50"
              data-testid="gallery-cleanup-btn"
            >
              {cleaning ? 'Limpando...' : 'Remover imagens quebradas'}
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function PdfDialog({ open, onOpenChange, pdfUploading, handleAddPdf }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [displayMode, setDisplayMode] = useState('full');
  const [pagesSpec, setPagesSpec] = useState('all');
  const fileInputRef = React.useRef(null);

  const reset = () => {
    setSelectedFile(null); setDisplayMode('full'); setPagesSpec('all');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const MODES = [
    { id: 'full', title: 'Visualizador completo', desc: 'Com controles do player (zoom, download, imprimir)' },
    { id: 'clean', title: 'Visualizador limpo', desc: 'Sem barra de controles — apenas navegação por rolagem' },
    { id: 'pages', title: 'Somente página(s)', desc: 'Páginas viram imagens limpas — ideal para texto ao lado' },
  ];

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) reset(); onOpenChange(o); }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-red-400" />
            Adicionar PDF ao Slide
          </DialogTitle>
          <DialogDescription>Envie um arquivo PDF e escolha como exibi-lo dentro do slide</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            className="hidden"
            onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
            data-testid="pdf-file-input"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="w-full border-2 border-dashed border-slate-600 hover:border-red-400/60 rounded-lg p-5 flex flex-col items-center gap-2 transition-colors"
            data-testid="pdf-dropzone"
          >
            <Upload className="w-6 h-6 text-slate-400" />
            {selectedFile ? (
              <div className="text-center">
                <p className="text-sm font-medium text-red-300" data-testid="pdf-selected-name">{selectedFile.name}</p>
                <p className="text-xs text-muted-foreground">{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB</p>
              </div>
            ) : (
              <div className="text-center">
                <p className="text-sm font-medium">Clique para selecionar o PDF</p>
                <p className="text-xs text-muted-foreground">Máx. 100MB — armazenado no projeto e incluído nos exports</p>
              </div>
            )}
          </button>

          <div className="space-y-2">
            <label className="text-sm font-medium">Modo de exibição</label>
            {MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setDisplayMode(m.id)}
                className={`w-full text-left px-3 py-2.5 rounded-lg border transition-colors ${
                  displayMode === m.id ? 'border-red-400/70 bg-red-500/10' : 'border-slate-700 hover:border-slate-500'
                }`}
                data-testid={`pdf-mode-${m.id}`}
              >
                <div className="flex items-center gap-2">
                  <span className={`w-3 h-3 rounded-full border-2 flex-shrink-0 ${displayMode === m.id ? 'border-red-400 bg-red-400' : 'border-slate-500'}`} />
                  <div>
                    <p className="text-sm font-medium">{m.title}</p>
                    <p className="text-xs text-muted-foreground">{m.desc}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>

          {displayMode === 'pages' && (
            <div>
              <label className="text-sm font-medium">Páginas a exibir</label>
              <Input
                placeholder='"all" para todas, ou ex.: 1-3,5'
                value={pagesSpec}
                onChange={(e) => setPagesSpec(e.target.value)}
                data-testid="pdf-pages-input"
              />
              <p className="text-xs text-muted-foreground mt-1">Máx. 30 páginas. As páginas viram imagens em alta resolução.</p>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => { reset(); onOpenChange(false); }} data-testid="pdf-cancel-btn">Cancelar</Button>
          <Button
            onClick={async () => { await handleAddPdf(selectedFile, { display: displayMode, pages: pagesSpec }); reset(); }}
            disabled={!selectedFile || pdfUploading}
            data-testid="confirm-add-pdf"
          >
            {pdfUploading ? (<><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Processando...</>) : 'Adicionar ao Slide'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function FlipbookDialog({ open, onOpenChange, flipbookConfig, setFlipbookConfig, handleAddFlipbook }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader><DialogTitle>Adicionar Flipbook</DialogTitle></DialogHeader>
        <div className="space-y-4 py-4">
          <div>
            <label className="text-sm font-medium">Tipo de Flipbook</label>
            <select className="w-full h-10 px-3 rounded-md border bg-background" value={flipbookConfig.type}
              onChange={(e) => setFlipbookConfig({ ...flipbookConfig, type: e.target.value })} data-testid="flipbook-type-select">
              <option value="external">URL Externa (FlipHTML5, Issuu, etc.)</option>
              <option value="pdf">Upload de PDF</option>
              <option value="images">Múltiplas Imagens</option>
            </select>
          </div>
          {flipbookConfig.type === 'external' && (
            <div>
              <label className="text-sm font-medium">URL do Flipbook</label>
              <Input placeholder="https://fliphtml5.com/..." value={flipbookConfig.url} onChange={(e) => setFlipbookConfig({ ...flipbookConfig, url: e.target.value })} data-testid="flipbook-url-input" />
              <p className="text-xs text-muted-foreground mt-1">Cole a URL de embed do seu flipbook</p>
            </div>
          )}
          {flipbookConfig.type === 'pdf' && (
            <div>
              <label className="text-sm font-medium">URL do PDF</label>
              <Input placeholder="https://exemplo.com/documento.pdf" value={flipbookConfig.url} onChange={(e) => setFlipbookConfig({ ...flipbookConfig, url: e.target.value })} data-testid="flipbook-pdf-input" />
            </div>
          )}
          {flipbookConfig.type === 'images' && (
            <div>
              <label className="text-sm font-medium">URLs das Imagens (uma por linha)</label>
              <textarea className="w-full h-32 p-3 rounded-md border bg-background text-sm"
                placeholder="https://exemplo.com/pagina1.jpg"
                value={flipbookConfig.pages.join('\n')}
                onChange={(e) => setFlipbookConfig({ ...flipbookConfig, pages: e.target.value.split('\n').filter(url => url.trim()) })}
                data-testid="flipbook-images-input" />
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button onClick={handleAddFlipbook} data-testid="confirm-add-flipbook">Adicionar Flipbook</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function RichTextDialog({
  open, onOpenChange,
  richTextContent, setRichTextContent,
  richTextGenerating, richTextImageGenerating,
  editingHtmlElementId,
  generateTextWithAI, generateImageWithAI,
  handleAddRichTextToSlide, handleCloseRichText,
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) handleCloseRichText(); else onOpenChange(o); }}>
      <DialogContent className="sm:max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-purple-500" />
            {editingHtmlElementId ? 'Editar Texto' : 'Criar Texto com IA'}
          </DialogTitle>
          <DialogDescription>
            {editingHtmlElementId ? 'Edite o texto existente ou gere novo conteúdo com IA' : 'Escreva seu texto ou use a IA para gerar conteúdo formatado automaticamente'}
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <RichTextEditor
            key={editingHtmlElementId || 'new'}
            content={richTextContent}
            onChange={setRichTextContent}
            onGenerateAI={generateTextWithAI}
            onGenerateAIImage={generateImageWithAI}
            isGenerating={richTextGenerating}
            isGeneratingImage={richTextImageGenerating}
            placeholder="Digite seu texto ou clique em 'Gerar com IA' para criar conteúdo..."
            className="min-h-[400px]"
          />
        </div>
        <DialogFooter className="flex justify-between">
          <Button variant="ghost" onClick={handleCloseRichText}>Cancelar</Button>
          <Button onClick={handleAddRichTextToSlide} disabled={!richTextContent.trim()} className="bg-purple-600 hover:bg-purple-700">
            {editingHtmlElementId ? (<><Check className="w-4 h-4 mr-2" />Salvar Alterações</>) : (<><Plus className="w-4 h-4 mr-2" />Adicionar ao Slide</>)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
