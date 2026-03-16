import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { Loader2, Sparkles, GitBranch, Users, Target, Building2 } from 'lucide-react';
import { getApiUrl } from '../../utils/apiUrl';

const API_URL = getApiUrl();

export default function ScenarioCreator({ open, onOpenChange, projectId, onScenarioCreated }) {
  const [generating, setGenerating] = useState(false);
  const [form, setForm] = useState({
    theme: '',
    objectives: '',
    audience: '',
    complexity: 'intermediate',
    industry: '',
    duration_minutes: 15,
  });

  const handleGenerate = async () => {
    if (!form.theme.trim()) {
      toast.error('Informe o tema do cenário');
      return;
    }
    if (!form.objectives.trim()) {
      toast.error('Informe os objetivos de aprendizagem');
      return;
    }

    setGenerating(true);
    try {
      // Step 1: Start async generation
      const startRes = await axios.post(`${API_URL}/api/scenarios/generate`, {
        project_id: projectId,
        theme: form.theme,
        objectives: form.objectives,
        audience: form.audience,
        complexity: form.complexity,
        industry: form.industry,
        duration_minutes: form.duration_minutes,
        language: 'pt-BR',
      });

      const taskId = startRes.data.task_id;
      if (!taskId) throw new Error('Falha ao iniciar geração');

      // Step 2: Poll for completion
      let attempts = 0;
      const maxAttempts = 60; // 60 * 2s = 120s max
      while (attempts < maxAttempts) {
        await new Promise(r => setTimeout(r, 2000));
        attempts++;

        try {
          const pollRes = await axios.get(`${API_URL}/api/scenarios/task/${taskId}`);
          const { status, scenario, error } = pollRes.data;

          if (status === 'completed' && scenario) {
            toast.success(`Cenário "${scenario.title}" gerado com ${scenario.nodes?.length || 0} cenas!`);
            onScenarioCreated(scenario);
            onOpenChange(false);
            setForm({ theme: '', objectives: '', audience: '', complexity: 'intermediate', industry: '', duration_minutes: 15 });
            return;
          } else if (status === 'failed') {
            throw new Error(error || 'Falha na geração do cenário');
          }
          // status === 'processing' -> continue polling
        } catch (pollErr) {
          if (pollErr.response?.status === 404) {
            throw new Error('Tarefa de geração não encontrada');
          }
          // Network error during poll -> retry
        }
      }

      throw new Error('Tempo limite excedido. Tente novamente.');
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      toast.error(`Erro na geração: ${msg}`);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto bg-slate-900 border-slate-700 text-slate-100">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg font-semibold">
            <GitBranch className="w-5 h-5 text-cyan-400" />
            Criador de Cenários de Aprendizagem
          </DialogTitle>
          <p className="text-sm text-slate-400 mt-1">
            Gere cenários interativos com IA para simulações de tomada de decisão
          </p>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Theme */}
          <div className="space-y-1.5">
            <Label className="flex items-center gap-1.5 text-sm font-medium text-slate-300">
              <Target className="w-3.5 h-3.5 text-cyan-400" />
              Tema do Cenário *
            </Label>
            <Input
              data-testid="scenario-theme-input"
              placeholder="Ex: Gestão de conflitos em equipes multiculturais"
              value={form.theme}
              onChange={(e) => setForm({ ...form, theme: e.target.value })}
              className="bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500"
            />
          </div>

          {/* Objectives */}
          <div className="space-y-1.5">
            <Label className="flex items-center gap-1.5 text-sm font-medium text-slate-300">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              Objetivos de Aprendizagem *
            </Label>
            <Textarea
              data-testid="scenario-objectives-input"
              placeholder="Ex: Desenvolver habilidades de mediação, identificar vieses culturais, praticar comunicação assertiva"
              value={form.objectives}
              onChange={(e) => setForm({ ...form, objectives: e.target.value })}
              className="bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500 min-h-[80px]"
            />
          </div>

          {/* Audience */}
          <div className="space-y-1.5">
            <Label className="flex items-center gap-1.5 text-sm font-medium text-slate-300">
              <Users className="w-3.5 h-3.5 text-green-400" />
              Público-Alvo
            </Label>
            <Input
              data-testid="scenario-audience-input"
              placeholder="Ex: Gestores de nível médio com 3-5 anos de experiência"
              value={form.audience}
              onChange={(e) => setForm({ ...form, audience: e.target.value })}
              className="bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500"
            />
          </div>

          {/* Industry */}
          <div className="space-y-1.5">
            <Label className="flex items-center gap-1.5 text-sm font-medium text-slate-300">
              <Building2 className="w-3.5 h-3.5 text-purple-400" />
              Setor / Indústria
            </Label>
            <Input
              data-testid="scenario-industry-input"
              placeholder="Ex: Tecnologia, Saúde, Finanças, Educação"
              value={form.industry}
              onChange={(e) => setForm({ ...form, industry: e.target.value })}
              className="bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Complexity */}
            <div className="space-y-1.5">
              <Label className="text-sm font-medium text-slate-300">Complexidade</Label>
              <Select
                value={form.complexity}
                onValueChange={(val) => setForm({ ...form, complexity: val })}
              >
                <SelectTrigger className="bg-slate-800 border-slate-600 text-slate-100" data-testid="scenario-complexity-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-slate-800 border-slate-600">
                  <SelectItem value="beginner" className="text-slate-100">Iniciante (3-4 decisões)</SelectItem>
                  <SelectItem value="intermediate" className="text-slate-100">Intermediário (5-7 decisões)</SelectItem>
                  <SelectItem value="advanced" className="text-slate-100">Avançado (8-12 decisões)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Duration */}
            <div className="space-y-1.5">
              <Label className="text-sm font-medium text-slate-300">Duração (min)</Label>
              <Select
                value={String(form.duration_minutes)}
                onValueChange={(val) => setForm({ ...form, duration_minutes: parseInt(val) })}
              >
                <SelectTrigger className="bg-slate-800 border-slate-600 text-slate-100" data-testid="scenario-duration-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-slate-800 border-slate-600">
                  <SelectItem value="5" className="text-slate-100">5 min</SelectItem>
                  <SelectItem value="10" className="text-slate-100">10 min</SelectItem>
                  <SelectItem value="15" className="text-slate-100">15 min</SelectItem>
                  <SelectItem value="20" className="text-slate-100">20 min</SelectItem>
                  <SelectItem value="30" className="text-slate-100">30 min</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={generating}
            className="text-slate-400 hover:text-slate-100"
            data-testid="scenario-cancel-btn"
          >
            Cancelar
          </Button>
          <Button
            onClick={handleGenerate}
            disabled={generating || !form.theme.trim() || !form.objectives.trim()}
            className="bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white"
            data-testid="scenario-generate-btn"
          >
            {generating ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Gerando cenário...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-2" />
                Gerar com IA
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
