import React, { useState, useEffect, useCallback } from 'react';
import { getApiUrl } from '../utils/apiUrl';
import { authHeaders } from '../contexts/AuthContext';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import {
  MessageSquare, BookOpen, Building2, TrendingUp, Clock,
  Loader2, ArrowLeft, RefreshCw, BarChart3, HelpCircle,
  ChevronDown, ChevronUp, Search, Hash, ThumbsUp, ThumbsDown, Smile,
} from 'lucide-react';

const API = getApiUrl();

export default function TutorDashboard() {
  const { isSuperAdmin } = useAuth();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedCourse, setSelectedCourse] = useState(null);
  const [courseDetail, setCourseDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [expandedCompanies, setExpandedCompanies] = useState({});
  const [searchQuery, setSearchQuery] = useState('');
  const [feedbackStats, setFeedbackStats] = useState(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/admin/tutor-dashboard`, { headers: authHeaders() });
      if (res.ok) {
        setDashboard(await res.json());
      } else {
        toast.error('Erro ao carregar dashboard do tutor');
      }
    } catch {
      toast.error('Erro de conexao');
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  const fetchCourseDetail = async (projectId) => {
    setLoadingDetail(true);
    try {
      const res = await fetch(`${API}/api/admin/tutor-dashboard/course/${projectId}`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setCourseDetail(data);
        setSelectedCourse(projectId);
      }
    } catch {
      toast.error('Erro ao carregar detalhes');
    }
    setLoadingDetail(false);
    // Feedback fetched in parallel — silently empty if there are no
    // ratings yet (most common case for fresh courses).
    fetchFeedbackStats(projectId);
  };

  const fetchFeedbackStats = async (projectId) => {
    setFeedbackLoading(true);
    setFeedbackStats(null);
    try {
      const res = await fetch(
        `${API}/api/admin/tutor/feedback-stats?projectId=${encodeURIComponent(projectId)}&limit=5`,
        { headers: authHeaders() },
      );
      if (res.ok) setFeedbackStats(await res.json());
    } catch {
      /* silent — feedback is auxiliary, no toast spam */
    }
    setFeedbackLoading(false);
  };

  const toggleCompany = (name) => {
    setExpandedCompanies(prev => ({ ...prev, [name]: !prev[name] }));
  };

  // Course detail view
  if (selectedCourse && courseDetail) {
    return (
      <div className="space-y-6" data-testid="tutor-course-detail">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => { setSelectedCourse(null); setCourseDetail(null); setFeedbackStats(null); }} data-testid="back-to-dashboard">
            <ArrowLeft className="w-4 h-4 mr-1" /> Voltar
          </Button>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-blue-400" />
            {courseDetail.courseName}
          </h2>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 gap-4">
          <Card className="bg-slate-900/50 border-slate-800">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-blue-400">{courseDetail.totalQuestions}</p>
              <p className="text-xs text-slate-400">Total de Perguntas</p>
            </CardContent>
          </Card>
          <Card className="bg-slate-900/50 border-slate-800">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-emerald-400">{courseDetail.uniqueQuestions}</p>
              <p className="text-xs text-slate-400">Perguntas Unicas</p>
            </CardContent>
          </Card>
        </div>

        {/* Top questions ranking */}
        <Card className="bg-slate-900/50 border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-amber-400" />
              Perguntas Mais Frequentes
            </CardTitle>
          </CardHeader>
          <CardContent>
            {courseDetail.topQuestions?.length > 0 ? (
              <div className="space-y-2">
                {courseDetail.topQuestions.map((q, i) => (
                  <div key={q.id || q.question || `q-${i}`} className="flex items-start gap-3 py-2 border-b border-slate-800 last:border-0">
                    <span className={`shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                      i < 3 ? 'bg-amber-600/20 text-amber-300' : 'bg-slate-700 text-slate-400'
                    }`}>
                      {i + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-white leading-relaxed">{q.question}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge className="text-[10px] bg-blue-600/15 text-blue-300">
                          <Hash className="w-2.5 h-2.5 mr-0.5" />{q.count}x
                        </Badge>
                        {q.lastAsked && (
                          <span className="text-[10px] text-slate-500">
                            Ultima: {new Date(q.lastAsked).toLocaleDateString('pt-BR')}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500 text-center py-4">Nenhuma pergunta registrada</p>
            )}
          </CardContent>
        </Card>

        {/* Student feedback (👍/👎) — aggregated from the in-widget
            ratings students give to assistant answers. Shows up only if
            there's at least one rating; until then we render a friendly
            empty state telling the author where this data comes from. */}
        <Card className="bg-slate-900/50 border-slate-800" data-testid="tutor-feedback-panel">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Smile className="w-4 h-4 text-emerald-400" />
              Feedback dos Alunos
              {feedbackLoading && <Loader2 className="w-3 h-3 ml-auto animate-spin text-slate-500" />}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!feedbackLoading && feedbackStats && feedbackStats.ratedTotal === 0 && (
              <div className="text-center py-6 space-y-1">
                <p className="text-sm text-slate-400" data-testid="feedback-empty-state">
                  Ainda não há avaliações dos alunos para este curso.
                </p>
                <p className="text-xs text-slate-500">
                  Após exportar e os alunos abrirem o curso, eles podem clicar em 👍 ou 👎
                  em cada resposta do Tutor IA. Os dados aparecem aqui.
                </p>
              </div>
            )}

            {!feedbackLoading && feedbackStats && feedbackStats.ratedTotal > 0 && (
              <div className="space-y-4" data-testid="feedback-stats-loaded">
                {/* KPI tiles */}
                <div className="grid grid-cols-3 gap-2">
                  <div className="bg-emerald-600/10 border border-emerald-600/30 rounded-lg p-3 text-center" data-testid="kpi-thumbs-up">
                    <div className="flex items-center justify-center gap-1 text-emerald-300">
                      <ThumbsUp className="w-3.5 h-3.5" />
                      <span className="text-xl font-bold">{feedbackStats.upTotal}</span>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-1 uppercase tracking-wide">positivos</p>
                  </div>
                  <div className="bg-rose-600/10 border border-rose-600/30 rounded-lg p-3 text-center" data-testid="kpi-thumbs-down">
                    <div className="flex items-center justify-center gap-1 text-rose-300">
                      <ThumbsDown className="w-3.5 h-3.5" />
                      <span className="text-xl font-bold">{feedbackStats.downTotal}</span>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-1 uppercase tracking-wide">negativos</p>
                  </div>
                  <div className="bg-indigo-600/10 border border-indigo-600/30 rounded-lg p-3 text-center" data-testid="kpi-satisfaction">
                    <div className="text-xl font-bold text-indigo-300">{feedbackStats.satisfactionPct}%</div>
                    <p className="text-[10px] text-slate-400 mt-1 uppercase tracking-wide">satisfação</p>
                  </div>
                </div>

                {/* Satisfaction bar — visual cue alongside the % tile */}
                <div className="space-y-1">
                  <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden flex">
                    <div
                      className="h-full bg-emerald-500"
                      style={{ width: `${(feedbackStats.upTotal / feedbackStats.ratedTotal) * 100}%` }}
                      data-testid="satisfaction-bar-positive"
                    />
                    <div
                      className="h-full bg-rose-500"
                      style={{ width: `${(feedbackStats.downTotal / feedbackStats.ratedTotal) * 100}%` }}
                      data-testid="satisfaction-bar-negative"
                    />
                  </div>
                  <p className="text-[10px] text-slate-500 text-right">
                    {feedbackStats.ratedTotal} {feedbackStats.ratedTotal === 1 ? 'avaliação' : 'avaliações'} no total
                  </p>
                </div>

                {/* Top NEGATIVE questions — the actionable signal: which
                    answers are consistently rated bad. Author should
                    refine the systemPrompt or the slide content. */}
                {feedbackStats.topNegative && feedbackStats.topNegative.length > 0 && (
                  <div data-testid="top-negative-list">
                    <h5 className="text-xs font-semibold uppercase tracking-wide text-rose-300 mb-2 flex items-center gap-1">
                      <ThumbsDown className="w-3 h-3" /> Respostas que receberam 👎
                    </h5>
                    <div className="space-y-2">
                      {feedbackStats.topNegative.map((q, i) => (
                        <div
                          key={`neg-${i}`}
                          className="p-3 bg-rose-950/20 border border-rose-900/30 rounded-lg space-y-1"
                          data-testid={`negative-item-${i}`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <p className="text-sm text-white flex-1">{q.question}</p>
                            <Badge className="text-[10px] bg-rose-600/20 text-rose-300 shrink-0">
                              <ThumbsDown className="w-2.5 h-2.5 mr-0.5" />{q.down}x
                            </Badge>
                          </div>
                          {q.lastAnswer && (
                            <p className="text-[11px] text-slate-400 line-clamp-2 italic">
                              &ldquo;{q.lastAnswer}&rdquo;
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Top POSITIVE — secondary, just for completeness */}
                {feedbackStats.topPositive && feedbackStats.topPositive.length > 0 && (
                  <div data-testid="top-positive-list">
                    <h5 className="text-xs font-semibold uppercase tracking-wide text-emerald-300 mb-2 flex items-center gap-1">
                      <ThumbsUp className="w-3 h-3" /> Respostas que receberam 👍
                    </h5>
                    <div className="space-y-1.5">
                      {feedbackStats.topPositive.slice(0, 3).map((q, i) => (
                        <div
                          key={`pos-${i}`}
                          className="px-3 py-2 bg-emerald-950/20 border border-emerald-900/30 rounded-md flex items-center justify-between gap-2"
                          data-testid={`positive-item-${i}`}
                        >
                          <p className="text-xs text-slate-200 flex-1 truncate">{q.question}</p>
                          <Badge className="text-[10px] bg-emerald-600/20 text-emerald-300 shrink-0">
                            <ThumbsUp className="w-2.5 h-2.5 mr-0.5" />{q.up}x
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent interactions */}
        <Card className="bg-slate-900/50 border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Clock className="w-4 h-4 text-slate-400" />
              Interacoes Recentes
              <Badge className="ml-auto text-[10px] bg-slate-700 text-slate-300" data-testid="recent-interactions-count">
                {courseDetail.recentLogs?.length || 0}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Native overflow scroll: shadcn ScrollArea ignored `max-h-*` here
                because Radix needs a FIXED height. Native scroll respects
                `max-h` and shows the scrollbar exactly when content overflows. */}
            <div
              className="max-h-[60vh] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-slate-900"
              data-testid="recent-interactions-scroll"
            >
              <div className="space-y-3">
                {courseDetail.recentLogs?.map((log, i) => (
                  <div key={log.id || log.timestamp || `log-${i}`} className="p-3 bg-slate-800/50 rounded-lg space-y-2">
                    <div className="flex items-start gap-2">
                      <HelpCircle className="w-4 h-4 text-blue-400 mt-0.5 shrink-0" />
                      <p className="text-sm text-white">{log.question}</p>
                    </div>
                    {log.response && (
                      <p className="text-xs text-slate-400 ml-6 line-clamp-3">{log.response}</p>
                    )}
                    <p className="text-[10px] text-slate-500 ml-6">
                      {log.createdAt ? new Date(log.createdAt).toLocaleString('pt-BR') : ''}
                    </p>
                  </div>
                ))}
                {(!courseDetail.recentLogs || courseDetail.recentLogs.length === 0) && (
                  <p className="text-sm text-slate-500 text-center py-4">Nenhuma interacao registrada</p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Main dashboard view
  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
      </div>
    );
  }

  if (!dashboard) {
    return (
      <Card className="bg-slate-900/50 border-slate-800">
        <CardContent className="p-8 text-center">
          <MessageSquare className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400">Erro ao carregar dashboard</p>
          <Button variant="outline" size="sm" onClick={fetchDashboard} className="mt-3">
            <RefreshCw className="w-4 h-4 mr-1" /> Tentar novamente
          </Button>
        </CardContent>
      </Card>
    );
  }

  const filteredCourses = searchQuery
    ? dashboard.courses.filter(c =>
        c.courseName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.companyName.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : dashboard.courses;

  return (
    <div className="space-y-6" data-testid="tutor-dashboard">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-blue-400" />
          Dashboard do Tutor IA
        </h2>
        <Button variant="outline" size="sm" onClick={fetchDashboard} disabled={loading} data-testid="refresh-tutor-dashboard">
          <RefreshCw className={`w-4 h-4 mr-1 ${loading ? 'animate-spin' : ''}`} /> Atualizar
        </Button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="bg-slate-900/50 border-slate-800">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-blue-400">{dashboard.totalQuestions}</p>
            <p className="text-xs text-slate-400 mt-1">Total de Perguntas</p>
          </CardContent>
        </Card>
        <Card className="bg-slate-900/50 border-slate-800">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-emerald-400">{dashboard.totalCourses}</p>
            <p className="text-xs text-slate-400 mt-1">Cursos com Perguntas</p>
          </CardContent>
        </Card>
        <Card className="bg-slate-900/50 border-slate-800">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-amber-400">{dashboard.companies?.length || 0}</p>
            <p className="text-xs text-slate-400 mt-1">Empresas Ativas</p>
          </CardContent>
        </Card>
      </div>

      {dashboard.totalQuestions === 0 ? (
        <Card className="bg-slate-900/50 border-slate-800">
          <CardContent className="p-8 text-center">
            <MessageSquare className="w-10 h-10 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-400">Nenhuma pergunta registrada no Tutor IA ainda.</p>
            <p className="text-xs text-slate-500 mt-2">
              As perguntas dos alunos serao exibidas aqui conforme interagirem com o Tutor nos cursos exportados.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Company breakdown (Super Admin only) */}
          {isSuperAdmin && dashboard.companies?.length > 0 && (
            <Card className="bg-slate-900/50 border-slate-800" data-testid="tutor-companies-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-amber-400" />
                  Perguntas por Empresa
                  {dashboard.totalCostUSD != null && (
                    <Badge className="ml-auto bg-emerald-600/15 text-emerald-300 text-[10px]" data-testid="tutor-total-cost-badge">
                      Custo total: US$ {dashboard.totalCostUSD.toFixed(4)} · R$ {dashboard.totalCostBRL?.toFixed(2)}
                    </Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {dashboard.companies.map((c, i) => {
                    const isExpanded = !!expandedCompanies[c.name];
                    return (
                      <div key={c.name || `company-${i}`} className="bg-slate-800/50 rounded-lg overflow-hidden" data-testid={`tutor-company-row-${i}`}>
                        <div
                          className="flex items-center justify-between p-3 cursor-pointer hover:bg-slate-800 transition-colors"
                          onClick={() => toggleCompany(c.name)}
                          data-testid={`tutor-company-toggle-${i}`}
                        >
                          <div className="flex items-center gap-3 flex-1 min-w-0">
                            <Building2 className="w-4 h-4 text-slate-400 shrink-0" />
                            <span className="text-sm font-medium truncate">{c.name}</span>
                            <Badge className="text-[10px] bg-blue-600/15 text-blue-300 shrink-0">{c.courses} curso{c.courses !== 1 ? 's' : ''}</Badge>
                          </div>
                          <div className="flex items-center gap-3 shrink-0">
                            {c.totalCostUSD != null && c.totalCostUSD > 0 && (
                              <span className="text-xs text-emerald-300/90 font-mono" data-testid={`tutor-company-cost-${i}`}>
                                R$ {c.totalCostBRL?.toFixed(2)}
                              </span>
                            )}
                            <span className="text-sm font-semibold text-amber-300">{c.totalQuestions} perguntas</span>
                            {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                          </div>
                        </div>

                        {/* Expanded: courses with their questions */}
                        {isExpanded && (
                          <div className="border-t border-slate-700/60 p-3 space-y-3 bg-slate-900/40" data-testid={`tutor-company-expanded-${i}`}>
                            {(c.courseList || []).length === 0 ? (
                              <p className="text-xs text-slate-500 italic">Nenhum curso encontrado.</p>
                            ) : (
                              c.courseList.map((cs, ci) => (
                                <div key={cs.projectId || ci} className="bg-slate-800/40 rounded-md p-3 space-y-2">
                                  <div className="flex items-center justify-between gap-2 flex-wrap">
                                    <div className="flex items-center gap-2 min-w-0">
                                      <BookOpen className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                                      <span className="text-xs font-medium truncate">{cs.courseName}</span>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0 flex-wrap">
                                      {cs.feedbackSummary && (cs.feedbackSummary.upTotal > 0 || cs.feedbackSummary.downTotal > 0) && (
                                        <div className="flex items-center gap-1" data-testid={`tutor-company-${i}-course-${ci}-feedback-inline`}>
                                          <Badge className="text-[10px] bg-emerald-600/15 text-emerald-300 px-1.5 py-0.5">
                                            <ThumbsUp className="w-2.5 h-2.5 mr-0.5" />{cs.feedbackSummary.upTotal}
                                          </Badge>
                                          <Badge className="text-[10px] bg-rose-600/15 text-rose-300 px-1.5 py-0.5">
                                            <ThumbsDown className="w-2.5 h-2.5 mr-0.5" />{cs.feedbackSummary.downTotal}
                                          </Badge>
                                          {cs.feedbackSummary.satisfactionPct !== null && (
                                            <Badge className="text-[10px] bg-indigo-600/15 text-indigo-300 px-1.5 py-0.5">
                                              {cs.feedbackSummary.satisfactionPct}% sat.
                                            </Badge>
                                          )}
                                        </div>
                                      )}
                                      {cs.totalCostUSD > 0 && (
                                        <Badge className="text-[10px] bg-emerald-600/10 text-emerald-300">
                                          US$ {cs.totalCostUSD.toFixed(4)}
                                        </Badge>
                                      )}
                                      <Badge className="text-[10px] bg-blue-600/15 text-blue-300">{cs.totalQuestions} perguntas</Badge>
                                      {cs.projectId && (
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          className="h-7 px-2.5 text-[10px] border-blue-500/40 text-blue-300 hover:bg-blue-500/10 hover:text-blue-200"
                                          onClick={(ev) => { ev.stopPropagation(); fetchCourseDetail(cs.projectId); }}
                                          data-testid={`tutor-company-${i}-course-${ci}-detail`}
                                        >
                                          Ver detalhes →
                                        </Button>
                                      )}
                                    </div>
                                  </div>

                                  {/* Top questions inline */}
                                  {(cs.topQuestions || []).length > 0 && (
                                    <div className="space-y-1">
                                      <p className="text-[10px] uppercase tracking-wide text-slate-500">Mais perguntadas</p>
                                      {cs.topQuestions.map((q, qi) => (
                                        <div key={qi} className="flex items-start gap-2 text-xs">
                                          <span className={`w-5 text-center font-bold shrink-0 ${qi === 0 ? 'text-amber-400' : 'text-slate-500'}`}>{qi + 1}.</span>
                                          <span className="text-slate-300 flex-1 break-words">{q.question}</span>
                                          <Badge className="text-[9px] bg-blue-600/10 text-blue-300 shrink-0">{q.count}x</Badge>
                                        </div>
                                      ))}
                                    </div>
                                  )}

                                  {/* Recent timeline (last 5) */}
                                  {(cs.recentQuestions || []).length > 0 && (
                                    <details className="text-xs">
                                      <summary className="cursor-pointer text-slate-400 hover:text-slate-200 select-none">
                                        Perguntas recentes ({cs.recentQuestions.length})
                                      </summary>
                                      <div className="mt-2 space-y-1 max-h-60 overflow-y-auto pr-1">
                                        {cs.recentQuestions.slice(0, 10).map((q, qi) => (
                                          <div key={qi} className="border-l-2 border-slate-700 pl-2 py-1">
                                            <p className="text-slate-200 break-words">{q.question}</p>
                                            <p className="text-[10px] text-slate-500 mt-0.5">
                                              {q.createdAt ? new Date(q.createdAt).toLocaleString('pt-BR') : ''}
                                              {q.estimatedCostUSD != null && q.estimatedCostUSD > 0 && (
                                                <span className="ml-2 text-emerald-400/80">· US$ {q.estimatedCostUSD.toFixed(6)}</span>
                                              )}
                                            </p>
                                          </div>
                                        ))}
                                      </div>
                                    </details>
                                  )}
                                </div>
                              ))
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Search */}
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Buscar por curso ou empresa..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-slate-900/50 border border-slate-800 rounded-lg pl-10 pr-4 py-2.5 text-sm text-white placeholder:text-slate-500 focus:border-blue-500 focus:outline-none"
              data-testid="tutor-dashboard-search"
            />
          </div>

          {/* Courses list */}
          <div className="space-y-3">
            {filteredCourses.map((course, i) => (
              <Card key={course.projectId || course.title || `course-${i}`} className="bg-slate-900/50 border-slate-800 hover:border-blue-700/40 transition-colors cursor-pointer" onClick={() => course.projectId && fetchCourseDetail(course.projectId)}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <BookOpen className="w-4 h-4 text-blue-400 shrink-0" />
                        <span className="text-sm font-medium truncate">{course.courseName}</span>
                        {course.companyName && (
                          <Badge className="text-[10px] bg-slate-700 text-slate-300 shrink-0">{course.companyName}</Badge>
                        )}
                      </div>

                      {/* Top 3 questions inline */}
                      <div className="space-y-1 mt-2">
                        {course.topQuestions?.slice(0, 3).map((q, qi) => (
                          <div key={qi} className="flex items-center gap-2 text-xs">
                            <span className={`w-5 text-center font-bold ${qi === 0 ? 'text-amber-400' : 'text-slate-500'}`}>{qi + 1}.</span>
                            <span className="text-slate-300 truncate flex-1">{q.question}</span>
                            <Badge className="text-[9px] bg-blue-600/10 text-blue-300 shrink-0">{q.count}x</Badge>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="text-right shrink-0 ml-4">
                      <p className="text-lg font-bold text-blue-400">{course.totalQuestions}</p>
                      <p className="text-[10px] text-slate-500">perguntas</p>
                      <p className="text-[10px] text-slate-500 mt-1">{course.uniqueQuestions} unicas</p>
                      {course.feedbackSummary && (course.feedbackSummary.upTotal > 0 || course.feedbackSummary.downTotal > 0) && (
                        <div className="mt-2 flex flex-col items-end gap-0.5" data-testid={`tutor-search-card-feedback-${course.projectId}`}>
                          <div className="flex items-center gap-1">
                            <span className="text-[10px] text-emerald-300 flex items-center gap-0.5">
                              <ThumbsUp className="w-2.5 h-2.5" />{course.feedbackSummary.upTotal}
                            </span>
                            <span className="text-[10px] text-rose-300 flex items-center gap-0.5">
                              <ThumbsDown className="w-2.5 h-2.5" />{course.feedbackSummary.downTotal}
                            </span>
                          </div>
                          {course.feedbackSummary.satisfactionPct !== null && (
                            <p className="text-[9px] text-indigo-300">{course.feedbackSummary.satisfactionPct}% sat.</p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
