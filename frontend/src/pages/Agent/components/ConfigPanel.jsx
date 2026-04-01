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

const API = getApiUrl();

const TEMPLATE_ICONS = {
  users: Users, shield: Shield, wrench: Wrench, heart: Heart,
  'hard-hat': HardHat, 'trending-up': TrendingUp,
};

export default function ConfigPanel({ config, setConfig, analysis, loading, onGenerate, templates, selectedTemplate, setSelectedTemplate, designTemplates, selectedDesignTemplate, setSelectedDesignTemplate }) {
  const update = (k, v) => setConfig(prev => ({ ...prev, [k]: v }));
  const [elVoices, setElVoices] = useState([]);
  const [loadingVoices, setLoadingVoices] = useState(false);

  useEffect(() => {
    if (config.narrationEnabled && elVoices.length === 0 && !loadingVoices) {
      setLoadingVoices(true);
      fetch(`${API}/api/elevenlabs/voices`, { headers: authHeaders() })
        .then(r => r.json())
        .then(data => setElVoices(data.voices || []))
        .catch(() => {})
        .finally(() => setLoadingVoices(false));
    }
  }, [config.narrationEnabled]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-4" data-testid="config-panel">
      <h2 className="text-lg font-semibold flex items-center gap-2"><Settings className="w-5 h-5 text-emerald-400" /> Configuração do Curso</h2>

      {/* Template Selection */}
      {templates.length > 0 && (
        <div className="space-y-2">
          <label className="text-xs text-slate-400 block">Template (opcional)</label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2" data-testid="template-grid">
            {templates.map(t => {
              const Icon = TEMPLATE_ICONS[t.icon] || BookOpen;
              const isSelected = selectedTemplate?.id === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => {
                    if (isSelected) {
                      setSelectedTemplate(null);
                    } else {
                      setSelectedTemplate(t);
                      setConfig(prev => ({ ...prev, ...t.defaultConfig }));
                    }
                  }}
                  className={`flex items-center gap-2 p-3 rounded-lg border text-left transition-all text-sm ${
                    isSelected
                      ? 'border-emerald-500 bg-emerald-600/10'
                      : 'border-slate-700 bg-slate-800/50 hover:border-slate-600'
                  }`}
                  data-testid={`template-${t.id}`}
                >
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ backgroundColor: t.color + '20' }}>
                    <Icon className="w-4 h-4" style={{ color: t.color }} />
                  </div>
                  <div className="min-w-0">
                    <p className="font-medium text-xs truncate">{t.name}</p>
                    <p className="text-[10px] text-slate-400 truncate">{t.description}</p>
                  </div>
                  {isSelected && <Check className="w-4 h-4 text-emerald-400 shrink-0 ml-auto" />}
                </button>
              );
            })}
          </div>
          {selectedTemplate && (
            <p className="text-xs text-emerald-400/70">
              <Zap className="w-3 h-3 inline mr-1" />
              Template "{selectedTemplate.name}" selecionado - configuração ajustada automaticamente
            </p>
          )}
        </div>
      )}

      {/* Design Template (Visual Theme) Selection */}
      {designTemplates.length > 0 && (
        <div className="space-y-2">
          <label className="text-xs text-slate-400 block flex items-center gap-1"><Palette className="w-3 h-3" /> Tema Visual</label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3" data-testid="design-template-grid">
            {designTemplates.map(dt => {
              const isSelected = selectedDesignTemplate?.id === dt.id;
              const p = dt.palette || {};
              return (
                <button
                  key={dt.id}
                  onClick={() => setSelectedDesignTemplate(isSelected ? null : dt)}
                  className={`relative overflow-hidden rounded-xl border text-left transition-all ${
                    isSelected
                      ? 'border-emerald-500 ring-2 ring-emerald-500/30 scale-[1.02]'
                      : 'border-slate-700 hover:border-slate-500'
                  }`}
                  data-testid={`design-template-${dt.id}`}
                >
                  {/* Mini slide preview */}
                  <div className="aspect-[16/9] relative" style={{ background: p.primary || '#0f172a' }}>
                    {/* Header bar */}
                    <div className="absolute top-0 left-0 right-0 h-[6px]" style={{ background: p.accent || '#10b981' }} />
                    {/* Content area */}
                    <div className="absolute bottom-0 left-0 right-0 h-[55%] mx-2 mb-1 rounded-t-sm" style={{ background: p.contentBg || '#f0fdf4' }}>
                      <div className="p-1.5 space-y-0.5">
                        <div className="h-1 rounded-full w-[60%]" style={{ background: (p.text || '#1e293b') + '88' }} />
                        <div className="h-0.5 rounded-full w-[80%]" style={{ background: (p.text || '#1e293b') + '44' }} />
                        <div className="h-0.5 rounded-full w-[50%]" style={{ background: (p.text || '#1e293b') + '44' }} />
                      </div>
                    </div>
                    {/* Font preview */}
                    <div className="absolute top-2 left-2 right-2 text-center">
                      <span style={{ fontFamily: dt.fonts?.heading, color: '#fff', fontSize: '9px', fontWeight: 700 }}>Aa</span>
                    </div>
                    {isSelected && (
                      <div className="absolute top-1 right-1 bg-emerald-500 rounded-full p-0.5">
                        <Check className="w-2.5 h-2.5 text-white" />
                      </div>
                    )}
                  </div>
                  {/* Name and description */}
                  <div className="p-2 bg-slate-900/80">
                    <p className="font-medium text-[11px] truncate" style={{ fontFamily: dt.fonts?.heading }}>{dt.name}</p>
                    <p className="text-[9px] text-slate-500 truncate">{dt.description}</p>
                  </div>
                </button>
              );
            })}
          </div>
          {selectedDesignTemplate && (
            <div className="p-2 rounded-lg border border-emerald-500/20 bg-emerald-900/10 flex items-center gap-2">
              <div className="w-5 h-5 rounded shrink-0" style={{ background: selectedDesignTemplate.preview }} />
              <p className="text-xs text-emerald-400/80">
                Tema <span className="font-semibold" style={{ fontFamily: selectedDesignTemplate.fonts?.heading }}>"{selectedDesignTemplate.name}"</span> será aplicado a todos os slides
              </p>
            </div>
          )}
        </div>
      )}

      <div className="grid gap-4">
        <Card className="bg-slate-900/50 border-slate-800">
          <CardContent className="p-4 space-y-4">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Título do Curso</label>
              <Input data-testid="config-title" value={config.title} onChange={e => update('title', e.target.value)} className="bg-slate-800 border-slate-700" />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Descrição</label>
              <Textarea value={config.description} onChange={e => update('description', e.target.value)} className="bg-slate-800 border-slate-700 text-sm" rows={2} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Nível</label>
                <Select value={config.depth} onValueChange={v => update('depth', v)}>
                  <SelectTrigger className="bg-slate-800 border-slate-700"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="basico">Básico</SelectItem>
                    <SelectItem value="intermediario">Intermediário</SelectItem>
                    <SelectItem value="avancado">Avançado</SelectItem>
                    <SelectItem value="especialista">Especialista</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Formato</label>
                <Select value={config.format} onValueChange={v => update('format', v)}>
                  <SelectTrigger className="bg-slate-800 border-slate-700"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="curso_completo">Curso Completo</SelectItem>
                    <SelectItem value="microlearning">Microlearning</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Duração alvo: {config.duration} minutos</label>
              <Slider value={[config.duration]} onValueChange={([v]) => update('duration', v)} min={5} max={120} step={5} className="mt-2" />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Módulos: {config.modules}</label>
              <Slider value={[config.modules]} onValueChange={([v]) => update('modules', v)} min={1} max={12} step={1} className="mt-2" />
            </div>
          </CardContent>
        </Card>

        {/* Narration Config */}
        <Card className="bg-slate-900/50 border-slate-800" data-testid="narration-config-card">
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Play className="w-4 h-4 text-amber-400" />
                <label className="text-sm font-medium">Narração Automática</label>
              </div>
              <button
                onClick={() => update('narrationEnabled', !config.narrationEnabled)}
                className={`w-10 h-5 rounded-full transition-colors relative ${config.narrationEnabled ? 'bg-amber-600' : 'bg-slate-700'}`}
                data-testid="narration-toggle"
              >
                <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${config.narrationEnabled ? 'translate-x-5' : 'translate-x-0.5'}`} />
              </button>
            </div>
            <p className="text-xs text-slate-400">Gerar áudio de narração para cada slide usando ElevenLabs (processado após criação do curso).</p>

            {config.narrationEnabled && (
              <div className="space-y-2 pt-1">
                <label className="text-xs text-slate-400 font-medium">Voz ElevenLabs</label>
                {loadingVoices ? (
                  <div className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="w-3 h-3 animate-spin" /> Carregando vozes...</div>
                ) : (
                  <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                    {elVoices.slice(0, 30).map(v => (
                      <button
                        key={v.voice_id}
                        onClick={() => update('narrationVoiceId', v.voice_id)}
                        className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-all text-left ${
                          config.narrationVoiceId === v.voice_id
                            ? 'border-amber-500 bg-amber-600/10 text-amber-300'
                            : 'border-slate-700/50 text-slate-400 hover:border-amber-500/30'
                        }`}
                        data-testid={`el-voice-${v.voice_id}`}
                      >
                        <span className="font-medium">{v.name}</span>
                        {v.gender && <span className="text-slate-500">{v.gender}</span>}
                        {v.accent && <span className="text-slate-600">{v.accent}</span>}
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
                  </div>
                )}
                {config.narrationEnabled && !config.narrationVoiceId && (
                  <p className="text-[11px] text-amber-400/70 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" /> Selecione uma voz para a narração.
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
      <Button onClick={onGenerate} disabled={loading} className="w-full bg-emerald-600 hover:bg-emerald-700" data-testid="generate-structure-btn">
        {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Layers className="w-4 h-4 mr-1" />}
        {selectedTemplate ? `Gerar com Template "${selectedTemplate.name}"` : 'Gerar Estrutura do Curso'}
      </Button>
    </div>
  );
}

