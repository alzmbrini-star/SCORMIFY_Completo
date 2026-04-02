import React, { useState } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../components/ui/select';
import { Badge } from '../../../components/ui/badge';
import { Textarea } from '../../../components/ui/textarea';
import { Input } from '../../../components/ui/input';
import {
  Video, Type, Code, Target, Volume2, Image, Gamepad2, UserCircle,
  Pencil, Check, RotateCcw, Monitor, BarChart3, Lightbulb,
} from 'lucide-react';

const slideTypeOptions = [
  { value: 'avatar_scene', label: 'Cena com Avatar', icon: Video, color: 'violet' },
  { value: 'scenario', label: 'Cenário Interativo', icon: Monitor, color: 'cyan' },
  { value: 'visual_summary', label: 'Resumo Visual', icon: BarChart3, color: 'amber' },
  { value: 'reinforcement', label: 'Reforço', icon: Lightbulb, color: 'rose' },
  { value: 'content', label: 'Conteúdo (Texto)', icon: Type, color: 'slate' },
  { value: 'simulator', label: 'Simulador Interativo', icon: Code, color: 'emerald' },
  { value: 'game', label: 'Jogo Educativo', icon: Gamepad2, color: 'emerald' },
  { value: 'quiz', label: 'Quiz', icon: Target, color: 'amber' },
];

const positionOptions = [
  { value: 'left', label: 'Esquerda' },
  { value: 'right', label: 'Direita' },
  { value: 'center', label: 'Centro' },
];

export function SlideTypeSwitcher({ currentType, onChange, className = '' }) {
  return (
    <div className={`flex items-center gap-2 ${className}`} data-testid="slide-type-switcher">
      <span className="text-[10px] text-slate-400 uppercase tracking-wider shrink-0">Tipo:</span>
      <Select value={currentType} onValueChange={onChange}>
        <SelectTrigger className="h-7 text-xs bg-slate-800/50 border-slate-700 w-48" data-testid="slide-type-select">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {slideTypeOptions.map(opt => {
            const Icon = opt.icon;
            return (
              <SelectItem key={opt.value} value={opt.value} data-testid={`type-option-${opt.value}`}>
                <span className="flex items-center gap-2">
                  <Icon className="w-3 h-3" />
                  {opt.label}
                </span>
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>
    </div>
  );
}

export function AvatarSceneMockup({
  narrationScript,
  backgroundDescription,
  avatarPosition = 'left',
  compact = false,
  editable = false,
  onScriptChange,
  onBackgroundChange,
  onPositionChange,
}) {
  const [editingScript, setEditingScript] = useState(false);
  const [editingBg, setEditingBg] = useState(false);
  const [localScript, setLocalScript] = useState(narrationScript || '');
  const [localBg, setLocalBg] = useState(backgroundDescription || '');

  const charCount = localScript.length;
  const charLimit = 1500;

  const confirmScript = () => {
    if (onScriptChange) onScriptChange(localScript);
    setEditingScript(false);
  };

  const confirmBg = () => {
    if (onBackgroundChange) onBackgroundChange(localBg);
    setEditingBg(false);
  };

  const resetScript = () => {
    setLocalScript(narrationScript || '');
    setEditingScript(false);
  };

  if (compact) {
    return (
      <div className="rounded-md bg-violet-950/30 border border-violet-800/20 p-2 space-y-1.5" data-testid="avatar-scene-mockup">
        <div className="flex items-center gap-1.5">
          <Volume2 className="w-3 h-3 text-violet-400" />
          <span className="text-[10px] font-medium text-violet-300 uppercase tracking-wider">Script de Narração</span>
          <Badge className="text-[8px] px-1 py-0 bg-violet-600/20 text-violet-300 ml-auto">
            {avatarPosition === 'left' ? 'Avatar Esquerda' : avatarPosition === 'right' ? 'Avatar Direita' : 'Avatar Centro'}
          </Badge>
        </div>
        <p className="text-xs text-violet-200/80 line-clamp-3">{narrationScript}</p>
        {backgroundDescription && (
          <div className="flex items-center gap-1.5">
            <Image className="w-3 h-3 text-violet-400" />
            <span className="text-[10px] text-violet-300/60">{backgroundDescription}</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-violet-950/20 border border-violet-800/20 overflow-hidden" data-testid="avatar-scene-mockup">
      {/* Visual Mockup */}
      <div className="relative h-28 bg-gradient-to-br from-slate-900 via-violet-950/40 to-slate-900 border-b border-violet-800/20">
        {/* Avatar placeholder */}
        <div className={`absolute bottom-2 ${avatarPosition === 'right' ? 'right-3' : avatarPosition === 'center' ? 'left-1/2 -translate-x-1/2' : 'left-3'} flex flex-col ${avatarPosition === 'right' ? 'items-end' : avatarPosition === 'center' ? 'items-center' : 'items-start'}`}>
          <div className="w-16 h-16 rounded-lg bg-violet-600/20 border border-violet-500/30 flex items-center justify-center">
            <UserCircle className="w-8 h-8 text-violet-400" />
          </div>
          <span className="text-[8px] text-violet-400 mt-0.5">Avatar</span>
        </div>
        {/* Content placeholder */}
        <div className={`absolute top-3 ${avatarPosition === 'center' ? 'left-3 right-3 top-1' : avatarPosition === 'left' ? 'right-3 w-1/2' : 'left-3 w-1/2'}`}>
          <div className="space-y-1">
            <div className="h-2.5 bg-slate-600/30 rounded w-3/4" />
            <div className="h-1.5 bg-slate-700/30 rounded w-full" />
            <div className="h-1.5 bg-slate-700/30 rounded w-5/6" />
            <div className="h-1.5 bg-slate-700/30 rounded w-2/3" />
          </div>
        </div>
        {/* Position selector */}
        {editable ? (
          <div className="absolute top-1.5 right-1.5">
            <Select value={avatarPosition} onValueChange={onPositionChange}>
              <SelectTrigger className="h-5 text-[9px] bg-violet-600/30 border-violet-500/20 text-violet-300 w-24 px-1.5" data-testid="avatar-position-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {positionOptions.map(p => (
                  <SelectItem key={p.value} value={p.value} className="text-xs">{p.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : (
          <Badge className="absolute top-1.5 right-1.5 text-[8px] px-1.5 py-0 bg-violet-600/30 text-violet-300 border border-violet-500/20">
            {avatarPosition === 'left' ? 'Esquerda' : avatarPosition === 'right' ? 'Direita' : 'Centro'}
          </Badge>
        )}
        {/* Background label / editor */}
        <div className="absolute bottom-1 right-1.5 left-24 flex items-center gap-1">
          {editable && !editingBg ? (
            <button
              onClick={(e) => { e.stopPropagation(); setEditingBg(true); }}
              className="flex items-center gap-1 group"
              data-testid="edit-bg-btn"
            >
              <Image className="w-2.5 h-2.5 text-violet-400/50 group-hover:text-violet-300" />
              <span className="text-[8px] text-violet-400/50 group-hover:text-violet-300 truncate max-w-40">
                {backgroundDescription || 'Clique para definir cenário'}
              </span>
              <Pencil className="w-2 h-2 text-violet-400/30 group-hover:text-violet-300" />
            </button>
          ) : !editingBg ? (
            <>
              <Image className="w-2.5 h-2.5 text-violet-400/50" />
              <span className="text-[8px] text-violet-400/50 max-w-32 truncate">{backgroundDescription}</span>
            </>
          ) : null}
        </div>
      </div>

      {/* Background description editor */}
      {editingBg && (
        <div className="p-2 border-b border-violet-800/20 bg-violet-950/30" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center gap-1.5 mb-1.5">
            <Image className="w-3 h-3 text-violet-400" />
            <span className="text-[10px] font-medium text-violet-300 uppercase tracking-wider">Cenário de Fundo</span>
          </div>
          <Input
            value={localBg}
            onChange={(e) => setLocalBg(e.target.value)}
            placeholder="Ex: Escritório moderno com tela mostrando gráficos"
            className="text-xs bg-violet-950/50 border-violet-800/40 text-violet-200 placeholder:text-violet-400/40 h-7"
            data-testid="bg-description-input"
          />
          <div className="flex gap-1.5 mt-1.5 justify-end">
            <button onClick={() => setEditingBg(false)} className="text-[10px] text-slate-400 hover:text-slate-200 px-2 py-0.5 rounded bg-slate-800/50">
              Cancelar
            </button>
            <button onClick={confirmBg} className="text-[10px] text-violet-200 hover:text-white px-2 py-0.5 rounded bg-violet-600/40 flex items-center gap-1" data-testid="confirm-bg-btn">
              <Check className="w-2.5 h-2.5" /> Salvar
            </button>
          </div>
        </div>
      )}

      {/* Narration script - editable */}
      <div className="p-2.5 space-y-1.5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-1.5">
          <Volume2 className="w-3 h-3 text-violet-400" />
          <span className="text-[10px] font-medium text-violet-300 uppercase tracking-wider">Script de Narração</span>
          {editable && !editingScript && (
            <button
              onClick={() => { setLocalScript(narrationScript || ''); setEditingScript(true); }}
              className="ml-auto flex items-center gap-1 text-[10px] text-violet-400/60 hover:text-violet-300 transition-colors"
              data-testid="edit-script-btn"
            >
              <Pencil className="w-2.5 h-2.5" /> Editar
            </button>
          )}
          {editable && editingScript && (
            <span className={`ml-auto text-[9px] ${charCount > charLimit ? 'text-red-400' : 'text-violet-400/50'}`}>
              {charCount}/{charLimit}
            </span>
          )}
        </div>

        {editingScript ? (
          <div className="space-y-1.5">
            <Textarea
              value={localScript}
              onChange={(e) => setLocalScript(e.target.value)}
              rows={4}
              className="text-xs bg-violet-950/50 border-violet-800/40 text-violet-200 placeholder:text-violet-400/40 resize-none focus:ring-violet-500/30"
              placeholder="Digite o texto que o avatar vai falar..."
              data-testid="narration-script-textarea"
            />
            <div className="flex gap-1.5 justify-end">
              <button
                onClick={resetScript}
                className="text-[10px] text-slate-400 hover:text-slate-200 px-2 py-0.5 rounded bg-slate-800/50 flex items-center gap-1"
                data-testid="reset-script-btn"
              >
                <RotateCcw className="w-2.5 h-2.5" /> Restaurar
              </button>
              <button
                onClick={confirmScript}
                className="text-[10px] text-violet-200 hover:text-white px-2 py-0.5 rounded bg-violet-600/40 flex items-center gap-1"
                data-testid="confirm-script-btn"
              >
                <Check className="w-2.5 h-2.5" /> Salvar
              </button>
            </div>
          </div>
        ) : (
          <p className="text-xs text-violet-200/80 leading-relaxed line-clamp-4">
            {narrationScript || 'Sem script definido'}
          </p>
        )}
      </div>
    </div>
  );
}
