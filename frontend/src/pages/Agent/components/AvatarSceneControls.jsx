import React from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../components/ui/select';
import { Badge } from '../../../components/ui/badge';
import {
  Video, Type, Code, Target, Volume2, Image, Gamepad2, UserCircle,
} from 'lucide-react';

const slideTypeOptions = [
  { value: 'avatar_scene', label: 'Cena com Avatar', icon: Video, color: 'violet' },
  { value: 'content', label: 'Conteúdo (Texto)', icon: Type, color: 'slate' },
  { value: 'simulator', label: 'Simulador Interativo', icon: Code, color: 'cyan' },
  { value: 'game', label: 'Jogo Educativo', icon: Gamepad2, color: 'emerald' },
  { value: 'quiz', label: 'Quiz', icon: Target, color: 'amber' },
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

export function AvatarSceneMockup({ narrationScript, backgroundDescription, avatarPosition = 'left', compact = false }) {
  const positions = {
    left: { avatar: 'left-3', content: 'right-3', avatarAlign: 'items-start', contentAlign: 'items-end' },
    right: { avatar: 'right-3', content: 'left-3', avatarAlign: 'items-end', contentAlign: 'items-start' },
    center: { avatar: 'left-1/2 -translate-x-1/2', content: 'left-1/2 -translate-x-1/2 top-2', avatarAlign: 'items-center', contentAlign: 'items-center' },
  };
  const pos = positions[avatarPosition] || positions.left;

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
        <div className={`absolute bottom-2 ${pos.avatar} flex flex-col ${pos.avatarAlign}`}>
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
        {/* Position label */}
        <Badge className="absolute top-1.5 right-1.5 text-[8px] px-1.5 py-0 bg-violet-600/30 text-violet-300 border border-violet-500/20">
          {avatarPosition === 'left' ? 'Esquerda' : avatarPosition === 'right' ? 'Direita' : 'Centro'}
        </Badge>
        {/* Background label */}
        {backgroundDescription && (
          <div className="absolute bottom-1 right-1.5 flex items-center gap-1">
            <Image className="w-2.5 h-2.5 text-violet-400/50" />
            <span className="text-[8px] text-violet-400/50 max-w-32 truncate">{backgroundDescription}</span>
          </div>
        )}
      </div>
      {/* Narration script */}
      <div className="p-2.5 space-y-1">
        <div className="flex items-center gap-1.5">
          <Volume2 className="w-3 h-3 text-violet-400" />
          <span className="text-[10px] font-medium text-violet-300 uppercase tracking-wider">Script de Narração</span>
        </div>
        <p className="text-xs text-violet-200/80 leading-relaxed line-clamp-4">{narrationScript || 'Sem script definido'}</p>
      </div>
    </div>
  );
}
