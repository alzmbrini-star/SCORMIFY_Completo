import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../contexts/ProjectContext';
import { useTheme } from '../contexts/ThemeContext';
import { useAuth } from '../contexts/AuthContext';
import { getApiUrl } from '../utils/apiUrl';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
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
  LogOut,
  User,
  Pencil,
  Brain,
  BookOpen,
  Layers,
  Download,
} from 'lucide-react';
import axios from 'axios';

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
  const [showRenameDialog, setShowRenameDialog] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [renameProjectId, setRenameProjectId] = useState(null);
  const [renameProjectName, setRenameProjectName] = useState('');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [processingJobId, setProcessingJobId] = useState(null);
  const [processingStatus, setProcessingStatus] = useState('');
  const fileInputRef = useRef(null);
  const API_URL = getApiUrl();

  // Dashboard metrics
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    fetchProjects();
    // Fetch dashboard metrics
    axios.get(`${API_URL}/api/dashboard/metrics`)
      .then(res => setMetrics(res.data))
      .catch(() => {});
  }, [fetchProjects, API_URL]);

  useEffect(() => {
    let interval;
    if (processingJobId) {
      interval = setInterval(async () => {
        try {
          const status = await checkJobStatus(processingJobId);
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
          clearInterval(interval);
          setProcessingJobId(null);
          toast.error('Error checking job status');
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
      const project = await createProject(newProjectName.trim());
      setShowNewProjectDialog(false);
      setNewProjectName('');
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
      const result = await uploadPPT(file);
      setProcessingJobId(result.jobId);
      setUploadProgress(30);
      setProcessingStatus('Processing PowerPoint...');
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Erro desconhecido';
      toast.error(`Falha no upload: ${detail}`);
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
    setShowRenameDialog(true);
  };

  const handleRenameProject = async () => {
    if (!renameProjectName.trim()) {
      toast.error('Por favor, insira um nome para o projeto');
      return;
    }
    try {
      await updateProject(renameProjectId, { name: renameProjectName.trim() });
      setShowRenameDialog(false);
      setRenameProjectId(null);
      setRenameProjectName('');
      toast.success('Projeto renomeado com sucesso!');
    } catch (err) {
      toast.error('Erro ao renomear projeto');
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
                </DialogHeader>
                <div className="py-4">
                  <Input
                    placeholder="Project name"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleCreateProject()}
                    data-testid="project-name-input"
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
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Import PowerPoint</DialogTitle>
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
                  )}
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Rename Project Dialog */}
        <Dialog open={showRenameDialog} onOpenChange={setShowRenameDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Renomear Projeto</DialogTitle>
            </DialogHeader>
            <div className="py-4">
              <Input
                placeholder="Nome do projeto"
                value={renameProjectName}
                onChange={(e) => setRenameProjectName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleRenameProject()}
                data-testid="rename-project-input"
                autoFocus
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowRenameDialog(false)}>
                Cancelar
              </Button>
              <Button onClick={handleRenameProject} data-testid="confirm-rename-btn">
                Renomear
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Projects Grid */}
        <div className="mb-6">
          <h3 className="text-xl font-semibold mb-4">Your Projects</h3>
        </div>

        {loading && projects.length === 0 ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : projects.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="py-16 text-center">
              <Presentation className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
              <h4 className="text-lg font-medium mb-2">No projects yet</h4>
              <p className="text-muted-foreground mb-4">
                Create a new project or import a PowerPoint to get started
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {projects.map((project) => (
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
                      />
                    ) : project.course?.slides?.[0]?.backgroundImage ? (
                      <img
                        src={`${getApiUrl()}${project.course.slides[0].backgroundImage}`}
                        alt=""
                        className="w-full h-full object-cover"
                      />
                    ) : project.course?.slides?.[0] ? (
                      <SlideMinPreview slide={project.course.slides[0]} title={project.title || project.name} />
                    ) : (
                      <Presentation className="w-12 h-12 text-muted-foreground" />
                    )}
                    {/* Slide count badge */}
                    <div className="absolute bottom-2 right-2 bg-black/70 text-white text-xs px-2 py-1 rounded">
                      {project.course?.slides?.length || 0} slides
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
