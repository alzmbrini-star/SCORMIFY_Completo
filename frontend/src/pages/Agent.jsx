import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
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
  PaintBucket, Target, Code, ExternalLink, BookOpenCheck, Volume2, Type,
} from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';

const API = getApiUrl();

// Extracted sub-panels
import ConfigPanel from './Agent/components/ConfigPanel';
import StoryboardPanel from './Agent/components/StoryboardPanel';
import MediaConfigPanel from './Agent/components/MediaConfigPanel';
import GeneratedPanel from './Agent/components/GeneratedPanel';
import { CourseReviewPanel, EditResultPanel } from './Agent/components/CoursePanels';


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
  { id: 'apply', label: 'Aplicar', icon: Check },
];

const TEMPLATE_ICONS = {
  users: Users, shield: Shield, wrench: Wrench, heart: Heart,
  'hard-hat': HardHat, 'trending-up': TrendingUp,
};

export default function Agent() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { isSuperAdmin, hasPermission, loading: authLoading } = useAuth();
  
  // Check access to AI Agent
  const hasAgentAccess = isSuperAdmin || hasPermission('agentAccess');
  
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
  });
  const [structure, setStructure] = useState(null);
  const [storyboard, setStoryboard] = useState(null);
  const [storyboardProgressMsg, setStoryboardProgressMsg] = useState(null);
  const [generatedProject, setGeneratedProject] = useState(null);
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
  const [editMediaProjectId, setEditMediaProjectId] = useState(null);
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
  const [selectedImprovements, setSelectedImprovements] = useState([]);
  const [editResult, setEditResult] = useState(null);

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
      toast.error('Você não tem permissão para acessar o Agente IA');
      navigate('/');
      return;
    }
    setAccessChecked(true);
  }, [authLoading, hasAgentAccess, navigate]);

  // Handle editMedia query param - load existing session for media editing
  useEffect(() => {
    const editProjectId = searchParams.get('editMedia');
    if (!editProjectId || mode) return;
    (async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API}/api/agent/sessions/by-project/${editProjectId}`);
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

  // Load templates on mount
  useEffect(() => {
    fetch(`${API}/api/agent/templates`)
      .then(r => r.json())
      .then(setTemplates)
      .catch(() => {});
    fetch(`${API}/api/agent/design-templates`)
      .then(r => r.json())
      .then(setDesignTemplates)
      .catch(() => {});
  }, []);

  const ensureSession = useCallback(async () => {
    if (sessionId) return sessionId;
    try {
      const res = await fetch(`${API}/api/agent/sessions`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      setSessionId(data.id);
      return data.id;
    } catch (e) {
      toast.error('Erro ao criar sessão');
      return null;
    }
  }, [sessionId]);

  // ===== CREATE MODE HANDLERS =====
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    addChatMsg('user', `Enviando arquivo: ${file.name}`);
    try {
      const sid = await ensureSession();
      if (!sid) return;
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API}/api/agent/sessions/${sid}/upload`, { method: 'POST', body: form });
      const data = await res.json();
      setFileName(file.name);
      addChatMsg('agent', `Arquivo "${file.name}" recebido! ${data.contentLength} caracteres extraídos. Clique em "Analisar".`);
      setCurrentStep(1);
    } catch {
      toast.error('Erro no upload');
      addChatMsg('agent', 'Erro ao processar o arquivo.');
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
      await fetch(`${API}/api/agent/sessions/${sid}/upload`, { method: 'POST', body: form });
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
      const res = await fetch(`${API}/api/agent/sessions/${sid}/upload`, { method: 'POST', body: form });
      const data = await res.json();
      setFileName(contentUrl);
      addChatMsg('agent', `Conteúdo extraído da URL! ${data.contentLength} caracteres. Clique em "Analisar".`);
      setCurrentStep(1);
    } catch { toast.error('Erro ao extrair conteúdo da URL'); addChatMsg('agent', 'Erro ao acessar a URL.'); }
    finally { setLoading(false); }
  };

  const handleAnalyze = async () => {
    setLoading(true);
    addChatMsg('agent', 'Analisando o conteúdo com IA...');
    try {
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/analyze`, { method: 'POST' });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setAnalysis(data);
      setConfig(prev => ({
        ...prev, title: data.title || prev.title, description: data.summary || prev.description,
        duration: data.estimatedDuration || prev.duration, modules: data.suggestedModules || prev.modules,
        depth: data.difficulty || prev.depth,
      }));
      addChatMsg('agent', `Análise concluída! "${data.title}" sugerido como título. Configure e gere a estrutura.`);
      setCurrentStep(2);
    } catch { toast.error('Erro na análise'); addChatMsg('agent', 'Erro ao analisar.'); }
    finally { setLoading(false); }
  };

  const handleGenerateStructure = async () => {
    setLoading(true);
    addChatMsg('agent', selectedTemplate ? `Gerando estrutura usando template "${selectedTemplate.name}"...` : 'Gerando a estrutura pedagógica...');
    try {
      const configToSend = { ...config };
      if (selectedDesignTemplate) configToSend.designTemplateId = selectedDesignTemplate.id;
      await fetch(`${API}/api/agent/sessions/${sessionId}/configure`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(configToSend),
      });
      const body = selectedTemplate ? { templateId: selectedTemplate.id } : {};
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/generate-structure`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setStructure(data);
      const totalSlides = data.modules?.reduce((sum, m) => sum + (m.slides?.length || 0), 0) || 0;
      addChatMsg('agent', `Estrutura criada! ${data.modules?.length || 0} módulos com ${totalSlides} slides.`);
      setCurrentStep(3);
    } catch { toast.error('Erro ao gerar estrutura'); addChatMsg('agent', 'Erro ao gerar estrutura.'); }
    finally { setLoading(false); }
  };

  const handleGenerateStoryboard = async () => {
    setLoading(true);
    setStoryboardProgressMsg('Verificando status...');
    try {
      // Check if storyboard already exists (e.g., user refreshed or polling timed out)
      const checkRes = await fetch(`${API}/api/agent/sessions/${sessionId}`);
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
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/generate-storyboard`, { method: 'POST' });
      if (!res.ok) throw new Error();
      const pollInterval = setInterval(async () => {
        try {
          const sRes = await fetch(`${API}/api/agent/sessions/${sessionId}`);
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
        fetch(`${API}/api/agent/sessions/${sessionId}`)
          .then(r => r.json())
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
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mediaConfig: enrichedConfig, bgConfig, globalTextColor, globalFontSize, globalAnimation, designTemplateId: selectedDesignTemplate?.id || '' }),
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
          method: 'POST', headers: { 'Content-Type': 'application/json' },
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
      const heygenMsg = heygenCount > 0 ? ` ${heygenCount} vídeos avatar HeyGen serão gerados em segundo plano (~1-3 min cada).` : '';
      addChatMsg('agent', `Mídia configurada! ${aiImageCount} imagens IA, ${videoCount} vídeos, ${heygenCount} avatares.${heygenMsg}${aiImageCount > 0 ? ' A geração de imagens pode levar alguns minutos.' : ''}`);
      setCurrentStep(6);
      handleGenerateCourse();
    } catch (err) { toast.error(err.message || 'Erro ao salvar mídia'); addChatMsg('agent', `Erro: ${err.message || 'Erro ao salvar configuração de mídia.'}`); }
    finally { setLoading(false); }
  };

  const handleGenerateCourse = async () => {
    setLoading(true);
    const aiCount = Object.values(mediaConfig).filter(m => m.type === 'ai_image').length;
    const heyCount = Object.values(mediaConfig).filter(m => m.type === 'heygen').length;
    addChatMsg('agent', `Gerando o curso no Scormfy...${aiCount > 0 ? ` Criando ${aiCount} imagens com IA (pode levar ~${aiCount * 15}s).` : ''}${heyCount > 0 ? ` ${heyCount} vídeos HeyGen serão gerados em segundo plano.` : ''}`);
    try {
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/generate-course`, { method: 'POST' });
      if (!res.ok) throw new Error('Falha ao iniciar geração');
      const initData = await res.json();
      
      if (initData.status === 'already_done') {
        setGeneratedProject(initData);
        setCurrentStep(6);
        return;
      }

      // Poll for completion
      const pollStatus = async () => {
        for (let i = 0; i < 120; i++) { // max 10 min (120 * 5s)
          await new Promise(r => setTimeout(r, 5000));
          try {
            const statusRes = await fetch(`${API}/api/agent/sessions/${sessionId}/course-status`);
            const statusData = await statusRes.json();
            if (statusData.message) {
              addChatMsg('agent', `Progresso: ${statusData.message}`);
            }
            if (statusData.status === 'done') {
              setGeneratedProject(statusData);
              const heygenMsg = statusData.heygenPending > 0 ? ` ${statusData.heygenPending} vídeos HeyGen em processamento.` : '';
              const narrationMsg = statusData.narrationPending > 0 ? ` ${statusData.narrationPending} narrações em geração.` : '';
              addChatMsg('agent', `Curso "${statusData.projectName}" criado! ${statusData.slidesCount} slides e ${statusData.quizCount} perguntas.${heygenMsg}${narrationMsg}`);
              setCurrentStep(6);
              toast.success('Curso gerado com sucesso!');
              return;
            }
            if (statusData.status === 'error') {
              throw new Error(statusData.error || 'Erro na geração');
            }
          } catch (pollErr) {
            if (pollErr.message.includes('Erro')) throw pollErr;
            // Network error, keep polling
          }
        }
        throw new Error('Timeout na geração do curso');
      };
      
      await pollStatus();
    } catch (e) {
      toast.error(e.message || 'Erro ao gerar curso');
      addChatMsg('agent', `Erro ao gerar o curso: ${e.message || 'Erro desconhecido'}`);
    } finally {
      setLoading(false);
    }
  };

  // ===== EDIT MODE HANDLERS =====
  const loadAgentCourses = async () => {
    try {
      const res = await fetch(`${API}/api/agent/courses`);
      const data = await res.json();
      setAgentCourses(data);
    } catch { toast.error('Erro ao carregar cursos'); }
  };

  const handleSelectMode = (m) => {
    setMode(m);
    setCurrentStep(0);
    if (m === 'create') {
      addChatMsg('agent', 'Envie o conteúdo que deseja transformar em curso. Você pode fazer upload de arquivo ou colar texto.');
    } else {
      addChatMsg('agent', 'Selecione um curso criado pelo agente para analisar e sugerir melhorias.');
      loadAgentCourses();
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
      const res = await fetch(`${API}/api/agent/courses/${course.id}/analyze`, { method: 'POST' });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setCourseAnalysis(data);
      setSelectedImprovements([]);
      addChatMsg('agent', `Análise concluída! Nota geral: ${data.overallScore}/10. ${data.improvements?.length || 0} melhorias sugeridas.`);
    } catch { toast.error('Erro na análise'); addChatMsg('agent', 'Erro ao analisar o curso.'); }
    finally { setLoading(false); }
  };

  const toggleImprovement = (improvement) => {
    setSelectedImprovements(prev => {
      const exists = prev.find(p => p.description === improvement.description);
      return exists ? prev.filter(p => p.description !== improvement.description) : [...prev, improvement];
    });
  };

  const handleApplyImprovements = async () => {
    if (selectedImprovements.length === 0) { toast.error('Selecione pelo menos uma melhoria'); return; }
    setLoading(true);
    addChatMsg('agent', `Aplicando ${selectedImprovements.length} melhorias ao curso...`);
    try {
      const res = await fetch(`${API}/api/agent/courses/${selectedCourse.id}/apply-improvements`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ improvements: selectedImprovements }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setEditResult(data);
      setCurrentStep(2);
      addChatMsg('agent', `Melhorias aplicadas! ${data.updatedSlides} slides atualizados, ${data.newSlides} novos slides. Total: ${data.totalSlides} slides.`);
      toast.success('Melhorias aplicadas com sucesso!');
    } catch { toast.error('Erro ao aplicar melhorias'); addChatMsg('agent', 'Erro ao aplicar as melhorias.'); }
    finally { setLoading(false); }
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
        method: 'POST', headers: { 'Content-Type': 'application/json' },
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
              method: 'POST', headers: { 'Content-Type': 'application/json' },
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
        <Button variant="ghost" size="sm" onClick={() => mode ? (setMode(null), setCurrentStep(0)) : navigate('/')} data-testid="back-to-dashboard">
          <ArrowLeft className="w-4 h-4 mr-1" /> {mode ? 'Voltar' : 'Dashboard'}
        </Button>
        <div className="w-px h-6 bg-slate-700" />
        <Brain className="w-5 h-5 text-emerald-400" />
        <span className="font-semibold text-sm">Agente de Design Instrucional</span>
        {mode && (
          <Badge className={`text-[10px] ${mode === 'create' ? 'bg-emerald-600/20 text-emerald-300' : 'bg-blue-600/20 text-blue-300'}`}>
            {mode === 'create' ? 'Novo Curso' : 'Editar Curso'}
          </Badge>
        )}
        <div className="flex-1" />
        {mode && (
          <div className="hidden md:flex items-center gap-1">
            {steps.map((step, i) => {
              const Icon = step.icon;
              const active = i === currentStep;
              const done = i < currentStep;
              return (
                <div key={step.id} className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${active ? 'bg-emerald-600/20 text-emerald-400' : done ? 'text-emerald-500/60' : 'text-slate-500'}`}>
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
      </header>

      {/* Main content */}
      <div className="flex-1 flex min-h-0">
        {/* Left Panel */}
        <div className={`flex-1 flex flex-col min-w-0 ${showChat ? 'hidden md:flex' : 'flex'}`}>
          <ScrollArea className="flex-1">
            <div className="p-6 max-w-4xl mx-auto space-y-6">
              {!mode && <ModeSelector onSelect={handleSelectMode} />}

              {/* CREATE MODE */}
              {mode === 'create' && currentStep === 0 && <UploadPanel contentText={contentText} setContentText={setContentText} contentUrl={contentUrl} setContentUrl={setContentUrl} fileName={fileName} fileInputRef={fileInputRef} handleFileUpload={handleFileUpload} handleTextSubmit={handleTextSubmit} handleUrlSubmit={handleUrlSubmit} loading={loading} />}
              {mode === 'create' && currentStep === 1 && <AnalyzePanel analysis={analysis} loading={loading} onAnalyze={handleAnalyze} />}
              {mode === 'create' && currentStep === 2 && <ConfigPanel config={config} setConfig={setConfig} analysis={analysis} loading={loading} onGenerate={handleGenerateStructure} templates={templates} selectedTemplate={selectedTemplate} setSelectedTemplate={setSelectedTemplate} designTemplates={designTemplates} selectedDesignTemplate={selectedDesignTemplate} setSelectedDesignTemplate={setSelectedDesignTemplate} />}
              {mode === 'create' && currentStep === 3 && <StructurePanel structure={structure} loading={loading} onApprove={handleGenerateStoryboard} progressMsg={storyboardProgressMsg} />}
              {mode === 'create' && currentStep === 4 && <StoryboardPanel storyboard={storyboard} loading={loading} onApprove={handleApproveStoryboard} config={config} setConfig={setConfig} sessionId={sessionId} />}
              {mode === 'create' && currentStep === 5 && <MediaConfigPanel storyboard={storyboard} mediaConfig={mediaConfig} setMediaConfig={setMediaConfig} loading={loading} onConfirm={handleSaveMediaConfig} heygenConfig={heygenConfig} setHeygenConfig={setHeygenConfig} bgConfig={bgConfig} setBgConfig={setBgConfig} sessionId={sessionId} globalTextColor={globalTextColor} setGlobalTextColor={setGlobalTextColor} globalFontSize={globalFontSize} setGlobalFontSize={setGlobalFontSize} globalAnimation={globalAnimation} setGlobalAnimation={setGlobalAnimation} isEditMode={!!editMediaProjectId} originalMediaConfig={originalMediaConfig} originalBgConfig={originalBgConfig} projectId={editMediaProjectId} selectedDesignTemplate={selectedDesignTemplate} setSelectedDesignTemplate={setSelectedDesignTemplate} />}
              {mode === 'create' && currentStep === 6 && <GeneratedPanel project={generatedProject} navigate={navigate} sessionId={sessionId} />}

              {/* EDIT MODE */}
              {mode === 'edit' && currentStep === 0 && <CourseListPanel courses={agentCourses} loading={loading} onSelect={handleSelectCourse} onRefresh={loadAgentCourses} />}
              {mode === 'edit' && currentStep === 1 && <CourseReviewPanel course={selectedCourse} analysis={courseAnalysis} loading={loading} selectedImprovements={selectedImprovements} toggleImprovement={toggleImprovement} onApply={handleApplyImprovements} />}
              {mode === 'edit' && currentStep === 2 && <EditResultPanel result={editResult} course={selectedCourse} navigate={navigate} />}
            </div>
          </ScrollArea>
        </div>

        {/* Right Panel - Chat */}
        <div className={`w-full md:w-96 lg:w-[420px] border-l border-slate-800 flex flex-col bg-slate-900/50 shrink-0 ${showChat ? 'flex' : 'hidden'}`}>
          <div className="p-3 border-b border-slate-800 flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-medium">Chat com o Agente</span>
            <Button variant="ghost" size="icon" className="ml-auto md:hidden" onClick={() => setShowChat(false)}>
              <X className="w-4 h-4" />
            </Button>
          </div>
          <ScrollArea className="flex-1 p-3">
            <div className="space-y-3">
              {chatMessages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${msg.role === 'user' ? 'bg-emerald-600/20 text-emerald-100' : 'bg-slate-800 text-slate-200'}`}>
                    {msg.text}
                  </div>
                </div>
              ))}
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
        </div>
      </div>
    </div>
  );
}

/* ====================== Sub-panels ====================== */

function ModeSelector({ onSelect }) {
  return (
    <div className="space-y-8" data-testid="mode-selector">
      <div className="text-center space-y-2">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-emerald-600/10 mb-2">
          <Sparkles className="w-8 h-8 text-emerald-400" />
        </div>
        <h1 className="text-2xl font-bold">Agente de Design Instrucional</h1>
        <p className="text-slate-400 text-sm max-w-lg mx-auto">
          Crie cursos profissionais do zero ou melhore cursos existentes com inteligência artificial.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-6 max-w-2xl mx-auto">
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
                Transforme qualquer conteúdo em um curso completo com estrutura pedagógica, quizzes e multimídia.
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
                Analise e melhore cursos criados pelo agente com sugestões inteligentes de conteúdo e estrutura.
              </p>
            </div>
            <div className="flex flex-wrap gap-1 justify-center">
              <Badge variant="outline" className="text-[10px] border-slate-700">Análise IA</Badge>
              <Badge variant="outline" className="text-[10px] border-slate-700">Melhorias</Badge>
              <Badge variant="outline" className="text-[10px] border-slate-700">Novos Slides</Badge>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function UploadPanel({ contentText, setContentText, contentUrl, setContentUrl, fileName, fileInputRef, handleFileUpload, handleTextSubmit, handleUrlSubmit, loading }) {
  return (
    <div className="space-y-6" data-testid="upload-panel">
      <div className="text-center space-y-2">
        <h1 className="text-xl font-bold">Envie o Conteúdo</h1>
        <p className="text-slate-400 text-sm max-w-lg mx-auto">
          Faça upload de um arquivo, cole o texto ou insira um link.
        </p>
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

function AnalyzePanel({ analysis, loading, onAnalyze }) {
  return (
    <div className="space-y-4" data-testid="analyze-panel">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold flex items-center gap-2"><Brain className="w-5 h-5 text-emerald-400" /> Análise do Conteúdo</h2>
        {!analysis && (
          <Button onClick={onAnalyze} disabled={loading} className="bg-emerald-600 hover:bg-emerald-700" data-testid="analyze-btn">
            {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Sparkles className="w-4 h-4 mr-1" />}
            Analisar Conteúdo
          </Button>
        )}
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

function CourseListPanel({ courses, loading, onSelect, onRefresh }) {
  const gradients = [
    'from-blue-600/80 to-cyan-500/80',
    'from-violet-600/80 to-fuchsia-500/80',
    'from-emerald-600/80 to-teal-500/80',
    'from-amber-600/80 to-orange-500/80',
    'from-rose-600/80 to-pink-500/80',
    'from-indigo-600/80 to-sky-500/80',
  ];
  return (
    <div className="space-y-4" data-testid="course-list-panel">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold flex items-center gap-2"><BookOpen className="w-5 h-5 text-blue-400" /> Cursos do Agente</h2>
        <Button variant="outline" size="sm" onClick={onRefresh} data-testid="refresh-courses-btn">
          <ArrowRight className="w-3 h-3 mr-1" /> Atualizar
        </Button>
      </div>

      {courses.length === 0 ? (
        <Card className="bg-slate-900/50 border-slate-800">
          <CardContent className="p-8 text-center space-y-3">
            <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto" />
            <p className="text-sm text-slate-300">Nenhum curso criado pelo agente encontrado.</p>
            <p className="text-xs text-slate-400">Crie um curso usando o modo "Criar Novo Curso" primeiro.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          {courses.map((course, idx) => (
            <Card
              key={course.id}
              className="bg-slate-900/50 border-slate-800 hover:border-blue-500/50 hover:scale-[1.02] transition-all cursor-pointer group overflow-hidden"
              onClick={() => onSelect(course)}
              data-testid={`course-item-${course.id}`}
            >
              <div className={`h-24 bg-gradient-to-br ${gradients[idx % gradients.length]} flex items-center justify-center relative`}>
                <BookOpen className="w-10 h-10 text-white/30 group-hover:text-white/50 transition-colors" />
                <Badge className="absolute top-2 right-2 bg-black/40 text-white text-[10px] border-0">
                  <Layers className="w-3 h-3 mr-1" />{course.slidesCount} slides
                </Badge>
              </div>
              <CardContent className="p-3 space-y-1.5">
                <h3 className="font-medium text-sm leading-tight line-clamp-2">{course.name}</h3>
                <p className="text-[11px] text-slate-400 line-clamp-2">{course.description || 'Sem descrição'}</p>
                {course.createdAt && (
                  <p className="text-[10px] text-slate-500">{new Date(course.createdAt).toLocaleDateString('pt-BR')}</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

