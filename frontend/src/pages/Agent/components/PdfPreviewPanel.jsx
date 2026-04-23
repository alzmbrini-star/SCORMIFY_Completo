import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, X as IconX, FileText, Image as ImageIcon, Save, Sparkles, Copy } from 'lucide-react';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Badge } from '../../../components/ui/badge';
import { toast } from 'sonner';

const authHeaders = (extra = {}) => {
  const t = localStorage.getItem('scormify_token');
  return t ? { Authorization: `Bearer ${t}`, ...extra } : extra;
};

/**
 * PdfPreviewPanel - appears after a PDF is uploaded and before the user clicks
 * "Analisar". Lets the user review each image extracted from the PDF, decide
 * which ones to include in the course, and add/edit captions.
 *
 * Props:
 *   - sessionId: agent session id
 *   - apiBase: absolute API url (REACT_APP_BACKEND_URL)
 *   - onSaved(): optional callback when user clicks "Salvar preferencias"
 */
export default function PdfPreviewPanel({ sessionId, apiBase, onSaved, onStatusChange }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [faithfulLoading, setFaithfulLoading] = useState(false);
  const [preview, setPreview] = useState(null);
  const [images, setImages] = useState([]);

  useEffect(() => {
    let active = true;
    let pollTimer = null;

    const load = async () => {
      // If Modo Fiel is running, its own polling loop drives the UI state.
      // Don't let the normal extraction poll overwrite it.
      if (faithfulLoading) {
        pollTimer = setTimeout(load, 2000);
        return;
      }
      try {
        // First check the extraction status
        const sessRes = await fetch(`${apiBase}/api/agent/sessions/${sessionId}?light=1`, {
          headers: authHeaders(),
        });
        const sessData = sessRes.ok ? await sessRes.json() : {};
        const status = sessData?.pdfExtractionStatus?.status;

        if (status === 'pdf_ready') {
          // PDF uploaded and ready for Modo Fiel. Don't poll — just show CTA.
          if (!active) return;
          if (onStatusChange) onStatusChange(false);
          setPreview({
            hasPdf: true,
            pdfReady: true,
            fileName: sessData.fileName || '',
          });
          setImages([]);
          setLoading(false);
          return;
        }

        if (status === 'processing') {
          if (!active) return;
          if (onStatusChange) onStatusChange(true);
          setPreview({
            hasPdf: true,
            processing: true,
            statusMessage: sessData.pdfExtractionStatus.message || 'Processando PDF...',
            progress: sessData.pdfExtractionStatus.progress || 0,
            fileName: sessData.fileName || '',
          });
          setImages([]);
          // Keep polling every 1.5s while processing (matches backend throttle)
          pollTimer = setTimeout(load, 1500);
          setLoading(false);
          return;
        }

        if (status === 'error') {
          if (active) {
            if (onStatusChange) onStatusChange(false);
            // Don't hide the panel — fetch preview so user sees the Modo Fiel
            // fallback with a friendly error message.
            try {
              const res = await fetch(`${apiBase}/api/agent/sessions/${sessionId}/pdf-preview`, {
                headers: authHeaders(),
              });
              if (res.ok) {
                const data = await res.json();
                setPreview(data);
                setImages((data.images || []).map(img => ({ ...img })));
              } else {
                setPreview({ hasPdf: false });
              }
            } catch {
              setPreview({ hasPdf: false });
            }
          }
          return;
        }

        // Extraction done (or no PDF) — fetch the preview endpoint normally
        if (onStatusChange) onStatusChange(false);
        const res = await fetch(`${apiBase}/api/agent/sessions/${sessionId}/pdf-preview`, {
          headers: authHeaders(),
        });
        if (!res.ok) throw new Error('Nao foi possivel carregar preview');
        const data = await res.json();
        if (!active) return;
        setPreview(data);
        setImages((data.images || []).map(img => ({ ...img })));
      } catch (e) {
        if (active) toast.error(e.message || 'Erro ao carregar preview');
      } finally {
        if (active) setLoading(false);
      }
    };

    load();
    return () => {
      active = false;
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [sessionId, apiBase]);

  const toggleInclude = (idx) => {
    setImages(prev => prev.map((it, i) => i === idx ? { ...it, included: !it.included } : it));
  };

  const setCaption = (idx, caption) => {
    setImages(prev => prev.map((it, i) => i === idx ? { ...it, caption } : it));
  };

  const selectAll = () => setImages(prev => prev.map(it => ({ ...it, included: true })));
  const selectNone = () => setImages(prev => prev.map(it => ({ ...it, included: false })));

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        images: images.map(img => ({
          filename: img.filename,
          included: img.included,
          caption: img.caption || '',
        })),
      };
      const res = await fetch(`${apiBase}/api/agent/sessions/${sessionId}/pdf-preview`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Erro ao salvar');
      const data = await res.json();
      toast.success(
        `Preferencias salvas: ${data.total - data.excluded} imagens incluidas, ${data.excluded} excluidas`
      );
      if (onSaved) onSaved(data);
    } catch (e) {
      toast.error(e.message || 'Falha ao salvar preferencias');
    } finally {
      setSaving(false);
    }
  };

  const handleGenerateFaithful = async () => {
    if (faithfulLoading) return;
    setFaithfulLoading(true);
    if (onStatusChange) onStatusChange(true);
    try {
      const res = await fetch(`${apiBase}/api/agent/sessions/${sessionId}/generate-faithful-course`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Erro ${res.status}`);
      }
      const data = await res.json();
      const projectId = data.projectId;
      if (!projectId) throw new Error('Resposta invalida do servidor');

      // Switch panel to "faithful processing" mode with its own progress
      setPreview(prev => ({
        ...(prev || {}),
        hasPdf: true,
        processing: true,
        faithfulMode: true,
        fileName: prev?.fileName || '',
        statusMessage: 'Renderizando paginas do PDF...',
        progress: 0,
      }));

      // Poll faithful status until done
      for (let i = 0; i < 600; i++) {  // 600 * 2s = 20 min max
        await new Promise(r => setTimeout(r, 2000));
        try {
          const sr = await fetch(`${apiBase}/api/projects/${projectId}/faithful-status`, {
            headers: authHeaders(),
          });
          if (!sr.ok) continue;
          const s = await sr.json();
          setPreview(prev => ({
            ...(prev || {}),
            hasPdf: true,
            processing: s.status === 'processing',
            faithfulMode: true,
            statusMessage: s.message || 'Renderizando...',
            progress: s.progress || 0,
          }));
          if (s.status === 'done') {
            toast.success('Curso fiel criado! Abrindo o editor...');
            setTimeout(() => navigate(`/editor/${projectId}`), 500);
            return;
          }
          if (s.status === 'error') {
            throw new Error(s.message || 'Falha ao gerar em Modo Fiel');
          }
        } catch (pollErr) {
          // Ignore transient poll errors (network/Cloudflare); keep polling
          console.warn('faithful poll retry:', pollErr);
        }
      }
      throw new Error('Tempo esgotado aguardando geracao do curso fiel');
    } catch (e) {
      toast.error(e.message || 'Falha ao gerar em Modo Fiel');
      setFaithfulLoading(false);
      if (onStatusChange) onStatusChange(false);
    }
  };

  if (loading) {
    return (
      <div
        data-testid="pdf-preview-loading"
        className="rounded-xl border border-slate-700 bg-slate-900/50 p-4 text-sm text-slate-400"
      >
        Carregando preview do PDF...
      </div>
    );
  }

  if (!preview?.hasPdf) return null;

  // Fresh PDF uploaded — offer Modo Fiel as the primary (and only) path.
  if (preview.pdfReady && !preview.processing && !preview.extractionFailed) {
    return (
      <div
        data-testid="pdf-preview-ready"
        className="rounded-xl border border-indigo-500/40 bg-gradient-to-br from-indigo-900/40 to-slate-900 overflow-hidden"
      >
        <div className="flex items-start gap-3 px-5 py-5">
          <div className="shrink-0 mt-1">
            <div className="w-10 h-10 rounded-full bg-indigo-500/20 border border-indigo-400/40 flex items-center justify-center">
              <FileText className="w-5 h-5 text-indigo-300" />
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <h4 className="text-base font-semibold text-white">
              PDF recebido {preview.fileName && <span className="text-indigo-200/80 font-normal">({preview.fileName})</span>}
            </h4>
            <p className="text-sm text-indigo-100/80 mt-1">
              Vamos gerar o curso em <b>Modo Fiel</b>: cada pagina vira um slide preservando
              o layout, cores, imagens e logos originais do PDF.
            </p>
            <ul className="text-xs text-indigo-200/70 mt-2 space-y-1 list-disc list-inside">
              <li>1 pagina do PDF = 1 slide identico</li>
              <li>Pula a IA e gera rapidamente</li>
              <li>Ideal para manuais, apresentacoes e materiais ja formatados</li>
            </ul>
          </div>
        </div>
        <div className="flex items-center justify-between px-5 py-4 bg-slate-900/80 border-t border-indigo-500/30">
          <p className="text-xs text-indigo-200/70">
            Preferiu usar outro metodo? Clique em &quot;Analisar Conteudo&quot; abaixo para gerar com IA baseado no texto.
          </p>
          <Button
            size="default"
            onClick={handleGenerateFaithful}
            disabled={faithfulLoading}
            className="bg-indigo-600 hover:bg-indigo-500 text-white shrink-0"
            data-testid="pdf-faithful-mode-btn"
          >
            <Sparkles className="w-4 h-4 mr-1.5" />
            {faithfulLoading ? 'Gerando...' : 'Gerar em Modo Fiel'}
          </Button>
        </div>
      </div>
    );
  }

  // Extraction failed or produced no images: offer Modo Fiel prominently.
  if (preview.extractionFailed) {
    return (
      <div
        data-testid="pdf-preview-failed"
        className="rounded-xl border border-amber-600/40 bg-slate-900/80 overflow-hidden"
      >
        <div className="flex items-start gap-3 px-4 py-4 bg-amber-900/20">
          <FileText className="w-6 h-6 text-amber-300 shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-semibold text-white">
              Extracao automatica nao produziu imagens {preview.fileName && <span className="text-amber-200/80 font-normal">({preview.fileName})</span>}
            </h4>
            <p className="text-xs text-amber-100/80 mt-1">
              {preview.statusMessage}
            </p>
          </div>
        </div>
        <div className="flex items-center justify-between px-4 py-3 bg-slate-900/80 border-t border-amber-700/30 gap-3">
          <p className="text-xs text-slate-300 flex-1">
            O <b>Modo Fiel</b> gera 1 slide por pagina do PDF, preservando o
            layout original (cores, imagens, logos). Recomendado para este PDF.
          </p>
          <Button
            size="sm"
            onClick={handleGenerateFaithful}
            disabled={faithfulLoading}
            className="bg-indigo-600 hover:bg-indigo-500 text-white shrink-0"
            data-testid="pdf-faithful-mode-btn-failed"
          >
            <Sparkles className="w-4 h-4 mr-1" />
            {faithfulLoading ? 'Gerando...' : 'Gerar em Modo Fiel'}
          </Button>
        </div>
      </div>
    );
  }

  if (preview.processing) {
    const pct = Math.max(0, Math.min(100, preview.progress || 0));
    const isFaithful = preview.faithfulMode;
    return (
      <div
        data-testid="pdf-preview-processing"
        className="rounded-xl border border-indigo-700/40 bg-slate-900/80 overflow-hidden"
      >
        <div className="flex items-start gap-3 px-4 pt-4 pb-2 bg-indigo-900/30">
          <div className="w-6 h-6 border-2 border-indigo-300 border-t-transparent rounded-full animate-spin shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-semibold text-white truncate">
              {isFaithful ? 'Gerando Modo Fiel' : 'Processando PDF'}... {preview.fileName && <span className="text-indigo-200/80 font-normal">({preview.fileName})</span>}
            </h4>
            <p className="text-xs text-indigo-200/80 mt-0.5">
              {preview.statusMessage}
            </p>
          </div>
          <span
            className="text-sm font-bold text-indigo-200 tabular-nums shrink-0"
            data-testid="pdf-preview-progress-pct"
          >
            {pct}%
          </span>
        </div>
        {/* Progress bar */}
        <div className="px-4 pb-3 bg-indigo-900/30">
          <div className="h-2 w-full bg-indigo-950/60 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-indigo-500 to-indigo-300 transition-all duration-500 ease-out rounded-full"
              style={{ width: `${pct}%` }}
              data-testid="pdf-preview-progress-bar"
            />
          </div>
          <p className="text-[11px] text-indigo-200/60 mt-2">
            {isFaithful
              ? 'Cada pagina esta sendo renderizada como slide. Voce sera redirecionado ao editor automaticamente.'
              : 'Esta tela atualiza automaticamente. Voce pode deixar essa aba aberta — vamos liberar o botao "Analisar" assim que terminar.'}
          </p>
        </div>

        {/* Show the escape-hatch Modo Fiel button ONLY when the normal
            extraction is running (not when Modo Fiel itself is processing) */}
        {!isFaithful && (
          <div className="flex items-center justify-between px-4 py-3 bg-slate-900/80 border-t border-indigo-700/30 gap-3">
            <div className="flex items-start gap-2 min-w-0 flex-1">
              <Copy className="w-4 h-4 text-indigo-300 mt-0.5 shrink-0" />
              <p className="text-xs text-indigo-200/80">
                Esta demorando? Voce pode pular a extracao e gerar o curso
                com <b>Modo Fiel</b> (cada pagina = 1 slide identico ao PDF).
              </p>
            </div>
            <Button
              size="sm"
              onClick={handleGenerateFaithful}
              disabled={faithfulLoading}
              className="bg-indigo-600 hover:bg-indigo-500 text-white shrink-0"
              data-testid="pdf-faithful-mode-btn-while-processing"
            >
              <Sparkles className="w-4 h-4 mr-1" />
              {faithfulLoading ? 'Gerando...' : 'Gerar em Modo Fiel'}
            </Button>
          </div>
        )}
      </div>
    );
  }

  const includedCount = images.filter(i => i.included).length;

  return (
    <div
      data-testid="pdf-preview-panel"
      className="rounded-xl border border-emerald-700/40 bg-slate-900/80 overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-700 px-4 py-3 bg-slate-900">
        <div className="flex items-center gap-3">
          <FileText className="w-5 h-5 text-emerald-400" />
          <div>
            <h4 className="text-sm font-semibold text-white">
              Imagens extraidas do PDF
            </h4>
            <p className="text-xs text-slate-400 mt-0.5">
              {preview.fileName} · {preview.totalPages} paginas
              {preview.scannedPages > 0 && ` (${preview.scannedPages} com OCR)`} ·
              {' '}{images.length} imagens encontradas
            </p>
          </div>
        </div>
        <Badge className="bg-emerald-600/20 text-emerald-300 border-emerald-500/30" data-testid="pdf-preview-count">
          {includedCount} / {images.length} incluidas
        </Badge>
      </div>

      {/* Faithful mode CTA */}
      <div className="flex items-center justify-between px-4 py-3 bg-indigo-900/40 border-b border-indigo-700/40">
        <div className="flex items-start gap-3">
          <Copy className="w-5 h-5 text-indigo-300 mt-0.5 shrink-0" />
          <div>
            <h5 className="text-sm font-semibold text-white">Modo Fiel — Pagina do PDF = Slide</h5>
            <p className="text-xs text-indigo-200/80 mt-0.5 max-w-2xl">
              Preserva o layout original do PDF pixel-a-pixel (cores, imagens, logos, setas, diagramas).
              Cada pagina vira um slide identico. Pula a IA — sem textos reescritos.
            </p>
          </div>
        </div>
        <Button
          size="sm"
          onClick={handleGenerateFaithful}
          disabled={faithfulLoading}
          className="bg-indigo-600 hover:bg-indigo-500 text-white shrink-0"
          data-testid="pdf-faithful-mode-btn"
        >
          <Sparkles className="w-4 h-4 mr-1" />
          {faithfulLoading ? 'Gerando...' : 'Gerar em Modo Fiel'}
        </Button>
      </div>

      {images.length === 0 ? (
        <div className="p-6 text-center text-sm text-slate-400 flex flex-col items-center gap-2">
          <ImageIcon className="w-8 h-8 text-slate-600" />
          Nenhuma imagem embutida foi encontrada neste PDF.<br />
          O conteudo textual sera usado normalmente na geracao do curso.
        </div>
      ) : (
        <>
          {/* Quick actions */}
          <div className="flex items-center gap-2 px-4 py-2 border-b border-slate-800 bg-slate-950/40">
            <Button
              size="sm"
              variant="outline"
              onClick={selectAll}
              className="h-7 text-xs border-slate-700 text-slate-300 hover:bg-slate-800"
              data-testid="pdf-preview-select-all"
            >
              Selecionar todas
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={selectNone}
              className="h-7 text-xs border-slate-700 text-slate-300 hover:bg-slate-800"
              data-testid="pdf-preview-select-none"
            >
              Desmarcar todas
            </Button>
            <div className="flex-1" />
            <Button
              size="sm"
              onClick={handleSave}
              disabled={saving}
              className="h-7 text-xs bg-emerald-600 hover:bg-emerald-700"
              data-testid="pdf-preview-save-btn"
            >
              <Save className="w-3.5 h-3.5 mr-1" />
              {saving ? 'Salvando...' : 'Salvar preferencias'}
            </Button>
          </div>

          {/* Grid */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 p-4 max-h-[420px] overflow-y-auto">
            {images.map((img, idx) => (
              <div
                key={img.filename}
                data-testid={`pdf-preview-item-${idx}`}
                className={
                  'relative rounded-lg border overflow-hidden transition-all ' +
                  (img.included
                    ? 'border-emerald-500/60 bg-slate-800/80'
                    : 'border-slate-700 bg-slate-900/60 opacity-60')
                }
              >
                <div className="relative aspect-video bg-slate-950 flex items-center justify-center">
                  <img
                    src={`${apiBase}${img.url}`}
                    alt={img.caption || img.filename}
                    loading="lazy"
                    className="w-full h-full object-contain"
                    onError={e => { e.currentTarget.style.opacity = '0.3'; }}
                  />
                  <button
                    type="button"
                    onClick={() => toggleInclude(idx)}
                    className={
                      'absolute top-1.5 right-1.5 w-7 h-7 rounded-full flex items-center justify-center transition ' +
                      (img.included
                        ? 'bg-emerald-500 text-white hover:bg-emerald-400'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600')
                    }
                    title={img.included ? 'Remover' : 'Incluir'}
                    data-testid={`pdf-preview-toggle-${idx}`}
                  >
                    {img.included ? <Check className="w-4 h-4" /> : <IconX className="w-4 h-4" />}
                  </button>
                  {img.pageHint && (
                    <span className="absolute bottom-1.5 left-1.5 text-[10px] px-1.5 py-0.5 rounded bg-black/60 text-slate-200">
                      {img.pageHint}
                    </span>
                  )}
                </div>
                <div className="p-2">
                  <Input
                    value={img.caption || ''}
                    onChange={e => setCaption(idx, e.target.value)}
                    disabled={!img.included}
                    placeholder="Legenda (opcional)"
                    maxLength={200}
                    className="h-7 text-[11px] bg-slate-950 border-slate-700 text-slate-200 placeholder:text-slate-500"
                    data-testid={`pdf-preview-caption-${idx}`}
                  />
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
