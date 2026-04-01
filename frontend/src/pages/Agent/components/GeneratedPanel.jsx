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

// Priority styles for suggestions
const PRIORITY_STYLES = {
  alta: 'bg-red-600/15 text-red-300 border-red-500/40',
  media: 'bg-amber-600/15 text-amber-300 border-amber-500/40',
  baixa: 'bg-slate-700/30 text-slate-300 border-slate-600/40',
};

// SuggestionsCategory component for displaying improvement suggestions
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

export default function GeneratedPanel({ project, navigate, sessionId }) {
  const [heygenStatus, setHeygenStatus] = useState(null);
  const [narrationStatus, setNarrationStatus] = useState(null);
  const [polling, setPolling] = useState(false);
  const [suggestions, setSuggestions] = useState(null);
  const [suggestionsStatus, setSuggestionsStatus] = useState('loading');
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const checkHeygenStatus = useCallback(async () => {
    if (!project?.projectId || !project?.heygenPending) return;
    setPolling(true);
    try {
      const res = await fetch(`${API}/api/agent/projects/${project.projectId}/heygen-status`, { headers: authHeaders() });
      const data = await res.json();
      setHeygenStatus(data);
    } catch { /* ignore */ }
    finally { setPolling(false); }
  }, [project?.projectId, project?.heygenPending]);

  const checkNarrationStatus = useCallback(async () => {
    if (!project?.projectId || !project?.narrationPending) return;
    try {
      const res = await fetch(`${API}/api/agent/projects/${project.projectId}/narration-status`, { headers: authHeaders() });
      const data = await res.json();
      setNarrationStatus(data);
    } catch { /* ignore */ }
  }, [project?.projectId, project?.narrationPending]);

  useEffect(() => {
    if (project?.heygenPending > 0) {
      checkHeygenStatus();
      const interval = setInterval(checkHeygenStatus, 15000);
      return () => clearInterval(interval);
    }
  }, [project?.heygenPending, checkHeygenStatus]);

  useEffect(() => {
    if (project?.narrationPending > 0) {
      checkNarrationStatus();
      const interval = setInterval(checkNarrationStatus, 10000);
      return () => clearInterval(interval);
    }
  }, [project?.narrationPending, checkNarrationStatus]);

  // Poll for suggestions
  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await fetch(`${API}/api/agent/sessions/${sessionId}/suggestions`, { headers: authHeaders() });
        const data = await res.json();
        if (cancelled) return;
        if (data.status === 'ready') {
          setSuggestions(data.suggestions);
          setSuggestionsStatus('ready');
        } else if (data.status === 'error') {
          setSuggestionsStatus('error');
        } else {
          setSuggestionsStatus('pending');
        }
      } catch { if (!cancelled) setSuggestionsStatus('error'); }
    };
    poll();
    const interval = setInterval(() => {
      if (suggestionsStatus === 'pending') poll();
    }, 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [sessionId, suggestionsStatus]);

  const handleRegenerateSuggestions = async () => {
    setRegenerating(true);
    setSuggestionsStatus('pending');
    setSuggestions(null);
    try {
      await fetch(`${API}/api/agent/sessions/${sessionId}/suggestions/regenerate`, { method: 'POST', headers: authHeaders() });
    } catch { /* will poll */ }
    finally { setRegenerating(false); }
  };

  if (!project) return null;
  return (
    <div className="space-y-6 text-center" data-testid="generated-panel">
      <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-emerald-600/10">
        <Check className="w-10 h-10 text-emerald-400" />
      </div>
      <h2 className="text-2xl font-bold">Curso Gerado com Sucesso!</h2>
      <p className="text-slate-400">{project.projectName}</p>
      <div className="flex justify-center gap-4">
        <Badge className="bg-emerald-600/20 text-emerald-300"><Layers className="w-3 h-3 mr-1" />{project.slidesCount} slides</Badge>
        <Badge className="bg-amber-600/20 text-amber-300"><BarChart3 className="w-3 h-3 mr-1" />{project.quizCount} perguntas</Badge>
      </div>

      {/* HeyGen Video Status */}
      {project.heygenPending > 0 && (
        <Card className="bg-purple-900/10 border-purple-800/30 text-left mx-auto max-w-md" data-testid="heygen-status-card">
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-purple-300 flex items-center gap-2">
                <UserCircle className="w-4 h-4" /> Vídeos Avatar HeyGen
              </h3>
              <Button variant="ghost" size="sm" onClick={checkHeygenStatus} disabled={polling} className="text-xs text-purple-400" data-testid="refresh-heygen-btn">
                {polling ? <Loader2 className="w-3 h-3 animate-spin" /> : <ArrowRight className="w-3 h-3" />} Atualizar
              </Button>
            </div>
            {heygenStatus?.videos?.map((v, i) => (
              <div key={i} className="flex items-center gap-2 text-xs" data-testid={`heygen-video-status-${i}`}>
                {v.status === 'completed' ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                ) : v.status === 'failed' ? (
                  <X className="w-3.5 h-3.5 text-red-400 shrink-0" />
                ) : (
                  <Loader2 className="w-3.5 h-3.5 text-purple-400 animate-spin shrink-0" />
                )}
                <span className="text-slate-300 truncate flex-1">{v.title}</span>
                <Badge variant="outline" className={`text-[9px] ${
                  v.status === 'completed' ? 'border-emerald-700 text-emerald-400' :
                  v.status === 'failed' ? 'border-red-700 text-red-400' :
                  'border-purple-700 text-purple-400'
                }`}>
                  {v.status === 'completed' ? 'Pronto' : v.status === 'failed' ? 'Falhou' : 'Processando...'}
                </Badge>
              </div>
            ))}
            {heygenStatus?.status === 'all_done' && (
              <p className="text-[11px] text-emerald-400/70 text-center">Todos os vídeos foram gerados! Abra o editor para visualizar.</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Narration Status */}
      {project.narrationPending > 0 && (
        <Card className="bg-amber-900/10 border-amber-800/30 text-left mx-auto max-w-md" data-testid="narration-status-card">
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-amber-300 flex items-center gap-2">
                <Play className="w-4 h-4" /> Narração ElevenLabs
              </h3>
              {narrationStatus && (
                <Badge variant="outline" className={`text-[10px] ${narrationStatus.status === 'all_done' ? 'border-emerald-700 text-emerald-400' : 'border-amber-700 text-amber-400'}`}>
                  {narrationStatus.completed || 0}/{narrationStatus.total || 0}
                </Badge>
              )}
            </div>
            {narrationStatus?.slides?.map((s, i) => (
              <div key={i} className="flex items-center gap-2 text-xs" data-testid={`narration-status-${i}`}>
                {s.status === 'completed' ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                ) : s.status === 'failed' ? (
                  <X className="w-3.5 h-3.5 text-red-400 shrink-0" />
                ) : (
                  <Loader2 className="w-3.5 h-3.5 text-amber-400 animate-spin shrink-0" />
                )}
                <span className="text-slate-300 truncate flex-1">{s.title}</span>
                <Badge variant="outline" className={`text-[9px] ${
                  s.status === 'completed' ? 'border-emerald-700 text-emerald-400' :
                  s.status === 'failed' ? 'border-red-700 text-red-400' :
                  'border-amber-700 text-amber-400'
                }`}>
                  {s.status === 'completed' ? 'Pronto' : s.status === 'failed' ? 'Falhou' : 'Gerando...'}
                </Badge>
              </div>
            ))}
            {narrationStatus?.status === 'all_done' && (
              <p className="text-[11px] text-emerald-400/70 text-center">Todas as narrações geradas! Abra o editor para ouvir.</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Improvement Suggestions */}
      <Card className="bg-slate-900/50 border-cyan-800/30 text-left mx-auto max-w-2xl" data-testid="suggestions-panel">
        <CardContent className="p-4 space-y-3">
          <button
            onClick={() => setSuggestionsOpen(!suggestionsOpen)}
            className="flex items-center justify-between w-full"
            data-testid="suggestions-toggle"
          >
            <h3 className="text-sm font-semibold text-cyan-300 flex items-center gap-2">
              <Lightbulb className="w-4 h-4" /> Sugestões de Melhoria
              {suggestionsStatus === 'pending' && <Loader2 className="w-3 h-3 animate-spin text-cyan-400/60" />}
              {suggestionsStatus === 'ready' && suggestions && (
                <Badge className="bg-cyan-600/20 text-cyan-300 text-[10px]">
                  {Object.values(suggestions).flat().length} sugestões
                </Badge>
              )}
            </h3>
            {suggestionsOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>

          {suggestionsOpen && (
            <div className="space-y-4 pt-2">
              {suggestionsStatus === 'pending' && (
                <div className="flex items-center gap-2 text-xs text-cyan-400/70 py-4 justify-center">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Analisando o processo e gerando sugestões...
                </div>
              )}
              {suggestionsStatus === 'error' && (
                <div className="text-center py-4 space-y-2">
                  <p className="text-xs text-red-400">Erro ao gerar sugestões.</p>
                  <Button variant="outline" size="sm" onClick={handleRegenerateSuggestions} disabled={regenerating} className="text-xs" data-testid="retry-suggestions-btn">
                    <RefreshCw className="w-3 h-3 mr-1" /> Tentar novamente
                  </Button>
                </div>
              )}
              {suggestionsStatus === 'ready' && suggestions && (
                <>
                  <SuggestionsCategory icon={Monitor} title="Plataforma — UX" color="blue" items={suggestions.platform_ux} />
                  <SuggestionsCategory icon={Rocket} title="Plataforma — Features" color="purple" items={suggestions.platform_features} />
                  <SuggestionsCategory icon={Zap} title="Plataforma — Performance" color="amber" items={suggestions.platform_performance} />
                  <SuggestionsCategory icon={BookMarked} title="Curso — Conteúdo" color="emerald" items={suggestions.course_content} />
                  <SuggestionsCategory icon={PaintBucket} title="Curso — Design" color="pink" items={suggestions.course_design} />
                  <SuggestionsCategory icon={Target} title="Curso — Pedagogia" color="orange" items={suggestions.course_pedagogy} />
                  <div className="pt-2 flex justify-center">
                    <Button variant="outline" size="sm" onClick={handleRegenerateSuggestions} disabled={regenerating} className="text-xs border-cyan-700/50 text-cyan-400" data-testid="regenerate-suggestions-btn">
                      {regenerating ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <RefreshCw className="w-3 h-3 mr-1" />}
                      Gerar novas sugestões
                    </Button>
                  </div>
                </>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex gap-3 justify-center">
        <Button onClick={() => navigate(`/editor/${project.projectId}`)} className="bg-emerald-600 hover:bg-emerald-700" data-testid="open-editor-btn">
          <BookOpen className="w-4 h-4 mr-2" /> Abrir no Editor
        </Button>
        <Button variant="outline" onClick={() => navigate('/')} data-testid="back-dashboard-btn">
          <ArrowLeft className="w-4 h-4 mr-2" /> Dashboard
        </Button>
      </div>
    </div>
  );
}

/* ====================== EDIT MODE PANELS ====================== */

