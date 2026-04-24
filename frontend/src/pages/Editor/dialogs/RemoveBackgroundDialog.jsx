import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '../../../components/ui/dialog';
import { Button } from '../../../components/ui/button';
import { Slider } from '../../../components/ui/slider';
import { Loader2, Pipette, X, Check, Scissors, Wand2 } from 'lucide-react';
import { toast } from 'sonner';
import { getApiUrl } from '../../../utils/apiUrl';

const authHeaders = (extra = {}) => {
  const t = localStorage.getItem('scormify_token');
  return t ? { Authorization: `Bearer ${t}`, ...extra } : extra;
};

/**
 * RemoveBackgroundDialog — in-browser background removal by color key.
 * Works perfectly for logos, signatures, and any image with a mostly solid
 * background (white/black/any uniform color). Zero server calls for the
 * processing itself — only the final upload.
 *
 * Props:
 *   open:       boolean — dialog open state
 *   imageUrl:   string  — source image URL (asset URL or data URL)
 *   projectId:  string  — target project for the new asset
 *   onApply:    (newUrl) => void — called when the processed image is saved
 *   onClose:    () => void
 */
export default function RemoveBackgroundDialog({ open, imageUrl, projectId, onApply, onClose }) {
  const [keyColor, setKeyColor] = useState({ r: 255, g: 255, b: 255 });
  const [tolerance, setTolerance] = useState(28);
  const [softness, setSoftness] = useState(12);
  const [pickMode, setPickMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const origCanvasRef = useRef(null);   // raw image, hidden
  const previewCanvasRef = useRef(null); // visible result
  const origImageRef = useRef(null);
  const API = getApiUrl();

  // Load source image once per open
  useEffect(() => {
    if (!open || !imageUrl) return;
    setLoading(true);
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      origImageRef.current = img;
      // Auto-detect probable background color: sample the 4 corner pixels
      // and average them. Works well for logos where corners = background.
      const oc = origCanvasRef.current;
      oc.width = img.naturalWidth;
      oc.height = img.naturalHeight;
      const octx = oc.getContext('2d');
      octx.drawImage(img, 0, 0);
      try {
        const w = oc.width, h = oc.height;
        const samples = [
          octx.getImageData(0, 0, 1, 1).data,
          octx.getImageData(w - 1, 0, 1, 1).data,
          octx.getImageData(0, h - 1, 1, 1).data,
          octx.getImageData(w - 1, h - 1, 1, 1).data,
        ];
        const avg = samples.reduce((a, s) => ({ r: a.r + s[0], g: a.g + s[1], b: a.b + s[2] }), { r: 0, g: 0, b: 0 });
        setKeyColor({
          r: Math.round(avg.r / samples.length),
          g: Math.round(avg.g / samples.length),
          b: Math.round(avg.b / samples.length),
        });
      } catch {
        // Fallback to pure white
      }
      setLoading(false);
    };
    img.onerror = () => {
      toast.error('Nao foi possivel carregar a imagem.');
      setLoading(false);
      onClose?.();
    };
    img.src = imageUrl;
  }, [open, imageUrl, onClose]);

  // Process preview whenever any parameter changes
  const processPreview = useCallback(() => {
    const img = origImageRef.current;
    const canvas = previewCanvasRef.current;
    if (!img || !canvas) return;

    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);

    const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = imgData.data;

    // Tolerance 0-100 → color distance in Lab-like space (simplified RGB)
    const tol = tolerance * 2.55;              // solid cutoff
    const edge = (tolerance + softness) * 2.55; // feathered edge

    for (let i = 0; i < data.length; i += 4) {
      const dr = data[i] - keyColor.r;
      const dg = data[i + 1] - keyColor.g;
      const db = data[i + 2] - keyColor.b;
      const dist = Math.sqrt(dr * dr + dg * dg + db * db);
      if (dist <= tol) {
        data[i + 3] = 0;
      } else if (dist < edge) {
        data[i + 3] = Math.round(data[i + 3] * ((dist - tol) / (edge - tol)));
      }
    }
    ctx.putImageData(imgData, 0, 0);
  }, [keyColor, tolerance, softness]);

  useEffect(() => {
    if (!loading) processPreview();
  }, [loading, processPreview]);

  // Eye-dropper on the preview
  const handlePreviewClick = (e) => {
    if (!pickMode) return;
    const canvas = previewCanvasRef.current;
    if (!canvas || !origImageRef.current) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.floor(((e.clientX - rect.left) / rect.width) * canvas.width);
    const y = Math.floor(((e.clientY - rect.top) / rect.height) * canvas.height);
    const octx = origCanvasRef.current.getContext('2d');
    const p = octx.getImageData(x, y, 1, 1).data;
    setKeyColor({ r: p[0], g: p[1], b: p[2] });
    setPickMode(false);
  };

  const handleReset = () => {
    setKeyColor({ r: 255, g: 255, b: 255 });
    setTolerance(28);
    setSoftness(12);
  };

  const handleApply = async () => {
    const canvas = previewCanvasRef.current;
    if (!canvas || !projectId) return;
    setSaving(true);
    try {
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
      if (!blob) throw new Error('Falha ao gerar imagem');
      const form = new FormData();
      form.append('file', blob, `bg-removed-${Date.now()}.png`);
      const res = await fetch(`${API}/api/projects/${projectId}/media`, {
        method: 'POST',
        headers: authHeaders(),
        body: form,
      });
      if (!res.ok) throw new Error(`Erro ${res.status} ao salvar imagem`);
      const data = await res.json();
      toast.success('Fundo removido! Imagem atualizada.');
      onApply?.(data.url);
      onClose?.();
    } catch (e) {
      toast.error(e.message || 'Falha ao aplicar');
    } finally {
      setSaving(false);
    }
  };

  const hex = '#' + [keyColor.r, keyColor.g, keyColor.b]
    .map(c => c.toString(16).padStart(2, '0')).join('');

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose?.()}>
      <DialogContent className="max-w-3xl bg-slate-900 border-slate-700 text-white">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Scissors className="w-4 h-4 text-emerald-400" />
            Remover Fundo
          </DialogTitle>
          <DialogDescription className="text-slate-400">
            Funciona melhor com logos e imagens de fundo solido (branco, preto ou qualquer cor uniforme).
          </DialogDescription>
        </DialogHeader>

        <div className="grid md:grid-cols-[1fr_240px] gap-4">
          {/* Preview area (checkerboard background so transparency is visible) */}
          <div
            className="relative rounded-lg overflow-hidden border border-slate-700"
            style={{
              backgroundImage:
                'linear-gradient(45deg, #334155 25%, transparent 25%), linear-gradient(-45deg, #334155 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #334155 75%), linear-gradient(-45deg, transparent 75%, #334155 75%)',
              backgroundSize: '20px 20px',
              backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0',
              backgroundColor: '#1e293b',
              minHeight: 320,
            }}
          >
            {loading ? (
              <div className="flex items-center justify-center h-80 text-slate-400 gap-2">
                <Loader2 className="w-5 h-5 animate-spin" /> Carregando imagem...
              </div>
            ) : (
              <canvas
                ref={previewCanvasRef}
                onClick={handlePreviewClick}
                className={`w-full h-auto max-h-[420px] object-contain ${pickMode ? 'cursor-crosshair' : 'cursor-default'}`}
                data-testid="bg-preview-canvas"
              />
            )}
            <canvas ref={origCanvasRef} className="hidden" />
          </div>

          {/* Controls */}
          <div className="space-y-5">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-2">
                Cor do fundo
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={hex}
                  onChange={(e) => {
                    const v = e.target.value;
                    setKeyColor({
                      r: parseInt(v.slice(1, 3), 16),
                      g: parseInt(v.slice(3, 5), 16),
                      b: parseInt(v.slice(5, 7), 16),
                    });
                  }}
                  className="h-9 w-12 rounded cursor-pointer bg-transparent border border-slate-700"
                  data-testid="bg-color-picker"
                />
                <code className="text-xs text-slate-300 flex-1">{hex.toUpperCase()}</code>
                <Button
                  type="button"
                  size="sm"
                  variant={pickMode ? 'default' : 'outline'}
                  onClick={() => setPickMode(v => !v)}
                  className={pickMode ? 'bg-emerald-600 hover:bg-emerald-700' : 'border-slate-700'}
                  title="Clique aqui e depois na imagem para escolher a cor"
                  data-testid="bg-picker-btn"
                >
                  <Pipette className="w-4 h-4" />
                </Button>
              </div>
              {pickMode && (
                <p className="text-[11px] text-emerald-300 mt-1">
                  Clique em qualquer ponto da imagem para usar aquela cor.
                </p>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-2">
                Tolerancia <span className="text-slate-500 ml-1">{tolerance}</span>
              </label>
              <Slider
                value={[tolerance]}
                onValueChange={(v) => setTolerance(v[0])}
                min={0}
                max={100}
                step={1}
                data-testid="bg-tolerance-slider"
              />
              <p className="text-[10px] text-slate-500 mt-1">
                Quanto maior, mais variacoes da cor sao removidas.
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-2">
                Suavidade das bordas <span className="text-slate-500 ml-1">{softness}</span>
              </label>
              <Slider
                value={[softness]}
                onValueChange={(v) => setSoftness(v[0])}
                min={0}
                max={50}
                step={1}
                data-testid="bg-softness-slider"
              />
              <p className="text-[10px] text-slate-500 mt-1">
                Transicao suave entre o que fica e o que e removido.
              </p>
            </div>

            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={handleReset}
              className="w-full border-slate-700 text-slate-300 hover:bg-slate-800"
              data-testid="bg-reset-btn"
            >
              <Wand2 className="w-3.5 h-3.5 mr-1" /> Restaurar padroes
            </Button>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
          <Button
            type="button"
            variant="outline"
            onClick={() => onClose?.()}
            disabled={saving}
            className="border-slate-700 text-slate-300 hover:bg-slate-800"
            data-testid="bg-cancel-btn"
          >
            <X className="w-4 h-4 mr-1" /> Cancelar
          </Button>
          <Button
            type="button"
            onClick={handleApply}
            disabled={saving || loading}
            className="bg-emerald-600 hover:bg-emerald-700"
            data-testid="bg-apply-btn"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Check className="w-4 h-4 mr-1" />}
            {saving ? 'Aplicando...' : 'Aplicar'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
