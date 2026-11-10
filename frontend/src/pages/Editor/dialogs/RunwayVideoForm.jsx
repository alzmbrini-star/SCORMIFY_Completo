import React, { useEffect, useRef, useState } from 'react';
import { Button } from '../../../components/ui/button';
import { Textarea } from '../../../components/ui/textarea';
import { authHeaders } from '../../../contexts/AuthContext';
import { getApiUrl } from '../../../utils/apiUrl';

export default function RunwayVideoForm({ onGenerate, onUseVideo, onRefresh, projectId, context, onBusyChange }) {
  const [configured, setConfigured] = useState(null);
  const [prompt, setPrompt] = useState('');
  const [model, setModel] = useState('gen4.5');
  const [duration, setDuration] = useState(5);
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const [image, setImage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [jobs, setJobs] = useState([]);
  const submitting = useRef(false);
  useEffect(() => {
    let active = true;
    fetch(`${getApiUrl()}/api/runway/status`, { headers: authHeaders() })
      .then(async response => { if (!response.ok) throw new Error('Não foi possível consultar a integração Runway.'); return response.json(); })
      .then(data => { if (active) setConfigured(data.configured); })
      .catch(err => { if (active) { setConfigured(false); setError(err.message); } });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    let active = true;
    if (projectId) fetch(`${getApiUrl()}/api/runway/projects/${projectId}/status`, { headers: authHeaders() })
      .then(async res => { if (!res.ok) throw new Error('Não foi possível carregar a biblioteca Runway.'); return res.json(); })
      .then(data => { if (active) setJobs(data.videos || []); }).catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [projectId]);
  const generate = async () => {
    if (submitting.current || !configured || !prompt.trim() || (model === 'gen4_turbo' && !image)) return;
    submitting.current = true; setBusy(true); onBusyChange(true); setError('');
    try { await onGenerate({ prompt: prompt.trim(), model, duration: Number(duration), aspectRatio, image }); }
    catch (err) { setError(err.response?.data?.detail || err.message || 'Não foi possível iniciar o vídeo.'); }
    finally { submitting.current = false; setBusy(false); onBusyChange(false); }
  };
  const refresh = async () => {
    setBusy(true); onBusyChange(true); setError('');
    try { const data = await onRefresh(); setJobs(data.videos || []); }
    catch (_) { setError('Não foi possível atualizar as tarefas. Tente novamente; atualizar não solicita outra geração.'); }
    finally { setBusy(false); onBusyChange(false); }
  };
  const upload = event => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 3 * 1024 * 1024) {
      setError('Escolha PNG, JPEG ou WebP de até 3 MB.'); return;
    }
    const reader = new FileReader();
    reader.onload = () => { setImage(String(reader.result)); setError(''); };
    reader.onerror = () => setError('Não foi possível ler a imagem.');
    reader.readAsDataURL(file);
  };
  const handleUseVideo = async job => {
    setBusy(true); onBusyChange(true); setError('');
    try { await onUseVideo(job); }
    catch (_) { setError('Não foi possível inserir o vídeo. Ele continua na biblioteca; tente novamente.'); }
    finally { setBusy(false); onBusyChange(false); }
  };
  return <div className="space-y-3 py-3" data-testid="runway-video-form">
    {configured === null && <p>Verificando integração Runway…</p>}
    {configured === false && <p role="alert" className="text-sm text-amber-400">Runway indisponível. Um administrador deve cadastrar RUNWAYML_API_SECRET no servidor e adicionar créditos na API Runway. Não cole a chave aqui.</p>}
    <label className="block text-sm">Modelo
      <select aria-label="Modelo Runway" value={model} disabled={busy} onChange={e => setModel(e.target.value)} className="mt-1 w-full rounded border bg-background p-2">
        <option value="gen4.5">Gen-4.5 — descrição ou imagem</option>
        <option value="gen4_turbo">Gen-4 Turbo — animar imagem (econômico)</option>
      </select>
    </label>
    <label className="block text-sm">Descreva a cena
      <Textarea value={prompt} disabled={busy} onChange={e => setPrompt(e.target.value)} maxLength={1000} className="mt-1 min-h-[100px]" placeholder="Descreva o ambiente, os personagens e os movimentos desejados." />
    </label>
    <Button type="button" size="sm" variant="outline" disabled={busy || !context} onClick={() => setPrompt(`${context}\nCena: `.slice(0, 1000))}>Usar contexto do slide</Button>
    <label className="block text-sm">Imagem inicial {model === 'gen4_turbo' ? '(obrigatória)' : '(opcional)'}
      <input aria-label="URL da imagem inicial" type="url" disabled={busy} value={image.startsWith('data:') ? '' : image} onChange={e => setImage(e.target.value)} placeholder="https://… imagem pública" className="mt-1 w-full rounded border bg-background p-2" />
      <input aria-label="Enviar imagem inicial" type="file" accept="image/png,image/jpeg,image/webp" disabled={busy} onChange={upload} className="mt-2 block max-w-full text-xs" />
    </label>
    {image && <div className="flex items-center gap-2"><img src={image} alt="Imagem inicial" className="h-16 w-24 object-contain" /><Button size="sm" variant="outline" disabled={busy} onClick={() => setImage('')}>Remover imagem</Button></div>}
    <div className="grid grid-cols-2 gap-2">
      <label className="text-sm">Duração<select aria-label="Duração Runway" value={duration} disabled={busy} onChange={e => setDuration(Number(e.target.value))} className="block w-full rounded border bg-background p-2"><option value={5}>5 segundos</option><option value={10}>10 segundos</option></select></label>
      <label className="text-sm">Formato<select aria-label="Formato Runway" value={aspectRatio} disabled={busy} onChange={e => setAspectRatio(e.target.value)} className="block w-full rounded border bg-background p-2"><option value="16:9">Horizontal</option><option value="9:16">Vertical</option></select></label>
    </div>
    <p className="text-xs text-amber-400">Estimativa: US$ {(duration * (model === 'gen4_turbo' ? .05 : .12)).toFixed(2)} por geração, sem impostos ou novas tentativas. Valores indicativos; confira a tabela Runway. Estes modelos geram vídeo sem narração. Escrever PT-BR no pedido não adiciona voz.</p>
    <p className="text-xs text-muted-foreground">Gerar consome créditos da API Runway, separados da assinatura do site. O vídeo será armazenado no projeto e inserido neste slide. Não feche o Editor durante o envio; após receber a tarefa, você pode voltar depois para acompanhar.</p>
    {error && <p role="alert" className="text-sm text-red-400">{typeof error === 'string' ? error : 'Confira os parâmetros enviados.'}</p>}
    <Button className="w-full" onClick={generate} disabled={busy || !configured || !prompt.trim() || (model === 'gen4_turbo' && !image)} data-testid="generate-runway-video">{busy ? 'Aguarde…' : 'Gerar vídeo com Runway'}</Button>
    <section className="border-t pt-3 space-y-2" aria-label="Biblioteca Runway do projeto">
      <div className="flex items-center justify-between gap-2"><h3 className="text-sm font-semibold">Biblioteca Runway deste projeto</h3><Button size="sm" variant="outline" disabled={busy} onClick={refresh}>Atualizar tarefas</Button></div>
      {!jobs.length && <p className="text-xs text-muted-foreground">Nenhum vídeo Runway neste projeto.</p>}
      {jobs.map(job => <div key={job.id} className="rounded border p-2 text-sm space-y-2">
        <p>{job.title} · {({completed:'Concluído',failed:'Falhou',unknown:'Envio não confirmado',submitting:'Enviando',submitted:'Na fila',processing:'Processando'})[job.status] || 'Salvando'}</p>
        {job.error && <p role="status" className="text-xs text-amber-400">{job.error}</p>}
        {job.videoUrl && <><video src={getApiUrl() + job.videoUrl} controls preload="none" className="w-full max-h-40" /><Button size="sm" disabled={busy} onClick={() => handleUseVideo(job)}>Inserir este vídeo no slide</Button></>}
      </div>)}
    </section>
  </div>;
}
