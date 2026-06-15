/**
 * WhiteboardDialog — UI for the self-hosted hand-writer / whiteboard
 * generator. The author types a script, picks a font + size + speed,
 * optionally enables transparent background (APNG), hits generate.
 * Backend renders in ~1-5s and binds the result to the current slide.
 */
import { useEffect, useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../components/ui/dialog';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Textarea } from '../../../components/ui/textarea';
import { Label } from '../../../components/ui/label';
import { Switch } from '../../../components/ui/switch';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../../components/ui/select';
import { Loader2, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { getApiUrl } from '../../../utils/apiUrl';

const SIZE_PRESETS = [
  { value: 64, label: 'Pequeno (64)' },
  { value: 96, label: 'Médio (96)' },
  { value: 140, label: 'Grande (140)' },
  { value: 180, label: 'Maior (180)' },
  { value: 220, label: 'Enorme (220)' },
];

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
  const [speed, setSpeed] = useState(6);  // chars/sec
  const [fontSize, setFontSize] = useState(96);
  const [fontFamily, setFontFamily] = useState('caveat');
  const [transparent, setTransparent] = useState(false);
  const [fonts, setFonts] = useState([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);  // { videoUrl, format }

  // Fetch the available fonts on dialog open.
  useEffect(() => {
    if (!open) return;
    fetch(`${getApiUrl()}/api/whiteboard/fonts`, { credentials: 'include' })
      .then((r) => r.ok ? r.json() : { fonts: [] })
      .then((d) => setFonts(d.fonts || []))
      .catch(() => setFonts([]));
  }, [open]);

  const handleGenerate = async () => {
    if (!text.trim()) {
      toast.error('Digite o texto que a caneta vai escrever');
      return;
    }
    setBusy(true);
    setResult(null);
    try {
      const res = await fetch(`${getApiUrl()}/api/whiteboard/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          text: text.trim(),
          title: title.trim() || null,
          fontSize: Number(fontSize) || 96,
          charsPerSecond: Number(speed) || 6,
          fontFamily: fontFamily || null,
          transparent: Boolean(transparent),
          projectId,
          slideId,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setResult({
        url: `${getApiUrl()}${data.videoUrl}`,
        format: data.format,
      });
      toast.success(`Animação gerada (${data.duration.toFixed(1)}s, ${(data.fileSize/1024).toFixed(0)} KB)`);
      if (onGenerated) onGenerated(data);
    } catch (e) {
      toast.error(e.message || 'Falha ao gerar animação');
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

        <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
          <div>
            <Label htmlFor="wb-title">Título (opcional)</Label>
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
              placeholder="O que a caneta vai escrever. Use Enter para quebras de linha."
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={6}
              maxLength={2000}
              className="font-mono text-sm"
            />
            <p className="text-[10px] text-muted-foreground mt-1">
              {text.length}/2000 caracteres. Máximo recomendado: 300 caracteres
              por slide.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="wb-font">Fonte</Label>
              <Select value={fontFamily} onValueChange={setFontFamily}>
                <SelectTrigger id="wb-font" data-testid="whiteboard-font-select">
                  <SelectValue placeholder="Escolha uma fonte" />
                </SelectTrigger>
                <SelectContent>
                  {fonts.length === 0 && (
                    <SelectItem value="caveat">Caveat (manuscrita)</SelectItem>
                  )}
                  {fonts.map((f) => (
                    <SelectItem key={f.id} value={f.id} data-testid={`font-opt-${f.id}`}>
                      {f.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="wb-size">Tamanho da fonte</Label>
              <div className="flex gap-2">
                <Select
                  value={String(fontSize)}
                  onValueChange={(v) => setFontSize(Number(v))}
                >
                  <SelectTrigger id="wb-size" data-testid="whiteboard-size-select" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SIZE_PRESETS.map((p) => (
                      <SelectItem key={p.value} value={String(p.value)}>
                        {p.label}
                      </SelectItem>
                    ))}
                    {!SIZE_PRESETS.some((p) => p.value === Number(fontSize)) && (
                      <SelectItem value={String(fontSize)}>
                        Customizado ({fontSize})
                      </SelectItem>
                    )}
                  </SelectContent>
                </Select>
                <Input
                  type="number"
                  min={40}
                  max={240}
                  value={fontSize}
                  data-testid="whiteboard-size-input"
                  onChange={(e) => setFontSize(Number(e.target.value) || 96)}
                  className="w-20"
                />
              </div>
            </div>
          </div>

          <div>
            <Label htmlFor="wb-speed">Velocidade da escrita (caracteres/seg)</Label>
            <Input
              id="wb-speed"
              data-testid="whiteboard-speed-input"
              type="number"
              min={2}
              max={30}
              value={speed}
              onChange={(e) => setSpeed(e.target.value)}
            />
            <p className="text-[10px] text-muted-foreground mt-1">
              4 = lento e dramático. 6 = natural (recomendado). 10+ = rápido.
            </p>
          </div>

          <div className="flex items-center justify-between p-3 border border-slate-700 rounded-md bg-slate-900/30">
            <div className="flex-1 pr-3">
              <Label htmlFor="wb-transparent" className="flex items-center gap-2 cursor-pointer">
                Fundo transparente
              </Label>
              <p className="text-[10px] text-muted-foreground mt-1">
                Gera um <strong>APNG animado</strong> com canal alpha — perfeito
                para sobrepor no background do slide. Sem fundo branco. Arquivo
                ~10x maior que MP4.
              </p>
            </div>
            <Switch
              id="wb-transparent"
              data-testid="whiteboard-transparent-toggle"
              checked={transparent}
              onCheckedChange={setTransparent}
            />
          </div>

          {result && (
            <div className="border border-slate-700 rounded-md overflow-hidden bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2220%22 height=%2220%22><rect width=%2210%22 height=%2210%22 fill=%22%23ccc%22/><rect x=%2210%22 y=%2210%22 width=%2210%22 height=%2210%22 fill=%22%23ccc%22/></svg>')]">
              {result.format === 'apng' ? (
                <img
                  src={result.url}
                  alt="Whiteboard animation"
                  className="w-full"
                  data-testid="whiteboard-preview-image"
                />
              ) : (
                <video
                  src={result.url}
                  controls
                  autoPlay
                  className="w-full"
                  data-testid="whiteboard-preview-video"
                />
              )}
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
