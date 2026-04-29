import React, { useState, useEffect, useCallback } from 'react';
import { Button } from '../../../components/ui/button';
import { Card, CardContent } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { Textarea } from '../../../components/ui/textarea';
import { Input } from '../../../components/ui/input';
import {
  Loader2, Download, Check, Sparkles, X, Wand2, Info, Image as ImageIcon, Zap, Crown,
} from 'lucide-react';
import { toast } from 'sonner';
import { authHeaders } from '../../../contexts/AuthContext';
import { getApiUrl } from '../../../utils/apiUrl';

const API = getApiUrl();

// Polling configuration
const POLL_INTERVAL_MS = 2500;
const POLL_MAX_ATTEMPTS = 60; // 60 * 2.5s = 2.5 minutes max

/**
 * KreaPanel — Krea AI image generation panel.
 * - Model dropdown exposes the 11 curated models (Flux, Imagen 4, Nano Banana, ChatGPT, etc.)
 * - Dimension selector (width/height) capped per-model.
 * - Async job: POST /generate -> poll GET /jobs/{id} until completed.
 * - Save to project: POST /jobs/{id}/save -> returns a project-scoped asset URL.
 */
export default function KreaPanel({
  projectId,
  onImageSaved,
  onClose,
  initialPrompt = '',
  initialModelId = null,
}) {
  const [prompt, setPrompt] = useState(initialPrompt);
  const [models, setModels] = useState([]);
  const [modelId, setModelId] = useState(initialModelId);
  const [width, setWidth] = useState(1024);
  const [height, setHeight] = useState(576);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(null);
  const [jobStatus, setJobStatus] = useState(''); // scheduled | processing | completed | failed
  const [images, setImages] = useState([]);
  const [currentJobId, setCurrentJobId] = useState(null);
  const [error, setError] = useState('');
  const [configured, setConfigured] = useState(true);

  // Load models on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const statusRes = await fetch(`${API}/api/krea/status`, { headers: authHeaders() });
        if (!statusRes.ok) throw new Error('Falha ao verificar status Krea AI');
        const statusData = await statusRes.json();
        if (cancelled) return;
        if (!statusData.configured) {
          setConfigured(false);
          return;
        }
        const modelsRes = await fetch(`${API}/api/krea/models`, { headers: authHeaders() });
        if (!modelsRes.ok) throw new Error('Falha ao carregar modelos Krea');
        const modelsData = await modelsRes.json();
        if (cancelled) return;
        setModels(modelsData.models || []);
        if (!modelId && (modelsData.models || []).length) {
          // Default: flux-1-dev (fastest) unless caller preselected one
          const def = modelsData.models.find(m => m.id === 'flux-1-dev') || modelsData.models[0];
          setModelId(def.id);
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedModel = models.find(m => m.id === modelId);

  // Clamp width/height to model's max when model changes
  useEffect(() => {
    if (!selectedModel) return;
    setWidth(w => Math.min(w, selectedModel.maxWidth || 1920));
    setHeight(h => Math.min(h, selectedModel.maxHeight || 1920));
  }, [selectedModel]);

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim() || !modelId) return;
    setGenerating(true);
    setImages([]);
    setError('');
    setJobStatus('scheduled');
    setCurrentJobId(null);

    try {
      const res = await fetch(`${API}/api/krea/generate`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          modelId,
          prompt: prompt.trim(),
          width,
          height,
          projectId,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Erro ao iniciar geração Krea AI');
      }
      const job = await res.json();
      const jobId = job.job_id;
      if (!jobId) throw new Error('Resposta inválida do Krea (sem job_id)');
      setCurrentJobId(jobId);
      setJobStatus(job.status || 'scheduled');

      // Poll for completion
      let attempts = 0;
      while (attempts < POLL_MAX_ATTEMPTS) {
        await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));
        attempts += 1;
        const pollRes = await fetch(`${API}/api/krea/jobs/${jobId}`, { headers: authHeaders() });
        if (!pollRes.ok) continue;
        const data = await pollRes.json();
        const status = data.status || '';
        setJobStatus(status);
        if (status === 'completed') {
          const urls = (data.result || {}).urls || [];
          setImages(urls);
          if (urls.length === 0) {
            throw new Error('Krea retornou job concluído sem imagens');
          }
          toast.success(`${urls.length} imagem(s) gerada(s) com ${selectedModel?.label || modelId}`);
          break;
        }
        if (status === 'failed' || status === 'cancelled') {
          throw new Error(`Geração ${status === 'failed' ? 'falhou' : 'cancelada'} no Krea AI`);
        }
      }
      if (attempts >= POLL_MAX_ATTEMPTS) {
        throw new Error('Timeout aguardando geração (2.5min)');
      }
    } catch (e) {
      setError(e.message);
      toast.error(e.message);
    } finally {
      setGenerating(false);
    }
  }, [prompt, modelId, width, height, projectId, selectedModel]);

  const handleSaveToProject = useCallback(async (imgIndex) => {
    if (!currentJobId) {
      toast.error('Nenhum job disponível');
      return;
    }
    if (!projectId) {
      toast.error('Nenhum projeto selecionado');
      return;
    }
    setSaving(imgIndex);
    try {
      const res = await fetch(`${API}/api/krea/jobs/${currentJobId}/save`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ projectId, urlIndex: imgIndex }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Erro ${res.status} ao salvar imagem`);
      }
      const data = await res.json();
      toast.success('Imagem Krea salva no projeto!');
      if (onImageSaved) onImageSaved(data.url, data.filename);
    } catch (e) {
      toast.error(e.message || 'Falha ao salvar imagem.');
    } finally {
      setSaving(null);
    }
  }, [currentJobId, projectId, onImageSaved]);

  if (!configured) {
    return (
      <Card className="bg-slate-900/80 border-slate-700" data-testid="krea-panel-not-configured">
        <CardContent className="p-6 text-center space-y-3">
          <div className="flex items-center justify-center gap-2">
            <Wand2 className="w-5 h-5 text-pink-400" />
            <h3 className="text-sm font-semibold text-white">Krea AI</h3>
          </div>
          <p className="text-xs text-slate-400">
            A chave <code className="text-amber-400">KREA_API_KEY</code> não está configurada.
            <br />Peça ao administrador para configurar em <strong>Admin → Integrações</strong>.
          </p>
          {onClose && <Button variant="outline" size="sm" onClick={onClose}>Fechar</Button>}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-slate-900/80 border-slate-700" data-testid="krea-panel">
      <CardContent className="p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Wand2 className="w-5 h-5 text-pink-400" />
            <h3 className="text-sm font-semibold text-white">Krea AI</h3>
            <Badge className="bg-pink-600/20 text-pink-300 text-[10px]">
              {models.length} modelos
            </Badge>
          </div>
          {onClose && (
            <Button variant="ghost" size="sm" onClick={onClose} className="h-7 w-7 p-0">
              <X className="w-4 h-4" />
            </Button>
          )}
        </div>

        {/* Model dropdown */}
        <div className="space-y-1.5">
          <label className="text-[11px] text-slate-400 font-medium">Modelo de imagem</label>
          <select
            value={modelId || ''}
            onChange={(e) => setModelId(e.target.value)}
            disabled={generating || !models.length}
            className="w-full bg-slate-800 border border-slate-700 rounded-md px-2 py-1.5 text-xs text-white focus:outline-none focus:border-pink-500"
            data-testid="krea-model-select"
          >
            {models.map(m => (
              <option key={m.id} value={m.id}>
                {m.label} {m.tier === 'premium' ? '⭐' : '⚡'} · ~${m.approxCostUSD} · {m.approxTimeSeconds}s
              </option>
            ))}
          </select>
          {selectedModel && (
            <div className="flex items-start gap-1.5 text-[10px] text-slate-500">
              <Info className="w-3 h-3 shrink-0 mt-0.5" />
              <span>{selectedModel.description}</span>
            </div>
          )}
        </div>

        {/* Prompt */}
        <Textarea
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          placeholder="Descreva a imagem... Ex: 'Sala de treinamento corporativo moderna, tela digital, iluminação cinematográfica'"
          className="bg-slate-800 border-slate-700 text-white text-sm min-h-[80px] resize-none"
          disabled={generating}
          data-testid="krea-prompt-input"
        />

        {/* Dimensions */}
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <label className="text-[11px] text-slate-400 font-medium">Largura</label>
            <Input
              type="number"
              min={256}
              max={selectedModel?.maxWidth || 1920}
              step={64}
              value={width}
              onChange={e => setWidth(parseInt(e.target.value || '1024', 10))}
              className="bg-slate-800 border-slate-700 text-white text-xs h-8"
              disabled={generating}
              data-testid="krea-width-input"
            />
          </div>
          <div className="space-y-1">
            <label className="text-[11px] text-slate-400 font-medium">Altura</label>
            <Input
              type="number"
              min={256}
              max={selectedModel?.maxHeight || 1920}
              step={64}
              value={height}
              onChange={e => setHeight(parseInt(e.target.value || '576', 10))}
              className="bg-slate-800 border-slate-700 text-white text-xs h-8"
              disabled={generating}
              data-testid="krea-height-input"
            />
          </div>
        </div>

        {/* Quick aspect-ratio presets */}
        <div className="flex flex-wrap gap-1.5">
          {[
            { label: '16:9 (1024×576)', w: 1024, h: 576 },
            { label: '4:3 (1024×768)', w: 1024, h: 768 },
            { label: '1:1 (1024×1024)', w: 1024, h: 1024 },
            { label: '9:16 (576×1024)', w: 576, h: 1024 },
          ].map(p => (
            <button
              key={p.label}
              disabled={generating}
              onClick={() => { setWidth(p.w); setHeight(p.h); }}
              className={`px-2 py-0.5 rounded text-[10px] transition ${
                width === p.w && height === p.h
                  ? 'bg-pink-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
              data-testid={`krea-preset-${p.w}x${p.h}`}
            >
              {p.label}
            </button>
          ))}
        </div>

        <Button
          onClick={handleGenerate}
          disabled={generating || !prompt.trim() || !modelId}
          className="w-full bg-gradient-to-r from-pink-600 to-violet-600 hover:from-pink-700 hover:to-violet-700"
          data-testid="krea-generate-btn"
        >
          {generating ? (
            <><Loader2 className="w-4 h-4 animate-spin mr-2" /> {jobStatus === 'processing' ? 'Renderizando...' : 'Na fila...'}</>
          ) : (
            <><Sparkles className="w-4 h-4 mr-2" /> Gerar com Krea AI</>
          )}
        </Button>

        {generating && (
          <div className="text-[11px] text-slate-400 text-center" data-testid="krea-job-status">
            Status: <span className="text-pink-400 font-mono">{jobStatus}</span>
            {currentJobId && <span className="ml-2 text-slate-600">job {currentJobId.slice(0, 8)}…</span>}
          </div>
        )}

        {error && (
          <p className="text-xs text-red-400 border border-red-500/30 bg-red-500/10 rounded p-2" data-testid="krea-error">
            {error}
          </p>
        )}

        {images.length > 0 && (
          <div className="grid grid-cols-2 gap-2" data-testid="krea-results">
            {images.map((url, i) => (
              <div
                key={i}
                className="relative group rounded-lg overflow-hidden border border-slate-700 bg-slate-950"
              >
                {/* Krea-generated image preview */}
                <img
                  src={url}
                  alt={`Imagem gerada ${i + 1}`}
                  className="w-full h-36 object-cover"
                  data-testid={`krea-result-img-${i}`}
                />
                <div className="absolute inset-0 bg-black/70 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                  <Button
                    size="sm"
                    onClick={() => handleSaveToProject(i)}
                    disabled={saving !== null}
                    className="bg-emerald-600 hover:bg-emerald-700 h-8 text-xs"
                    data-testid={`krea-save-${i}`}
                  >
                    {saving === i ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3 mr-1" />}
                    Usar no Curso
                  </Button>
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-2.5 py-1 rounded bg-slate-700 hover:bg-slate-600 text-white text-xs flex items-center gap-1"
                    data-testid={`krea-preview-${i}`}
                  >
                    <Download className="w-3 h-3" /> Abrir
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
