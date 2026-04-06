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
  PaintBucket, Target, Code, ExternalLink, BookOpenCheck, Volume2, Type, Save,
} from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../../components/ui/tabs';
import { SlideTypeSwitcher, AvatarSceneMockup } from './AvatarSceneControls';

const API = getApiUrl();

export default function StoryboardPanel({ storyboard, loading, onApprove, onSubmitForApproval, config, setConfig, sessionId, companies }) {
  const [activeSlide, setActiveSlide] = useState(0);
  const [narrationSlides, setNarrationSlides] = useState({});
  const [elVoices, setElVoices] = useState([]);
  const [loadingVoices, setLoadingVoices] = useState(false);
  const [savingConfig, setSavingConfig] = useState(false);
  const [showNarrationPanel, setShowNarrationPanel] = useState(false);
  const [slideTypeOverrides, setSlideTypeOverrides] = useState({});
  const [editedSlides, setEditedSlides] = useState({});
  const [savingEdits, setSavingEdits] = useState(false);
  const [showApprovalDialog, setShowApprovalDialog] = useState(false);
  const [selectedCompanyId, setSelectedCompanyId] = useState('');

  // Initialize narration slides when storyboard loads
  useEffect(() => {
    if (storyboard?.slides) {
      const initial = {};
      storyboard.slides.forEach((s, i) => {
        initial[i] = config.narrationEnabled && !!s.narrationScript;
      });
      setNarrationSlides(initial);
      if (config.narrationEnabled) setShowNarrationPanel(true);
    }
  }, [storyboard?.slides?.length]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch voices when narration is enabled
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

  // Cost calculation - ElevenLabs Starter: $5/30,000 chars
  const COST_PER_CHAR = 5.0 / 30000.0;
  const slideCosts = useMemo(() => {
    if (!storyboard?.slides) return [];
    return storyboard.slides.map((s, i) => {
      const charCount = (s.narrationScript || '').length;
      const cost = charCount * COST_PER_CHAR;
      const enabled = !!narrationSlides[i];
      return { charCount, cost, enabled, hasScript: !!s.narrationScript };
    });
  }, [storyboard?.slides, narrationSlides, COST_PER_CHAR]);

  const totalChars = slideCosts.filter(s => s.enabled).reduce((sum, s) => sum + s.charCount, 0);
  const totalCost = slideCosts.filter(s => s.enabled).reduce((sum, s) => sum + s.cost, 0);
  const enabledCount = slideCosts.filter(s => s.enabled).length;
  const totalWithScript = slideCosts.filter(s => s.hasScript).length;

  const toggleSlide = (i) => {
    setNarrationSlides(prev => ({ ...prev, [i]: !prev[i] }));
  };

  const toggleAll = (enabled) => {
    const newSlides = {};
    storyboard.slides.forEach((s, i) => {
      newSlides[i] = enabled && !!s.narrationScript;
    });
    setNarrationSlides(newSlides);
  };

  const handleNarrationToggle = () => {
    const newEnabled = !config.narrationEnabled;
    setConfig(prev => ({ ...prev, narrationEnabled: newEnabled }));
    if (newEnabled) {
      setShowNarrationPanel(true);
      const initial = {};
      storyboard.slides.forEach((s, i) => {
        initial[i] = !!s.narrationScript;
      });
      setNarrationSlides(initial);
    } else {
      const cleared = {};
      storyboard.slides.forEach((_, i) => { cleared[i] = false; });
      setNarrationSlides(cleared);
    }
  };

  // Save narration config and approve
  const handleApprove = async () => {
    if (config.narrationEnabled && enabledCount > 0) {
      setSavingConfig(true);
      try {
        await fetch(`${API}/api/agent/sessions/${sessionId}/save-narration-config`, {
          method: 'POST',
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({
            narrationSlides,
            narrationVoiceId: config.narrationVoiceId,
            narrationEnabled: true,
          }),
        });
      } catch (e) {
        console.error('Failed to save narration config:', e);
      }
      setSavingConfig(false);
    }
    // If there are type overrides, save them to the session
    if (Object.keys(slideTypeOverrides).length > 0) {
      try {
        await fetch(`${API}/api/agent/sessions/${sessionId}/save-type-overrides`, {
          method: 'POST',
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ typeOverrides: slideTypeOverrides }),
        });
      } catch (e) {
        console.error('Failed to save type overrides:', e);
      }
    }
    onApprove();
  };

  const handleSlideTypeChange = (slideIndex, newType) => {
    setSlideTypeOverrides(prev => ({ ...prev, [slideIndex]: newType }));
  };

  const [slideScriptOverrides, setSlideScriptOverrides] = useState({});
  const [slideBgOverrides, setSlideBgOverrides] = useState({});
  const [slidePositionOverrides, setSlidePositionOverrides] = useState({});

  const handleSlideScriptChange = (slideIndex, newScript) => {
    setSlideScriptOverrides(prev => ({ ...prev, [slideIndex]: newScript }));
  };

  const handleSlideBgChange = (slideIndex, newBg) => {
    setSlideBgOverrides(prev => ({ ...prev, [slideIndex]: newBg }));
  };

  const handleSlidePositionChange = (slideIndex, newPos) => {
    setSlidePositionOverrides(prev => ({ ...prev, [slideIndex]: newPos }));
  };

  const getSlideEffectiveType = (slide, index) => slideTypeOverrides[index] ?? slide.type;

  // Text editing helpers
  const handleSlideTextEdit = (slideIdx, field, value) => {
    setEditedSlides(prev => {
      const slide = prev[slideIdx] || {};
      return { ...prev, [slideIdx]: { ...slide, [field]: value } };
    });
  };

  const handleSlideElementEdit = (slideIdx, elIdx, content) => {
    setEditedSlides(prev => {
      const slide = prev[slideIdx] || {};
      const elements = slide.elements || [];
      const existing = elements.find(e => e.index === elIdx);
      const updated = existing
        ? elements.map(e => e.index === elIdx ? { ...e, content } : e)
        : [...elements, { index: elIdx, content }];
      return { ...prev, [slideIdx]: { ...slide, elements: updated } };
    });
  };

  const hasEdits = Object.keys(editedSlides).length > 0;

  const saveTextEdits = async () => {
    if (!hasEdits || !sessionId) return;
    setSavingEdits(true);
    try {
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/update-storyboard-text`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ edits: editedSlides }),
      });
      if (res.ok) {
        toast.success('Textos salvos!');
        setEditedSlides({});
      } else {
        toast.error('Erro ao salvar textos');
      }
    } catch {
      toast.error('Erro ao salvar');
    }
    setSavingEdits(false);
  };

  const handleSubmitForApproval = async () => {
    if (!selectedCompanyId) {
      toast.error('Selecione uma empresa para enviar a aprovacao');
      return;
    }
    // Save edits first if any
    if (hasEdits) await saveTextEdits();
    if (onSubmitForApproval) {
      onSubmitForApproval(selectedCompanyId);
      setShowApprovalDialog(false);
      setSelectedCompanyId('');
    }
  };

  if (!storyboard?.slides) return null;
  const slide = storyboard.slides[activeSlide];
  const currentCost = slideCosts[activeSlide];

  return (
    <div className="space-y-4" data-testid="storyboard-panel">
      <h2 className="text-lg font-semibold flex items-center gap-2">
        <BookOpen className="w-5 h-5 text-emerald-400" /> Storyboard
      </h2>

      {/* Slide selector pills */}
      <div className="flex gap-1 flex-wrap">
        {storyboard.slides.map((s, i) => {
          const effType = getSlideEffectiveType(s, i);
          const isAvatar = s.type === 'avatar_scene' && effType === 'avatar_scene';
          const wasConverted = s.type === 'avatar_scene' && effType !== 'avatar_scene';
          return (
          <button key={i} onClick={() => setActiveSlide(i)}
            className={`px-2 py-1 rounded text-xs transition-colors relative ${
              i === activeSlide
                ? (isAvatar ? 'bg-violet-600 text-white' : 'bg-emerald-600 text-white')
                : (isAvatar ? 'bg-violet-900/50 text-violet-300 hover:bg-violet-800/50' : 'bg-slate-800 text-slate-400 hover:bg-slate-700')
            }`}
            data-testid={`storyboard-slide-btn-${i}`}
          >
            {i + 1}
            {narrationSlides[i] && config.narrationEnabled && (
              <span className="absolute -top-1 -right-1 w-2 h-2 bg-amber-400 rounded-full" />
            )}
            {wasConverted && (
              <span className="absolute -top-1 -left-1 w-2 h-2 bg-amber-400 rounded-full" />
            )}
          </button>
          );
        })}
      </div>

      {/* Current slide preview */}
      {slide && (() => {
        const effectiveType = getSlideEffectiveType(slide, activeSlide);
        const isAvatarScene = slide.type === 'avatar_scene';
        const wasConverted = effectiveType !== slide.type;
        const typeBadgeClass = effectiveType === 'avatar_scene' ? 'bg-violet-600/20 text-violet-300'
          : effectiveType === 'quiz' ? 'bg-amber-600/20 text-amber-300'
          : effectiveType === 'title' ? 'bg-blue-600/20 text-blue-300'
          : effectiveType === 'simulator' || effectiveType === 'game' ? 'bg-cyan-600/20 text-cyan-300'
          : 'bg-slate-700 text-slate-300';

        return (
        <Card className={`bg-slate-900/50 ${isAvatarScene && !wasConverted ? 'border-violet-800/30' : 'border-slate-800'}`}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Badge className={`text-xs ${typeBadgeClass}`}>{effectiveType}</Badge>
              <span className="text-slate-500">Slide {activeSlide + 1}:</span>
              <input
                type="text"
                value={(editedSlides[activeSlide]?.title) ?? slide.title ?? ''}
                onChange={e => handleSlideTextEdit(activeSlide, 'title', e.target.value)}
                className="bg-transparent border-b border-transparent hover:border-slate-600 focus:border-amber-500 focus:outline-none text-sm font-semibold text-white flex-1 min-w-0 px-1"
                data-testid={`storyboard-slide-title-input-${activeSlide}`}
              />
              {editedSlides[activeSlide] && <Badge className="text-[9px] bg-amber-600/20 text-amber-300 px-1.5 py-0">Editado</Badge>}
              {wasConverted && (
                <Badge className="text-[9px] bg-amber-600/20 text-amber-300 px-1.5 py-0">Tipo alterado</Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* Avatar scene mockup (when type is still avatar_scene) */}
            {isAvatarScene && effectiveType === 'avatar_scene' && slide.avatarScene && (
              <AvatarSceneMockup
                narrationScript={slideScriptOverrides[activeSlide] ?? slide.avatarScene.narrationScript ?? slide.narrationScript}
                backgroundDescription={slideBgOverrides[activeSlide] ?? slide.avatarScene.backgroundPrompt ?? slide.avatarScene.backgroundDescription}
                avatarPosition={slidePositionOverrides[activeSlide] ?? slide.avatarScene.avatarPosition ?? 'left'}
                editable
                onScriptChange={(newScript) => handleSlideScriptChange(activeSlide, newScript)}
                onBackgroundChange={(newBg) => handleSlideBgChange(activeSlide, newBg)}
                onPositionChange={(newPos) => handleSlidePositionChange(activeSlide, newPos)}
              />
            )}

            {/* Conversion notice */}
            {wasConverted && (
              <div className="text-xs text-amber-300/80 bg-amber-950/20 rounded-md p-2.5 border border-amber-800/20">
                Este slide será gerado como <strong>{effectiveType === 'content' ? 'conteúdo textual rico' : effectiveType === 'simulator' ? 'simulador interativo' : effectiveType === 'game' ? 'jogo educativo' : effectiveType === 'quiz' ? 'quiz' : effectiveType}</strong> ao invés de cena com avatar.
              </div>
            )}

            {/* Regular slide content preview - EDITABLE */}
            {(!isAvatarScene || wasConverted) && (
              <div className="space-y-2">
                {slide.elements?.map((el, elIdx) => (
                  <div key={elIdx}>
                    <label className="text-[10px] text-slate-500 mb-0.5 block">Conteudo {elIdx + 1}</label>
                    <Textarea
                      value={
                        (editedSlides[activeSlide]?.elements?.find(e => e.index === elIdx)?.content) ??
                        (el.content || '')
                      }
                      onChange={e => handleSlideElementEdit(activeSlide, elIdx, e.target.value)}
                      className="bg-slate-800/70 border-slate-700 text-sm text-white min-h-[60px] focus:border-emerald-500"
                      data-testid={`storyboard-element-input-${activeSlide}-${elIdx}`}
                    />
                  </div>
                ))}
              </div>
            )}

            {/* Also show content for avatar scenes - EDITABLE */}
            {isAvatarScene && !wasConverted && slide.elements?.length > 0 && (
              <div className="space-y-2">
                {slide.elements?.map((el, elIdx) => (
                  <div key={elIdx}>
                    <label className="text-[10px] text-slate-500 mb-0.5 block">Conteudo {elIdx + 1}</label>
                    <Textarea
                      value={
                        (editedSlides[activeSlide]?.elements?.find(e => e.index === elIdx)?.content) ??
                        (el.content || '')
                      }
                      onChange={e => handleSlideElementEdit(activeSlide, elIdx, e.target.value)}
                      className="bg-slate-800/70 border-slate-700 text-sm text-white min-h-[60px] focus:border-violet-500"
                      data-testid={`storyboard-avatar-element-input-${activeSlide}-${elIdx}`}
                    />
                  </div>
                ))}
              </div>
            )}

            {/* Type switcher for avatar_scene slides */}
            {isAvatarScene && (
              <SlideTypeSwitcher
                currentType={effectiveType}
                onChange={(newType) => handleSlideTypeChange(activeSlide, newType)}
              />
            )}

            {/* Narration script for current slide */}
            {slide.narrationScript && (
              <div className={`rounded-lg p-3 border ${narrationSlides[activeSlide] && config.narrationEnabled ? 'bg-amber-900/15 border-amber-700/30' : 'bg-slate-800/50 border-slate-700/30'}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-slate-400 flex items-center gap-1">
                    <Volume2 className="w-3 h-3" /> Roteiro de Narração
                  </span>
                  {config.narrationEnabled && (
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-slate-500">{currentCost?.charCount || 0} chars</span>
                      <button
                        onClick={() => toggleSlide(activeSlide)}
                        className={`w-8 h-4 rounded-full transition-colors relative ${narrationSlides[activeSlide] ? 'bg-amber-500' : 'bg-slate-700'}`}
                        data-testid={`narration-slide-toggle-${activeSlide}`}
                      >
                        <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${narrationSlides[activeSlide] ? 'translate-x-4' : 'translate-x-0.5'}`} />
                      </button>
                    </div>
                  )}
                </div>
                <Textarea
                  value={
                    (editedSlides[activeSlide]?.narrationScript) ??
                    slide.narrationScript
                  }
                  onChange={e => handleSlideTextEdit(activeSlide, 'narrationScript', e.target.value)}
                  className="bg-transparent border-0 text-sm text-slate-300 p-0 min-h-[40px] focus:ring-0 resize-none"
                  data-testid={`storyboard-narration-input-${activeSlide}`}
                />
              </div>
            )}

            {slide.quizQuestions?.length > 0 && (
              <div className="bg-amber-900/10 rounded p-3 border border-amber-800/20">
                <span className="text-xs text-amber-400 block mb-2">Perguntas do Quiz:</span>
                {slide.quizQuestions.map((q, qi) => (
                  <div key={qi} className="mb-2">
                    <p className="text-sm font-medium text-slate-200">{qi + 1}. {q.text}</p>
                    <div className="ml-4 mt-1 space-y-1">
                      {q.alternatives?.map((a, ai) => (
                        <p key={ai} className={`text-xs ${a.isCorrect ? 'text-emerald-400' : 'text-slate-400'}`}>
                          {a.isCorrect ? '\u2713' : '\u25CB'} {a.text}
                        </p>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
        );
      })()}

      {/* Slide navigation */}
      <div className="flex justify-between items-center">
        <Button variant="outline" size="sm" onClick={() => setActiveSlide(Math.max(0, activeSlide - 1))} disabled={activeSlide === 0}>
          <ArrowLeft className="w-4 h-4 mr-1" /> Anterior
        </Button>
        <span className="text-xs text-slate-400">{activeSlide + 1} / {storyboard.slides.length}</span>
        <Button variant="outline" size="sm" onClick={() => setActiveSlide(Math.min(storyboard.slides.length - 1, activeSlide + 1))} disabled={activeSlide >= storyboard.slides.length - 1}>
          Próxima <ArrowRight className="w-4 h-4 ml-1" />
        </Button>
      </div>

      {/* ===== NARRATION CONTROL PANEL ===== */}
      <Card className="bg-slate-900/50 border-slate-800" data-testid="narration-control-panel">
        <CardContent className="p-4 space-y-3">
          {/* Header with global toggle */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Volume2 className="w-4 h-4 text-amber-400" />
              <span className="text-sm font-medium">Narração por Slide</span>
              <Badge className="bg-amber-600/20 text-amber-300 text-[10px]">ElevenLabs</Badge>
            </div>
            <button
              onClick={handleNarrationToggle}
              className={`w-10 h-5 rounded-full transition-colors relative ${config.narrationEnabled ? 'bg-amber-500' : 'bg-slate-700'}`}
              data-testid="storyboard-narration-global-toggle"
            >
              <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${config.narrationEnabled ? 'translate-x-5' : 'translate-x-0.5'}`} />
            </button>
          </div>

          {config.narrationEnabled && (
            <>
              {/* Voice selector */}
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium">Voz</label>
                {loadingVoices ? (
                  <div className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="w-3 h-3 animate-spin" /> Carregando vozes...</div>
                ) : (
                  <div className="flex gap-1.5 flex-wrap max-h-24 overflow-y-auto">
                    {elVoices.slice(0, 20).map(v => (
                      <button
                        key={v.voice_id}
                        onClick={() => setConfig(prev => ({ ...prev, narrationVoiceId: v.voice_id }))}
                        className={`flex items-center gap-1 px-2 py-1 rounded-md border text-[11px] transition-all ${
                          config.narrationVoiceId === v.voice_id
                            ? 'border-amber-500 bg-amber-600/10 text-amber-300'
                            : 'border-slate-700/50 text-slate-400 hover:border-amber-500/30'
                        }`}
                        data-testid={`storyboard-voice-${v.voice_id}`}
                      >
                        <span className="font-medium">{v.name}</span>
                        {v.gender && <span className="text-slate-500 text-[10px]">{v.gender}</span>}
                        {v.preview_url && (
                          <span
                            role="button"
                            onClick={(e) => { e.stopPropagation(); new Audio(v.preview_url).play(); }}
                            className="text-amber-400 hover:text-amber-300 cursor-pointer ml-0.5"
                          >
                            <Play className="w-2.5 h-2.5" />
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
                {!config.narrationVoiceId && (
                  <p className="text-[10px] text-amber-400/70 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" /> Selecione uma voz.
                  </p>
                )}
              </div>

              {/* Select all / deselect all */}
              <div className="flex items-center justify-between border-t border-slate-800 pt-2">
                <span className="text-xs text-slate-400">
                  {enabledCount} de {totalWithScript} slides com narração
                </span>
                <div className="flex gap-2">
                  <button onClick={() => toggleAll(true)} className="text-[10px] text-amber-400 hover:text-amber-300 underline" data-testid="narration-select-all">
                    Selecionar todos
                  </button>
                  <button onClick={() => toggleAll(false)} className="text-[10px] text-slate-500 hover:text-slate-300 underline" data-testid="narration-deselect-all">
                    Desmarcar todos
                  </button>
                </div>
              </div>

              {/* Per-slide list */}
              <div className="space-y-1 max-h-48 overflow-y-auto pr-1" data-testid="narration-slides-list">
                {storyboard.slides.map((s, i) => {
                  const sc = slideCosts[i];
                  if (!sc?.hasScript) return null;
                  return (
                    <div
                      key={i}
                      className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-all cursor-pointer ${
                        sc.enabled
                          ? 'border-amber-500/40 bg-amber-900/10'
                          : 'border-slate-800 bg-slate-800/30 opacity-60'
                      }`}
                      onClick={() => { toggleSlide(i); setActiveSlide(i); }}
                      data-testid={`narration-slide-row-${i}`}
                    >
                      <Checkbox
                        checked={sc.enabled}
                        onCheckedChange={() => toggleSlide(i)}
                        className="data-[state=checked]:bg-amber-500 data-[state=checked]:border-amber-500"
                      />
                      <span className={`font-medium flex-1 truncate ${i === activeSlide ? 'text-amber-200' : 'text-slate-300'}`}>
                        {i + 1}. {s.title}
                      </span>
                      <span className="text-slate-500 tabular-nums">{sc.charCount} chars</span>
                      <span className="text-amber-400/80 tabular-nums w-14 text-right">${sc.cost.toFixed(4)}</span>
                    </div>
                  );
                })}
              </div>

              {/* Cost summary */}
              <div className="bg-slate-800/60 rounded-lg p-3 border border-amber-800/20" data-testid="narration-cost-summary">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[10px] text-slate-400">Plano Starter ElevenLabs</p>
                    <p className="text-xs text-slate-500">$5 / 30.000 caracteres por mês</p>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold text-amber-300" data-testid="narration-total-cost">${totalCost.toFixed(4)}</p>
                    <p className="text-[10px] text-slate-500">{totalChars.toLocaleString()} caracteres</p>
                  </div>
                </div>
                {totalChars > 0 && (
                  <div className="mt-2">
                    <div className="w-full bg-slate-700 rounded-full h-1.5">
                      <div
                        className="bg-amber-500 h-1.5 rounded-full transition-all"
                        style={{ width: `${Math.min((totalChars / 30000) * 100, 100)}%` }}
                      />
                    </div>
                    <p className="text-[10px] text-slate-500 mt-1">
                      {((totalChars / 30000) * 100).toFixed(1)}% da cota mensal Starter
                    </p>
                  </div>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Save edits button */}
      {hasEdits && (
        <Button
          onClick={saveTextEdits}
          disabled={savingEdits}
          className="w-full bg-blue-600 hover:bg-blue-700"
          data-testid="save-storyboard-text-edits"
        >
          {savingEdits ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Pencil className="w-4 h-4 mr-1" />}
          Salvar Edicoes de Texto ({Object.keys(editedSlides).length} slides)
        </Button>
      )}

      {/* Approve button - direct to media config */}
      <Button
        onClick={handleApprove}
        disabled={loading || savingConfig || (config.narrationEnabled && !config.narrationVoiceId && enabledCount > 0)}
        className="w-full bg-emerald-600 hover:bg-emerald-700"
        data-testid="approve-storyboard-btn"
      >
        {(loading || savingConfig) ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Play className="w-4 h-4 mr-1" />}
        {savingConfig ? 'Salvando configuracao...' : 'Aprovar e Configurar Midia'}
      </Button>

      {/* Submit for approval button - opens company selector */}
      {onSubmitForApproval && (
        <Button
          onClick={() => setShowApprovalDialog(true)}
          disabled={loading || savingConfig || savingEdits}
          variant="outline"
          className="w-full border-amber-700 text-amber-300 hover:bg-amber-900/20"
          data-testid="submit-for-approval-btn"
        >
          <Send className="w-4 h-4 mr-1" />
          Enviar para Aprovacao
        </Button>
      )}

      {/* Company selection dialog for approval */}
      {showApprovalDialog && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" data-testid="approval-company-dialog">
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-md mx-4 space-y-4">
            <h3 className="text-base font-semibold flex items-center gap-2">
              <Send className="w-4 h-4 text-amber-400" />
              Enviar para Aprovacao
            </h3>
            <p className="text-sm text-slate-400">
              Selecione a empresa cujo aprovador ira revisar este storyboard:
            </p>
            <select
              value={selectedCompanyId}
              onChange={e => setSelectedCompanyId(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white focus:border-amber-500 focus:outline-none"
              data-testid="approval-company-select"
            >
              <option value="">-- Selecione a Empresa --</option>
              {(companies || []).map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <div className="flex gap-2 pt-2">
              <Button
                onClick={handleSubmitForApproval}
                disabled={!selectedCompanyId || savingEdits}
                className="flex-1 bg-amber-600 hover:bg-amber-700"
                data-testid="confirm-submit-approval"
              >
                <Send className="w-4 h-4 mr-1" /> Enviar
              </Button>
              <Button
                variant="outline"
                onClick={() => { setShowApprovalDialog(false); setSelectedCompanyId(''); }}
                className="flex-1"
              >
                Cancelar
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


const GRADIENT_DIRECTIONS = [
  { id: 'to right', label: '→' },
  { id: 'to left', label: '←' },
  { id: 'to bottom', label: '↓' },
  { id: 'to top', label: '↑' },
  { id: 'to bottom right', label: '↘' },
  { id: 'to bottom left', label: '↙' },
  { id: 'to top right', label: '↗' },
  { id: 'to top left', label: '↖' },
];

