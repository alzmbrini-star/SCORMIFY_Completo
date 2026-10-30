import React, { useId } from 'react';

export default function SimulatorExperienceOptions({ complexity = 'guided', visualStyle = 'illustrated', activityType = 'simulation', onChange, disabled = false }) {
  const id = useId();
  return <fieldset disabled={disabled} className="rounded-lg border border-slate-500/50 p-4 space-y-3" data-testid="simulator-experience-options">
    <legend className="px-1 text-sm font-semibold">Experiência dos simuladores</legend>
    <label htmlFor={`${id}-type`} className="block text-sm">Tipo de atividade
      <select id={`${id}-type`} className="block w-full mt-1 rounded border border-slate-500 bg-slate-900 text-slate-100 p-2" value={activityType} onChange={e => onChange({complexity, visualStyle, activityType:e.target.value})}>
        <option value="simulation">Simulação interativa — decisões e consequências</option>
        <option value="visualization">Visualização didática — animar, observar e explorar</option>
      </select>
    </label>
    {activityType === 'visualization' && <p className="text-sm">Animação explicativa com iniciar/pausar, velocidade, linha do tempo e legendas. Sem pontuação, aprovação ou fracasso. Representações simplificadas devem informar seus limites científicos.</p>}
    <div className="grid gap-3 sm:grid-cols-2">
      <label htmlFor={`${id}-complexity`} className="text-sm">Complexidade da interação
        <select id={`${id}-complexity`} disabled={activityType === 'visualization'} className="block w-full mt-1 rounded border border-slate-500 bg-slate-900 text-slate-100 p-2" value={complexity} onChange={e => onChange({ complexity: e.target.value, visualStyle, activityType })}>
          <option value="guided">Guiado — cenário e poucas escolhas</option>
          <option value="applied">Aplicado — experimentação e consequências</option>
          <option value="advanced">Avançado — instrumentos e parâmetros</option>
        </select>
      </label>
      <label htmlFor={`${id}-style`} className="text-sm">Abordagem visual
        <select id={`${id}-style`} className="block w-full mt-1 rounded border border-slate-500 bg-slate-900 text-slate-100 p-2" value={visualStyle} onChange={e => onChange({ complexity, visualStyle: e.target.value, activityType })}>
          <option value="illustrated">Cenário ilustrado contextualizado</option>
          <option value="technical">Esquema técnico explicativo</option>
        </select>
      </label>
    </div>
    <p className="text-xs leading-relaxed">O nível muda a orientação e os controles expostos, não a qualidade da arte nem o nível do curso. Cenários devem ser bem acabados em todos os níveis. Aplica-se às novas gerações de simuladores; não altera atividades já inseridas.</p>
  </fieldset>;
}
