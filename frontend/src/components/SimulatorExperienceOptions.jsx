import React, { useId } from 'react';

export default function SimulatorExperienceOptions({ complexity = 'guided', visualStyle = 'illustrated', activityType = 'simulation', objectImages = false, onChange, disabled = false }) {
  const id = useId();
  const change = patch => onChange({complexity, visualStyle, activityType, ...(objectImages ? {objectImages:true} : {}), ...patch});
  return <fieldset disabled={disabled} className="rounded-lg border border-slate-500/50 p-4 space-y-3" data-testid="simulator-experience-options">
    <legend className="px-1 text-sm font-semibold">Experiência dos simuladores</legend>
    <label htmlFor={`${id}-type`} className="block text-sm">Tipo de atividade
      <select id={`${id}-type`} className="block w-full mt-1 rounded border border-slate-500 bg-slate-900 text-slate-100 p-2" value={activityType} onChange={e => change({activityType:e.target.value})}>
        <option value="simulation">Simulação interativa — decisões e consequências</option>
        <option value="visualization">Visualização didática — animar, observar e explorar</option>
      </select>
    </label>
    {activityType === 'visualization' && <p className="text-sm">Animação explicativa com iniciar/pausar, velocidade, linha do tempo e legendas. Sem pontuação, aprovação ou fracasso. Representações simplificadas devem informar seus limites científicos.</p>}
    <div className="grid gap-3 sm:grid-cols-2">
      <label htmlFor={`${id}-complexity`} className="text-sm">Complexidade da interação
        <select id={`${id}-complexity`} disabled={activityType === 'visualization'} className="block w-full mt-1 rounded border border-slate-500 bg-slate-900 text-slate-100 p-2" value={complexity} onChange={e => change({ complexity: e.target.value })}>
          <option value="guided">Guiado — demonstração visual do mecanismo</option>
          <option value="applied">Aplicado — experimentação e consequências</option>
          <option value="advanced">Avançado — instrumentos e parâmetros</option>
        </select>
      </label>
      <label htmlFor={`${id}-style`} className="text-sm">Abordagem visual
        <select id={`${id}-style`} className="block w-full mt-1 rounded border border-slate-500 bg-slate-900 text-slate-100 p-2" value={visualStyle} onChange={e => change({ visualStyle: e.target.value })}>
          <option value="illustrated">Cenário ilustrado contextualizado</option>
          <option value="technical">Esquema técnico explicativo</option>
        </select>
      </label>
    </div>
    <label className="block text-sm"><input type="checkbox" checked={objectImages} onChange={e => change({objectImages:e.target.checked})} className="mr-2" />Ilustrar objetos com imagens IA</label>
    <p className="text-xs">Opcional: gera até 4 peças individuais com fundo transparente por simulador, consome créditos OpenAI e pode demorar mais. Salva as imagens na biblioteca e incorpora no HTML/SCORM. Partes deformáveis e fluxos permanecem vetoriais; se uma imagem falhar, a peça anterior é mantida. Não redesenha atividades já inseridas sem refino explícito.</p>
    <p className="text-xs leading-relaxed">Guiado prioriza uma cena própria para o assunto, objetos reconhecíveis e movimentos explicativos, com poucos controles e sem exigir cálculos, indicadores ou reprovação. Recursos gráficos podem ser reutilizados, sem repetir um modelo temático. Aplicado e Avançado mantêm desafios mais completos. O acabamento visual é importante em todos os níveis. Aplica-se às novas gerações; atividades existentes exigem refino explícito.</p>
  </fieldset>;
}
