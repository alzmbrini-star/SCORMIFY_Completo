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
  ChevronDown, ChevronUp, Search, Hash,
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
  };

  const toggleCompany = (name) => {
    setExpandedCompanies(prev => ({ ...prev, [name]: !prev[name] }));
  };

  // Course detail view
  if (selectedCourse && courseDetail) {
    return (
      <div className="space-y-6" data-testid="tutor-course-detail">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => { setSelectedCourse(null); setCourseDetail(null); }} data-testid="back-to-dashboard">
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

        {/* Recent interactions */}
        <Card className="bg-slate-900/50 border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Clock className="w-4 h-4 text-slate-400" />
              Interacoes Recentes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="max-h-[400px]">
              <div className="space-y-3">
                {courseDetail.recentLogs?.map((log, i) => (
                  <div key={log.id || log.timestamp || `log-${i}`} className="p-3 bg-slate-800/50 rounded-lg space-y-2">
                    <div className="flex items-start gap-2">
                      <HelpCircle className="w-4 h-4 text-blue-400 mt-0.5 shrink-0" />
                      <p className="text-sm text-white">{log.question}</p>
                    </div>
                    {log.response && (
                      <p className="text-xs text-slate-400 ml-6 line-clamp-2">{log.response}</p>
                    )}
                    <p className="text-[10px] text-slate-500 ml-6">
                      {log.createdAt ? new Date(log.createdAt).toLocaleString('pt-BR') : ''}
                    </p>
                  </div>
                ))}
              </div>
            </ScrollArea>
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
            <Card className="bg-slate-900/50 border-slate-800">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-amber-400" />
                  Perguntas por Empresa
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {dashboard.companies.map((c, i) => (
                    <div key={c.name || `company-${i}`}
                      className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg cursor-pointer hover:bg-slate-800 transition-colors"
                      onClick={() => toggleCompany(c.name)}
                    >
                      <div className="flex items-center gap-3">
                        <Building2 className="w-4 h-4 text-slate-400" />
                        <span className="text-sm font-medium">{c.name}</span>
                        <Badge className="text-[10px] bg-blue-600/15 text-blue-300">{c.courses} curso{c.courses !== 1 ? 's' : ''}</Badge>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-semibold text-amber-300">{c.totalQuestions} perguntas</span>
                        {expandedCompanies[c.name] ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                      </div>
                    </div>
                  ))}
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
