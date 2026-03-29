/**
 * GamificationPanel - Configure badges and feedback for courses
 */
import React, { useState, useEffect } from 'react';
import { 
  Trophy, Award, Star, Target, Brain, Lightbulb, Rocket, 
  CheckCircle, Shield, Heart, ThumbsUp, Smile, Flame, Zap,
  Plus, Trash2, Upload, Save, RefreshCw, Crown, Medal, Puzzle, Badge as BadgeIcon
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Switch } from '../../components/ui/switch';
import { toast } from 'sonner';
import { getApiUrl } from '../../utils/apiUrl';

const API = getApiUrl();

// Icon mapping
const ICONS = {
  trophy: Trophy,
  award: Award,
  star: Star,
  medal: Medal,
  crown: Crown,
  target: Target,
  brain: Brain,
  lightbulb: Lightbulb,
  puzzle: Puzzle,
  rocket: Rocket,
  flame: Flame,
  zap: Zap,
  'check-circle': CheckCircle,
  badge: BadgeIcon,
  shield: Shield,
  heart: Heart,
  'thumbs-up': ThumbsUp,
  smile: Smile,
};

const CRITERIA_TYPES = [
  { value: 'quiz_score', label: 'Pontuação do Quiz' },
  { value: 'scenario_score', label: 'Pontuação do Cenário' },
  { value: 'course_completion', label: 'Conclusão do Curso' },
];

const OPERATORS = [
  { value: 'gte', label: '>= (maior ou igual)' },
  { value: 'gt', label: '> (maior que)' },
  { value: 'eq', label: '= (igual a)' },
  { value: 'lte', label: '<= (menor ou igual)' },
  { value: 'lt', label: '< (menor que)' },
];

export default function GamificationPanel({ projectId, onClose }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState({
    enabled: true,
    showBadgesAfterQuiz: true,
    showBadgesAfterScenario: true,
    showFinalSummary: true,
    badges: [],
    quizFeedbackRanges: [],
    scenarioFeedbackRanges: [],
    completionFeedback: null,
  });
  const [activeTab, setActiveTab] = useState('badges');
  const [showAddBadge, setShowAddBadge] = useState(false);
  const [newBadge, setNewBadge] = useState({
    name: '',
    description: '',
    icon: 'award',
    iconColor: '#fbbf24',
    customImage: null,
    criteria: { type: 'quiz_score', threshold: 80, operator: 'gte' }
  });
  const [uploadingImage, setUploadingImage] = useState(false);

  useEffect(() => {
    loadConfig();
  }, [projectId]);

  const loadConfig = async () => {
    try {
      const res = await fetch(`${API}/api/projects/${projectId}/gamification`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setConfig(data);
      }
    } catch (error) {
      console.error('Error loading gamification config:', error);
      toast.error('Erro ao carregar configurações');
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/projects/${projectId}/gamification`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(config),
      });
      if (res.ok) {
        toast.success('Configurações salvas!');
      } else {
        toast.error('Erro ao salvar');
      }
    } catch (error) {
      toast.error('Erro ao salvar configurações');
    } finally {
      setSaving(false);
    }
  };

  const resetToDefaults = async () => {
    try {
      const res = await fetch(`${API}/api/gamification/defaults`, { credentials: 'include' });
      if (res.ok) {
        const defaults = await res.json();
        setConfig(prev => ({
          ...prev,
          badges: defaults.badges,
          quizFeedbackRanges: defaults.quizFeedbackRanges,
          scenarioFeedbackRanges: defaults.scenarioFeedbackRanges,
        }));
        toast.success('Configurações restauradas para o padrão');
      }
    } catch (error) {
      toast.error('Erro ao restaurar padrões');
    }
  };

  const handleBadgeImageUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      toast.error('Arquivo deve ser uma imagem');
      return;
    }
    if (file.size > 500 * 1024) {
      toast.error('Imagem muito grande (máximo 500KB)');
      return;
    }
    setUploadingImage(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API}/api/gamification/upload-badge-image`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        setNewBadge(prev => ({ ...prev, customImage: data.imageUrl }));
        toast.success('Imagem carregada!');
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || 'Erro ao carregar imagem');
      }
    } catch (error) {
      toast.error('Erro ao carregar imagem');
    } finally {
      setUploadingImage(false);
    }
  };

  const addBadge = () => {
    if (!newBadge.name.trim()) {
      toast.error('Nome do badge é obrigatório');
      return;
    }
    const badge = {
      ...newBadge,
      id: `badge_custom_${Date.now()}`,
      isDefault: false,
      createdAt: new Date().toISOString(),
    };
    setConfig(prev => ({
      ...prev,
      badges: [...prev.badges, badge],
    }));
    setNewBadge({
      name: '',
      description: '',
      icon: 'award',
      iconColor: '#fbbf24',
      customImage: null,
      criteria: { type: 'quiz_score', threshold: 80, operator: 'gte' }
    });
    setShowAddBadge(false);
    toast.success('Badge adicionado!');
  };

  const removeBadge = (badgeId) => {
    const badge = config.badges.find(b => b.id === badgeId);
    if (badge?.isDefault) {
      toast.error('Badges padrão não podem ser removidos');
      return;
    }
    setConfig(prev => ({
      ...prev,
      badges: prev.badges.filter(b => b.id !== badgeId),
    }));
    toast.success('Badge removido');
  };

  const updateFeedbackRange = (type, index, field, value) => {
    const key = type === 'quiz' ? 'quizFeedbackRanges' : 'scenarioFeedbackRanges';
    setConfig(prev => ({
      ...prev,
      [key]: prev[key].map((r, i) => i === index ? { ...r, [field]: value } : r),
    }));
  };

  const IconComponent = ({ icon, color, size = 24 }) => {
    const Icon = ICONS[icon] || Award;
    return <Icon size={size} style={{ color }} />;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
      </div>
    );
  }

  return (
    <div className="bg-slate-800 rounded-lg p-6 max-h-[80vh] overflow-y-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Trophy className="w-6 h-6 text-yellow-500" />
          Gamificação
        </h2>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={resetToDefaults} className="gap-1">
            <RefreshCw className="w-4 h-4" /> Restaurar Padrões
          </Button>
          <Button onClick={saveConfig} disabled={saving} className="gap-1 bg-indigo-600 hover:bg-indigo-700">
            <Save className="w-4 h-4" /> {saving ? 'Salvando...' : 'Salvar'}
          </Button>
        </div>
      </div>

      {/* Main Toggle */}
      <div className="flex items-center justify-between p-4 bg-slate-700/50 rounded-lg mb-6">
        <div>
          <h3 className="text-white font-medium">Ativar Gamificação</h3>
          <p className="text-sm text-slate-400">Habilita badges e feedbacks nos cursos exportados</p>
        </div>
        <Switch
          checked={config.enabled}
          onCheckedChange={(checked) => setConfig(prev => ({ ...prev, enabled: checked }))}
        />
      </div>

      {/* Options */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <label className="flex items-center gap-2 p-3 bg-slate-700/30 rounded-lg cursor-pointer">
          <Switch
            checked={config.showBadgesAfterQuiz}
            onCheckedChange={(checked) => setConfig(prev => ({ ...prev, showBadgesAfterQuiz: checked }))}
          />
          <span className="text-sm text-slate-300">Mostrar após Quiz</span>
        </label>
        <label className="flex items-center gap-2 p-3 bg-slate-700/30 rounded-lg cursor-pointer">
          <Switch
            checked={config.showBadgesAfterScenario}
            onCheckedChange={(checked) => setConfig(prev => ({ ...prev, showBadgesAfterScenario: checked }))}
          />
          <span className="text-sm text-slate-300">Mostrar após Cenário</span>
        </label>
        <label className="flex items-center gap-2 p-3 bg-slate-700/30 rounded-lg cursor-pointer">
          <Switch
            checked={config.showFinalSummary}
            onCheckedChange={(checked) => setConfig(prev => ({ ...prev, showFinalSummary: checked }))}
          />
          <span className="text-sm text-slate-300">Resumo Final</span>
        </label>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-4 border-b border-slate-700">
        {['badges', 'quiz-feedback', 'scenario-feedback'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab 
                ? 'text-indigo-400 border-b-2 border-indigo-400' 
                : 'text-slate-400 hover:text-white'
            }`}
          >
            {tab === 'badges' ? 'Badges' : tab === 'quiz-feedback' ? 'Feedback Quiz' : 'Feedback Cenário'}
          </button>
        ))}
      </div>

      {/* Badges Tab */}
      {activeTab === 'badges' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <p className="text-sm text-slate-400">Configure os badges que os alunos podem conquistar</p>
            <Button size="sm" onClick={() => setShowAddBadge(true)} className="gap-1">
              <Plus className="w-4 h-4" /> Adicionar Badge
            </Button>
          </div>

          {/* Add Badge Form */}
          {showAddBadge && (
            <div className="p-4 bg-slate-700/50 rounded-lg space-y-4">
              <h4 className="text-white font-medium">Novo Badge</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Nome</label>
                  <Input
                    value={newBadge.name}
                    onChange={(e) => setNewBadge(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="Ex: Expert em Vendas"
                  />
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Descrição</label>
                  <Input
                    value={newBadge.description}
                    onChange={(e) => setNewBadge(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Ex: Acertou todas as questões de vendas"
                  />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Ícone</label>
                  <select
                    value={newBadge.icon}
                    onChange={(e) => setNewBadge(prev => ({ ...prev, icon: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white"
                  >
                    {Object.keys(ICONS).map(icon => (
                      <option key={icon} value={icon}>{icon}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Cor</label>
                  <input
                    type="color"
                    value={newBadge.iconColor}
                    onChange={(e) => setNewBadge(prev => ({ ...prev, iconColor: e.target.value }))}
                    className="w-full h-10 rounded-md cursor-pointer"
                  />
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Preview</label>
                  <div className="flex items-center justify-center h-10 bg-slate-800 rounded-md">
                    <IconComponent icon={newBadge.icon} color={newBadge.iconColor} size={28} />
                  </div>
                </div>
              </div>
              {/* Custom Image Upload */}
              <div className="space-y-2">
                <label className="block text-sm text-slate-400">Imagem Personalizada (opcional)</label>
                <div className="flex items-center gap-3">
                  {newBadge.customImage ? (
                    <div className="relative w-16 h-16 rounded-lg overflow-hidden border border-slate-600 bg-slate-800 shrink-0">
                      <img src={newBadge.customImage} alt="Badge" className="w-full h-full object-cover" />
                      <button
                        onClick={() => setNewBadge(prev => ({ ...prev, customImage: null }))}
                        className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center text-white text-xs"
                        data-testid="remove-badge-image-btn"
                      >
                        &times;
                      </button>
                    </div>
                  ) : (
                    <div className="w-16 h-16 rounded-lg border-2 border-dashed border-slate-600 flex items-center justify-center bg-slate-800/50 shrink-0">
                      <IconComponent icon={newBadge.icon} color={newBadge.iconColor} size={28} />
                    </div>
                  )}
                  <div className="flex-1">
                    <label className="cursor-pointer">
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleBadgeImageUpload}
                        className="hidden"
                        data-testid="badge-image-upload-input"
                      />
                      <div className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-md text-sm text-white transition-colors">
                        {uploadingImage ? (
                          <><RefreshCw className="w-4 h-4 animate-spin" /> Carregando...</>
                        ) : (
                          <><Upload className="w-4 h-4" /> Enviar Imagem</>
                        )}
                      </div>
                    </label>
                    <p className="text-[10px] text-slate-500 mt-1">PNG, JPG ou SVG (máx 500KB). Substitui o ícone padrão.</p>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Critério</label>
                  <select
                    value={newBadge.criteria.type}
                    onChange={(e) => setNewBadge(prev => ({ 
                      ...prev, 
                      criteria: { ...prev.criteria, type: e.target.value } 
                    }))}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white"
                  >
                    {CRITERIA_TYPES.map(c => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Operador</label>
                  <select
                    value={newBadge.criteria.operator}
                    onChange={(e) => setNewBadge(prev => ({ 
                      ...prev, 
                      criteria: { ...prev.criteria, operator: e.target.value } 
                    }))}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white"
                  >
                    {OPERATORS.map(o => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Valor (%)</label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={newBadge.criteria.threshold}
                    onChange={(e) => setNewBadge(prev => ({ 
                      ...prev, 
                      criteria: { ...prev.criteria, threshold: parseInt(e.target.value) || 0 } 
                    }))}
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowAddBadge(false)}>Cancelar</Button>
                <Button onClick={addBadge}>Adicionar</Button>
              </div>
            </div>
          )}

          {/* Badges List */}
          <div className="grid grid-cols-2 gap-4">
            {config.badges.map(badge => (
              <div key={badge.id} className="p-4 bg-slate-700/30 rounded-lg flex items-start gap-3">
                <div className="p-2 bg-slate-800 rounded-lg">
                  {badge.customImage ? (
                    <img src={badge.customImage} alt={badge.name} className="w-8 h-8 object-contain" />
                  ) : (
                    <IconComponent icon={badge.icon} color={badge.iconColor} size={32} />
                  )}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h4 className="text-white font-medium">{badge.name}</h4>
                    {badge.isDefault && (
                      <span className="text-xs px-2 py-0.5 bg-indigo-600/30 text-indigo-300 rounded">Padrão</span>
                    )}
                  </div>
                  <p className="text-sm text-slate-400">{badge.description}</p>
                  <p className="text-xs text-slate-500 mt-1">
                    {CRITERIA_TYPES.find(c => c.value === badge.criteria?.type)?.label} 
                    {' '}{OPERATORS.find(o => o.value === badge.criteria?.operator)?.label} 
                    {' '}{badge.criteria?.threshold}%
                  </p>
                </div>
                {!badge.isDefault && (
                  <button 
                    onClick={() => removeBadge(badge.id)}
                    className="p-1 text-slate-500 hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quiz Feedback Tab */}
      {activeTab === 'quiz-feedback' && (
        <div className="space-y-4">
          <p className="text-sm text-slate-400">Configure mensagens de feedback por faixa de pontuação nos quizzes</p>
          {config.quizFeedbackRanges.map((range, index) => (
            <div key={range.id || index} className="p-4 bg-slate-700/30 rounded-lg space-y-3">
              <div className="grid grid-cols-4 gap-3">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">De (%)</label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={range.minScore}
                    onChange={(e) => updateFeedbackRange('quiz', index, 'minScore', parseInt(e.target.value) || 0)}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Até (%)</label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={range.maxScore}
                    onChange={(e) => updateFeedbackRange('quiz', index, 'maxScore', parseInt(e.target.value) || 0)}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Título</label>
                  <Input
                    value={range.title}
                    onChange={(e) => updateFeedbackRange('quiz', index, 'title', e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Emoji</label>
                  <Input
                    value={range.emoji}
                    onChange={(e) => updateFeedbackRange('quiz', index, 'emoji', e.target.value)}
                    className="text-center text-2xl"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Mensagem</label>
                <Input
                  value={range.message}
                  onChange={(e) => updateFeedbackRange('quiz', index, 'message', e.target.value)}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Scenario Feedback Tab */}
      {activeTab === 'scenario-feedback' && (
        <div className="space-y-4">
          <p className="text-sm text-slate-400">Configure mensagens de feedback por faixa de pontuação nos cenários</p>
          {config.scenarioFeedbackRanges.map((range, index) => (
            <div key={range.id || index} className="p-4 bg-slate-700/30 rounded-lg space-y-3">
              <div className="grid grid-cols-4 gap-3">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">De (%)</label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={range.minScore}
                    onChange={(e) => updateFeedbackRange('scenario', index, 'minScore', parseInt(e.target.value) || 0)}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Até (%)</label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={range.maxScore}
                    onChange={(e) => updateFeedbackRange('scenario', index, 'maxScore', parseInt(e.target.value) || 0)}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Título</label>
                  <Input
                    value={range.title}
                    onChange={(e) => updateFeedbackRange('scenario', index, 'title', e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Emoji</label>
                  <Input
                    value={range.emoji}
                    onChange={(e) => updateFeedbackRange('scenario', index, 'emoji', e.target.value)}
                    className="text-center text-2xl"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Mensagem</label>
                <Input
                  value={range.message}
                  onChange={(e) => updateFeedbackRange('scenario', index, 'message', e.target.value)}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
