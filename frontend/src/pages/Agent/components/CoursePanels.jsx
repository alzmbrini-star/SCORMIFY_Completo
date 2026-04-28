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
import { SlideTypeSwitcher, AvatarSceneMockup } from './AvatarSceneControls';

const API = getApiUrl();

/* ─── Avatar Preview Card ─── */
function AvatarPreviewCard({ avatar, ...props }) {
  const [showVideo, setShowVideo] = useState(false);
  const videoRef = useRef(null);

  if (!avatar) return null;

  return (
    <div className="rounded-lg bg-violet-950/40 border border-violet-700/30 overflow-hidden" {...props}>
      <div className="relative">
        {showVideo && avatar.preview_video_url ? (
          <video
            ref={videoRef}
            src={avatar.preview_video_url}
            autoPlay
            loop
            muted
            playsInline
            className="w-full h-40 object-cover"
            onError={() => setShowVideo(false)}
            data-testid="avatar-preview-video"
          />
        ) : (
          <img
            src={avatar.preview_image_url}
            alt={avatar.avatar_name}
            className="w-full h-40 object-cover"
            onError={(e) => { e.target.style.display = 'none'; }}
            data-testid="avatar-preview-image"
          />
        )}
        {/* Toggle video/image button */}
        {avatar.preview_video_url && (
          <button
            onClick={() => setShowVideo(!showVideo)}
            className="absolute bottom-2 right-2 flex items-center gap-1 px-2 py-1 rounded-md bg-black/60 backdrop-blur-sm text-[10px] text-white/90 hover:bg-violet-600/60 transition-colors"
            data-testid="avatar-toggle-video-btn"
          >
            {showVideo ? (
              <><Eye className="w-3 h-3" /> Foto</>
            ) : (
              <><Play className="w-3 h-3" /> Ver Animado</>
            )}
          </button>
        )}
      </div>
      <div className="p-2.5 flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-violet-500 shrink-0" />
        <p className="text-xs text-violet-200 font-medium">{avatar.avatar_name}</p>
        <Badge className="text-[8px] px-1.5 py-0 bg-violet-600/20 text-violet-300 ml-auto">{avatar.gender}</Badge>
      </div>
    </div>
  );
}

/* ─── Voice Option Row ─── */
function VoiceOptionRow({ voice, isSelected, onSelect }) {
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef(null);

  const handlePlay = (e) => {
    e.stopPropagation();
    if (!voice.preview_audio) return;
    if (playing && audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setPlaying(false);
      return;
    }
    const audio = new Audio(voice.preview_audio);
    audioRef.current = audio;
    audio.play().catch(() => {});
    setPlaying(true);
    audio.onended = () => setPlaying(false);
    audio.onerror = () => setPlaying(false);
  };

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  return (
    <button
      onClick={onSelect}
      className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-all text-left ${
        isSelected
          ? 'border-violet-500 bg-violet-600/10 text-violet-300'
          : 'border-slate-700/50 text-slate-400 hover:border-violet-500/30'
      }`}
      data-testid={`voice-option-${voice.voice_id}`}
    >
      <Volume2 className={`w-3 h-3 shrink-0 ${isSelected ? 'text-violet-400' : 'text-slate-500'}`} />
      <span className="font-medium truncate">{voice.country_flag || ''} {voice.name}</span>
      <span className="text-[10px] text-slate-500 shrink-0">{voice.gender}</span>
      {voice.language_code && (
        <Badge className="text-[8px] px-1 py-0 bg-slate-800 text-slate-400 shrink-0">{voice.language_code}</Badge>
      )}
      {voice.preview_audio && (
        <span
          role="button"
          onClick={handlePlay}
          className={`ml-auto shrink-0 p-1 rounded-full transition-colors ${
            playing ? 'bg-violet-500/30 text-violet-300' : 'text-violet-400/60 hover:text-violet-300 hover:bg-violet-500/10'
          }`}
          data-testid={`play-voice-${voice.voice_id}`}
          title="Ouvir preview da voz"
        >
          {playing ? (
            <span className="flex items-center justify-center w-3.5 h-3.5">
              <span className="w-1 h-3 bg-violet-300 rounded-sm mx-px" />
              <span className="w-1 h-3 bg-violet-300 rounded-sm mx-px" />
            </span>
          ) : (
            <Play className="w-3.5 h-3.5" />
          )}
        </span>
      )}
    </button>
  );
}

/* ─── Voice Preview Card ─── */
function VoicePreviewCard({ voice, ...props }) {
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef(null);

  const handlePlay = () => {
    if (!voice.preview_audio) return;
    if (playing && audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setPlaying(false);
      return;
    }
    const audio = new Audio(voice.preview_audio);
    audioRef.current = audio;
    audio.play().catch(() => {});
    setPlaying(true);
    audio.onended = () => setPlaying(false);
    audio.onerror = () => setPlaying(false);
  };

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  if (!voice) return null;

  return (
    <div className="rounded-lg bg-violet-950/40 border border-violet-700/30 p-3" {...props}>
      <div className="flex items-center gap-3">
        <button
          onClick={handlePlay}
          disabled={!voice.preview_audio}
          className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 transition-all ${
            playing
              ? 'bg-violet-500 text-white shadow-lg shadow-violet-500/30'
              : voice.preview_audio
                ? 'bg-violet-600/20 text-violet-300 hover:bg-violet-500/30'
                : 'bg-slate-800 text-slate-600 cursor-not-allowed'
          }`}
          data-testid="selected-voice-play-btn"
        >
          {playing ? (
            <span className="flex items-center gap-0.5">
              <span className="w-1 h-4 bg-white rounded-sm animate-pulse" />
              <span className="w-1 h-4 bg-white rounded-sm animate-pulse" style={{ animationDelay: '150ms' }} />
            </span>
          ) : (
            <Play className="w-4 h-4 ml-0.5" />
          )}
        </button>
        <div className="flex-1 min-w-0">
          <p className="text-xs text-violet-200 font-medium">{voice.country_flag || ''} {voice.name}</p>
          <p className="text-[10px] text-violet-400/70">{voice.gender} {voice.language_code ? `\u2022 ${voice.language_code}` : ''}</p>
        </div>
        <Badge className="text-[8px] px-1.5 py-0 bg-emerald-600/20 text-emerald-300 shrink-0">Selecionada</Badge>
      </div>
      {!voice.preview_audio && (
        <p className="text-[10px] text-slate-500 mt-2">Preview de áudio não disponível para esta voz.</p>
      )}
    </div>
  );
}

/* ─── Test Combination Player ─── */
function TestCombinationPlayer({ avatarId, voiceId, avatarName, voiceName }) {
  const [state, setState] = useState('idle'); // idle | generating | polling | ready | error
  const [videoUrl, setVideoUrl] = useState(null);
  const [videoId, setVideoId] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const pollRef = useRef(null);

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  // Reset when avatar/voice changes
  useEffect(() => {
    setState('idle');
    setVideoUrl(null);
    setVideoId(null);
    setErrorMsg('');
    if (pollRef.current) clearInterval(pollRef.current);
  }, [avatarId, voiceId]);

  const handleGenerate = async () => {
    if (!avatarId || !voiceId) return;
    setState('generating');
    setErrorMsg('');
    setVideoUrl(null);

    try {
      const res = await fetch(`${API}/api/heygen/test-combination`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ avatar_id: avatarId, voice_id: voiceId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Falha ao gerar vídeo de teste');
      }
      const data = await res.json();
      setVideoId(data.video_id);
      setState('polling');

      // Poll for status
      pollRef.current = setInterval(async () => {
        try {
          const sRes = await fetch(`${API}/api/heygen/video-status/${data.video_id}`, { headers: authHeaders() });
          if (!sRes.ok) return;
          const sData = await sRes.json();
          if (sData.status === 'completed' && sData.video_url) {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setVideoUrl(sData.video_url);
            setState('ready');
          } else if (sData.status === 'failed') {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setState('error');
            setErrorMsg('O vídeo de teste falhou na geração.');
          }
        } catch {}
      }, 4000);
    } catch (e) {
      setState('error');
      setErrorMsg(e.message);
    }
  };

  const isProcessing = state === 'generating' || state === 'polling';

  return (
    <div className="rounded-lg border border-dashed border-violet-600/30 bg-violet-950/20 p-3 space-y-3" data-testid="test-combination-section">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-violet-300">Testar Combinação</p>
          <p className="text-[10px] text-slate-400">Gere um mini vídeo para validar avatar + voz</p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={!avatarId || !voiceId || isProcessing}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            isProcessing
              ? 'bg-violet-600/30 text-violet-300 cursor-wait'
              : !avatarId || !voiceId
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                : 'bg-violet-600 text-white hover:bg-violet-500 shadow-md shadow-violet-500/20'
          }`}
          data-testid="test-combination-btn"
        >
          {isProcessing ? (
            <><Loader2 className="w-3 h-3 animate-spin" /> Gerando...</>
          ) : (
            <><Video className="w-3 h-3" /> Testar</>
          )}
        </button>
      </div>

      {isProcessing && (
        <div className="flex items-center gap-2 text-[10px] text-violet-400 animate-pulse" data-testid="test-combination-loading">
          <Loader2 className="w-3 h-3 animate-spin" />
          {state === 'generating' ? 'Enviando para HeyGen...' : 'Processando vídeo... Isso pode levar até 2 minutos.'}
        </div>
      )}

      {state === 'error' && (
        <p className="text-[10px] text-red-400" data-testid="test-combination-error">{errorMsg}</p>
      )}

      {state === 'ready' && videoUrl && (
        <div className="rounded-lg overflow-hidden border border-violet-700/30" data-testid="test-combination-video">
          <video
            src={videoUrl}
            controls
            autoPlay
            className="w-full max-h-56"
            style={{ background: '#000' }}
          />
          <div className="px-2.5 py-1.5 bg-slate-900/50 flex items-center gap-2 text-[10px] text-violet-300">
            <Check className="w-3 h-3 text-emerald-400" />
            Preview gerado com sucesso
          </div>
        </div>
      )}
    </div>
  );
}


export function CourseReviewPanel({ course, analysis, loading, selectedImprovements, toggleImprovement, selectedNewSlides = [], toggleNewSlide, onApply, onTypeOverride, onScriptOverride }) {
  const [avatarLimit, setAvatarLimit] = useState(3);
  const [avatarSettingsOpen, setAvatarSettingsOpen] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [typeOverrides, setTypeOverrides] = useState({});
  const [scriptOverrides, setScriptOverrides] = useState({});
  const [bgOverrides, setBgOverrides] = useState({});
  const [positionOverrides, setPositionOverrides] = useState({});
  const [defaultAvatarId, setDefaultAvatarId] = useState('');
  const [defaultVoiceId, setDefaultVoiceId] = useState('');
  const [heygenAvatars, setHeygenAvatars] = useState([]);
  const [heygenVoices, setHeygenVoices] = useState([]);
  const [loadingAvatars, setLoadingAvatars] = useState(false);
  const [loadingVoices, setLoadingVoices] = useState(false);
  // Filter chips: 'all' or one of the improvement type keys
  const [categoryFilter, setCategoryFilter] = useState('all');

  const handleTypeChange = (impIndex, newType) => {
    setTypeOverrides(prev => ({ ...prev, [impIndex]: newType }));
    if (onTypeOverride) onTypeOverride(impIndex, newType);
  };

  const handleScriptChange = (impIndex, newScript) => {
    setScriptOverrides(prev => ({ ...prev, [impIndex]: newScript }));
    if (onScriptOverride) onScriptOverride(impIndex, { narrationScript: newScript });
  };

  const handleBgChange = (impIndex, newBg) => {
    setBgOverrides(prev => ({ ...prev, [impIndex]: newBg }));
    if (onScriptOverride) onScriptOverride(impIndex, { backgroundDescription: newBg });
  };

  const handlePositionChange = (impIndex, newPos) => {
    setPositionOverrides(prev => ({ ...prev, [impIndex]: newPos }));
    if (onScriptOverride) onScriptOverride(impIndex, { avatarPosition: newPos });
  };

  const getEffectiveType = (imp, index) => typeOverrides[index] ?? imp.type;

  // Load avatar settings
  useEffect(() => {
    if (!course?.id) return;
    fetch(`${API}/api/agent/projects/${course.id}/avatar-settings`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          if (data.maxScenes) setAvatarLimit(data.maxScenes);
          if (data.defaultAvatarId) setDefaultAvatarId(data.defaultAvatarId);
          if (data.defaultVoiceId) setDefaultVoiceId(data.defaultVoiceId);
        }
      })
      .catch(() => {});
  }, [course?.id]);

  // Load HeyGen avatars when settings open
  useEffect(() => {
    if (!avatarSettingsOpen || heygenAvatars.length > 0) return;
    setLoadingAvatars(true);
    fetch(`${API}/api/heygen/avatars?limit=50`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : { avatars: [] })
      .then(data => setHeygenAvatars(data.avatars || []))
      .catch(() => {})
      .finally(() => setLoadingAvatars(false));
  }, [avatarSettingsOpen, heygenAvatars.length]);

  // Load HeyGen voices when settings open (prioritize PT-BR)
  useEffect(() => {
    if (!avatarSettingsOpen || heygenVoices.length > 0) return;
    setLoadingVoices(true);
    fetch(`${API}/api/heygen/voices?language=portuguese`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : { voices: [] })
      .then(data => {
        const voices = data.voices || [];
        // Sort: PT-BR first, then other Portuguese, then rest
        voices.sort((a, b) => {
          const aIsBR = a.language_code === 'pt-BR' ? 0 : a.language_code?.startsWith('pt') ? 1 : 2;
          const bIsBR = b.language_code === 'pt-BR' ? 0 : b.language_code?.startsWith('pt') ? 1 : 2;
          return aIsBR - bIsBR;
        });
        setHeygenVoices(voices);
      })
      .catch(() => {})
      .finally(() => setLoadingVoices(false));
  }, [avatarSettingsOpen, heygenVoices.length]);

  const saveAllSettings = async (overrides = {}) => {
    setSavingSettings(true);
    const payload = {
      maxScenes: overrides.maxScenes ?? avatarLimit,
      defaultAvatarId: (overrides.defaultAvatarId ?? defaultAvatarId) || null,
      defaultVoiceId: (overrides.defaultVoiceId ?? defaultVoiceId) || null,
    };
    try {
      await fetch(`${API}/api/agent/projects/${course.id}/avatar-settings`, {
        method: 'PUT',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload),
      });
    } catch { /* ignore */ }
    finally { setSavingSettings(false); }
  };

  const handleAvatarSelect = (val) => {
    setDefaultAvatarId(val);
    saveAllSettings({ defaultAvatarId: val });
  };

  const handleVoiceSelect = (val) => {
    setDefaultVoiceId(val);
    saveAllSettings({ defaultVoiceId: val });
  };

  const handleLimitChange = (val) => {
    setAvatarLimit(val);
    saveAllSettings({ maxScenes: val });
  };

  if (!course) return null;
  const priorityColors = { alta: 'text-red-400 border-red-800/40', media: 'text-amber-400 border-amber-800/40', baixa: 'text-blue-400 border-blue-800/40' };
  const typeLabels = { content: 'Conteúdo', structure: 'Estrutura', quiz: 'Quiz', narration: 'Narração', visual: 'Visual', simulator: 'Simulador', avatar_scene: 'Cena com Avatar', scenario: 'Cenário Interativo', visual_summary: 'Resumo Visual', reinforcement: 'Reforço', imagem_simples: 'Imagem (econômica)', imagem_premium: 'Imagem Premium' };
  const typeIcons = { content: Type, structure: Layers, quiz: Target, narration: Volume2, visual: Palette, simulator: Code, avatar_scene: Video, scenario: Monitor, visual_summary: BarChart3, reinforcement: Lightbulb, imagem_simples: Image, imagem_premium: ImagePlus };

  return (
    <div className="space-y-4" data-testid="course-review-panel">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold flex items-center gap-2"><Brain className="w-5 h-5 text-blue-400" /> Análise: {course.name}</h2>
      </div>

      {loading && !analysis && (
        <Card className="bg-slate-900/50 border-slate-800">
          <CardContent className="p-8 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-blue-400 mx-auto mb-3" />
            <p className="text-sm text-slate-300">Analisando o curso com IA...</p>
          </CardContent>
        </Card>
      )}

      {analysis && (
        <div className="space-y-4">
          {/* Score Card */}
          <Card className="bg-slate-900/50 border-slate-800">
            <CardContent className="p-4">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-xl bg-blue-600/10 flex items-center justify-center">
                  <span className="text-2xl font-bold text-blue-400">{analysis.overallScore}</span>
                  <span className="text-xs text-slate-400">/10</span>
                </div>
                <div className="flex-1">
                  <h3 className="font-medium text-sm mb-1">Avaliação Geral</h3>
                  {analysis.strengths?.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {analysis.strengths.map((s, i) => (
                        <Badge key={i} className="bg-emerald-600/20 text-emerald-300 text-[10px]">
                          <Star className="w-2 h-2 mr-1" />{s}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Avatar scene settings */}
          <Card className="bg-violet-950/20 border-violet-800/20">
            <CardContent className="p-3">
              <button
                onClick={() => setAvatarSettingsOpen(!avatarSettingsOpen)}
                className="w-full flex items-center justify-between text-left"
                data-testid="avatar-settings-toggle"
              >
                <div className="flex items-center gap-2">
                  <Video className="w-4 h-4 text-violet-400" />
                  <span className="text-sm font-medium text-violet-200">Configurações de Avatar</span>
                  {defaultAvatarId && (
                    <Badge className="text-[8px] bg-emerald-600/20 text-emerald-300 px-1.5 py-0">Configurado</Badge>
                  )}
                  {!defaultAvatarId && (
                    <Badge className="text-[8px] bg-amber-600/20 text-amber-300 px-1.5 py-0">Sem avatar</Badge>
                  )}
                </div>
                {avatarSettingsOpen ? <ChevronUp className="w-4 h-4 text-violet-400" /> : <ChevronDown className="w-4 h-4 text-violet-400" />}
              </button>
              {avatarSettingsOpen && (
                <div className="mt-3 space-y-4 pt-3 border-t border-violet-800/20">
                  {/* Avatar HeyGen selector with visual grid */}
                  <div className="space-y-2">
                    <label className="text-xs text-violet-300 font-medium">Avatar HeyGen</label>
                    {loadingAvatars ? (
                      <div className="flex items-center gap-2 text-xs text-violet-400">
                        <Loader2 className="w-3 h-3 animate-spin" /> Carregando avatares...
                      </div>
                    ) : heygenAvatars.length > 0 ? (
                      <div className="space-y-3">
                        {/* Avatar grid */}
                        <div className="grid grid-cols-4 gap-2 max-h-52 overflow-y-auto pr-1" data-testid="avatar-grid">
                          {heygenAvatars.map(a => (
                            <button
                              key={a.avatar_id}
                              onClick={() => handleAvatarSelect(a.avatar_id)}
                              className={`relative rounded-lg border-2 overflow-hidden transition-all group ${
                                defaultAvatarId === a.avatar_id
                                  ? 'border-violet-500 ring-1 ring-violet-500/30 shadow-lg shadow-violet-500/10'
                                  : 'border-slate-700/50 hover:border-violet-500/40'
                              }`}
                              data-testid={`avatar-option-${a.avatar_id}`}
                            >
                              {a.preview_image_url ? (
                                <img src={a.preview_image_url} alt={a.avatar_name} className="w-full h-20 object-cover" />
                              ) : (
                                <div className="w-full h-20 bg-slate-800 flex items-center justify-center">
                                  <UserCircle className="w-8 h-8 text-slate-600" />
                                </div>
                              )}
                              <p className="text-[9px] text-center truncate px-1 py-0.5 bg-slate-900/80">{a.avatar_name}</p>
                              {defaultAvatarId === a.avatar_id && (
                                <div className="absolute top-1 right-1 bg-violet-500 rounded-full p-0.5">
                                  <Check className="w-2.5 h-2.5 text-white" />
                                </div>
                              )}
                            </button>
                          ))}
                        </div>
                        {/* Selected avatar large preview */}
                        {defaultAvatarId && (() => {
                          const sel = heygenAvatars.find(a => a.avatar_id === defaultAvatarId);
                          if (!sel) return null;
                          return (
                            <AvatarPreviewCard
                              avatar={sel}
                              data-testid="selected-avatar-preview"
                            />
                          );
                        })()}
                      </div>
                    ) : (
                      <p className="text-[10px] text-amber-300/70">Nenhum avatar disponível. Verifique sua chave API HeyGen.</p>
                    )}
                  </div>

                  {/* HeyGen voice selector with audio preview */}
                  <div className="space-y-2">
                    <label className="text-xs text-violet-300 font-medium">Voz HeyGen</label>
                    {loadingVoices ? (
                      <div className="flex items-center gap-2 text-xs text-violet-400">
                        <Loader2 className="w-3 h-3 animate-spin" /> Carregando vozes...
                      </div>
                    ) : heygenVoices.length > 0 ? (
                      <div className="space-y-2">
                        <div className="space-y-1 max-h-44 overflow-y-auto pr-1" data-testid="voice-list">
                          {heygenVoices.map(v => (
                            <VoiceOptionRow
                              key={v.voice_id}
                              voice={v}
                              isSelected={defaultVoiceId === v.voice_id}
                              onSelect={() => handleVoiceSelect(v.voice_id)}
                            />
                          ))}
                        </div>
                        {/* Selected voice preview card */}
                        {defaultVoiceId && (() => {
                          const sel = heygenVoices.find(v => v.voice_id === defaultVoiceId);
                          if (!sel) return null;
                          return (
                            <VoicePreviewCard voice={sel} data-testid="selected-voice-preview" />
                          );
                        })()}
                      </div>
                    ) : (
                      <p className="text-[10px] text-amber-300/70">Nenhuma voz disponível. Verifique sua chave API HeyGen.</p>
                    )}
                  </div>

                  {/* Test Combination */}
                  <TestCombinationPlayer
                    avatarId={defaultAvatarId}
                    voiceId={defaultVoiceId}
                    avatarName={heygenAvatars.find(a => a.avatar_id === defaultAvatarId)?.avatar_name}
                    voiceName={heygenVoices.find(v => v.voice_id === defaultVoiceId)?.name}
                  />

                  {/* Max scenes */}
                  <div className="flex items-center justify-between">
                    <label className="text-xs text-violet-300">Máximo de cenas com avatar</label>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        min={0}
                        max={20}
                        value={avatarLimit}
                        onChange={(e) => handleLimitChange(parseInt(e.target.value) || 0)}
                        className="w-16 h-7 text-xs bg-violet-950/50 border-violet-800/40 text-center"
                        data-testid="avatar-limit-input"
                      />
                      {savingSettings && <Loader2 className="w-3 h-3 animate-spin text-violet-400" />}
                    </div>
                  </div>

                  <p className="text-[10px] text-violet-400/60">
                    Configure o avatar e a voz HeyGen padrão para que os vídeos sejam gerados automaticamente ao aplicar melhorias com cenas de avatar.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Missing elements */}
          {analysis.missingElements?.length > 0 && (
            <Card className="bg-amber-900/10 border-amber-800/30">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-amber-400 flex items-center gap-1">
                  <AlertTriangle className="w-4 h-4" /> Elementos Faltantes
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <ul className="space-y-1">
                  {analysis.missingElements.map((m, i) => (
                    <li key={i} className="text-sm text-amber-200 flex items-start gap-2">
                      <ChevronRight className="w-3 h-3 mt-1 shrink-0" />{m}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Improvements */}
          {analysis.improvements?.length > 0 && (() => {
            const avatarCount = analysis.improvements.filter(imp => imp.type === 'avatar_scene').length;
            // Build category counts (using type AFTER user overrides)
            const categoryCounts = analysis.improvements.reduce((acc, imp, i) => {
              const t = getEffectiveType(imp, i);
              acc[t] = (acc[t] || 0) + 1;
              return acc;
            }, {});
            const categoryColors = {
              content: 'bg-slate-700 text-slate-200 border-slate-600',
              structure: 'bg-blue-900/40 text-blue-300 border-blue-700/50',
              quiz: 'bg-purple-900/40 text-purple-300 border-purple-700/50',
              narration: 'bg-sky-900/40 text-sky-300 border-sky-700/50',
              visual: 'bg-pink-900/40 text-pink-300 border-pink-700/50',
              simulator: 'bg-emerald-900/40 text-emerald-300 border-emerald-700/50',
              avatar_scene: 'bg-violet-900/40 text-violet-300 border-violet-700/50',
              scenario: 'bg-cyan-900/40 text-cyan-300 border-cyan-700/50',
              visual_summary: 'bg-amber-900/40 text-amber-300 border-amber-700/50',
              reinforcement: 'bg-rose-900/40 text-rose-300 border-rose-700/50',
              imagem_simples: 'bg-pink-900/40 text-pink-300 border-pink-700/50',
              imagem_premium: 'bg-fuchsia-900/40 text-fuchsia-300 border-fuchsia-700/50',
            };
            const filtered = analysis.improvements
              .map((imp, i) => ({ imp, i }))
              .filter(({ imp, i }) => categoryFilter === 'all' || getEffectiveType(imp, i) === categoryFilter);
            return (
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-slate-300">Melhorias Sugeridas ({analysis.improvements.length})</h3>
              <p className="text-xs text-slate-400">Selecione as melhorias que deseja aplicar:</p>
              {/* Category filter chips */}
              <div className="flex flex-wrap gap-1.5 py-1" data-testid="improvement-category-filters">
                <button
                  type="button"
                  onClick={() => setCategoryFilter('all')}
                  className={`text-[10px] px-2 py-1 rounded-full border transition-all ${
                    categoryFilter === 'all'
                      ? 'bg-emerald-900/50 text-emerald-200 border-emerald-700 font-semibold'
                      : 'bg-slate-800/40 text-slate-400 border-slate-700 hover:border-slate-600'
                  }`}
                  data-testid="filter-chip-all"
                >
                  Todas ({analysis.improvements.length})
                </button>
                {Object.entries(categoryCounts).sort(([, a], [, b]) => b - a).map(([type, count]) => {
                  const Icon = typeIcons[type] || Lightbulb;
                  const active = categoryFilter === type;
                  return (
                    <button
                      key={type}
                      type="button"
                      onClick={() => setCategoryFilter(type)}
                      className={`text-[10px] px-2 py-1 rounded-full border transition-all flex items-center gap-1 ${
                        active
                          ? `${categoryColors[type] || 'bg-slate-700 text-slate-100 border-slate-500'} font-semibold ring-1 ring-white/20`
                          : 'bg-slate-800/40 text-slate-400 border-slate-700 hover:border-slate-600'
                      }`}
                      data-testid={`filter-chip-${type}`}
                    >
                      <Icon className="w-3 h-3" />
                      {typeLabels[type] || type} ({count})
                    </button>
                  );
                })}
              </div>
              {avatarCount > 0 && (
                <div className="flex items-center gap-2 p-2 rounded-md bg-violet-950/20 border border-violet-800/20">
                  <Video className="w-4 h-4 text-violet-400" />
                  <span className="text-xs text-violet-300">
                    {avatarCount} sugestão(ões) de cena com avatar. Ao aplicar, a imagem de fundo, narração e vídeo do avatar serão gerados automaticamente.
                  </span>
                </div>
              )}
              {filtered.length === 0 && categoryFilter !== 'all' && (
                <div className="text-xs text-slate-500 italic py-3 text-center">
                  Nenhuma melhoria desta categoria. Clique em "Todas" para ver tudo.
                </div>
              )}
              <div className="space-y-2">
                {filtered.map(({ imp, i }) => {
                  const isSelected = selectedImprovements.find(s => s.description === imp.description);
                  const effectiveType = getEffectiveType(imp, i);
                  const isAvatarScene = imp.type === 'avatar_scene';
                  const wasConverted = effectiveType !== imp.type;
                  const TypeIcon = typeIcons[effectiveType] || Lightbulb;
                  return (
                    <Card
                      key={i}
                      className={`bg-slate-900/50 transition-all ${
                        isAvatarScene && !wasConverted
                          ? (isSelected ? 'border-violet-500/50 ring-1 ring-violet-500/20' : 'border-violet-800/30 hover:border-violet-700/50')
                          : (isSelected ? 'border-emerald-500/50' : 'border-slate-800 hover:border-slate-700')
                      }`}
                      data-testid={`improvement-${i}`}
                    >
                      <CardContent className="p-3 space-y-2">
                        <div className="flex items-start gap-3 cursor-pointer" onClick={() => toggleImprovement({...imp, type: effectiveType})}>
                          <Checkbox checked={!!isSelected} className="mt-0.5 shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <Badge variant="outline" className={`text-[10px] ${priorityColors[imp.priority] || 'text-slate-400 border-slate-600'}`}>
                                {imp.priority}
                              </Badge>
                              <Badge variant="outline" className={`text-[10px] ${
                                effectiveType === 'avatar_scene' ? 'border-violet-600/50 text-violet-300 bg-violet-500/10' :
                                effectiveType === 'scenario' ? 'border-cyan-600/50 text-cyan-300 bg-cyan-500/10' :
                                effectiveType === 'visual_summary' ? 'border-amber-600/50 text-amber-300 bg-amber-500/10' :
                                effectiveType === 'reinforcement' ? 'border-rose-600/50 text-rose-300 bg-rose-500/10' :
                                effectiveType === 'simulator' ? 'border-emerald-600/50 text-emerald-300 bg-emerald-500/10' :
                                effectiveType === 'imagem_simples' ? 'border-pink-600/50 text-pink-300 bg-pink-500/10' :
                                effectiveType === 'imagem_premium' ? 'border-fuchsia-600/50 text-fuchsia-300 bg-fuchsia-500/10' :
                                'border-slate-600'
                              }`}>
                                <TypeIcon className="w-2.5 h-2.5 mr-1" />
                                {typeLabels[effectiveType] || effectiveType}
                              </Badge>
                              {wasConverted && (
                                <Badge className="text-[9px] bg-amber-600/20 text-amber-300 px-1.5 py-0">
                                  Alterado
                                </Badge>
                              )}
                              {imp.slideIndex !== undefined && (
                                <span className="text-[10px] text-slate-500">Slide {imp.slideIndex + 1}</span>
                              )}
                            </div>
                            <p className="text-sm text-slate-200">{imp.description}</p>
                            <p className="text-xs text-slate-400 mt-1">{imp.suggestion}</p>
                            {imp.scenarioTheme && (
                              <div className="mt-1.5 flex flex-wrap gap-1.5">
                                <Badge className="text-[9px] bg-cyan-900/30 text-cyan-300 border-cyan-700/30">{imp.scenarioTheme}</Badge>
                                {imp.scenarioComplexity && <Badge className="text-[9px] bg-slate-800 text-slate-300">{imp.scenarioComplexity}</Badge>}
                              </div>
                            )}
                            {imp.summaryFormat && (
                              <Badge className="text-[9px] bg-amber-900/30 text-amber-300 border-amber-700/30 mt-1.5">{imp.summaryFormat}</Badge>
                            )}
                            {imp.reinforcementType && (
                              <Badge className="text-[9px] bg-rose-900/30 text-rose-300 border-rose-700/30 mt-1.5">{imp.reinforcementType}</Badge>
                            )}
                            {imp.imagePrompt && (effectiveType === 'imagem_simples' || effectiveType === 'imagem_premium') && (
                              <div className="mt-1.5 space-y-1.5">
                                <div className="flex flex-wrap items-center gap-1.5">
                                  {effectiveType === 'imagem_premium' ? (
                                    <Badge className="text-[9px] bg-fuchsia-900/30 text-fuchsia-300 border-fuchsia-700/30">
                                      Leonardo AI · Premium
                                    </Badge>
                                  ) : (
                                    <Badge className="text-[9px] bg-pink-900/30 text-pink-300 border-pink-700/30">
                                      Gemini Nano Banana · Econômica
                                    </Badge>
                                  )}
                                  {imp.imageStyle && <Badge className="text-[9px] bg-slate-800 text-slate-300">{imp.imageStyle}</Badge>}
                                  {/* Toggle: switch between simples ↔ premium */}
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setTypeOverrides(prev => ({
                                        ...prev,
                                        [i]: effectiveType === 'imagem_premium' ? 'imagem_simples' : 'imagem_premium',
                                      }));
                                    }}
                                    className="text-[9px] px-2 py-0.5 rounded-full border border-slate-600 text-slate-300 hover:border-slate-400 hover:text-white transition"
                                    data-testid={`toggle-image-type-${i}`}
                                  >
                                    {effectiveType === 'imagem_premium' ? '↓ Trocar por econômica' : '↑ Trocar por premium'}
                                  </button>
                                </div>
                                <p className="text-[10px] text-slate-400/70 italic">{imp.imagePrompt}</p>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Avatar Scene Mockup + Type Switcher */}
                        {isAvatarScene && (
                          <div className="ml-8 space-y-2">
                            {effectiveType === 'avatar_scene' && (imp.narrationScript || scriptOverrides[i]) && (
                              <AvatarSceneMockup
                                narrationScript={scriptOverrides[i] ?? imp.narrationScript}
                                backgroundDescription={bgOverrides[i] ?? imp.backgroundDescription}
                                avatarPosition={positionOverrides[i] ?? imp.avatarPosition ?? 'left'}
                                editable
                                onScriptChange={(newScript) => handleScriptChange(i, newScript)}
                                onBackgroundChange={(newBg) => handleBgChange(i, newBg)}
                                onPositionChange={(newPos) => handlePositionChange(i, newPos)}
                              />
                            )}
                            {wasConverted && (
                              <div className="text-xs text-amber-300/80 bg-amber-950/20 rounded-md p-2 border border-amber-800/20">
                                A IA vai gerar {effectiveType === 'content' ? 'conteúdo textual rico' : effectiveType === 'simulator' ? 'um simulador interativo' : effectiveType === 'game' ? 'um jogo educativo' : effectiveType === 'quiz' ? 'um quiz' : effectiveType === 'scenario' ? 'um cenário interativo de decisão' : effectiveType === 'visual_summary' ? 'um quadro de resumo visual' : effectiveType === 'reinforcement' ? 'um reforço de aprendizagem' : effectiveType === 'imagem_simples' ? 'uma imagem econômica via Gemini Nano Banana' : effectiveType === 'imagem_premium' ? 'uma imagem premium via Leonardo AI' : 'este conteúdo'} ao invés de uma cena com avatar.
                              </div>
                            )}
                            <SlideTypeSwitcher
                              currentType={effectiveType}
                              onChange={(newType) => handleTypeChange(i, newType)}
                            />
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
            );
          })()}

          {/* Suggested new slides - now selectable */}
          {analysis.suggestedNewSlides?.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-slate-300">Novos Slides Sugeridos</h3>
                <button
                  onClick={() => {
                    if (selectedNewSlides.length === analysis.suggestedNewSlides.length) {
                      analysis.suggestedNewSlides.forEach(ns => {
                        if (selectedNewSlides.find(s => s.title === ns.title)) toggleNewSlide(ns);
                      });
                    } else {
                      analysis.suggestedNewSlides.forEach(ns => {
                        if (!selectedNewSlides.find(s => s.title === ns.title)) toggleNewSlide(ns);
                      });
                    }
                  }}
                  className="text-[10px] text-blue-400 hover:text-blue-300 transition-colors"
                  data-testid="select-all-new-slides"
                >
                  {selectedNewSlides.length === analysis.suggestedNewSlides.length ? 'Desmarcar todos' : 'Selecionar todos'}
                </button>
              </div>
              {analysis.suggestedNewSlides.map((ns, i) => {
                const isSelected = selectedNewSlides.some(s => s.title === ns.title);
                return (
                  <Card
                    key={i}
                    className={`bg-slate-900/50 cursor-pointer transition-all ${
                      isSelected ? 'border-blue-500 ring-1 ring-blue-500/20' : 'border-slate-800 hover:border-slate-700'
                    }`}
                    onClick={() => toggleNewSlide(ns)}
                    data-testid={`new-slide-${i}`}
                  >
                    <CardContent className="p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <Checkbox
                          checked={isSelected}
                          onCheckedChange={() => toggleNewSlide(ns)}
                          className="data-[state=checked]:bg-blue-600 data-[state=checked]:border-blue-600"
                          data-testid={`new-slide-checkbox-${i}`}
                        />
                        <Badge className="bg-blue-600/20 text-blue-300 text-[10px]">
                          <Plus className="w-2 h-2 mr-1" />Novo
                        </Badge>
                        <Badge variant="outline" className={`text-[10px] ${
                          ns.type === 'scenario' ? 'border-cyan-600/50 text-cyan-300 bg-cyan-500/10' :
                          ns.type === 'visual_summary' ? 'border-amber-600/50 text-amber-300 bg-amber-500/10' :
                          ns.type === 'reinforcement' ? 'border-rose-600/50 text-rose-300 bg-rose-500/10' :
                          ns.type === 'avatar_scene' ? 'border-violet-600/50 text-violet-300 bg-violet-500/10' :
                          ns.type === 'imagem_premium' ? 'border-fuchsia-600/50 text-fuchsia-300 bg-fuchsia-500/10' :
                          'border-slate-600'
                        }`}>{typeLabels[ns.type] || ns.type}</Badge>
                        {ns.position && (
                          <span className="text-[10px] text-slate-500 ml-auto">{ns.position}</span>
                        )}
                      </div>
                      <p className="text-sm text-slate-200 ml-6">{ns.title}</p>
                      <p className="text-xs text-slate-400 ml-6">{ns.reason}</p>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}

          {/* Apply button */}
          <Button
            onClick={onApply}
            disabled={loading || (selectedImprovements.length === 0 && selectedNewSlides.length === 0)}
            className="w-full bg-blue-600 hover:bg-blue-700"
            data-testid="apply-improvements-btn"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin mr-1" />
            ) : (
              <Zap className="w-4 h-4 mr-1" />
            )}
            Aplicar {selectedImprovements.length + selectedNewSlides.length} {(selectedImprovements.length + selectedNewSlides.length) === 1 ? 'Item Selecionado' : 'Itens Selecionados'}
          </Button>
        </div>
      )}
    </div>
  );
}


export function EditResultPanel({ result, course, navigate, onUndo, loading }) {
  const [avatarStatus, setAvatarStatus] = useState(null);
  const [pollingActive, setPollingActive] = useState(false);

  useEffect(() => {
    if (!result?.avatarScenesTriggered || result.avatarScenesTriggered === 0) return;
    setPollingActive(true);

    const poll = async () => {
      try {
        const resp = await fetch(`${API}/api/agent/projects/${course.id}/avatar-generation-status`, { headers: authHeaders() });
        if (resp.ok) {
          const data = await resp.json();
          setAvatarStatus(data);
          if (data.status === 'completed') {
            setPollingActive(false);
            toast.success('Cenas com avatar geradas com sucesso!');
          }
        }
      } catch (e) { /* ignore */ }
    };

    poll();
    const interval = setInterval(poll, 5000);
    return () => clearInterval(interval);
  }, [result?.avatarScenesTriggered, course?.id]);

  if (!result) return null;

  return (
    <div className="space-y-6 text-center" data-testid="edit-result-panel">
      <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-blue-600/10">
        <Check className="w-10 h-10 text-blue-400" />
      </div>
      <h2 className="text-2xl font-bold">Melhorias Aplicadas!</h2>
      <p className="text-slate-400">{course?.name}</p>
      <div className="flex justify-center gap-4 flex-wrap">
        <Badge className="bg-blue-600/20 text-blue-300">
          <Pencil className="w-3 h-3 mr-1" />{result.updatedSlides} slides atualizados
        </Badge>
        <Badge className="bg-emerald-600/20 text-emerald-300">
          <Plus className="w-3 h-3 mr-1" />{result.newSlides} novos slides
        </Badge>
        <Badge className="bg-purple-600/20 text-purple-300">
          <Layers className="w-3 h-3 mr-1" />{result.totalSlides} total
        </Badge>
      </div>

      {/* Avatar scene generation progress */}
      {result.avatarScenesTriggered > 0 && (
        <Card className="bg-violet-950/30 border-violet-800/30 text-left">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Video className="w-4 h-4 text-violet-400" />
              <span className="text-sm font-medium text-violet-200">
                Geração de Cenas com Avatar ({result.avatarScenesTriggered})
              </span>
              {pollingActive && <Loader2 className="w-3 h-3 animate-spin text-violet-400" />}
            </div>
            {avatarStatus?.scenes?.map((scene, i) => (
              <div key={i} className="flex items-center gap-3 py-1.5 border-t border-violet-800/20 first:border-0">
                <span className="text-xs text-slate-300 flex-1 truncate">{scene.slideTitle || `Cena ${i + 1}`}</span>
                <div className="flex items-center gap-2">
                  <StatusBadge label="BG" status={scene.bgStatus} />
                  <StatusBadge label="Audio" status={scene.audioStatus} />
                  <StatusBadge label="Avatar" status={scene.heygenStatus} />
                </div>
              </div>
            ))}
            {!avatarStatus && pollingActive && (
              <p className="text-xs text-violet-300/60">Iniciando geração...</p>
            )}
            {avatarStatus?.status === 'completed' && (
              <p className="text-xs text-emerald-300 mt-2 flex items-center gap-1">
                <Check className="w-3 h-3" /> Todas as cenas foram geradas!
              </p>
            )}
            {avatarStatus?.scenes?.some(s => s.heygenStatus === 'skipped_no_avatar') && (
              <p className="text-xs text-amber-300/80 mt-2 flex items-start gap-1.5 bg-amber-950/20 rounded p-2 border border-amber-800/20">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                <span>Vídeo do avatar não gerado: configure um Avatar ID padrão nas Configurações de Avatar do curso antes de analisar.</span>
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <div className="flex gap-3 justify-center flex-wrap">
        <Button onClick={() => navigate(`/editor/${course.id}`)} className="bg-blue-600 hover:bg-blue-700" data-testid="open-edited-course-btn">
          <BookOpen className="w-4 h-4 mr-2" /> Abrir no Editor
        </Button>
        {result.canUndo && onUndo && (
          <Button variant="outline" onClick={onUndo} disabled={loading} className="border-amber-600/50 text-amber-400 hover:bg-amber-600/10" data-testid="undo-improvements-btn">
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} /> Desfazer Melhorias
          </Button>
        )}
        <Button variant="outline" onClick={() => navigate('/')} data-testid="back-dashboard-edited-btn">
          <ArrowLeft className="w-4 h-4 mr-2" /> Dashboard
        </Button>
      </div>
    </div>
  );
}

function StatusBadge({ label, status }) {
  const statusConfig = {
    completed: { cls: 'bg-emerald-600/20 text-emerald-300', icon: Check },
    failed: { cls: 'bg-red-600/20 text-red-300', icon: X },
    processing: { cls: 'bg-blue-600/20 text-blue-300', icon: Loader2 },
    pending: { cls: 'bg-slate-600/20 text-slate-300', icon: Clock },
    skipped: { cls: 'bg-slate-600/20 text-slate-500', icon: null },
    skipped_no_avatar: { cls: 'bg-amber-600/20 text-amber-300', icon: AlertTriangle },
  };
  const cfg = statusConfig[status] || statusConfig.pending;
  const Icon = cfg.icon;
  return (
    <Badge className={`text-[9px] px-1.5 py-0 ${cfg.cls}`}>
      {Icon && <Icon className={`w-2 h-2 mr-0.5 ${status === 'processing' ? 'animate-spin' : ''}`} />}
      {label}
    </Badge>
  );
}


export function PreviewPanel({ preview, loading, onConfirm, onCancel, onSubmitForApproval, companies }) {
  const [activeTab, setActiveTab] = useState('changes');
  const [showApprovalDialog, setShowApprovalDialog] = useState(false);
  const [selectedCompanyId, setSelectedCompanyId] = useState('');

  if (!preview) return null;

  // Check if content looks like HTML/CSS code (not readable text)
  const isHtmlContent = (text) => {
    if (!text) return false;
    return /(<[a-z][\s\S]*>|{[^}]*:[^}]*}|body\s*{|\.[\w-]+\s*{)/i.test(text);
  };

  // Render HTML visually in a sandboxed iframe
  const HtmlVisualPreview = ({ htmlParts, label }) => {
    const combined = (htmlParts || []).join('\n');
    if (!combined) return <span className="text-slate-500 italic text-xs">Sem conteudo</span>;

    const hasHtml = isHtmlContent(combined);

    if (hasHtml) {
      const srcdoc = `<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{margin:0;padding:12px;font-family:'Segoe UI',Roboto,sans-serif;background:#1c1917;color:#fff;overflow:auto;font-size:13px;}</style></head><body>${combined}</body></html>`;
      return (
        <iframe
          srcDoc={srcdoc}
          sandbox="allow-same-origin"
          className="w-full rounded-lg border border-slate-700 bg-slate-900"
          style={{ height: 200, pointerEvents: 'none' }}
          title={label}
        />
      );
    }

    // Fallback: plain text
    return (
      <p className="text-xs text-slate-300 whitespace-pre-line leading-relaxed">
        {combined.substring(0, 500)}
        {combined.length > 500 && '...'}
      </p>
    );
  };

  const handleSubmitApproval = () => {
    if (selectedCompanyId && onSubmitForApproval) {
      onSubmitForApproval(selectedCompanyId);
      setShowApprovalDialog(false);
      setSelectedCompanyId('');
    }
  };

  return (
    <div className="space-y-4" data-testid="preview-panel">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Eye className="w-5 h-5 text-blue-400" /> Preview das Melhorias
        </h2>
        <div className="flex items-center gap-2">
          <Badge className="bg-blue-600/20 text-blue-300 text-xs">
            {preview.updatedCount} alterados
          </Badge>
          {preview.newCount > 0 && (
            <Badge className="bg-emerald-600/20 text-emerald-300 text-xs">
              {preview.newCount} novos
            </Badge>
          )}
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-slate-800/50 w-full">
          <TabsTrigger value="changes" className="flex-1 text-xs">Slides Alterados ({preview.updatedCount})</TabsTrigger>
          {preview.newCount > 0 && (
            <TabsTrigger value="new" className="flex-1 text-xs">Novos Slides ({preview.newCount})</TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="changes" className="space-y-4 mt-4">
          {preview.comparisons?.map((comp, i) => {
            const titleChanged = comp.title.before !== comp.title.after;
            const hasHtmlData = comp.htmlBefore?.length > 0 || comp.htmlAfter?.length > 0;

            return (
              <Card key={i} className="bg-slate-900/50 border-slate-800 overflow-hidden" data-testid={`preview-comparison-${i}`}>
                <CardHeader className="py-2 px-4 bg-slate-800/50">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Layers className="w-4 h-4 text-blue-400" />
                    Slide {comp.slideIndex + 1}
                    {titleChanged && (
                      <Badge className="bg-amber-600/20 text-amber-300 text-[10px]">Titulo alterado</Badge>
                    )}
                    {hasHtmlData && (
                      <Badge className="bg-violet-600/20 text-violet-300 text-[10px]">Visual</Badge>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="grid grid-cols-2 divide-x divide-slate-700">
                    {/* Before */}
                    <div className="p-3">
                      <div className="flex items-center gap-1 mb-2">
                        <div className="w-2 h-2 rounded-full bg-red-500" />
                        <span className="text-[10px] font-medium text-red-400 uppercase tracking-wider">Antes</span>
                      </div>
                      <p className="text-xs font-semibold text-slate-200 mb-2">{comp.title.before}</p>
                      {hasHtmlData ? (
                        <HtmlVisualPreview htmlParts={comp.htmlBefore} label={`Antes - Slide ${comp.slideIndex + 1}`} />
                      ) : (
                        <div className="bg-slate-800 rounded-lg p-3 max-h-52 overflow-y-auto">
                          <p className="text-xs text-slate-300 whitespace-pre-line leading-relaxed">
                            {(comp.contentBefore || []).join('\n\n').substring(0, 500) || <span className="text-slate-500 italic">Sem conteudo de texto</span>}
                          </p>
                        </div>
                      )}
                    </div>
                    {/* After */}
                    <div className="p-3">
                      <div className="flex items-center gap-1 mb-2">
                        <div className="w-2 h-2 rounded-full bg-emerald-500" />
                        <span className="text-[10px] font-medium text-emerald-400 uppercase tracking-wider">Depois</span>
                      </div>
                      <p className="text-xs font-semibold text-slate-200 mb-2">{comp.title.after}</p>
                      {hasHtmlData ? (
                        <HtmlVisualPreview htmlParts={comp.htmlAfter} label={`Depois - Slide ${comp.slideIndex + 1}`} />
                      ) : (
                        <div className="bg-emerald-950/40 border border-emerald-800/30 rounded-lg p-3 max-h-52 overflow-y-auto">
                          <p className="text-xs text-emerald-200 whitespace-pre-line leading-relaxed">
                            {(comp.contentAfter || []).join('\n\n').substring(0, 500) || <span className="text-slate-500 italic">Sem conteudo de texto</span>}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
          {preview.comparisons?.length === 0 && (
            <p className="text-sm text-slate-400 text-center py-4">Nenhum slide existente será alterado.</p>
          )}
        </TabsContent>

        {preview.newCount > 0 && (
          <TabsContent value="new" className="space-y-3 mt-4">
            {preview.newSlides?.map((ns, i) => {
              const hasHtml = ns.html?.length > 0;
              return (
                <Card key={i} className="bg-slate-900/50 border-slate-800" data-testid={`preview-new-slide-${i}`}>
                  <CardContent className="p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge className="bg-emerald-600/20 text-emerald-300 text-[10px]">
                        <Plus className="w-2 h-2 mr-1" /> Novo
                      </Badge>
                      <span className="text-xs text-slate-500">Apos slide {ns.afterIndex + 1}</span>
                    </div>
                    <p className="text-sm font-medium text-slate-200 mb-2">{ns.title}</p>
                    {hasHtml ? (
                      <HtmlVisualPreview htmlParts={ns.html} label={`Novo Slide - ${ns.title}`} />
                    ) : (
                      <div className="bg-emerald-950/40 border border-emerald-800/30 rounded-lg p-3 max-h-40 overflow-y-auto">
                        <p className="text-xs text-emerald-200 whitespace-pre-line leading-relaxed">
                          {(ns.content || []).join('\n\n').substring(0, 300) || <span className="text-slate-500 italic">Sem conteudo de texto</span>}
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </TabsContent>
        )}
      </Tabs>

      {/* Action buttons */}
      <div className="flex gap-3 pt-2">
        <Button
          onClick={onConfirm}
          disabled={loading}
          className="flex-1 bg-emerald-600 hover:bg-emerald-700"
          data-testid="confirm-improvements-btn"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Check className="w-4 h-4 mr-1" />}
          Confirmar e Aplicar
        </Button>
        {onSubmitForApproval && (
          <Button
            onClick={() => setShowApprovalDialog(true)}
            disabled={loading}
            variant="outline"
            className="flex-1 border-amber-700 text-amber-300 hover:bg-amber-900/20"
            data-testid="submit-improvements-for-approval-btn"
          >
            <Send className="w-4 h-4 mr-1" /> Enviar para Aprovacao
          </Button>
        )}
        <Button
          variant="outline"
          onClick={onCancel}
          disabled={loading}
          className="border-slate-600 hover:bg-slate-800"
          data-testid="cancel-preview-btn"
        >
          <X className="w-4 h-4 mr-1" /> Cancelar
        </Button>
      </div>

      {/* Company selection dialog for improvement approval */}
      {showApprovalDialog && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" data-testid="improvement-approval-company-dialog">
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-md mx-4 space-y-4">
            <h3 className="text-base font-semibold flex items-center gap-2">
              <Send className="w-4 h-4 text-amber-400" />
              Enviar Melhorias para Aprovacao
            </h3>
            <p className="text-sm text-slate-400">
              Selecione a empresa cujo aprovador ira revisar estas melhorias antes de serem aplicadas ao curso:
            </p>
            <select
              value={selectedCompanyId}
              onChange={e => setSelectedCompanyId(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white focus:border-amber-500 focus:outline-none"
              data-testid="improvement-approval-company-select"
            >
              <option value="">-- Selecione a Empresa --</option>
              {(companies || []).map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <div className="flex gap-2 pt-2">
              <Button
                onClick={handleSubmitApproval}
                disabled={!selectedCompanyId}
                className="flex-1 bg-amber-600 hover:bg-amber-700"
                data-testid="confirm-submit-improvement-approval"
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