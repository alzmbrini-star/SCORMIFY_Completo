import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { getApiUrl } from '../utils/apiUrl';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Slider } from '../components/ui/slider';
import { toast } from 'sonner';
import {
  Brain, Upload, FileText, Settings, BookOpen, Layers, Play,
  Send, ArrowLeft, ArrowRight, Check, Loader2, Sparkles,
  GraduationCap, Clock, BarChart3, Lightbulb, ChevronRight,
  X, MessageSquare, PanelRightOpen, PanelRightClose,
} from 'lucide-react';

const API = getApiUrl();

const STEPS = [
  { id: 'upload', label: 'Conteúdo', icon: Upload },
  { id: 'analyze', label: 'Análise', icon: Brain },
  { id: 'configure', label: 'Configurar', icon: Settings },
  { id: 'structure', label: 'Estrutura', icon: Layers },
  { id: 'storyboard', label: 'Storyboard', icon: BookOpen },
  { id: 'generate', label: 'Gerar Curso', icon: Play },
];

const STEP_INDEX = { upload: 0, analyze: 1, configure: 2, structure: 3, storyboard: 4, generate: 5 };

export default function Agent() {
  const navigate = useNavigate();
  const [sessionId, setSessionId] = useState(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [showChat, setShowChat] = useState(true);

  // Data
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

  // Chat
  const [chatMessages, setChatMessages] = useState([
    { role: 'agent', text: 'Olá! Sou seu Agente de Design Instrucional. Envie o conteúdo que deseja transformar em curso e eu vou guiá-lo por todo o processo de criação.' },
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

  // Create session on first interaction
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

  // File upload
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
      addChatMsg('agent', `Arquivo "${file.name}" recebido com sucesso! ${data.contentLength} caracteres extraídos. Clique em "Analisar" ou envie mais conteúdo.`);
      setCurrentStep(1);
    } catch (e) {
      toast.error('Erro no upload');
      addChatMsg('agent', 'Erro ao processar o arquivo. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  // Text upload
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
      addChatMsg('agent', 'Conteúdo recebido! Agora vou analisar o material. Clique em "Analisar Conteúdo".');
      setCurrentStep(1);
    } catch (e) {
      toast.error('Erro ao enviar conteúdo');
    } finally {
      setLoading(false);
    }
  };

  // Step 1: Analyze
  const handleAnalyze = async () => {
    setLoading(true);
    addChatMsg('agent', 'Analisando o conteúdo com IA... Isso pode levar alguns segundos.');
    try {
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/analyze`, { method: 'POST' });
      if (!res.ok) throw new Error('Falha na análise');
      const data = await res.json();
      setAnalysis(data);
      setConfig(prev => ({
        ...prev,
        title: data.title || prev.title,
        description: data.summary || prev.description,
        duration: data.estimatedDuration || prev.duration,
        modules: data.suggestedModules || prev.modules,
        depth: data.difficulty || prev.depth,
      }));
      addChatMsg('agent', `Análise concluída! Identifiquei ${data.mainTopics?.length || 0} tópicos principais. Sugiro "${data.title}" como título. Revise a configuração e ajuste conforme necessário.`);
      setCurrentStep(2);
    } catch (e) {
      toast.error('Erro na análise');
      addChatMsg('agent', 'Erro ao analisar. Verifique se o conteúdo foi enviado corretamente.');
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Configure & Generate Structure
  const handleGenerateStructure = async () => {
    setLoading(true);
    addChatMsg('agent', 'Gerando a estrutura pedagógica do curso...');
    try {
      // Save config
      await fetch(`${API}/api/agent/sessions/${sessionId}/configure`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      // Generate structure
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/generate-structure`, { method: 'POST' });
      if (!res.ok) throw new Error('Falha na geração');
      const data = await res.json();
      setStructure(data);
      const totalSlides = data.modules?.reduce((sum, m) => sum + (m.slides?.length || 0), 0) || 0;
      addChatMsg('agent', `Estrutura criada! ${data.modules?.length || 0} módulos com ${totalSlides} slides no total. Revise e aprove para gerar o storyboard detalhado.`);
      setCurrentStep(3);
    } catch (e) {
      toast.error('Erro ao gerar estrutura');
      addChatMsg('agent', 'Erro ao gerar a estrutura. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  // Step 3: Generate Storyboard (background task with polling)
  const handleGenerateStoryboard = async () => {
    setLoading(true);
    addChatMsg('agent', 'Criando storyboard detalhado com conteúdo para cada slide... Isso pode levar até 1 minuto.');
    try {
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/generate-storyboard`, { method: 'POST' });
      if (!res.ok) throw new Error('Falha no storyboard');
      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const sRes = await fetch(`${API}/api/agent/sessions/${sessionId}`);
          const session = await sRes.json();
          if (session.step === 'storyboarded' && session.storyboard) {
            clearInterval(pollInterval);
            setStoryboard(session.storyboard);
            addChatMsg('agent', `Storyboard completo com ${session.storyboard.slides?.length || 0} slides detalhados! Revise o conteúdo e aprove para gerar o curso.`);
            setCurrentStep(4);
            setLoading(false);
          } else if (session.step === 'structured') {
            clearInterval(pollInterval);
            addChatMsg('agent', 'Erro ao gerar storyboard. Tente novamente.');
            setLoading(false);
          }
        } catch (e) { /* keep polling */ }
      }, 3000);
      // Timeout after 3 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        if (loading) {
          addChatMsg('agent', 'A geração do storyboard está demorando. Verifique o status em alguns instantes.');
          setLoading(false);
        }
      }, 180000);
    } catch (e) {
      toast.error('Erro ao gerar storyboard');
      addChatMsg('agent', 'Erro ao iniciar geração do storyboard.');
      setLoading(false);
    }
  };

  // Step 4: Generate Course
  const handleGenerateCourse = async () => {
    setLoading(true);
    addChatMsg('agent', 'Gerando o curso no Scormfy... Criando slides, elementos e quizzes...');
    try {
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/generate-course`, { method: 'POST' });
      if (!res.ok) throw new Error('Falha na geração');
      const data = await res.json();
      setGeneratedProject(data);
      addChatMsg('agent', `Curso "${data.projectName}" criado com sucesso! ${data.slidesCount} slides e ${data.quizCount} perguntas de quiz. Você pode abrir no editor para ajustes finais ou exportar como SCORM.`);
      setCurrentStep(5);
      toast.success('Curso gerado com sucesso!');
    } catch (e) {
      toast.error('Erro ao gerar curso');
      addChatMsg('agent', 'Erro ao gerar o curso. Tente novamente.');
    } finally {
      setLoading(false);
    }
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
    } catch (e) {
      addChatMsg('agent', 'Erro ao processar sua mensagem.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen flex flex-col bg-slate-950 text-white" data-testid="agent-page">
      {/* Header */}
      <header className="h-14 border-b border-slate-800 flex items-center px-4 gap-3 shrink-0">
        <Button variant="ghost" size="sm" onClick={() => navigate('/')} data-testid="back-to-dashboard">
          <ArrowLeft className="w-4 h-4 mr-1" /> Dashboard
        </Button>
        <div className="w-px h-6 bg-slate-700" />
        <Brain className="w-5 h-5 text-emerald-400" />
        <span className="font-semibold text-sm">Agente de Design Instrucional</span>
        <div className="flex-1" />
        {/* Step indicator */}
        <div className="hidden md:flex items-center gap-1">
          {STEPS.map((step, i) => {
            const Icon = step.icon;
            const active = i === currentStep;
            const done = i < currentStep;
            return (
              <div key={step.id} className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${active ? 'bg-emerald-600/20 text-emerald-400' : done ? 'text-emerald-500/60' : 'text-slate-500'}`}>
                {done ? <Check className="w-3 h-3" /> : <Icon className="w-3 h-3" />}
                <span className="hidden lg:inline">{step.label}</span>
                {i < STEPS.length - 1 && <ChevronRight className="w-3 h-3 text-slate-600 ml-1" />}
              </div>
            );
          })}
        </div>
        <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setShowChat(!showChat)}>
          {showChat ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
        </Button>
      </header>

      {/* Main content */}
      <div className="flex-1 flex min-h-0">
        {/* Left Panel - Visual content */}
        <div className={`flex-1 flex flex-col min-w-0 ${showChat ? 'hidden md:flex' : 'flex'}`}>
          <ScrollArea className="flex-1">
            <div className="p-6 max-w-4xl mx-auto space-y-6">
              {currentStep === 0 && <UploadPanel contentText={contentText} setContentText={setContentText} fileName={fileName} fileInputRef={fileInputRef} handleFileUpload={handleFileUpload} handleTextSubmit={handleTextSubmit} loading={loading} />}
              {currentStep === 1 && <AnalyzePanel analysis={analysis} loading={loading} onAnalyze={handleAnalyze} />}
              {currentStep >= 2 && currentStep < 3 && <ConfigPanel config={config} setConfig={setConfig} analysis={analysis} loading={loading} onGenerate={handleGenerateStructure} />}
              {currentStep === 3 && <StructurePanel structure={structure} loading={loading} onApprove={handleGenerateStoryboard} />}
              {currentStep === 4 && <StoryboardPanel storyboard={storyboard} loading={loading} onApprove={handleGenerateCourse} />}
              {currentStep === 5 && <GeneratedPanel project={generatedProject} navigate={navigate} />}
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

function UploadPanel({ contentText, setContentText, fileName, fileInputRef, handleFileUpload, handleTextSubmit, loading }) {
  return (
    <div className="space-y-6" data-testid="upload-panel">
      <div className="text-center space-y-2">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-emerald-600/10 mb-2">
          <Sparkles className="w-8 h-8 text-emerald-400" />
        </div>
        <h1 className="text-2xl font-bold">Agente de Design Instrucional</h1>
        <p className="text-slate-400 text-sm max-w-lg mx-auto">
          Transforme qualquer conteúdo em um curso profissional. Envie texto, PDF, PPT ou DOC e o agente IA criará um curso completo com estrutura pedagógica, quizzes e multimídia.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {/* File upload */}
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

        {/* Text paste */}
        <Card className="bg-slate-900/50 border-slate-800">
          <CardContent className="p-6 space-y-3">
            <FileText className="w-10 h-10 text-blue-400 mx-auto" />
            <p className="font-medium text-sm text-center">Texto Direto</p>
            <Textarea
              data-testid="content-text-input"
              value={contentText}
              onChange={e => setContentText(e.target.value)}
              placeholder="Cole ou digite o conteúdo aqui..."
              className="bg-slate-800 border-slate-700 text-sm min-h-[120px]"
            />
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

function ConfigPanel({ config, setConfig, analysis, loading, onGenerate }) {
  const update = (k, v) => setConfig(prev => ({ ...prev, [k]: v }));
  return (
    <div className="space-y-4" data-testid="config-panel">
      <h2 className="text-lg font-semibold flex items-center gap-2"><Settings className="w-5 h-5 text-emerald-400" /> Configuração do Curso</h2>
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
        Gerar Estrutura do Curso
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
      {/* Slide navigator */}
      <div className="flex gap-1 flex-wrap">
        {storyboard.slides.map((s, i) => (
          <button key={i} onClick={() => setActiveSlide(i)}
            className={`px-2 py-1 rounded text-xs transition-colors ${i === activeSlide ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}`}>
            {i + 1}
          </button>
        ))}
      </div>
      {/* Slide detail */}
      {slide && (
        <Card className="bg-slate-900/50 border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Badge className={`text-xs ${slide.type === 'quiz' ? 'bg-amber-600/20 text-amber-300' : slide.type === 'title' ? 'bg-blue-600/20 text-blue-300' : 'bg-slate-700 text-slate-300'}`}>{slide.type}</Badge>
              Slide {activeSlide + 1}: {slide.title}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* Preview */}
            <div className="rounded-lg overflow-hidden border border-slate-700" style={{ background: slide.background || '#fff', aspectRatio: '1920/820' }}>
              <div className="p-4 h-full overflow-auto">
                {slide.elements?.map((el, i) => (
                  <div key={i} className="text-sm" dangerouslySetInnerHTML={{ __html: el.content || '' }} style={{ color: slide.type === 'title' ? '#fff' : '#333' }} />
                ))}
              </div>
            </div>
            {/* Narration */}
            {slide.narrationScript && (
              <div className="bg-slate-800/50 rounded p-3">
                <span className="text-xs text-slate-400 block mb-1">Narração:</span>
                <p className="text-sm text-slate-300">{slide.narrationScript}</p>
              </div>
            )}
            {/* Quiz questions */}
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
      {/* Navigation */}
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
