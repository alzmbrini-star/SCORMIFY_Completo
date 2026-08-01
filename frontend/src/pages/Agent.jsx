import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { authHeaders } from '../contexts/AuthContext';
import { getApiUrl } from '../utils/apiUrl';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { ScrollArea } from '../components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { AnimPreviewButton } from '../components/AnimPreviewButton';
import { Slider } from '../components/ui/slider';
import { Checkbox } from '../components/ui/checkbox';
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
  PaintBucket, Target, Code, ExternalLink, BookOpenCheck, Volume2, Type, LogOut,
} from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';

const API = getApiUrl();

// Retry fetch wrapper for transient 5xx errors (deploy restarts, Atlas timeouts)
async function fetchRetry(url, options = {}, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(url, options);
      if (res.status >= 500 && i < maxRetries - 1) {
        await new Promise(r => setTimeout(r, 1000 * (i + 1)));
        continue;
      }
      return res;
    } catch (err) {
      if (i < maxRetries - 1) {
        await new Promise(r => setTimeout(r, 1000 * (i + 1)));
        continue;
      }
      throw err;
    }
  }
}

// Extracted sub-panels
import ConfigPanel from './Agent/components/ConfigPanel';
import StoryboardPanel from './Agent/components/StoryboardPanel';
import StoryboardChat from './Agent/components/StoryboardChat';
import MediaConfigChat from './Agent/components/MediaConfigChat';
import MediaConfigPanel from './Agent/components/MediaConfigPanel';
import GeneratedPanel from './Agent/components/GeneratedPanel';
import ApprovalQueuePanel from './Agent/components/ApprovalQueuePanel';
import { CourseReviewPanel, EditResultPanel, PreviewPanel } from './Agent/components/CoursePanels';
import PdfPreviewPanel from './Agent/components/PdfPreviewPanel';
import CompanySelector from '../components/CompanySelector';


// ===== CREATE MODE STEPS =====
const CREATE_STEPS = [
  { id: 'upload', label: 'Conteúdo', icon: Upload },
  { id: 'analyze', label: 'Análise', icon: Brain },
  { id: 'configure', label: 'Configurar', icon: Settings },
  { id: 'structure', label: 'Estrutura', icon: Layers },
  { id: 'storyboard', label: 'Storyboard', icon: BookOpen },
  { id: 'media', label: 'Mídia', icon: Image },
  { id: 'generate', label: 'Gerar Curso', icon: Play },
];

// ===== EDIT MODE STEPS =====
const EDIT_STEPS = [
  { id: 'select', label: 'Selecionar', icon: BookOpen },
  { id: 'review', label: 'Análise', icon: Brain },
  { id: 'preview', label: 'Preview', icon: Eye },
  { id: 'apply', label: 'Resultado', icon: Check },
];

const TEMPLATE_ICONS = {
  users: Users, shield: Shield, wrench: Wrench, heart: Heart,
  'hard-hat': HardHat, 'trending-up': TrendingUp,
};

export default function Agent() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { isSuperAdmin, hasPermission, loading: authLoading, isAprovador, user: authUser, logout } = useAuth();
  
  // Check access to AI Agent
  const hasAgentAccess = isSuperAdmin || isAprovador || hasPermission('agentAccess');
  
  // Mode: null = selection, 'create' = new course, 'edit' = edit existing
  const [mode, setMode] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [accessChecked, setAccessChecked] = useState(false);
  const [showChat, setShowChat] = useState(true);

  // Create mode data
  const [contentText, setContentText] = useState('');
  const [contentUrl, setContentUrl] = useState('');
  const [fileName, setFileName] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [config, setConfig] = useState({
    title: '', depth: 'intermediario', duration: 30, modules: 3,
    interactivity: 'media', visualStyle: 'moderno e profissional',
    format: 'curso_completo', description: '',
    narrationEnabled: false, narrationVoiceId: '',
    resourceBalance: 'media',
    enabledResources: {
      quiz: true,
      simulator: true,
      scenario: true,
      avatar_scene: false,
      infographic: true,
      flashcard: true,
      timeline: true,
      case_study: true,
    },
  });
  const [structure, setStructure] = useState(null);
  const [storyboard, setStoryboard] = useState(null);
  const [storyboardProgressMsg, setStoryboardProgressMsg] = useState(null);
  const [generatedProject, setGeneratedProject] = useState(null);
  const [generationPhases, setGenerationPhases] = useState([]); // Track generation progress phases
  const [generationStartTime, setGenerationStartTime] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [designTemplates, setDesignTemplates] = useState([]);
  const [selectedDesignTemplate, setSelectedDesignTemplate] = useState(null);
  const [mediaConfig, setMediaConfig] = useState({});
  const [heygenConfig, setHeygenConfig] = useState({ avatarId: '', voiceId: '' });
  const [bgConfig, setBgConfig] = useState({});
  const [globalTextColor, setGlobalTextColor] = useState('');
  const [globalFontSize, setGlobalFontSize] = useState('');
  const [globalAnimation, setGlobalAnimation] = useState('');
  // Brand Library: when on, the AI Agent prefers the company's curated
  // imagery over Leonardo/Gemini generations. Mode controls the fallback:
  // 'preferred' (try library first, fall back to AI) or 'strict' (library
  // only — slides without a match render without background).
  const [useBrandLibrary, setUseBrandLibrary] = useState(false);
  const [brandLibraryMode, setBrandLibraryMode] = useState('preferred');
  const [brandLibraryCount, setBrandLibraryCount] = useState(null); // null = not yet loaded
  const [editMediaProjectId, setEditMediaProjectId] = useState(null);
  // Resumed session support: the project already generated by this session
  // (drives the "novo curso vs substituir" choice on re-generation).
  const [resumedProjectId, setResumedProjectId] = useState(null);
  const [generateChoiceOpen, setGenerateChoiceOpen] = useState(false);
  // Track original configs for smart edit (only apply changed slides)
  const [originalMediaConfig, setOriginalMediaConfig] = useState(null);
  const [originalBgConfig, setOriginalBgConfig] = useState(null);
  const [originalGlobalTextColor, setOriginalGlobalTextColor] = useState('');
  const [originalGlobalFontSize, setOriginalGlobalFontSize] = useState('');
  const [originalGlobalAnimation, setOriginalGlobalAnimation] = useState('');
  const [originalDesignTemplate, setOriginalDesignTemplate] = useState(null);

  // Edit mode data
  const [agentCourses, setAgentCourses] = useState([]);
  const [selectedCourse, setSelectedCourse] = useState(null);
  const [courseAnalysis, setCourseAnalysis] = useState(null);

  // Companies for approval workflow
  const [companiesList, setCompaniesList] = useState([]);
  const [selectedImprovements, setSelectedImprovements] = useState([]);
  const [selectedNewSlides, setSelectedNewSlides] = useState([]);
  const [editResult, setEditResult] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [applyProgress, setApplyProgress] = useState(null); // { progress, message } during async apply

  // Chat
  const [chatMessages, setChatMessages] = useState([
    { role: 'agent', text: 'Olá! Sou seu Agente de Design Instrucional. Escolha se deseja criar um novo curso ou editar um existente.' },
  ]);
  const [chatInput, setChatInput] = useState('');
  const chatEndRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // Check access to AI Agent and redirect if not authorized
  useEffect(() => {
    if (authLoading) return;
    
    if (!hasAgentAccess) {
      toast.error('Voce nao tem permissao para acessar o Agente IA');
      navigate('/');
      return;
    }
    setAccessChecked(true);
    
    // Auto-select approval mode for aprovador users
    if (isAprovador && !isSuperAdmin && !mode) {
      setMode('approval');
    }
  }, [authLoading, hasAgentAccess, navigate, isAprovador, isSuperAdmin]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch companies for approval company selector
  useEffect(() => {
    if (!isSuperAdmin) return;
    (async () => {
      try {
        const res = await fetch(`${API}/api/companies`, { headers: authHeaders() });
        if (res.ok) setCompaniesList(await res.json());
      } catch { /* ignore */ }
    })();
  }, [isSuperAdmin]);

  // Handle editMedia query param - load existing session for media editing
  useEffect(() => {
    const editProjectId = searchParams.get('editMedia');
    if (!editProjectId || mode) return;
    (async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API}/api/agent/sessions/by-project/${editProjectId}`, { headers: authHeaders() });
        if (!res.ok) { toast.error('Sessão não encontrada para este projeto'); setLoading(false); return; }
        const session = await res.json();
        setSessionId(session.id);
        setMode('create');
        setStoryboard(session.storyboard);
        setMediaConfig(session.mediaConfig || {});
        setBgConfig(session.bgConfig || {});
        setOriginalMediaConfig(JSON.parse(JSON.stringify(session.mediaConfig || {})));
        setOriginalBgConfig(JSON.parse(JSON.stringify(session.bgConfig || {})));
        setGlobalTextColor(session.globalTextColor || '');
        setGlobalFontSize(session.globalFontSize || '');
        setGlobalAnimation(session.globalAnimation || '');
        setOriginalGlobalTextColor(session.globalTextColor || '');
        setOriginalGlobalFontSize(session.globalFontSize || '');
        setOriginalGlobalAnimation(session.globalAnimation || '');
        setEditMediaProjectId(editProjectId);
        // When opening an existing project for media editing, pull its
        // companyId from the session payload (sessions cache it) OR fall
        // back to fetching the project. We need this so the Brand Library
        // picker can list ONLY this company's curated images.
        let resolvedCompanyId = session.companyId || session.company_id || '';
        if (!resolvedCompanyId) {
          try {
            const pr = await fetch(`${API}/api/projects/${editProjectId}`, { headers: authHeaders() });
            if (pr.ok) {
              const pdata = await pr.json();
              resolvedCompanyId = pdata?.companyId || pdata?.company_id || '';
            }
          } catch (_e) { /* ignore — picker will show empty state */ }
        }
        if (resolvedCompanyId) setAgentCompanyId(resolvedCompanyId);
        setConfig(session.config || {});
        setStructure(session.structure);
        setCurrentStep(5); // Go directly to Media Config step
        addChatMsg('agent', `Editando mídia do projeto. Altere configurações e clique em "Aplicar Alterações" para atualizar o projeto.`);
      } catch { toast.error('Erro ao carregar sessão'); }
      finally { setLoading(false); }
    })();
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  const addChatMsg = useCallback((role, text) => {
    setChatMessages(prev => [...prev, { role, text, ts: new Date().toISOString() }]);
  }, []);

  // Rehydrate the whole wizard from a persisted agent session — used by
  // the "Reabrir no Assistente" flows (?resume={projectId} or course list).
  const hydrateWizardFromSession = async (lightSession) => {
    let session = lightSession;
    try {
      const fr = await fetch(`${API}/api/agent/sessions/${lightSession.id}?full=1`, { headers: authHeaders() });
      if (fr.ok) session = await fr.json();
    } catch { /* fall back to the light session */ }
    setSessionId(session.id);
    setMode('create');
    setFileName(session.fileName || '');
    setContentText(session.contentText || '');
    if (session.analysis) setAnalysis(session.analysis);
    if (session.config && Object.keys(session.config).length > 0) {
      setConfig(prev => ({ ...prev, ...session.config }));
    }
    setStructure(session.structure || null);
    setStoryboard(session.storyboard || null);
    setMediaConfig(session.mediaConfig || {});
    setBgConfig(session.bgConfig || {});
    setGlobalTextColor(session.globalTextColor || '');
    setGlobalFontSize(session.globalFontSize || '');
    setGlobalAnimation(session.globalAnimation || '');
    setUseBrandLibrary(!!session.useBrandLibrary);
    setBrandLibraryMode(session.brandLibraryMode || 'preferred');
    if (session.companyId) setAgentCompanyId(session.companyId);
    setResumedProjectId(session.projectId || null);
    if (session.courseResult) setGeneratedProject({ ...session.courseResult, status: 'done' });
    const landing = session.storyboard ? (session.projectId ? 5 : 4)
      : session.structure ? 3 : session.analysis ? 2 : 1;
    setCurrentStep(landing);
    addChatMsg('agent', 'Sessão do curso recarregada! Clique nas etapas no topo para navegar. Você pode modificar e re-executar qualquer fase — as etapas seguintes serão refeitas na sequência normal.');
  };

  // Handle ?resume={projectId} — reopen the wizard for an existing course.
  useEffect(() => {
    const resumeProjectId = searchParams.get('resume');
    if (!resumeProjectId || mode) return;
    (async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API}/api/agent/sessions/by-project/${resumeProjectId}`, { headers: authHeaders() });
        if (!res.ok) { toast.error('Sessão do Agente IA não encontrada para este curso'); return; }
        await hydrateWizardFromSession(await res.json());
        toast.success('Curso reaberto no assistente');
      } catch { toast.error('Erro ao carregar sessão'); }
      finally { setLoading(false); }
    })();
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleReopenWizard = async (course) => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/agent/sessions/by-project/${course.id}`, { headers: authHeaders() });
      if (!res.ok) { toast.error('Sessão do Agente IA não encontrada para este curso'); return; }
      await hydrateWizardFromSession(await res.json());
      toast.success('Curso reaberto no assistente');
    } catch { toast.error('Erro ao carregar sessão'); }
    finally { setLoading(false); }
  };

  // Which wizard steps the author can jump to directly via the stepper.
  const canJumpToStep = (i) => {
    if (mode !== 'create' || editMediaProjectId) return false;
    switch (i) {
      case 0: return true;
      case 1: return !!sessionId;
      case 2: return !!analysis;
      case 3: return !!structure;
      case 4: return !!storyboard;
      case 5: return !!storyboard;
      case 6: return !!generatedProject;
      default: return false;
    }
  };

  // Load templates on mount
  useEffect(() => {
    fetchRetry(`${API}/api/agent/templates`, { headers: authHeaders() })
      .then(r => r.json())
      .then(setTemplates)
      .catch(() => {});
    fetchRetry(`${API}/api/agent/design-templates`, { headers: authHeaders() })
      .then(r => r.json())
      .then(setDesignTemplates)
      .catch(() => {});
  }, []);

  const [agentCompanyId, setAgentCompanyId] = useState('');

  // Brand Library count for the active company. Fetched when the user
  // lands on step 5 so the MediaConfigPanel can show "N imagens disponíveis"
  // or disable the toggle if the library is empty.
  useEffect(() => {
    if (currentStep !== 5) return;
    // Resolve the company we'd generate this course for. Super-admin may
    // pick a target company explicitly; regular users always have their own.
    const cid = agentCompanyId || authUser?.companyId;
    if (!cid) {
      setBrandLibraryCount(0);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API}/api/companies/${cid}/assets?type=background`, {
          headers: authHeaders(),
        });
        if (!r.ok) {
          if (!cancelled) setBrandLibraryCount(0);
          return;
        }
        const d = await r.json();
        if (!cancelled) setBrandLibraryCount(d.total || 0);
      } catch (_e) {
        if (!cancelled) setBrandLibraryCount(0);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep, agentCompanyId, authUser?.companyId]);

  const ensureSession = useCallback(async () => {
    if (sessionId) return sessionId;
    try {
      const body = agentCompanyId ? { companyId: agentCompanyId } : {};
      const res = await fetchRetry(`${API}/api/agent/sessions`, {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body),
      });
      const data = await res.json();
      setSessionId(data.id);
      return data.id;
    } catch (e) {
      toast.error('Erro ao criar sessão');
      return null;
    }
  }, [sessionId, agentCompanyId]);

  // ===== CREATE MODE HANDLERS =====
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    addChatMsg('user', `Enviando arquivo: ${file.name}`);
    try {
      const sid = await ensureSession();
      if (!sid) return;

      const CHUNK_THRESHOLD = 5 * 1024 * 1024; // 5 MB
      let data;

      if (file.size <= CHUNK_THRESHOLD) {
        // Small file: single POST
        const form = new FormData();
        form.append('file', file);
        const res = await fetch(`${API}/api/agent/sessions/${sid}/upload`, {
          method: 'POST', headers: authHeaders(), body: form,
        });
        if (!res.ok) throw new Error(`Upload falhou (${res.status})`);
        data = await res.json();
      } else {
        // Large file: chunked upload to bypass proxy/Cloudflare body limits.
        // 2026-05-25: reduced chunk size from 4MB to 2MB after production
        // reported "Falha no chunk 3/7 (502)" on a 26.5MB PDF. Smaller chunks
        // are far less likely to trip Cloudflare/nginx upstream timeouts
        // under high write contention. Added retry with exponential backoff
        // (3 attempts per chunk) to survive transient gateway hiccups.
        const CHUNK_SIZE = 2 * 1024 * 1024; // 2 MB per chunk
        const MAX_RETRIES = 3;
        const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
        const uploadId = `u${Date.now()}${Math.random().toString(36).slice(2, 8)}`;

        addChatMsg('agent', `Arquivo grande (${(file.size / 1024 / 1024).toFixed(1)} MB). Enviando em ${totalChunks} partes...`);

        let lastResponse = null;
        for (let i = 0; i < totalChunks; i++) {
          const start = i * CHUNK_SIZE;
          const end = Math.min(start + CHUNK_SIZE, file.size);
          const chunk = file.slice(start, end);

          let attempt = 0;
          let chunkOk = false;
          let lastStatus = 0;
          while (attempt < MAX_RETRIES && !chunkOk) {
            attempt += 1;
            try {
              const form = new FormData();
              form.append('chunk', chunk, `chunk_${i}`);
              form.append('uploadId', uploadId);
              form.append('chunkIndex', String(i));
              form.append('totalChunks', String(totalChunks));
              form.append('fileName', file.name);

              const res = await fetch(`${API}/api/agent/sessions/${sid}/upload-chunk`, {
                method: 'POST', headers: authHeaders(), body: form,
              });
              lastStatus = res.status;
              if (res.ok) {
                lastResponse = await res.json();
                chunkOk = true;
                break;
              }
              // Retry on transient gateway errors (502/503/504). Anything else
              // is a permanent failure — bubble up immediately.
              if ([502, 503, 504].includes(res.status) && attempt < MAX_RETRIES) {
                await new Promise(r => setTimeout(r, 800 * attempt));
                continue;
              }
              throw new Error(`Falha no chunk ${i + 1}/${totalChunks} (${res.status})`);
            } catch (chunkErr) {
              if (attempt >= MAX_RETRIES) {
                throw new Error(`Falha no chunk ${i + 1}/${totalChunks} (${lastStatus || chunkErr.message})`);
              }
              await new Promise(r => setTimeout(r, 800 * attempt));
            }
          }
          setFileName(`${file.name} (${i + 1}/${totalChunks})`);
        }
        data = lastResponse;
      }

      setFileName(file.name);
      const msg = data?.pdfProcessing
        ? `Arquivo "${file.name}" recebido! Extraindo imagens e texto em segundo plano...`
        : `Arquivo "${file.name}" recebido! ${data?.contentLength || 0} caracteres extraídos. Clique em "Analisar".`;
      addChatMsg('agent', msg);
      setCurrentStep(1);
    } catch (err) {
      toast.error(err?.message || 'Erro no upload');
      addChatMsg('agent', err?.message || 'Erro ao processar o arquivo.');
    } finally { setLoading(false); }
  };

  const handleTextSubmit = async () => {
    if (!contentText.trim()) return;
    setLoading(true);
    addChatMsg('user', `Conteúdo enviado (${contentText.length} caracteres)`);
    try {
      const sid = await ensureSession();
      if (!sid) return;
      const form = new FormData();
      form.append('text', contentText);
      await fetch(`${API}/api/agent/sessions/${sid}/upload`, { method: 'POST', headers: authHeaders(), body: form });
      addChatMsg('agent', 'Conteúdo recebido! Clique em "Analisar Conteúdo".');
      setCurrentStep(1);
    } catch { toast.error('Erro ao enviar conteúdo'); }
    finally { setLoading(false); }
  };

  const handleUrlSubmit = async () => {
    if (!contentUrl.trim()) return;
    setLoading(true);
    addChatMsg('user', `Extraindo conteúdo de: ${contentUrl}`);
    try {
      const sid = await ensureSession();
      if (!sid) return;
      const form = new FormData();
      form.append('url', contentUrl);
      const res = await fetch(`${API}/api/agent/sessions/${sid}/upload`, { method: 'POST', headers: authHeaders(), body: form });
      const data = await res.json();
      setFileName(contentUrl);
      addChatMsg('agent', `Conteúdo extraído da URL! ${data.contentLength} caracteres. Clique em "Analisar".`);
      setCurrentStep(1);
    } catch { toast.error('Erro ao extrair conteúdo da URL'); addChatMsg('agent', 'Erro ao acessar a URL.'); }
    finally { setLoading(false); }
  };

  // Polling helper: waits for session step to change
  const pollSessionStep = async (targetStep, errorStep, maxWait = 180000) => {
    const start = Date.now();
    while (Date.now() - start < maxWait) {
      await new Promise(r => setTimeout(r, 3000));
      try {
        const res = await fetchRetry(`${API}/api/agent/sessions/${sessionId}?light=1`, { headers: authHeaders() }, 2);
        if (!res.ok) continue;
        const session = await res.json();
        if (session.step === targetStep) return session;
        if (session.step === errorStep) throw new Error(session.error || 'Erro no processamento');
      } catch (e) {
        if (e.message && e.message !== 'Erro no processamento') continue;
        throw e;
      }
    }
    throw new Error('Timeout aguardando processamento');
  };

  const handleAnalyze = async (forceRegen = false) => {
    if (forceRegen) {
      const ok = window.confirm('Refazer a análise com IA? As etapas seguintes (estrutura, storyboard) continuarão disponíveis, mas deverão ser regeradas para refletir a nova análise.');
      if (!ok) return;
    }
    setLoading(true);
    addChatMsg('agent', forceRegen ? 'Reanalisando o conteudo com IA...' : 'Analisando o conteudo com IA...');
    try {
      const res = await fetchRetry(`${API}/api/agent/sessions/${sessionId}/analyze${forceRegen ? '?force=1' : ''}`, { method: 'POST', headers: authHeaders() });
      if (!res.ok) {
        // Parse backend error message if possible
        let errMsg = `Erro ${res.status} na analise`;
        try {
          const errBody = await res.json();
          if (errBody?.detail) errMsg = errBody.detail;
        } catch { /* ignore */ }
        throw new Error(errMsg);
      }
      const data = await res.json();

      // If already analyzed (cached), use directly
      if (data.title || data.topics) {
        setAnalysis(data);
        setConfig(prev => ({
          ...prev, title: data.title || prev.title, description: data.summary || prev.description,
          duration: data.estimatedDuration || prev.duration, modules: data.suggestedModules || prev.modules,
          depth: data.difficulty || prev.depth,
        }));
        addChatMsg('agent', `Analise concluida! "${data.title}" sugerido como titulo. Configure e gere a estrutura.`);
        setCurrentStep(2);
      } else if (data.status === 'processing') {
        // Poll for completion
        addChatMsg('agent', 'Analise em andamento... aguarde.');
        const session = await pollSessionStep('analyzed', 'analysis_error');
        const analysis = session.analysis;
        setAnalysis(analysis);
        setConfig(prev => ({
          ...prev, title: analysis.title || prev.title, description: analysis.summary || prev.description,
          duration: analysis.estimatedDuration || prev.duration, modules: analysis.suggestedModules || prev.modules,
          depth: analysis.difficulty || prev.depth,
        }));
        addChatMsg('agent', `Analise concluida! "${analysis.title}" sugerido como titulo. Configure e gere a estrutura.`);
        setCurrentStep(2);
      }
    } catch (e) { toast.error(e.message || 'Erro na analise'); addChatMsg('agent', 'Erro ao analisar.'); }
    finally { setLoading(false); }
  };

  const handleGenerateStructure = async () => {
    if (structure) {
      const ok = window.confirm('Já existe uma estrutura gerada. Deseja REGENERAR a estrutura com as configurações atuais? (Cancelar mantém a estrutura existente)');
      if (!ok) { setCurrentStep(3); return; }
    }
    setLoading(true);
    addChatMsg('agent', selectedTemplate ? `Gerando estrutura usando template "${selectedTemplate.name}"...` : 'Gerando a estrutura pedagogica...');
    try {
      const configToSend = { ...config };
      if (selectedDesignTemplate) configToSend.designTemplateId = selectedDesignTemplate.id;
      await fetch(`${API}/api/agent/sessions/${sessionId}/configure`, {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify(configToSend),
      });
      const body = selectedTemplate ? { templateId: selectedTemplate.id } : {};
      if (structure) body.force = true;
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/generate-structure`, {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();

      // If already structured (cached), use directly
      if (data.modules) {
        setStructure(data);
        const totalSlides = data.modules?.reduce((sum, m) => sum + (m.slides?.length || 0), 0) || 0;
        addChatMsg('agent', `Estrutura criada! ${data.modules?.length || 0} modulos com ${totalSlides} slides.`);
        setCurrentStep(3);
      } else if (data.status === 'processing') {
        // Poll for completion
        addChatMsg('agent', 'Gerando estrutura... aguarde.');
        const session = await pollSessionStep('structured', 'structure_error');
        const structure = session.structure;
        setStructure(structure);
        const totalSlides = structure.modules?.reduce((sum, m) => sum + (m.slides?.length || 0), 0) || 0;
        addChatMsg('agent', `Estrutura criada! ${structure.modules?.length || 0} modulos com ${totalSlides} slides.`);
        setCurrentStep(3);
      }
    } catch (e) { toast.error(e.message || 'Erro ao gerar estrutura'); addChatMsg('agent', 'Erro ao gerar estrutura.'); }
    finally { setLoading(false); }
  };

  const handleGenerateStoryboard = async () => {
    setLoading(true);
    setStoryboardProgressMsg('Verificando status...');
    try {
      // Check if storyboard already exists (e.g., user refreshed or polling timed out)
      const checkRes = await fetch(`${API}/api/agent/sessions/${sessionId}`, { headers: authHeaders() });
      const checkSession = await checkRes.json();
      if (checkSession.step === 'storyboarded' && checkSession.storyboard) {
        setStoryboard(checkSession.storyboard);
        const mc = {};
        checkSession.storyboard.slides?.forEach((s, i) => {
          if (s.type === 'content') mc[String(i)] = { type: 'ai_image' };
        });
        setMediaConfig(mc);
        addChatMsg('agent', `Storyboard já estava pronto com ${checkSession.storyboard.slides?.length || 0} slides! Configure a mídia.`);
        setCurrentStep(4);
        setLoading(false);
        setStoryboardProgressMsg(null);
        return;
      }

      setStoryboardProgressMsg('Iniciando geração do storyboard...');
      addChatMsg('agent', 'Criando storyboard detalhado... Pode levar 5-10 minutos. Você verá o progresso abaixo.');
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/generate-storyboard`, { method: 'POST', headers: authHeaders() });
      if (!res.ok) throw new Error();
      const pollInterval = setInterval(async () => {
        try {
          const sRes = await fetch(`${API}/api/agent/sessions/${sessionId}?light=1`, { headers: authHeaders() });
          if (!sRes.ok) return; // Skip this poll cycle on error
          const session = await sRes.json();

          // Show progress
          if (session.storyboardProgress) {
            const p = session.storyboardProgress;
            const pct = Math.round((p.batch / p.total) * 100);
            setStoryboardProgressMsg(`${p.message} (${pct}%)`);
          } else if (session.step === 'storyboarding') {
            setStoryboardProgressMsg('Processando com IA... aguarde.');
          }

          if (session.step === 'storyboarded' && session.storyboard) {
            clearInterval(pollInterval);
            setStoryboard(session.storyboard);
            setStoryboardProgressMsg(null);
            const mc = {};
            session.storyboard.slides?.forEach((s, i) => {
              if (s.type === 'content') {
                mc[String(i)] = { type: 'ai_image' };
              }
            });
            setMediaConfig(mc);
            addChatMsg('agent', `Storyboard completo com ${session.storyboard.slides?.length || 0} slides! Configure a mídia de cada slide.`);
            setCurrentStep(4);
            setLoading(false);
          } else if (session.step === 'structured' && !session.storyboardProgress) {
            clearInterval(pollInterval);
            setStoryboardProgressMsg(null);
            addChatMsg('agent', session.error || 'Erro ao gerar storyboard. Tente novamente.');
            toast.error(session.error || 'Erro no storyboard');
            setLoading(false);
          }
        } catch { /* polling error - will retry next interval */ }
      }, 4000);
      // Timeout: 15 minutes (storyboard generation can take 5-10 min with model fallbacks)
      setTimeout(() => {
        clearInterval(pollInterval);
        // Final check before giving up
        fetch(`${API}/api/agent/sessions/${sessionId}?light=1`, { headers: authHeaders() })          .then(r => r.json())
          .then(session => {
            if (session.step === 'storyboarded' && session.storyboard) {
              setStoryboard(session.storyboard);
              const mc = {};
              session.storyboard.slides?.forEach((s, i) => {
                if (s.type === 'content') mc[String(i)] = { type: 'ai_image' };
              });
              setMediaConfig(mc);
              addChatMsg('agent', `Storyboard completo com ${session.storyboard.slides?.length || 0} slides!`);
              setCurrentStep(4);
            } else {
              addChatMsg('agent', 'A geração está demorando mais que o esperado. Clique em "Aprovar e Gerar Storyboard" para verificar o status.');
              toast.error('Timeout - tente novamente');
            }
            setStoryboardProgressMsg(null);
            setLoading(false);
          })
          .catch(() => { setStoryboardProgressMsg(null); setLoading(false); });
      }, 900000);
    } catch { toast.error('Erro no storyboard'); setLoading(false); setStoryboardProgressMsg(null); }
  };

  const handleApproveStoryboard = () => {
    addChatMsg('agent', 'Agora configure a mídia de cada slide: imagem IA, vídeo YouTube/Vimeo, avatar HeyGen ou sem mídia.');
    setCurrentStep(5); // media config step
  };

  const handleSubmitForApproval = async (targetCompanyId) => {
    if (!sessionId) return;
    setLoading(true);
    addChatMsg('agent', 'Enviando storyboard para aprovacao...');
    try {
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/submit-for-approval`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ targetCompanyId }),
      });
      if (res.ok) {
        const data = await res.json();
        addChatMsg('agent', `Storyboard enviado para aprovacao da empresa "${data.targetCompany || ''}"! O aprovador da empresa vai revisar o conteudo.`);
        toast.success('Storyboard enviado para aprovacao');
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Erro ao enviar para aprovacao');
      }
    } catch {
      toast.error('Erro ao enviar para aprovacao');
    }
    setLoading(false);
  };

  // Resume an approved session - load it into the create wizard at the storyboard step
  const handleResumeApprovedSession = async (session) => {
    setLoading(true);
    try {
      // First, call resume endpoint to set step back to 'storyboarded'
      const resumeRes = await fetch(`${API}/api/agent/sessions/${session.id}/resume-from-approval`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({}),
      });
      if (!resumeRes.ok) {
        const err = await resumeRes.json();
        toast.error(err.detail || 'Erro ao retomar');
        setLoading(false);
        return;
      }

      // Now fetch the full session to load into the wizard
      const fullRes = await fetch(`${API}/api/agent/sessions/${session.id}`, { headers: authHeaders() });
      if (!fullRes.ok) {
        toast.error('Erro ao carregar sessao');
        setLoading(false);
        return;
      }
      const fullSession = await fullRes.json();

      // Load all session data into state
      setSessionId(fullSession.id);
      setStoryboard(fullSession.storyboard);
      setConfig(fullSession.config || {});
      setStructure(fullSession.structure || null);
      setMediaConfig(fullSession.mediaConfig || {});
      setBgConfig(fullSession.bgConfig || {});
      setGlobalTextColor(fullSession.globalTextColor || '');
      setGlobalFontSize(fullSession.globalFontSize || '');
      setGlobalAnimation(fullSession.globalAnimation || '');
      
      // Switch to create mode at storyboard step
      setMode('create');
      setCurrentStep(4); // storyboard step
      addChatMsg('agent', 'Storyboard aprovado carregado! Voce pode revisar e prosseguir para a configuracao de midia.');
      toast.success('Sessao retomada com sucesso');
    } catch {
      toast.error('Erro ao retomar sessao');
    }
    setLoading(false);
  };

  const handleSaveMediaConfig = async () => {
    setLoading(true);
    addChatMsg('agent', 'Salvando configuração de mídia e fundos...');
    try {
      const enrichedConfig = { ...mediaConfig };
      for (const [key, val] of Object.entries(enrichedConfig)) {
        if (val.type === 'heygen') {
          enrichedConfig[key] = { ...val, avatar_id: heygenConfig.avatarId, voice_id: heygenConfig.voiceId };
        }
      }
      const saveRes = await fetch(`${API}/api/agent/sessions/${sessionId}/media-config`, {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          mediaConfig: enrichedConfig, bgConfig,
          globalTextColor, globalFontSize, globalAnimation,
          designTemplateId: selectedDesignTemplate?.id || '',
          useBrandLibrary, brandLibraryMode,
        }),
      });
      if (!saveRes.ok) throw new Error('Falha ao salvar configuração de mídia');

      // If editing existing project, detect changed slides and apply only those
      if (editMediaProjectId) {
        // Compute changed slide indices
        const changedSlides = [];
        const allKeys = new Set([
          ...Object.keys(enrichedConfig),
          ...Object.keys(originalMediaConfig || {}),
          ...Object.keys(bgConfig),
          ...Object.keys(originalBgConfig || {}),
        ]);
        for (const key of allKeys) {
          const mcChanged = JSON.stringify(enrichedConfig[key] || {}) !== JSON.stringify((originalMediaConfig || {})[key] || {});
          const bgChanged = JSON.stringify((bgConfig || {})[key] || {}) !== JSON.stringify((originalBgConfig || {})[key] || {});
          if (mcChanged || bgChanged) changedSlides.push(parseInt(key, 10));
        }
        // Also add if global settings actually CHANGED (compare to originals)
        const hasGlobalChanges = 
          (globalTextColor !== originalGlobalTextColor) ||
          (globalFontSize !== originalGlobalFontSize) ||
          (globalAnimation !== originalGlobalAnimation) ||
          (!!selectedDesignTemplate && selectedDesignTemplate?.id !== originalDesignTemplate?.id);

        addChatMsg('agent', hasGlobalChanges
          ? 'Aplicando alterações globais ao projeto...'
          : `Aplicando alterações em ${changedSlides.length} slide(s) modificado(s)...`);

        const res = await fetch(`${API}/api/agent/sessions/${sessionId}/apply-media-changes`, {
          method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({
            projectId: editMediaProjectId,
            changedSlides: hasGlobalChanges ? null : (changedSlides.length > 0 ? changedSlides : []),
          }),
        });
        if (!res.ok) throw new Error('Falha ao aplicar alterações');
        const data = await res.json();
        addChatMsg('agent', `Alterações aplicadas! ${data.updatedSlides || 0} slides atualizados.`);
        toast.success('Alterações aplicadas com sucesso!');
        navigate(`/editor/${editMediaProjectId}`);
        return;
      }

      // New course: proceed to generation
      const aiImageCount = Object.values(mediaConfig).filter(m => m.type === 'ai_image').length;
      const videoCount = Object.values(mediaConfig).filter(m => m.type === 'youtube' || m.type === 'vimeo').length;
      const heygenCount = Object.values(mediaConfig).filter(m => m.type === 'heygen').length;
      const klingCount = Object.values(mediaConfig).filter(m => m.type === 'kling').length;
      const heygenMsg = heygenCount > 0 ? ` ${heygenCount} vídeos avatar HeyGen serão gerados em segundo plano (~1-3 min cada).` : '';
      const klingMsg = klingCount > 0 ? ` ${klingCount} cenas Kling serão processadas em segundo plano.` : '';
      addChatMsg('agent', `Mídia configurada! ${aiImageCount} imagens IA, ${videoCount} vídeos, ${heygenCount} avatares e ${klingCount} cenas Kling.${heygenMsg}${klingMsg}${aiImageCount > 0 ? ' A geração de imagens pode levar alguns minutos.' : ''}`);
      if (resumedProjectId) {
        // This session already generated a course — let the author choose
        // between creating a new project or replacing the existing one.
        setGenerateChoiceOpen(true);
      } else {
        setCurrentStep(6);
        handleGenerateCourse();
      }
    } catch (err) { toast.error(err.message || 'Erro ao salvar mídia'); addChatMsg('agent', `Erro: ${err.message || 'Erro ao salvar configuração de mídia.'}`); }
    finally { setLoading(false); }
  };

  const handleGenerateChoice = (choiceMode) => {
    if (choiceMode === 'replace') {
      const ok = window.confirm('Tem certeza? O curso gerado anteriormente será EXCLUÍDO permanentemente (incluindo edições manuais feitas no Editor).');
      if (!ok) return;
    }
    setGenerateChoiceOpen(false);
    setCurrentStep(6);
    handleGenerateCourse(choiceMode);
  };

  const handleGenerateCourse = async (genMode = null) => {
    setLoading(true);
    setGenerationStartTime(Date.now());
    const aiCount = Object.values(mediaConfig).filter(m => m.type === 'ai_image').length;
    const heyCount = Object.values(mediaConfig).filter(m => m.type === 'heygen').length;
    const klingCount = Object.values(mediaConfig).filter(m => m.type === 'kling').length;
    const vidCount = Object.values(mediaConfig).filter(m => m.type === 'youtube' || m.type === 'vimeo').length;
    const slideCount = storyboard?.slides?.length || 0;

    setGenerationPhases([
      { id: 'init', label: 'Iniciando geração do curso', status: 'active', icon: 'rocket' },
      { id: 'slides', label: `Gerando ${slideCount} slides com IA`, status: 'pending', icon: 'layers' },
      ...(aiCount > 0 ? [{ id: 'images', label: `Criando ${aiCount} imagens com IA`, status: 'pending', icon: 'image', total: aiCount, completed: 0 }] : []),
      { id: 'save', label: 'Salvando e finalizando projeto', status: 'pending', icon: 'save' },
    ]);

    addChatMsg('agent', `Gerando o curso no Scormfy...${aiCount > 0 ? ` Criando ${aiCount} imagens com IA (pode levar ~${aiCount * 15}s).` : ''}${heyCount > 0 ? ` ${heyCount} vídeos HeyGen serão gerados em segundo plano.` : ''}${klingCount > 0 ? ` ${klingCount} cenas Kling serão geradas em segundo plano.` : ''}`);
    try {
      const res = await fetchRetry(`${API}/api/agent/sessions/${sessionId}/generate-course`, {
        method: 'POST',
        headers: authHeaders(genMode ? { 'Content-Type': 'application/json' } : undefined),
        ...(genMode ? { body: JSON.stringify({ mode: genMode }) } : {}),
      });
      if (!res.ok) throw new Error('Falha ao iniciar geração');
      const initData = await res.json();
      
      if (initData.status === 'already_done') {
        setGeneratedProject(initData);
        setCurrentStep(6);
        setGenerationPhases([]);
        return;
      }

      // Poll for completion
      const pollStatus = async () => {
        let lastProgressMsg = '';
        for (let i = 0; i < 360; i++) {
          await new Promise(r => setTimeout(r, 5000));
          try {
            const statusRes = await fetchRetry(`${API}/api/agent/sessions/${sessionId}/course-status`, { headers: authHeaders() }, 2);
            const statusData = await statusRes.json();
            if (statusData.message && statusData.message !== lastProgressMsg) {
              lastProgressMsg = statusData.message;
              addChatMsg('agent', `${statusData.message}`);

              // Update generation phases based on message
              setGenerationPhases(prev => {
                const next = [...prev];
                const msg = statusData.message.toLowerCase();
                if (msg.includes('slides com ia') || msg.includes('gerando slides')) {
                  next.forEach(p => { if (p.id === 'init') p.status = 'done'; });
                  const sp = next.find(p => p.id === 'slides');
                  if (sp) sp.status = 'active';
                } else if (msg.includes('imagens ia') || msg.includes('gerando imagens')) {
                  next.forEach(p => { if (p.id === 'init' || p.id === 'slides') p.status = 'done'; });
                  const ip = next.find(p => p.id === 'images');
                  if (ip) {
                    ip.status = 'active';
                    const match = statusData.message.match(/(\d+)\/(\d+)/);
                    if (match) { ip.completed = parseInt(match[1]); ip.total = parseInt(match[2]); }
                  }
                } else if (msg.includes('salvando')) {
                  next.forEach(p => { if (p.status !== 'pending' || p.id === 'save') {} else { p.status = 'done'; } });
                  next.forEach(p => { if (p.id !== 'save') p.status = 'done'; });
                  const sp = next.find(p => p.id === 'save');
                  if (sp) sp.status = 'active';
                }
                return next;
              });
            }
            if (statusData.status === 'done') {
              setGenerationPhases(prev => prev.map(p => ({ ...p, status: 'done' })));
              setGeneratedProject(statusData);
              if (statusData.projectId) setResumedProjectId(statusData.projectId);
              const heygenMsg = statusData.heygenPending > 0 ? ` ${statusData.heygenPending} vídeos HeyGen em processamento.` : '';
              const klingMsg = statusData.klingPending > 0 ? ` ${statusData.klingPending} cenas Kling em processamento.` : '';
              const narrationMsg = statusData.narrationPending > 0 ? ` ${statusData.narrationPending} narrações em geração.` : '';
              addChatMsg('agent', `Curso "${statusData.projectName}" criado! ${statusData.slidesCount} slides e ${statusData.quizCount} perguntas.${heygenMsg}${klingMsg}${narrationMsg}`);
              setTimeout(() => { setCurrentStep(6); setGenerationPhases([]); }, 1500);
              toast.success('Curso gerado com sucesso!');
              return;
            }
            if (statusData.status === 'error') {
              throw new Error(statusData.error || 'Erro na geração');
            }
          } catch (pollErr) {
            if (pollErr.message.includes('Erro')) throw pollErr;
          }
        }
        throw new Error('Timeout na geração do curso');
      };
      
      await pollStatus();
    } catch (e) {
      toast.error(e.message || 'Erro ao gerar curso');
      addChatMsg('agent', `Erro ao gerar o curso: ${e.message || 'Erro desconhecido'}`);
      setGenerationPhases([]);
    } finally {
      setLoading(false);
    }
  };

  // ===== EDIT MODE HANDLERS =====
  const loadAgentCourses = async () => {
    try {
      const res = await fetch(`${API}/api/agent/courses`, { headers: authHeaders() });
      const data = await res.json();
      setAgentCourses(data);
    } catch { toast.error('Erro ao carregar cursos'); }
  };

  const handleSelectMode = (m) => {
    setMode(m);
    setCurrentStep(0);
    if (m === 'create') {
      addChatMsg('agent', 'Envie o conteúdo que deseja transformar em curso. Você pode fazer upload de arquivo ou colar texto.');
    } else if (m === 'edit') {
      addChatMsg('agent', 'Selecione um curso para analisar e sugerir melhorias. Você pode escolher cursos criados pelo agente ou importados de PPT.');
      loadAgentCourses();
    } else if (m === 'approval') {
      addChatMsg('agent', 'Fila de aprovacao de storyboards. Revise, edite textos e aprove ou devolva para revisao.');
    }
  };

  const handleSelectCourse = (course) => {
    setSelectedCourse(course);
    addChatMsg('user', `Selecionei o curso: ${course.name}`);
    setCurrentStep(1);
    handleAnalyzeCourse(course);
  };

  const handleAnalyzeCourse = async (course) => {
    setLoading(true);
    addChatMsg('agent', `Analisando o curso "${course.name}"...`);
    try {
      const res = await fetch(`${API}/api/agent/courses/${course.id}/analyze`, { method: 'POST', headers: authHeaders() });
      if (!res.ok) throw new Error();
      const data = await res.json();

      // If result returned directly (not processing), use it
      if (data.overallScore !== undefined || data.improvements) {
        setCourseAnalysis(data);
        setSelectedImprovements([]);
        addChatMsg('agent', `Analise concluida! Nota geral: ${data.overallScore}/10. ${data.improvements?.length || 0} melhorias sugeridas.`);
      } else if (data.status === 'processing') {
        addChatMsg('agent', 'Analise em andamento... aguarde.');
        // Poll every 2s for faster response
        const maxWait = 180000;
        const start = Date.now();
        let result = null;
        while (Date.now() - start < maxWait) {
          await new Promise(r => setTimeout(r, 2000));
          const pollRes = await fetch(`${API}/api/agent/courses/${course.id}/analyze`, { method: 'POST', headers: authHeaders() });
          if (!pollRes.ok) continue;
          const pollData = await pollRes.json();
          if (pollData.overallScore !== undefined || pollData.improvements) {
            result = pollData;
            break;
          }
          if (pollData.status === 'error') throw new Error(pollData.error || 'Erro na analise');
        }
        if (!result) throw new Error('Timeout aguardando analise do curso');
        setCourseAnalysis(result);
        setSelectedImprovements([]);
        addChatMsg('agent', `Analise concluida! Nota geral: ${result.overallScore}/10. ${result.improvements?.length || 0} melhorias sugeridas.`);
      }
    } catch (e) { toast.error(e.message || 'Erro na analise'); addChatMsg('agent', 'Erro ao analisar o curso.'); }
    finally { setLoading(false); }
  };

  const toggleImprovement = (improvement) => {
    setSelectedImprovements(prev => {
      const exists = prev.find(p => p.description === improvement.description);
      if (exists) {
        return prev.filter(p => p.description !== improvement.description);
      }
      return [...prev, improvement];
    });
  };

  const toggleNewSlide = (newSlide) => {
    setSelectedNewSlides(prev => {
      const exists = prev.find(p => p.title === newSlide.title);
      if (exists) {
        return prev.filter(p => p.title !== newSlide.title);
      }
      return [...prev, newSlide];
    });
  };

  const handleTypeOverride = (impIndex, newType, extras = {}) => {
    // Update the type in selectedImprovements if it was selected
    setSelectedImprovements(prev => prev.map(imp => {
      const original = courseAnalysis?.improvements?.[impIndex];
      if (original && imp.description === original.description) {
        const updated = { ...imp, type: newType };
        // Krea: attach selected model + build the _kreaImage hint the backend pipeline reads.
        if (newType === 'imagem_krea') {
          const kreaModelId = extras.kreaModelId || 'flux-1-dev';
          updated.kreaModelId = kreaModelId;
          updated._kreaImage = {
            prompt: imp.imagePrompt || imp.description || '',
            modelId: kreaModelId,
            width: 1024,
            height: 576,
          };
        } else {
          // Switching away from Krea — clean up Krea-specific fields
          delete updated.kreaModelId;
          delete updated._kreaImage;
        }
        return updated;
      }
      return imp;
    }));
  };

  const handleScriptOverride = (impIndex, changes) => {
    // Update narrationScript/backgroundDescription/avatarPosition in selectedImprovements
    setSelectedImprovements(prev => prev.map(imp => {
      const original = courseAnalysis?.improvements?.[impIndex];
      if (original && imp.description === original.description) {
        return { ...imp, ...changes };
      }
      return imp;
    }));
  };

  const handleApplyImprovements = async () => {
    if (selectedImprovements.length === 0 && selectedNewSlides.length === 0) { toast.error('Selecione pelo menos uma melhoria ou novo slide'); return; }
    setLoading(true);
    const totalSelected = selectedImprovements.length + selectedNewSlides.length;
    addChatMsg('agent', `Gerando preview de ${totalSelected} melhorias...`);
    try {
      const res = await fetch(`${API}/api/agent/courses/${selectedCourse.id}/preview-improvements`, {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ improvements: selectedImprovements, selectedNewSlides: selectedNewSlides.length > 0 ? selectedNewSlides : null }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setPreviewData(data);
      setCurrentStep(2);
      addChatMsg('agent', `Preview pronto! ${data.updatedCount} slides alterados, ${data.newCount} novos slides. Revise as mudanças antes de confirmar.`);
    } catch { toast.error('Erro ao gerar preview'); addChatMsg('agent', 'Erro ao gerar preview das melhorias.'); }
    finally { setLoading(false); }
  };

  const handleConfirmImprovements = async () => {
    if (!previewData?.previewId) return;
    setLoading(true);
    setApplyProgress({ progress: 0, message: 'Iniciando aplicação...' });
    addChatMsg('agent', 'Aplicando melhorias ao curso (isso pode levar alguns minutos)...');
    try {
      // Step 1: Trigger background apply (returns 202 immediately with applyJobId)
      const res = await fetch(`${API}/api/agent/courses/${selectedCourse.id}/apply-improvements`, {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ improvements: selectedImprovements, selectedNewSlides: selectedNewSlides.length > 0 ? selectedNewSlides : null, previewId: previewData.previewId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Falha ao iniciar aplicação');
      }
      const startData = await res.json();

      // Backwards-compat: if backend ever returns synchronous result, use it directly
      if (startData.status !== 'processing' || !startData.applyJobId) {
        setApplyProgress(null);
        setEditResult(startData);
        setCurrentStep(3);
        toast.success('Melhorias aplicadas com sucesso!');
        return;
      }

      // Step 2: Poll /apply-status until done or error
      const jobId = startData.applyJobId;
      const startTime = Date.now();
      const MAX_WAIT_MS = 10 * 60 * 1000; // 10 minutes
      const POLL_INTERVAL_MS = 3000;

      while (true) {
        if (Date.now() - startTime > MAX_WAIT_MS) {
          throw new Error('Tempo limite excedido. As melhorias podem ainda estar sendo aplicadas em segundo plano.');
        }
        await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));

        const statusRes = await fetchRetry(
          `${API}/api/agent/courses/${selectedCourse.id}/apply-status/${jobId}`,
          { headers: authHeaders() },
        );
        // Auth/RBAC failures are terminal — break out instead of looping forever
        if (statusRes.status === 401 || statusRes.status === 403 || statusRes.status === 404) {
          throw new Error('Sessão expirada ou acesso negado. Faça login novamente.');
        }
        if (!statusRes.ok) continue; // other transient 5xx — keep trying
        const job = await statusRes.json();

        setApplyProgress({
          progress: job.progress ?? 0,
          message: job.message || 'Processando...',
        });

        if (job.status === 'done') {
          setApplyProgress(null);
          setEditResult(job);
          setCurrentStep(3);
          let msg = `Melhorias aplicadas! ${job.updatedSlides} slides atualizados, ${job.newSlides} novos slides. Total: ${job.totalSlides} slides.`;
          if (job.scenariosGenerated > 0) msg += ` ${job.scenariosGenerated} cenário(s) interativo(s) gerado(s).`;
          if (job.leonardoImagesGenerated > 0) msg += ` ${job.leonardoImagesGenerated} imagem(ns) premium (Leonardo).`;
          if (job.geminiImagesGenerated > 0) msg += ` ${job.geminiImagesGenerated} imagem(ns) econômica(s) (Gemini).`;
          if (job.avatarScenesTriggered > 0) msg += ` ${job.avatarScenesTriggered} cena(s) com avatar gerando em segundo plano.`;
          addChatMsg('agent', msg);
          toast.success('Melhorias aplicadas com sucesso!');
          return;
        }
        if (job.status === 'error') {
          throw new Error(job.error || 'Falha ao aplicar melhorias');
        }
        // status === 'processing' → keep polling
      }
    } catch (err) {
      setApplyProgress(null);
      const msg = err?.message || 'Erro ao aplicar melhorias';
      toast.error(msg);
      addChatMsg('agent', `Erro ao aplicar as melhorias: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  const handleUndoImprovements = async () => {
    if (!selectedCourse?.id) return;
    setLoading(true);
    addChatMsg('agent', 'Desfazendo melhorias...');
    try {
      const res = await fetch(`${API}/api/agent/courses/${selectedCourse.id}/undo-improvements`, {
        method: 'POST', headers: authHeaders(),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setEditResult(null);
      setPreviewData(null);
      setCourseAnalysis(null);
      setSelectedImprovements([]);
      setCurrentStep(0);
      addChatMsg('agent', `Melhorias desfeitas! O curso voltou ao estado original com ${data.totalSlides} slides.`);
      toast.success('Melhorias desfeitas com sucesso!');
      loadAgentCourses();
    } catch { toast.error('Erro ao desfazer melhorias'); addChatMsg('agent', 'Erro ao desfazer as melhorias.'); }
    finally { setLoading(false); }
  };

  const handleCancelPreview = () => {
    setPreviewData(null);
    setCurrentStep(1);
    addChatMsg('agent', 'Preview cancelado. Você pode ajustar as melhorias selecionadas e tentar novamente.');
  };

  const handleSubmitImprovementsForApproval = async (targetCompanyId) => {
    if (!previewData?.previewId || !selectedCourse?.id) return;
    setLoading(true);
    addChatMsg('agent', 'Enviando melhorias para aprovacao...');
    try {
      const res = await fetch(`${API}/api/agent/courses/${selectedCourse.id}/submit-improvements-for-approval`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          previewId: previewData.previewId,
          targetCompanyId,
          improvements: selectedImprovements,
          selectedNewSlides: selectedNewSlides.length > 0 ? selectedNewSlides : null,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        addChatMsg('agent', `Melhorias enviadas para aprovacao da empresa "${data.targetCompany}"! ${data.updatedCount} slides alterados e ${data.newCount} novos slides aguardam revisao.`);
        toast.success('Melhorias enviadas para aprovacao');
        setPreviewData(null);
        setCurrentStep(0);
        setCourseAnalysis(null);
        setSelectedImprovements([]);
        setSelectedNewSlides([]);
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Erro ao enviar para aprovacao');
      }
    } catch {
      toast.error('Erro ao enviar para aprovacao');
    }
    setLoading(false);
  };

  // Chat with agent
  const handleChat = async () => {
    if (!chatInput.trim() || !sessionId) return;
    const msg = chatInput;
    setChatInput('');
    addChatMsg('user', msg);
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/chat`, {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ message: msg }),
      });
      const data = await res.json();
      const response = data.response || '';

      // Check if agent wants to add a scenario
      if (response.includes('[AÇÃO:CENÁRIO]')) {
        const cleanResponse = response.replace('[AÇÃO:CENÁRIO]', '').trim();
        addChatMsg('agent', cleanResponse || 'Gerando cenário interativo para o curso...');
        // Trigger async scenario generation - get projectId from generatedProject or editMediaProjectId
        const currentProjectId = generatedProject?.projectId || editMediaProjectId;
        if (currentProjectId) {
          addChatMsg('agent', '⏳ Gerando cenário interativo com IA... isso pode levar alguns segundos.');
          try {
            const scenarioRes = await fetch(`${API}/api/agent/sessions/${sessionId}/add-scenario`, {
              method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
              body: JSON.stringify({ projectId: currentProjectId }),
            });
            const scenarioData = await scenarioRes.json();
            if (scenarioData.success) {
              addChatMsg('agent', `✅ Cenário "${scenarioData.scenario?.title}" adicionado ao curso com ${scenarioData.scenario?.nodes?.length || 0} cenas! Você pode visualizá-lo no editor.`);
            } else {
              addChatMsg('agent', `Não foi possível gerar o cenário: ${scenarioData.detail || 'erro desconhecido'}`);
            }
          } catch (e) {
            addChatMsg('agent', 'Erro ao gerar cenário. Tente novamente.');
          }
        } else {
          addChatMsg('agent', 'Para adicionar um cenário, primeiro gere o curso.');
        }
      } else {
        addChatMsg('agent', response);
      }
    } catch { addChatMsg('agent', 'Erro ao processar mensagem.'); }
    finally { setLoading(false); }
  };

  const steps = mode === 'edit' ? EDIT_STEPS : CREATE_STEPS;

  // Show loading while checking access
  if (authLoading || !accessChecked) {
    return (
      <div className="h-screen flex items-center justify-center bg-slate-950" data-testid="agent-loading">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
          <span className="text-slate-400">Verificando acesso...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-slate-950 text-white" data-testid="agent-page">
      {/* Header */}
      <header className="h-14 border-b border-slate-800 flex items-center px-4 gap-3 shrink-0">
        <Button variant="ghost" size="sm" onClick={() => {
          if (mode && !(isAprovador && !isSuperAdmin)) {
            setMode(null);
            setCurrentStep(0);
          } else if (isAprovador && !isSuperAdmin) {
            if (mode) { setMode(null); setCurrentStep(0); }
            // Aprovador can't go to dashboard - just reset mode
          } else {
            navigate('/');
          }
        }} data-testid="back-to-dashboard">
          <ArrowLeft className="w-4 h-4 mr-1" /> {mode ? 'Voltar' : (isAprovador && !isSuperAdmin) ? 'Painel' : 'Dashboard'}
        </Button>
        <div className="w-px h-6 bg-slate-700" />
        <Brain className="w-5 h-5 text-emerald-400" />
        <span className="font-semibold text-sm">Agente de Design Instrucional</span>
        {mode && (
          <Badge className={`text-[10px] ${mode === 'create' ? 'bg-emerald-600/20 text-emerald-300' : mode === 'approval' ? 'bg-amber-600/20 text-amber-300' : 'bg-blue-600/20 text-blue-300'}`}>
            {mode === 'create' ? 'Novo Curso' : mode === 'approval' ? 'Fila de Aprovacao' : 'Editar Curso'}
          </Badge>
        )}
        <div className="flex-1" />
        {mode && mode !== 'approval' && (
          <div className="hidden md:flex items-center gap-1">
            {steps.map((step, i) => {
              const Icon = step.icon;
              const active = i === currentStep;
              const done = i < currentStep;
              const clickable = !loading && i !== currentStep && canJumpToStep(i);
              return (
                <div
                  key={step.id}
                  onClick={clickable ? () => setCurrentStep(i) : undefined}
                  role={clickable ? 'button' : undefined}
                  title={clickable ? `Ir para ${step.label}` : undefined}
                  data-testid={`step-nav-${step.id}`}
                  className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${active ? 'bg-emerald-600/20 text-emerald-400' : done ? 'text-emerald-500/60' : 'text-slate-500'} ${clickable ? 'cursor-pointer hover:bg-slate-800 hover:text-emerald-300 transition-colors' : ''}`}
                >
                  {done ? <Check className="w-3 h-3" /> : <Icon className="w-3 h-3" />}
                  <span className="hidden lg:inline">{step.label}</span>
                  {i < steps.length - 1 && <ChevronRight className="w-3 h-3 text-slate-600 ml-1" />}
                </div>
              );
            })}
          </div>
        )}
        <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setShowChat(!showChat)}>
          {showChat ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
        </Button>
        {/* Logout button for Aprovador (no dashboard access) */}
        {isAprovador && !isSuperAdmin && (
          <Button variant="ghost" size="sm" onClick={() => { logout(); navigate('/login'); }} className="text-slate-400 hover:text-red-400" data-testid="aprovador-logout">
            <LogOut className="w-4 h-4 mr-1" /> Sair
          </Button>
        )}
      </header>

      {/* Regenerate choice dialog for resumed sessions */}
      <Dialog open={generateChoiceOpen} onOpenChange={setGenerateChoiceOpen}>
        <DialogContent className="bg-slate-900 border-slate-700 text-white" data-testid="generate-choice-dialog">
          <DialogHeader>
            <DialogTitle>Este curso já foi gerado</DialogTitle>
            <DialogDescription className="text-slate-400">
              Você está gerando novamente um curso que já existe. Como deseja prosseguir?
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 pt-2">
            <Button className="w-full bg-emerald-600 hover:bg-emerald-700 justify-start" onClick={() => handleGenerateChoice('new')} data-testid="generate-new-course-btn">
              <Plus className="w-4 h-4 mr-2" /> Criar um NOVO curso (o atual permanece intacto)
            </Button>
            <Button variant="destructive" className="w-full justify-start" onClick={() => handleGenerateChoice('replace')} data-testid="generate-replace-course-btn">
              <RefreshCw className="w-4 h-4 mr-2" /> SUBSTITUIR o curso existente (o antigo será excluído)
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Main content */}
      <div className="flex-1 flex min-h-0">
        {/* Left Panel */}
        <div className={`flex-1 flex flex-col min-w-0 ${showChat ? 'hidden md:flex' : 'flex'}`}>
          <ScrollArea className="flex-1">
            <div className="p-6 max-w-4xl mx-auto space-y-6">
              {!mode && <ModeSelector onSelect={handleSelectMode} showApprovalQueue={isSuperAdmin || isAprovador} isAprovadorOnly={isAprovador && !isSuperAdmin} />}

              {/* APPROVAL QUEUE MODE */}
              {mode === 'approval' && <ApprovalQueuePanel onResumeSession={handleResumeApprovedSession} />}

              {/* CREATE MODE */}
              {mode === 'create' && currentStep === 0 && <UploadPanel contentText={contentText} setContentText={setContentText} contentUrl={contentUrl} setContentUrl={setContentUrl} fileName={fileName} fileInputRef={fileInputRef} handleFileUpload={handleFileUpload} handleTextSubmit={handleTextSubmit} handleUrlSubmit={handleUrlSubmit} loading={loading} agentCompanyId={agentCompanyId} setAgentCompanyId={setAgentCompanyId} />}
              {mode === 'create' && currentStep === 1 && <AnalyzePanel analysis={analysis} loading={loading} onAnalyze={handleAnalyze} sessionId={sessionId} apiBase={API} />}
              {mode === 'create' && currentStep === 2 && <ConfigPanel config={config} setConfig={setConfig} analysis={analysis} loading={loading} onGenerate={handleGenerateStructure} templates={templates} selectedTemplate={selectedTemplate} setSelectedTemplate={setSelectedTemplate} designTemplates={designTemplates} selectedDesignTemplate={selectedDesignTemplate} setSelectedDesignTemplate={setSelectedDesignTemplate} />}
              {mode === 'create' && currentStep === 3 && <StructurePanel structure={structure} loading={loading} onApprove={handleGenerateStoryboard} progressMsg={storyboardProgressMsg} />}
              {mode === 'create' && currentStep === 4 && <StoryboardPanel storyboard={storyboard} loading={loading} onApprove={handleApproveStoryboard} onSubmitForApproval={handleSubmitForApproval} config={config} setConfig={setConfig} sessionId={sessionId} companies={companiesList} />}
              {mode === 'create' && currentStep === 5 && <MediaConfigPanel storyboard={storyboard} mediaConfig={mediaConfig} setMediaConfig={setMediaConfig} loading={loading} onConfirm={handleSaveMediaConfig} heygenConfig={heygenConfig} setHeygenConfig={setHeygenConfig} bgConfig={bgConfig} setBgConfig={setBgConfig} sessionId={sessionId} globalTextColor={globalTextColor} setGlobalTextColor={setGlobalTextColor} globalFontSize={globalFontSize} setGlobalFontSize={setGlobalFontSize} globalAnimation={globalAnimation} setGlobalAnimation={setGlobalAnimation} isEditMode={!!editMediaProjectId} originalMediaConfig={originalMediaConfig} originalBgConfig={originalBgConfig} projectId={editMediaProjectId} selectedDesignTemplate={selectedDesignTemplate} setSelectedDesignTemplate={setSelectedDesignTemplate} useBrandLibrary={useBrandLibrary} setUseBrandLibrary={setUseBrandLibrary} brandLibraryMode={brandLibraryMode} setBrandLibraryMode={setBrandLibraryMode} brandLibraryCount={brandLibraryCount} brandLibraryCompanyId={agentCompanyId || authUser?.companyId} />}
              {mode === 'create' && generationPhases.length > 0 && !generatedProject && (
                <GeneratingProgressPanel phases={generationPhases} startTime={generationStartTime} config={config} storyboard={storyboard} mediaConfig={mediaConfig} />
              )}
              {mode === 'create' && currentStep === 6 && generatedProject && <GeneratedPanel project={generatedProject} navigate={navigate} sessionId={sessionId} />}

              {/* EDIT MODE */}
              {mode === 'edit' && currentStep === 0 && <CourseListPanel courses={agentCourses} loading={loading} onSelect={handleSelectCourse} onRefresh={loadAgentCourses} onReopenWizard={handleReopenWizard} />}
              {mode === 'edit' && currentStep === 1 && <CourseReviewPanel course={selectedCourse} analysis={courseAnalysis} loading={loading} selectedImprovements={selectedImprovements} toggleImprovement={toggleImprovement} selectedNewSlides={selectedNewSlides} toggleNewSlide={toggleNewSlide} onApply={handleApplyImprovements} onTypeOverride={handleTypeOverride} onScriptOverride={handleScriptOverride} />}
              {mode === 'edit' && currentStep === 2 && <PreviewPanel preview={previewData} loading={loading} applyProgress={applyProgress} onConfirm={handleConfirmImprovements} onCancel={handleCancelPreview} onSubmitForApproval={isSuperAdmin ? handleSubmitImprovementsForApproval : null} companies={companiesList} />}
              {mode === 'edit' && currentStep === 3 && <EditResultPanel result={editResult} course={selectedCourse} navigate={navigate} onUndo={handleUndoImprovements} loading={loading} />}
            </div>
          </ScrollArea>
        </div>

        {/* Right Panel - Chat */}
        <div className={`w-full md:w-96 lg:w-[420px] border-l border-slate-800 flex flex-col bg-slate-900/50 shrink-0 ${showChat ? 'flex' : 'hidden'}`}>
          {/* During Storyboard review, show the conversational editor instead of
              the passive progress log. */}
          {mode === 'create' && currentStep === 4 && sessionId ? (
            <StoryboardChat
              sessionId={sessionId}
              onStoryboardUpdate={(updated) => {
                if (updated) setStoryboard(updated);
              }}
            />
          ) : mode === 'create' && currentStep === 5 && sessionId ? (
            <MediaConfigChat
              sessionId={sessionId}
              onMediaConfigUpdate={({ mediaConfig: mc, bgConfig: bc }) => {
                if (mc) setMediaConfig(mc);
                if (bc) setBgConfig(bc);
              }}
            />
          ) : (
            <>
              <div className="p-3 border-b border-slate-800 flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-medium">Chat com o Agente</span>
                <Button variant="ghost" size="icon" className="ml-auto md:hidden" onClick={() => setShowChat(false)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
          <ScrollArea className="flex-1 p-3">
            <div className="space-y-3">
              {chatMessages.map((msg, i) => {
                const isProgress = msg.text?.match(/gerando|criando|salvando|processando|iniciando/i) && msg.role === 'agent';
                const isSuccess = msg.text?.match(/criado!|completo|configurada!|criada!/i) && msg.role === 'agent';
                const isError = msg.text?.match(/erro|falha|timeout/i) && msg.role === 'agent';
                return (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm flex items-start gap-2 ${
                      msg.role === 'user' ? 'bg-emerald-600/20 text-emerald-100' :
                      isError ? 'bg-red-900/20 border border-red-800/30 text-red-200' :
                      isSuccess ? 'bg-emerald-900/20 border border-emerald-800/30 text-emerald-200' :
                      isProgress ? 'bg-slate-800 text-slate-300' :
                      'bg-slate-800 text-slate-200'
                    }`}>
                      {msg.role === 'agent' && isProgress && <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-400 shrink-0 mt-0.5" />}
                      {msg.role === 'agent' && isSuccess && <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />}
                      {msg.role === 'agent' && isError && <AlertTriangle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />}
                      <span>{msg.text}</span>
                    </div>
                  </div>
                );
              })}
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-slate-800 rounded-lg px-3 py-2 text-sm text-slate-400 flex items-center gap-2">
                    <Loader2 className="w-3 h-3 animate-spin" /> Processando...
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
          </ScrollArea>
          <div className="p-3 border-t border-slate-800">
            <div className="flex gap-2">
              <Input
                data-testid="agent-chat-input"
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleChat()}
                placeholder="Pergunte ao agente..."
                className="bg-slate-800 border-slate-700 text-sm"
                disabled={loading || !sessionId}
              />
              <Button size="icon" onClick={handleChat} disabled={loading || !sessionId || !chatInput.trim()} data-testid="agent-chat-send">
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ====================== Sub-panels ====================== */

function ModeSelector({ onSelect, showApprovalQueue, isAprovadorOnly }) {
  return (
    <div className="space-y-8" data-testid="mode-selector">
      <div className="text-center space-y-2">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-emerald-600/10 mb-2">
          <Sparkles className="w-8 h-8 text-emerald-400" />
        </div>
        <h1 className="text-2xl font-bold">
          {isAprovadorOnly ? 'Painel do Aprovador' : 'Agente de Design Instrucional'}
        </h1>
        <p className="text-slate-400 text-sm max-w-lg mx-auto">
          {isAprovadorOnly
            ? 'Revise e aprove storyboards enviados para sua empresa.'
            : 'Crie cursos profissionais do zero ou melhore cursos existentes com inteligencia artificial.'}
        </p>
      </div>

      <div className={`grid gap-6 max-w-3xl mx-auto ${isAprovadorOnly ? 'md:grid-cols-1 max-w-md' : showApprovalQueue ? 'md:grid-cols-3' : 'md:grid-cols-2'}`}>
        {!isAprovadorOnly && (
          <Card
            className="bg-slate-900/50 border-slate-800 hover:border-emerald-500/50 transition-all cursor-pointer group"
            onClick={() => onSelect('create')}
            data-testid="mode-create"
          >
            <CardContent className="p-8 text-center space-y-4">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-emerald-600/10 group-hover:bg-emerald-600/20 transition-colors">
                <Plus className="w-7 h-7 text-emerald-400" />
              </div>
              <div>
                <h3 className="font-semibold text-base mb-1">Criar Novo Curso</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Transforme qualquer conteudo em um curso completo com estrutura pedagogica, quizzes e multimidia.
                </p>
              </div>
              <div className="flex flex-wrap gap-1 justify-center">
                <Badge variant="outline" className="text-[10px] border-slate-700">PDF</Badge>
                <Badge variant="outline" className="text-[10px] border-slate-700">PPT</Badge>
                <Badge variant="outline" className="text-[10px] border-slate-700">DOC</Badge>
                <Badge variant="outline" className="text-[10px] border-slate-700">Texto</Badge>
              </div>
            </CardContent>
          </Card>
        )}

        {!isAprovadorOnly && (
          <Card
            className="bg-slate-900/50 border-slate-800 hover:border-blue-500/50 transition-all cursor-pointer group"
            onClick={() => onSelect('edit')}
            data-testid="mode-edit"
          >
            <CardContent className="p-8 text-center space-y-4">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-blue-600/10 group-hover:bg-blue-600/20 transition-colors">
                <Pencil className="w-7 h-7 text-blue-400" />
              </div>
              <div>
                <h3 className="font-semibold text-base mb-1">Editar Curso Existente</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Analise e melhore cursos criados pelo agente com sugestoes inteligentes de conteudo e estrutura.
                </p>
              </div>
              <div className="flex flex-wrap gap-1 justify-center">
                <Badge variant="outline" className="text-[10px] border-slate-700">Analise IA</Badge>
                <Badge variant="outline" className="text-[10px] border-slate-700">Melhorias</Badge>
                <Badge variant="outline" className="text-[10px] border-slate-700">Novos Slides</Badge>
              </div>
            </CardContent>
          </Card>
        )}

        {showApprovalQueue && (
          <Card
            className="bg-slate-900/50 border-slate-800 hover:border-amber-500/50 transition-all cursor-pointer group"
            onClick={() => onSelect('approval')}
            data-testid="mode-approval"
          >
            <CardContent className="p-8 text-center space-y-4">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-amber-600/10 group-hover:bg-amber-600/20 transition-colors">
                <BookOpenCheck className="w-7 h-7 text-amber-400" />
              </div>
              <div>
                <h3 className="font-semibold text-base mb-1">Fila de Aprovacao</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Revise storyboards pendentes, edite textos e aprove ou devolva para revisao.
                </p>
              </div>
              <div className="flex flex-wrap gap-1 justify-center">
                <Badge variant="outline" className="text-[10px] border-amber-700">Revisar</Badge>
                <Badge variant="outline" className="text-[10px] border-amber-700">Editar</Badge>
                <Badge variant="outline" className="text-[10px] border-amber-700">Aprovar</Badge>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

function UploadPanel({ contentText, setContentText, contentUrl, setContentUrl, fileName, fileInputRef, handleFileUpload, handleTextSubmit, handleUrlSubmit, loading, agentCompanyId, setAgentCompanyId }) {
  return (
    <div className="space-y-6" data-testid="upload-panel">
      <div className="text-center space-y-2">
        <h1 className="text-xl font-bold">Envie o Conteúdo</h1>
        <p className="text-slate-400 text-sm max-w-lg mx-auto">
          Faça upload de um arquivo, cole o texto ou insira um link.
        </p>
      </div>
      {/* Company picker (super_admin only — hidden for everyone else) */}
      <div className="max-w-md mx-auto">
        <CompanySelector
          value={agentCompanyId}
          onChange={setAgentCompanyId}
          testIdPrefix="agent-company"
        />
      </div>
      <div className="grid md:grid-cols-3 gap-4">
        {/* File Upload */}
        <Card className="bg-slate-900/50 border-slate-800 hover:border-emerald-600/40 transition-colors cursor-pointer"
          onClick={() => fileInputRef.current?.click()}>
          <CardContent className="p-5 text-center space-y-3">
            <Upload className="w-10 h-10 text-emerald-400 mx-auto" />
            <div>
              <p className="font-medium text-sm">Upload de Arquivo</p>
              <p className="text-xs text-slate-400">PDF, DOCX, PPT, TXT</p>
            </div>
            {fileName && !fileName.startsWith('http') && <Badge variant="secondary" className="text-xs">{fileName}</Badge>}
            <input ref={fileInputRef} type="file" className="hidden" accept=".pdf,.ppt,.pptx,.doc,.docx,.txt" onChange={handleFileUpload} data-testid="file-upload-input" />
          </CardContent>
        </Card>

        {/* Text Input */}
        <Card className="bg-slate-900/50 border-slate-800">
          <CardContent className="p-5 space-y-3">
            <FileText className="w-10 h-10 text-blue-400 mx-auto" />
            <p className="font-medium text-sm text-center">Texto Direto</p>
            <Textarea data-testid="content-text-input" value={contentText} onChange={e => setContentText(e.target.value)} placeholder="Cole ou digite o conteúdo aqui..." className="bg-slate-800 border-slate-700 text-sm min-h-[100px]" />
            <Button onClick={handleTextSubmit} disabled={loading || !contentText.trim()} className="w-full bg-emerald-600 hover:bg-emerald-700" size="sm" data-testid="submit-text-btn">
              {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Send className="w-4 h-4 mr-1" />}
              Enviar Texto
            </Button>
          </CardContent>
        </Card>

        {/* URL Input */}
        <Card className="bg-slate-900/50 border-slate-800">
          <CardContent className="p-5 space-y-3">
            <Lightbulb className="w-10 h-10 text-amber-400 mx-auto" />
            <p className="font-medium text-sm text-center">Link / Website</p>
            <Input
              data-testid="content-url-input"
              value={contentUrl}
              onChange={e => setContentUrl(e.target.value)}
              placeholder="https://example.com/artigo..."
              className="bg-slate-800 border-slate-700 text-sm"
            />
            <Button onClick={handleUrlSubmit} disabled={loading || !contentUrl.trim()} className="w-full bg-amber-600 hover:bg-amber-700" size="sm" data-testid="submit-url-btn">
              {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Send className="w-4 h-4 mr-1" />}
              Extrair Conteúdo
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function AnalyzePanel({ analysis, loading, onAnalyze, sessionId, apiBase }) {
  const [pdfProcessing, setPdfProcessing] = useState(false);
  return (
    <div className="space-y-4" data-testid="analyze-panel">
      {sessionId && apiBase && (
        <PdfPreviewPanel
          sessionId={sessionId}
          apiBase={apiBase}
          onStatusChange={setPdfProcessing}
        />
      )}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold flex items-center gap-2"><Brain className="w-5 h-5 text-emerald-400" /> Análise do Conteúdo</h2>
        <Button
          onClick={() => onAnalyze(!!analysis)}
          disabled={loading || pdfProcessing}
          title={pdfProcessing ? 'Aguarde a extracao do PDF terminar' : undefined}
          variant={analysis ? 'outline' : 'default'}
          className={analysis ? 'border-amber-500/40 text-amber-300 hover:bg-amber-600/10' : 'bg-emerald-600 hover:bg-emerald-700'}
          data-testid="analyze-btn"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : analysis ? <RefreshCw className="w-4 h-4 mr-1" /> : <Sparkles className="w-4 h-4 mr-1" />}
          {pdfProcessing ? 'Aguardando PDF...' : analysis ? 'Reanalisar Conteúdo' : 'Analisar Conteúdo'}
        </Button>
      </div>
      {analysis && (
        <div className="grid gap-4">
          <Card className="bg-slate-900/50 border-slate-800">
            <CardContent className="p-4 space-y-3">
              <h3 className="font-semibold text-emerald-400">{analysis.title}</h3>
              <p className="text-sm text-slate-300">{analysis.summary}</p>
              <div className="flex flex-wrap gap-2">
                <Badge className="bg-blue-600/20 text-blue-300">{analysis.difficulty}</Badge>
                <Badge className="bg-purple-600/20 text-purple-300"><Clock className="w-3 h-3 mr-1" />{analysis.estimatedDuration} min</Badge>
                <Badge className="bg-amber-600/20 text-amber-300"><Layers className="w-3 h-3 mr-1" />{analysis.suggestedModules} módulos</Badge>
              </div>
            </CardContent>
          </Card>
          <div className="grid md:grid-cols-2 gap-4">
            <Card className="bg-slate-900/50 border-slate-800">
              <CardHeader className="pb-2"><CardTitle className="text-sm text-slate-400">Tópicos Principais</CardTitle></CardHeader>
              <CardContent className="pt-0">
                <ul className="space-y-1">{analysis.mainTopics?.map((t, i) => <li key={i} className="text-sm flex items-start gap-2"><ChevronRight className="w-3 h-3 mt-1 text-emerald-400 shrink-0" />{t}</li>)}</ul>
              </CardContent>
            </Card>
            <Card className="bg-slate-900/50 border-slate-800">
              <CardHeader className="pb-2"><CardTitle className="text-sm text-slate-400">Palavras-chave</CardTitle></CardHeader>
              <CardContent className="pt-0">
                <div className="flex flex-wrap gap-1">{analysis.keywords?.map((k, i) => <Badge key={i} variant="outline" className="text-xs border-slate-600">{k}</Badge>)}</div>
              </CardContent>
            </Card>
          </div>
          {analysis.gaps?.length > 0 && (
            <Card className="bg-amber-900/10 border-amber-800/30">
              <CardHeader className="pb-2"><CardTitle className="text-sm text-amber-400 flex items-center gap-1"><Lightbulb className="w-4 h-4" /> Lacunas Identificadas</CardTitle></CardHeader>
              <CardContent className="pt-0">
                <ul className="space-y-1">{analysis.gaps.map((g, i) => <li key={i} className="text-sm text-amber-200">{g}</li>)}</ul>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

function StructurePanel({ structure, loading, onApprove, progressMsg }) {
  if (!structure) return null;
  return (
    <div className="space-y-4" data-testid="structure-panel">
      <h2 className="text-lg font-semibold flex items-center gap-2"><Layers className="w-5 h-5 text-emerald-400" /> Estrutura do Curso</h2>
      <Card className="bg-slate-900/50 border-slate-800">
        <CardContent className="p-4 space-y-2">
          <h3 className="font-semibold text-emerald-400">{structure.courseTitle}</h3>
          <p className="text-sm text-slate-300">{structure.courseDescription}</p>
          {structure.learningObjectives?.length > 0 && (
            <div>
              <span className="text-xs text-slate-400">Objetivos de Aprendizagem:</span>
              <ul className="mt-1 space-y-1">{structure.learningObjectives.map((o, i) => <li key={i} className="text-sm flex gap-2"><GraduationCap className="w-3 h-3 mt-1 text-emerald-400 shrink-0" />{o}</li>)}</ul>
            </div>
          )}
        </CardContent>
      </Card>
      {structure.modules?.map((mod, mi) => (
        <Card key={mi} className="bg-slate-900/50 border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Badge className="bg-emerald-600/20 text-emerald-300 text-xs">Módulo {mi + 1}</Badge>
              {mod.title}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0 space-y-1">
            <p className="text-xs text-slate-400 mb-2">{mod.description}</p>
            {mod.slides?.map((sl, si) => (
              <div key={si} className="flex items-center gap-2 text-sm py-1 px-2 rounded bg-slate-800/50">
                <Badge variant="outline" className={`text-[10px] ${sl.type === 'quiz' ? 'border-amber-500 text-amber-400' : sl.type === 'title' ? 'border-blue-500 text-blue-400' : sl.type === 'summary' ? 'border-purple-500 text-purple-400' : 'border-slate-600 text-slate-400'}`}>
                  {sl.type}
                </Badge>
                <span className="text-slate-300">{sl.title}</span>
                <span className="text-xs text-slate-500 ml-auto">{sl.estimatedDuration}s</span>
              </div>
            ))}
          </CardContent>
        </Card>
      ))}

      {/* Progress indicator during storyboard generation */}
      {progressMsg && (
        <Card className="bg-emerald-900/10 border-emerald-800/30" data-testid="storyboard-progress-card">
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center gap-3">
              <Loader2 className="w-5 h-5 text-emerald-400 animate-spin shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium text-emerald-300">Gerando Storyboard...</p>
                <p className="text-xs text-emerald-400/70 mt-0.5">{progressMsg}</p>
              </div>
            </div>
            <p className="text-[11px] text-slate-500">Cada lote de slides leva ~30-90s. O GPT-4o é usado automaticamente se o GPT-5.2 estiver lento. Tempo estimado: 5-10 minutos.</p>
          </CardContent>
        </Card>
      )}

      <Button onClick={onApprove} disabled={loading} className="w-full bg-emerald-600 hover:bg-emerald-700" data-testid="approve-structure-btn">
        {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <BookOpen className="w-4 h-4 mr-1" />}
        {loading ? 'Gerando Storyboard...' : 'Aprovar e Gerar Storyboard'}
      </Button>
    </div>
  );
}


function GeneratingProgressPanel({ phases, startTime, config, storyboard, mediaConfig }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!startTime) return;
    const iv = setInterval(() => setElapsed(Math.floor((Date.now() - startTime) / 1000)), 1000);
    return () => clearInterval(iv);
  }, [startTime]);

  const doneCount = phases.filter(p => p.status === 'done').length;
  const totalCount = phases.length;
  const activePhase = phases.find(p => p.status === 'active');
  const progressPercent = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0;

  // For image phase, compute finer progress
  const imagePhase = phases.find(p => p.id === 'images');
  let effectivePercent = progressPercent;
  if (activePhase?.id === 'images' && imagePhase?.total > 0) {
    const basePercent = Math.round((doneCount / totalCount) * 100);
    const phaseWidth = Math.round(100 / totalCount);
    effectivePercent = basePercent + Math.round((imagePhase.completed / imagePhase.total) * phaseWidth);
  }
  if (doneCount === totalCount) effectivePercent = 100;

  const formatTime = (s) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const slideCount = storyboard?.slides?.length || 0;
  const aiCount = Object.values(mediaConfig || {}).filter(m => m.type === 'ai_image').length;
  const heyCount = Object.values(mediaConfig || {}).filter(m => m.type === 'heygen').length;

  const phaseIcons = {
    rocket: Rocket, layers: Layers, image: Image, save: Check,
  };

  return (
    <div className="space-y-6" data-testid="generating-progress-panel">
      {/* Header */}
      <div className="text-center space-y-2">
        <div className="relative mx-auto w-16 h-16 flex items-center justify-center">
          <div className="absolute inset-0 rounded-full bg-emerald-500/10 animate-ping" style={{ animationDuration: '2s' }} />
          <div className="absolute inset-1 rounded-full bg-emerald-500/5" />
          <Sparkles className="w-8 h-8 text-emerald-400 animate-pulse" />
        </div>
        <h2 className="text-xl font-semibold text-slate-100">Gerando seu Curso</h2>
        <p className="text-sm text-slate-400">{config?.title || 'Curso'}</p>
      </div>

      {/* Main progress bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-xs text-slate-400">
          <span>Progresso geral</span>
          <span className="tabular-nums font-medium text-emerald-400">{effectivePercent}%</span>
        </div>
        <div className="h-3 bg-slate-800 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-1000 ease-out"
            style={{
              width: `${Math.max(effectivePercent, 3)}%`,
              background: 'linear-gradient(90deg, #059669, #10b981, #34d399)',
            }}
          />
        </div>
        <div className="flex justify-between text-[11px] text-slate-500">
          <span>Tempo: {formatTime(elapsed)}</span>
          <span>{doneCount}/{totalCount} etapas concluídas</span>
        </div>
      </div>

      {/* Phase timeline */}
      <Card className="bg-slate-900/50 border-slate-800">
        <CardContent className="p-4 space-y-0">
          {phases.map((phase, idx) => {
            const Icon = phaseIcons[phase.icon] || Layers;
            const isActive = phase.status === 'active';
            const isDone = phase.status === 'done';
            const isPending = phase.status === 'pending';
            return (
              <div key={phase.id} className="flex items-start gap-3 relative" data-testid={`phase-${phase.id}`}>
                {/* Vertical connector */}
                {idx < phases.length - 1 && (
                  <div className={`absolute left-[15px] top-[32px] w-0.5 h-[calc(100%-16px)] ${isDone ? 'bg-emerald-500/50' : 'bg-slate-700'}`} />
                )}
                {/* Icon circle */}
                <div className={`relative z-10 shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-all ${
                  isDone ? 'bg-emerald-500/20 text-emerald-400' :
                  isActive ? 'bg-emerald-500/10 text-emerald-300 ring-2 ring-emerald-500/40' :
                  'bg-slate-800 text-slate-500'
                }`}>
                  {isDone ? <Check className="w-4 h-4" /> :
                   isActive ? <Loader2 className="w-4 h-4 animate-spin" /> :
                   <Icon className="w-4 h-4" />}
                </div>
                {/* Content */}
                <div className={`flex-1 pb-4 ${isPending ? 'opacity-40' : ''}`}>
                  <p className={`text-sm font-medium ${isDone ? 'text-emerald-400' : isActive ? 'text-slate-100' : 'text-slate-400'}`}>
                    {phase.label}
                  </p>
                  {isActive && phase.id === 'images' && phase.total > 0 && (
                    <div className="mt-1.5 space-y-1">
                      <div className="h-1.5 w-full bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full bg-emerald-400 transition-all duration-700"
                          style={{ width: `${Math.round((phase.completed / phase.total) * 100)}%` }}
                        />
                      </div>
                      <p className="text-[11px] text-slate-500">{phase.completed} de {phase.total} imagens</p>
                    </div>
                  )}
                  {isActive && phase.id !== 'images' && (
                    <p className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1">
                      <span className="inline-block w-1 h-1 rounded-full bg-emerald-400 animate-pulse" />
                      Em andamento...
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-slate-800/50 rounded-lg p-3 text-center">
          <Layers className="w-5 h-5 text-blue-400 mx-auto mb-1" />
          <p className="text-lg font-bold text-slate-100">{slideCount}</p>
          <p className="text-[11px] text-slate-400">Slides</p>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-3 text-center">
          <Image className="w-5 h-5 text-purple-400 mx-auto mb-1" />
          <p className="text-lg font-bold text-slate-100">{aiCount}</p>
          <p className="text-[11px] text-slate-400">Imagens IA</p>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-3 text-center">
          <Clock className="w-5 h-5 text-amber-400 mx-auto mb-1" />
          <p className="text-lg font-bold text-slate-100 tabular-nums">{formatTime(elapsed)}</p>
          <p className="text-[11px] text-slate-400">Tempo</p>
        </div>
      </div>

      {/* Tip */}
      <div className="bg-slate-800/30 rounded-lg p-3 flex items-start gap-2">
        <Lightbulb className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        <p className="text-xs text-slate-400">
          A geração pode levar alguns minutos dependendo da quantidade de slides e imagens.
          Não feche esta janela durante o processo.
        </p>
      </div>
    </div>
  );
}


function CourseListPanel({ courses, loading, onSelect, onRefresh, onReopenWizard }) {
  const [filter, setFilter] = useState('all'); // all | agent | imported
  const gradients = [
    'from-blue-600/80 to-cyan-500/80',
    'from-violet-600/80 to-fuchsia-500/80',
    'from-emerald-600/80 to-teal-500/80',
    'from-amber-600/80 to-orange-500/80',
    'from-rose-600/80 to-pink-500/80',
    'from-indigo-600/80 to-sky-500/80',
  ];

  const filtered = filter === 'all' ? courses : courses.filter(c => c.source === filter);
  const agentCount = courses.filter(c => c.source === 'agent').length;
  const importedCount = courses.filter(c => c.source !== 'agent').length;

  return (
    <div className="space-y-4" data-testid="course-list-panel">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold flex items-center gap-2"><BookOpen className="w-5 h-5 text-blue-400" /> Cursos Disponíveis</h2>
        <Button variant="outline" size="sm" onClick={onRefresh} data-testid="refresh-courses-btn">
          <ArrowRight className="w-3 h-3 mr-1" /> Atualizar
        </Button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1.5" data-testid="course-filter-tabs">
        {[
          { key: 'all', label: `Todos (${courses.length})` },
          { key: 'agent', label: `Agente (${agentCount})` },
          { key: 'imported', label: `Importados (${importedCount})` },
        ].map(t => (
          <button
            key={t.key}
            onClick={() => setFilter(t.key)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
              filter === t.key
                ? 'bg-blue-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
            }`}
            data-testid={`filter-${t.key}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <Card className="bg-slate-900/50 border-slate-800">
          <CardContent className="p-8 text-center space-y-3">
            <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto" />
            <p className="text-sm text-slate-300">Nenhum curso encontrado nesta categoria.</p>
            <p className="text-xs text-slate-400">Crie um curso pelo agente ou importe um arquivo PPT no Dashboard.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((course, idx) => (
            <Card
              key={course.id}
              className="bg-slate-900/50 border-slate-800 hover:border-blue-500/50 hover:scale-[1.02] transition-all cursor-pointer group overflow-hidden"
              onClick={() => onSelect(course)}
              data-testid={`course-item-${course.id}`}
            >
              <div className={`h-24 bg-gradient-to-br ${gradients[idx % gradients.length]} flex items-center justify-center relative`}>
                {course.source === 'agent' ? (
                  <Brain className="w-10 h-10 text-white/30 group-hover:text-white/50 transition-colors" />
                ) : (
                  <Upload className="w-10 h-10 text-white/30 group-hover:text-white/50 transition-colors" />
                )}
                <Badge className="absolute top-2 right-2 bg-black/40 text-white text-[10px] border-0">
                  <Layers className="w-3 h-3 mr-1" />{course.slidesCount} slides
                </Badge>
                <Badge className={`absolute top-2 left-2 text-[9px] border-0 ${
                  course.source === 'agent' ? 'bg-violet-600/70 text-violet-100' : 'bg-emerald-600/70 text-emerald-100'
                }`}>
                  {course.source === 'agent' ? 'Agente' : 'Importado'}
                </Badge>
              </div>
              <CardContent className="p-3 space-y-1.5">
                <h3 className="font-medium text-sm leading-tight line-clamp-2">{course.name}</h3>
                <p className="text-[11px] text-slate-400 line-clamp-2">{course.description || 'Sem descrição'}</p>
                {course.createdAt && (
                  <p className="text-[10px] text-slate-500">{new Date(course.createdAt).toLocaleDateString('pt-BR')}</p>
                )}
                {course.source === 'agent' && onReopenWizard && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="w-full mt-1 h-7 text-[11px] border-violet-500/40 text-violet-300 hover:bg-violet-600/20 hover:text-violet-200"
                    onClick={(e) => { e.stopPropagation(); onReopenWizard(course); }}
                    disabled={loading}
                    data-testid={`reopen-wizard-${course.id}`}
                  >
                    <RefreshCw className="w-3 h-3 mr-1" /> Reabrir no Assistente
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
