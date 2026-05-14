import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { getApiUrl } from '../../../utils/apiUrl';
import { authHeaders } from '../../../contexts/AuthContext';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Textarea } from '../../../components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { ScrollArea } from '../../../components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../components/ui/select';
import { AnimPreviewButton } from '../../../components/AnimPreviewButton';
import { Slider } from '../../../components/ui/slider';
import { Checkbox } from '../../../components/ui/checkbox';
import { toast } from 'sonner';
import {
  Brain, Upload, FileText, Settings, BookOpen, Layers, Play,
  Send, ArrowLeft, ArrowRight, Check, Loader2, Sparkles,
  GraduationCap, Clock, BarChart3, Lightbulb, ChevronRight,
  X, MessageSquare, PanelRightOpen, PanelRightClose,
  Pencil, Plus, Shield, Wrench, Heart, HardHat, TrendingUp, Users,
  AlertTriangle, Star, Zap, Image, Video, UserCircle, Eye,
  Palette, Droplets, ImagePlus, UploadCloud,
  ChevronDown, ChevronUp, RefreshCw, Monitor, Rocket, BookMarked,
  PaintBucket, Target, Code, ExternalLink, BookOpenCheck, Volume2, Type,
} from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../../components/ui/tabs';
import BrandLibraryPicker from '../../Editor/dialogs/BrandLibraryPicker';

const API = getApiUrl();

const GRADIENT_DIRECTIONS = [
  { id: 'to right', label: '\u2192' },
  { id: 'to left', label: '\u2190' },
  { id: 'to bottom', label: '\u2193' },
  { id: 'to top', label: '\u2191' },
  { id: 'to bottom right', label: '\u2198' },
  { id: 'to bottom left', label: '\u2199' },
  { id: 'to top right', label: '\u2197' },
  { id: 'to top left', label: '\u2196' },
];

function SlideBackgroundPicker({ slideIndex, bgConfig, setBgConfig, allSlides, isGlobal }) {
  const bg = bgConfig[String(slideIndex)] || { type: 'default' };

  const updateBg = (patch) => {
    setBgConfig(prev => ({ ...prev, [String(slideIndex)]: { ...bg, ...patch } }));
  };

  const applyToAll = () => {
    const newCfg = {};
    allSlides.forEach((_, i) => { newCfg[String(i)] = { ...bg }; });
    setBgConfig(newCfg);
    toast.success('Fundo aplicado a todos os slides');
  };

  const applyToType = (slideType) => {
    const newCfg = { ...bgConfig };
    allSlides.forEach((s, i) => { if (s.type === slideType) newCfg[String(i)] = { ...bg }; });
    setBgConfig(newCfg);
    toast.success(`Fundo aplicado aos slides "${slideType}"`);
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { toast.error('Imagem deve ter no máximo 5MB'); return; }
    const reader = new FileReader();
    reader.onload = (ev) => {
      updateBg({ type: 'image', imageData: ev.target.result, opacity: bg.opacity ?? 30 });
    };
    reader.readAsDataURL(file);
  };

  const [aiPrompt, setAiPrompt] = useState('');
  const [aiLoading, setAiLoading] = useState(false);

  const generateAiBg = async () => {
    if (!aiPrompt.trim()) return;
    setAiLoading(true);
    try {
      const res = await fetch(`${API}/api/agent/generate-bg-image`, {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ prompt: aiPrompt }),
      });
      const data = await res.json();
      if (data.imageUrl) {
        updateBg({ type: 'image', imageUrl: data.imageUrl, opacity: bg.opacity ?? 30, aiPrompt });
        toast.success('Imagem de fundo gerada!');
      } else { toast.error('Erro ao gerar imagem'); }
    } catch { toast.error('Erro ao gerar imagem'); }
    finally { setAiLoading(false); }
  };

  const previewStyle = bg.type === 'solid'
    ? { background: bg.color || '#1e293b' }
    : bg.type === 'gradient'
    ? { background: `linear-gradient(${bg.direction || 'to right'}, ${bg.color1 || '#1e293b'}, ${bg.color2 || '#10b981'})` }
    : bg.type === 'image'
    ? { backgroundImage: `url(${bg.imageData || bg.imageUrl || ''})`, backgroundSize: 'cover', backgroundPosition: 'center' }
    : { background: '#1e293b' };

  return (
    <div className="space-y-2" data-testid={`bg-picker-slide-${slideIndex}`}>
      <div className="flex items-center gap-2">
        <Palette className="w-3.5 h-3.5 text-cyan-400" />
        <span className="text-xs font-medium text-cyan-300">Fundo</span>
        {/* Mini preview */}
        <div className="w-8 h-5 rounded border border-slate-600 shrink-0" style={previewStyle} />
        {!isGlobal && (
          <div className="ml-auto flex gap-1">
            <button onClick={applyToAll} className="text-[10px] text-cyan-400/70 hover:text-cyan-300 px-1" title="Aplicar a todos">
              Todos
            </button>
            <button onClick={() => applyToType(allSlides[slideIndex]?.type || 'content')} className="text-[10px] text-cyan-400/70 hover:text-cyan-300 px-1" title="Aplicar ao mesmo tipo">
              Tipo
            </button>
          </div>
        )}
      </div>

      <Tabs value={bg.type || 'default'} onValueChange={(v) => updateBg({ type: v })} className="w-full">
        <TabsList className="w-full h-7 bg-slate-800/80 p-0.5">
          <TabsTrigger value="default" className="text-[10px] h-6 px-2 data-[state=active]:bg-slate-700">Padrão</TabsTrigger>
          <TabsTrigger value="solid" className="text-[10px] h-6 px-2 data-[state=active]:bg-slate-700">Cor</TabsTrigger>
          <TabsTrigger value="gradient" className="text-[10px] h-6 px-2 data-[state=active]:bg-slate-700">Degradê</TabsTrigger>
          <TabsTrigger value="image" className="text-[10px] h-6 px-2 data-[state=active]:bg-slate-700">Imagem</TabsTrigger>
        </TabsList>

        <TabsContent value="default" className="mt-1">
          <p className="text-[10px] text-slate-500">Usa a cor do template selecionado.</p>
        </TabsContent>

        <TabsContent value="solid" className="mt-1">
          <div className="flex items-center gap-2">
            <input
              type="color"
              value={bg.color || '#1e293b'}
              onChange={(e) => updateBg({ color: e.target.value })}
              className="w-8 h-8 rounded cursor-pointer border-0 bg-transparent"
              data-testid={`bg-color-picker-${slideIndex}`}
            />
            <Input
              value={bg.color || '#1e293b'}
              onChange={(e) => updateBg({ color: e.target.value })}
              className="h-7 text-xs bg-slate-800 border-slate-700 w-24"
              placeholder="#1e293b"
            />
          </div>
        </TabsContent>

        <TabsContent value="gradient" className="mt-1">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={bg.color1 || '#1e293b'}
                onChange={(e) => updateBg({ color1: e.target.value })}
                className="w-7 h-7 rounded cursor-pointer border-0 bg-transparent"
                data-testid={`bg-gradient-color1-${slideIndex}`}
              />
              <input
                type="color"
                value={bg.color2 || '#10b981'}
                onChange={(e) => updateBg({ color2: e.target.value })}
                className="w-7 h-7 rounded cursor-pointer border-0 bg-transparent"
                data-testid={`bg-gradient-color2-${slideIndex}`}
              />
              <div className="flex gap-0.5 ml-1">
                {GRADIENT_DIRECTIONS.map(d => (
                  <button
                    key={d.id}
                    onClick={() => updateBg({ direction: d.id })}
                    className={`w-6 h-6 rounded text-[10px] transition-colors ${
                      (bg.direction || 'to right') === d.id
                        ? 'bg-cyan-600/30 text-cyan-300 border border-cyan-500/50'
                        : 'bg-slate-800 text-slate-500 hover:text-slate-300 border border-slate-700'
                    }`}
                    title={d.id}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </div>
            {/* Gradient preview */}
            <div
              className="h-6 rounded border border-slate-700"
              style={{ background: `linear-gradient(${bg.direction || 'to right'}, ${bg.color1 || '#1e293b'}, ${bg.color2 || '#10b981'})` }}
            />
          </div>
        </TabsContent>

        <TabsContent value="image" className="mt-1">
          <div className="space-y-2">
            <div className="flex gap-2">
              <label className="flex-1">
                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-dashed border-slate-600 text-xs text-slate-400 hover:border-cyan-500/50 hover:text-cyan-300 cursor-pointer transition-colors" data-testid={`bg-upload-btn-${slideIndex}`}>
                  <UploadCloud className="w-3.5 h-3.5" /> Upload
                </div>
                <input type="file" accept="image/*" onChange={handleImageUpload} className="hidden" />
              </label>
              <div className="flex-1 flex gap-1">
                <Input
                  value={aiPrompt}
                  onChange={(e) => setAiPrompt(e.target.value)}
                  placeholder="Descreva o fundo..."
                  className="h-8 text-xs bg-slate-800 border-slate-700 flex-1"
                  data-testid={`bg-ai-prompt-${slideIndex}`}
                  onKeyDown={(e) => e.key === 'Enter' && generateAiBg()}
                />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={generateAiBg}
                  disabled={aiLoading || !aiPrompt.trim()}
                  className="h-8 px-2 text-xs border-cyan-700/50 text-cyan-300"
                  data-testid={`bg-ai-generate-${slideIndex}`}
                >
                  {aiLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                </Button>
              </div>
            </div>
            {(bg.imageData || bg.imageUrl) && (
              <div className="space-y-1.5">
                <div className="relative h-16 rounded border border-slate-700 overflow-hidden">
                  <img src={bg.imageData || bg.imageUrl} alt="bg" className="w-full h-full object-cover" style={{ opacity: (bg.opacity ?? 30) / 100 }} />
                  <div className="absolute inset-0 bg-slate-900" style={{ opacity: 1 - (bg.opacity ?? 30) / 100 }} />
                </div>
                <div className="flex items-center gap-2">
                  <Droplets className="w-3 h-3 text-slate-400" />
                  <span className="text-[10px] text-slate-400 w-14">Opacidade</span>
                  <Slider
                    value={[bg.opacity ?? 30]}
                    onValueChange={([v]) => updateBg({ opacity: v })}
                    min={5} max={100} step={5}
                    className="flex-1"
                    data-testid={`bg-opacity-slider-${slideIndex}`}
                  />
                  <span className="text-[10px] text-slate-400 w-8 text-right">{bg.opacity ?? 30}%</span>
                </div>
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

const MEDIA_TYPES = [
  { id: 'ai_image', label: 'Imagem IA', description: 'Fotorealista gerada por IA', icon: Image, color: 'emerald' },
  { id: 'gallery_image', label: 'Da Galeria', description: 'Reutilizar imagem existente', icon: ImagePlus, color: 'amber' },
  { id: 'brand_library_image', label: 'Biblioteca da Marca', description: 'Imagem curada da empresa', icon: Layers, color: 'indigo' },
  { id: 'leonardo', label: 'Leonardo AI', description: 'Imagem premium com Leonardo', icon: Sparkles, color: 'violet' },
  { id: 'youtube', label: 'YouTube', description: 'Vídeo do YouTube', icon: Video, color: 'red' },
  { id: 'vimeo', label: 'Vimeo', description: 'Vídeo do Vimeo', icon: Video, color: 'blue' },
  { id: 'heygen', label: 'Avatar HeyGen', description: 'Vídeo com avatar IA', icon: UserCircle, color: 'purple' },
  { id: 'flipbook', label: 'Flipbook', description: 'PDF/URL interativo', icon: BookOpenCheck, color: 'orange' },
  { id: 'html', label: 'HTML', description: 'Código HTML ou URL', icon: Code, color: 'cyan' },
  { id: 'button', label: 'Botão Link', description: 'Botão com link externo', icon: ExternalLink, color: 'teal' },
  { id: 'none', label: 'Sem mídia', description: 'Apenas texto', icon: FileText, color: 'slate' },
];

const NARRATION_STYLES = [
  { id: 'educational', label: 'Educativo' },
  { id: 'conversational', label: 'Conversacional' },
  { id: 'formal', label: 'Formal' },
  { id: 'friendly', label: 'Amigável' },
];


function CostEstimateCard({ sessionId, aiCount, leonardoCount, videoCount, heygenCount, bgConfig, isEditMode, changedSlideCount }) {
  const [estimate, setEstimate] = useState(null);
  const [loadingEstimate, setLoadingEstimate] = useState(false);

  const fetchEstimate = useCallback(async () => {
    if (!sessionId) return;
    setLoadingEstimate(true);
    try {
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/cost-estimate`, { method: 'POST', headers: authHeaders() });
      const data = await res.json();
      setEstimate(data.estimate);
    } catch { /* ignore */ }
    finally { setLoadingEstimate(false); }
  }, [sessionId]);

  useEffect(() => { fetchEstimate(); }, [fetchEstimate]);

  const customBgCount = Object.values(bgConfig || {}).filter(b => b.type && b.type !== 'default').length;

  // In edit mode, scale costs by ratio of changed slides to total
  const getEditScaledEstimate = () => {
    if (!estimate || !isEditMode || changedSlideCount == null) return estimate;
    const total = estimate.totalSlides || 1;
    const ratio = Math.min(changedSlideCount / total, 1);
    return {
      ...estimate,
      totalSlides: changedSlideCount,
      aiImages: Math.round(estimate.aiImages * ratio),
      leonardoImages: Math.round((estimate.leonardoImages || 0) * ratio),
      costs: {
        text: Math.round(estimate.costs.text * ratio * 1000) / 1000,
        images: Math.round(estimate.costs.images * ratio * 1000) / 1000,
        leonardo: Math.round((estimate.costs.leonardo || 0) * ratio * 1000) / 1000,
        narration: Math.round(estimate.costs.narration * ratio * 1000) / 1000,
        total: Math.round(estimate.costs.total * ratio * 1000) / 1000,
      },
      comparison: {
        ...estimate.comparison,
        oldTotal: Math.round(estimate.comparison.oldTotal * ratio * 1000) / 1000,
        newTotal: Math.round(estimate.costs.total * ratio * 1000) / 1000,
        savingsPercent: estimate.comparison.savingsPercent,
      },
    };
  };
  const displayEstimate = isEditMode ? getEditScaledEstimate() : estimate;

  return (
    <Card className="bg-slate-900/50 border-emerald-800/30" data-testid="cost-estimate-card">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-semibold text-emerald-300 flex items-center gap-1.5">
            <BarChart3 className="w-3.5 h-3.5" /> Resumo & Estimativa de Custo
          </h4>
          <button onClick={fetchEstimate} className="text-[10px] text-slate-500 hover:text-slate-300" disabled={loadingEstimate}>
            {loadingEstimate ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
          </button>
        </div>

        {isEditMode && changedSlideCount != null && (
          <div className="flex items-center gap-1.5 text-xs">
            <Badge className="bg-blue-600/20 text-blue-300">
              {changedSlideCount} slide(s) modificado(s) de {estimate?.totalSlides || '?'}
            </Badge>
          </div>
        )}

        {/* Media summary badges */}
        <div className="flex flex-wrap gap-2 text-xs">
          {aiCount > 0 && <Badge className="bg-emerald-600/20 text-emerald-300"><Image className="w-3 h-3 mr-1" />{aiCount} Imagens IA</Badge>}
          {leonardoCount > 0 && <Badge className="bg-fuchsia-600/20 text-fuchsia-300"><Sparkles className="w-3 h-3 mr-1" />{leonardoCount} Leonardo AI</Badge>}
          {videoCount > 0 && <Badge className="bg-red-600/20 text-red-300"><Video className="w-3 h-3 mr-1" />{videoCount} Videos</Badge>}
          {heygenCount > 0 && <Badge className="bg-purple-600/20 text-purple-300"><UserCircle className="w-3 h-3 mr-1" />{heygenCount} Avatares</Badge>}
          {customBgCount > 0 && <Badge className="bg-cyan-600/20 text-cyan-300"><Palette className="w-3 h-3 mr-1" />{customBgCount} Fundos</Badge>}
        </div>

        {displayEstimate && (
          <div className="space-y-2">
            {/* Cost breakdown */}
            <div className={`grid gap-2 text-center ${(displayEstimate.leonardoImages || 0) > 0 ? 'grid-cols-4' : 'grid-cols-3'}`}>
              <div className="bg-slate-800/60 rounded-lg p-2">
                <p className="text-[10px] text-slate-400">Texto (IA)</p>
                <p className="text-sm font-bold text-slate-200">${displayEstimate.costs.text.toFixed(3)}</p>
                <p className="text-[9px] text-cyan-400/60">{displayEstimate.models.text}</p>
              </div>
              <div className="bg-slate-800/60 rounded-lg p-2">
                <p className="text-[10px] text-slate-400">Imagens ({displayEstimate.aiImages})</p>
                <p className="text-sm font-bold text-slate-200">${displayEstimate.costs.images.toFixed(3)}</p>
                <p className="text-[9px] text-cyan-400/60">{displayEstimate.models.images}</p>
              </div>
              {(displayEstimate.leonardoImages || 0) > 0 && (
                <div className="bg-fuchsia-900/20 border border-fuchsia-800/30 rounded-lg p-2">
                  <p className="text-[10px] text-fuchsia-300">Leonardo ({displayEstimate.leonardoImages})</p>
                  <p className="text-sm font-bold text-fuchsia-200">${(displayEstimate.costs.leonardo || 0).toFixed(3)}</p>
                  <p className="text-[9px] text-fuchsia-400/60">{displayEstimate.models.leonardo}</p>
                </div>
              )}
              <div className="bg-slate-800/60 rounded-lg p-2">
                <p className="text-[10px] text-slate-400">Narracao</p>
                <p className="text-sm font-bold text-slate-200">${displayEstimate.costs.narration.toFixed(3)}</p>
                <p className="text-[9px] text-cyan-400/60">{displayEstimate.models.narration}</p>
              </div>
            </div>

            {/* Total and savings */}
            <div className="flex items-center justify-between bg-emerald-900/20 border border-emerald-800/30 rounded-lg px-3 py-2">
              <div>
                <p className="text-xs text-slate-400">{isEditMode ? 'Custo dos slides modificados' : 'Custo estimado total'}</p>
                <p className="text-lg font-bold text-emerald-300">${displayEstimate.costs.total.toFixed(3)}</p>
              </div>
              {displayEstimate.comparison.savingsPercent > 0 && (
                <div className="text-right">
                  <Badge className="bg-emerald-600/30 text-emerald-300 text-xs">
                    <TrendingUp className="w-3 h-3 mr-1" />
                    {displayEstimate.comparison.savingsPercent}% economia
                  </Badge>
                  <p className="text-[10px] text-slate-500 mt-0.5 line-through">${displayEstimate.comparison.oldTotal.toFixed(3)} (GPT-5.2)</p>
                </div>
              )}
            </div>

            <p className="text-[10px] text-slate-500 text-center">
              {displayEstimate.totalSlides} slides | {displayEstimate.storyboardBatches || Math.ceil(displayEstimate.totalSlides / 4)} batches | Gemini 3 Flash + Nano Banana{(displayEstimate.leonardoImages || 0) > 0 ? ' + Leonardo AI' : ''}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}


function ImageGalleryModal({ onClose, onSelect }) {
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    setLoading(true);
    fetch(`${API}/api/gallery/images`, { headers: authHeaders() })
      .then(r => r.json())
      .then(data => setImages(data.images || []))
      .catch(() => toast.error('Erro ao carregar galeria'))
      .finally(() => setLoading(false));
  }, []);

  const filtered = search
    ? images.filter(img =>
        (img.keywords || '').toLowerCase().includes(search.toLowerCase()) ||
        (img.projectName || '').toLowerCase().includes(search.toLowerCase())
      )
    : images;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" data-testid="gallery-modal">
      <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl">
        <div className="flex items-center justify-between p-4 border-b border-slate-800">
          <h3 className="text-base font-semibold flex items-center gap-2">
            <ImagePlus className="w-5 h-5 text-amber-400" />
            Galeria de Imagens
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-4 border-b border-slate-800">
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Buscar por palavras-chave ou projeto..."
            className="bg-slate-800 border-slate-700"
            data-testid="gallery-search"
          />
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-slate-400" /></div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              <ImagePlus className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">{images.length === 0 ? 'Nenhuma imagem na galeria ainda.' : 'Nenhuma imagem encontrada.'}</p>
              <p className="text-xs mt-1 text-slate-500">{images.length === 0 ? 'As imagens geradas por IA serão salvas aqui automaticamente.' : 'Tente outra busca.'}</p>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-3">
              {filtered.map(img => (
                <button
                  key={img.id}
                  onClick={() => onSelect(img)}
                  className="group relative rounded-lg overflow-hidden border border-slate-700 hover:border-amber-500 transition-all aspect-[4/3]"
                  data-testid={`gallery-image-${img.id}`}
                >
                  <img
                    src={img.imageUrl.startsWith('/') ? `${API}${img.imageUrl}` : img.imageUrl}
                    alt={img.keywords || ''}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-2">
                    <p className="text-[10px] text-white/90 truncate">{img.keywords || 'Sem palavras-chave'}</p>
                    <p className="text-[9px] text-white/50 truncate">{img.projectName || ''}</p>
                  </div>
                  <div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <div className="bg-amber-500 text-black rounded-full p-1"><Check className="w-3 h-3" /></div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="p-3 border-t border-slate-800 text-center">
          <p className="text-[10px] text-slate-500">{filtered.length} de {images.length} imagens</p>
        </div>
      </div>
    </div>
  );
}


const PRIORITY_STYLES = {
  alta: 'bg-red-600/15 text-red-300 border-red-500/40',
  media: 'bg-amber-600/15 text-amber-300 border-amber-500/40',
  baixa: 'bg-slate-700/30 text-slate-300 border-slate-600/40',
};


function SuggestionsCategory({ icon: Icon, title, color, items }) {
  if (!items || items.length === 0) return null;
  const colorMap = {
    blue: 'text-blue-400 border-blue-800/40',
    purple: 'text-purple-400 border-purple-800/40',
    amber: 'text-amber-400 border-amber-800/40',
    emerald: 'text-emerald-400 border-emerald-800/40',
    pink: 'text-pink-400 border-pink-800/40',
    orange: 'text-orange-400 border-orange-800/40',
  };
  const colors = colorMap[color] || colorMap.blue;

  return (
    <div className={`border rounded-lg p-3 space-y-2 ${colors.split(' ').slice(1).join(' ')}`} data-testid={`suggestions-category-${color}`}>
      <div className="flex items-center gap-2">
        <Icon className={`w-3.5 h-3.5 ${colors.split(' ')[0]}`} />
        <span className={`text-xs font-semibold ${colors.split(' ')[0]}`}>{title}</span>
        <Badge variant="outline" className="text-[9px] ml-auto border-slate-700 text-slate-400">{items.length}</Badge>
      </div>
      {items.map((item, idx) => (
        <div key={idx} className="pl-5 space-y-0.5" data-testid={`suggestion-item-${color}-${idx}`}>
          <div className="flex items-start gap-2">
            <span className="text-xs font-medium text-slate-200">{item.title}</span>
            <Badge variant="outline" className={`text-[8px] shrink-0 ${PRIORITY_STYLES[item.priority] || PRIORITY_STYLES.media}`}>
              {item.priority}
            </Badge>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">{item.description}</p>
          {item.impact && <p className="text-[10px] text-cyan-400/60 italic">{item.impact}</p>}
        </div>
      ))}
    </div>
  );
}


export default function MediaConfigPanel({ storyboard, mediaConfig, setMediaConfig, loading, onConfirm, heygenConfig, setHeygenConfig, bgConfig, setBgConfig, sessionId, globalTextColor, setGlobalTextColor, globalFontSize, setGlobalFontSize, globalAnimation, setGlobalAnimation, isEditMode, originalMediaConfig, originalBgConfig, projectId, selectedDesignTemplate, setSelectedDesignTemplate, useBrandLibrary, setUseBrandLibrary, brandLibraryMode, setBrandLibraryMode, brandLibraryCount, brandLibraryCompanyId }) {
  const [avatars, setAvatars] = useState([]);
  const [voices, setVoices] = useState([]);
  const [loadingAvatars, setLoadingAvatars] = useState(false);
  const [loadingVoices, setLoadingVoices] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [previewVideoId, setPreviewVideoId] = useState(null);
  const [showGallery, setShowGallery] = useState(false);
  const [gallerySlideIndex, setGallerySlideIndex] = useState(null);
  // Brand Library Picker state (per-slide manual selection — different from
  // the global toggle that lets the agent auto-pick).
  const [showBrandPicker, setShowBrandPicker] = useState(false);
  const [brandPickerSlideIdx, setBrandPickerSlideIdx] = useState(null);
  const [designTemplates, setDesignTemplates] = useState([]);

  // ElevenLabs narration state - restore voiceId from existing mediaConfig when editing
  const [elVoices, setElVoices] = useState([]);
  const [loadingElVoices, setLoadingElVoices] = useState(false);
  const [narrationVoiceId, setNarrationVoiceId] = useState(() => {
    // Extract voiceId from first narration-enabled slide in mediaConfig
    for (const val of Object.values(mediaConfig || {})) {
      if (val?.narration?.enabled && val?.narration?.voiceId) {
        return val.narration.voiceId;
      }
    }
    return '';
  });
  const [narrationStyle, setNarrationStyle] = useState('educational');
  const [generatingScripts, setGeneratingScripts] = useState({}); // { slideIndex: true }
  const [scriptOptions, setScriptOptions] = useState({}); // { slideIndex: ["opt1", "opt2", "opt3"] }
  const [previewingAudio, setPreviewingAudio] = useState(null);

  const contentSlides = (storyboard?.slides || [])
    .map((s, i) => ({ ...s, index: i }))
    .filter(s => s.type === 'content');

  const updateSlideMedia = (idx, type, url, extra = {}) => {
    setMediaConfig(prev => ({
      ...prev,
      [String(idx)]: { ...prev[String(idx)], type, ...(url ? { url } : {}), ...extra },
    }));
  };

  const setAllSlidesMedia = (type) => {
    const mc = {};
    contentSlides.forEach(s => { mc[String(s.index)] = { type }; });
    setMediaConfig(mc);
  };

  const aiCount = Object.values(mediaConfig).filter(m => m.type === 'ai_image').length;
  const leonardoCount = Object.values(mediaConfig).filter(m => m.type === 'leonardo').length;
  const videoCount = Object.values(mediaConfig).filter(m => m.type === 'youtube' || m.type === 'vimeo').length;
  const heygenCount = Object.values(mediaConfig).filter(m => m.type === 'heygen').length;
  const narrationCount = Object.values(mediaConfig).filter(m => m.narration?.enabled).length;

  // Load design templates
  useEffect(() => {
    fetch(`${API}/api/agent/design-templates`, { headers: authHeaders() })
      .then(r => r.json())
      .then(setDesignTemplates)
      .catch(() => {});
  }, []);

  // Apply design template: sets backgrounds for all slides based on template colors
  const applyDesignTemplate = (dt) => {
    if (!dt) return;
    setSelectedDesignTemplate(dt);
    const p = dt.palette;
    const slides = storyboard?.slides || [];
    const newBg = {};
    slides.forEach((s, i) => {
      const slideType = s.type || 'content';
      if (slideType === 'title' || slideType === 'cover' || slideType === 'quiz' || slideType === 'summary') {
        newBg[String(i)] = { type: 'solid', color: p.primary };
      } else {
        newBg[String(i)] = { type: 'solid', color: p.contentBg };
      }
    });
    setBgConfig(newBg);
    toast.success(`Tema "${dt.name}" aplicado a ${slides.length} slides!`);
  };

  // Fetch HeyGen avatars/voices when needed
  useEffect(() => {
    if (heygenCount > 0 && avatars.length === 0 && !loadingAvatars) {
      setLoadingAvatars(true);
      fetch(`${API}/api/heygen/avatars?limit=50`, { headers: authHeaders() })
        .then(r => r.json())
        .then(data => setAvatars(data.avatars || []))
        .catch(() => toast.error('Erro ao carregar avatares'))
        .finally(() => setLoadingAvatars(false));
    }
    if (heygenCount > 0 && voices.length === 0 && !loadingVoices) {
      setLoadingVoices(true);
      fetch(`${API}/api/heygen/voices?language=portuguese`, { headers: authHeaders() })
        .then(r => r.json())
        .then(data => setVoices(data.voices || []))
        .catch(() => toast.error('Erro ao carregar vozes'))
        .finally(() => setLoadingVoices(false));
    }
  }, [heygenCount]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch ElevenLabs voices when narration is active
  useEffect(() => {
    if (narrationCount > 0 && elVoices.length === 0 && !loadingElVoices) {
      setLoadingElVoices(true);
      fetch(`${API}/api/elevenlabs/voices`, { headers: authHeaders() })
        .then(r => r.json())
        .then(data => setElVoices(data.voices || []))
        .catch(() => toast.error('Erro ao carregar vozes ElevenLabs'))
        .finally(() => setLoadingElVoices(false));
    }
  }, [narrationCount]); // eslint-disable-line react-hooks/exhaustive-deps

  const heygenReady = heygenCount === 0 || (heygenConfig.avatarId && heygenConfig.voiceId);
  const narrationReady = narrationCount === 0 || narrationVoiceId;

  // Compute changed slides count in edit mode
  const changedSlideCount = useMemo(() => {
    if (!isEditMode || !originalMediaConfig) return null;
    const allKeys = new Set([
      ...Object.keys(mediaConfig), ...Object.keys(originalMediaConfig || {}),
      ...Object.keys(bgConfig), ...Object.keys(originalBgConfig || {}),
    ]);
    let count = 0;
    for (const key of allKeys) {
      const mcChanged = JSON.stringify(mediaConfig[key] || {}) !== JSON.stringify((originalMediaConfig || {})[key] || {});
      const bgChanged = JSON.stringify((bgConfig || {})[key] || {}) !== JSON.stringify((originalBgConfig || {})[key] || {});
      if (mcChanged || bgChanged) count++;
    }
    return count;
  }, [isEditMode, mediaConfig, bgConfig, originalMediaConfig, originalBgConfig]);

  // Toggle narration for a slide
  const toggleSlideNarration = (idx, enabled) => {
    setMediaConfig(prev => ({
      ...prev,
      [String(idx)]: {
        ...prev[String(idx)],
        narration: { ...(prev[String(idx)]?.narration || {}), enabled, voiceId: narrationVoiceId },
      },
    }));
  };

  // Generate 3 narration script options for a slide
  const generateNarrationScripts = async (idx) => {
    setGeneratingScripts(prev => ({ ...prev, [idx]: true }));
    try {
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/generate-slide-narration`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ slideIndex: idx, style: narrationStyle }),
      });
      if (!res.ok) {
        const err = await res.text();
        console.error('Narration API error:', res.status, err);
        toast.error(`Erro ${res.status}: ${err.slice(0, 100)}`);
        return;
      }
      const data = await res.json();
      if (data.options) {
        setScriptOptions(prev => ({ ...prev, [idx]: data.options }));
      } else {
        toast.error('Erro ao gerar roteiros: resposta sem opções');
      }
    } catch (e) {
      console.error('Narration fetch error:', e);
      toast.error(`Erro de rede ao gerar roteiros: ${e.message}`);
    } finally {
      setGeneratingScripts(prev => ({ ...prev, [idx]: false }));
    }
  };

  // Select a narration script for a slide
  const selectNarrationScript = (idx, script) => {
    setMediaConfig(prev => ({
      ...prev,
      [String(idx)]: {
        ...prev[String(idx)],
        narration: { ...(prev[String(idx)]?.narration || {}), enabled: true, voiceId: narrationVoiceId, selectedScript: script },
      },
    }));
  };

  // Preview narration audio
  const previewNarration = async (idx, text) => {
    if (!narrationVoiceId || !text) return;
    setPreviewingAudio(idx);
    try {
      const res = await fetch(`${API}/api/elevenlabs/generate-speech`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ text: text.slice(0, 200), voice_id: narrationVoiceId }),
      });
      if (!res.ok) {
        const err = await res.text();
        console.error('ElevenLabs API error:', res.status, err);
        toast.error(`Erro ElevenLabs ${res.status}: ${err.slice(0, 100)}`);
        return;
      }
      const data = await res.json();
      if (data.audio_base64) {
        new Audio(data.audio_base64).play();
      }
    } catch (e) {
      console.error('ElevenLabs fetch error:', e);
      toast.error(`Erro de rede ao gerar áudio: ${e.message}`);
    } finally {
      setPreviewingAudio(null);
    }
  };

  // HeyGen Preview
  const handleHeygenPreview = async () => {
    if (!heygenConfig.avatarId || !heygenConfig.voiceId) return;
    setPreviewLoading(true);
    setPreviewUrl(null);
    setPreviewVideoId(null);
    try {
      // Get short text from first heygen slide
      const firstHeygenSlide = contentSlides.find((_, i) => (mediaConfig[String(_.index)] || {}).type === 'heygen');
      const previewText = firstHeygenSlide
        ? (firstHeygenSlide.elements?.find(e => e.content)?.content || 'Olá! Este é um preview do avatar.').slice(0, 200)
        : 'Olá! Este é um preview do avatar para o seu curso.';

      const res = await fetch(`${API}/api/heygen/generate`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          script: previewText,
          avatar_id: heygenConfig.avatarId,
          voice_id: heygenConfig.voiceId,
          title: 'Agent Preview',
        }),
      });
      const data = await res.json();
      if (data.video_id) {
        setPreviewVideoId(data.video_id);
        toast.success('Preview em geração... (~1-2 min)');
      } else {
        toast.error('Erro ao gerar preview');
        setPreviewLoading(false);
      }
    } catch {
      toast.error('Erro ao gerar preview');
      setPreviewLoading(false);
    }
  };

  // Poll for preview video status
  useEffect(() => {
    if (!previewVideoId) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/heygen/video/${previewVideoId}/status`, { headers: authHeaders() });
        const data = await res.json();
        if (data.status === 'completed' && data.video_url) {
          setPreviewUrl(data.video_url);
          setPreviewLoading(false);
          setPreviewVideoId(null);
          clearInterval(interval);
        } else if (data.status === 'failed') {
          toast.error('Preview falhou');
          setPreviewLoading(false);
          setPreviewVideoId(null);
          clearInterval(interval);
        }
      } catch { /* ignore */ }
    }, 8000);
    return () => clearInterval(interval);
  }, [previewVideoId]);

  if (!storyboard?.slides) return null;

  return (
    <div className="space-y-4" data-testid="media-config-panel">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Image className="w-5 h-5 text-emerald-400" /> Configurar Mídia dos Slides
        </h2>
      </div>

      <p className="text-sm text-slate-400">
        Escolha o tipo de mídia para cada slide de conteúdo. Imagens IA serão geradas automaticamente baseadas no contexto de cada slide.
      </p>

      {/* Global text color for all slides */}
      <Card className="bg-slate-900/50 border-slate-800" data-testid="global-text-color-card">
        <CardContent className="p-4 space-y-3">
          {/* Color row */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Pencil className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-medium text-cyan-300">Cor das Fontes (Todos os Slides)</span>
            </div>
            <div className="flex items-center gap-2 ml-auto">
              <input
                type="color"
                value={globalTextColor || '#ffffff'}
                onChange={e => setGlobalTextColor(e.target.value)}
                className="w-8 h-8 rounded cursor-pointer border-0 bg-transparent"
                data-testid="global-text-color-picker"
              />
              <Input
                value={globalTextColor || ''}
                onChange={e => setGlobalTextColor(e.target.value)}
                placeholder="#ffffff (padrão do template)"
                className="h-8 text-xs bg-slate-800 border-slate-700 w-44"
                data-testid="global-text-color-input"
              />
              {globalTextColor && (
                <button
                  onClick={() => setGlobalTextColor('')}
                  className="text-[10px] text-slate-500 hover:text-red-400 px-1"
                  title="Resetar para cor do template"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
          {/* Font size row */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Type className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-medium text-cyan-300">Tamanho das Fontes</span>
            </div>
            <div className="flex items-center gap-1.5 ml-auto">
              {[
                { label: 'P', value: '80', title: 'Pequeno (80%)' },
                { label: 'N', value: '', title: 'Normal (padrão)' },
                { label: 'G', value: '120', title: 'Grande (120%)' },
                { label: 'GG', value: '140', title: 'Extra Grande (140%)' },
              ].map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setGlobalFontSize(opt.value)}
                  title={opt.title}
                  className={`px-3 py-1.5 rounded text-xs font-semibold transition-all ${
                    globalFontSize === opt.value
                      ? 'bg-cyan-600 text-white'
                      : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200'
                  }`}
                  data-testid={`font-size-${opt.value || 'normal'}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          {/* Preview */}
          <div className="flex items-center gap-3">
            <span className="text-[11px] text-slate-500">Preview:</span>
            <div className="flex gap-2">
              {['#1e293b', '#0f172a', '#ffffff', '#f1f5f9'].map(bg => (
                <div
                  key={bg}
                  className="flex items-center justify-center w-24 h-8 rounded border border-slate-700 font-medium"
                  style={{ background: bg, color: globalTextColor || '#ffffff', fontSize: `${Math.round(12 * (parseInt(globalFontSize || '100') / 100))}px` }}
                >
                  Texto
                </div>
              ))}
              {Object.values(bgConfig).find(b => b.type === 'solid')?.color && (
                <div
                  className="flex items-center justify-center w-24 h-8 rounded border border-cyan-700/50 font-medium"
                  style={{ background: Object.values(bgConfig).find(b => b.type === 'solid').color, color: globalTextColor || '#ffffff', fontSize: `${Math.round(12 * (parseInt(globalFontSize || '100') / 100))}px` }}
                >
                  Seu Fundo
                </div>
              )}
            </div>
          </div>
          {!globalTextColor && !globalFontSize && <p className="text-[10px] text-slate-500 mt-1">Deixe vazio para usar o padrão do template selecionado.</p>}
        </CardContent>
      </Card>

      {/* Global Animation Picker */}
      <Card className="bg-slate-900/50 border-slate-800" data-testid="global-animation-card">
        <CardContent className="p-4 space-y-3">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-amber-400" /> Animação de Entrada dos Textos
          </h3>
          <p className="text-xs text-slate-400">Aplique uma animação de entrada em todos os textos durante a transição de slides.</p>
          <div className="grid grid-cols-3 gap-1.5">
            <AnimPreviewButton animId="" label="Nenhuma" selected={!globalAnimation} onClick={() => setGlobalAnimation('')} testId="global-anim-none" />
            <AnimPreviewButton animId="fadeIn" label="Fade In" selected={globalAnimation === 'fadeIn'} onClick={() => setGlobalAnimation('fadeIn')} testId="global-anim-fadeIn" />
            <AnimPreviewButton animId="slideInLeft" label="Slide Esq." selected={globalAnimation === 'slideInLeft'} onClick={() => setGlobalAnimation('slideInLeft')} testId="global-anim-slideInLeft" />
            <AnimPreviewButton animId="slideInRight" label="Slide Dir." selected={globalAnimation === 'slideInRight'} onClick={() => setGlobalAnimation('slideInRight')} testId="global-anim-slideInRight" />
            <AnimPreviewButton animId="slideInUp" label="Slide Baixo" selected={globalAnimation === 'slideInUp'} onClick={() => setGlobalAnimation('slideInUp')} testId="global-anim-slideInUp" />
            <AnimPreviewButton animId="slideInDown" label="Slide Cima" selected={globalAnimation === 'slideInDown'} onClick={() => setGlobalAnimation('slideInDown')} testId="global-anim-slideInDown" />
            <AnimPreviewButton animId="zoomIn" label="Zoom In" selected={globalAnimation === 'zoomIn'} onClick={() => setGlobalAnimation('zoomIn')} testId="global-anim-zoomIn" />
            <AnimPreviewButton animId="typewriter" label="Typewriter" selected={globalAnimation === 'typewriter'} onClick={() => setGlobalAnimation('typewriter')} testId="global-anim-typewriter" />
            <AnimPreviewButton animId="bounce" label="Bounce" selected={globalAnimation === 'bounce'} onClick={() => setGlobalAnimation('bounce')} testId="global-anim-bounce" />
          </div>
          {globalAnimation && (
            <div className="text-[10px] text-amber-400/60 flex items-center gap-1">
              <Check className="w-3 h-3" /> Animação "{globalAnimation}" será aplicada a todos os textos.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Brand Library — Use company's curated imagery */}
      <Card className="bg-slate-900/50 border-slate-800" data-testid="brand-library-card">
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-400" /> Biblioteca de Marca da Empresa
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                {brandLibraryCount == null
                  ? 'Use imagens curadas da sua empresa em vez de gerar via IA.'
                  : brandLibraryCount === 0
                    ? 'Nenhuma imagem cadastrada — peça ao super-admin para popular a biblioteca.'
                    : `${brandLibraryCount} imagem(ns) disponíveis. O Agente IA escolherá automaticamente a melhor para cada slide.`}
              </p>
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={!!useBrandLibrary}
                onChange={(e) => setUseBrandLibrary?.(e.target.checked)}
                disabled={brandLibraryCount === 0}
                data-testid="brand-library-toggle"
                className="w-4 h-4 rounded accent-indigo-500"
              />
              <span className="text-sm text-white">{useBrandLibrary ? 'Ativo' : 'Inativo'}</span>
            </label>
          </div>
          {useBrandLibrary && (
            <div className="grid grid-cols-2 gap-2" data-testid="brand-library-mode-picker">
              <button
                type="button"
                onClick={() => setBrandLibraryMode?.('preferred')}
                data-testid="bl-mode-preferred"
                className={`text-left rounded border p-2 ${brandLibraryMode === 'preferred' ? 'border-indigo-400 bg-indigo-500/10' : 'border-slate-700 bg-slate-800/50'}`}
              >
                <p className="text-xs font-medium text-white">Preferida</p>
                <p className="text-[10px] text-slate-400">Tenta a biblioteca; cai para IA se não houver match.</p>
              </button>
              <button
                type="button"
                onClick={() => setBrandLibraryMode?.('strict')}
                data-testid="bl-mode-strict"
                className={`text-left rounded border p-2 ${brandLibraryMode === 'strict' ? 'border-indigo-400 bg-indigo-500/10' : 'border-slate-700 bg-slate-800/50'}`}
              >
                <p className="text-xs font-medium text-white">Estrita</p>
                <p className="text-[10px] text-slate-400">Apenas biblioteca; slides sem match ficam sem imagem.</p>
              </button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Quick apply buttons */}
      <div className="flex gap-2 flex-wrap">
        <Button variant="outline" size="sm" onClick={() => setAllSlidesMedia('ai_image')} className="text-xs" data-testid="set-all-ai-image">
          <Image className="w-3 h-3 mr-1 text-emerald-400" /> Todas: Imagem IA
        </Button>
        <Button variant="outline" size="sm" onClick={() => setAllSlidesMedia('none')} className="text-xs" data-testid="set-all-none">
          <FileText className="w-3 h-3 mr-1" /> Todas: Sem mídia
        </Button>
      </div>

      {/* HeyGen Avatar/Voice Picker */}
      {heygenCount > 0 && (
        <Card className="bg-purple-900/10 border-purple-800/30" data-testid="heygen-config-card">
          <CardContent className="p-4 space-y-3">
            <h3 className="text-sm font-semibold text-purple-300 flex items-center gap-2">
              <UserCircle className="w-4 h-4" /> Configurar Avatar HeyGen
            </h3>
            <p className="text-xs text-purple-300/60">
              Escolha o avatar e a voz que serão usados em {heygenCount} slide{heygenCount > 1 ? 's' : ''}.
              Os vídeos serão gerados automaticamente após a criação do curso.
            </p>

            {/* Avatar selection */}
            <div className="space-y-2">
              <label className="text-xs text-slate-400 font-medium">Avatar</label>
              {loadingAvatars ? (
                <div className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="w-3 h-3 animate-spin" /> Carregando avatares...</div>
              ) : (
                <div className="grid grid-cols-4 gap-2 max-h-48 overflow-y-auto pr-1">
                  {avatars.slice(0, 20).map(av => (
                    <button
                      key={av.avatar_id}
                      onClick={() => setHeygenConfig(prev => ({ ...prev, avatarId: av.avatar_id }))}
                      className={`rounded-lg border-2 overflow-hidden transition-all ${
                        heygenConfig.avatarId === av.avatar_id
                          ? 'border-purple-500 ring-1 ring-purple-500/30'
                          : 'border-slate-700/50 hover:border-purple-500/40'
                      }`}
                      data-testid={`heygen-avatar-${av.avatar_id}`}
                    >
                      {av.preview_image_url ? (
                        <img src={av.preview_image_url} alt={av.avatar_name} className="w-full h-16 object-cover" />
                      ) : (
                        <div className="w-full h-16 bg-slate-800 flex items-center justify-center">
                          <UserCircle className="w-6 h-6 text-slate-600" />
                        </div>
                      )}
                      <p className="text-[9px] text-center text-slate-400 truncate px-1 py-0.5">{av.avatar_name}</p>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Voice selection */}
            <div className="space-y-2">
              <label className="text-xs text-slate-400 font-medium">Voz (Português)</label>
              {loadingVoices ? (
                <div className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="w-3 h-3 animate-spin" /> Carregando vozes...</div>
              ) : (
                <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                  {voices.map(v => (
                    <button
                      key={v.voice_id}
                      onClick={() => setHeygenConfig(prev => ({ ...prev, voiceId: v.voice_id }))}
                      className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-all text-left ${
                        heygenConfig.voiceId === v.voice_id
                          ? 'border-purple-500 bg-purple-600/10 text-purple-300'
                          : 'border-slate-700/50 text-slate-400 hover:border-purple-500/30'
                      }`}
                      data-testid={`heygen-voice-${v.voice_id}`}
                    >
                      <span className="font-medium">{v.name}</span>
                      <span className="text-slate-500">{v.gender}</span>
                      {v.country_flag && <span>{v.country_flag}</span>}
                      {v.preview_audio && (
                        <span
                          role="button"
                          onClick={(e) => { e.stopPropagation(); new Audio(v.preview_audio).play(); }}
                          className="ml-auto text-purple-400 hover:text-purple-300 cursor-pointer"
                          data-testid={`play-voice-${v.voice_id}`}
                        >
                          <Play className="w-3 h-3" />
                        </span>
                      )}
                    </button>
                  ))}
                  {voices.length === 0 && !loadingVoices && (
                    <p className="text-xs text-slate-500 text-center py-2">Nenhuma voz portuguesa encontrada</p>
                  )}
                </div>
              )}
            </div>

            {!heygenReady && (
              <p className="text-[11px] text-amber-400/70 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Selecione um avatar e uma voz para continuar.
              </p>
            )}

            {/* Preview button + video */}
            {heygenReady && (
              <div className="space-y-2 pt-1 border-t border-purple-800/20">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleHeygenPreview}
                  disabled={previewLoading}
                  className="w-full text-xs border-purple-700/50 text-purple-300 hover:bg-purple-600/10"
                  data-testid="heygen-preview-btn"
                >
                  {previewLoading ? (
                    <><Loader2 className="w-3 h-3 animate-spin mr-1" /> Gerando preview (~1-2 min)...</>
                  ) : (
                    <><Eye className="w-3 h-3 mr-1" /> Testar Avatar + Voz</>
                  )}
                </Button>
                {previewUrl && (
                  <div className="rounded-lg overflow-hidden border border-purple-800/30" data-testid="heygen-preview-video">
                    <video src={previewUrl} controls autoPlay className="w-full rounded-lg" style={{ maxHeight: '200px' }} />
                    <p className="text-[10px] text-purple-400/50 text-center py-1">Preview do avatar selecionado</p>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ElevenLabs Narration Voice Picker */}
      {narrationCount > 0 && (
        <Card className="bg-amber-900/10 border-amber-800/30" data-testid="narration-voice-config-card">
          <CardContent className="p-4 space-y-3">
            <h3 className="text-sm font-semibold text-amber-300 flex items-center gap-2">
              <Volume2 className="w-4 h-4" /> Configurar Narração ElevenLabs
            </h3>
            <p className="text-xs text-amber-300/60">
              Selecione a voz e o estilo para narração em {narrationCount} slide{narrationCount > 1 ? 's' : ''}.
              O áudio será gerado automaticamente após a criação do curso.
            </p>

            {/* Narration style */}
            <div className="space-y-1">
              <label className="text-xs text-slate-400 font-medium">Estilo da Narração</label>
              <div className="flex gap-2 flex-wrap">
                {NARRATION_STYLES.map(s => (
                  <button
                    key={s.id}
                    onClick={() => setNarrationStyle(s.id)}
                    className={`text-[11px] px-3 py-1.5 rounded-lg border transition-all ${
                      narrationStyle === s.id ? 'border-amber-500 bg-amber-600/15 text-amber-300' : 'border-slate-700/50 text-slate-500 hover:border-slate-600'
                    }`}
                    data-testid={`narration-style-${s.id}`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Voice selection */}
            <div className="space-y-2">
              <label className="text-xs text-slate-400 font-medium">Voz ElevenLabs</label>
              {loadingElVoices ? (
                <div className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="w-3 h-3 animate-spin" /> Carregando vozes...</div>
              ) : (
                <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
                  {elVoices.map(v => (
                    <button
                      key={v.voice_id}
                      onClick={() => {
                        setNarrationVoiceId(v.voice_id);
                        // Update all narration-enabled slides with the new voice
                        setMediaConfig(prev => {
                          const next = { ...prev };
                          Object.keys(next).forEach(k => {
                            if (next[k]?.narration?.enabled) {
                              next[k] = { ...next[k], narration: { ...next[k].narration, voiceId: v.voice_id } };
                            }
                          });
                          return next;
                        });
                      }}
                      className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-all text-left ${
                        narrationVoiceId === v.voice_id
                          ? 'border-amber-500 bg-amber-600/10 text-amber-300'
                          : 'border-slate-700/50 text-slate-400 hover:border-amber-500/30'
                      }`}
                      data-testid={`el-narration-voice-${v.voice_id}`}
                    >
                      <Volume2 className="w-3 h-3 shrink-0" />
                      <span className="font-medium">{v.name}</span>
                      {v.labels?.gender && <span className="text-slate-500">{v.labels.gender}</span>}
                      {v.preview_url && (
                        <span
                          role="button"
                          onClick={(e) => { e.stopPropagation(); new Audio(v.preview_url).play(); }}
                          className="ml-auto text-amber-400 hover:text-amber-300 cursor-pointer"
                        >
                          <Play className="w-3 h-3" />
                        </span>
                      )}
                    </button>
                  ))}
                  {elVoices.length === 0 && !loadingElVoices && (
                    <p className="text-xs text-slate-500 text-center py-2">Nenhuma voz encontrada</p>
                  )}
                </div>
              )}
            </div>

            {!narrationVoiceId && narrationCount > 0 && (
              <p className="text-[11px] text-amber-400/70 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Selecione uma voz para a narração.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Global Background Control - Apply to ALL slides at once */}
      {/* Design Template Picker */}
      {designTemplates.length > 0 && (
        <Card className="bg-gradient-to-br from-amber-900/20 to-slate-900/50 border-amber-700/30">
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Palette className="w-4 h-4 text-amber-400" />
              <span className="text-sm font-semibold text-amber-300">Tema Visual</span>
              <Badge variant="outline" className="text-[9px] border-amber-600/40 text-amber-400">Aplica fundos + estilos</Badge>
            </div>
            <p className="text-xs text-slate-400">Selecione um tema para aplicar cores, fontes e estilos de header a todos os slides</p>
            <div className="grid grid-cols-3 gap-2" data-testid="media-design-template-grid">
              {designTemplates.map(dt => {
                const isSelected = selectedDesignTemplate?.id === dt.id;
                const p = dt.palette || {};
                return (
                  <button
                    key={dt.id}
                    onClick={() => applyDesignTemplate(isSelected ? null : dt)}
                    className={`relative overflow-hidden rounded-lg border text-left transition-all ${
                      isSelected ? 'border-amber-500 ring-1 ring-amber-500/30' : 'border-slate-700 hover:border-slate-500'
                    }`}
                    data-testid={`media-design-template-${dt.id}`}
                  >
                    <div className="aspect-[16/10] relative" style={{ background: p.primary || '#0f172a' }}>
                      <div className="absolute top-0 left-0 right-0 h-[5px]" style={{ background: p.accent || '#10b981' }} />
                      <div className="absolute bottom-0 left-0 right-0 h-[50%] mx-1.5 mb-1 rounded-t-sm" style={{ background: p.contentBg || '#f0fdf4' }}>
                        <div className="p-1 space-y-0.5">
                          <div className="h-0.5 rounded-full w-[60%]" style={{ background: (p.text || '#1e293b') + '88' }} />
                          <div className="h-0.5 rounded-full w-[40%]" style={{ background: (p.text || '#1e293b') + '44' }} />
                        </div>
                      </div>
                      <div className="absolute top-1.5 left-0 right-0 text-center">
                        <span style={{ fontFamily: dt.fonts?.heading, color: '#fff', fontSize: '8px', fontWeight: 700 }}>Aa</span>
                      </div>
                      {isSelected && <div className="absolute top-0.5 right-0.5 bg-amber-500 rounded-full p-0.5"><Check className="w-2 h-2 text-white" /></div>}
                    </div>
                    <div className="p-1.5 bg-slate-900/80">
                      <p className="font-medium text-[10px] truncate" style={{ fontFamily: dt.fonts?.heading }}>{dt.name}</p>
                    </div>
                  </button>
                );
              })}
            </div>
            {selectedDesignTemplate && (
              <div className="p-2 rounded-lg border border-amber-500/20 bg-amber-900/10 flex items-center gap-2">
                <div className="w-4 h-4 rounded shrink-0" style={{ background: selectedDesignTemplate.preview }} />
                <p className="text-[10px] text-amber-400/80">
                  Tema <span className="font-semibold">"{selectedDesignTemplate.name}"</span> — fundos, fontes e headers serão aplicados ao clicar "Aplicar Alterações"
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card className="bg-gradient-to-br from-cyan-900/30 to-slate-900/50 border-cyan-700/30">
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Palette className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-semibold text-cyan-300">Fundo Global</span>
              <Badge variant="outline" className="text-[9px] border-cyan-600/40 text-cyan-400">Todos os Slides</Badge>
            </div>
          </div>
          <p className="text-xs text-slate-400">Aplicar o mesmo fundo a todos os slides de uma vez</p>
          <SlideBackgroundPicker
            slideIndex="__global__"
            bgConfig={bgConfig}
            setBgConfig={(fn) => {
              const globalBg = typeof fn === 'function' ? fn(bgConfig)['__global__'] : fn['__global__'];
              if (globalBg) {
                setBgConfig(() => {
                  const newConfig = {};
                  const totalSlides = storyboard?.slides?.length || 0;
                  for (let i = 0; i < totalSlides; i++) {
                    newConfig[String(i)] = { ...globalBg };
                  }
                  return newConfig;
                });
                toast.success(`Fundo aplicado a todos os ${storyboard?.slides?.length || 0} slides!`);
              }
            }}
            allSlides={storyboard?.slides || []}
            isGlobal
          />
        </CardContent>
      </Card>

      {/* Per-slide config - ALL slides for background, content slides for media */}
      <div className="space-y-3">
        {(storyboard?.slides || []).map((slide, idx) => {
          const isContent = slide.type === 'content';
          const mc = mediaConfig[String(idx)] || { type: 'ai_image' };
          const borderColor = !isContent ? 'border-slate-700/50'
            : mc.type === 'ai_image' ? 'border-emerald-600/40' : mc.type === 'gallery_image' ? 'border-amber-600/40' : mc.type === 'youtube' ? 'border-red-600/40' : mc.type === 'vimeo' ? 'border-blue-600/40' : mc.type === 'heygen' ? 'border-purple-600/40' : 'border-slate-700';
          const typeLabel = { title: 'Capa', content: 'Conteúdo', quiz: 'Quiz', summary: 'Resumo' };
          const typeColor = { title: 'text-blue-400 border-blue-500/40', content: 'text-slate-400 border-slate-600', quiz: 'text-amber-400 border-amber-500/40', summary: 'text-purple-400 border-purple-500/40' };

          return (
            <Card key={idx} className={`bg-slate-900/50 ${borderColor} transition-colors`} data-testid={`media-slide-${idx}`}>
              <CardContent className="p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className={`text-[10px] ${typeColor[slide.type] || 'border-slate-600 text-slate-400'}`}>
                    {typeLabel[slide.type] || slide.type} {idx + 1}
                  </Badge>
                  <span className="text-sm font-medium truncate">{slide.title}</span>
                  {slide.moduleName && <span className="text-[10px] text-slate-500 ml-auto shrink-0">{slide.moduleName}</span>}
                </div>

                {/* Background picker - ALL slides */}
                <SlideBackgroundPicker
                  slideIndex={idx}
                  bgConfig={bgConfig}
                  setBgConfig={setBgConfig}
                  allSlides={storyboard?.slides || []}
                />

                {/* Media type selector - only content slides */}
                {isContent && (
                  <>
                    <div className="border-t border-slate-800 pt-2">
                      <div className="flex items-center gap-2 mb-2">
                        <Image className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-xs font-medium text-emerald-300">Mídia</span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {MEDIA_TYPES.map(mt => {
                          const Icon = mt.icon;
                          const isActive = mc.type === mt.id;
                          const bgColors = {
                            emerald: 'bg-emerald-600/15 border-emerald-500 text-emerald-300',
                            amber: 'bg-amber-600/15 border-amber-500 text-amber-300',
                            red: 'bg-red-600/15 border-red-500 text-red-300',
                            blue: 'bg-blue-600/15 border-blue-500 text-blue-300',
                            purple: 'bg-purple-600/15 border-purple-500 text-purple-300',
                            orange: 'bg-orange-600/15 border-orange-500 text-orange-300',
                            cyan: 'bg-cyan-600/15 border-cyan-500 text-cyan-300',
                            teal: 'bg-teal-600/15 border-teal-500 text-teal-300',
                            indigo: 'bg-indigo-600/15 border-indigo-500 text-indigo-300',
                            violet: 'bg-violet-600/15 border-violet-500 text-violet-300',
                            slate: 'bg-slate-800 border-slate-600 text-slate-300',
                          };
                          return (
                            <button
                              key={mt.id}
                              onClick={() => {
                                if (mt.id === 'gallery_image') {
                                  setGallerySlideIndex(idx);
                                  setShowGallery(true);
                                } else if (mt.id === 'brand_library_image') {
                                  setBrandPickerSlideIdx(idx);
                                  setShowBrandPicker(true);
                                } else {
                                  updateSlideMedia(idx, mt.id, '');
                                }
                              }}
                              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-all ${
                                isActive ? bgColors[mt.color] : 'border-slate-700/50 text-slate-500 hover:border-slate-600 hover:text-slate-400'
                              }`}
                              data-testid={`media-type-${mt.id}-slide-${idx}`}
                            >
                              <Icon className="w-3.5 h-3.5" />
                              {mt.label}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* URL input for YouTube/Vimeo */}
                    {(mc.type === 'youtube' || mc.type === 'vimeo') && (
                      <Input
                        value={mc.url || ''}
                        onChange={e => updateSlideMedia(idx, mc.type, e.target.value)}
                        placeholder={mc.type === 'youtube' ? 'https://youtube.com/watch?v=...' : 'https://vimeo.com/...'}
                        className="bg-slate-800 border-slate-700 text-sm"
                        data-testid={`media-url-slide-${idx}`}
                      />
                    )}

                    {/* AI image info */}
                    {mc.type === 'ai_image' && slide.imageKeywords && (
                      <p className="text-[11px] text-emerald-400/60">
                        <Sparkles className="w-3 h-3 inline mr-1" />
                        Será gerada imagem sobre: {slide.imageKeywords}
                      </p>
                    )}

                    {/* Gallery image preview */}
                    {mc.type === 'gallery_image' && mc.galleryImageUrl && (
                      <div className="flex items-center gap-3 p-2 bg-amber-900/10 rounded-lg border border-amber-700/30">
                        <img src={mc.galleryImageUrl.startsWith('/') ? `${API}${mc.galleryImageUrl}` : mc.galleryImageUrl} alt="" className="w-16 h-12 object-cover rounded" />
                        <div className="flex-1 min-w-0">
                          <p className="text-[11px] text-amber-300 truncate">{mc.galleryKeywords || 'Imagem da galeria'}</p>
                          <button onClick={() => { setGallerySlideIndex(idx); setShowGallery(true); }} className="text-[10px] text-amber-400/70 hover:text-amber-300 underline">Trocar imagem</button>
                        </div>
                      </div>
                    )}
                    {mc.type === 'gallery_image' && !mc.galleryImageUrl && (
                      <button onClick={() => { setGallerySlideIndex(idx); setShowGallery(true); }} className="text-[11px] text-amber-400/70 hover:text-amber-300 flex items-center gap-1">
                        <ImagePlus className="w-3 h-3" /> Clique para selecionar da galeria
                      </button>
                    )}

                    {/* Brand Library image preview — manual per-slide pick */}
                    {mc.type === 'brand_library_image' && mc.brandImageUrl && (
                      <div className="flex items-center gap-3 p-2 bg-indigo-900/10 rounded-lg border border-indigo-700/30" data-testid={`brand-lib-preview-slide-${idx}`}>
                        <img
                          src={mc.brandImageUrl.startsWith('/') ? `${API}${mc.brandImageUrl}` : mc.brandImageUrl}
                          alt=""
                          className="w-16 h-12 object-cover rounded"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-[11px] text-indigo-300 truncate">
                            {mc.brandImageFilename || 'Imagem da biblioteca'}
                          </p>
                          <button
                            onClick={() => { setBrandPickerSlideIdx(idx); setShowBrandPicker(true); }}
                            className="text-[10px] text-indigo-400/70 hover:text-indigo-300 underline"
                            data-testid={`brand-lib-swap-slide-${idx}`}
                          >
                            Trocar imagem
                          </button>
                        </div>
                      </div>
                    )}
                    {mc.type === 'brand_library_image' && !mc.brandImageUrl && (
                      <button
                        onClick={() => { setBrandPickerSlideIdx(idx); setShowBrandPicker(true); }}
                        className="text-[11px] text-indigo-400/70 hover:text-indigo-300 flex items-center gap-1"
                        data-testid={`brand-lib-open-slide-${idx}`}
                      >
                        <Layers className="w-3 h-3" /> Clique para escolher da biblioteca da empresa
                      </button>
                    )}

                    {/* Leonardo AI info */}
                    {mc.type === 'leonardo' && (
                      <div className="space-y-1.5">
                        <p className="text-[11px] text-violet-400/60">
                          <Sparkles className="w-3 h-3 inline mr-1" />
                          Imagem sera gerada via Leonardo AI com alta qualidade
                        </p>
                        <Input
                          value={mc.leonardoPrompt || ''}
                          onChange={e => updateSlideMedia(idx, 'leonardo', mc.url || '', { leonardoPrompt: e.target.value })}
                          placeholder="Descreva a imagem (opcional - usa keywords do slide por padrao)"
                          className="h-7 text-[11px] bg-slate-800/60 border-violet-700/30"
                          data-testid={`leonardo-prompt-${idx}`}
                        />
                      </div>
                    )}

                    {/* HeyGen info */}
                    {mc.type === 'heygen' && (
                      <p className="text-[11px] text-purple-400/60">
                        <UserCircle className="w-3 h-3 inline mr-1" />
                        {heygenConfig.avatarId && heygenConfig.voiceId
                          ? 'Avatar e voz selecionados. O vídeo será gerado automaticamente.'
                          : 'Configure o avatar e a voz acima para gerar o vídeo.'}
                      </p>
                    )}

                    {/* Flipbook config */}
                    {mc.type === 'flipbook' && (
                      <div className="space-y-2" data-testid={`flipbook-config-${idx}`}>
                        <div className="flex gap-2">
                          <button
                            onClick={() => updateSlideMedia(idx, 'flipbook', mc.url || '', { flipbookSource: 'url' })}
                            className={`text-[10px] px-2 py-1 rounded border transition-colors ${mc.flipbookSource !== 'upload' ? 'border-orange-500/50 text-orange-300 bg-orange-600/10' : 'border-slate-700 text-slate-500'}`}
                          >URL</button>
                          <button
                            onClick={() => updateSlideMedia(idx, 'flipbook', mc.url || '', { flipbookSource: 'upload' })}
                            className={`text-[10px] px-2 py-1 rounded border transition-colors ${mc.flipbookSource === 'upload' ? 'border-orange-500/50 text-orange-300 bg-orange-600/10' : 'border-slate-700 text-slate-500'}`}
                          >Upload PDF</button>
                        </div>
                        {mc.flipbookSource === 'upload' ? (
                          <div className="space-y-1">
                            <label className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-dashed border-slate-600 text-xs text-slate-400 hover:border-orange-500/50 hover:text-orange-300 cursor-pointer transition-colors">
                              <UploadCloud className="w-3.5 h-3.5" /> {mc.fileName || 'Selecionar PDF'}
                              <input type="file" accept=".pdf" onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) updateSlideMedia(idx, 'flipbook', '', { flipbookSource: 'upload', fileName: file.name, file });
                              }} className="hidden" />
                            </label>
                          </div>
                        ) : (
                          <Input
                            value={mc.url || ''}
                            onChange={e => updateSlideMedia(idx, 'flipbook', e.target.value)}
                            placeholder="https://flipbook-url.com/embed/..."
                            className="bg-slate-800 border-slate-700 text-sm"
                            data-testid={`flipbook-url-${idx}`}
                          />
                        )}
                        <p className="text-[10px] text-orange-400/50">O flipbook será embutido como elemento interativo no slide.</p>
                      </div>
                    )}

                    {/* HTML embed config */}
                    {mc.type === 'html' && (
                      <div className="space-y-2" data-testid={`html-config-${idx}`}>
                        <div className="flex gap-2">
                          <button
                            onClick={() => updateSlideMedia(idx, 'html', mc.url || '', { htmlSource: 'url' })}
                            className={`text-[10px] px-2 py-1 rounded border transition-colors ${mc.htmlSource !== 'code' ? 'border-cyan-500/50 text-cyan-300 bg-cyan-600/10' : 'border-slate-700 text-slate-500'}`}
                          >URL / iframe</button>
                          <button
                            onClick={() => updateSlideMedia(idx, 'html', mc.url || '', { htmlSource: 'code' })}
                            className={`text-[10px] px-2 py-1 rounded border transition-colors ${mc.htmlSource === 'code' ? 'border-cyan-500/50 text-cyan-300 bg-cyan-600/10' : 'border-slate-700 text-slate-500'}`}
                          >Código HTML</button>
                        </div>
                        {mc.htmlSource === 'code' ? (
                          <textarea
                            value={mc.htmlCode || ''}
                            onChange={e => updateSlideMedia(idx, 'html', '', { htmlSource: 'code', htmlCode: e.target.value })}
                            placeholder="<div>Seu HTML aqui...</div>"
                            rows={4}
                            className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs font-mono text-cyan-300 resize-y"
                            data-testid={`html-code-${idx}`}
                          />
                        ) : (
                          <Input
                            value={mc.url || ''}
                            onChange={e => updateSlideMedia(idx, 'html', e.target.value)}
                            placeholder="https://site.com/embed/..."
                            className="bg-slate-800 border-slate-700 text-sm"
                            data-testid={`html-url-${idx}`}
                          />
                        )}
                        <p className="text-[10px] text-cyan-400/50">Conteúdo HTML será renderizado dentro do slide.</p>
                      </div>
                    )}

                    {/* Button with external link config */}
                    {mc.type === 'button' && (
                      <div className="space-y-2" data-testid={`button-config-${idx}`}>
                        <Input
                          value={mc.buttonText || ''}
                          onChange={e => updateSlideMedia(idx, 'button', mc.url || '', { buttonText: e.target.value })}
                          placeholder="Texto do botão (ex: Saiba Mais)"
                          className="bg-slate-800 border-slate-700 text-sm"
                          data-testid={`button-text-${idx}`}
                        />
                        <Input
                          value={mc.url || ''}
                          onChange={e => updateSlideMedia(idx, 'button', e.target.value, { buttonText: mc.buttonText })}
                          placeholder="https://link-externo.com"
                          className="bg-slate-800 border-slate-700 text-sm"
                          data-testid={`button-url-${idx}`}
                        />
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-slate-400">Cor:</span>
                          <input
                            type="color"
                            value={mc.buttonColor || '#10b981'}
                            onChange={e => updateSlideMedia(idx, 'button', mc.url || '', { buttonText: mc.buttonText, buttonColor: e.target.value })}
                            className="w-6 h-6 rounded cursor-pointer border-0 bg-transparent"
                          />
                          <div className="flex-1 flex items-center justify-center px-3 py-1.5 rounded-lg text-xs text-white font-medium" style={{ background: mc.buttonColor || '#10b981' }}>
                            {mc.buttonText || 'Botão'}
                          </div>
                        </div>
                        <p className="text-[10px] text-teal-400/50">O botão será inserido no slide com link para URL externa.</p>
                      </div>
                    )}

                    {/* Per-slide Narration */}
                    <div className="border-t border-slate-800 pt-2">
                      <div className="flex items-center gap-2 mb-2">
                        <Volume2 className="w-3.5 h-3.5 text-amber-400" />
                        <span className="text-xs font-medium text-amber-300">Narração</span>
                        <button
                          onClick={() => toggleSlideNarration(idx, !mc.narration?.enabled)}
                          className={`ml-auto w-9 h-5 rounded-full transition-colors relative ${mc.narration?.enabled ? 'bg-amber-600' : 'bg-slate-700'}`}
                          data-testid={`narration-toggle-slide-${idx}`}
                        >
                          <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${mc.narration?.enabled ? 'translate-x-4' : 'translate-x-0.5'}`} />
                        </button>
                      </div>

                      {mc.narration?.enabled && (
                        <div className="space-y-2 pl-1">
                          {/* Generate scripts button */}
                          {!scriptOptions[idx] && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => generateNarrationScripts(idx)}
                              disabled={generatingScripts[idx]}
                              className="w-full text-xs border-amber-700/50 text-amber-300 hover:bg-amber-600/10"
                              data-testid={`generate-narration-slide-${idx}`}
                            >
                              {generatingScripts[idx] ? (
                                <><Loader2 className="w-3 h-3 animate-spin mr-1" /> Gerando 3 opções...</>
                              ) : (
                                <><Sparkles className="w-3 h-3 mr-1" /> Gerar 3 Opções de Roteiro</>
                              )}
                            </Button>
                          )}

                          {/* Script options */}
                          {scriptOptions[idx] && (
                            <div className="space-y-2">
                              <div className="flex items-center justify-between">
                                <span className="text-[10px] text-slate-400 font-medium">Escolha um roteiro:</span>
                                <button
                                  onClick={() => {
                                    setScriptOptions(prev => { const n = {...prev}; delete n[idx]; return n; });
                                    generateNarrationScripts(idx);
                                  }}
                                  className="text-[10px] text-amber-400 hover:text-amber-300 flex items-center gap-1"
                                  disabled={generatingScripts[idx]}
                                >
                                  <RefreshCw className="w-3 h-3" /> Regenerar
                                </button>
                              </div>
                              {scriptOptions[idx].map((opt, oi) => {
                                const isSelected = mc.narration?.selectedScript === opt;
                                return (
                                  <div
                                    key={oi}
                                    role="button"
                                    tabIndex={0}
                                    onClick={() => selectNarrationScript(idx, opt)}
                                    className={`w-full text-left p-2.5 rounded-lg border text-[11px] leading-relaxed transition-all cursor-pointer ${
                                      isSelected
                                        ? 'border-amber-500 bg-amber-600/10 text-amber-200'
                                        : 'border-slate-700/50 text-slate-400 hover:border-amber-500/30'
                                    }`}
                                    data-testid={`narration-option-${idx}-${oi}`}
                                  >
                                    <div className="flex items-start gap-2">
                                      <Badge variant="outline" className={`text-[9px] shrink-0 mt-0.5 ${isSelected ? 'border-amber-500 text-amber-300' : 'border-slate-600 text-slate-500'}`}>
                                        {oi + 1}
                                      </Badge>
                                      <span>{opt}</span>
                                    </div>
                                    {isSelected && narrationVoiceId && (
                                      <div className="flex items-center gap-2 mt-2 pt-2 border-t border-amber-800/30">
                                        <button
                                          onClick={(e) => { e.stopPropagation(); previewNarration(idx, opt); }}
                                          disabled={previewingAudio === idx}
                                          className="text-[10px] text-amber-400 hover:text-amber-300 flex items-center gap-1"
                                        >
                                          {previewingAudio === idx ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                                          Ouvir Preview
                                        </button>
                                        <Check className="w-3 h-3 text-amber-400 ml-auto" />
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          )}

                          {mc.narration?.selectedScript && (
                            <p className="text-[10px] text-amber-400/60 flex items-center gap-1">
                              <Check className="w-3 h-3" /> Roteiro selecionado. Áudio será gerado com a voz escolhida.
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Summary & Cost Estimate */}
      <CostEstimateCard sessionId={sessionId} aiCount={aiCount} leonardoCount={leonardoCount} videoCount={videoCount} heygenCount={heygenCount} bgConfig={bgConfig} isEditMode={isEditMode} changedSlideCount={changedSlideCount} />

      {(!heygenReady || !narrationReady) && !loading && (
        <p className="text-xs text-amber-400/80 text-center">
          {!heygenReady && 'Selecione avatar e voz do HeyGen. '}
          {!narrationReady && 'Selecione uma voz para a narração antes de aplicar.'}
        </p>
      )}
      <Button onClick={onConfirm} disabled={loading || !heygenReady || !narrationReady} className={`w-full ${isEditMode ? 'bg-blue-600 hover:bg-blue-700' : 'bg-emerald-600 hover:bg-emerald-700'}`} data-testid="confirm-media-btn">
        {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : isEditMode ? <Check className="w-4 h-4 mr-1" /> : <Play className="w-4 h-4 mr-1" />}
        {isEditMode ? 'Aplicar Alterações ao Projeto' : 'Confirmar Mídia e Gerar Curso'}
      </Button>

      {/* Image Gallery Modal */}
      {showGallery && (
        <ImageGalleryModal
          onClose={() => setShowGallery(false)}
          onSelect={(img) => {
            if (gallerySlideIndex !== null) {
              updateSlideMedia(gallerySlideIndex, 'gallery_image', '', {
                galleryImageUrl: img.imageUrl,
                galleryKeywords: img.keywords,
                galleryImageId: img.id,
              });
            }
            setShowGallery(false);
          }}
        />
      )}

      {/* Brand Library Picker — per-slide manual selection from the company's
          curated imagery. Same `BrandLibraryPicker` used in the Editor so the
          UX feels consistent between Wizard and post-generation editing. */}
      <BrandLibraryPicker
        open={showBrandPicker}
        onClose={() => setShowBrandPicker(false)}
        companyId={brandLibraryCompanyId}
        defaultType="background"
        onPick={(asset) => {
          if (brandPickerSlideIdx !== null) {
            updateSlideMedia(brandPickerSlideIdx, 'brand_library_image', '', {
              brandImageUrl: asset.url,
              brandImageAssetId: asset.id,
              brandImageFilename: asset.originalFilename || asset.filename,
            });
          }
          setShowBrandPicker(false);
        }}
      />
    </div>
  );
}


