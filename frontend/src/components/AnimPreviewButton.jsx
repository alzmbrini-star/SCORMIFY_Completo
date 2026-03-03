import React, { useState, useEffect, useRef } from 'react';

const ANIM_KEYFRAMES = {
  fadeIn: { from: { opacity: 0 }, to: { opacity: 1 } },
  slideInLeft: { from: { opacity: 0, transform: 'translateX(-12px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
  slideInRight: { from: { opacity: 0, transform: 'translateX(12px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
  slideInUp: { from: { opacity: 0, transform: 'translateY(10px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
  slideInDown: { from: { opacity: 0, transform: 'translateY(-10px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
  zoomIn: { from: { opacity: 0, transform: 'scale(0.4)' }, to: { opacity: 1, transform: 'scale(1)' } },
  typewriter: { from: { clipPath: 'inset(0 100% 0 0)' }, to: { clipPath: 'inset(0 0% 0 0)' } },
  bounce: { from: { opacity: 0, transform: 'translateY(-10px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
};

const EASE = {
  bounce: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
  typewriter: 'steps(8, end)',
  default: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
};

export function AnimPreviewButton({ animId, label, selected, onClick, testId }) {
  const [playing, setPlaying] = useState(false);
  const [style, setStyle] = useState({});
  const timerRef = useRef(null);
  const kf = ANIM_KEYFRAMES[animId];

  const playPreview = () => {
    if (!kf || playing) return;
    setPlaying(true);
    setStyle(kf.from);
    timerRef.current = setTimeout(() => {
      const ease = EASE[animId] || EASE.default;
      const prop = animId === 'typewriter' ? 'clip-path 0.6s ' + ease : 'all 0.5s ' + ease;
      setStyle({ ...kf.to, transition: prop });
    }, 60);
    setTimeout(() => {
      setPlaying(false);
      setStyle({});
    }, 1200);
  };

  useEffect(() => () => clearTimeout(timerRef.current), []);

  return (
    <button
      onClick={onClick}
      onMouseEnter={playPreview}
      className={`relative flex flex-col items-center gap-1 px-2 py-2 rounded-lg border transition-colors ${
        selected
          ? 'border-amber-500 bg-amber-600/10 text-amber-300'
          : 'border-slate-700/50 text-slate-500 hover:border-amber-500/30 hover:text-slate-300'
      }`}
      data-testid={testId}
    >
      {/* Mini preview box */}
      <div className="w-full h-5 rounded bg-slate-800/60 overflow-hidden flex items-center justify-center relative">
        {kf ? (
          <div className="flex flex-col gap-[2px] items-start px-1 w-full" style={style}>
            <div className="h-[3px] w-[70%] rounded-full bg-amber-400/70" />
            <div className="h-[2px] w-[90%] rounded-full bg-slate-500/50" />
            <div className="h-[2px] w-[50%] rounded-full bg-slate-500/50" />
          </div>
        ) : (
          <div className="flex flex-col gap-[2px] items-start px-1 w-full">
            <div className="h-[3px] w-[70%] rounded-full bg-slate-600/50" />
            <div className="h-[2px] w-[90%] rounded-full bg-slate-700/50" />
            <div className="h-[2px] w-[50%] rounded-full bg-slate-700/50" />
          </div>
        )}
      </div>
      <span className="text-[10px] leading-tight">{label}</span>
    </button>
  );
}
