import React, { useState, useCallback, useEffect } from 'react';
import { getApiUrl } from '../../utils/apiUrl';
import { authHeaders } from '../../contexts/AuthContext';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { ScrollArea } from '../../components/ui/scroll-area';
import { Checkbox } from '../../components/ui/checkbox';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { toast } from 'sonner';
import {
  Sparkles, Loader2, Check, AlertTriangle, Eye, Paintbrush,
  Monitor, Smartphone, Type, Palette, Layout, Layers, X, ChevronDown, ChevronUp, Wand2,
  Maximize2, Minimize2, Undo2,
} from 'lucide-react';
import KreaPanel from '../../pages/Agent/components/KreaPanel';

const API = getApiUrl();

const SEVERITY_STYLES = {
  alta: 'bg-red-500/15 border-red-500/30 text-red-300',
  media: 'bg-amber-500/15 border-amber-500/30 text-amber-300',
  baixa: 'bg-blue-500/15 border-blue-500/30 text-blue-300',
};

const CATEGORY_ICONS = {
  contraste: Palette,
  harmonizacao: Paintbrush,
  fonte: Type,
  layout: Layout,
  consistencia: Layers,
  legibilidade_html: Monitor,
};

const CATEGORY_LABELS = {
  contraste: 'Contraste',
  harmonizacao: 'Harmonizacao',
  fonte: 'Fontes',
  layout: 'Layout',
  consistencia: 'Consistencia',
  legibilidade_html: 'HTML/Simuladores',
};

function ScoreRing({ score }) {
  const color = score >= 80 ? '#10b981' : score >= 60 ? '#f59e0b' : '#ef4444';
  const circumference = 2 * Math.PI * 36;
  const offset = circumference - (score / 100) * circumference;
  return (
    <div className="relative w-24 h-24 mx-auto">
      <svg className="w-24 h-24 -rotate-90" viewBox="0 0 80 80">
        <circle cx="40" cy="40" r="36" fill="none" stroke="#1e293b" strokeWidth="6" />
        <circle cx="40" cy="40" r="36" fill="none" stroke={color} strokeWidth="6"
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round" className="transition-all duration-1000" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold" style={{ color }}>{score}</span>
        <span className="text-[10px] text-slate-400">/ 100</span>
      </div>
    </div>
  );
}

export default function AestheticsPanel({ projectId, onFixApplied, onClose, expanded = false, onToggleExpand }) {
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [selectedFixes, setSelectedFixes] = useState(new Set());
  const [applying, setApplying] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState(new Set());
  const [showKrea, setShowKrea] = useState(false);
  const [kreaInitialPrompt, setKreaInitialPrompt] = useState('');
  // Snapshot/revert state — populated either after apply succeeds or
  // detected on mount (so a revert button appears even after a refresh).
  const [canRevert, setCanRevert] = useState(false);
  const [reverting, setReverting] = useState(false);

  // Check on mount whether a revertible snapshot already exists for this project
  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/api/aesthetics/snapshot-status/${projectId}`, {
          headers: authHeaders(),
          credentials: 'include',
        });
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) setCanRevert(!!data.hasSnapshot);
      } catch (_e) { /* silent */ }
    })();
    return () => { cancelled = true; };
  }, [projectId]);

  const handleRevert = useCallback(async () => {
    if (!projectId) return;
    setReverting(true);
    try {
      const res = await fetch(`${API}/api/aesthetics/revert/${projectId}`, {
        method: 'POST',
        headers: authHeaders(),
        credentials: 'include',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Erro ${res.status}`);
      }
      toast.success('Correções esteticas revertidas!');
      setCanRevert(false);
      if (onFixApplied) onFixApplied();
    } catch (e) {
      toast.error(e.message || 'Erro ao reverter');
    }
    setReverting(false);
  }, [projectId, onFixApplied]);

  const handleAnalyze = useCallback(async () => {
    if (!projectId) return;
    setAnalyzing(true);
    setResult(null);
    setSelectedFixes(new Set());
    try {
      const res = await fetch(`${API}/api/aesthetics/analyze/${projectId}`, {
        method: 'POST',
        headers: authHeaders(),
        credentials: 'include',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Erro na analise');
      }
      const data = await res.json();
      setResult(data);
      // Auto-expand categories with issues
      const cats = new Set(data.issues?.map(i => i.category) || []);
      setExpandedCategories(cats);
      toast.success(`Analise concluida! Score: ${data.score}/100`);
    } catch (e) {
      toast.error(e.message || 'Erro ao analisar estetica');
    }
    setAnalyzing(false);
  }, [projectId]);

  const toggleFix = (issueId) => {
    setSelectedFixes(prev => {
      const next = new Set(prev);
      if (next.has(issueId)) next.delete(issueId);
      else next.add(issueId);
      return next;
    });
  };

  const selectAll = () => {
    if (!result?.issues) return;
    setSelectedFixes(new Set(result.issues.map(i => i.id)));
  };

  const deselectAll = () => setSelectedFixes(new Set());

  const handleApply = useCallback(async (applyAll = false) => {
    if (!projectId || (!applyAll && selectedFixes.size === 0)) return;
    setApplying(true);
    try {
      const res = await fetch(`${API}/api/aesthetics/apply-fix/${projectId}`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        credentials: 'include',
        body: JSON.stringify(applyAll ? { applyAll: true } : { fixIds: [...selectedFixes] }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Erro ${res.status}`);
      }
      const data = await res.json();
      toast.success(`${data.applied} correcoes aplicadas!`);
      if (data.canRevert) setCanRevert(true);
      if (onFixApplied) onFixApplied();
    } catch (e) {
      toast.error(e.message || 'Erro ao aplicar correcoes');
    }
    setApplying(false);
  }, [projectId, selectedFixes, onFixApplied]);

  const toggleCategory = (cat) => {
    setExpandedCategories(prev => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  // Group issues by category
  const groupedIssues = {};
  (result?.issues || []).forEach(issue => {
    const cat = issue.category || 'outro';
    if (!groupedIssues[cat]) groupedIssues[cat] = [];
    groupedIssues[cat].push(issue);
  });

  return (
    <div className="space-y-4" data-testid="aesthetics-panel">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-violet-400" />
          <h3 className="text-sm font-semibold text-white">Analisador de Estetica</h3>
        </div>
        <div className="flex items-center gap-1">
          {onToggleExpand && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onToggleExpand}
              className="h-7 w-7 p-0 text-slate-400 hover:text-violet-300"
              title={expanded ? 'Colapsar painel' : 'Expandir para tela cheia'}
              data-testid="aesthetics-toggle-expand"
            >
              {expanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </Button>
          )}
          {onClose && (
            <Button variant="ghost" size="sm" onClick={onClose} className="h-7 w-7 p-0">
              <X className="w-4 h-4" />
            </Button>
          )}
        </div>
      </div>

      {!result && (
        <Card className="bg-slate-900/50 border-slate-700">
          <CardContent className="p-4 text-center space-y-3">
            <div className="flex justify-center gap-6 text-slate-400">
              <div className="text-center"><Palette className="w-6 h-6 mx-auto mb-1 text-violet-400" /><span className="text-[10px]">Cores</span></div>
              <div className="text-center"><Type className="w-6 h-6 mx-auto mb-1 text-emerald-400" /><span className="text-[10px]">Fontes</span></div>
              <div className="text-center"><Layout className="w-6 h-6 mx-auto mb-1 text-amber-400" /><span className="text-[10px]">Layout</span></div>
              <div className="text-center"><Monitor className="w-6 h-6 mx-auto mb-1 text-blue-400" /><span className="text-[10px]">HTML</span></div>
            </div>
            <p className="text-xs text-slate-400">
              Analisa contraste, harmonizacao de cores, fontes, layout e legibilidade de simuladores/cenarios.
            </p>
            <Button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="w-full bg-violet-600 hover:bg-violet-700"
              data-testid="analyze-aesthetics-btn"
            >
              {analyzing ? (
                <><Loader2 className="w-4 h-4 animate-spin mr-2" /> Analisando slides...</>
              ) : (
                <><Eye className="w-4 h-4 mr-2" /> Analisar Estetica do Curso</>
              )}
            </Button>
          </CardContent>
        </Card>
      )}

      {result && (
        <>
          {/* Score */}
          <Card className="bg-slate-900/50 border-slate-700">
            <CardContent className="p-4 space-y-2">
              <ScoreRing score={result.score || 0} />
              <p className="text-xs text-slate-300 text-center mt-2">{result.summary}</p>
              <div className="flex justify-center gap-2 mt-2">
                {Object.entries(groupedIssues).map(([cat, items]) => {
                  const Icon = CATEGORY_ICONS[cat] || AlertTriangle;
                  return (
                    <Badge key={cat} variant="outline" className="text-[10px] gap-1">
                      <Icon className="w-3 h-3" /> {items.length}
                    </Badge>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* Issues by category */}
          <ScrollArea className={expanded ? 'max-h-[68vh]' : 'max-h-[45vh]'}>
            <div className={expanded ? 'grid grid-cols-2 gap-3 pr-2' : 'space-y-2 pr-2'}>
              {Object.entries(groupedIssues).map(([cat, items]) => {
                const Icon = CATEGORY_ICONS[cat] || AlertTriangle;
                const expandedCat = expandedCategories.has(cat);
                return (
                  <div key={cat} className="border border-slate-700 rounded-lg overflow-hidden">
                    <button
                      onClick={() => toggleCategory(cat)}
                      className="w-full flex items-center justify-between px-3 py-2 bg-slate-800/50 hover:bg-slate-800 transition-colors"
                      data-testid={`aesthetics-category-${cat}`}
                    >
                      <div className="flex items-center gap-2">
                        <Icon className="w-4 h-4 text-slate-300" />
                        <span className={`font-medium text-slate-200 ${expanded ? 'text-sm' : 'text-xs'}`}>{CATEGORY_LABELS[cat] || cat}</span>
                        <Badge className="text-[9px] bg-slate-700 text-slate-300">{items.length}</Badge>
                      </div>
                      {expandedCat ? <ChevronUp className="w-3 h-3 text-slate-400" /> : <ChevronDown className="w-3 h-3 text-slate-400" />}
                    </button>
                    {expandedCat && (
                      <div className="p-2 space-y-1.5">
                        {items.map(issue => (
                          <div
                            key={issue.id}
                            className={`flex items-start gap-2 p-2 rounded border ${expanded ? 'text-sm' : 'text-xs'} ${SEVERITY_STYLES[issue.severity] || SEVERITY_STYLES.baixa}`}
                            data-testid={`aesthetics-issue-${issue.id}`}
                          >
                            <Checkbox
                              checked={selectedFixes.has(issue.id)}
                              onCheckedChange={() => toggleFix(issue.id)}
                              className="mt-0.5 shrink-0"
                            />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-1.5 mb-0.5">
                                <Badge className="text-[8px] px-1 py-0">{issue.severity}</Badge>
                                <span className="text-slate-400">Slide {(issue.slideIndex || 0) + 1}</span>
                              </div>
                              <p className="text-slate-200 leading-snug">{issue.description}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </ScrollArea>

          {/* Global suggestions */}
          {result.globalSuggestions?.length > 0 && (
            <Card className="bg-violet-900/10 border-violet-800/30">
              <CardContent className="p-3 space-y-1.5">
                <span className="text-[10px] font-medium text-violet-300">Sugestoes Globais</span>
                {result.globalSuggestions.map((s, i) => (
                  <p key={i} className="text-[11px] text-slate-300">- {s.description}</p>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Action buttons */}
          <div className="space-y-2 pb-16">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-400">{selectedFixes.size} de {result.issues?.length || 0} selecionadas</span>
              <div className="flex gap-2">
                <button onClick={selectAll} className="text-[10px] text-violet-400 hover:text-violet-300 underline" data-testid="aesthetics-select-all">Selecionar todas</button>
                <button onClick={deselectAll} className="text-[10px] text-slate-500 hover:text-slate-300 underline">Desmarcar</button>
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => handleApply(false)}
                disabled={applying || selectedFixes.size === 0}
                className="flex-1 bg-violet-600 hover:bg-violet-700 text-xs h-9"
                data-testid="aesthetics-apply-selected"
              >
                {applying ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Paintbrush className="w-3 h-3 mr-1" />}
                Aplicar Selecionadas ({selectedFixes.size})
              </Button>
              <Button
                onClick={() => handleApply(true)}
                disabled={applying || !result.issues?.length}
                variant="outline"
                className="text-xs h-9 border-violet-700 text-violet-300 hover:bg-violet-900/20"
                data-testid="aesthetics-apply-all"
              >
                <Check className="w-3 h-3 mr-1" /> Aplicar Todas
              </Button>
            </div>

            {/* Revert button — only shown when a snapshot exists (i.e., user just
                applied something or has a pending unconsumed snapshot). */}
            {canRevert && (
              <Button
                onClick={handleRevert}
                disabled={reverting}
                variant="outline"
                className="w-full text-xs h-9 border-amber-700/60 text-amber-300 hover:bg-amber-900/20 bg-amber-950/20"
                data-testid="aesthetics-revert"
              >
                {reverting ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Undo2 className="w-3 h-3 mr-1" />}
                Reverter ultima aplicacao
              </Button>
            )}

            {/* Krea AI: regenerate images based on aesthetic analysis — promoted
                to be just below the apply buttons so it's never hidden under
                floating watermarks/logos at the viewport bottom. */}
            <Button
              onClick={() => {
                // Build a context-aware default prompt from the summary + first image-related issue
                const imgIssue = result.issues?.find(i =>
                  i.category === 'contraste' || i.category === 'harmonizacao' || i.category === 'legibilidade_html'
                );
                const contextHint = imgIssue?.description || result.summary || '';
                const defaultPrompt = contextHint
                  ? `Imagem ilustrativa educacional de alta qualidade, estilo profissional, paleta de cores harmônica com boa legibilidade. Contexto: ${contextHint.slice(0, 250)}`
                  : 'Imagem ilustrativa educacional de alta qualidade, estilo profissional, paleta harmônica';
                setKreaInitialPrompt(defaultPrompt);
                setShowKrea(true);
              }}
              variant="outline"
              className="w-full text-xs h-9 border-pink-700/50 text-pink-300 hover:bg-pink-900/20 bg-gradient-to-r from-pink-900/10 to-rose-900/10"
              data-testid="aesthetics-krea-regenerate"
            >
              <Wand2 className="w-3 h-3 mr-1" /> Regerar imagens com Krea AI
            </Button>

            <Button
              onClick={handleAnalyze}
              disabled={analyzing}
              variant="ghost"
              className="w-full text-xs h-8 text-slate-400"
              data-testid="aesthetics-reanalyze"
            >
              <Eye className="w-3 h-3 mr-1" /> Re-analisar
            </Button>
          </div>
        </>
      )}

      {/* Krea AI dialog — opens pre-filled with context-aware prompt */}
      <Dialog open={showKrea} onOpenChange={setShowKrea}>
        <DialogContent className="max-w-2xl bg-slate-900 border-slate-700 p-0 max-h-[90vh] overflow-y-auto">
          <DialogHeader className="sr-only">
            <DialogTitle>Krea AI — Regeração estética</DialogTitle>
          </DialogHeader>
          <KreaPanel
            projectId={projectId}
            initialPrompt={kreaInitialPrompt}
            onClose={() => setShowKrea(false)}
            onImageSaved={() => {
              toast.success('Imagem Krea salva! Adicione manualmente ao slide no editor.');
              setShowKrea(false);
              if (onFixApplied) onFixApplied();
            }}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
