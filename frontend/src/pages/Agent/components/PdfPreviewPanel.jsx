import { useEffect, useState } from 'react';
import { Check, X as IconX, FileText, Image as ImageIcon, Save } from 'lucide-react';
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
export default function PdfPreviewPanel({ sessionId, apiBase, onSaved }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState(null);
  const [images, setImages] = useState([]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
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
    })();
    return () => { active = false; };
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
