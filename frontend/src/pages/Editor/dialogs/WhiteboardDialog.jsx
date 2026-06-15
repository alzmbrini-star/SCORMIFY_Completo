/**
 * WhiteboardDialog — UI for the self-hosted hand-writer / whiteboard
 * video generator. The author types a script and optionally a title,
 * picks pen speed, hits generate. The backend renders an MP4 in ~1-3s
 * (CPU-bound, scales with script length) and returns a URL we drop into
 * the current slide's `videoUrl` field — same field used by HeyGen so
 * downstream SCORM export already handles playback.
 */
import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../components/ui/dialog';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Textarea } from '../../../components/ui/textarea';
import { Label } from '../../../components/ui/label';
import { Loader2, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { getApiUrl } from '../../../utils/apiUrl';

export default function WhiteboardDialog({
  open,
  onOpenChange,
  projectId,
  slideId,
  defaultTitle = '',
  defaultText = '',
  onGenerated,
}) {
  const [title, setTitle] = useState(defaultTitle);
  const [text, setText] = useState(defaultText);
  const [speed, setSpeed] = useState(19);  // chars/sec
  const [busy, setBusy] = useState(false);
  const [videoUrl, setVideoUrl] = useState('');

  const handleGenerate = async () => {
    if (!text.trim()) {
      toast.error('Digite o texto que a mão vai escrever');
      return;
    }
    setBusy(true);
    setVideoUrl('');
    try {
      const res = await fetch(`${getApiUrl()}/api/whiteboard/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          text: text.trim(),
          title: title.trim() || null,
          fontSize: 96,
          charsPerSecond: Number(speed) || 19,
          projectId,
          slideId,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setVideoUrl(`${getApiUrl()}${data.videoUrl}`);
      toast.success(`Video gerado (${data.duration.toFixed(1)}s)`);
      if (onGenerated) onGenerated(data);
    } catch (e) {
      toast.error(e.message || 'Falha ao gerar video');
    }
    setBusy(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl" data-testid="whiteboard-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-amber-500" />
            Gerar Whiteboard (Hand Writer)
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <Label htmlFor="wb-title">Titulo (opcional)</Label>
            <Input
              id="wb-title"
              data-testid="whiteboard-title-input"
              placeholder="Ex.: Aula 1"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
            />
          </div>

          <div>
            <Label htmlFor="wb-text">Texto a escrever</Label>
            <Textarea
              id="wb-text"
              data-testid="whiteboard-text-input"
              placeholder="O que a mao vai escrever no quadro. Use Enter para quebras de linha."
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={6}
              maxLength={2000}
              className="font-mono text-sm"
            />
            <p className="text-[10px] text-muted-foreground mt-1">
              {text.length}/2000 caracteres. Maximo recomendado: 300 caracteres
              por slide (~15s de animacao).
            </p>
          </div>

          <div>
            <Label htmlFor="wb-speed">Velocidade da escrita (chars/seg)</Label>
            <Input
              id="wb-speed"
              data-testid="whiteboard-speed-input"
              type="number"
              min={4}
              max={40}
              value={speed}
              onChange={(e) => setSpeed(e.target.value)}
            />
            <p className="text-[10px] text-muted-foreground mt-1">
              19 = ritmo natural. 30+ = rapido. 10 = lento e dramatico.
            </p>
          </div>

          {videoUrl && (
            <div className="border border-slate-700 rounded-md overflow-hidden">
              <video
                src={videoUrl}
                controls
                autoPlay
                className="w-full"
                data-testid="whiteboard-preview-video"
              />
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={busy}>
            Fechar
          </Button>
          <Button
            onClick={handleGenerate}
            disabled={busy || !text.trim()}
            className="bg-amber-600 hover:bg-amber-700"
            data-testid="whiteboard-generate-btn"
          >
            {busy ? (
              <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Gerando...</>
            ) : (
              <><Sparkles className="w-4 h-4 mr-2" /> Gerar e Aplicar ao Slide</>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
