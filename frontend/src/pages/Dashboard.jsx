import React, { useEffect, useState, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../contexts/ProjectContext';
import { useTheme } from '../contexts/ThemeContext';
import { useAuth } from '../contexts/AuthContext';
import { getApiUrl } from '../utils/apiUrl';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
  DialogFooter,
} from '../components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '../components/ui/dropdown-menu';
import { Progress } from '../components/ui/progress';
import { toast } from 'sonner';
import CompanySelector from '../components/CompanySelector';
import {
  Plus,
  Upload,
  FolderOpen,
  Trash2,
  MoreVertical,
  Sun,
  Moon,
  Presentation,
  Clock,
  Loader2,
  Settings,
  KeyRound,
  LogOut,
  User,
  Pencil,
  Brain,
  BookOpen,
  Layers,
  Download,
  Filter,
  Search,
  X,
  Copy,
} from 'lucide-react';
import axios from 'axios';
import TutorialImportDialog from '../components/dashboard/TutorialImportDialog';

// Pure helper to parse an ISO date string into a millisecond timestamp.
// Lives outside the component so `useMemo` filter logic stays pure under
// strict hooks/purity lint rules. Returns 0 for invalid/empty input —
// callers compare `>= cutoff`, so 0 just excludes the project from
// recency filters (legacy/seed data without createdAt).
const isoToMs = (iso) => {
  if (!iso) return 0;
  const n = Date.parse(iso);
  return Number.isFinite(n) ? n : 0;
};

export default function Dashboard() {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const { user, logout, isCompanyAdmin, isSuperAdmin, hasPermission } = useAuth();
  const {
    projects,
    loading,
    fetchProjects,
    createProject,
    updateProject,
    deleteProject,
    uploadPPT,
    checkJobStatus,
  } = useProject();

  // Check if user has access to AI Agent
  const hasAgentAccess = isSuperAdmin || hasPermission('agentAccess');

  const [showNewProjectDialog, setShowNewProjectDialog] = useState(false);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [showTutorialImport, setShowTutorialImport] = useState(false);
  const [showRenameDialog, setShowRenameDialog] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectCompanyId, setNewProjectCompanyId] = useState('');
  const [uploadCompanyId, setUploadCompanyId] = useState('');
  const [renameProjectId, setRenameProjectId] = useState(null);
  const [renameProjectName, setRenameProjectName] = useState('');
  const [renameProjectCompanyId, setRenameProjectCompanyId] = useState('');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [processingJobId, setProcessingJobId] = useState(null);
  const [processingStatus, setProcessingStatus] = useState('');
  const fileInputRef = useRef(null);
  const API_URL = getApiUrl();

  // Dashboard metrics
  const [metrics, setMetrics] = useState(null);

  // 2026-05-27: Super-admin filters for the projects grid (company + date
  // recency). Hidden for non-super-admin users — those only see their own
  // company anyway, so a filter would be redundant.
  const [filterCompanyId, setFilterCompanyId] = useState('all');
  const [filterDateRange, setFilterDateRange] = useState('all'); // all | 7d | 30d | 90d
  const [companiesList, setCompaniesList] = useState([]);

  // 2026-06-01: Search by project name. Available to ALL roles (not just
  // super admin) — even within a single company the catalog grows large
  // and finding a specific course by scrolling is painful. Debounced
  // (250ms) so typing stays snappy while filtering large project lists.
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  useEffect(() => {
    const t = setTimeout(() => setSearchQuery(searchInput.trim().toLowerCase()), 250);
    return () => clearTimeout(t);
  }, [searchInput]);

  // Recency cutoff for date filter — bound to filter changes via useMemo
  // (pure: same `filterDateRange` => same `cutoffMs`). For our "last N
  // days" semantics, staleness within a single browser session is fine;
  // user re-opens the filter to force a refresh if needed.
  const cutoffMs = useMemo(() => {
    if (filterDateRange === 'all') return 0;
    const days = parseInt(filterDateRange, 10);
    if (!Number.isFinite(days) || days <= 0) return 0;
    return Date.now() - days * 24 * 60 * 60 * 1000;
  }, [filterDateRange]);

  useEffect(() => {
    if (!isSuperAdmin) return;
    axios.get(`${API_URL}/api/companies`)
      .then(res => setCompaniesList(Array.isArray(res.data) ? res.data : (res.data?.companies || [])))
      .catch(() => setCompaniesList([]));
  }, [isSuperAdmin, API_URL]);

  // Apply client-side filtering for the grid.
  const filteredProjects = useMemo(() => {
    let list = [...(projects || [])];
    // Name search — match against project.name AND course.metadata.title
    // so titles tweaked only on the course (without renaming the project)
    // still surface in search results.
    if (searchQuery) {
      list = list.filter((p) => {
        const n = (p.name || '').toLowerCase();
        const t = ((p.course && p.course.metadata && p.course.metadata.title) || '').toLowerCase();
        return n.includes(searchQuery) || t.includes(searchQuery);
      });
    }
    if (isSuperAdmin && filterCompanyId !== 'all') {
      if (filterCompanyId === '__none__') {
        list = list.filter(p => !p.companyId);
      } else {
        list = list.filter(p => p.companyId === filterCompanyId);
      }
    }
    if (cutoffMs > 0) {
      list = list.filter(p => isoToMs(p.createdAt || p.updatedAt) >= cutoffMs);
    }
    // Always sort by most recent first when a recency filter is on, so the
    // "criados recentemente" view feels right.
    list.sort((a, b) => {
      const ta = new Date(a.createdAt || a.updatedAt || 0).getTime();
      const tb = new Date(b.createdAt || b.updatedAt || 0).getTime();
      return tb - ta;
    });
    return list;
  }, [projects, isSuperAdmin, filterCompanyId, cutoffMs, searchQuery]);

  useEffect(() => {
    fetchProjects();
    // Fetch dashboard metrics
    axios.get(`${API_URL}/api/dashboard/metrics`)
      .then(res => setMetrics(res.data))
      .catch(() => {});
  }, [fetchProjects, API_URL]);

  useEffect(() => {
    let interval;
    let errorCount = 0;
    const MAX_ERRORS = 15; // tolerate ~15s of downtime (polling every 1s)
    if (processingJobId) {
      interval = setInterval(async () => {
        try {
          const status = await checkJobStatus(processingJobId);
          errorCount = 0; // reset on success
          setProcessingStatus(status.message);
          setUploadProgress(status.progress);

          if (status.status === 'completed') {
            clearInterval(interval);
            setProcessingJobId(null);
            setShowUploadDialog(false);
            toast.success('PowerPoint imported successfully!');
            fetchProjects();
            if (status.result?.projectId) {
              navigate(`/editor/${status.result.projectId}`);
            }
          } else if (status.status === 'failed') {
            clearInterval(interval);
            setProcessingJobId(null);
            toast.error(`Import failed: ${status.message}`);
          }
        } catch (err) {
          errorCount++;
          const httpStatus = err.response?.status;
          if (httpStatus === 502 || httpStatus === 503 || httpStatus === 504) {
            setProcessingStatus('Servidor reiniciando, aguarde...');
          }
          if (errorCount >= MAX_ERRORS) {
            clearInterval(interval);
            setProcessingJobId(null);
            setUploadProgress(0);
            setProcessingStatus('');
            toast.error('Servidor indisponivel. Recarregue a pagina e tente novamente.');
          }
        }
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [processingJobId, checkJobStatus, fetchProjects, navigate]);

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) {
      toast.error('Please enter a project name');
      return;
    }
    try {
      const project = await createProject(newProjectName.trim(), '', newProjectCompanyId || null);
      setShowNewProjectDialog(false);
      setNewProjectName('');
      setNewProjectCompanyId('');
      toast.success('Project created!');
      navigate(`/editor/${project.id}`);
    } catch (err) {
      toast.error('Failed to create project');
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pptx') && !file.name.toLowerCase().endsWith('.ppt')) {
      toast.error('Please upload a PPT or PPTX file');
      return;
    }

    try {
      setUploadProgress(10);
      setProcessingStatus('Uploading file...');
      const result = await uploadPPT(file, undefined, uploadCompanyId || null);
      setProcessingJobId(result.jobId);
      setUploadProgress(30);
      setProcessingStatus('Processing PowerPoint...');
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail || err.message || 'Erro desconhecido';
      if (status === 410 || status === 404) {
        toast.error('O servidor reiniciou durante o upload. Por favor, tente importar novamente.');
      } else {
        toast.error(`Falha no upload: ${detail}`);
      }
      setUploadProgress(0);
      setProcessingStatus('');
      setProcessingJobId(null);
      setShowUploadDialog(false);
    }
  };

  const handleDeleteProject = async (projectId, e) => {
    e.stopPropagation();
    if (window.confirm('Tem certeza que deseja excluir este projeto? Esta ação não pode ser desfeita.')) {
      try {
        await deleteProject(projectId);
        toast.success('Projeto excluído com sucesso!');
      } catch (err) {
        toast.error('Erro ao excluir projeto');
      }
    }
  };

  const handleOpenRenameDialog = (project, e) => {
    e.stopPropagation();
    setRenameProjectId(project.id);
    setRenameProjectName(project.name);
    setRenameProjectCompanyId(project.companyId || '');
    setShowRenameDialog(true);
  };

  const handleDuplicateProject = async (projectId, e) => {
    // Admin-only feature — the DropdownMenuItem is only rendered for
    // super_admin/company_admin, but the backend also enforces RBAC.
    e.stopPropagation();
    const tId = toast.loading('Duplicando curso...');
    try {
      const res = await axios.post(
        `${API_URL}/api/projects/${projectId}/duplicate`,
        {},
      );
      const dup = res.data;
      toast.dismiss(tId);
      toast.success(`"${dup.name}" criado com sucesso!`);
      // Reload the project list so the duplicate appears immediately.
      await fetchProjects();
    } catch (err) {
      toast.dismiss(tId);
      const msg = err.response?.data?.detail || err.message;
      toast.error(`Erro ao duplicar: ${msg}`);
    }
  };

  const handleRenameProject = async () => {
    if (!renameProjectName.trim()) {
      toast.error('Por favor, insira um nome para o projeto');
      return;
    }
    try {
      const payload = { name: renameProjectName.trim() };
      // Only super_admin can change companyId — backend silently drops it for others.
      // We send only when changed to avoid noisy PUTs.
      if (isSuperAdmin && renameProjectCompanyId) {
        payload.companyId = renameProjectCompanyId;
      }
      await updateProject(renameProjectId, payload);
      setShowRenameDialog(false);
      setRenameProjectId(null);
      setRenameProjectName('');
      setRenameProjectCompanyId('');
      toast.success('Projeto atualizado com sucesso!');
    } catch (err) {
      toast.error('Erro ao atualizar projeto');
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="glass sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <img 
              src="/didaxis-logo.png" 
              alt="Didaxis" 
              className="h-14 object-contain"
            />
            <div className="h-10 w-px bg-border" />
            <h1 className="text-2xl font-bold tracking-tight">Scormify</h1>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              className="rounded-full"
              data-testid="theme-toggle"
            >
              {theme === 'dark' ? (
                <Sun className="w-5 h-5" />
              ) : (
                <Moon className="w-5 h-5" />
              )}
            </Button>
            
            {/* User Menu */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="gap-2" data-testid="user-menu-btn">
                  {user?.picture ? (
                    <img src={user.picture} alt={user.name} className="w-6 h-6 rounded-full" />
                  ) : (
                    <User className="w-5 h-5" />
                  )}
                  <span className="hidden sm:inline">{user?.name}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem disabled className="text-muted-foreground text-xs">
                  {user?.email}
                </DropdownMenuItem>
                {user?.company && (
                  <DropdownMenuItem disabled className="text-muted-foreground text-xs">
                    {user.company.name}
                  </DropdownMenuItem>
                )}
                <div className="h-px bg-border my-1" />
                {isCompanyAdmin && (
                  <DropdownMenuItem onClick={() => navigate('/admin')}>
                    <Settings className="w-4 h-4 mr-2" />
                    Administração
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem onClick={() => navigate('/change-password')}>
                  <KeyRound className="w-4 h-4 mr-2" />
                  Trocar senha
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={logout} className="text-red-500">
                  <LogOut className="w-4 h-4 mr-2" />
                  Sair
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Metrics Cards */}
        {metrics && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8" data-testid="dashboard-metrics">
            <Card className="border-border/50 bg-card/80 backdrop-blur-sm hover:border-primary/30 transition-colors">
              <CardContent className="p-5 flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                  <BookOpen className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Cursos Criados</p>
                  <p className="text-2xl font-bold" data-testid="metric-courses">{metrics.totalCourses}</p>
                </div>
              </CardContent>
            </Card>
            <Card className="border-border/50 bg-card/80 backdrop-blur-sm hover:border-amber-500/30 transition-colors">
              <CardContent className="p-5 flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-amber-500/10 flex items-center justify-center shrink-0">
                  <Layers className="w-6 h-6 text-amber-500" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Total de Slides</p>
                  <p className="text-2xl font-bold" data-testid="metric-slides">{metrics.totalSlides}</p>
                </div>
              </CardContent>
            </Card>
            <Card className="border-border/50 bg-card/80 backdrop-blur-sm hover:border-emerald-500/30 transition-colors">
              <CardContent className="p-5 flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center shrink-0">
                  <Download className="w-6 h-6 text-emerald-500" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Exportacoes</p>
                  <p className="text-2xl font-bold" data-testid="metric-exports">{metrics.totalExports}</p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Hero Section */}
        <div className="gradient-hero rounded-2xl p-8 mb-8">
          <h2 className="text-3xl font-bold mb-2">Welcome to Scormify</h2>
          <p className="text-muted-foreground mb-6">
            Convert your PowerPoint presentations to SCORM 1.2 packages
          </p>
          <div className="flex gap-4">
            <Dialog open={showNewProjectDialog} onOpenChange={setShowNewProjectDialog}>
              <DialogTrigger asChild>
                <Button className="btn-primary gap-2" data-testid="new-project-btn">
                  <Plus className="w-4 h-4" />
                  New Project
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create New Project</DialogTitle>
                  <DialogDescription>Crie um novo projeto em branco para comecar a editar.</DialogDescription>
                </DialogHeader>
                <div className="py-4 space-y-4">
                  <Input
                    placeholder="Project name"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleCreateProject()}
                    data-testid="project-name-input"
                  />
                  <CompanySelector
                    value={newProjectCompanyId}
                    onChange={setNewProjectCompanyId}
                    testIdPrefix="new-project-company"
                  />
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setShowNewProjectDialog(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleCreateProject} data-testid="create-project-btn">
                    Create
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            <Dialog open={showUploadDialog} onOpenChange={setShowUploadDialog}>
              <DialogTrigger asChild>
                <Button variant="outline" className="gap-2" data-testid="upload-ppt-btn">
                  <Upload className="w-4 h-4" />
                  Import PPT
                </Button>
              </DialogTrigger>

            {/* AI Agent Button - only visible to users with access */}
            {hasAgentAccess && (
              <Button
                variant="outline"
                className="gap-2 border-emerald-600/40 text-emerald-400 hover:bg-emerald-600/10 hover:text-emerald-300"
                onClick={() => navigate('/agent')}
                data-testid="ai-agent-btn"
              >
                <Brain className="w-4 h-4" />
                Agente IA
              </Button>
            )}

            {/* Tutorial Import Button - import step-by-step tutorials from
                the external Auto-Instructor agent. */}
            <Button
              variant="outline"
              className="gap-2 border-cyan-600/40 text-cyan-300 hover:bg-cyan-600/10"
              onClick={() => setShowTutorialImport(true)}
              data-testid="tutorial-import-btn"
            >
              <Download className="w-4 h-4" />
              Importar Tutorial
            </Button>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Import PowerPoint</DialogTitle>
                  <DialogDescription>Importe um arquivo .ppt ou .pptx para converter em curso.</DialogDescription>
                </DialogHeader>
                <div className="py-6">
                  {processingJobId ? (
                    <div className="space-y-4">
                      <div className="flex items-center gap-3">
                        <Loader2 className="w-5 h-5 animate-spin text-primary" />
                        <span>{processingStatus}</span>
                      </div>
                      <Progress value={uploadProgress} className="h-2" />
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <CompanySelector
                        value={uploadCompanyId}
                        onChange={setUploadCompanyId}
                        testIdPrefix="upload-company"
                      />
                      <div
                        className="border-2 border-dashed border-border rounded-xl p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
                        onClick={() => fileInputRef.current?.click()}
                      >
                        <Upload className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                        <p className="text-muted-foreground mb-2">
                          Drag & drop or click to upload
                        </p>
                        <p className="text-sm text-muted-foreground">
                          Supports .ppt and .pptx files
                        </p>
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept=".ppt,.pptx"
                          className="hidden"
                          onChange={handleFileUpload}
                          data-testid="file-input"
                        />
                      </div>
                    </div>
                  )}
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Rename / Edit Project Dialog */}
        <Dialog open={showRenameDialog} onOpenChange={setShowRenameDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Editar Projeto</DialogTitle>
              <DialogDescription>Atualize o nome do projeto e (super-admin) reatribua a empresa cliente.</DialogDescription>
            </DialogHeader>
            <div className="py-4 space-y-4">
              <Input
                placeholder="Nome do projeto"
                value={renameProjectName}
                onChange={(e) => setRenameProjectName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleRenameProject()}
                data-testid="rename-project-input"
                autoFocus
              />
              <CompanySelector
                value={renameProjectCompanyId}
                onChange={setRenameProjectCompanyId}
                label="Reatribuir a empresa"
                testIdPrefix="rename-company"
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowRenameDialog(false)}>
                Cancelar
              </Button>
              <Button onClick={handleRenameProject} data-testid="confirm-rename-btn">
                Salvar
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Tutorial Import Dialog */}
        <TutorialImportDialog
          open={showTutorialImport}
          onOpenChange={setShowTutorialImport}
          onProjectCreated={(projectId) => {
            fetchProjects();
            if (projectId) navigate(`/editor/${projectId}`);
          }}
        />

        {/* Projects Grid */}
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <h3 className="text-xl font-semibold">Your Projects</h3>
          <div className="flex flex-wrap items-center gap-2">
            {/* Search by project name — available to all roles. */}
            <div className="relative" data-testid="dashboard-search-wrapper">
              <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                placeholder="Buscar por nome..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="bg-background border border-border rounded-md pl-8 pr-7 py-1.5 text-sm w-56"
                data-testid="dashboard-search-input"
              />
              {searchInput && (
                <button
                  type="button"
                  onClick={() => setSearchInput('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  data-testid="dashboard-search-clear"
                  aria-label="Limpar busca"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
            {/* Super-admin only filters: company + recency. Non-super-admin
                users only see their own company so filters would be noise. */}
            {isSuperAdmin && (
              <div className="flex flex-wrap items-center gap-2" data-testid="dashboard-superadmin-filters">
                <div className="flex items-center gap-1.5">
                  <Filter className="w-3.5 h-3.5 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">Empresa:</span>
                  <select
                    value={filterCompanyId}
                    onChange={(e) => setFilterCompanyId(e.target.value)}
                    className="bg-background border border-border rounded-md px-2 py-1.5 text-sm min-w-[160px]"
                    data-testid="filter-company-select"
                  >
                    <option value="all">Todas as empresas</option>
                    <option value="__none__">Sem empresa</option>
                    {companiesList.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
                <div className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">Criados:</span>
                  <select
                    value={filterDateRange}
                    onChange={(e) => setFilterDateRange(e.target.value)}
                    className="bg-background border border-border rounded-md px-2 py-1.5 text-sm"
                    data-testid="filter-date-select"
                  >
                    <option value="all">Qualquer data</option>
                    <option value="7">Últimos 7 dias</option>
                    <option value="30">Últimos 30 dias</option>
                    <option value="90">Últimos 90 dias</option>
                  </select>
                </div>
                {(filterCompanyId !== 'all' || filterDateRange !== 'all') && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 px-2 text-xs"
                    onClick={() => { setFilterCompanyId('all'); setFilterDateRange('all'); }}
                    data-testid="filter-clear-btn"
                  >
                    Limpar
                  </Button>
                )}
              </div>
            )}
            {/* Result count badge — visible to everyone, always shows the
                current filter ratio so the user knows how many projects
                were matched vs total available. */}
            <Badge variant="outline" className="text-xs" data-testid="filter-count-badge">
              {filteredProjects.length} de {projects.length}
            </Badge>
          </div>
        </div>

        {loading && projects.length === 0 ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : filteredProjects.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="py-16 text-center">
              <Presentation className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
              <h4 className="text-lg font-medium mb-2">
                {projects.length === 0 ? 'No projects yet' : 'Nenhum projeto corresponde aos filtros'}
              </h4>
              <p className="text-muted-foreground mb-4">
                {projects.length === 0
                  ? 'Create a new project or import a PowerPoint to get started'
                  : 'Ajuste os filtros de empresa ou data para ver mais projetos.'}
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {filteredProjects.map((project) => (
              <Card
                key={project.id}
                className="card-hover cursor-pointer group relative"
                onClick={() => navigate(`/editor/${project.id}`)}
                data-testid={`project-card-${project.id}`}
              >
                {/* Delete button - always visible on hover */}
                <Button
                  variant="destructive"
                  size="icon"
                  className="absolute -top-2 -right-2 h-8 w-8 rounded-full opacity-0 group-hover:opacity-100 transition-opacity z-10 shadow-lg"
                  onClick={(e) => handleDeleteProject(project.id, e)}
                  data-testid={`delete-project-${project.id}`}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
                
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <CardTitle className="text-base truncate pr-8">
                      {project.name}
                    </CardTitle>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                          data-testid={`project-menu-${project.id}`}
                        >
                          <MoreVertical className="w-4 h-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={(e) => handleOpenRenameDialog(project, e)}
                          data-testid={`rename-project-${project.id}`}
                        >
                          <Pencil className="w-4 h-4 mr-2" />
                          Renomear
                        </DropdownMenuItem>
                        {/* Duplicate — visible only to super_admin and
                            company_admin. Backend also enforces RBAC. */}
                        {(isSuperAdmin || isCompanyAdmin) && (
                          <DropdownMenuItem
                            onClick={(e) => handleDuplicateProject(project.id, e)}
                            data-testid={`duplicate-project-${project.id}`}
                          >
                            <Copy className="w-4 h-4 mr-2" />
                            Duplicar
                          </DropdownMenuItem>
                        )}
                        {/* Reopen the AI Agent wizard for agent-created courses */}
                        {(project.createdByAgent || project.agentSessionId) && (
                          <DropdownMenuItem
                            onClick={(e) => { e.stopPropagation(); navigate(`/agent?resume=${project.id}`); }}
                            data-testid={`reopen-agent-${project.id}`}
                          >
                            <Brain className="w-4 h-4 mr-2" />
                            Reabrir no Assistente IA
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={(e) => handleDeleteProject(project.id, e)}
                        >
                          <Trash2 className="w-4 h-4 mr-2" />
                          Excluir
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="aspect-video bg-muted rounded-lg mb-3 flex items-center justify-center overflow-hidden relative">
                    {project.thumbnail ? (
                      <img
                        src={project.thumbnail}
                        alt=""
                        className="w-full h-full object-cover"
                        onError={(e) => { e.target.onerror = null; e.target.style.display = 'none'; }}
                      />
                    ) : project.course?.slides?.[0]?.backgroundImage ? (
                      <img
                        src={`${getApiUrl()}${project.course.slides[0].backgroundImage}`}
                        alt=""
                        className="w-full h-full object-cover"
                        onError={(e) => { e.target.onerror = null; e.target.style.display = 'none'; }}
                      />
                    ) : project.course?.slides?.[0] ? (
                      <SlideMinPreview slide={project.course.slides[0]} title={project.title || project.name} />
                    ) : (
                      <Presentation className="w-12 h-12 text-muted-foreground" />
                    )}
                    {/* Slide count badge */}
                    <div className="absolute bottom-2 right-2 bg-black/70 text-white text-xs px-2 py-1 rounded">
                      {project.course?.slidesCount ?? project.course?.slides?.length ?? 0} slides
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Clock className="w-3 h-3" />
                    <span>{formatDate(project.updatedAt || project.createdAt)}</span>
                    <span className={`ml-auto px-2 py-0.5 rounded text-xs ${
                      project.status === 'ready' ? 'bg-green-500/20 text-green-500' :
                      project.status === 'processing' ? 'bg-yellow-500/20 text-yellow-500' :
                      'bg-gray-500/20 text-gray-500'
                    }`}>
                      {project.status || 'draft'}
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}


function SlideMinPreview({ slide, title }) {
  const bg = slide.background || '#1e293b';
  const isGradient = bg.includes('gradient');
  const elements = slide.elements || [];
  const titleEl = elements.find(e => e.htmlContent?.includes('<h1') || e.htmlContent?.includes('font-size:4'));
  let titleText = title || slide.title || '';
  if (titleEl?.htmlContent) {
    const m = titleEl.htmlContent.match(/>([^<]{3,})</);
    if (m) titleText = m[1];
  }
  const subtitleEl = elements.find(e => e !== titleEl && (e.htmlContent?.includes('<p') || e.htmlContent?.includes('font-size:1')));
  let subtitleText = '';
  if (subtitleEl?.htmlContent) {
    const m = subtitleEl.htmlContent.match(/>([^<]{3,})</);
    if (m) subtitleText = m[1];
  }
  const textColor = elements[0]?.style?.color || (isGradient || bg < '#888' ? '#e2e8f0' : '#1e293b');
  const accentEl = elements.find(e => e.htmlContent?.includes('background:') || e.htmlContent?.includes('background-color:'));
  let accentColor = '';
  if (accentEl?.htmlContent) {
    const m = accentEl.htmlContent.match(/background(?:-color)?:\s*(#[0-9a-fA-F]{3,8})/);
    if (m) accentColor = m[1];
  }

  return (
    <div className="w-full h-full relative" style={{ background: bg }} data-testid="slide-min-preview">
      {accentColor && <div className="absolute top-0 left-0 right-0 h-1" style={{ background: accentColor }} />}
      <div className="absolute inset-0 flex flex-col items-center justify-center p-3 text-center gap-1">
        <span className="font-bold text-[11px] leading-tight line-clamp-2" style={{ color: textColor }}>{titleText}</span>
        {subtitleText && <span className="text-[8px] leading-tight line-clamp-1 opacity-70" style={{ color: textColor }}>{subtitleText}</span>}
      </div>
    </div>
  );
}
