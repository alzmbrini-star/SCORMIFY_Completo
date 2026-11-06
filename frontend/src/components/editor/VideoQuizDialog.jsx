import React, { useEffect, useRef, useState, useMemo } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { authHeaders } from '../../contexts/AuthContext';
import { getApiUrl } from '../../utils/apiUrl';
import { absoluteVideoQuestions, nextVideoQuestionTime, prepareVideoQuizDraft, videoQuizSnapshot } from '../../utils/videoQuizDraft';
import { toast } from 'sonner';
import { videoQuizSource } from '../../utils/videoQuizProviders';
import VideoSourcePreview from './VideoSourcePreview';

const blank = () => ({at: 10, relative: false, question: '', options: ['', '', '', ''], correctIndex: 0, explanation: '', maxAttempts: 3});

export default function VideoQuizDialog({ open, onOpenChange, element, onApply, projectId }) {
  const [draft, setDraft] = useState({}), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [script, setScript] = useState(''), [bank, setBank] = useState([]), [search, setSearch] = useState('');
  const [duration, setDuration] = useState(0), [validationErrors, setValidationErrors] = useState([]), [savePhase, setSavePhase] = useState('');
  const sessionRef = useRef(null), durationRef = useRef(0), formRef = useRef(null), saveRef = useRef(false), videoRef = useRef(null);
  const source = useMemo(()=>{try{return videoQuizSource(draft.src);}catch(e){return {error:e.message};}},[draft.src]);
  function loadedDuration(d) {
    if (Number.isFinite(d) && d > 0) { durationRef.current = d; setDuration(d); setDraft(prev => ({...prev, checkpoints: absoluteVideoQuestions(prev.checkpoints, d)})); }
  }
  useEffect(() => {
    if (!open) { sessionRef.current = null; return; }
    const identity = element.id || 'current-video';
    if (sessionRef.current === identity) return;
    sessionRef.current = identity;
    const initial = videoQuizSnapshot(element) || {title: 'Vídeo com perguntas', src: element.embedUrl || element.src || '', instanceId: element.id, graded:false, checkpoints: [blank()]};
    setDraft({...JSON.parse(JSON.stringify(initial)), src: initial.src?.startsWith('/api/') ? `${getApiUrl()}${initial.src}` : initial.src});
    durationRef.current = 0; setDuration(0); setValidationErrors([]); setSavePhase('');
    setError(''); setScript(''); setBank([]); setSearch('');
  }, [open, element]);
  const patch = (i, data) => { setDraft(prev => ({...prev, timingReviewConfirmed:false, checkpoints: prev.checkpoints.map((cp, n) => n === i ? {...cp, ...data} : cp)})); setValidationErrors(prev => prev.filter(item => item.index !== i)); setError(''); };
  async function post(path, data) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), path === 'plan' ? 120000 : 45000);
    try {
      const res = await fetch(`${getApiUrl()}/api/heygen/video-quiz/${path}`, {method: 'POST', signal: controller.signal, headers: {...authHeaders(), 'Content-Type': 'application/json'}, body: JSON.stringify(data)});
      const result = await res.json(); if (!res.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Não foi possível processar a atividade.'); return result;
    } catch (e) { if (e.name === 'AbortError') throw new Error('O servidor demorou para responder. Suas perguntas continuam neste rascunho; tente salvar novamente.'); throw e; }
    finally { clearTimeout(timer); }
  }
  async function save() {
    if (saveRef.current) return;
    const prepared = prepareVideoQuizDraft(draft, durationRef.current);
    if(source.error)prepared.errors.unshift({message:source.error});
    else prepared.config.src=source.src;
    setValidationErrors(prepared.errors); setError('');
    if (prepared.errors.length) return;
    saveRef.current = true; setBusy(true); setSavePhase('Preparando as perguntas…');
    try {
      const result = await post('build', prepared.config);
      setSavePhase('Gravando as perguntas no curso…');
      const saved = await onApply({type: 'html', htmlContent: result.htmlContent, htmlDisplayMode: 'page', videoQuizConfig: result.config, animations: [], startTime: 0, endTime: null});
      if (JSON.stringify(saved?.videoQuizConfig?.checkpoints) !== JSON.stringify(result.config.checkpoints)) throw new Error('Não foi possível confirmar todas as perguntas no curso. O rascunho foi preservado; tente salvar novamente.');
      toast.success(`${result.config.checkpoints.length} pergunta(s) salva(s) no vídeo.`);
      onOpenChange(false);
    } catch (e) { const detail=e.response?.data?.detail; setError(typeof detail === 'string' ? detail : e.message || 'Não foi possível salvar. O rascunho foi preservado.'); }
    finally { saveRef.current = false; setBusy(false); setSavePhase(''); }
  }
  async function generate() {
    setBusy(true); setError('');
    try { const result = await post('plan', {context: script}); setDraft(prev => ({...prev, checkpoints: absoluteVideoQuestions(result.checkpoints, durationRef.current)})); setValidationErrors([]); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function loadBank() {
    setBusy(true); setError('');
    try { const res = await fetch(`${getApiUrl()}/api/questions${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''}`, {headers: authHeaders()}); if (!res.ok) throw new Error('Não foi possível abrir o Banco.'); const data = await res.json(); setBank(Array.isArray(data) ? data : []); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  function importQuestion(q) {
    const opts = q.alternatives || q.options || [];
    setDraft(prev => { const retained = absoluteVideoQuestions(prev.checkpoints.filter(cp => cp.question.trim()), durationRef.current); return {...prev, checkpoints: [...retained, {...blank(), ...nextVideoQuestionTime(retained, durationRef.current), question: q.text || q.prompt || q.title || '', options: opts.map(o => o.text), correctIndex: opts.findIndex(o => o.isCorrect), explanation: q.explanation || ''}]}; });
  }
  const questions = draft.checkpoints || [];
  return <Dialog open={open} onOpenChange={v => !busy && onOpenChange(v)}><DialogContent className="sm:max-w-4xl max-h-[90vh] flex flex-col">
    <DialogHeader><DialogTitle>Perguntas durante o vídeo</DialogTitle><DialogDescription>O vídeo pausa para as perguntas. Escolha se a atividade é prática sem nota ou avaliação.</DialogDescription></DialogHeader>
    {(error || validationErrors.length > 0) && <div role="alert" className="rounded border border-red-400 bg-red-950 p-3 text-sm text-red-100 max-h-36 overflow-y-auto">
      <p className="font-medium">As perguntas ainda não foram salvas. O rascunho foi mantido.</p>
      {error && <p>{error}</p>}
      {validationErrors.map((item, i) => <button type="button" key={i} className="block underline text-left mt-1" onClick={() => { const field = [...(formRef.current?.querySelectorAll('[aria-label]') || [])].find(node => node.getAttribute('aria-label') === item.label); field?.scrollIntoView?.({block: 'center'}); field?.focus(); }}>{item.message}</button>)}
    </div>}
    <div ref={formRef} className="flex-1 min-h-0 overflow-y-auto space-y-4 pr-2">
      {draft.timingReviewRequired && <div role="note" className="rounded border border-amber-400 bg-amber-950 p-3 text-sm text-amber-100">As perguntas foram planejadas com a fala do avatar, mas os tempos ainda precisam de revisão. Assista ao vídeo e pause após cada frase de transição, antes da próxima fala. Use “Usar tempo atual do vídeo” em cada pergunta. Não há pausas por percentual; a atividade só será liberada após sua confirmação.</div>}
      {draft.narrationScript && <details><summary>Roteiro falado e transições do avatar</summary><p className="whitespace-pre-wrap text-sm mt-2">{draft.narrationScript}</p></details>}
      <label className="block text-sm">Título<Input value={draft.title || ''} onChange={e => setDraft({...draft, title: e.target.value})} /></label>
      <label className="block text-sm">Vale nota?<select aria-label="Vale nota?" className="block w-full mt-1 rounded border border-input bg-background p-2" disabled={busy} value={draft.graded===true?'yes':'no'} onChange={e=>setDraft({...draft,graded:e.target.value==='yes'})}><option value="no">Não — prática e revisão livre</option><option value="yes">Sim — atividade avaliativa</option></select></label>
      <p className="text-xs text-muted-foreground">{draft.graded===true ? 'Cada pergunta acertada dentro do limite de tentativas tem o mesmo peso. A explicação após esgotar as tentativas não pontua. A nota é enviada ao concluir o vídeo e compõe o resultado do curso no SCORM. Uma nova tentativa avaliativa precisa ser iniciada explicitamente.' : 'Não altera nota, aprovação ou reprovação. O aluno pode usar “Rever vídeo e perguntas” para começar de novo e responder novamente, inclusive após concluir. A revisão não bloqueia novamente as seções já liberadas.'}</p>
      <label className="block text-sm">Vídeo — Bunny, Vimeo, YouTube, HeyGen, MP4 ou WebM<Input aria-label="Link ou iframe do vídeo" placeholder="Cole uma URL ou o iframe completo do provedor" disabled={busy} value={draft.src || ''} onChange={e => { durationRef.current = 0; setDuration(0); setDraft({...draft, src: e.target.value}); }} /></label>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={draft.preserveTransparency !== false} onChange={e => setDraft({...draft, preserveTransparency: e.target.checked})} />Preservar fundo transparente do vídeo</label>
      <p className="text-xs text-muted-foreground">Mantém o canal alfa do arquivo original (por exemplo, WebM transparente do HeyGen), sem converter o vídeo. Não remove um fundo que já esteja gravado no vídeo. O painel de perguntas mantém o contraste.</p>
      <p className="text-xs text-muted-foreground">Aceita URL ou iframe de Bunny Stream, Vimeo e YouTube. As perguntas controlam a pausa e a retomada dentro do slide. Vídeos externos exigem internet também no HTML/SCORM. Não use transmissões ao vivo. Prefira pausas ao final das frases.</p>
      <p className="text-xs text-amber-300">Bunny protegido: cole o iframe completo para manter token e expires e autorize os domínios do Editor e do LMS no provedor. Vimeo não listado: mantenha o hash do link. YouTube precisa permitir incorporação e ser aberto em HTTPS (arquivos locais podem ser bloqueados). O provedor pode exibir seus próprios controles e avisos.</p>
      {draft.src && source.error && <p role="alert" className="text-sm text-amber-300">{source.error}</p>}
      {draft.src && !source.error && (source.provider==='direct' ? <video ref={videoRef} src={source.src} controls preload="metadata" className="w-full max-h-48 bg-black" onLoadedMetadata={e => loadedDuration(e.currentTarget.duration)} /> : <VideoSourcePreview source={source} onDuration={loadedDuration} />)}
      {duration > 0 && <p className="text-xs text-muted-foreground">Duração do vídeo: {duration.toFixed(1)} segundos. Cada pergunta deve ter um momento diferente, antes do final.</p>}
      <details><summary>Gerar perguntas com IA a partir do roteiro</summary><p className="text-xs text-muted-foreground">Usa os créditos de IA configurados e substitui o rascunho de perguntas. Revise as respostas e os momentos sugeridos antes de aplicar.</p><Textarea aria-label="Roteiro para gerar perguntas" value={script} onChange={e => setScript(e.target.value)} placeholder="Cole a fala do personagem..." /><Button disabled={busy || script.trim().length < 40} onClick={generate}>Gerar duas perguntas com IA</Button></details>
      <details><summary>Usar perguntas do Banco</summary><Button onClick={loadBank} disabled={busy}>Carregar Banco do projeto</Button><Input aria-label="Buscar questão no Banco" placeholder="Buscar questão..." value={search} onChange={e => setSearch(e.target.value)} />{bank.filter(q => { const opts = q.alternatives || q.options || []; return opts.length >= 2 && opts.filter(o => o.isCorrect).length === 1 && String(q.text || q.prompt || q.title || '').toLowerCase().includes(search.toLowerCase()); }).slice(0, 30).map(q => <Button key={q.id} variant="outline" className="block w-full text-left truncate mt-1" disabled={questions.length >= 12} onClick={() => importQuestion(q)}>{q.text || q.prompt || q.title}</Button>)}</details>
      {questions.map((cp, i) => <fieldset key={i} className={`border rounded-lg p-3 space-y-2 ${validationErrors.some(item => item.index === i) ? 'border-red-400' : 'border-border'}`} disabled={busy}><legend>Pergunta {i+1}</legend>
        {cp.pauseCue && <p className="text-sm">Pausar após a fala: <strong>“{cp.pauseCue}”</strong>{cp.timingStatus==='audio-aligned' ? ' — tempo alinhado com legenda e pausa medida no áudio; confira a reprodução.' : ''}</p>}
        <div className="flex gap-3"><label className="text-sm flex-1">{cp.relative ? 'Posição proporcional (0 a 1)' : 'Pausa em segundos'}<Input aria-label={`Tempo da pergunta ${i+1}`} type="number" min="0" step="0.001" value={cp.at ?? ''} onChange={e => patch(i, {at: e.target.value === '' ? null : Number(e.target.value)})} /></label><label className="text-sm flex-1">Máximo de tentativas<Input aria-label={`Máximo de tentativas da pergunta ${i+1}`} type="number" min="1" max="10" value={cp.maxAttempts} onChange={e => patch(i, {maxAttempts: Number(e.target.value)})} /></label></div>
        {source.provider==='direct' && <Button variant="outline" onClick={() => { const video=videoRef.current; if(video && Number.isFinite(video.currentTime)){video.pause();patch(i,{at:Math.round(video.currentTime*1000)/1000,relative:false});} }}>Usar tempo atual do vídeo — pergunta {i+1}</Button>}
        <Textarea aria-label={`Enunciado ${i+1}`} value={cp.question} onChange={e => patch(i, {question: e.target.value})} placeholder="Enunciado da pergunta" />
        <p className="text-xs text-muted-foreground">Preencha ao menos duas alternativas e marque a correta. Alternativas extras vazias não impedem o salvamento.</p>
        {cp.options.map((option, j) => <label key={j} className="flex items-center gap-2"><input type="radio" aria-label={`Alternativa correta ${j+1} da pergunta ${i+1}`} checked={cp.correctIndex === j} name={`correct-${i}`} onChange={() => patch(i, {correctIndex: j})} /><Input aria-label={`Alternativa ${j+1} da pergunta ${i+1}`} value={option} onChange={e => patch(i, {options: cp.options.map((o, n) => n === j ? e.target.value : o)})} /></label>)}
        <label className="block text-sm">Explicação final (obrigatória)<Textarea aria-label={`Explicação ${i+1}`} value={cp.explanation} onChange={e => patch(i, {explanation: e.target.value})} placeholder="Explicação exibida no painel de perguntas após o limite de erros" /></label>
        <Button variant="outline" onClick={() => setDraft(prev => ({...prev, checkpoints: prev.checkpoints.filter((_, n) => i !== n)}))}>Remover pergunta</Button>
      </fieldset>)}
      <Button variant="outline" disabled={busy || questions.length >= 12} onClick={() => setDraft(prev => { const current = absoluteVideoQuestions(prev.checkpoints, durationRef.current); return {...prev, checkpoints: [...current, {...blank(), ...nextVideoQuestionTime(current, durationRef.current)}]}; })}>Adicionar pausa com pergunta</Button>
      {draft.timingReviewRequired && <label className="flex items-start gap-2 text-sm"><input type="checkbox" aria-label="Confirmar revisão das pausas" checked={draft.timingReviewConfirmed===true} onChange={e=>setDraft({...draft,timingReviewConfirmed:e.target.checked})} />Escutei as transições e confirmei que cada pausa acontece após a fala, antes da próxima explicação.</label>}
    </div>
    <p role="status" aria-live="polite" className="text-sm">{savePhase || `${questions.length} pergunta(s) neste rascunho. Clique em Aplicar ao vídeo para salvar.`}</p>
    <div className="flex justify-end gap-2"><Button variant="outline" disabled={busy} onClick={() => onOpenChange(false)}>Cancelar</Button><Button disabled={busy || !questions.length} onClick={save}>{busy ? 'Processando…' : 'Aplicar ao vídeo'}</Button></div>
  </DialogContent></Dialog>;
}
