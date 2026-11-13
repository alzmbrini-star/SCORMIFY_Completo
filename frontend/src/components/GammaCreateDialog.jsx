import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authHeaders, useAuth } from '../contexts/AuthContext';
import { getApiUrl } from '../utils/apiUrl';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import CompanySelector from './CompanySelector';
import GammaDesignPicker from './GammaDesignPicker';
import GammaDocumentInput from './GammaDocumentInput';
import './gammaDialog.css';

const API = getApiUrl();
const ACTIVE = ['pending', 'submitting', 'assessment'];
async function api(path, options = {}) {
  const response = await fetch(`${API}/api/gamma${path}`, { credentials: 'include', ...options,
    headers: authHeaders({ 'Content-Type': 'application/json' }) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível consultar o Gamma.');
  return data;
}

export default function GammaCreateDialog({ onCreated }) {
  const { user, isSuperAdmin, isCompanyAdmin } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [configured, setConfigured] = useState(null);
  const [title, setTitle] = useState('');
  const [prompt, setPrompt] = useState('');
  const [slideCount, setSlideCount] = useState('5');
  const count = Number(slideCount);
  const validCount = slideCount.trim() !== '' && Number.isInteger(count) && count >= 1 && count <= 100;
  const [companyId, setCompanyId] = useState('');
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [documentBusy, setDocumentBusy] = useState(false);
  const [assessmentEnabled, setAssessmentEnabled] = useState(false);
  const [assessmentCount, setAssessmentCount] = useState('5');
  const [assessmentImages, setAssessmentImages] = useState(true);
  const [assessmentConfigured, setAssessmentConfigured] = useState(true);
  const validAssessmentCount = /^\d+$/.test(assessmentCount) && Number(assessmentCount)>=1 && Number(assessmentCount)<=10;
  const [uncertain, setUncertain] = useState(false);
  const [design, setDesign] = useState(null);
  const [designRequired, setDesignRequired] = useState(false);
  const [step, setStep] = useState('content');
  const requestId = useRef(null);
  const submitting = useRef(false);
  const allowed = isSuperAdmin || isCompanyAdmin || user?.role === 'editor' || user?.roles?.includes('editor');

  useEffect(() => {
    if (!open || !allowed) return undefined;
    let cancelled = false, timer;
    const refresh = async () => {
      try {
        const config = await api('/status');
        const rows = await api('/jobs');
        const updated = [];
        for (const row of rows) updated.push(ACTIVE.includes(row.status) ? await api(`/jobs/${row.id}`) : row);
        if (!cancelled) { setConfigured(config.configured); setAssessmentConfigured(config.assessmentConfigured!==false); setJobs(updated); }
      } catch (e) { if (!cancelled) setError(e.message); }
      if (!cancelled) timer = setTimeout(refresh, 10000);
    };
    refresh();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [open, allowed]);

  if (!allowed) return null;
  const generate = async () => {
    if (submitting.current || busy || documentBusy || uncertain || !validCount || (assessmentEnabled && (!validAssessmentCount || !assessmentConfigured)) || prompt.length > 100000) return;
    submitting.current = true;
    setBusy(true); setError('');
    requestId.current = requestId.current || crypto.randomUUID();
    try {
      const row = await api('/generate', { method: 'POST', body: JSON.stringify({ requestId: requestId.current, title: title.trim(), prompt: prompt.trim(), companyId: companyId || null, numCards: count,
        interactiveAssessment: {enabled: assessmentEnabled, questionCount: assessmentEnabled ? Number(assessmentCount) : 5, images: assessmentImages},
        ...(design?.kind === 'theme' ? {themeId: design.id} : design?.kind === 'template' ? {templateId: design.id} : {}) }) });
      setJobs(previous => [row, ...previous.filter(item => item.id !== row.id)]);
      if (row.status === 'unknown') setUncertain(true);
      else { requestId.current = null; setTitle(''); setPrompt(''); }
      onCreated?.();
      setStep('history');
    } catch (e) { setError(e.message + ' Consulte o histórico antes de tentar novamente.'); setUncertain(true); }
    finally { submitting.current = false; setBusy(false); }
  };
  const download = async (job) => {
    try {
      const response = await fetch(`${API}/api/gamma/jobs/${job.id}/download`, { credentials: 'include', headers: authHeaders() });
      if (!response.ok) throw new Error('ZIP ainda não disponível.');
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'Gamma-slides.zip'; anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (e) { setError(e.message); }
  };
  const retryAssessment = async job => {
    if (!window.confirm('Tentar somente a avaliação novamente? Usa créditos de IA do SCORMIFY. Os slides Gamma e as edições serão preservados.')) return;
    try {const updated=await api(`/jobs/${job.id}/retry-assessment`,{method:'POST'});setJobs(rows=>rows.map(r=>r.id===job.id?updated:r));}
    catch(e){setError(e.message);}
  };
  const labels = { submitting: 'Enviando ao Gamma', pending: 'Gerando / importando', assessment: 'Preparando avaliação e imagens', completed: 'Concluído', failed: 'Falhou', unknown: 'Sem confirmação — confira no Gamma', preserved: 'Slides existentes preservados' };
  return <>
    <Button variant="outline" onClick={() => setOpen(true)} data-testid="gamma-create-open">Criar com Gamma</Button>
    <Dialog open={open} onOpenChange={next => {setOpen(next); if (!next) {setDesign(null); setDesignRequired(false); setStep('content');}}}><DialogContent className="gamma-dialog">
      <div className="gamma-head"><div className="gamma-eyebrow">SCORMIFY + GAMMA</div>
      <DialogHeader><DialogTitle>Criar apresentação com Gamma</DialogTitle><DialogDescription>Português do Brasil · novo projeto independente · qualidade standard</DialogDescription></DialogHeader>
      <nav className="gamma-tabs" role="tablist" aria-label="Etapas da criação Gamma" onKeyDown={e => {const keys=['content','design','history'];const index=keys.indexOf(step);if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();const next=keys[(index+(e.key==='ArrowRight'?1:2))%3];setStep(next);e.currentTarget.querySelector(`[data-step="${next}"]`)?.focus();}}}>
        {[['content','Conteúdo'],['design','Aparência'],['history',`Histórico (${jobs.length})`]].map(([id,label],index)=><button type="button" key={id} id={`gamma-tab-${id}`} data-step={id} role="tab" aria-selected={step===id} aria-controls={`gamma-panel-${id}`} tabIndex={step===id?0:-1} onClick={()=>setStep(id)}><span>{index+1}</span>{label}</button>)}
      </nav></div>
      <div className="gamma-body">
      {configured === false && <p role="alert" className="gamma-error">GAMMA_API_KEY não está configurada no servidor.</p>}
      <section id="gamma-panel-content" role="tabpanel" aria-labelledby="gamma-tab-content" hidden={step!=='content'}>
      <div className="gamma-content-grid"><div className="gamma-section gamma-fields">
      <div><h3>O que vamos ensinar?</h3><p className="text-sm">Defina o conteúdo. Depois, escolha o visual.</p></div>
      <label>Título do curso<Input aria-label="Título Gamma" maxLength={160} value={title} disabled={busy} onChange={e => setTitle(e.target.value)} /></label>
      <label>Quantidade de slides<Input aria-label="Quantidade de slides Gamma" type="number" inputMode="numeric" min="1" max="100" step="1" value={slideCount} disabled={busy} onChange={e=>setSlideCount(e.target.value)} aria-invalid={!validCount} aria-describedby="gamma-count-help"/></label>
      <p id="gamma-count-help" className={validCount?'gamma-help':'gamma-error'}>Digite de 1 a 100. O Gamma limita o plano gratuito a 10 slides e os pagos a até 100. Quantidades maiores podem consumir mais créditos. O limite da sua conta será validado pelo Gamma.</p>
      <label>Conteúdo da apresentação<textarea aria-label="Conteúdo Gamma" className="w-full min-h-28 p-3" maxLength={100000} value={prompt} disabled={busy || documentBusy} onChange={e => setPrompt(e.target.value)} placeholder="Tema, público, objetivos e tópicos. Inclua o conteúdo que deseja ensinar." /></label>
      <p className="gamma-help">{prompt.length.toLocaleString('pt-BR')} / 100.000 caracteres. Revise o conteúdo e escolha slides suficientes para cobrir seus tópicos.</p>
      <GammaDocumentInput value={prompt} onChange={setPrompt} disabled={busy || uncertain} onBusy={setDocumentBusy}/>
      <CompanySelector value={companyId} onChange={setCompanyId} testIdPrefix="gamma-company" native disabled={busy}/>
      </div><aside className="gamma-side"><strong>Seu curso, um novo começo</strong><p>{validCount?`${count} ${count===1?'slide':'slides'} em PT-BR`:'Defina a quantidade de slides'}, sem alterar seus projetos existentes.</p><p>Você poderá acrescentar textos, perguntas e interações no Editor.</p>
      <fieldset className="gamma-assessment"><legend>Avaliação ao final · opcional</legend>
        <label className="gamma-assessment-check"><input type="checkbox" checked={assessmentEnabled} disabled={busy || uncertain} onChange={e=>setAssessmentEnabled(e.target.checked)}/>Adicionar avaliação interativa</label>
        <p className="gamma-help">Usa o conteúdo revisado ao lado, incluindo o texto do Word, PDF ou PowerPoint carregado. Acrescenta 1 slide após a apresentação, sem substituir slides Gamma.</p>
        {assessmentEnabled&&<><label>Quantidade de questões<Input aria-label="Quantidade de questões da avaliação Gamma" type="number" min="1" max="10" step="1" inputMode="numeric" value={assessmentCount} disabled={busy || uncertain} onChange={e=>setAssessmentCount(e.target.value)} aria-invalid={!validAssessmentCount}/></label>
        {!assessmentConfigured&&<p className="gamma-error" role="alert">A IA do SCORMIFY não está configurada. Solicite a configuração ao administrador ou desmarque a avaliação para gerar apenas os slides Gamma.</p>}
        {!validAssessmentCount&&<p className="gamma-error" role="alert">Informe de 1 a 10 questões.</p>}
        <label className="gamma-assessment-check"><input type="checkbox" checked={assessmentImages} disabled={busy || uncertain} onChange={e=>setAssessmentImages(e.target.checked)}/>Gerar imagem de apoio para cada questão</label>
        <p className="gamma-help">Questões de escolha única com feedback, revisáveis no Editor. Imagens ficam vinculadas às questões e salvas na biblioteca. Usa créditos de IA do SCORMIFY, além dos créditos Gamma. Revise conteúdo, gabarito e imagens antes de publicar; a conclusão segue as regras existentes do curso.</p></>}
      </fieldset>
      <details className="gamma-help mt-4"><summary>Créditos e edição dos slides</summary><p>Usa créditos da conta Gamma configurada no servidor. A quantidade é uma meta: o Gamma pode entregar um número diferente, que será informado no histórico, sem gerar novamente. Preserva o visual como imagem-base por slide; o texto da imagem não será editável separadamente. Arquivos muito grandes podem atingir os limites de importação de 80 MB no ZIP e 160 MB nas imagens descompactadas. Confira o resultado antes de publicar.</p></details></aside></div>
      </section>
      <section id="gamma-panel-design" role="tabpanel" aria-labelledby="gamma-tab-design" hidden={step!=='design'}>
      <GammaDesignPicker api={api} value={design} onChange={(selection, required) => {setDesign(selection); if (required !== undefined) setDesignRequired(required);}} disabled={busy || uncertain || configured !== true}/>
      </section>
      <section id="gamma-panel-history" role="tabpanel" aria-labelledby="gamma-tab-history" hidden={step!=='history'}>
      <section className="space-y-3" aria-label="Histórico Gamma"><h3 className="font-semibold">Gerações recentes</h3>
        {jobs.length===0&&<div className="gamma-info">Nenhuma geração ainda. Comece em Conteúdo e escolha a aparência.</div>}
        {jobs.map(job => <article key={job.id} className="gamma-job space-y-2" data-testid="gamma-job">
          <strong>{job.title}</strong><div><span role="status" className={`gamma-status gamma-status-${job.status}`}>{labels[job.status] || job.status}{job.progress?.percent != null ? ` · ${job.progress.percent}%` : ''}{job.actualSlides ? ` · ${job.actualSlides} slides` : ''}</span></div>
          <p>Quantidade solicitada: {job.numCards || 5}{job.actualSlides ? ` · recebida: ${job.actualSlides}` : ''}</p>
          {job.interactiveAssessment?.enabled&&<div className="gamma-info" aria-label="Avaliação final Gamma"><strong>Avaliação interativa final</strong>
            <p>{job.assessment?.status==='ready'?`${job.assessment.questionCount || job.interactiveAssessment.questionCount} questões prontas para revisar no Editor${job.totalSlides?` · ${job.totalSlides} slides no projeto`:''}`:job.assessment?.status==='failed'?'Avaliação não concluída; slides Gamma preservados.':`Preparação em andamento${job.assessment?.total?` · ${job.assessment.progress || 0}/${job.assessment.total} questões preparadas`:''}`}</p>
            {job.assessment?.imagesReady!=null&&<p>{job.assessment.imagesReady} imagens de apoio disponíveis na biblioteca.</p>}
            {job.assessment?.warning&&<p role="status">{job.assessment.warning}</p>}{job.assessment?.error&&<p role="alert">{job.assessment.error}</p>}
            {job.assessment?.status==='failed'&&<Button size="sm" variant="outline" onClick={()=>retryAssessment(job)}>Tentar somente avaliação novamente — usa créditos IA</Button>}
          </div>}
          {job.error && <p className="text-sm text-amber-500">{job.error}</p>}{job.warning && <p>{job.warning}</p>}
          {job.credits?.deducted != null && <p className="text-sm">Créditos informados pelo Gamma: {job.credits.deducted} consumidos{job.credits.remaining != null ? ` · saldo ${job.credits.remaining}` : ''}.</p>}
          <div className="flex flex-wrap gap-2">
            {job.status === 'completed' && <Button size="sm" onClick={() => { onCreated?.(); setOpen(false); navigate(`/editor/${job.projectId}`); }}>Abrir novo projeto</Button>}
            {['completed', 'preserved'].includes(job.status) && <Button size="sm" variant="outline" onClick={() => download(job)}>Baixar ZIP original</Button>}
            {job.gammaUrl && <a href={job.gammaUrl} target="_blank" rel="noopener noreferrer" className="underline p-2">Abrir no Gamma</a>}
          </div>
        </article>)}
      </section>
      </section></div>
      <footer className="gamma-footer">
      {error && <p role="alert" className="gamma-error">{error}</p>}
      {uncertain && <p role="status" className="gamma-error">Solicitação sem confirmação. Não repetiremos automaticamente. Reabra esta janela para consultar o histórico e confira também sua conta Gamma.</p>}
      <div className="gamma-footer-main"><div className="gamma-footer-summary"><strong>{design?.name || (designRequired?'Escolha um visual':'Visual automático')}</strong><div>{title.trim().length<3||prompt.trim().length<20?'Preencha o título e pelo menos 20 caracteres de conteúdo.':assessmentEnabled?'Slides + 1 avaliação final · usa créditos Gamma e IA SCORMIFY':'Conteúdo pronto · gera um novo projeto · usa créditos Gamma'}</div></div>
      <div className="gamma-footer-actions">{step==='content'?<Button variant="outline" onClick={()=>setStep('design')}>Escolher aparência →</Button>:<Button variant="outline" onClick={()=>setStep('content')}>← Conteúdo</Button>}
      <Button onClick={generate} disabled={busy || documentBusy || uncertain || prompt.length > 100000 || !validCount || (assessmentEnabled && (!validAssessmentCount || !assessmentConfigured)) || configured !== true || (designRequired && !design) || title.trim().length < 3 || prompt.trim().length < 20} data-testid="gamma-generate">{busy ? 'Enviando…' : documentBusy ? 'Lendo arquivo…' : validCount ? `Gerar ${count} ${count===1?'slide':'slides'}` : 'Informe a quantidade'}</Button></div></div>
      </footer>
    </DialogContent></Dialog>
  </>;
}
