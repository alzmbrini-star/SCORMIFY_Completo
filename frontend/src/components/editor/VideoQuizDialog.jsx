import React, { useEffect, useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { authHeaders } from '../../contexts/AuthContext';
import { getApiUrl } from '../../utils/apiUrl';

const blank = () => ({at: 10, relative: false, question: '', options: ['', '', '', ''], correctIndex: 0, explanation: '', maxAttempts: 3});

export default function VideoQuizDialog({ open, onOpenChange, element, onApply, projectId }) {
  const [draft, setDraft] = useState({}), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [script, setScript] = useState(''), [bank, setBank] = useState([]), [search, setSearch] = useState('');
  useEffect(() => {
    if (!open) return;
    const initial = element.videoQuizConfig || {title: 'Vídeo com perguntas', src: element.src || '', instanceId: element.id, checkpoints: [blank()]};
    setDraft({...initial, src: initial.src?.startsWith('/api/') ? `${getApiUrl()}${initial.src}` : initial.src});
    setError(''); setScript(''); setBank([]);
  }, [open, element]);
  const patch = (i, data) => setDraft(prev => ({...prev, checkpoints: prev.checkpoints.map((cp, n) => n === i ? {...cp, ...data} : cp)}));
  async function post(path, data) {
    const res = await fetch(`${getApiUrl()}/api/heygen/video-quiz/${path}`, {method: 'POST', headers: {...authHeaders(), 'Content-Type': 'application/json'}, body: JSON.stringify(data)});
    const result = await res.json(); if (!res.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Não foi possível processar a atividade.'); return result;
  }
  async function save() {
    setBusy(true); setError('');
    try { const result = await post('build', draft); await onApply({type: 'html', htmlContent: result.htmlContent, htmlDisplayMode: 'page', videoQuizConfig: result.config, animations: [], startTime: 0, endTime: null}); onOpenChange(false); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function generate() {
    setBusy(true); setError('');
    try { const result = await post('plan', {context: script}); setDraft(prev => ({...prev, checkpoints: result.checkpoints})); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function loadBank() {
    setBusy(true); setError('');
    try { const res = await fetch(`${getApiUrl()}/api/questions${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''}`, {headers: authHeaders()}); if (!res.ok) throw new Error('Não foi possível abrir o Banco.'); const data = await res.json(); setBank(Array.isArray(data) ? data : []); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  function importQuestion(q) {
    const opts = q.alternatives || q.options || [];
    setDraft(prev => { const retained = prev.checkpoints.filter(cp => cp.question.trim()); return {...prev, checkpoints: [...retained, {...blank(), at: 10 * (retained.length + 1), question: q.text || q.prompt || q.title || '', options: opts.map(o => o.text), correctIndex: opts.findIndex(o => o.isCorrect), explanation: q.explanation || ''}]}; });
  }
  const questions = draft.checkpoints || [];
  return <Dialog open={open} onOpenChange={v => !busy && onOpenChange(v)}><DialogContent className="sm:max-w-4xl max-h-[90vh] flex flex-col">
    <DialogHeader><DialogTitle>Perguntas durante o vídeo</DialogTitle><DialogDescription>O vídeo pausa; acerto ou explicação após o limite de tentativas libera a continuação. Não altera a aprovação do curso.</DialogDescription></DialogHeader>
    <div className="flex-1 overflow-y-auto space-y-4 pr-2">
      <label className="block text-sm">Título<Input value={draft.title || ''} onChange={e => setDraft({...draft, title: e.target.value})} /></label>
      <label className="block text-sm">Vídeo direto (HeyGen, MP4 ou WebM)<Input value={draft.src || ''} onChange={e => setDraft({...draft, src: e.target.value})} /></label>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={draft.preserveTransparency !== false} onChange={e => setDraft({...draft, preserveTransparency: e.target.checked})} />Preservar fundo transparente do vídeo</label>
      <p className="text-xs text-muted-foreground">Mantém o canal alfa do arquivo original (por exemplo, WebM transparente do HeyGen), sem converter o vídeo. Não remove um fundo que já esteja gravado no vídeo. O painel de perguntas mantém o contraste.</p>
      <p className="text-xs text-muted-foreground">Não aceita iframe de YouTube/Vimeo/Bunny. Links externos exigem conexão e podem expirar. Revise os tempos assistindo ao vídeo; prefira pausas ao final das frases. A atividade passa a ocupar este elemento no slide.</p>
      {draft.src && <video src={draft.src} controls preload="metadata" className="w-full max-h-48 bg-black" onLoadedMetadata={e => { const d = e.currentTarget.duration; if (Number.isFinite(d)) setDraft(prev => ({...prev, checkpoints: prev.checkpoints.map(cp => cp.relative ? {...cp, at: Math.round(cp.at * d * 10) / 10, relative: false} : cp)})); }} />}
      <details><summary>Gerar perguntas com IA a partir do roteiro</summary><p className="text-xs text-muted-foreground">Usa os créditos de IA configurados e substitui o rascunho de perguntas. Revise as respostas e os momentos sugeridos antes de aplicar.</p><Textarea aria-label="Roteiro para gerar perguntas" value={script} onChange={e => setScript(e.target.value)} placeholder="Cole a fala do personagem..." /><Button disabled={busy || script.trim().length < 40} onClick={generate}>Gerar duas perguntas com IA</Button></details>
      <details><summary>Usar perguntas do Banco</summary><Button onClick={loadBank} disabled={busy}>Carregar Banco do projeto</Button><Input aria-label="Buscar questão no Banco" placeholder="Buscar questão..." value={search} onChange={e => setSearch(e.target.value)} />{bank.filter(q => { const opts = q.alternatives || q.options || []; return opts.length >= 2 && opts.filter(o => o.isCorrect).length === 1 && String(q.text || q.prompt || q.title || '').toLowerCase().includes(search.toLowerCase()); }).slice(0, 30).map(q => <Button key={q.id} variant="outline" className="block w-full text-left truncate mt-1" disabled={questions.length >= 12} onClick={() => importQuestion(q)}>{q.text || q.prompt || q.title}</Button>)}</details>
      {questions.map((cp, i) => <fieldset key={i} className="border border-border rounded-lg p-3 space-y-2" disabled={busy}><legend>Pergunta {i+1}</legend>
        <div className="flex gap-3"><label className="text-sm flex-1">{cp.relative ? 'Posição proporcional (0 a 1)' : 'Pausa em segundos'}<Input aria-label={`Tempo da pergunta ${i+1}`} type="number" min="0" step="0.1" value={cp.at} onChange={e => patch(i, {at: Number(e.target.value)})} /></label><label className="text-sm flex-1">Máximo de tentativas<Input type="number" min="1" max="10" value={cp.maxAttempts} onChange={e => patch(i, {maxAttempts: Number(e.target.value)})} /></label></div>
        <Textarea aria-label={`Enunciado ${i+1}`} value={cp.question} onChange={e => patch(i, {question: e.target.value})} placeholder="Enunciado da pergunta" />
        {cp.options.map((option, j) => <label key={j} className="flex items-center gap-2"><input type="radio" aria-label={`Alternativa correta ${j+1} da pergunta ${i+1}`} checked={cp.correctIndex === j} name={`correct-${i}`} onChange={() => patch(i, {correctIndex: j})} /><Input aria-label={`Alternativa ${j+1} da pergunta ${i+1}`} value={option} onChange={e => patch(i, {options: cp.options.map((o, n) => n === j ? e.target.value : o)})} /></label>)}
        <Textarea aria-label={`Explicação ${i+1}`} value={cp.explanation} onChange={e => patch(i, {explanation: e.target.value})} placeholder="Explicação exibida abaixo do personagem" />
        <Button variant="outline" onClick={() => setDraft(prev => ({...prev, checkpoints: prev.checkpoints.filter((_, n) => i !== n)}))}>Remover pergunta</Button>
      </fieldset>)}
      <Button variant="outline" disabled={busy || questions.length >= 12} onClick={() => setDraft(prev => ({...prev, checkpoints: [...prev.checkpoints, {...blank(), at: 10 * (prev.checkpoints.length + 1)}]}))}>Adicionar pausa com pergunta</Button>
    </div>
    {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
    <div className="flex justify-end gap-2"><Button variant="outline" disabled={busy} onClick={() => onOpenChange(false)}>Cancelar</Button><Button disabled={busy || !questions.length} onClick={save}>{busy ? 'Processando…' : 'Aplicar ao vídeo'}</Button></div>
  </DialogContent></Dialog>;
}
