// Animation types and CSS keyframes for slide elements
export const ANIMATION_TYPES = [
  { id: 'fadeIn', label: 'Fade In', icon: 'eye', category: 'entrance', description: 'Aparece suavemente' },
  { id: 'slideInLeft', label: 'Slide Esquerda', icon: 'arrow-right', category: 'entrance', description: 'Entra pela esquerda' },
  { id: 'slideInRight', label: 'Slide Direita', icon: 'arrow-left', category: 'entrance', description: 'Entra pela direita' },
  { id: 'slideInUp', label: 'Slide Baixo', icon: 'arrow-up', category: 'entrance', description: 'Entra por baixo' },
  { id: 'slideInDown', label: 'Slide Cima', icon: 'arrow-down', category: 'entrance', description: 'Entra por cima' },
  { id: 'zoomIn', label: 'Zoom In', icon: 'zoom-in', category: 'entrance', description: 'Cresce do centro' },
  { id: 'typewriter', label: 'Typewriter', icon: 'type', category: 'entrance', description: 'Texto digitando' },
  { id: 'bounce', label: 'Bounce', icon: 'chevrons-down', category: 'entrance', description: 'Entra com quique' },
];

export const ANIMATION_DURATIONS = [
  { value: 0.3, label: 'Rápida' },
  { value: 0.5, label: 'Normal' },
  { value: 0.8, label: 'Lenta' },
  { value: 1.2, label: 'Muito lenta' },
];

// Get initial CSS state for an animation (before it plays)
export function getAnimationInitialStyle(animType) {
  switch (animType) {
    case 'fadeIn': return { opacity: 0 };
    case 'slideInLeft': return { opacity: 0, transform: 'translateX(-60px)' };
    case 'slideInRight': return { opacity: 0, transform: 'translateX(60px)' };
    case 'slideInUp': return { opacity: 0, transform: 'translateY(40px)' };
    case 'slideInDown': return { opacity: 0, transform: 'translateY(-40px)' };
    case 'zoomIn': return { opacity: 0, transform: 'scale(0.5)' };
    case 'bounce': return { opacity: 0, transform: 'translateY(-30px)' };
    case 'typewriter': return { opacity: 1, clipPath: 'inset(0 100% 0 0)' };
    default: return {};
  }
}

// Get final CSS state (after animation completes)
export function getAnimationFinalStyle(animType) {
  switch (animType) {
    case 'fadeIn': return { opacity: 1 };
    case 'slideInLeft':
    case 'slideInRight':
    case 'slideInUp':
    case 'slideInDown': return { opacity: 1, transform: 'translateX(0) translateY(0)' };
    case 'zoomIn': return { opacity: 1, transform: 'scale(1)' };
    case 'bounce': return { opacity: 1, transform: 'translateY(0)' };
    case 'typewriter': return { opacity: 1, clipPath: 'inset(0 0% 0 0)' };
    default: return {};
  }
}

// Get CSS transition property for an animation
export function getAnimationTransition(animType, duration = 0.5) {
  const ease = animType === 'bounce' ? 'cubic-bezier(0.34, 1.56, 0.64, 1)' : 'cubic-bezier(0.25, 0.46, 0.45, 0.94)';
  if (animType === 'typewriter') {
    return `clip-path ${duration}s steps(20, end)`;
  }
  return `opacity ${duration}s ${ease}, transform ${duration}s ${ease}`;
}
