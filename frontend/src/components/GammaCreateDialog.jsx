import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authHeaders, useAuth } from '../contexts/AuthContext';
import { getApiUrl } from '../utils/apiUrl';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import CompanySelector from './CompanySelector';
import GammaDesignPicker from './GammaDesignPicker';

const API = getApiUrl();
const ACTIVE = ['pending', 'submitting'];
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
  const [companyId, setCompanyId] = useState('');
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [design, setDesign] = useState(null);
  const [designRequired, setDesignRequired] = useState(false);
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
        if (!cancelled) { setConfigured(config.configured); setJobs(updated); }
      } catch (e) { if (!cancelled) setError(e.message); }
      if (!cancelled) timer = setTimeout(refresh, 10000);
    };
    refresh();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [open, allowed]);

  if (!allowed) return null;
  const generate = async () => {
    if (submitting.current || busy || uncertain) return;
    submitting.current = true;
    setBusy(true); setError('');
    requestId.current = requestId.current || crypto.randomUUID();
    try {
      const row = await api('/generate', { method: 'POST', body: JSON.stringify({ requestId: requestId.current, title: title.trim(), prompt: prompt.trim(), companyId: companyId || null,
        ...(design?.kind === 'theme' ? {themeId: design.id} : design?.kind === 'template' ? {templateId: design.id} : {}) }) });
      setJobs(previous => [row, ...previous.filter(item => item.id !== row.id)]);
      if (row.status === 'unknown') setUncertain(true);
      else { requestId.current = null; setTitle(''); setPrompt(''); }
      onCreated?.();
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
  const labels = { submitting: 'Enviando ao Gamma', pending: 'Gerando / importando', completed: 'Concluído', failed: 'Falhou', unknown: 'Sem confirmação — confira no Gamma', preserved: 'Slides existentes preservados' };
  return <>
    <Button variant="outline" onClick={() => setOpen(true)} data-testid="gamma-create-open">Criar com Gamma</Button>
    <Dialog open={open} onOpenChange={next => {setOpen(next); if (!next) {setDesign(null); setDesignRequired(false);}}}><DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
      <DialogHeader><DialogTitle>Criar 5 slides com Gamma</DialogTitle><DialogDescription>Português do Brasil · novo projeto independente · qualidade standard</DialogDescription></DialogHeader>
      <p className="text-sm text-muted-foreground">Usa créditos da conta Gamma configurada no servidor. Preserva o visual como imagem-base por slide; o texto da imagem não será editável separadamente. Depois, acrescente textos e interações no Editor. Seus cursos existentes não serão alterados.</p>
      {configured === false && <p role="alert">GAMMA_API_KEY não está configurada no servidor.</p>}
      <label className="space-y-1">Título do curso<Input aria-label="Título Gamma" maxLength={160} value={title} onChange={e => setTitle(e.target.value)} /></label>
      <label className="space-y-1">Conteúdo dos cinco slides<textarea aria-label="Conteúdo Gamma" className="w-full min-h-28 p-3 rounded border bg-background" maxLength={10000} value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Tema, público, objetivos e tópicos. Inclua o conteúdo que deseja ensinar." /></label>
      <CompanySelector value={companyId} onChange={setCompanyId} testIdPrefix="gamma-company" />
      <GammaDesignPicker api={api} value={design} onChange={(selection, required) => {setDesign(selection); if (required !== undefined) setDesignRequired(required);}} disabled={busy || uncertain || configured !== true}/>
      <Button onClick={generate} disabled={busy || uncertain || configured !== true || (designRequired && !design) || title.trim().length < 3 || prompt.trim().length < 20} data-testid="gamma-generate">{busy ? 'Enviando uma única solicitação…' : 'Gerar em novo projeto — usa créditos Gamma'}</Button>
      {error && <p role="alert" className="text-amber-500">{error}</p>}
      {uncertain && <p role="status">Solicitação sem confirmação. Não repetiremos automaticamente. Reabra esta janela para consultar o histórico e confira também sua conta Gamma.</p>}
      <section className="space-y-3" aria-label="Histórico Gamma"><h3 className="font-semibold">Gerações recentes</h3>
        {jobs.map(job => <article key={job.id} className="border rounded p-3 space-y-2" data-testid="gamma-job">
          <strong>{job.title}</strong><p role="status">{labels[job.status] || job.status}{job.progress?.percent != null ? ` · ${job.progress.percent}%` : ''}{job.actualSlides ? ` · ${job.actualSlides} slides` : ''}</p>
          {job.error && <p className="text-sm text-amber-500">{job.error}</p>}{job.warning && <p>{job.warning}</p>}
          {job.credits?.deducted != null && <p className="text-sm">Créditos informados pelo Gamma: {job.credits.deducted} consumidos{job.credits.remaining != null ? ` · saldo ${job.credits.remaining}` : ''}.</p>}
          <div className="flex flex-wrap gap-2">
            {job.status === 'completed' && <Button size="sm" onClick={() => { onCreated?.(); setOpen(false); navigate(`/editor/${job.projectId}`); }}>Abrir novo projeto</Button>}
            {['completed', 'preserved'].includes(job.status) && <Button size="sm" variant="outline" onClick={() => download(job)}>Baixar ZIP original</Button>}
            {job.gammaUrl && <a href={job.gammaUrl} target="_blank" rel="noopener noreferrer" className="underline p-2">Abrir no Gamma</a>}
          </div>
        </article>)}
      </section>
    </DialogContent></Dialog>
  </>;
}
