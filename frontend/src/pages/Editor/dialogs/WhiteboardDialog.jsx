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
import { authHeaders } from '../../../contexts/AuthContext';

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

function WhiteboardPlanPreview({ plan }) {
  const operations = plan?.ops || [];
  return (
    <div className="rounded-md overflow-hidden border border-slate-700 bg-white">
      <svg
        viewBox="0 0 1920 1080"
        role="img"
        aria-label="Prévia visual do plano do Whiteboard"
        className="block w-full aspect-video"
      >
        <defs>
          <marker id="wb-plan-arrow" markerWidth="14" markerHeight="14" refX="11" refY="5" orient="auto">
            <path d="M 0 0 L 12 5 L 0 10 z" fill="#334155" />
          </marker>
        </defs>
        <rect width="1920" height="1080" fill="#fff" />
        {operations.map((op, index) => {
          const color = op.color || '#1f2937';
          const key = op.id || `${op.type}-${index}`;
          if (op.type === 'text') {
            return (
              <text
                key={key}
                x={op.x}
                y={op.y}
                fill={color}
                fontSize={op.font_size || 80}
                dominantBaseline="hanging"
                fontFamily="'Caveat', 'Segoe Print', cursive"
              >
                {op.text}
              </text>
            );
          }
          if (op.type === 'rectangle') {
            return <rect key={key} x={op.x} y={op.y} width={op.w} height={op.h} fill="none" stroke={color} strokeWidth={op.width || 6} rx="8" />;
          }
          if (op.type === 'circle') {
            return <ellipse key={key} cx={op.cx} cy={op.cy} rx={op.rx} ry={op.ry} fill="none" stroke={color} strokeWidth={op.width || 6} />;
          }
          if (op.type === 'arrow') {
            return <line key={key} x1={op.x1} y1={op.y1} x2={op.x2} y2={op.y2} stroke={color} strokeWidth={op.width || 7} markerEnd="url(#wb-plan-arrow)" />;
          }
          if (op.type === 'underline') {
            return <line key={key} x1={op.x1} y1={op.y1} x2={op.x2} y2={op.y1} stroke={color} strokeWidth={op.width || 5} />;
          }
          if (op.type === 'icon') {
            const size = op.size || 220;
            return (
              <g key={key}>
                <rect x={op.x - size / 2} y={op.y - size / 2} width={size} height={size} fill="none" stroke={color} strokeWidth={op.width || 5} strokeDasharray="18 12" rx="20" />
                <text x={op.x} y={op.y} fill={color} fontSize="34" textAnchor="middle" dominantBaseline="middle">{op.name}</text>
              </g>
            );
          }
          return null;
        })}
      </svg>
    </div>
  );
}

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
  // Eraser motion pattern. "horizontal" sweeps every stripe left→right.
  // "zigzag" alternates direction per stripe (serpentine path) — more
  // organic / teacher-like. Only meaningful when eraseAtEnd is ON.
  const [eraseStyle, setEraseStyle] = useState(() => _lsRead('eraseStyle', 'horizontal'));
  // Drawing implement — "pen" (sleek minimalist pen) or "hand"
  // (stylized hand holding a pen). Persisted in localStorage so the
  // author's preference survives across dialog opens.
  const [tool, setTool] = useState(() => _lsRead('tool', 'pen'));
  const [fonts, setFonts] = useState([]);
  const [busy, setBusy] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [showAi, setShowAi] = useState(false);
  // AI render-plan mode: instead of writing text linearly, the author
  // describes the scene in natural language ("escreva X, faça círculo
  // vermelho em volta, seta para Y...") and the backend asks OpenAI
  // to produce a structured plan with shape ops. Preview the plan
  // before rendering so unexpected layouts can be caught early.
  const [planMode, setPlanMode] = useState(() => _lsRead('planMode', false));
  const [planDescription, setPlanDescription] = useState('');
  const [aiPlan, setAiPlan] = useState(null);  // { summary, ops }
  const [planBusy, setPlanBusy] = useState(false);
  const [allowColorPerShape, setAllowColorPerShape] = useState(() => _lsRead('allowColorPerShape', true));
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
    fetch(`${getApiUrl()}/api/whiteboard/fonts`, {
      credentials: 'include',
      headers: authHeaders(),
    })
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
  useEffect(() => { _lsWrite('eraseStyle', eraseStyle); }, [eraseStyle]);
  useEffect(() => { _lsWrite('tool', tool); }, [tool]);
  useEffect(() => { _lsWrite('planMode', planMode); }, [planMode]);
  useEffect(() => { _lsWrite('allowColorPerShape', allowColorPerShape); }, [allowColorPerShape]);

  const handleGenerateAi = async () => {
    setAiBusy(true);
    try {
      const res = await fetch(`${getApiUrl()}/api/whiteboard/generate-text`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
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
        headers: authHeaders({ 'Content-Type': 'application/json' }),
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
          eraseStyle: eraseStyle || 'horizontal',
          tool: tool || 'pen',
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
            headers: authHeaders(),
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

  // ── AI plan flow ──────────────────────────────────────────────────
  // The plan mode operates in 2 steps so the author can review what
  // the LLM will draw BEFORE the (potentially slow) pen-trace render
  // kicks off:
  //   1. POST /ai-plan       → returns {summary, ops}, displayed below
  //   2. POST /generate-from-plan → kicks off the same async job pipeline
  //                                 we use for the text-only renderer
  const handleGeneratePlan = async () => {
    if (!planDescription.trim()) {
      toast.error('Descreva o que quer desenhar');
      return;
    }
    setPlanBusy(true);
    setAiPlan(null);
    try {
      const res = await fetch(`${getApiUrl()}/api/whiteboard/ai-plan`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        credentials: 'include',
        body: JSON.stringify({
          description: planDescription.trim(),
          inkColor: inkColor || null,
          allowColorPerShape: Boolean(allowColorPerShape),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const plan = await res.json();
      setAiPlan(plan);
      toast.success(`Plano gerado com ${plan.ops?.length || 0} operações`);
    } catch (e) {
      toast.error(e.message || 'Falha ao gerar plano');
    }
    setPlanBusy(false);
  };

  const handleRenderFromPlan = async () => {
    if (!aiPlan || !aiPlan.ops?.length) {
      toast.error('Gere um plano primeiro');
      return;
    }
    setBusy(true);
    setResult(null);
    try {
      const res = await fetch(`${getApiUrl()}/api/whiteboard/generate-from-plan`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        credentials: 'include',
        body: JSON.stringify({
          plan: aiPlan,
          fontFamily: fontFamily || null,
          transparent: Boolean(transparent),
          title: title.trim() || null,
          tool: tool || 'pen',
          projectId,
          slideId,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const enq = await res.json();
      const jobId = enq.jobId;
      if (!jobId) throw new Error('Resposta inesperada do servidor');
      // Reuse the same polling loop conventions as the text generate
      // path (5min ceiling, 8 consecutive transient errors before giving
      // up). Long shape-heavy plans can run 30–60s.
      const started = Date.now();
      const maxMs = 5 * 60 * 1000;
      let consecutiveErrors = 0;
      const MAX_CONSEC_ERRORS = 8;
      let data = null;
      // eslint-disable-next-line no-constant-condition
      while (true) {
        await new Promise((r) => setTimeout(r, 2000));
        let sres;
        try {
          sres = await fetch(`${getApiUrl()}/api/job/${jobId}`, {
            credentials: 'include',
            headers: authHeaders(),
          });
        } catch {
          consecutiveErrors += 1;
          if (consecutiveErrors >= MAX_CONSEC_ERRORS) {
            throw new Error('Conexão perdida após várias tentativas');
          }
          continue;
        }
        if (sres.status >= 500) {
          consecutiveErrors += 1;
          if (consecutiveErrors >= MAX_CONSEC_ERRORS) {
            throw new Error(`Servidor instável (${sres.status})`);
          }
          continue;
        }
        if (!sres.ok) throw new Error(`HTTP ${sres.status}`);
        consecutiveErrors = 0;
        const sjob = await sres.json();
        if (sjob.status === 'completed' && sjob.result) { data = sjob.result; break; }
        if (sjob.status === 'failed') throw new Error(sjob.message || 'Falha na geração');
        if (Date.now() - started > maxMs) throw new Error('Timeout aguardando renderização');
      }
      setResult({ url: `${getApiUrl()}${data.videoUrl}`, format: data.format });
      toast.success(`Whiteboard gerado (${data.duration.toFixed(1)}s)`);
      if (onGenerated) onGenerated(data);
    } catch (e) {
      toast.error(e.message || 'Falha ao renderizar plano');
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
          {/* AI plan mode toggle. When ON, the standard text editor is
              replaced with a description textarea + plan preview panel.
              All render settings (transparent, erase, font) still apply. */}
          <div className="flex items-center justify-between p-3 border border-amber-700/40 rounded-md bg-amber-950/20">
            <div className="flex-1 pr-3">
              <Label htmlFor="wb-plan-mode" className="flex items-center gap-2 cursor-pointer">
                <Wand2 className="w-4 h-4 text-amber-400" /> Modo IA + Formas
              </Label>
              <p className="text-[10px] text-muted-foreground mt-1">
                Descreva em português o que quer desenhar — a IA cria um plano
                com <strong>texto + setas, círculos, retângulos, sublinhados</strong> e
                a caneta executa em ordem. Útil pra <strong>destacar conceitos</strong>,
                <strong> conectar ideias</strong> e dar vida didática aos slides.
              </p>
            </div>
            <Switch
              id="wb-plan-mode"
              data-testid="whiteboard-plan-mode-toggle"
              checked={planMode}
              onCheckedChange={setPlanMode}
            />
          </div>

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

          {planMode && (
            <div className="border border-amber-700/30 rounded-md bg-amber-950/10 p-3 space-y-3">
              <div>
                <Label htmlFor="wb-plan-desc" className="text-xs">Descreva o que desenhar (PT-BR)</Label>
                <Textarea
                  id="wb-plan-desc"
                  data-testid="whiteboard-plan-description-input"
                  placeholder="Ex.: Escreva 'Vendas Q4' no topo. Faça um círculo vermelho em volta. Embaixo, escreva 'Meta: R$ 1M' em verde. Desenhe uma seta azul apontando do círculo até o valor."
                  value={planDescription}
                  onChange={(e) => {
                    setPlanDescription(e.target.value);
                    setAiPlan(null);
                  }}
                  rows={5}
                  maxLength={2000}
                  disabled={planBusy || busy}
                  className="text-sm"
                />
                <div className="flex items-center justify-between mt-1">
                  <span className="text-[10px] text-muted-foreground">
                    {planDescription.length}/2000 — OpenAI vai interpretar e validar a geometria
                  </span>
                  <label className="flex items-center gap-1.5 text-[10px] text-muted-foreground cursor-pointer">
                    <Switch
                      data-testid="whiteboard-plan-multicolor-toggle"
                      checked={allowColorPerShape}
                      onCheckedChange={(checked) => {
                        setAllowColorPerShape(checked);
                        setAiPlan(null);
                      }}
                      className="scale-75"
                    />
                    Cores diferentes por forma
                  </label>
                </div>
              </div>
              <Button
                type="button"
                onClick={handleGeneratePlan}
                disabled={planBusy || busy || !planDescription.trim()}
                size="sm"
                data-testid="whiteboard-plan-generate-btn"
                className="bg-amber-600 hover:bg-amber-700 w-full"
              >
                {planBusy ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Gerando plano...</>
                ) : (
                  <><Sparkles className="w-4 h-4 mr-2" /> Gerar plano preciso</>
                )}
              </Button>

              {aiPlan && (
                <div className="border border-amber-700/40 rounded-md bg-amber-500/5 p-3 space-y-2" data-testid="whiteboard-plan-preview">
                  <div className="text-xs">
                    <strong className="text-amber-300">Plano:</strong>
                    <span className="text-slate-200 ml-1">{aiPlan.summary}</span>
                  </div>
                  <WhiteboardPlanPreview plan={aiPlan} />
                  {aiPlan.quality && (
                    <div className="text-[10px] text-slate-300 flex flex-wrap items-center gap-2">
                      <span className={aiPlan.quality.score >= 88 ? 'text-emerald-400' : 'text-amber-300'}>
                        Qualidade geométrica: {aiPlan.quality.score}/100
                      </span>
                      {(aiPlan.quality.warnings || []).map((warning) => (
                        <span key={warning} className="rounded bg-amber-950/60 px-1.5 py-0.5 text-amber-200">
                          {warning}
                        </span>
                      ))}
                    </div>
                  )}
                  <details className="text-[10px] text-slate-400">
                    <summary className="cursor-pointer hover:text-slate-200">
                      Operações ({aiPlan.ops?.length || 0})
                    </summary>
                    <ul className="mt-1 space-y-0.5 max-h-32 overflow-y-auto font-mono">
                      {(aiPlan.ops || []).map((op, idx) => (
                        <li key={idx} className="flex items-center gap-2">
                          <span
                            className="inline-block w-2 h-2 rounded-full"
                            style={{ background: op.color || '#64748b' }}
                          />
                          <span className="text-amber-300">{op.type}</span>
                          {op.type === 'text' && <span>"{op.text}"</span>}
                          {op.type === 'circle' && <span>raio {op.rx}×{op.ry} em ({op.cx},{op.cy})</span>}
                          {op.type === 'rectangle' && <span>{op.w}×{op.h} em ({op.x},{op.y})</span>}
                          {op.type === 'arrow' && <span>({op.x1},{op.y1})→({op.x2},{op.y2})</span>}
                          {op.type === 'underline' && <span>({op.x1},{op.y1})→({op.x2})</span>}
                        </li>
                      ))}
                    </ul>
                  </details>
                </div>
              )}
            </div>
          )}

          {!planMode && (
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
          )}

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

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="wb-tool">Ferramenta de desenho</Label>
              <Select value={tool} onValueChange={setTool}>
                <SelectTrigger id="wb-tool" data-testid="whiteboard-tool-select">
                  <SelectValue placeholder="Escolha a ferramenta" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pen" data-testid="tool-opt-pen">
                    🖊️ Caneta
                  </SelectItem>
                  <SelectItem value="hand" data-testid="tool-opt-hand">
                    ✋ Mão (cartoon)
                  </SelectItem>
                  <SelectItem value="hand_real" data-testid="tool-opt-hand-real">
                    🤚 Mão realista
                  </SelectItem>
                </SelectContent>
              </Select>
              <p className="text-[10px] text-muted-foreground mt-1">
                &quot;Mão&quot; mostra uma mão estilizada segurando a caneta (estilo VideoScribe).
              </p>
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

          {eraseAtEnd && (
            <div className="p-3 border border-slate-700 rounded-md bg-slate-900/30 space-y-2">
              <Label htmlFor="wb-erase-style">Padrão do apagador</Label>
              <Select value={eraseStyle} onValueChange={setEraseStyle}>
                <SelectTrigger id="wb-erase-style" data-testid="whiteboard-erase-style-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="horizontal" data-testid="erase-style-horizontal">
                    Horizontal — esquerda → direita em cada linha
                  </SelectItem>
                  <SelectItem value="zigzag" data-testid="erase-style-zigzag">
                    Zig-Zag — alterna direção (serpenteia)
                  </SelectItem>
                </SelectContent>
              </Select>
              <p className="text-[10px] text-muted-foreground">
                <strong>Zig-Zag</strong> evita o "teletransporte" do apagador entre
                linhas — fica mais natural, como um professor real.
              </p>
            </div>
          )}

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
            onClick={planMode ? handleRenderFromPlan : handleGenerate}
            disabled={busy || planBusy || (planMode ? !aiPlan?.ops?.length : !text.trim())}
            className="bg-amber-600 hover:bg-amber-700"
            data-testid="whiteboard-generate-btn"
          >
            {busy ? (
              <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Gerando...</>
            ) : (
              <><Sparkles className="w-4 h-4 mr-2" />
                {planMode ? 'Renderizar Plano' : 'Gerar e Aplicar ao Slide'}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
