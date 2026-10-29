/* Trusted finite-state interpreter. No eval, generated JS, network or timers. */
(function (root) {
  'use strict';
  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function evaluate(node, state) {
    if (typeof node === 'boolean' || typeof node === 'number') return node;
    if (Object.prototype.hasOwnProperty.call(node, 'var')) return state[node.var];
    const args = node.args.map(arg => evaluate(arg, state));
    switch (node.op) {
      case 'all': return args.every(Boolean);
      case 'any': return args.some(Boolean);
      case 'not': return !args[0];
      case 'eq': return args[0] === args[1];
      case 'ne': return args[0] !== args[1];
      case 'lt': return args[0] < args[1];
      case 'le': return args[0] <= args[1];
      case 'gt': return args[0] > args[1];
      case 'ge': return args[0] >= args[1];
      default: {
        let value;
        switch (node.op) {
          case 'add': value = args[0] + args[1]; break;
          case 'sub': value = args[0] - args[1]; break;
          case 'mul': value = args[0] * args[1]; break;
          case 'min': value = Math.min(...args); break;
          case 'max': value = Math.max(...args); break;
          default: throw new Error('Operador não suportado');
        }
        if (!Number.isSafeInteger(value) || Math.abs(value) > 1000000) throw new Error('Limite numérico');
        return value;
      }
    }
  }
  function createRuleEngine(definition) {
    const spec = clone(definition);
    const initial = Object.fromEntries(spec.variables.map(v => [v.id, v.initial]));
    let state = clone(initial), history = [], snapshots = [], sequence = 0;
    const listeners = new Set();
    function result() {
      if (evaluate(spec.failure.when, state)) return 'failure';
      if (evaluate(spec.goal.when, state)) return 'success';
      if (history.length >= spec.maxSteps) return 'failure';
      return spec.actions.some(a => candidate(a).enabled) ? 'active' : 'failure';
    }
    function candidate(action) {
      if (!evaluate(action.requires, state)) return {enabled:false, reason:action.unavailable};
      const updated = clone(state);
      try {
        for (const [key, expr] of Object.entries(action.effects)) updated[key] = evaluate(expr, state);
      } catch (_) { return {enabled:false, reason:'A ação excede o limite numérico do modelo.'}; }
      const outside = spec.variables.find(v => updated[v.id] < v.min || updated[v.id] > v.max);
      if (outside) return {enabled:false, reason:'Limite de '+outside.label+' seria ultrapassado. '+action.unavailable};
      if (spec.variables.every(v => updated[v.id] === state[v.id])) return {enabled:false, reason:'Esta ação não altera o estado atual. '+action.unavailable};
      return {enabled:true, updated};
    }
    function available(action) {
      if (result() !== 'active') return {enabled:false, reason:'Esta tentativa terminou. Reinicie para experimentar outra estratégia.'};
      return candidate(action);
    }
    function view() {
      const outcome = result();
      return clone({state, history, snapshots, outcome, steps:history.length,
        remaining:Math.max(0, spec.maxSteps-history.length),
        scene:spec.scenes.find(s => evaluate(s.when,state)),
        actions:spec.actions.map(a => {const status=available(a); return {id:a.id,enabled:status.enabled,reason:status.reason || ''};}),
        message:outcome === 'success' ? spec.goal.message : outcome === 'failure'
          ? (evaluate(spec.failure.when,state) ? spec.failure.message : history.length >= spec.maxSteps
            ? 'Limite de decisões atingido sem cumprir o objetivo. Compare o histórico e tente outra estratégia.'
            : 'Não há ações viáveis neste estado. Compare as decisões que consumiram recursos ou bloquearam alternativas e reinicie para experimentar outra estratégia.') : ''});
    }
    function emit() { const current=view(); listeners.forEach(listener => listener(clone(current))); return current; }
    return Object.freeze({
      getState:view,
      act(id) {
        const action=spec.actions.find(a => a.id===id);
        if (!action) return {ok:false, reason:'Ação inexistente'};
        const status=available(action);
        if (!status.enabled) return {ok:false, reason:status.reason};
        const before=clone(state); state=status.updated;
        const changes=spec.variables.filter(v => state[v.id]!==before[v.id]).map(v => ({id:v.id,label:v.label,before:before[v.id],after:state[v.id],unit:v.unit}));
        history.push({id:action.id,label:action.label,feedback:action.feedback,changes});
        return {ok:true,view:emit()};
      },
      saveSnapshot() {
        sequence+=1;
        snapshots.push({id:sequence,step:history.length,state:clone(state),outcome:result()});
        if (snapshots.length>5) snapshots.shift();
        emit(); return sequence;
      },
      compare(id) {
        const saved=snapshots.find(s => s.id===id);
        return saved ? spec.variables.map(v => ({id:v.id,label:v.label,delta:state[v.id]-saved.state[v.id],unit:v.unit})) : null;
      },
      reset() { state=clone(initial); history=[]; snapshots=[]; sequence=0; return emit(); },
      subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); }
    });
  }
  root.createRuleEngine=createRuleEngine;
  if (typeof module !== 'undefined' && module.exports) module.exports={createRuleEngine,evaluate};
})(typeof globalThis !== 'undefined' ? globalThis : this);
