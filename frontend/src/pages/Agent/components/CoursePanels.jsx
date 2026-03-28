import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { getApiUrl } from '../../../utils/apiUrl';
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

export function CourseReviewPanel({ course, analysis, loading, selectedImprovements, toggleImprovement, onApply }) {
  const [avatarLimit, setAvatarLimit] = useState(3);
  const [avatarSettingsOpen, setAvatarSettingsOpen] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);

  useEffect(() => {
    if (!course?.id) return;
    fetch(`${API}/api/agent/projects/${course.id}/avatar-settings`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.maxScenes) setAvatarLimit(data.maxScenes); })
      .catch(() => {});
  }, [course?.id]);

  const saveAvatarSettings = async (val) => {
    setAvatarLimit(val);
    setSavingSettings(true);
    try {
      await fetch(`${API}/api/agent/projects/${course.id}/avatar-settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ maxScenes: val }),
      });
    } catch { /* ignore */ }
    finally { setSavingSettings(false); }
  };

  if (!course) return null;
  const priorityColors = { alta: 'text-red-400 border-red-800/40', media: 'text-amber-400 border-amber-800/40', baixa: 'text-blue-400 border-blue-800/40' };
  const typeLabels = { content: 'Conteúdo', structure: 'Estrutura', quiz: 'Quiz', narration: 'Narração', visual: 'Visual', simulator: 'Simulador', avatar_scene: 'Cena com Avatar' };
  const typeIcons = { content: Type, structure: Layers, quiz: Target, narration: Volume2, visual: Palette, simulator: Code, avatar_scene: Video };

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
                </div>
                {avatarSettingsOpen ? <ChevronUp className="w-4 h-4 text-violet-400" /> : <ChevronDown className="w-4 h-4 text-violet-400" />}
              </button>
              {avatarSettingsOpen && (
                <div className="mt-3 space-y-3 pt-3 border-t border-violet-800/20">
                  <div className="flex items-center justify-between">
                    <label className="text-xs text-violet-300">Máximo de cenas com avatar</label>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        min={0}
                        max={20}
                        value={avatarLimit}
                        onChange={(e) => saveAvatarSettings(parseInt(e.target.value) || 0)}
                        className="w-16 h-7 text-xs bg-violet-950/50 border-violet-800/40 text-center"
                        data-testid="avatar-limit-input"
                      />
                      {savingSettings && <Loader2 className="w-3 h-3 animate-spin text-violet-400" />}
                    </div>
                  </div>
                  <p className="text-[10px] text-violet-400/60">
                    Define quantas cenas com avatar o agente pode sugerir. A geração do avatar e narração consome créditos HeyGen/ElevenLabs.
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
            return (
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-slate-300">Melhorias Sugeridas ({analysis.improvements.length})</h3>
              <p className="text-xs text-slate-400">Selecione as melhorias que deseja aplicar:</p>
              {avatarCount > 0 && (
                <div className="flex items-center gap-2 p-2 rounded-md bg-violet-950/20 border border-violet-800/20">
                  <Video className="w-4 h-4 text-violet-400" />
                  <span className="text-xs text-violet-300">
                    {avatarCount} sugestão(ões) de cena com avatar. Ao aplicar, a imagem de fundo, narração e vídeo do avatar serão gerados automaticamente.
                  </span>
                </div>
              )}
              <div className="space-y-2">
                {analysis.improvements.map((imp, i) => {
                  const isSelected = selectedImprovements.find(s => s.description === imp.description);
                  const isAvatarScene = imp.type === 'avatar_scene';
                  const TypeIcon = typeIcons[imp.type] || Lightbulb;
                  return (
                    <Card
                      key={i}
                      className={`bg-slate-900/50 cursor-pointer transition-all ${
                        isAvatarScene
                          ? (isSelected ? 'border-violet-500/50 ring-1 ring-violet-500/20' : 'border-violet-800/30 hover:border-violet-700/50')
                          : (isSelected ? 'border-emerald-500/50' : 'border-slate-800 hover:border-slate-700')
                      }`}
                      onClick={() => toggleImprovement(imp)}
                      data-testid={`improvement-${i}`}
                    >
                      <CardContent className="p-3 flex items-start gap-3">
                        <Checkbox checked={!!isSelected} className="mt-0.5 shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <Badge variant="outline" className={`text-[10px] ${priorityColors[imp.priority] || 'text-slate-400 border-slate-600'}`}>
                              {imp.priority}
                            </Badge>
                            <Badge variant="outline" className={`text-[10px] ${isAvatarScene ? 'border-violet-600/50 text-violet-300 bg-violet-500/10' : 'border-slate-600'}`}>
                              <TypeIcon className="w-2.5 h-2.5 mr-1" />
                              {typeLabels[imp.type] || imp.type}
                            </Badge>
                            {imp.slideIndex !== undefined && (
                              <span className="text-[10px] text-slate-500">Slide {imp.slideIndex + 1}</span>
                            )}
                          </div>
                          <p className="text-sm text-slate-200">{imp.description}</p>
                          <p className="text-xs text-slate-400 mt-1">{imp.suggestion}</p>
                          {isAvatarScene && imp.narrationScript && (
                            <div className="mt-2 p-2 rounded-md bg-violet-950/30 border border-violet-800/20">
                              <div className="flex items-center gap-1.5 mb-1">
                                <Volume2 className="w-3 h-3 text-violet-400" />
                                <span className="text-[10px] font-medium text-violet-300 uppercase tracking-wider">Script de Narração</span>
                              </div>
                              <p className="text-xs text-violet-200/80 line-clamp-3">{imp.narrationScript}</p>
                              {imp.backgroundDescription && (
                                <div className="flex items-center gap-1.5 mt-2">
                                  <Image className="w-3 h-3 text-violet-400" />
                                  <span className="text-[10px] text-violet-300/60">{imp.backgroundDescription}</span>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
            );
          })()}

          {/* Suggested new slides */}
          {analysis.suggestedNewSlides?.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-slate-300">Novos Slides Sugeridos</h3>
              {analysis.suggestedNewSlides.map((ns, i) => (
                <Card key={i} className="bg-slate-900/50 border-slate-800">
                  <CardContent className="p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge className="bg-blue-600/20 text-blue-300 text-[10px]">
                        <Plus className="w-2 h-2 mr-1" />Novo
                      </Badge>
                      <Badge variant="outline" className="text-[10px] border-slate-600">{ns.type}</Badge>
                    </div>
                    <p className="text-sm text-slate-200">{ns.title}</p>
                    <p className="text-xs text-slate-400">{ns.reason}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Apply button */}
          <Button
            onClick={onApply}
            disabled={loading || selectedImprovements.length === 0}
            className="w-full bg-blue-600 hover:bg-blue-700"
            data-testid="apply-improvements-btn"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin mr-1" />
            ) : (
              <Zap className="w-4 h-4 mr-1" />
            )}
            Aplicar {selectedImprovements.length} Melhoria{selectedImprovements.length !== 1 ? 's' : ''} Selecionada{selectedImprovements.length !== 1 ? 's' : ''}
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
        const resp = await fetch(`${API}/api/agent/projects/${course.id}/avatar-generation-status`);
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


export function PreviewPanel({ preview, loading, onConfirm, onCancel }) {
  const [activeTab, setActiveTab] = useState('changes');

  if (!preview) return null;

  // Strip HTML tags and decode entities for readable text
  const stripHtml = (html) => {
    if (!html) return '';
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    return tmp.textContent || tmp.innerText || '';
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
            const beforeText = (comp.contentBefore || []).map(c => stripHtml(c)).join('\n\n');
            const afterText = (comp.contentAfter || []).map(c => stripHtml(c)).join('\n\n');
            const titleChanged = comp.title.before !== comp.title.after;

            return (
              <Card key={i} className="bg-slate-900/50 border-slate-800 overflow-hidden" data-testid={`preview-comparison-${i}`}>
                <CardHeader className="py-2 px-4 bg-slate-800/50">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Layers className="w-4 h-4 text-blue-400" />
                    Slide {comp.slideIndex + 1}
                    {titleChanged && (
                      <Badge className="bg-amber-600/20 text-amber-300 text-[10px]">Título alterado</Badge>
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
                      <div className="bg-slate-800 rounded-lg p-3 max-h-52 overflow-y-auto">
                        <p className="text-xs text-slate-300 whitespace-pre-line leading-relaxed">
                          {beforeText.substring(0, 500) || <span className="text-slate-500 italic">Sem conteúdo de texto</span>}
                          {beforeText.length > 500 && '...'}
                        </p>
                      </div>
                    </div>
                    {/* After */}
                    <div className="p-3">
                      <div className="flex items-center gap-1 mb-2">
                        <div className="w-2 h-2 rounded-full bg-emerald-500" />
                        <span className="text-[10px] font-medium text-emerald-400 uppercase tracking-wider">Depois</span>
                      </div>
                      <p className="text-xs font-semibold text-slate-200 mb-2">{comp.title.after}</p>
                      <div className="bg-emerald-950/40 border border-emerald-800/30 rounded-lg p-3 max-h-52 overflow-y-auto">
                        <p className="text-xs text-emerald-200 whitespace-pre-line leading-relaxed">
                          {afterText.substring(0, 500) || <span className="text-slate-500 italic">Sem conteúdo de texto</span>}
                          {afterText.length > 500 && '...'}
                        </p>
                      </div>
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
              const newText = (ns.content || []).map(c => stripHtml(c)).join('\n\n');
              return (
                <Card key={i} className="bg-slate-900/50 border-slate-800" data-testid={`preview-new-slide-${i}`}>
                  <CardContent className="p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge className="bg-emerald-600/20 text-emerald-300 text-[10px]">
                        <Plus className="w-2 h-2 mr-1" /> Novo
                      </Badge>
                      <span className="text-xs text-slate-500">Após slide {ns.afterIndex + 1}</span>
                    </div>
                    <p className="text-sm font-medium text-slate-200 mb-2">{ns.title}</p>
                    <div className="bg-emerald-950/40 border border-emerald-800/30 rounded-lg p-3 max-h-40 overflow-y-auto">
                      <p className="text-xs text-emerald-200 whitespace-pre-line leading-relaxed">
                        {newText.substring(0, 300) || <span className="text-slate-500 italic">Sem conteúdo de texto</span>}
                        {newText.length > 300 && '...'}
                      </p>
                    </div>
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
    </div>
  );
}