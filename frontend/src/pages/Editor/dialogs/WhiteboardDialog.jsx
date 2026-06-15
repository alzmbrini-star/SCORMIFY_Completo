/**
 * WhiteboardDialog — UI for the self-hosted hand-writer / whiteboard
 * generator. The author types a script, picks a font + size + speed,
 * optionally enables transparent background (APNG), hits generate.
 * Backend renders in ~1-5s and binds the result to the current slide.
 */
import { useEffect, useRef, useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../components/ui/dialog';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Textarea } from '../../../components/ui/textarea';
import { Label } from '../../../components/ui/label';
import { Switch } from '../../../components/ui/switch';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../../components/ui/select';
import { Loader2, Sparkles, Wand2, Palette, Eraser, Bold, Underline, AlignLeft, AlignCenter, AlignRight, List } from 'lucide-react';
import { toast } from 'sonner';
import { getApiUrl } from '../../../utils/apiUrl';

const SIZE_PRESETS = [
  { value: 64, label: 'Pequeno (64)' },
  { value: 96, label: 'Médio (96)' },
  { value: 140, label: 'Grande (140)' },
  { value: 180, label: 'Maior (180)' },
  { value: 220, label: 'Enorme (220)' },
];

// Quick palette for the in-text color picker (handpicked for high
// contrast against white whiteboards).
const PALETTE = [
  '#1a1a1a', '#FF0000', '#E11D48', '#F59E0B', '#16A34A',
  '#0EA5E9', '#2563EB', '#7C3AED', '#DB2777', '#0D9488',
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
  const [textHtml, setTextHtml] = useState('');
  const [inkColor, setInkColor] = useState('#1a1a1a');
  // Render preferences are persisted in localStorage so when the user
  // closes and reopens the dialog (Radix unmounts content by default),
  // their last chosen speed / font / transparency / erase setting comes
  // back. Without this, every reopen reset everything to defaults — and
  // users would generate a second whiteboard expecting "Fundo
  // transparente" still ON but get an opaque MP4 instead.
  const _lsRead = (key, fallback) => {
    try {
      const v = localStorage.getItem(`wb:${key}`);
      if (v === null) return fallback;
      return JSON.parse(v);
    } catch {
      return fallback;
    }
  };
  const [speed, setSpeed] = useState(() => _lsRead('speed', 6));
  const [fontSize, setFontSize] = useState(() => _lsRead('fontSize', 96));
  const [fontFamily, setFontFamily] = useState(() => _lsRead('fontFamily', 'caveat'));
  const [transparent, setTransparent] = useState(() => _lsRead('transparent', false));
  const [eraseAtEnd, setEraseAtEnd] = useState(() => _lsRead('eraseAtEnd', false));
  const [fonts, setFonts] = useState([]);
  const [busy, setBusy] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [showAi, setShowAi] = useState(false);
  const [result, setResult] = useState(null);  // { videoUrl, format }
  const editorRef = useRef(null);

  // Apply a foreground color to the current selection inside the
  // contentEditable. Falls back to applying to the whole content if
  // nothing is selected.
  const applyColorToSelection = (hex) => {
    const el = editorRef.current;
    if (!el) return;
    el.focus();
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) {
      // Nothing selected: just update the *default* ink color for the
      // whole text — the dedicated ink color picker controls this.
      setInkColor(hex);
      return;
    }
    // execCommand is deprecated but still the simplest way to wrap a
    // selection in <span style="color:..."> for our purposes.
    document.execCommand('styleWithCSS', false, true);
    document.execCommand('foreColor', false, hex);
    syncEditorState();
  };

  const clearFormattingOnSelection = () => {
    const el = editorRef.current;
    if (!el) return;
    el.focus();
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    document.execCommand('removeFormat');
    syncEditorState();
  };

  // Apply a generic execCommand-based formatting action to the current
  // selection inside the editor. Used for bold/underline/align/list.
  const runFormatCommand = (command, value = null) => {
    const el = editorRef.current;
    if (!el) return;
    el.focus();
    document.execCommand('styleWithCSS', false, true);
    document.execCommand(command, false, value);
    syncEditorState();
  };

  const syncEditorState = () => {
    const el = editorRef.current;
    if (!el) return;
    setTextHtml(el.innerHTML);
    setText(el.innerText);
  };

  // Keep the contentEditable in sync when the AI populates `text` or
  // when the dialog reopens with a default value.
  useEffect(() => {
    if (!editorRef.current) return;
    // Only push text→editor if the editor doesn't already have it (avoids
    // overwriting cursor position during typing).
    if (editorRef.current.innerText.trim() !== (text || '').trim()) {
      editorRef.current.innerText = text || '';
      setTextHtml(editorRef.current.innerHTML);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  // Fetch the available fonts on dialog open.
  useEffect(() => {
    if (!open) return;
    fetch(`${getApiUrl()}/api/whiteboard/fonts`, { credentials: 'include' })
      .then((r) => r.ok ? r.json() : { fonts: [] })
      .then((d) => setFonts(d.fonts || []))
      .catch(() => setFonts([]));
  }, [open]);

  // Persist user preferences to localStorage so a second generation
  // (even after the dialog closed and remounted) keeps the same render
  // settings. Without this, "Fundo transparente" / "Apagar ao final"
  // silently flipped back to OFF between sessions.
  const _lsWrite = (key, val) => {
    try { localStorage.setItem(`wb:${key}`, JSON.stringify(val)); }
    catch { /* localStorage quota / privacy mode — ignore */ }
  };
  useEffect(() => { _lsWrite('speed', speed); }, [speed]);
  useEffect(() => { _lsWrite('fontSize', fontSize); }, [fontSize]);
  useEffect(() => { _lsWrite('fontFamily', fontFamily); }, [fontFamily]);
  useEffect(() => { _lsWrite('transparent', transparent); }, [transparent]);
  useEffect(() => { _lsWrite('eraseAtEnd', eraseAtEnd); }, [eraseAtEnd]);

  const handleGenerateAi = async () => {
    setAiBusy(true);
    try {
      const res = await fetch(`${getApiUrl()}/api/whiteboard/generate-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          userPrompt: aiPrompt.trim() || null,
          projectId,
          slideId,
          maxChars: 280,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setText(data.text || '');
      toast.success(`Texto gerado pela IA (${data.charsUsed} caracteres)`);
      setShowAi(false);
    } catch (e) {
      toast.error(e.message || 'Falha ao gerar texto com IA');
    }
    setAiBusy(false);
  };

  const handleGenerate = async () => {
    if (!text.trim()) {
      toast.error('Digite o texto que a caneta vai escrever');
      return;
    }
    setBusy(true);
    setResult(null);
    try {
      // Detect whether the user actually applied any inline formatting
      // (color, bold, underline, alignment, lists). If not, send just
      // plain text — smaller payloads and the backend treats the whole
      // text with the global ink color.
      const hasFormatting = textHtml && (
        /<(span|font)[^>]*color\s*[:=]/i.test(textHtml)
        || /<(b|strong|u)[\s>]/i.test(textHtml)
        || /text-align\s*:\s*(center|right)/i.test(textHtml)
        || /<li[\s>]/i.test(textHtml)
        || /font-weight\s*:\s*(bold|[6-9]\d\d)/i.test(textHtml)
        || /text-decoration[^;]*underline/i.test(textHtml)
      );
      const res = await fetch(`${getApiUrl()}/api/whiteboard/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          text: text.trim(),
          textHtml: hasFormatting ? textHtml : null,
          title: title.trim() || null,
          fontSize: Number(fontSize) || 96,
          charsPerSecond: Number(speed) || 6,
          fontFamily: fontFamily || null,
          transparent: Boolean(transparent),
          eraseAtEnd: Boolean(eraseAtEnd),
          inkColor: inkColor || null,
          projectId,
          slideId,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const enq = await res.json();
      // Async job: poll until completed. Renders can run 30–90s for long
      // APNGs — a synchronous request would hit Cloudflare's ~100s upstream
      // timeout (520). Polling sidesteps that entirely.
      const jobId = enq.jobId;
      if (!jobId) throw new Error('Resposta inesperada do servidor');
      const started = Date.now();
      const maxMs = 5 * 60 * 1000; // 5 min ceiling — long APNGs can be slow
      let consecutiveErrors = 0;
      const MAX_CONSEC_ERRORS = 8;  // ~16s of solid downtime before we give up
      let data = null;
      // eslint-disable-next-line no-constant-condition
      while (true) {
        await new Promise((r) => setTimeout(r, 2000));
        let sres;
        try {
          sres = await fetch(`${getApiUrl()}/api/job/${jobId}`, {
            credentials: 'include',
          });
        } catch (netErr) {
          // Network blip — keep trying. Cloudflare may briefly drop the
          // upstream while the pod is under CPU/memory pressure.
          consecutiveErrors += 1;
          if (consecutiveErrors >= MAX_CONSEC_ERRORS) {
            throw new Error('Conexão perdida com o servidor após várias tentativas');
          }
          continue;
        }
        // 5xx (incl. Cloudflare 502/503/504/520/521/522/523/524) are
        // transient — keep polling. Only abort on 4xx (real client/auth
        // errors) or after too many consecutive transient failures.
        if (sres.status >= 500) {
          consecutiveErrors += 1;
          if (consecutiveErrors >= MAX_CONSEC_ERRORS) {
            throw new Error(`Servidor instável (${sres.status}) após ${MAX_CONSEC_ERRORS} tentativas`);
          }
          continue;
        }
        if (!sres.ok) {
          throw new Error(`Status HTTP ${sres.status}`);
        }
        consecutiveErrors = 0;
        const sjob = await sres.json();
        if (sjob.status === 'completed' && sjob.result) {
          data = sjob.result;
          break;
        }
        if (sjob.status === 'failed') {
          throw new Error(sjob.message || 'Falha na geração');
        }
        if (Date.now() - started > maxMs) {
          throw new Error('Timeout aguardando renderização (5min)');
        }
      }
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
            <div className="flex items-center justify-between mb-1">
              <Label htmlFor="wb-text">Texto a escrever</Label>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setShowAi((v) => !v)}
                data-testid="whiteboard-ai-toggle"
                className="h-7 px-2 text-xs text-violet-300 hover:text-violet-200 hover:bg-violet-500/10"
              >
                <Wand2 className="w-3 h-3 mr-1" />
                {showAi ? 'Ocultar IA' : 'Gerar com IA'}
              </Button>
            </div>
            {showAi && (
              <div className="mb-2 p-3 border border-violet-700/40 rounded-md bg-violet-500/5 space-y-2">
                <Label htmlFor="wb-ai-prompt" className="text-xs text-violet-200">
                  Instrução opcional (a IA já usa o título e conteúdo do slide
                  como contexto)
                </Label>
                <Input
                  id="wb-ai-prompt"
                  data-testid="whiteboard-ai-prompt-input"
                  placeholder="Ex.: tom motivacional, 2 linhas, focar nos benefícios"
                  value={aiPrompt}
                  onChange={(e) => setAiPrompt(e.target.value)}
                  maxLength={500}
                  disabled={aiBusy}
                />
                <Button
                  type="button"
                  onClick={handleGenerateAi}
                  disabled={aiBusy}
                  size="sm"
                  data-testid="whiteboard-ai-run-btn"
                  className="bg-violet-600 hover:bg-violet-700 w-full"
                >
                  {aiBusy ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Gerando com GPT-4o...</>
                  ) : (
                    <><Wand2 className="w-4 h-4 mr-2" /> Gerar texto agora</>
                  )}
                </Button>
                <p className="text-[10px] text-violet-200/70">
                  O texto gerado substituirá o conteúdo atual do campo abaixo.
                </p>
              </div>
            )}
            <Textarea
              id="wb-text-hidden"
              data-testid="whiteboard-text-input"
              value={text}
              readOnly
              className="hidden"
            />
            {/* Mini-RTF editor: contentEditable div that lets the author
                wrap selected text in inline color spans. The plain-text
                `text` and rich `textHtml` are kept in sync. */}
            <div className="rounded-md border border-slate-700 bg-slate-950/40 overflow-hidden">
              <div className="flex flex-wrap items-center gap-1 px-2 py-1.5 border-b border-slate-700 bg-slate-900/40">
                <span className="text-[10px] text-slate-400 mr-1 flex items-center gap-1">
                  <Palette className="w-3 h-3" />
                  Cor:
                </span>
                {PALETTE.map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => applyColorToSelection(c)}
                    title={c}
                    data-testid={`color-swatch-${c}`}
                    className="w-5 h-5 rounded-sm border border-slate-600 hover:scale-110 transition-transform"
                    style={{ backgroundColor: c }}
                  />
                ))}
                <label className="ml-1 flex items-center gap-1 text-[10px] text-slate-400 cursor-pointer">
                  <span>+</span>
                  <input
                    type="color"
                    onChange={(e) => applyColorToSelection(e.target.value)}
                    data-testid="whiteboard-color-custom"
                    className="w-5 h-5 p-0 border-0 bg-transparent cursor-pointer"
                  />
                </label>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={clearFormattingOnSelection}
                  className="h-6 px-2 ml-auto text-[10px]"
                  data-testid="whiteboard-clear-format"
                >
                  <Eraser className="w-3 h-3 mr-1" /> Limpar
                </Button>
              </div>
              <div className="flex flex-wrap items-center gap-0.5 px-2 py-1 border-b border-slate-700 bg-slate-900/30">
                <Button
                  type="button" variant="ghost" size="sm"
                  onClick={() => runFormatCommand('bold')}
                  data-testid="whiteboard-fmt-bold"
                  title="Negrito (traços mais grossos)"
                  className="h-7 w-7 p-0"
                >
                  <Bold className="w-3.5 h-3.5" />
                </Button>
                <Button
                  type="button" variant="ghost" size="sm"
                  onClick={() => runFormatCommand('underline')}
                  data-testid="whiteboard-fmt-underline"
                  title="Sublinhado"
                  className="h-7 w-7 p-0"
                >
                  <Underline className="w-3.5 h-3.5" />
                </Button>
                <div className="w-px h-5 bg-slate-700 mx-1" />
                <Button
                  type="button" variant="ghost" size="sm"
                  onClick={() => runFormatCommand('justifyLeft')}
                  data-testid="whiteboard-fmt-align-left"
                  title="Alinhar à esquerda"
                  className="h-7 w-7 p-0"
                >
                  <AlignLeft className="w-3.5 h-3.5" />
                </Button>
                <Button
                  type="button" variant="ghost" size="sm"
                  onClick={() => runFormatCommand('justifyCenter')}
                  data-testid="whiteboard-fmt-align-center"
                  title="Centralizar"
                  className="h-7 w-7 p-0"
                >
                  <AlignCenter className="w-3.5 h-3.5" />
                </Button>
                <Button
                  type="button" variant="ghost" size="sm"
                  onClick={() => runFormatCommand('justifyRight')}
                  data-testid="whiteboard-fmt-align-right"
                  title="Alinhar à direita"
                  className="h-7 w-7 p-0"
                >
                  <AlignRight className="w-3.5 h-3.5" />
                </Button>
                <div className="w-px h-5 bg-slate-700 mx-1" />
                <Button
                  type="button" variant="ghost" size="sm"
                  onClick={() => runFormatCommand('insertUnorderedList')}
                  data-testid="whiteboard-fmt-bullet"
                  title="Lista com marcadores"
                  className="h-7 w-7 p-0"
                >
                  <List className="w-3.5 h-3.5" />
                </Button>
              </div>
              <div
                ref={editorRef}
                contentEditable
                suppressContentEditableWarning
                onInput={syncEditorState}
                onBlur={syncEditorState}
                onPaste={(e) => {
                  // Strip rich formatting from external paste sources —
                  // we want to start clean and let the author apply our
                  // palette colors deliberately.
                  e.preventDefault();
                  const pasted = (e.clipboardData || window.clipboardData)
                    .getData('text/plain');
                  document.execCommand('insertText', false, pasted);
                }}
                data-testid="whiteboard-text-editor"
                className="min-h-[120px] max-h-[300px] overflow-y-auto px-3 py-2 text-sm font-mono outline-none focus:bg-slate-900/30"
                style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
                aria-label="Texto a escrever"
              />
            </div>
            <p className="text-[10px] text-muted-foreground mt-1">
              {text.length}/2000 caracteres. <strong>Selecione um trecho</strong>
              {' '}e clique numa cor para destacá-lo. Cor padrão das letras: 
              <input
                type="color"
                value={inkColor}
                onChange={(e) => setInkColor(e.target.value)}
                data-testid="whiteboard-default-ink-color"
                className="ml-1 w-6 h-4 align-middle border border-slate-600 cursor-pointer p-0"
              />
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

          <div className="flex items-center justify-between p-3 border border-slate-700 rounded-md bg-slate-900/30">
            <div className="flex-1 pr-3">
              <Label htmlFor="wb-erase-at-end" className="flex items-center gap-2 cursor-pointer">
                <Eraser className="w-4 h-4" /> Apagar ao final
              </Label>
              <p className="text-[10px] text-muted-foreground mt-1">
                Adiciona um <strong>apagador estilo lousa</strong> passando
                horizontalmente após a escrita — ideal para encadear vários
                whiteboards no Timeline sem que o texto anterior fique na tela.
              </p>
            </div>
            <Switch
              id="wb-erase-at-end"
              data-testid="whiteboard-erase-at-end-toggle"
              checked={eraseAtEnd}
              onCheckedChange={setEraseAtEnd}
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
