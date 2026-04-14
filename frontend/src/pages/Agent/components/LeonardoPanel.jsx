import React, { useState } from 'react';
import { Button } from '../../../components/ui/button';
import { Card, CardContent } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { Textarea } from '../../../components/ui/textarea';
import { ImagePlus, Loader2, Download, Check, Sparkles, X, Wand2 } from 'lucide-react';
import { toast } from 'sonner';
import { authHeaders } from '../../../contexts/AuthContext';

const API = process.env.REACT_APP_BACKEND_URL;

const STYLE_PRESETS = [
  { id: null, label: 'Automatico' },
  { id: 'CINEMATIC', label: 'Cinematico' },
  { id: 'ILLUSTRATION', label: 'Ilustracao' },
  { id: 'PHOTOGRAPHY', label: 'Fotografia' },
  { id: 'DIGITAL_ART', label: 'Arte Digital' },
  { id: 'RENDER_3D', label: '3D' },
];

export default function LeonardoPanel({ projectId, onImageSaved, onClose }) {
  const [prompt, setPrompt] = useState('');
  const [style, setStyle] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(null);
  const [images, setImages] = useState([]);
  const [error, setError] = useState('');

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    setGenerating(true);
    setImages([]);
    setError('');

    try {
      // Start generation
      const res = await fetch(`${API}/api/leonardo/generate`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          prompt: prompt.trim(),
          width: 1024,
          height: 576,
          numImages: 4,
          style,
          projectId,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Erro ao gerar');
      }
      const { generationId } = await res.json();

      // Poll for results
      let attempts = 0;
      while (attempts < 30) {
        await new Promise(r => setTimeout(r, 4000));
        attempts++;
        const pollRes = await fetch(`${API}/api/leonardo/status/${generationId}`, { headers: authHeaders() });
        if (!pollRes.ok) continue;
        const pollData = await pollRes.json();

        if (pollData.status === 'complete') {
          setImages(pollData.images || []);
          toast.success(`${pollData.images?.length || 0} imagens geradas!`);
          break;
        }
        if (pollData.status === 'failed') {
          throw new Error('Geracao falhou no Leonardo AI');
        }
      }
      if (images.length === 0 && attempts >= 30) {
        throw new Error('Timeout aguardando geracao');
      }
    } catch (e) {
      setError(e.message);
      toast.error(e.message);
    }
    setGenerating(false);
  };

  const handleSaveToProject = async (imageUrl, index) => {
    if (!projectId) {
      toast.error('Nenhum projeto selecionado');
      return;
    }
    setSaving(index);
    try {
      const res = await fetch(`${API}/api/leonardo/save-to-project`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ imageUrl, projectId, prompt: prompt.trim() }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      toast.success('Imagem salva no projeto!');
      if (onImageSaved) onImageSaved(data.url, data.filename);
    } catch {
      toast.error('Erro ao salvar imagem');
    }
    setSaving(null);
  };

  return (
    <Card className="bg-slate-900/80 border-slate-700" data-testid="leonardo-panel">
      <CardContent className="p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Wand2 className="w-5 h-5 text-violet-400" />
            <h3 className="text-sm font-semibold text-white">Leonardo AI</h3>
            <Badge className="bg-violet-600/20 text-violet-300 text-[10px]">Geracao de Imagens</Badge>
          </div>
          {onClose && (
            <Button variant="ghost" size="sm" onClick={onClose} className="h-7 w-7 p-0">
              <X className="w-4 h-4" />
            </Button>
          )}
        </div>

        <Textarea
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          placeholder="Descreva a imagem que deseja gerar... Ex: Sala de treinamento corporativo moderna com tela digital, estilo cinematografico"
          className="bg-slate-800 border-slate-700 text-white text-sm min-h-[80px] resize-none"
          data-testid="leonardo-prompt-input"
        />

        {/* Style presets */}
        <div className="flex flex-wrap gap-1.5">
          {STYLE_PRESETS.map(s => (
            <button
              key={s.id || 'auto'}
              onClick={() => setStyle(s.id)}
              className={`px-2.5 py-1 rounded-md text-[11px] transition-all ${
                style === s.id
                  ? 'bg-violet-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
              data-testid={`leonardo-style-${s.id || 'auto'}`}
            >
              {s.label}
            </button>
          ))}
        </div>

        <Button
          onClick={handleGenerate}
          disabled={generating || !prompt.trim()}
          className="w-full bg-violet-600 hover:bg-violet-700"
          data-testid="leonardo-generate-btn"
        >
          {generating ? (
            <><Loader2 className="w-4 h-4 animate-spin mr-2" /> Gerando imagens...</>
          ) : (
            <><Sparkles className="w-4 h-4 mr-2" /> Gerar com Leonardo AI</>
          )}
        </Button>

        {error && (
          <p className="text-xs text-red-400" data-testid="leonardo-error">{error}</p>
        )}

        {/* Generated images grid */}
        {images.length > 0 && (
          <div className="grid grid-cols-2 gap-2" data-testid="leonardo-results">
            {images.map((url, i) => (
              <div key={i} className="relative group rounded-lg overflow-hidden border border-slate-700">
                <img src={url} alt={`Gerada ${i + 1}`} className="w-full h-32 object-cover" />
                <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                  <Button
                    size="sm"
                    onClick={() => handleSaveToProject(url, i)}
                    disabled={saving !== null}
                    className="bg-emerald-600 hover:bg-emerald-700 h-8 text-xs"
                    data-testid={`leonardo-save-${i}`}
                  >
                    {saving === i ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3 mr-1" />}
                    Usar no Curso
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
