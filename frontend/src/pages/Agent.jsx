import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { getApiUrl } from '../utils/apiUrl';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { ScrollArea } from '../components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Slider } from '../components/ui/slider';
import { Checkbox } from '../components/ui/checkbox';
import { toast } from 'sonner';
import {
  Brain, Upload, FileText, Settings, BookOpen, Layers, Play,
  Send, ArrowLeft, ArrowRight, Check, Loader2, Sparkles,
  GraduationCap, Clock, BarChart3, Lightbulb, ChevronRight,
  X, MessageSquare, PanelRightOpen, PanelRightClose,
  Pencil, Plus, Shield, Wrench, Heart, HardHat, TrendingUp, Users,
  AlertTriangle, Star, Zap,
} from 'lucide-react';

const API = getApiUrl();

// ===== CREATE MODE STEPS =====
const CREATE_STEPS = [
  { id: 'upload', label: 'Conteúdo', icon: Upload },
  { id: 'analyze', label: 'Análise', icon: Brain },
  { id: 'configure', label: 'Configurar', icon: Settings },
  { id: 'structure', label: 'Estrutura', icon: Layers },
  { id: 'storyboard', label: 'Storyboard', icon: BookOpen },
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
  // Mode: null = selection, 'create' = new course, 'edit' = edit existing
  const [mode, setMode] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [showChat, setShowChat] = useState(true);

  // Create mode data
  const [contentText, setContentText] = useState('');
  const [fileName, setFileName] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [config, setConfig] = useState({
    title: '', depth: 'intermediario', duration: 30, modules: 3,
    interactivity: 'media', visualStyle: 'moderno e profissional',
    format: 'curso_completo', description: '',
  });
  const [structure, setStructure] = useState(null);
  const [storyboard, setStoryboard] = useState(null);
  const [generatedProject, setGeneratedProject] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);

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

  const addChatMsg = useCallback((role, text) => {
    setChatMessages(prev => [...prev, { role, text, ts: new Date().toISOString() }]);
  }, []);

  // Load templates on mount
  useEffect(() => {
    fetch(`${API}/api/agent/templates`)
      .then(r => r.json())
      .then(setTemplates)
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
      await fetch(`${API}/api/agent/sessions/${sessionId}/configure`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config),
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
    addChatMsg('agent', 'Criando storyboard detalhado... Pode levar até 1 minuto.');
    try {
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/generate-storyboard`, { method: 'POST' });
      if (!res.ok) throw new Error();
      const pollInterval = setInterval(async () => {
        try {
          const sRes = await fetch(`${API}/api/agent/sessions/${sessionId}`);
          const session = await sRes.json();
          if (session.step === 'storyboarded' && session.storyboard) {
            clearInterval(pollInterval);
            setStoryboard(session.storyboard);
            addChatMsg('agent', `Storyboard completo com ${session.storyboard.slides?.length || 0} slides!`);
            setCurrentStep(4);
            setLoading(false);
          } else if (session.step === 'structured') {
            clearInterval(pollInterval);
            addChatMsg('agent', session.error || 'Erro ao gerar storyboard.');
            toast.error(session.error || 'Erro no storyboard');
            setLoading(false);
          }
        } catch { /* polling */ }
      }, 3000);
      setTimeout(() => { clearInterval(pollInterval); setLoading(false); }, 180000);
    } catch { toast.error('Erro no storyboard'); setLoading(false); }
  };

  const handleGenerateCourse = async () => {
    setLoading(true);
    addChatMsg('agent', 'Gerando o curso no Scormfy...');
    try {
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/generate-course`, { method: 'POST' });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setGeneratedProject(data);
      addChatMsg('agent', `Curso "${data.projectName}" criado! ${data.slidesCount} slides e ${data.quizCount} perguntas.`);
      setCurrentStep(5);
      toast.success('Curso gerado com sucesso!');
    } catch { toast.error('Erro ao gerar curso'); addChatMsg('agent', 'Erro ao gerar o curso.'); }
    finally { setLoading(false); }
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
              {mode === 'create' && currentStep === 0 && <UploadPanel contentText={contentText} setContentText={setContentText} fileName={fileName} fileInputRef={fileInputRef} handleFileUpload={handleFileUpload} handleTextSubmit={handleTextSubmit} loading={loading} />}
              {mode === 'create' && currentStep === 1 && <AnalyzePanel analysis={analysis} loading={loading} onAnalyze={handleAnalyze} />}
              {mode === 'create' && currentStep === 2 && <ConfigPanel config={config} setConfig={setConfig} analysis={analysis} loading={loading} onGenerate={handleGenerateStructure} templates={templates} selectedTemplate={selectedTemplate} setSelectedTemplate={setSelectedTemplate} />}
              {mode === 'create' && currentStep === 3 && <StructurePanel structure={structure} loading={loading} onApprove={handleGenerateStoryboard} />}
              {mode === 'create' && currentStep === 4 && <StoryboardPanel storyboard={storyboard} loading={loading} onApprove={handleGenerateCourse} />}
              {mode === 'create' && currentStep === 5 && <GeneratedPanel project={generatedProject} navigate={navigate} />}

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

function UploadPanel({ contentText, setContentText, fileName, fileInputRef, handleFileUpload, handleTextSubmit, loading }) {
  return (
    <div className="space-y-6" data-testid="upload-panel">
      <div className="text-center space-y-2">
        <h1 className="text-xl font-bold">Envie o Conteúdo</h1>
        <p className="text-slate-400 text-sm max-w-lg mx-auto">
          Faça upload de um arquivo ou cole o texto diretamente.
        </p>
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <Card className="bg-slate-900/50 border-slate-800 hover:border-emerald-600/40 transition-colors cursor-pointer"
          onClick={() => fileInputRef.current?.click()}>
          <CardContent className="p-6 text-center space-y-3">
            <Upload className="w-10 h-10 text-emerald-400 mx-auto" />
            <div>
              <p className="font-medium text-sm">Upload de Arquivo</p>
              <p className="text-xs text-slate-400">PDF, PPT, PPTX, DOC, DOCX, TXT</p>
            </div>
            {fileName && <Badge variant="secondary" className="text-xs">{fileName}</Badge>}
            <input ref={fileInputRef} type="file" className="hidden" accept=".pdf,.ppt,.pptx,.doc,.docx,.txt" onChange={handleFileUpload} data-testid="file-upload-input" />
          </CardContent>
        </Card>
        <Card className="bg-slate-900/50 border-slate-800">
          <CardContent className="p-6 space-y-3">
            <FileText className="w-10 h-10 text-blue-400 mx-auto" />
            <p className="font-medium text-sm text-center">Texto Direto</p>
            <Textarea data-testid="content-text-input" value={contentText} onChange={e => setContentText(e.target.value)} placeholder="Cole ou digite o conteúdo aqui..." className="bg-slate-800 border-slate-700 text-sm min-h-[120px]" />
            <Button onClick={handleTextSubmit} disabled={loading || !contentText.trim()} className="w-full bg-emerald-600 hover:bg-emerald-700" size="sm" data-testid="submit-text-btn">
              {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Send className="w-4 h-4 mr-1" />}
              Enviar Conteúdo
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

function ConfigPanel({ config, setConfig, analysis, loading, onGenerate, templates, selectedTemplate, setSelectedTemplate }) {
  const update = (k, v) => setConfig(prev => ({ ...prev, [k]: v }));
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
      </div>
      <Button onClick={onGenerate} disabled={loading} className="w-full bg-emerald-600 hover:bg-emerald-700" data-testid="generate-structure-btn">
        {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Layers className="w-4 h-4 mr-1" />}
        {selectedTemplate ? `Gerar com Template "${selectedTemplate.name}"` : 'Gerar Estrutura do Curso'}
      </Button>
    </div>
  );
}

function StructurePanel({ structure, loading, onApprove }) {
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
      <Button onClick={onApprove} disabled={loading} className="w-full bg-emerald-600 hover:bg-emerald-700" data-testid="approve-structure-btn">
        {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <BookOpen className="w-4 h-4 mr-1" />}
        Aprovar e Gerar Storyboard
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

function GeneratedPanel({ project, navigate }) {
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
        <div className="grid gap-3">
          {courses.map(course => (
            <Card
              key={course.id}
              className="bg-slate-900/50 border-slate-800 hover:border-blue-500/40 transition-all cursor-pointer"
              onClick={() => onSelect(course)}
              data-testid={`course-item-${course.id}`}
            >
              <CardContent className="p-4 flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-blue-600/10 flex items-center justify-center shrink-0">
                  <BookOpen className="w-5 h-5 text-blue-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-sm truncate">{course.name}</h3>
                  <p className="text-xs text-slate-400 truncate">{course.description || 'Sem descrição'}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Badge variant="outline" className="text-[10px] border-slate-600">
                    <Layers className="w-3 h-3 mr-1" />{course.slidesCount} slides
                  </Badge>
                  <ChevronRight className="w-4 h-4 text-slate-500" />
                </div>
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
