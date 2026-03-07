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
  if (!course) return null;
  const priorityColors = { alta: 'text-red-400 border-red-800/40', media: 'text-amber-400 border-amber-800/40', baixa: 'text-blue-400 border-blue-800/40' };
  const typeLabels = { content: 'Conteúdo', structure: 'Estrutura', quiz: 'Quiz', narration: 'Narração', visual: 'Visual' };

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
          {analysis.improvements?.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-slate-300">Melhorias Sugeridas ({analysis.improvements.length})</h3>
              <p className="text-xs text-slate-400">Selecione as melhorias que deseja aplicar:</p>
              <div className="space-y-2">
                {analysis.improvements.map((imp, i) => {
                  const isSelected = selectedImprovements.find(s => s.description === imp.description);
                  return (
                    <Card
                      key={i}
                      className={`bg-slate-900/50 cursor-pointer transition-all ${isSelected ? 'border-emerald-500/50' : 'border-slate-800 hover:border-slate-700'}`}
                      onClick={() => toggleImprovement(imp)}
                      data-testid={`improvement-${i}`}
                    >
                      <CardContent className="p-3 flex items-start gap-3">
                        <Checkbox checked={!!isSelected} className="mt-0.5 shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <Badge variant="outline" className={`text-[10px] ${priorityColors[imp.priority] || 'text-slate-400 border-slate-600'}`}>
                              {imp.priority}
                            </Badge>
                            <Badge variant="outline" className="text-[10px] border-slate-600">
                              {typeLabels[imp.type] || imp.type}
                            </Badge>
                            {imp.slideIndex !== undefined && (
                              <span className="text-[10px] text-slate-500">Slide {imp.slideIndex + 1}</span>
                            )}
                          </div>
                          <p className="text-sm text-slate-200">{imp.description}</p>
                          <p className="text-xs text-slate-400 mt-1">{imp.suggestion}</p>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          )}

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


export function EditResultPanel({ result, course, navigate }) {
  if (!result) return null;
  return (
    <div className="space-y-6 text-center" data-testid="edit-result-panel">
      <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-blue-600/10">
        <Check className="w-10 h-10 text-blue-400" />
      </div>
      <h2 className="text-2xl font-bold">Melhorias Aplicadas!</h2>
      <p className="text-slate-400">{course?.name}</p>
      <div className="flex justify-center gap-4">
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
      <div className="flex gap-3 justify-center">
        <Button onClick={() => navigate(`/editor/${course.id}`)} className="bg-blue-600 hover:bg-blue-700" data-testid="open-edited-course-btn">
          <BookOpen className="w-4 h-4 mr-2" /> Abrir no Editor
        </Button>
        <Button variant="outline" onClick={() => navigate('/')} data-testid="back-dashboard-edited-btn">
          <ArrowLeft className="w-4 h-4 mr-2" /> Dashboard
        </Button>
      </div>
    </div>
  );
}