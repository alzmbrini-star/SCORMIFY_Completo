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
        body: JSON.stringify({ mediaConfig: enrichedConfig, bgConfig, globalTextColor, globalFontSize, globalAnimation }),
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
        // Also add if global settings changed (affects all slides)
        const hasGlobalChanges = !!globalTextColor || !!globalFontSize || !!globalAnimation;

        addChatMsg('agent', hasGlobalChanges
          ? 'Aplicando alterações globais ao projeto...'
          : `Aplicando alterações em ${changedSlides.length} slide(s) modificado(s)...`);

        const res = await fetch(`${API}/api/agent/sessions/${sessionId}/apply-media-changes`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            projectId: editMediaProjectId,
            changedSlides: hasGlobalChanges ? null : changedSlides,
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
      addChatMsg('agent', data.response);
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
              {mode === 'create' && currentStep === 4 && <StoryboardPanel storyboard={storyboard} loading={loading} onApprove={handleApproveStoryboard} />}
              {mode === 'create' && currentStep === 5 && <MediaConfigPanel storyboard={storyboard} mediaConfig={mediaConfig} setMediaConfig={setMediaConfig} loading={loading} onConfirm={handleSaveMediaConfig} heygenConfig={heygenConfig} setHeygenConfig={setHeygenConfig} bgConfig={bgConfig} setBgConfig={setBgConfig} sessionId={sessionId} globalTextColor={globalTextColor} setGlobalTextColor={setGlobalTextColor} globalFontSize={globalFontSize} setGlobalFontSize={setGlobalFontSize} globalAnimation={globalAnimation} setGlobalAnimation={setGlobalAnimation} isEditMode={!!editMediaProjectId} originalMediaConfig={originalMediaConfig} originalBgConfig={originalBgConfig} projectId={editMediaProjectId} />}
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

function ConfigPanel({ config, setConfig, analysis, loading, onGenerate, templates, selectedTemplate, setSelectedTemplate, designTemplates, selectedDesignTemplate, setSelectedDesignTemplate }) {
  const update = (k, v) => setConfig(prev => ({ ...prev, [k]: v }));
  const [elVoices, setElVoices] = useState([]);
  const [loadingVoices, setLoadingVoices] = useState(false);

  useEffect(() => {
    if (config.narrationEnabled && elVoices.length === 0 && !loadingVoices) {
      setLoadingVoices(true);
      fetch(`${API}/api/elevenlabs/voices`)
        .then(r => r.json())
        .then(data => setElVoices(data.voices || []))
        .catch(() => {})
        .finally(() => setLoadingVoices(false));
    }
  }, [config.narrationEnabled]);

  return (
    <div className="space-y-4" data-testid="config-panel">
      <h2 className="text-lg font-semibold flex items-center gap-2"><Settings className="w-5 h-5 text-emerald-400" /> Configuração do Curso</h2>

      {/* Template Selection */}
      {templates.length > 0 && (
        <div className="space-y-2">
          <label className="text-xs text-slate-400 block">Template (opcional)</label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2" data-testid="template-grid">
            {templates.map(t => {
              const Icon = TEMPLATE_ICONS[t.icon] || BookOpen;
              const isSelected = selectedTemplate?.id === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => {
                    if (isSelected) {
                      setSelectedTemplate(null);
                    } else {
                      setSelectedTemplate(t);
                      setConfig(prev => ({ ...prev, ...t.defaultConfig }));
                    }
                  }}
                  className={`flex items-center gap-2 p-3 rounded-lg border text-left transition-all text-sm ${
                    isSelected
                      ? 'border-emerald-500 bg-emerald-600/10'
                      : 'border-slate-700 bg-slate-800/50 hover:border-slate-600'
                  }`}
                  data-testid={`template-${t.id}`}
                >
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ backgroundColor: t.color + '20' }}>
                    <Icon className="w-4 h-4" style={{ color: t.color }} />
                  </div>
                  <div className="min-w-0">
                    <p className="font-medium text-xs truncate">{t.name}</p>
                    <p className="text-[10px] text-slate-400 truncate">{t.description}</p>
                  </div>
                  {isSelected && <Check className="w-4 h-4 text-emerald-400 shrink-0 ml-auto" />}
                </button>
              );
            })}
          </div>
          {selectedTemplate && (
            <p className="text-xs text-emerald-400/70">
              <Zap className="w-3 h-3 inline mr-1" />
              Template "{selectedTemplate.name}" selecionado - configuração ajustada automaticamente
            </p>
          )}
        </div>
      )}

      {/* Design Template (Visual Theme) Selection */}
      {designTemplates.length > 0 && (
        <div className="space-y-2">
          <label className="text-xs text-slate-400 block flex items-center gap-1"><Palette className="w-3 h-3" /> Tema Visual</label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2" data-testid="design-template-grid">
            {designTemplates.map(dt => {
              const isSelected = selectedDesignTemplate?.id === dt.id;
              return (
                <button
                  key={dt.id}
                  onClick={() => setSelectedDesignTemplate(isSelected ? null : dt)}
                  className={`flex items-center gap-2 p-3 rounded-lg border text-left transition-all text-sm ${
                    isSelected
                      ? 'border-emerald-500 bg-emerald-600/10 ring-1 ring-emerald-500/30'
                      : 'border-slate-700 bg-slate-800/50 hover:border-slate-600'
                  }`}
                  data-testid={`design-template-${dt.id}`}
                >
                  <div className="w-8 h-8 rounded-lg shrink-0" style={{ background: dt.preview }} />
                  <div className="min-w-0">
                    <p className="font-medium text-xs truncate">{dt.name}</p>
                    <p className="text-[10px] text-slate-400 truncate">{dt.description}</p>
                  </div>
                  {isSelected && <Check className="w-4 h-4 text-emerald-400 shrink-0 ml-auto" />}
                </button>
              );
            })}
          </div>
          {selectedDesignTemplate && (
            <p className="text-xs text-emerald-400/70">
              <Palette className="w-3 h-3 inline mr-1" />
              Tema "{selectedDesignTemplate.name}" será aplicado aos slides
            </p>
          )}
        </div>
      )}

      <div className="grid gap-4">
        <Card className="bg-slate-900/50 border-slate-800">
          <CardContent className="p-4 space-y-4">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Título do Curso</label>
              <Input data-testid="config-title" value={config.title} onChange={e => update('title', e.target.value)} className="bg-slate-800 border-slate-700" />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Descrição</label>
              <Textarea value={config.description} onChange={e => update('description', e.target.value)} className="bg-slate-800 border-slate-700 text-sm" rows={2} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Nível</label>
                <Select value={config.depth} onValueChange={v => update('depth', v)}>
                  <SelectTrigger className="bg-slate-800 border-slate-700"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="basico">Básico</SelectItem>
                    <SelectItem value="intermediario">Intermediário</SelectItem>
                    <SelectItem value="avancado">Avançado</SelectItem>
                    <SelectItem value="especialista">Especialista</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Formato</label>
                <Select value={config.format} onValueChange={v => update('format', v)}>
                  <SelectTrigger className="bg-slate-800 border-slate-700"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="curso_completo">Curso Completo</SelectItem>
                    <SelectItem value="microlearning">Microlearning</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Duração alvo: {config.duration} minutos</label>
              <Slider value={[config.duration]} onValueChange={([v]) => update('duration', v)} min={5} max={120} step={5} className="mt-2" />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Módulos: {config.modules}</label>
              <Slider value={[config.modules]} onValueChange={([v]) => update('modules', v)} min={1} max={12} step={1} className="mt-2" />
            </div>
          </CardContent>
        </Card>

        {/* Narration Config */}
        <Card className="bg-slate-900/50 border-slate-800" data-testid="narration-config-card">
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Play className="w-4 h-4 text-amber-400" />
                <label className="text-sm font-medium">Narração Automática</label>
              </div>
              <button
                onClick={() => update('narrationEnabled', !config.narrationEnabled)}
                className={`w-10 h-5 rounded-full transition-colors relative ${config.narrationEnabled ? 'bg-amber-600' : 'bg-slate-700'}`}
                data-testid="narration-toggle"
              >
                <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${config.narrationEnabled ? 'translate-x-5' : 'translate-x-0.5'}`} />
              </button>
            </div>
            <p className="text-xs text-slate-400">Gerar áudio de narração para cada slide usando ElevenLabs (processado após criação do curso).</p>

            {config.narrationEnabled && (
              <div className="space-y-2 pt-1">
                <label className="text-xs text-slate-400 font-medium">Voz ElevenLabs</label>
                {loadingVoices ? (
                  <div className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="w-3 h-3 animate-spin" /> Carregando vozes...</div>
                ) : (
                  <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                    {elVoices.slice(0, 30).map(v => (
                      <button
                        key={v.voice_id}
                        onClick={() => update('narrationVoiceId', v.voice_id)}
                        className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-all text-left ${
                          config.narrationVoiceId === v.voice_id
                            ? 'border-amber-500 bg-amber-600/10 text-amber-300'
                            : 'border-slate-700/50 text-slate-400 hover:border-amber-500/30'
                        }`}
                        data-testid={`el-voice-${v.voice_id}`}
                      >
                        <span className="font-medium">{v.name}</span>
                        {v.gender && <span className="text-slate-500">{v.gender}</span>}
                        {v.accent && <span className="text-slate-600">{v.accent}</span>}
                        {v.preview_url && (
                          <span
                            role="button"
                            onClick={(e) => { e.stopPropagation(); new Audio(v.preview_url).play(); }}
                            className="ml-auto text-amber-400 hover:text-amber-300 cursor-pointer"
                          >
                            <Play className="w-3 h-3" />
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
                {config.narrationEnabled && !config.narrationVoiceId && (
                  <p className="text-[11px] text-amber-400/70 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" /> Selecione uma voz para a narração.
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
      <Button onClick={onGenerate} disabled={loading} className="w-full bg-emerald-600 hover:bg-emerald-700" data-testid="generate-structure-btn">
        {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Layers className="w-4 h-4 mr-1" />}
        {selectedTemplate ? `Gerar com Template "${selectedTemplate.name}"` : 'Gerar Estrutura do Curso'}
      </Button>
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

function StoryboardPanel({ storyboard, loading, onApprove }) {
  const [activeSlide, setActiveSlide] = useState(0);
  if (!storyboard?.slides) return null;
  const slide = storyboard.slides[activeSlide];
  return (
    <div className="space-y-4" data-testid="storyboard-panel">
      <h2 className="text-lg font-semibold flex items-center gap-2"><BookOpen className="w-5 h-5 text-emerald-400" /> Storyboard</h2>
      <div className="flex gap-1 flex-wrap">
        {storyboard.slides.map((s, i) => (
          <button key={i} onClick={() => setActiveSlide(i)}
            className={`px-2 py-1 rounded text-xs transition-colors ${i === activeSlide ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}`}>
            {i + 1}
          </button>
        ))}
      </div>
      {slide && (
        <Card className="bg-slate-900/50 border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Badge className={`text-xs ${slide.type === 'quiz' ? 'bg-amber-600/20 text-amber-300' : slide.type === 'title' ? 'bg-blue-600/20 text-blue-300' : 'bg-slate-700 text-slate-300'}`}>{slide.type}</Badge>
              Slide {activeSlide + 1}: {slide.title}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded-lg overflow-hidden border border-slate-700" style={{ background: slide.background || '#fff', aspectRatio: '1920/820' }}>
              <div className="p-4 h-full overflow-auto">
                {slide.elements?.map((el, i) => (
                  <div key={i} className="text-sm" dangerouslySetInnerHTML={{ __html: el.content || '' }} style={{ color: slide.type === 'title' ? '#fff' : '#333' }} />
                ))}
              </div>
            </div>
            {slide.narrationScript && (
              <div className="bg-slate-800/50 rounded p-3">
                <span className="text-xs text-slate-400 block mb-1">Narração:</span>
                <p className="text-sm text-slate-300">{slide.narrationScript}</p>
              </div>
            )}
            {slide.quizQuestions?.length > 0 && (
              <div className="bg-amber-900/10 rounded p-3 border border-amber-800/20">
                <span className="text-xs text-amber-400 block mb-2">Perguntas do Quiz:</span>
                {slide.quizQuestions.map((q, qi) => (
                  <div key={qi} className="mb-2">
                    <p className="text-sm font-medium text-slate-200">{qi + 1}. {q.text}</p>
                    <div className="ml-4 mt-1 space-y-1">
                      {q.alternatives?.map((a, ai) => (
                        <p key={ai} className={`text-xs ${a.isCorrect ? 'text-emerald-400' : 'text-slate-400'}`}>
                          {a.isCorrect ? '✓' : '○'} {a.text}
                        </p>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
      <div className="flex justify-between items-center">
        <Button variant="outline" size="sm" onClick={() => setActiveSlide(Math.max(0, activeSlide - 1))} disabled={activeSlide === 0}>
          <ArrowLeft className="w-4 h-4 mr-1" /> Anterior
        </Button>
        <span className="text-xs text-slate-400">{activeSlide + 1} / {storyboard.slides.length}</span>
        <Button variant="outline" size="sm" onClick={() => setActiveSlide(Math.min(storyboard.slides.length - 1, activeSlide + 1))} disabled={activeSlide >= storyboard.slides.length - 1}>
          Próximo <ArrowRight className="w-4 h-4 ml-1" />
        </Button>
      </div>
      <Button onClick={onApprove} disabled={loading} className="w-full bg-emerald-600 hover:bg-emerald-700" data-testid="approve-storyboard-btn">
        {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Play className="w-4 h-4 mr-1" />}
        Aprovar e Gerar Curso no Scormfy
      </Button>
    </div>
  );
}


const GRADIENT_DIRECTIONS = [
  { id: 'to right', label: '→' },
  { id: 'to left', label: '←' },
  { id: 'to bottom', label: '↓' },
  { id: 'to top', label: '↑' },
  { id: 'to bottom right', label: '↘' },
  { id: 'to bottom left', label: '↙' },
  { id: 'to top right', label: '↗' },
  { id: 'to top left', label: '↖' },
];

function SlideBackgroundPicker({ slideIndex, bgConfig, setBgConfig, allSlides, isGlobal }) {
  const bg = bgConfig[String(slideIndex)] || { type: 'default' };

  const updateBg = (patch) => {
    setBgConfig(prev => ({ ...prev, [String(slideIndex)]: { ...bg, ...patch } }));
  };

  const applyToAll = () => {
    const newCfg = {};
    allSlides.forEach((_, i) => { newCfg[String(i)] = { ...bg }; });
    setBgConfig(newCfg);
    toast.success('Fundo aplicado a todos os slides');
  };

  const applyToType = (slideType) => {
    const newCfg = { ...bgConfig };
    allSlides.forEach((s, i) => { if (s.type === slideType) newCfg[String(i)] = { ...bg }; });
    setBgConfig(newCfg);
    toast.success(`Fundo aplicado aos slides "${slideType}"`);
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { toast.error('Imagem deve ter no máximo 5MB'); return; }
    const reader = new FileReader();
    reader.onload = (ev) => {
      updateBg({ type: 'image', imageData: ev.target.result, opacity: bg.opacity ?? 30 });
    };
    reader.readAsDataURL(file);
  };

  const [aiPrompt, setAiPrompt] = useState('');
  const [aiLoading, setAiLoading] = useState(false);

  const generateAiBg = async () => {
    if (!aiPrompt.trim()) return;
    setAiLoading(true);
    try {
      const res = await fetch(`${API}/api/agent/generate-bg-image`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: aiPrompt }),
      });
      const data = await res.json();
      if (data.imageUrl) {
        updateBg({ type: 'image', imageUrl: data.imageUrl, opacity: bg.opacity ?? 30, aiPrompt });
        toast.success('Imagem de fundo gerada!');
      } else { toast.error('Erro ao gerar imagem'); }
    } catch { toast.error('Erro ao gerar imagem'); }
    finally { setAiLoading(false); }
  };

  const previewStyle = bg.type === 'solid'
    ? { background: bg.color || '#1e293b' }
    : bg.type === 'gradient'
    ? { background: `linear-gradient(${bg.direction || 'to right'}, ${bg.color1 || '#1e293b'}, ${bg.color2 || '#10b981'})` }
    : bg.type === 'image'
    ? { backgroundImage: `url(${bg.imageData || bg.imageUrl || ''})`, backgroundSize: 'cover', backgroundPosition: 'center' }
    : { background: '#1e293b' };

  return (
    <div className="space-y-2" data-testid={`bg-picker-slide-${slideIndex}`}>
      <div className="flex items-center gap-2">
        <Palette className="w-3.5 h-3.5 text-cyan-400" />
        <span className="text-xs font-medium text-cyan-300">Fundo</span>
        {/* Mini preview */}
        <div className="w-8 h-5 rounded border border-slate-600 shrink-0" style={previewStyle} />
        {!isGlobal && (
          <div className="ml-auto flex gap-1">
            <button onClick={applyToAll} className="text-[10px] text-cyan-400/70 hover:text-cyan-300 px-1" title="Aplicar a todos">
              Todos
            </button>
            <button onClick={() => applyToType(allSlides[slideIndex]?.type || 'content')} className="text-[10px] text-cyan-400/70 hover:text-cyan-300 px-1" title="Aplicar ao mesmo tipo">
              Tipo
            </button>
          </div>
        )}
      </div>

      <Tabs value={bg.type || 'default'} onValueChange={(v) => updateBg({ type: v })} className="w-full">
        <TabsList className="w-full h-7 bg-slate-800/80 p-0.5">
          <TabsTrigger value="default" className="text-[10px] h-6 px-2 data-[state=active]:bg-slate-700">Padrão</TabsTrigger>
          <TabsTrigger value="solid" className="text-[10px] h-6 px-2 data-[state=active]:bg-slate-700">Cor</TabsTrigger>
          <TabsTrigger value="gradient" className="text-[10px] h-6 px-2 data-[state=active]:bg-slate-700">Degradê</TabsTrigger>
          <TabsTrigger value="image" className="text-[10px] h-6 px-2 data-[state=active]:bg-slate-700">Imagem</TabsTrigger>
        </TabsList>

        <TabsContent value="default" className="mt-1">
          <p className="text-[10px] text-slate-500">Usa a cor do template selecionado.</p>
        </TabsContent>

        <TabsContent value="solid" className="mt-1">
          <div className="flex items-center gap-2">
            <input
              type="color"
              value={bg.color || '#1e293b'}
              onChange={(e) => updateBg({ color: e.target.value })}
              className="w-8 h-8 rounded cursor-pointer border-0 bg-transparent"
              data-testid={`bg-color-picker-${slideIndex}`}
            />
            <Input
              value={bg.color || '#1e293b'}
              onChange={(e) => updateBg({ color: e.target.value })}
              className="h-7 text-xs bg-slate-800 border-slate-700 w-24"
              placeholder="#1e293b"
            />
          </div>
        </TabsContent>

        <TabsContent value="gradient" className="mt-1">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={bg.color1 || '#1e293b'}
                onChange={(e) => updateBg({ color1: e.target.value })}
                className="w-7 h-7 rounded cursor-pointer border-0 bg-transparent"
                data-testid={`bg-gradient-color1-${slideIndex}`}
              />
              <input
                type="color"
                value={bg.color2 || '#10b981'}
                onChange={(e) => updateBg({ color2: e.target.value })}
                className="w-7 h-7 rounded cursor-pointer border-0 bg-transparent"
                data-testid={`bg-gradient-color2-${slideIndex}`}
              />
              <div className="flex gap-0.5 ml-1">
                {GRADIENT_DIRECTIONS.map(d => (
                  <button
                    key={d.id}
                    onClick={() => updateBg({ direction: d.id })}
                    className={`w-6 h-6 rounded text-[10px] transition-colors ${
                      (bg.direction || 'to right') === d.id
                        ? 'bg-cyan-600/30 text-cyan-300 border border-cyan-500/50'
                        : 'bg-slate-800 text-slate-500 hover:text-slate-300 border border-slate-700'
                    }`}
                    title={d.id}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </div>
            {/* Gradient preview */}
            <div
              className="h-6 rounded border border-slate-700"
              style={{ background: `linear-gradient(${bg.direction || 'to right'}, ${bg.color1 || '#1e293b'}, ${bg.color2 || '#10b981'})` }}
            />
          </div>
        </TabsContent>

        <TabsContent value="image" className="mt-1">
          <div className="space-y-2">
            <div className="flex gap-2">
              <label className="flex-1">
                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-dashed border-slate-600 text-xs text-slate-400 hover:border-cyan-500/50 hover:text-cyan-300 cursor-pointer transition-colors" data-testid={`bg-upload-btn-${slideIndex}`}>
                  <UploadCloud className="w-3.5 h-3.5" /> Upload
                </div>
                <input type="file" accept="image/*" onChange={handleImageUpload} className="hidden" />
              </label>
              <div className="flex-1 flex gap-1">
                <Input
                  value={aiPrompt}
                  onChange={(e) => setAiPrompt(e.target.value)}
                  placeholder="Descreva o fundo..."
                  className="h-8 text-xs bg-slate-800 border-slate-700 flex-1"
                  data-testid={`bg-ai-prompt-${slideIndex}`}
                  onKeyDown={(e) => e.key === 'Enter' && generateAiBg()}
                />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={generateAiBg}
                  disabled={aiLoading || !aiPrompt.trim()}
                  className="h-8 px-2 text-xs border-cyan-700/50 text-cyan-300"
                  data-testid={`bg-ai-generate-${slideIndex}`}
                >
                  {aiLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                </Button>
              </div>
            </div>
            {(bg.imageData || bg.imageUrl) && (
              <div className="space-y-1.5">
                <div className="relative h-16 rounded border border-slate-700 overflow-hidden">
                  <img src={bg.imageData || bg.imageUrl} alt="bg" className="w-full h-full object-cover" style={{ opacity: (bg.opacity ?? 30) / 100 }} />
                  <div className="absolute inset-0 bg-slate-900" style={{ opacity: 1 - (bg.opacity ?? 30) / 100 }} />
                </div>
                <div className="flex items-center gap-2">
                  <Droplets className="w-3 h-3 text-slate-400" />
                  <span className="text-[10px] text-slate-400 w-14">Opacidade</span>
                  <Slider
                    value={[bg.opacity ?? 30]}
                    onValueChange={([v]) => updateBg({ opacity: v })}
                    min={5} max={100} step={5}
                    className="flex-1"
                    data-testid={`bg-opacity-slider-${slideIndex}`}
                  />
                  <span className="text-[10px] text-slate-400 w-8 text-right">{bg.opacity ?? 30}%</span>
                </div>
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

const MEDIA_TYPES = [
  { id: 'ai_image', label: 'Imagem IA', description: 'Fotorealista gerada por IA', icon: Image, color: 'emerald' },
  { id: 'gallery_image', label: 'Da Galeria', description: 'Reutilizar imagem existente', icon: ImagePlus, color: 'amber' },
  { id: 'youtube', label: 'YouTube', description: 'Vídeo do YouTube', icon: Video, color: 'red' },
  { id: 'vimeo', label: 'Vimeo', description: 'Vídeo do Vimeo', icon: Video, color: 'blue' },
  { id: 'heygen', label: 'Avatar HeyGen', description: 'Vídeo com avatar IA', icon: UserCircle, color: 'purple' },
  { id: 'flipbook', label: 'Flipbook', description: 'PDF/URL interativo', icon: BookOpenCheck, color: 'orange' },
  { id: 'html', label: 'HTML', description: 'Código HTML ou URL', icon: Code, color: 'cyan' },
  { id: 'button', label: 'Botão Link', description: 'Botão com link externo', icon: ExternalLink, color: 'teal' },
  { id: 'none', label: 'Sem mídia', description: 'Apenas texto', icon: FileText, color: 'slate' },
];

const NARRATION_STYLES = [
  { id: 'educational', label: 'Educativo' },
  { id: 'conversational', label: 'Conversacional' },
  { id: 'formal', label: 'Formal' },
  { id: 'friendly', label: 'Amigável' },
];

function CostEstimateCard({ sessionId, aiCount, videoCount, heygenCount, bgConfig, isEditMode, changedSlideCount }) {
  const [estimate, setEstimate] = useState(null);
  const [loadingEstimate, setLoadingEstimate] = useState(false);

  const fetchEstimate = useCallback(async () => {
    if (!sessionId) return;
    setLoadingEstimate(true);
    try {
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/cost-estimate`, { method: 'POST' });
      const data = await res.json();
      setEstimate(data.estimate);
    } catch { /* ignore */ }
    finally { setLoadingEstimate(false); }
  }, [sessionId]);

  useEffect(() => { fetchEstimate(); }, [fetchEstimate]);

  const customBgCount = Object.values(bgConfig || {}).filter(b => b.type && b.type !== 'default').length;

  // In edit mode, scale costs by ratio of changed slides to total
  const getEditScaledEstimate = () => {
    if (!estimate || !isEditMode || changedSlideCount == null) return estimate;
    const total = estimate.totalSlides || 1;
    const ratio = Math.min(changedSlideCount / total, 1);
    return {
      ...estimate,
      totalSlides: changedSlideCount,
      aiImages: Math.round(estimate.aiImages * ratio),
      costs: {
        text: Math.round(estimate.costs.text * ratio * 1000) / 1000,
        images: Math.round(estimate.costs.images * ratio * 1000) / 1000,
        narration: Math.round(estimate.costs.narration * ratio * 1000) / 1000,
        total: Math.round(estimate.costs.total * ratio * 1000) / 1000,
      },
      comparison: {
        ...estimate.comparison,
        oldTotal: Math.round(estimate.comparison.oldTotal * ratio * 1000) / 1000,
        newTotal: Math.round(estimate.costs.total * ratio * 1000) / 1000,
        savingsPercent: estimate.comparison.savingsPercent,
      },
    };
  };
  const displayEstimate = isEditMode ? getEditScaledEstimate() : estimate;

  return (
    <Card className="bg-slate-900/50 border-emerald-800/30" data-testid="cost-estimate-card">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-semibold text-emerald-300 flex items-center gap-1.5">
            <BarChart3 className="w-3.5 h-3.5" /> Resumo & Estimativa de Custo
          </h4>
          <button onClick={fetchEstimate} className="text-[10px] text-slate-500 hover:text-slate-300" disabled={loadingEstimate}>
            {loadingEstimate ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
          </button>
        </div>

        {isEditMode && changedSlideCount != null && (
          <div className="flex items-center gap-1.5 text-xs">
            <Badge className="bg-blue-600/20 text-blue-300">
              {changedSlideCount} slide(s) modificado(s) de {estimate?.totalSlides || '?'}
            </Badge>
          </div>
        )}

        {/* Media summary badges */}
        <div className="flex flex-wrap gap-2 text-xs">
          {aiCount > 0 && <Badge className="bg-emerald-600/20 text-emerald-300"><Image className="w-3 h-3 mr-1" />{aiCount} Imagens IA</Badge>}
          {videoCount > 0 && <Badge className="bg-red-600/20 text-red-300"><Video className="w-3 h-3 mr-1" />{videoCount} Vídeos</Badge>}
          {heygenCount > 0 && <Badge className="bg-purple-600/20 text-purple-300"><UserCircle className="w-3 h-3 mr-1" />{heygenCount} Avatares</Badge>}
          {customBgCount > 0 && <Badge className="bg-cyan-600/20 text-cyan-300"><Palette className="w-3 h-3 mr-1" />{customBgCount} Fundos</Badge>}
        </div>

        {displayEstimate && (
          <div className="space-y-2">
            {/* Cost breakdown */}
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="bg-slate-800/60 rounded-lg p-2">
                <p className="text-[10px] text-slate-400">Texto (IA)</p>
                <p className="text-sm font-bold text-slate-200">${displayEstimate.costs.text.toFixed(3)}</p>
                <p className="text-[9px] text-cyan-400/60">{displayEstimate.models.text}</p>
              </div>
              <div className="bg-slate-800/60 rounded-lg p-2">
                <p className="text-[10px] text-slate-400">Imagens ({displayEstimate.aiImages})</p>
                <p className="text-sm font-bold text-slate-200">${displayEstimate.costs.images.toFixed(3)}</p>
                <p className="text-[9px] text-cyan-400/60">{displayEstimate.models.images}</p>
              </div>
              <div className="bg-slate-800/60 rounded-lg p-2">
                <p className="text-[10px] text-slate-400">Narração</p>
                <p className="text-sm font-bold text-slate-200">${displayEstimate.costs.narration.toFixed(3)}</p>
                <p className="text-[9px] text-cyan-400/60">{displayEstimate.models.narration}</p>
              </div>
            </div>

            {/* Total and savings */}
            <div className="flex items-center justify-between bg-emerald-900/20 border border-emerald-800/30 rounded-lg px-3 py-2">
              <div>
                <p className="text-xs text-slate-400">{isEditMode ? 'Custo dos slides modificados' : 'Custo estimado total'}</p>
                <p className="text-lg font-bold text-emerald-300">${displayEstimate.costs.total.toFixed(3)}</p>
              </div>
              {displayEstimate.comparison.savingsPercent > 0 && (
                <div className="text-right">
                  <Badge className="bg-emerald-600/30 text-emerald-300 text-xs">
                    <TrendingUp className="w-3 h-3 mr-1" />
                    {displayEstimate.comparison.savingsPercent}% economia
                  </Badge>
                  <p className="text-[10px] text-slate-500 mt-0.5 line-through">${displayEstimate.comparison.oldTotal.toFixed(3)} (GPT-5.2)</p>
                </div>
              )}
            </div>

            <p className="text-[10px] text-slate-500 text-center">
              {displayEstimate.totalSlides} slides | {displayEstimate.storyboardBatches || Math.ceil(displayEstimate.totalSlides / 4)} batches | Gemini 3 Flash + Nano Banana
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MediaConfigPanel({ storyboard, mediaConfig, setMediaConfig, loading, onConfirm, heygenConfig, setHeygenConfig, bgConfig, setBgConfig, sessionId, globalTextColor, setGlobalTextColor, globalFontSize, setGlobalFontSize, globalAnimation, setGlobalAnimation, isEditMode, originalMediaConfig, originalBgConfig, projectId }) {
  const [avatars, setAvatars] = useState([]);
  const [voices, setVoices] = useState([]);
  const [loadingAvatars, setLoadingAvatars] = useState(false);
  const [loadingVoices, setLoadingVoices] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [previewVideoId, setPreviewVideoId] = useState(null);
  const [showGallery, setShowGallery] = useState(false);
  const [gallerySlideIndex, setGallerySlideIndex] = useState(null);

  // ElevenLabs narration state - restore voiceId from existing mediaConfig when editing
  const [elVoices, setElVoices] = useState([]);
  const [loadingElVoices, setLoadingElVoices] = useState(false);
  const [narrationVoiceId, setNarrationVoiceId] = useState(() => {
    // Extract voiceId from first narration-enabled slide in mediaConfig
    for (const val of Object.values(mediaConfig || {})) {
      if (val?.narration?.enabled && val?.narration?.voiceId) {
        return val.narration.voiceId;
      }
    }
    return '';
  });
  const [narrationStyle, setNarrationStyle] = useState('educational');
  const [generatingScripts, setGeneratingScripts] = useState({}); // { slideIndex: true }
  const [scriptOptions, setScriptOptions] = useState({}); // { slideIndex: ["opt1", "opt2", "opt3"] }
  const [previewingAudio, setPreviewingAudio] = useState(null);

  const contentSlides = (storyboard?.slides || [])
    .map((s, i) => ({ ...s, index: i }))
    .filter(s => s.type === 'content');

  const updateSlideMedia = (idx, type, url, extra = {}) => {
    setMediaConfig(prev => ({
      ...prev,
      [String(idx)]: { ...prev[String(idx)], type, ...(url ? { url } : {}), ...extra },
    }));
  };

  const setAllSlidesMedia = (type) => {
    const mc = {};
    contentSlides.forEach(s => { mc[String(s.index)] = { type }; });
    setMediaConfig(mc);
  };

  const aiCount = Object.values(mediaConfig).filter(m => m.type === 'ai_image').length;
  const videoCount = Object.values(mediaConfig).filter(m => m.type === 'youtube' || m.type === 'vimeo').length;
  const heygenCount = Object.values(mediaConfig).filter(m => m.type === 'heygen').length;
  const narrationCount = Object.values(mediaConfig).filter(m => m.narration?.enabled).length;

  // Fetch HeyGen avatars/voices when needed
  useEffect(() => {
    if (heygenCount > 0 && avatars.length === 0 && !loadingAvatars) {
      setLoadingAvatars(true);
      fetch(`${API}/api/heygen/avatars?limit=50`)
        .then(r => r.json())
        .then(data => setAvatars(data.avatars || []))
        .catch(() => toast.error('Erro ao carregar avatares'))
        .finally(() => setLoadingAvatars(false));
    }
    if (heygenCount > 0 && voices.length === 0 && !loadingVoices) {
      setLoadingVoices(true);
      fetch(`${API}/api/heygen/voices?language=portuguese`)
        .then(r => r.json())
        .then(data => setVoices(data.voices || []))
        .catch(() => toast.error('Erro ao carregar vozes'))
        .finally(() => setLoadingVoices(false));
    }
  }, [heygenCount]);

  // Fetch ElevenLabs voices when narration is active
  useEffect(() => {
    if (narrationCount > 0 && elVoices.length === 0 && !loadingElVoices) {
      setLoadingElVoices(true);
      fetch(`${API}/api/elevenlabs/voices`)
        .then(r => r.json())
        .then(data => setElVoices(data.voices || []))
        .catch(() => toast.error('Erro ao carregar vozes ElevenLabs'))
        .finally(() => setLoadingElVoices(false));
    }
  }, [narrationCount]);

  const heygenReady = heygenCount === 0 || (heygenConfig.avatarId && heygenConfig.voiceId);
  const narrationReady = narrationCount === 0 || narrationVoiceId;

  // Compute changed slides count in edit mode
  const changedSlideCount = useMemo(() => {
    if (!isEditMode || !originalMediaConfig) return null;
    const allKeys = new Set([
      ...Object.keys(mediaConfig), ...Object.keys(originalMediaConfig || {}),
      ...Object.keys(bgConfig), ...Object.keys(originalBgConfig || {}),
    ]);
    let count = 0;
    for (const key of allKeys) {
      const mcChanged = JSON.stringify(mediaConfig[key] || {}) !== JSON.stringify((originalMediaConfig || {})[key] || {});
      const bgChanged = JSON.stringify((bgConfig || {})[key] || {}) !== JSON.stringify((originalBgConfig || {})[key] || {});
      if (mcChanged || bgChanged) count++;
    }
    return count;
  }, [isEditMode, mediaConfig, bgConfig, originalMediaConfig, originalBgConfig]);

  // Toggle narration for a slide
  const toggleSlideNarration = (idx, enabled) => {
    setMediaConfig(prev => ({
      ...prev,
      [String(idx)]: {
        ...prev[String(idx)],
        narration: { ...(prev[String(idx)]?.narration || {}), enabled, voiceId: narrationVoiceId },
      },
    }));
  };

  // Generate 3 narration script options for a slide
  const generateNarrationScripts = async (idx) => {
    setGeneratingScripts(prev => ({ ...prev, [idx]: true }));
    try {
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/generate-slide-narration`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slideIndex: idx, style: narrationStyle }),
      });
      if (!res.ok) {
        const err = await res.text();
        console.error('Narration API error:', res.status, err);
        toast.error(`Erro ${res.status}: ${err.slice(0, 100)}`);
        return;
      }
      const data = await res.json();
      if (data.options) {
        setScriptOptions(prev => ({ ...prev, [idx]: data.options }));
      } else {
        toast.error('Erro ao gerar roteiros: resposta sem opções');
      }
    } catch (e) {
      console.error('Narration fetch error:', e);
      toast.error(`Erro de rede ao gerar roteiros: ${e.message}`);
    } finally {
      setGeneratingScripts(prev => ({ ...prev, [idx]: false }));
    }
  };

  // Select a narration script for a slide
  const selectNarrationScript = (idx, script) => {
    setMediaConfig(prev => ({
      ...prev,
      [String(idx)]: {
        ...prev[String(idx)],
        narration: { ...(prev[String(idx)]?.narration || {}), enabled: true, voiceId: narrationVoiceId, selectedScript: script },
      },
    }));
  };

  // Preview narration audio
  const previewNarration = async (idx, text) => {
    if (!narrationVoiceId || !text) return;
    setPreviewingAudio(idx);
    try {
      const res = await fetch(`${API}/api/elevenlabs/generate-speech`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text.slice(0, 200), voice_id: narrationVoiceId }),
      });
      if (!res.ok) {
        const err = await res.text();
        console.error('ElevenLabs API error:', res.status, err);
        toast.error(`Erro ElevenLabs ${res.status}: ${err.slice(0, 100)}`);
        return;
      }
      const data = await res.json();
      if (data.audio_base64) {
        new Audio(data.audio_base64).play();
      }
    } catch (e) {
      console.error('ElevenLabs fetch error:', e);
      toast.error(`Erro de rede ao gerar áudio: ${e.message}`);
    } finally {
      setPreviewingAudio(null);
    }
  };

  // HeyGen Preview
  const handleHeygenPreview = async () => {
    if (!heygenConfig.avatarId || !heygenConfig.voiceId) return;
    setPreviewLoading(true);
    setPreviewUrl(null);
    setPreviewVideoId(null);
    try {
      // Get short text from first heygen slide
      const firstHeygenSlide = contentSlides.find((_, i) => (mediaConfig[String(_.index)] || {}).type === 'heygen');
      const previewText = firstHeygenSlide
        ? (firstHeygenSlide.elements?.find(e => e.content)?.content || 'Olá! Este é um preview do avatar.').slice(0, 200)
        : 'Olá! Este é um preview do avatar para o seu curso.';

      const res = await fetch(`${API}/api/heygen/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script: previewText,
          avatar_id: heygenConfig.avatarId,
          voice_id: heygenConfig.voiceId,
          title: 'Agent Preview',
        }),
      });
      const data = await res.json();
      if (data.video_id) {
        setPreviewVideoId(data.video_id);
        toast.success('Preview em geração... (~1-2 min)');
      } else {
        toast.error('Erro ao gerar preview');
        setPreviewLoading(false);
      }
    } catch {
      toast.error('Erro ao gerar preview');
      setPreviewLoading(false);
    }
  };

  // Poll for preview video status
  useEffect(() => {
    if (!previewVideoId) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/heygen/video/${previewVideoId}/status`);
        const data = await res.json();
        if (data.status === 'completed' && data.video_url) {
          setPreviewUrl(data.video_url);
          setPreviewLoading(false);
          setPreviewVideoId(null);
          clearInterval(interval);
        } else if (data.status === 'failed') {
          toast.error('Preview falhou');
          setPreviewLoading(false);
          setPreviewVideoId(null);
          clearInterval(interval);
        }
      } catch { /* ignore */ }
    }, 8000);
    return () => clearInterval(interval);
  }, [previewVideoId]);

  if (!storyboard?.slides) return null;

  return (
    <div className="space-y-4" data-testid="media-config-panel">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Image className="w-5 h-5 text-emerald-400" /> Configurar Mídia dos Slides
        </h2>
      </div>

      <p className="text-sm text-slate-400">
        Escolha o tipo de mídia para cada slide de conteúdo. Imagens IA serão geradas automaticamente baseadas no contexto de cada slide.
      </p>

      {/* Global text color for all slides */}
      <Card className="bg-slate-900/50 border-slate-800" data-testid="global-text-color-card">
        <CardContent className="p-4 space-y-3">
          {/* Color row */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Pencil className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-medium text-cyan-300">Cor das Fontes (Todos os Slides)</span>
            </div>
            <div className="flex items-center gap-2 ml-auto">
              <input
                type="color"
                value={globalTextColor || '#ffffff'}
                onChange={e => setGlobalTextColor(e.target.value)}
                className="w-8 h-8 rounded cursor-pointer border-0 bg-transparent"
                data-testid="global-text-color-picker"
              />
              <Input
                value={globalTextColor || ''}
                onChange={e => setGlobalTextColor(e.target.value)}
                placeholder="#ffffff (padrão do template)"
                className="h-8 text-xs bg-slate-800 border-slate-700 w-44"
                data-testid="global-text-color-input"
              />
              {globalTextColor && (
                <button
                  onClick={() => setGlobalTextColor('')}
                  className="text-[10px] text-slate-500 hover:text-red-400 px-1"
                  title="Resetar para cor do template"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
          {/* Font size row */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Type className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-medium text-cyan-300">Tamanho das Fontes</span>
            </div>
            <div className="flex items-center gap-1.5 ml-auto">
              {[
                { label: 'P', value: '80', title: 'Pequeno (80%)' },
                { label: 'N', value: '', title: 'Normal (padrão)' },
                { label: 'G', value: '120', title: 'Grande (120%)' },
                { label: 'GG', value: '140', title: 'Extra Grande (140%)' },
              ].map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setGlobalFontSize(opt.value)}
                  title={opt.title}
                  className={`px-3 py-1.5 rounded text-xs font-semibold transition-all ${
                    globalFontSize === opt.value
                      ? 'bg-cyan-600 text-white'
                      : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200'
                  }`}
                  data-testid={`font-size-${opt.value || 'normal'}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          {/* Preview */}
          <div className="flex items-center gap-3">
            <span className="text-[11px] text-slate-500">Preview:</span>
            <div className="flex gap-2">
              {['#1e293b', '#0f172a', '#ffffff', '#f1f5f9'].map(bg => (
                <div
                  key={bg}
                  className="flex items-center justify-center w-24 h-8 rounded border border-slate-700 font-medium"
                  style={{ background: bg, color: globalTextColor || '#ffffff', fontSize: `${Math.round(12 * (parseInt(globalFontSize || '100') / 100))}px` }}
                >
                  Texto
                </div>
              ))}
              {Object.values(bgConfig).find(b => b.type === 'solid')?.color && (
                <div
                  className="flex items-center justify-center w-24 h-8 rounded border border-cyan-700/50 font-medium"
                  style={{ background: Object.values(bgConfig).find(b => b.type === 'solid').color, color: globalTextColor || '#ffffff', fontSize: `${Math.round(12 * (parseInt(globalFontSize || '100') / 100))}px` }}
                >
                  Seu Fundo
                </div>
              )}
            </div>
          </div>
          {!globalTextColor && !globalFontSize && <p className="text-[10px] text-slate-500 mt-1">Deixe vazio para usar o padrão do template selecionado.</p>}
        </CardContent>
      </Card>

      {/* Global Animation Picker */}
      <Card className="bg-slate-900/50 border-slate-800" data-testid="global-animation-card">
        <CardContent className="p-4 space-y-3">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-amber-400" /> Animação de Entrada dos Textos
          </h3>
          <p className="text-xs text-slate-400">Aplique uma animação de entrada em todos os textos durante a transição de slides.</p>
          <div className="grid grid-cols-3 gap-1.5">
            <AnimPreviewButton animId="" label="Nenhuma" selected={!globalAnimation} onClick={() => setGlobalAnimation('')} testId="global-anim-none" />
            <AnimPreviewButton animId="fadeIn" label="Fade In" selected={globalAnimation === 'fadeIn'} onClick={() => setGlobalAnimation('fadeIn')} testId="global-anim-fadeIn" />
            <AnimPreviewButton animId="slideInLeft" label="Slide Esq." selected={globalAnimation === 'slideInLeft'} onClick={() => setGlobalAnimation('slideInLeft')} testId="global-anim-slideInLeft" />
            <AnimPreviewButton animId="slideInRight" label="Slide Dir." selected={globalAnimation === 'slideInRight'} onClick={() => setGlobalAnimation('slideInRight')} testId="global-anim-slideInRight" />
            <AnimPreviewButton animId="slideInUp" label="Slide Baixo" selected={globalAnimation === 'slideInUp'} onClick={() => setGlobalAnimation('slideInUp')} testId="global-anim-slideInUp" />
            <AnimPreviewButton animId="slideInDown" label="Slide Cima" selected={globalAnimation === 'slideInDown'} onClick={() => setGlobalAnimation('slideInDown')} testId="global-anim-slideInDown" />
            <AnimPreviewButton animId="zoomIn" label="Zoom In" selected={globalAnimation === 'zoomIn'} onClick={() => setGlobalAnimation('zoomIn')} testId="global-anim-zoomIn" />
            <AnimPreviewButton animId="typewriter" label="Typewriter" selected={globalAnimation === 'typewriter'} onClick={() => setGlobalAnimation('typewriter')} testId="global-anim-typewriter" />
            <AnimPreviewButton animId="bounce" label="Bounce" selected={globalAnimation === 'bounce'} onClick={() => setGlobalAnimation('bounce')} testId="global-anim-bounce" />
          </div>
          {globalAnimation && (
            <div className="text-[10px] text-amber-400/60 flex items-center gap-1">
              <Check className="w-3 h-3" /> Animação "{globalAnimation}" será aplicada a todos os textos.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Quick apply buttons */}
      <div className="flex gap-2 flex-wrap">
        <Button variant="outline" size="sm" onClick={() => setAllSlidesMedia('ai_image')} className="text-xs" data-testid="set-all-ai-image">
          <Image className="w-3 h-3 mr-1 text-emerald-400" /> Todas: Imagem IA
        </Button>
        <Button variant="outline" size="sm" onClick={() => setAllSlidesMedia('none')} className="text-xs" data-testid="set-all-none">
          <FileText className="w-3 h-3 mr-1" /> Todas: Sem mídia
        </Button>
      </div>

      {/* HeyGen Avatar/Voice Picker */}
      {heygenCount > 0 && (
        <Card className="bg-purple-900/10 border-purple-800/30" data-testid="heygen-config-card">
          <CardContent className="p-4 space-y-3">
            <h3 className="text-sm font-semibold text-purple-300 flex items-center gap-2">
              <UserCircle className="w-4 h-4" /> Configurar Avatar HeyGen
            </h3>
            <p className="text-xs text-purple-300/60">
              Escolha o avatar e a voz que serão usados em {heygenCount} slide{heygenCount > 1 ? 's' : ''}.
              Os vídeos serão gerados automaticamente após a criação do curso.
            </p>

            {/* Avatar selection */}
            <div className="space-y-2">
              <label className="text-xs text-slate-400 font-medium">Avatar</label>
              {loadingAvatars ? (
                <div className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="w-3 h-3 animate-spin" /> Carregando avatares...</div>
              ) : (
                <div className="grid grid-cols-4 gap-2 max-h-48 overflow-y-auto pr-1">
                  {avatars.slice(0, 20).map(av => (
                    <button
                      key={av.avatar_id}
                      onClick={() => setHeygenConfig(prev => ({ ...prev, avatarId: av.avatar_id }))}
                      className={`rounded-lg border-2 overflow-hidden transition-all ${
                        heygenConfig.avatarId === av.avatar_id
                          ? 'border-purple-500 ring-1 ring-purple-500/30'
                          : 'border-slate-700/50 hover:border-purple-500/40'
                      }`}
                      data-testid={`heygen-avatar-${av.avatar_id}`}
                    >
                      {av.preview_image_url ? (
                        <img src={av.preview_image_url} alt={av.avatar_name} className="w-full h-16 object-cover" />
                      ) : (
                        <div className="w-full h-16 bg-slate-800 flex items-center justify-center">
                          <UserCircle className="w-6 h-6 text-slate-600" />
                        </div>
                      )}
                      <p className="text-[9px] text-center text-slate-400 truncate px-1 py-0.5">{av.avatar_name}</p>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Voice selection */}
            <div className="space-y-2">
              <label className="text-xs text-slate-400 font-medium">Voz (Português)</label>
              {loadingVoices ? (
                <div className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="w-3 h-3 animate-spin" /> Carregando vozes...</div>
              ) : (
                <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                  {voices.map(v => (
                    <button
                      key={v.voice_id}
                      onClick={() => setHeygenConfig(prev => ({ ...prev, voiceId: v.voice_id }))}
                      className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-all text-left ${
                        heygenConfig.voiceId === v.voice_id
                          ? 'border-purple-500 bg-purple-600/10 text-purple-300'
                          : 'border-slate-700/50 text-slate-400 hover:border-purple-500/30'
                      }`}
                      data-testid={`heygen-voice-${v.voice_id}`}
                    >
                      <span className="font-medium">{v.name}</span>
                      <span className="text-slate-500">{v.gender}</span>
                      {v.country_flag && <span>{v.country_flag}</span>}
                      {v.preview_audio && (
                        <span
                          role="button"
                          onClick={(e) => { e.stopPropagation(); new Audio(v.preview_audio).play(); }}
                          className="ml-auto text-purple-400 hover:text-purple-300 cursor-pointer"
                          data-testid={`play-voice-${v.voice_id}`}
                        >
                          <Play className="w-3 h-3" />
                        </span>
                      )}
                    </button>
                  ))}
                  {voices.length === 0 && !loadingVoices && (
                    <p className="text-xs text-slate-500 text-center py-2">Nenhuma voz portuguesa encontrada</p>
                  )}
                </div>
              )}
            </div>

            {!heygenReady && (
              <p className="text-[11px] text-amber-400/70 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Selecione um avatar e uma voz para continuar.
              </p>
            )}

            {/* Preview button + video */}
            {heygenReady && (
              <div className="space-y-2 pt-1 border-t border-purple-800/20">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleHeygenPreview}
                  disabled={previewLoading}
                  className="w-full text-xs border-purple-700/50 text-purple-300 hover:bg-purple-600/10"
                  data-testid="heygen-preview-btn"
                >
                  {previewLoading ? (
                    <><Loader2 className="w-3 h-3 animate-spin mr-1" /> Gerando preview (~1-2 min)...</>
                  ) : (
                    <><Eye className="w-3 h-3 mr-1" /> Testar Avatar + Voz</>
                  )}
                </Button>
                {previewUrl && (
                  <div className="rounded-lg overflow-hidden border border-purple-800/30" data-testid="heygen-preview-video">
                    <video src={previewUrl} controls autoPlay className="w-full rounded-lg" style={{ maxHeight: '200px' }} />
                    <p className="text-[10px] text-purple-400/50 text-center py-1">Preview do avatar selecionado</p>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ElevenLabs Narration Voice Picker */}
      {narrationCount > 0 && (
        <Card className="bg-amber-900/10 border-amber-800/30" data-testid="narration-voice-config-card">
          <CardContent className="p-4 space-y-3">
            <h3 className="text-sm font-semibold text-amber-300 flex items-center gap-2">
              <Volume2 className="w-4 h-4" /> Configurar Narração ElevenLabs
            </h3>
            <p className="text-xs text-amber-300/60">
              Selecione a voz e o estilo para narração em {narrationCount} slide{narrationCount > 1 ? 's' : ''}.
              O áudio será gerado automaticamente após a criação do curso.
            </p>

            {/* Narration style */}
            <div className="space-y-1">
              <label className="text-xs text-slate-400 font-medium">Estilo da Narração</label>
              <div className="flex gap-2 flex-wrap">
                {NARRATION_STYLES.map(s => (
                  <button
                    key={s.id}
                    onClick={() => setNarrationStyle(s.id)}
                    className={`text-[11px] px-3 py-1.5 rounded-lg border transition-all ${
                      narrationStyle === s.id ? 'border-amber-500 bg-amber-600/15 text-amber-300' : 'border-slate-700/50 text-slate-500 hover:border-slate-600'
                    }`}
                    data-testid={`narration-style-${s.id}`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Voice selection */}
            <div className="space-y-2">
              <label className="text-xs text-slate-400 font-medium">Voz ElevenLabs</label>
              {loadingElVoices ? (
                <div className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="w-3 h-3 animate-spin" /> Carregando vozes...</div>
              ) : (
                <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
                  {elVoices.map(v => (
                    <button
                      key={v.voice_id}
                      onClick={() => {
                        setNarrationVoiceId(v.voice_id);
                        // Update all narration-enabled slides with the new voice
                        setMediaConfig(prev => {
                          const next = { ...prev };
                          Object.keys(next).forEach(k => {
                            if (next[k]?.narration?.enabled) {
                              next[k] = { ...next[k], narration: { ...next[k].narration, voiceId: v.voice_id } };
                            }
                          });
                          return next;
                        });
                      }}
                      className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-all text-left ${
                        narrationVoiceId === v.voice_id
                          ? 'border-amber-500 bg-amber-600/10 text-amber-300'
                          : 'border-slate-700/50 text-slate-400 hover:border-amber-500/30'
                      }`}
                      data-testid={`el-narration-voice-${v.voice_id}`}
                    >
                      <Volume2 className="w-3 h-3 shrink-0" />
                      <span className="font-medium">{v.name}</span>
                      {v.labels?.gender && <span className="text-slate-500">{v.labels.gender}</span>}
                      {v.preview_url && (
                        <span
                          role="button"
                          onClick={(e) => { e.stopPropagation(); new Audio(v.preview_url).play(); }}
                          className="ml-auto text-amber-400 hover:text-amber-300 cursor-pointer"
                        >
                          <Play className="w-3 h-3" />
                        </span>
                      )}
                    </button>
                  ))}
                  {elVoices.length === 0 && !loadingElVoices && (
                    <p className="text-xs text-slate-500 text-center py-2">Nenhuma voz encontrada</p>
                  )}
                </div>
              )}
            </div>

            {!narrationVoiceId && narrationCount > 0 && (
              <p className="text-[11px] text-amber-400/70 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Selecione uma voz para a narração.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Global Background Control - Apply to ALL slides at once */}
      <Card className="bg-gradient-to-br from-cyan-900/30 to-slate-900/50 border-cyan-700/30">
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Palette className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-semibold text-cyan-300">Fundo Global</span>
              <Badge variant="outline" className="text-[9px] border-cyan-600/40 text-cyan-400">Todos os Slides</Badge>
            </div>
          </div>
          <p className="text-xs text-slate-400">Aplicar o mesmo fundo a todos os slides de uma vez</p>
          <SlideBackgroundPicker
            slideIndex="__global__"
            bgConfig={bgConfig}
            setBgConfig={(fn) => {
              const globalBg = typeof fn === 'function' ? fn(bgConfig)['__global__'] : fn['__global__'];
              if (globalBg) {
                setBgConfig(() => {
                  const newConfig = {};
                  const totalSlides = storyboard?.slides?.length || 0;
                  for (let i = 0; i < totalSlides; i++) {
                    newConfig[String(i)] = { ...globalBg };
                  }
                  return newConfig;
                });
                toast.success(`Fundo aplicado a todos os ${storyboard?.slides?.length || 0} slides!`);
              }
            }}
            allSlides={storyboard?.slides || []}
            isGlobal
          />
        </CardContent>
      </Card>

      {/* Per-slide config - ALL slides for background, content slides for media */}
      <div className="space-y-3">
        {(storyboard?.slides || []).map((slide, idx) => {
          const isContent = slide.type === 'content';
          const mc = mediaConfig[String(idx)] || { type: 'ai_image' };
          const borderColor = !isContent ? 'border-slate-700/50'
            : mc.type === 'ai_image' ? 'border-emerald-600/40' : mc.type === 'gallery_image' ? 'border-amber-600/40' : mc.type === 'youtube' ? 'border-red-600/40' : mc.type === 'vimeo' ? 'border-blue-600/40' : mc.type === 'heygen' ? 'border-purple-600/40' : 'border-slate-700';
          const typeLabel = { title: 'Capa', content: 'Conteúdo', quiz: 'Quiz', summary: 'Resumo' };
          const typeColor = { title: 'text-blue-400 border-blue-500/40', content: 'text-slate-400 border-slate-600', quiz: 'text-amber-400 border-amber-500/40', summary: 'text-purple-400 border-purple-500/40' };

          return (
            <Card key={idx} className={`bg-slate-900/50 ${borderColor} transition-colors`} data-testid={`media-slide-${idx}`}>
              <CardContent className="p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className={`text-[10px] ${typeColor[slide.type] || 'border-slate-600 text-slate-400'}`}>
                    {typeLabel[slide.type] || slide.type} {idx + 1}
                  </Badge>
                  <span className="text-sm font-medium truncate">{slide.title}</span>
                  {slide.moduleName && <span className="text-[10px] text-slate-500 ml-auto shrink-0">{slide.moduleName}</span>}
                </div>

                {/* Background picker - ALL slides */}
                <SlideBackgroundPicker
                  slideIndex={idx}
                  bgConfig={bgConfig}
                  setBgConfig={setBgConfig}
                  allSlides={storyboard?.slides || []}
                />

                {/* Media type selector - only content slides */}
                {isContent && (
                  <>
                    <div className="border-t border-slate-800 pt-2">
                      <div className="flex items-center gap-2 mb-2">
                        <Image className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-xs font-medium text-emerald-300">Mídia</span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {MEDIA_TYPES.map(mt => {
                          const Icon = mt.icon;
                          const isActive = mc.type === mt.id;
                          const bgColors = {
                            emerald: 'bg-emerald-600/15 border-emerald-500 text-emerald-300',
                            amber: 'bg-amber-600/15 border-amber-500 text-amber-300',
                            red: 'bg-red-600/15 border-red-500 text-red-300',
                            blue: 'bg-blue-600/15 border-blue-500 text-blue-300',
                            purple: 'bg-purple-600/15 border-purple-500 text-purple-300',
                            orange: 'bg-orange-600/15 border-orange-500 text-orange-300',
                            cyan: 'bg-cyan-600/15 border-cyan-500 text-cyan-300',
                            teal: 'bg-teal-600/15 border-teal-500 text-teal-300',
                            slate: 'bg-slate-800 border-slate-600 text-slate-300',
                          };
                          return (
                            <button
                              key={mt.id}
                              onClick={() => {
                                if (mt.id === 'gallery_image') {
                                  setGallerySlideIndex(idx);
                                  setShowGallery(true);
                                } else {
                                  updateSlideMedia(idx, mt.id, '');
                                }
                              }}
                              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-all ${
                                isActive ? bgColors[mt.color] : 'border-slate-700/50 text-slate-500 hover:border-slate-600 hover:text-slate-400'
                              }`}
                              data-testid={`media-type-${mt.id}-slide-${idx}`}
                            >
                              <Icon className="w-3.5 h-3.5" />
                              {mt.label}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* URL input for YouTube/Vimeo */}
                    {(mc.type === 'youtube' || mc.type === 'vimeo') && (
                      <Input
                        value={mc.url || ''}
                        onChange={e => updateSlideMedia(idx, mc.type, e.target.value)}
                        placeholder={mc.type === 'youtube' ? 'https://youtube.com/watch?v=...' : 'https://vimeo.com/...'}
                        className="bg-slate-800 border-slate-700 text-sm"
                        data-testid={`media-url-slide-${idx}`}
                      />
                    )}

                    {/* AI image info */}
                    {mc.type === 'ai_image' && slide.imageKeywords && (
                      <p className="text-[11px] text-emerald-400/60">
                        <Sparkles className="w-3 h-3 inline mr-1" />
                        Será gerada imagem sobre: {slide.imageKeywords}
                      </p>
                    )}

                    {/* Gallery image preview */}
                    {mc.type === 'gallery_image' && mc.galleryImageUrl && (
                      <div className="flex items-center gap-3 p-2 bg-amber-900/10 rounded-lg border border-amber-700/30">
                        <img src={mc.galleryImageUrl.startsWith('/') ? `${API}${mc.galleryImageUrl}` : mc.galleryImageUrl} alt="" className="w-16 h-12 object-cover rounded" />
                        <div className="flex-1 min-w-0">
                          <p className="text-[11px] text-amber-300 truncate">{mc.galleryKeywords || 'Imagem da galeria'}</p>
                          <button onClick={() => { setGallerySlideIndex(idx); setShowGallery(true); }} className="text-[10px] text-amber-400/70 hover:text-amber-300 underline">Trocar imagem</button>
                        </div>
                      </div>
                    )}
                    {mc.type === 'gallery_image' && !mc.galleryImageUrl && (
                      <button onClick={() => { setGallerySlideIndex(idx); setShowGallery(true); }} className="text-[11px] text-amber-400/70 hover:text-amber-300 flex items-center gap-1">
                        <ImagePlus className="w-3 h-3" /> Clique para selecionar da galeria
                      </button>
                    )}

                    {/* HeyGen info */}
                    {mc.type === 'heygen' && (
                      <p className="text-[11px] text-purple-400/60">
                        <UserCircle className="w-3 h-3 inline mr-1" />
                        {heygenConfig.avatarId && heygenConfig.voiceId
                          ? 'Avatar e voz selecionados. O vídeo será gerado automaticamente.'
                          : 'Configure o avatar e a voz acima para gerar o vídeo.'}
                      </p>
                    )}

                    {/* Flipbook config */}
                    {mc.type === 'flipbook' && (
                      <div className="space-y-2" data-testid={`flipbook-config-${idx}`}>
                        <div className="flex gap-2">
                          <button
                            onClick={() => updateSlideMedia(idx, 'flipbook', mc.url || '', { flipbookSource: 'url' })}
                            className={`text-[10px] px-2 py-1 rounded border transition-colors ${mc.flipbookSource !== 'upload' ? 'border-orange-500/50 text-orange-300 bg-orange-600/10' : 'border-slate-700 text-slate-500'}`}
                          >URL</button>
                          <button
                            onClick={() => updateSlideMedia(idx, 'flipbook', mc.url || '', { flipbookSource: 'upload' })}
                            className={`text-[10px] px-2 py-1 rounded border transition-colors ${mc.flipbookSource === 'upload' ? 'border-orange-500/50 text-orange-300 bg-orange-600/10' : 'border-slate-700 text-slate-500'}`}
                          >Upload PDF</button>
                        </div>
                        {mc.flipbookSource === 'upload' ? (
                          <div className="space-y-1">
                            <label className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-dashed border-slate-600 text-xs text-slate-400 hover:border-orange-500/50 hover:text-orange-300 cursor-pointer transition-colors">
                              <UploadCloud className="w-3.5 h-3.5" /> {mc.fileName || 'Selecionar PDF'}
                              <input type="file" accept=".pdf" onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) updateSlideMedia(idx, 'flipbook', '', { flipbookSource: 'upload', fileName: file.name, file });
                              }} className="hidden" />
                            </label>
                          </div>
                        ) : (
                          <Input
                            value={mc.url || ''}
                            onChange={e => updateSlideMedia(idx, 'flipbook', e.target.value)}
                            placeholder="https://flipbook-url.com/embed/..."
                            className="bg-slate-800 border-slate-700 text-sm"
                            data-testid={`flipbook-url-${idx}`}
                          />
                        )}
                        <p className="text-[10px] text-orange-400/50">O flipbook será embutido como elemento interativo no slide.</p>
                      </div>
                    )}

                    {/* HTML embed config */}
                    {mc.type === 'html' && (
                      <div className="space-y-2" data-testid={`html-config-${idx}`}>
                        <div className="flex gap-2">
                          <button
                            onClick={() => updateSlideMedia(idx, 'html', mc.url || '', { htmlSource: 'url' })}
                            className={`text-[10px] px-2 py-1 rounded border transition-colors ${mc.htmlSource !== 'code' ? 'border-cyan-500/50 text-cyan-300 bg-cyan-600/10' : 'border-slate-700 text-slate-500'}`}
                          >URL / iframe</button>
                          <button
                            onClick={() => updateSlideMedia(idx, 'html', mc.url || '', { htmlSource: 'code' })}
                            className={`text-[10px] px-2 py-1 rounded border transition-colors ${mc.htmlSource === 'code' ? 'border-cyan-500/50 text-cyan-300 bg-cyan-600/10' : 'border-slate-700 text-slate-500'}`}
                          >Código HTML</button>
                        </div>
                        {mc.htmlSource === 'code' ? (
                          <textarea
                            value={mc.htmlCode || ''}
                            onChange={e => updateSlideMedia(idx, 'html', '', { htmlSource: 'code', htmlCode: e.target.value })}
                            placeholder="<div>Seu HTML aqui...</div>"
                            rows={4}
                            className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs font-mono text-cyan-300 resize-y"
                            data-testid={`html-code-${idx}`}
                          />
                        ) : (
                          <Input
                            value={mc.url || ''}
                            onChange={e => updateSlideMedia(idx, 'html', e.target.value)}
                            placeholder="https://site.com/embed/..."
                            className="bg-slate-800 border-slate-700 text-sm"
                            data-testid={`html-url-${idx}`}
                          />
                        )}
                        <p className="text-[10px] text-cyan-400/50">Conteúdo HTML será renderizado dentro do slide.</p>
                      </div>
                    )}

                    {/* Button with external link config */}
                    {mc.type === 'button' && (
                      <div className="space-y-2" data-testid={`button-config-${idx}`}>
                        <Input
                          value={mc.buttonText || ''}
                          onChange={e => updateSlideMedia(idx, 'button', mc.url || '', { buttonText: e.target.value })}
                          placeholder="Texto do botão (ex: Saiba Mais)"
                          className="bg-slate-800 border-slate-700 text-sm"
                          data-testid={`button-text-${idx}`}
                        />
                        <Input
                          value={mc.url || ''}
                          onChange={e => updateSlideMedia(idx, 'button', e.target.value, { buttonText: mc.buttonText })}
                          placeholder="https://link-externo.com"
                          className="bg-slate-800 border-slate-700 text-sm"
                          data-testid={`button-url-${idx}`}
                        />
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-slate-400">Cor:</span>
                          <input
                            type="color"
                            value={mc.buttonColor || '#10b981'}
                            onChange={e => updateSlideMedia(idx, 'button', mc.url || '', { buttonText: mc.buttonText, buttonColor: e.target.value })}
                            className="w-6 h-6 rounded cursor-pointer border-0 bg-transparent"
                          />
                          <div className="flex-1 flex items-center justify-center px-3 py-1.5 rounded-lg text-xs text-white font-medium" style={{ background: mc.buttonColor || '#10b981' }}>
                            {mc.buttonText || 'Botão'}
                          </div>
                        </div>
                        <p className="text-[10px] text-teal-400/50">O botão será inserido no slide com link para URL externa.</p>
                      </div>
                    )}

                    {/* Per-slide Narration */}
                    <div className="border-t border-slate-800 pt-2">
                      <div className="flex items-center gap-2 mb-2">
                        <Volume2 className="w-3.5 h-3.5 text-amber-400" />
                        <span className="text-xs font-medium text-amber-300">Narração</span>
                        <button
                          onClick={() => toggleSlideNarration(idx, !mc.narration?.enabled)}
                          className={`ml-auto w-9 h-5 rounded-full transition-colors relative ${mc.narration?.enabled ? 'bg-amber-600' : 'bg-slate-700'}`}
                          data-testid={`narration-toggle-slide-${idx}`}
                        >
                          <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${mc.narration?.enabled ? 'translate-x-4' : 'translate-x-0.5'}`} />
                        </button>
                      </div>

                      {mc.narration?.enabled && (
                        <div className="space-y-2 pl-1">
                          {/* Generate scripts button */}
                          {!scriptOptions[idx] && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => generateNarrationScripts(idx)}
                              disabled={generatingScripts[idx]}
                              className="w-full text-xs border-amber-700/50 text-amber-300 hover:bg-amber-600/10"
                              data-testid={`generate-narration-slide-${idx}`}
                            >
                              {generatingScripts[idx] ? (
                                <><Loader2 className="w-3 h-3 animate-spin mr-1" /> Gerando 3 opções...</>
                              ) : (
                                <><Sparkles className="w-3 h-3 mr-1" /> Gerar 3 Opções de Roteiro</>
                              )}
                            </Button>
                          )}

                          {/* Script options */}
                          {scriptOptions[idx] && (
                            <div className="space-y-2">
                              <div className="flex items-center justify-between">
                                <span className="text-[10px] text-slate-400 font-medium">Escolha um roteiro:</span>
                                <button
                                  onClick={() => {
                                    setScriptOptions(prev => { const n = {...prev}; delete n[idx]; return n; });
                                    generateNarrationScripts(idx);
                                  }}
                                  className="text-[10px] text-amber-400 hover:text-amber-300 flex items-center gap-1"
                                  disabled={generatingScripts[idx]}
                                >
                                  <RefreshCw className="w-3 h-3" /> Regenerar
                                </button>
                              </div>
                              {scriptOptions[idx].map((opt, oi) => {
                                const isSelected = mc.narration?.selectedScript === opt;
                                return (
                                  <div
                                    key={oi}
                                    role="button"
                                    tabIndex={0}
                                    onClick={() => selectNarrationScript(idx, opt)}
                                    className={`w-full text-left p-2.5 rounded-lg border text-[11px] leading-relaxed transition-all cursor-pointer ${
                                      isSelected
                                        ? 'border-amber-500 bg-amber-600/10 text-amber-200'
                                        : 'border-slate-700/50 text-slate-400 hover:border-amber-500/30'
                                    }`}
                                    data-testid={`narration-option-${idx}-${oi}`}
                                  >
                                    <div className="flex items-start gap-2">
                                      <Badge variant="outline" className={`text-[9px] shrink-0 mt-0.5 ${isSelected ? 'border-amber-500 text-amber-300' : 'border-slate-600 text-slate-500'}`}>
                                        {oi + 1}
                                      </Badge>
                                      <span>{opt}</span>
                                    </div>
                                    {isSelected && narrationVoiceId && (
                                      <div className="flex items-center gap-2 mt-2 pt-2 border-t border-amber-800/30">
                                        <button
                                          onClick={(e) => { e.stopPropagation(); previewNarration(idx, opt); }}
                                          disabled={previewingAudio === idx}
                                          className="text-[10px] text-amber-400 hover:text-amber-300 flex items-center gap-1"
                                        >
                                          {previewingAudio === idx ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                                          Ouvir Preview
                                        </button>
                                        <Check className="w-3 h-3 text-amber-400 ml-auto" />
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          )}

                          {mc.narration?.selectedScript && (
                            <p className="text-[10px] text-amber-400/60 flex items-center gap-1">
                              <Check className="w-3 h-3" /> Roteiro selecionado. Áudio será gerado com a voz escolhida.
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Summary & Cost Estimate */}
      <CostEstimateCard sessionId={sessionId} aiCount={aiCount} videoCount={videoCount} heygenCount={heygenCount} bgConfig={bgConfig} isEditMode={isEditMode} changedSlideCount={changedSlideCount} />

      {(!heygenReady || !narrationReady) && !loading && (
        <p className="text-xs text-amber-400/80 text-center">
          {!heygenReady && 'Selecione avatar e voz do HeyGen. '}
          {!narrationReady && 'Selecione uma voz para a narração antes de aplicar.'}
        </p>
      )}
      <Button onClick={onConfirm} disabled={loading || !heygenReady || !narrationReady} className={`w-full ${isEditMode ? 'bg-blue-600 hover:bg-blue-700' : 'bg-emerald-600 hover:bg-emerald-700'}`} data-testid="confirm-media-btn">
        {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : isEditMode ? <Check className="w-4 h-4 mr-1" /> : <Play className="w-4 h-4 mr-1" />}
        {isEditMode ? 'Aplicar Alterações ao Projeto' : 'Confirmar Mídia e Gerar Curso'}
      </Button>

      {/* Image Gallery Modal */}
      {showGallery && (
        <ImageGalleryModal
          onClose={() => setShowGallery(false)}
          onSelect={(img) => {
            if (gallerySlideIndex !== null) {
              updateSlideMedia(gallerySlideIndex, 'gallery_image', '', {
                galleryImageUrl: img.imageUrl,
                galleryKeywords: img.keywords,
                galleryImageId: img.id,
              });
            }
            setShowGallery(false);
          }}
        />
      )}
    </div>
  );
}


function ImageGalleryModal({ onClose, onSelect }) {
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    setLoading(true);
    fetch(`${API}/api/gallery/images`)
      .then(r => r.json())
      .then(data => setImages(data.images || []))
      .catch(() => toast.error('Erro ao carregar galeria'))
      .finally(() => setLoading(false));
  }, []);

  const filtered = search
    ? images.filter(img =>
        (img.keywords || '').toLowerCase().includes(search.toLowerCase()) ||
        (img.projectName || '').toLowerCase().includes(search.toLowerCase())
      )
    : images;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" data-testid="gallery-modal">
      <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl">
        <div className="flex items-center justify-between p-4 border-b border-slate-800">
          <h3 className="text-base font-semibold flex items-center gap-2">
            <ImagePlus className="w-5 h-5 text-amber-400" />
            Galeria de Imagens
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-4 border-b border-slate-800">
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Buscar por palavras-chave ou projeto..."
            className="bg-slate-800 border-slate-700"
            data-testid="gallery-search"
          />
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-slate-400" /></div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              <ImagePlus className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">{images.length === 0 ? 'Nenhuma imagem na galeria ainda.' : 'Nenhuma imagem encontrada.'}</p>
              <p className="text-xs mt-1 text-slate-500">{images.length === 0 ? 'As imagens geradas por IA serão salvas aqui automaticamente.' : 'Tente outra busca.'}</p>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-3">
              {filtered.map(img => (
                <button
                  key={img.id}
                  onClick={() => onSelect(img)}
                  className="group relative rounded-lg overflow-hidden border border-slate-700 hover:border-amber-500 transition-all aspect-[4/3]"
                  data-testid={`gallery-image-${img.id}`}
                >
                  <img
                    src={img.imageUrl.startsWith('/') ? `${API}${img.imageUrl}` : img.imageUrl}
                    alt={img.keywords || ''}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-2">
                    <p className="text-[10px] text-white/90 truncate">{img.keywords || 'Sem palavras-chave'}</p>
                    <p className="text-[9px] text-white/50 truncate">{img.projectName || ''}</p>
                  </div>
                  <div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <div className="bg-amber-500 text-black rounded-full p-1"><Check className="w-3 h-3" /></div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="p-3 border-t border-slate-800 text-center">
          <p className="text-[10px] text-slate-500">{filtered.length} de {images.length} imagens</p>
        </div>
      </div>
    </div>
  );
}


const PRIORITY_STYLES = {
  alta: 'bg-red-600/15 text-red-300 border-red-500/40',
  media: 'bg-amber-600/15 text-amber-300 border-amber-500/40',
  baixa: 'bg-slate-700/30 text-slate-300 border-slate-600/40',
};

function SuggestionsCategory({ icon: Icon, title, color, items }) {
  if (!items || items.length === 0) return null;
  const colorMap = {
    blue: 'text-blue-400 border-blue-800/40',
    purple: 'text-purple-400 border-purple-800/40',
    amber: 'text-amber-400 border-amber-800/40',
    emerald: 'text-emerald-400 border-emerald-800/40',
    pink: 'text-pink-400 border-pink-800/40',
    orange: 'text-orange-400 border-orange-800/40',
  };
  const colors = colorMap[color] || colorMap.blue;

  return (
    <div className={`border rounded-lg p-3 space-y-2 ${colors.split(' ').slice(1).join(' ')}`} data-testid={`suggestions-category-${color}`}>
      <div className="flex items-center gap-2">
        <Icon className={`w-3.5 h-3.5 ${colors.split(' ')[0]}`} />
        <span className={`text-xs font-semibold ${colors.split(' ')[0]}`}>{title}</span>
        <Badge variant="outline" className="text-[9px] ml-auto border-slate-700 text-slate-400">{items.length}</Badge>
      </div>
      {items.map((item, idx) => (
        <div key={idx} className="pl-5 space-y-0.5" data-testid={`suggestion-item-${color}-${idx}`}>
          <div className="flex items-start gap-2">
            <span className="text-xs font-medium text-slate-200">{item.title}</span>
            <Badge variant="outline" className={`text-[8px] shrink-0 ${PRIORITY_STYLES[item.priority] || PRIORITY_STYLES.media}`}>
              {item.priority}
            </Badge>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">{item.description}</p>
          {item.impact && <p className="text-[10px] text-cyan-400/60 italic">{item.impact}</p>}
        </div>
      ))}
    </div>
  );
}

function GeneratedPanel({ project, navigate, sessionId }) {
  const [heygenStatus, setHeygenStatus] = useState(null);
  const [narrationStatus, setNarrationStatus] = useState(null);
  const [polling, setPolling] = useState(false);
  const [suggestions, setSuggestions] = useState(null);
  const [suggestionsStatus, setSuggestionsStatus] = useState('loading');
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const checkHeygenStatus = useCallback(async () => {
    if (!project?.projectId || !project?.heygenPending) return;
    setPolling(true);
    try {
      const res = await fetch(`${API}/api/agent/projects/${project.projectId}/heygen-status`);
      const data = await res.json();
      setHeygenStatus(data);
    } catch { /* ignore */ }
    finally { setPolling(false); }
  }, [project?.projectId, project?.heygenPending]);

  const checkNarrationStatus = useCallback(async () => {
    if (!project?.projectId || !project?.narrationPending) return;
    try {
      const res = await fetch(`${API}/api/agent/projects/${project.projectId}/narration-status`);
      const data = await res.json();
      setNarrationStatus(data);
    } catch { /* ignore */ }
  }, [project?.projectId, project?.narrationPending]);

  useEffect(() => {
    if (project?.heygenPending > 0) {
      checkHeygenStatus();
      const interval = setInterval(checkHeygenStatus, 15000);
      return () => clearInterval(interval);
    }
  }, [project?.heygenPending, checkHeygenStatus]);

  useEffect(() => {
    if (project?.narrationPending > 0) {
      checkNarrationStatus();
      const interval = setInterval(checkNarrationStatus, 10000);
      return () => clearInterval(interval);
    }
  }, [project?.narrationPending, checkNarrationStatus]);

  // Poll for suggestions
  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await fetch(`${API}/api/agent/sessions/${sessionId}/suggestions`);
        const data = await res.json();
        if (cancelled) return;
        if (data.status === 'ready') {
          setSuggestions(data.suggestions);
          setSuggestionsStatus('ready');
        } else if (data.status === 'error') {
          setSuggestionsStatus('error');
        } else {
          setSuggestionsStatus('pending');
        }
      } catch { if (!cancelled) setSuggestionsStatus('error'); }
    };
    poll();
    const interval = setInterval(() => {
      if (suggestionsStatus === 'pending') poll();
    }, 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [sessionId, suggestionsStatus]);

  const handleRegenerateSuggestions = async () => {
    setRegenerating(true);
    setSuggestionsStatus('pending');
    setSuggestions(null);
    try {
      await fetch(`${API}/api/agent/sessions/${sessionId}/suggestions/regenerate`, { method: 'POST' });
    } catch { /* will poll */ }
    finally { setRegenerating(false); }
  };

  if (!project) return null;
  return (
    <div className="space-y-6 text-center" data-testid="generated-panel">
      <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-emerald-600/10">
        <Check className="w-10 h-10 text-emerald-400" />
      </div>
      <h2 className="text-2xl font-bold">Curso Gerado com Sucesso!</h2>
      <p className="text-slate-400">{project.projectName}</p>
      <div className="flex justify-center gap-4">
        <Badge className="bg-emerald-600/20 text-emerald-300"><Layers className="w-3 h-3 mr-1" />{project.slidesCount} slides</Badge>
        <Badge className="bg-amber-600/20 text-amber-300"><BarChart3 className="w-3 h-3 mr-1" />{project.quizCount} perguntas</Badge>
      </div>

      {/* HeyGen Video Status */}
      {project.heygenPending > 0 && (
        <Card className="bg-purple-900/10 border-purple-800/30 text-left mx-auto max-w-md" data-testid="heygen-status-card">
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-purple-300 flex items-center gap-2">
                <UserCircle className="w-4 h-4" /> Vídeos Avatar HeyGen
              </h3>
              <Button variant="ghost" size="sm" onClick={checkHeygenStatus} disabled={polling} className="text-xs text-purple-400" data-testid="refresh-heygen-btn">
                {polling ? <Loader2 className="w-3 h-3 animate-spin" /> : <ArrowRight className="w-3 h-3" />} Atualizar
              </Button>
            </div>
            {heygenStatus?.videos?.map((v, i) => (
              <div key={i} className="flex items-center gap-2 text-xs" data-testid={`heygen-video-status-${i}`}>
                {v.status === 'completed' ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                ) : v.status === 'failed' ? (
                  <X className="w-3.5 h-3.5 text-red-400 shrink-0" />
                ) : (
                  <Loader2 className="w-3.5 h-3.5 text-purple-400 animate-spin shrink-0" />
                )}
                <span className="text-slate-300 truncate flex-1">{v.title}</span>
                <Badge variant="outline" className={`text-[9px] ${
                  v.status === 'completed' ? 'border-emerald-700 text-emerald-400' :
                  v.status === 'failed' ? 'border-red-700 text-red-400' :
                  'border-purple-700 text-purple-400'
                }`}>
                  {v.status === 'completed' ? 'Pronto' : v.status === 'failed' ? 'Falhou' : 'Processando...'}
                </Badge>
              </div>
            ))}
            {heygenStatus?.status === 'all_done' && (
              <p className="text-[11px] text-emerald-400/70 text-center">Todos os vídeos foram gerados! Abra o editor para visualizar.</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Narration Status */}
      {project.narrationPending > 0 && (
        <Card className="bg-amber-900/10 border-amber-800/30 text-left mx-auto max-w-md" data-testid="narration-status-card">
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-amber-300 flex items-center gap-2">
                <Play className="w-4 h-4" /> Narração ElevenLabs
              </h3>
              {narrationStatus && (
                <Badge variant="outline" className={`text-[10px] ${narrationStatus.status === 'all_done' ? 'border-emerald-700 text-emerald-400' : 'border-amber-700 text-amber-400'}`}>
                  {narrationStatus.completed || 0}/{narrationStatus.total || 0}
                </Badge>
              )}
            </div>
            {narrationStatus?.slides?.map((s, i) => (
              <div key={i} className="flex items-center gap-2 text-xs" data-testid={`narration-status-${i}`}>
                {s.status === 'completed' ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                ) : s.status === 'failed' ? (
                  <X className="w-3.5 h-3.5 text-red-400 shrink-0" />
                ) : (
                  <Loader2 className="w-3.5 h-3.5 text-amber-400 animate-spin shrink-0" />
                )}
                <span className="text-slate-300 truncate flex-1">{s.title}</span>
                <Badge variant="outline" className={`text-[9px] ${
                  s.status === 'completed' ? 'border-emerald-700 text-emerald-400' :
                  s.status === 'failed' ? 'border-red-700 text-red-400' :
                  'border-amber-700 text-amber-400'
                }`}>
                  {s.status === 'completed' ? 'Pronto' : s.status === 'failed' ? 'Falhou' : 'Gerando...'}
                </Badge>
              </div>
            ))}
            {narrationStatus?.status === 'all_done' && (
              <p className="text-[11px] text-emerald-400/70 text-center">Todas as narrações geradas! Abra o editor para ouvir.</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Improvement Suggestions */}
      <Card className="bg-slate-900/50 border-cyan-800/30 text-left mx-auto max-w-2xl" data-testid="suggestions-panel">
        <CardContent className="p-4 space-y-3">
          <button
            onClick={() => setSuggestionsOpen(!suggestionsOpen)}
            className="flex items-center justify-between w-full"
            data-testid="suggestions-toggle"
          >
            <h3 className="text-sm font-semibold text-cyan-300 flex items-center gap-2">
              <Lightbulb className="w-4 h-4" /> Sugestões de Melhoria
              {suggestionsStatus === 'pending' && <Loader2 className="w-3 h-3 animate-spin text-cyan-400/60" />}
              {suggestionsStatus === 'ready' && suggestions && (
                <Badge className="bg-cyan-600/20 text-cyan-300 text-[10px]">
                  {Object.values(suggestions).flat().length} sugestões
                </Badge>
              )}
            </h3>
            {suggestionsOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>

          {suggestionsOpen && (
            <div className="space-y-4 pt-2">
              {suggestionsStatus === 'pending' && (
                <div className="flex items-center gap-2 text-xs text-cyan-400/70 py-4 justify-center">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Analisando o processo e gerando sugestões...
                </div>
              )}
              {suggestionsStatus === 'error' && (
                <div className="text-center py-4 space-y-2">
                  <p className="text-xs text-red-400">Erro ao gerar sugestões.</p>
                  <Button variant="outline" size="sm" onClick={handleRegenerateSuggestions} disabled={regenerating} className="text-xs" data-testid="retry-suggestions-btn">
                    <RefreshCw className="w-3 h-3 mr-1" /> Tentar novamente
                  </Button>
                </div>
              )}
              {suggestionsStatus === 'ready' && suggestions && (
                <>
                  <SuggestionsCategory icon={Monitor} title="Plataforma — UX" color="blue" items={suggestions.platform_ux} />
                  <SuggestionsCategory icon={Rocket} title="Plataforma — Features" color="purple" items={suggestions.platform_features} />
                  <SuggestionsCategory icon={Zap} title="Plataforma — Performance" color="amber" items={suggestions.platform_performance} />
                  <SuggestionsCategory icon={BookMarked} title="Curso — Conteúdo" color="emerald" items={suggestions.course_content} />
                  <SuggestionsCategory icon={PaintBucket} title="Curso — Design" color="pink" items={suggestions.course_design} />
                  <SuggestionsCategory icon={Target} title="Curso — Pedagogia" color="orange" items={suggestions.course_pedagogy} />
                  <div className="pt-2 flex justify-center">
                    <Button variant="outline" size="sm" onClick={handleRegenerateSuggestions} disabled={regenerating} className="text-xs border-cyan-700/50 text-cyan-400" data-testid="regenerate-suggestions-btn">
                      {regenerating ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <RefreshCw className="w-3 h-3 mr-1" />}
                      Gerar novas sugestões
                    </Button>
                  </div>
                </>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex gap-3 justify-center">
        <Button onClick={() => navigate(`/editor/${project.projectId}`)} className="bg-emerald-600 hover:bg-emerald-700" data-testid="open-editor-btn">
          <BookOpen className="w-4 h-4 mr-2" /> Abrir no Editor
        </Button>
        <Button variant="outline" onClick={() => navigate('/')} data-testid="back-dashboard-btn">
          <ArrowLeft className="w-4 h-4 mr-2" /> Dashboard
        </Button>
      </div>
    </div>
  );
}

/* ====================== EDIT MODE PANELS ====================== */

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

function CourseReviewPanel({ course, analysis, loading, selectedImprovements, toggleImprovement, onApply }) {
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

function EditResultPanel({ result, course, navigate }) {
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