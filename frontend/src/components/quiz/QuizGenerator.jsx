import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Separator } from '../ui/separator';
import { Checkbox } from '../ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../ui/dialog';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import {
  Loader2,
  Sparkles,
  Upload,
  FileText,
  Plus,
  Trash2,
  Check,
  X,
  HelpCircle,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function QuizGenerator({ 
  open, 
  onOpenChange, 
  projectId,
  onQuizCreated 
}) {
  // Tab state
  const [activeTab, setActiveTab] = useState('generate');
  
  // Question bank state
  const [questions, setQuestions] = useState([]);
  const [questionsLoading, setQuestionsLoading] = useState(false);
  const [selectedQuestionIds, setSelectedQuestionIds] = useState([]);
  
  // AI Generation state
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiContext, setAiContext] = useState('');
  const [questionType, setQuestionType] = useState('mixed');
  const [questionCount, setQuestionCount] = useState(5);
  const [generating, setGenerating] = useState(false);
  
  // Document upload state
  const [docFile, setDocFile] = useState(null);
  const [docText, setDocText] = useState('');
  const [docParsing, setDocParsing] = useState(false);
  
  // Manual question creation state
  const [showManualDialog, setShowManualDialog] = useState(false);
  const [manualQuestion, setManualQuestion] = useState({
    type: 'multiple_choice',
    text: '',
    alternatives: [
      { text: '', isCorrect: false },
      { text: '', isCorrect: false },
      { text: '', isCorrect: false },
      { text: '', isCorrect: false },
    ],
    explanation: '',
  });
  
  // Quiz config state
  const [quizConfig, setQuizConfig] = useState({
    title: 'Quiz',
    questionCount: 5,
    shuffleQuestions: true,
    shuffleAlternatives: true,
    showFeedback: true,
    passingScore: 60,
  });

  // Load questions when dialog opens
  useEffect(() => {
    if (open) {
      loadQuestions();
    }
  }, [open, projectId]);

  const loadQuestions = async () => {
    setQuestionsLoading(true);
    try {
      const params = projectId ? { project_id: projectId } : {};
      const response = await axios.get(`${API_URL}/api/questions`, { params });
      setQuestions(response.data);
    } catch (err) {
      console.error('Failed to load questions:', err);
      toast.error('Erro ao carregar questões');
    } finally {
      setQuestionsLoading(false);
    }
  };

  const handleGenerateWithAI = async () => {
    if (!aiPrompt.trim() && !docText.trim()) {
      toast.error('Por favor, insira um tema ou faça upload de um documento');
      return;
    }

    setGenerating(true);
    try {
      const response = await axios.post(`${API_URL}/api/questions/generate`, {
        projectId,
        source: docText ? 'document' : 'prompt',
        prompt: aiPrompt,
        context: aiContext,
        documentContent: docText,
        questionType,
        count: questionCount,
      });

      if (response.data.success) {
        toast.success(`${response.data.count} questões geradas com sucesso!`);
        await loadQuestions();
        // Auto-select the new questions
        const newIds = response.data.questions.map(q => q.id);
        setSelectedQuestionIds(prev => [...prev, ...newIds]);
        setActiveTab('bank');
      }
    } catch (err) {
      console.error('Failed to generate questions:', err);
      toast.error('Erro ao gerar questões. Tente novamente.');
    } finally {
      setGenerating(false);
    }
  };

  const handleDocUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.doc') && !file.name.toLowerCase().endsWith('.docx')) {
      toast.error('Por favor, selecione um arquivo .doc ou .docx');
      return;
    }

    setDocFile(file);
    setDocParsing(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await axios.post(`${API_URL}/api/questions/parse-doc`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      if (response.data.success) {
        setDocText(response.data.text);
        toast.success(`Documento processado: ${response.data.wordCount} palavras extraídas`);
      }
    } catch (err) {
      console.error('Failed to parse document:', err);
      toast.error('Erro ao processar documento');
      setDocFile(null);
    } finally {
      setDocParsing(false);
    }
  };

  const handleToggleQuestion = (questionId) => {
    setSelectedQuestionIds(prev => 
      prev.includes(questionId) 
        ? prev.filter(id => id !== questionId)
        : [...prev, questionId]
    );
  };

  const handleSelectAll = () => {
    if (selectedQuestionIds.length === questions.length) {
      setSelectedQuestionIds([]);
    } else {
      setSelectedQuestionIds(questions.map(q => q.id));
    }
  };

  const handleDeleteQuestion = async (questionId) => {
    try {
      await axios.delete(`${API_URL}/api/questions/${questionId}`);
      toast.success('Questão excluída');
      await loadQuestions();
      setSelectedQuestionIds(prev => prev.filter(id => id !== questionId));
    } catch (err) {
      toast.error('Erro ao excluir questão');
    }
  };

  const handleCreateManualQuestion = async () => {
    if (!manualQuestion.text.trim()) {
      toast.error('Por favor, insira o texto da questão');
      return;
    }

    const hasCorrect = manualQuestion.alternatives.some(a => a.isCorrect);
    if (!hasCorrect) {
      toast.error('Marque pelo menos uma alternativa como correta');
      return;
    }

    const validAlts = manualQuestion.alternatives.filter(a => a.text.trim());
    if (validAlts.length < 2) {
      toast.error('Adicione pelo menos 2 alternativas');
      return;
    }

    try {
      await axios.post(`${API_URL}/api/questions`, {
        projectId,
        type: manualQuestion.type,
        text: manualQuestion.text,
        alternatives: validAlts,
        explanation: manualQuestion.explanation,
        tags: ['manual'],
      });

      toast.success('Questão criada com sucesso!');
      setShowManualDialog(false);
      resetManualQuestion();
      await loadQuestions();
    } catch (err) {
      toast.error('Erro ao criar questão');
    }
  };

  const resetManualQuestion = () => {
    setManualQuestion({
      type: 'multiple_choice',
      text: '',
      alternatives: [
        { text: '', isCorrect: false },
        { text: '', isCorrect: false },
        { text: '', isCorrect: false },
        { text: '', isCorrect: false },
      ],
      explanation: '',
    });
  };

  const handleAddAlternative = () => {
    setManualQuestion(prev => ({
      ...prev,
      alternatives: [...prev.alternatives, { text: '', isCorrect: false }],
    }));
  };

  const handleRemoveAlternative = (index) => {
    setManualQuestion(prev => ({
      ...prev,
      alternatives: prev.alternatives.filter((_, i) => i !== index),
    }));
  };

  const handleUpdateAlternative = (index, field, value) => {
    setManualQuestion(prev => ({
      ...prev,
      alternatives: prev.alternatives.map((alt, i) => {
        if (i === index) {
          if (field === 'isCorrect' && value && prev.type === 'true_false') {
            // For true/false, only one can be correct
            return { ...alt, isCorrect: true };
          }
          return { ...alt, [field]: value };
        }
        if (field === 'isCorrect' && value && prev.type === 'true_false') {
          return { ...alt, isCorrect: false };
        }
        return alt;
      }),
    }));
  };

  const handleCreateQuiz = () => {
    if (selectedQuestionIds.length === 0) {
      toast.error('Selecione pelo menos uma questão para o quiz');
      return;
    }

    // Create quiz element data
    const quizData = {
      type: 'quiz',
      quizConfig: {
        ...quizConfig,
        questionIds: selectedQuestionIds,
        questionCount: Math.min(quizConfig.questionCount, selectedQuestionIds.length),
      },
      // Position in center of slide
      x: 100,
      y: 100,
      width: 1000,
      height: 500,
    };

    onQuizCreated(quizData);
    onOpenChange(false);
    toast.success('Quiz adicionado ao slide!');
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <HelpCircle className="w-5 h-5 text-cyan-500" />
              Gerador de Quiz
            </DialogTitle>
            <DialogDescription>
              Gere questões com IA, faça upload de documentos ou crie manualmente
            </DialogDescription>
          </DialogHeader>

          <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
            <TabsList className="grid grid-cols-3 w-full">
              <TabsTrigger value="generate" className="gap-2">
                <Sparkles className="w-4 h-4" />
                Gerar com IA
              </TabsTrigger>
              <TabsTrigger value="bank" className="gap-2">
                <FileText className="w-4 h-4" />
                Banco ({questions.length})
              </TabsTrigger>
              <TabsTrigger value="config" className="gap-2">
                <CheckCircle className="w-4 h-4" />
                Configurar ({selectedQuestionIds.length})
              </TabsTrigger>
            </TabsList>

            {/* Tab: Generate with AI */}
            <TabsContent value="generate" className="flex-1 overflow-auto p-4 space-y-4">
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Tema / Assunto</Label>
                  <Input
                    placeholder="Ex: Segurança no trabalho, EPIs, primeiros socorros..."
                    value={aiPrompt}
                    onChange={(e) => setAiPrompt(e.target.value)}
                    data-testid="quiz-ai-prompt"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Contexto adicional (opcional)</Label>
                  <Textarea
                    placeholder="Informações adicionais para contextualizar as questões..."
                    value={aiContext}
                    onChange={(e) => setAiContext(e.target.value)}
                    rows={3}
                    data-testid="quiz-ai-context"
                  />
                </div>

                <Separator />

                <div className="space-y-2">
                  <Label>Ou faça upload de um documento .doc/.docx</Label>
                  <div className="flex gap-2">
                    <Input
                      type="file"
                      accept=".doc,.docx"
                      onChange={handleDocUpload}
                      className="flex-1"
                      data-testid="quiz-doc-upload"
                    />
                    {docParsing && <Loader2 className="w-5 h-5 animate-spin" />}
                  </div>
                  {docFile && (
                    <p className="text-sm text-muted-foreground flex items-center gap-1">
                      <FileText className="w-4 h-4" />
                      {docFile.name}
                    </p>
                  )}
                  {docText && (
                    <div className="mt-2 p-3 bg-muted rounded-lg max-h-32 overflow-auto">
                      <p className="text-sm text-muted-foreground">
                        {docText.substring(0, 500)}
                        {docText.length > 500 && '...'}
                      </p>
                    </div>
                  )}
                </div>

                <Separator />

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Tipo de questão</Label>
                    <Select value={questionType} onValueChange={setQuestionType}>
                      <SelectTrigger data-testid="quiz-question-type">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="multiple_choice">Múltipla Escolha</SelectItem>
                        <SelectItem value="true_false">Verdadeiro/Falso</SelectItem>
                        <SelectItem value="mixed">Misto</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>Quantidade de questões</Label>
                    <Select value={String(questionCount)} onValueChange={(v) => setQuestionCount(Number(v))}>
                      <SelectTrigger data-testid="quiz-question-count">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="3">3 questões</SelectItem>
                        <SelectItem value="5">5 questões</SelectItem>
                        <SelectItem value="10">10 questões</SelectItem>
                        <SelectItem value="15">15 questões</SelectItem>
                        <SelectItem value="20">20 questões</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <Button
                  className="w-full gap-2"
                  onClick={handleGenerateWithAI}
                  disabled={generating || (!aiPrompt.trim() && !docText.trim())}
                  data-testid="quiz-generate-btn"
                >
                  {generating ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Gerando questões...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      Gerar Questões com IA
                    </>
                  )}
                </Button>
              </div>
            </TabsContent>

            {/* Tab: Question Bank */}
            <TabsContent value="bank" className="flex-1 flex flex-col min-h-0 p-4 overflow-hidden">
              <div className="flex justify-between items-center mb-4 flex-shrink-0">
                <div className="flex items-center gap-2">
                  <Checkbox
                    checked={questions.length > 0 && selectedQuestionIds.length === questions.length}
                    onCheckedChange={handleSelectAll}
                    data-testid="quiz-select-all"
                  />
                  <span className="text-sm text-muted-foreground">
                    {selectedQuestionIds.length} selecionada(s)
                  </span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => setShowManualDialog(true)}
                  data-testid="quiz-add-manual-btn"
                >
                  <Plus className="w-4 h-4" />
                  Criar Manualmente
                </Button>
              </div>

              <div className="flex-1 overflow-y-auto pr-2" style={{ maxHeight: 'calc(90vh - 280px)' }}>
                {questionsLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-6 h-6 animate-spin" />
                  </div>
                ) : questions.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <HelpCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>Nenhuma questão encontrada</p>
                    <p className="text-sm">Gere questões com IA ou crie manualmente</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {questions.map((question, idx) => (
                      <div
                        key={question.id}
                        className={`p-4 border rounded-lg transition-colors ${
                          selectedQuestionIds.includes(question.id)
                            ? 'border-cyan-500 bg-cyan-500/5'
                            : 'border-border hover:border-muted-foreground'
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <Checkbox
                            checked={selectedQuestionIds.includes(question.id)}
                            onCheckedChange={() => handleToggleQuestion(question.id)}
                            data-testid={`quiz-question-checkbox-${idx}`}
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className={`px-2 py-0.5 text-xs rounded-full ${
                                question.type === 'true_false' 
                                  ? 'bg-purple-500/20 text-purple-400' 
                                  : 'bg-cyan-500/20 text-cyan-400'
                              }`}>
                                {question.type === 'true_false' ? 'V/F' : 'Múltipla'}
                              </span>
                              {question.tags?.includes('ai-generated') && (
                                <span className="px-2 py-0.5 text-xs rounded-full bg-amber-500/20 text-amber-400">
                                  IA
                                </span>
                              )}
                            </div>
                            <p className="font-medium mb-2">{question.text}</p>
                            <div className="grid grid-cols-2 gap-2">
                              {question.alternatives?.map((alt, altIdx) => (
                                <div
                                  key={alt.id || altIdx}
                                  className={`text-sm px-2 py-1 rounded ${
                                    alt.isCorrect
                                      ? 'bg-green-500/20 text-green-400'
                                      : 'bg-muted text-muted-foreground'
                                  }`}
                                >
                                  {alt.isCorrect && <Check className="w-3 h-3 inline mr-1" />}
                                  {alt.text}
                                </div>
                              ))}
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive hover:bg-destructive/10"
                            onClick={() => handleDeleteQuestion(question.id)}
                            data-testid={`quiz-delete-question-${idx}`}
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </TabsContent>

            {/* Tab: Quiz Config */}
            <TabsContent value="config" className="flex-1 overflow-auto p-4 space-y-4">
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Título do Quiz</Label>
                  <Input
                    value={quizConfig.title}
                    onChange={(e) => setQuizConfig(prev => ({ ...prev, title: e.target.value }))}
                    placeholder="Quiz de Avaliação"
                    data-testid="quiz-config-title"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Número de questões a exibir</Label>
                  <Select
                    value={String(quizConfig.questionCount)}
                    onValueChange={(v) => setQuizConfig(prev => ({ ...prev, questionCount: Number(v) }))}
                  >
                    <SelectTrigger data-testid="quiz-config-count">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[1, 2, 3, 5, 10, 15, 20, 30, 50].map(n => (
                        <SelectItem key={n} value={String(n)}>
                          {n} {n === 1 ? 'questão' : 'questões'}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    {selectedQuestionIds.length} questões selecionadas no banco
                  </p>
                </div>

                <Separator />

                <div className="space-y-3">
                  <Label>Opções</Label>
                  
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="shuffle-questions"
                      checked={quizConfig.shuffleQuestions}
                      onCheckedChange={(checked) => 
                        setQuizConfig(prev => ({ ...prev, shuffleQuestions: checked }))
                      }
                      data-testid="quiz-config-shuffle-questions"
                    />
                    <label htmlFor="shuffle-questions" className="text-sm cursor-pointer">
                      Embaralhar ordem das questões
                    </label>
                  </div>

                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="shuffle-alternatives"
                      checked={quizConfig.shuffleAlternatives}
                      onCheckedChange={(checked) => 
                        setQuizConfig(prev => ({ ...prev, shuffleAlternatives: checked }))
                      }
                      data-testid="quiz-config-shuffle-alternatives"
                    />
                    <label htmlFor="shuffle-alternatives" className="text-sm cursor-pointer">
                      Embaralhar alternativas
                    </label>
                  </div>

                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="show-feedback"
                      checked={quizConfig.showFeedback}
                      onCheckedChange={(checked) => 
                        setQuizConfig(prev => ({ ...prev, showFeedback: checked }))
                      }
                      data-testid="quiz-config-show-feedback"
                    />
                    <label htmlFor="show-feedback" className="text-sm cursor-pointer">
                      Mostrar feedback (certo/errado) após cada resposta
                    </label>
                  </div>
                </div>

                <Separator />

                <div className="space-y-2">
                  <Label>Nota mínima para aprovação (%)</Label>
                  <Select
                    value={String(quizConfig.passingScore)}
                    onValueChange={(v) => setQuizConfig(prev => ({ ...prev, passingScore: Number(v) }))}
                  >
                    <SelectTrigger data-testid="quiz-config-passing-score">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="50">50%</SelectItem>
                      <SelectItem value="60">60%</SelectItem>
                      <SelectItem value="70">70%</SelectItem>
                      <SelectItem value="80">80%</SelectItem>
                      <SelectItem value="90">90%</SelectItem>
                      <SelectItem value="100">100%</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {selectedQuestionIds.length > 0 && (
                  <div className="p-4 bg-cyan-500/10 border border-cyan-500/30 rounded-lg">
                    <p className="text-sm text-cyan-400 font-medium mb-2">
                      Resumo do Quiz
                    </p>
                    <ul className="text-sm text-muted-foreground space-y-1">
                      <li>• {selectedQuestionIds.length} questões no banco</li>
                      <li>• {Math.min(quizConfig.questionCount, selectedQuestionIds.length)} questões serão exibidas</li>
                      <li>• Nota mínima: {quizConfig.passingScore}% ({(quizConfig.passingScore / 10).toFixed(1)} de 10)</li>
                    </ul>
                  </div>
                )}
              </div>
            </TabsContent>
          </Tabs>

          <DialogFooter className="pt-4 border-t">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button
              onClick={handleCreateQuiz}
              disabled={selectedQuestionIds.length === 0}
              className="gap-2"
              data-testid="quiz-create-btn"
            >
              <CheckCircle className="w-4 h-4" />
              Adicionar Quiz ao Slide
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Manual Question Dialog */}
      <Dialog open={showManualDialog} onOpenChange={setShowManualDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Criar Questão Manualmente</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Tipo de questão</Label>
              <Select
                value={manualQuestion.type}
                onValueChange={(v) => {
                  setManualQuestion(prev => ({
                    ...prev,
                    type: v,
                    alternatives: v === 'true_false'
                      ? [{ text: 'Verdadeiro', isCorrect: false }, { text: 'Falso', isCorrect: false }]
                      : [{ text: '', isCorrect: false }, { text: '', isCorrect: false }, { text: '', isCorrect: false }, { text: '', isCorrect: false }],
                  }));
                }}
              >
                <SelectTrigger data-testid="manual-question-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="multiple_choice">Múltipla Escolha</SelectItem>
                  <SelectItem value="true_false">Verdadeiro/Falso</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Pergunta</Label>
              <Textarea
                value={manualQuestion.text}
                onChange={(e) => setManualQuestion(prev => ({ ...prev, text: e.target.value }))}
                placeholder="Digite a pergunta..."
                rows={3}
                data-testid="manual-question-text"
              />
            </div>

            <div className="space-y-2">
              <Label>Alternativas</Label>
              <div className="space-y-2">
                {manualQuestion.alternatives.map((alt, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <Checkbox
                      checked={alt.isCorrect}
                      onCheckedChange={(checked) => handleUpdateAlternative(idx, 'isCorrect', checked)}
                      data-testid={`manual-alt-correct-${idx}`}
                    />
                    <Input
                      value={alt.text}
                      onChange={(e) => handleUpdateAlternative(idx, 'text', e.target.value)}
                      placeholder={manualQuestion.type === 'true_false' ? alt.text : `Alternativa ${idx + 1}`}
                      disabled={manualQuestion.type === 'true_false'}
                      className="flex-1"
                      data-testid={`manual-alt-text-${idx}`}
                    />
                    {manualQuestion.type !== 'true_false' && manualQuestion.alternatives.length > 2 && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleRemoveAlternative(idx)}
                        className="h-8 w-8 text-destructive"
                      >
                        <X className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
              {manualQuestion.type !== 'true_false' && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleAddAlternative}
                  className="mt-2 gap-1"
                >
                  <Plus className="w-4 h-4" />
                  Adicionar alternativa
                </Button>
              )}
            </div>

            <div className="space-y-2">
              <Label>Explicação (opcional)</Label>
              <Textarea
                value={manualQuestion.explanation}
                onChange={(e) => setManualQuestion(prev => ({ ...prev, explanation: e.target.value }))}
                placeholder="Explicação que será mostrada após a resposta..."
                rows={2}
                data-testid="manual-question-explanation"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowManualDialog(false); resetManualQuestion(); }}>
              Cancelar
            </Button>
            <Button onClick={handleCreateManualQuestion} data-testid="manual-question-save-btn">
              Salvar Questão
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
