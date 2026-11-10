import React, { useCallback, useEffect, useRef, useState } from 'react';
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
  const [narrationReady, setNarrationReady] = useState(false);
  const [narrationAllowed, setNarrationAllowed] = useState(false);
  const [narrate, setNarrate] = useState(false);
  const [narrationText, setNarrationText] = useState('');
  const [voiceId, setVoiceId] = useState('');
  const [voices, setVoices] = useState([]);
  const [voiceSearch, setVoiceSearch] = useState('');
  const [voicesLoading, setVoicesLoading] = useState(false);
  const [voiceError, setVoiceError] = useState('');
  const [allowOtherVoices, setAllowOtherVoices] = useState(false);
  const [moreVoices, setMoreVoices] = useState(false);
  const [musicReady, setMusicReady] = useState(false);
  const [music, setMusic] = useState(false);
  const [musicPrompt, setMusicPrompt] = useState('Trilha instrumental ambiente suave, acolhedora e discreta, adequada para um vídeo educativo, sem voz.');
  const [musicVolume, setMusicVolume] = useState(15);
  const submitting = useRef(false);
  const loadVoices = useCallback(async (search = '') => {
    setVoicesLoading(true); setVoiceError('');
    try {
      const response = await fetch(`${getApiUrl()}/api/runway/voices?search=${encodeURIComponent(search)}`, {headers:authHeaders()});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível carregar as vozes.');
      setVoices(data.voices || []); setMoreVoices(Boolean(data.hasMore)); setVoiceId('');
    } catch (err) { setVoiceError(err.message); }
    finally { setVoicesLoading(false); }
  }, []);
  useEffect(() => { if (narrate) loadVoices(); }, [narrate, loadVoices]);
  useEffect(() => {
    let active = true;
    fetch(`${getApiUrl()}/api/runway/status`, { headers: authHeaders() })
      .then(async response => { if (!response.ok) throw new Error('Não foi possível consultar a integração Runway.'); return response.json(); })
      .then(data => { if (active) { setConfigured(data.configured); setNarrationReady(Boolean(data.narrationConfigured)); setNarrationAllowed(Boolean(data.narrationAllowed)); setMusicReady(Boolean(data.musicConfigured)); } })
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
    if (submitting.current || !configured || !prompt.trim() || (model === 'gen4_turbo' && !image) || (music && (!musicReady || !musicPrompt.trim())) || (narrate && (!narrationText.trim() || !voiceId || !narrationReady || !narrationAllowed))) return;
    submitting.current = true; setBusy(true); onBusyChange(true); setError('');
    try { await onGenerate({ prompt: prompt.trim(), model, duration: Number(duration), aspectRatio, image,
      ...(narrate ? {narration:{enabled:true, text:narrationText.trim(), voiceId, language:'pt-BR', allowOtherVoices}} : {}),
      ...(music ? {music:{enabled:true, prompt:musicPrompt.trim(), volume:musicVolume}} : {}),
    }); }
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
    <fieldset className="space-y-3 rounded border p-3" disabled={busy}>
      <legend className="text-sm font-semibold">Narração em português do Brasil</legend>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={narrate} disabled={busy || !narrationReady || !narrationAllowed} onChange={e => setNarrate(e.target.checked)} />Adicionar narração PT-BR (ElevenLabs)</label>
      {configured !== null && (!narrationReady || !narrationAllowed) && <p className="text-xs text-amber-400">{!narrationAllowed ? 'Sua empresa precisa da permissão ElevenLabs para usar narração.' : 'Narração indisponível: o administrador deve conferir ELEVENLABS_API_KEY, FFmpeg e FFprobe no servidor. A geração sem voz continua disponível.'}</p>}
      {narrate && <>
        <label className="block text-sm">Texto da narração PT-BR<Textarea aria-label="Texto da narração PT-BR" value={narrationText} onChange={e => setNarrationText(e.target.value)} maxLength={600} placeholder="Escreva exatamente o que deve ser falado em português do Brasil." className="mt-1 min-h-[100px]" /></label>
        <p className="text-xs text-muted-foreground">{narrationText.length}/600 caracteres. Revise a fala antes de gerar; não usamos a descrição visual como roteiro automaticamente.</p>
        <label className="block text-xs">Buscar voz<input aria-label="Buscar voz ElevenLabs" value={voiceSearch} onChange={e => setVoiceSearch(e.target.value)} maxLength={80} className="block w-full rounded border bg-background p-2" /></label>
        <Button size="sm" variant="outline" disabled={voicesLoading} onClick={() => loadVoices(voiceSearch)}>Buscar vozes</Button>
        <label className="block text-sm">Voz<select aria-label="Voz da narração PT-BR" value={voiceId} onChange={e => setVoiceId(e.target.value)} disabled={voicesLoading} className="mt-1 block w-full rounded border bg-background p-2">
          <option value="">{voicesLoading ? 'Carregando vozes…' : 'Selecione uma voz'}</option>
          {voices.filter(v => allowOtherVoices || v.brazilian).map(v => <option key={v.id} value={v.id}>{v.name} · {v.brazilian ? 'Brasil' : v.accent || 'sotaque não identificado'}</option>)}
        </select></label>
        {!voicesLoading && !voices.some(v => v.brazilian) && <p className="text-xs text-amber-400">Nenhuma voz identificada como brasileira nesta busca. Adicione uma voz PT-BR à conta ElevenLabs ou amplie a seleção abaixo.</p>}
        {moreVoices && <p className="text-xs">Há mais vozes na conta. Refine a busca pelo nome da voz.</p>}
        <label className="flex gap-2 text-xs"><input type="checkbox" checked={allowOtherVoices} onChange={e => {setAllowOtherVoices(e.target.checked);setVoiceId('');}} />Incluir outras vozes multilíngues — o sotaque brasileiro não é garantido.</label>
        {voices.find(v => v.id === voiceId)?.previewUrl && <audio aria-label="Prévia da voz" src={voices.find(v => v.id === voiceId).previewUrl} controls preload="none" className="w-full" />}
        {voiceError && <p role="alert" className="text-xs text-red-400">{voiceError}</p>}
        <p className="text-xs text-amber-400">A fala consome créditos ElevenLabs além do vídeo Runway. O texto é enviado à ElevenLabs. Se a fala for mais longa, o último quadro será mantido até ela terminar, sem acelerar nem cortar a frase. É voz em off, não sincronização labial.</p>
      </>}
    </fieldset>
    <fieldset className="space-y-2 rounded border p-3" disabled={busy}>
      <legend className="text-sm font-semibold">Trilha sonora instrumental</legend>
      <label className="flex gap-2 text-sm"><input type="checkbox" checked={music} disabled={!musicReady || busy} onChange={e => setMusic(e.target.checked)} />Gerar música de fundo com Runway</label>
      {configured !== null && !musicReady && <p className="text-xs text-amber-400">Requer chave Runway, FFmpeg e FFprobe no servidor.</p>}
      {music && <>
        <label className="block text-sm">Estilo da trilha<Textarea aria-label="Estilo da trilha" value={musicPrompt} onChange={e => setMusicPrompt(e.target.value)} maxLength={1000} /></label>
        <label className="block text-sm">Volume da música: {musicVolume}%<input aria-label="Volume da música" type="range" min="0" max="50" value={musicVolume} onChange={e => setMusicVolume(Number(e.target.value))} className="block w-full" /></label>
        <p className="text-xs text-muted-foreground">Sem voz cantada. Entrada e saída suaves, com redução automática sob a narração. Não cite artistas ou músicas existentes. O volume escolhido fica incorporado no arquivo; para mudar depois, edite a mídia.</p>
        <p className="text-xs text-amber-400">Custo adicional indicativo: aproximadamente 20 créditos Runway por minuto solicitado (mínimo 1 crédito). A duração acompanha o vídeo ou a narração, até 90 s. Confira a tabela oficial antes de gerar. Sem repetição paga automática.</p>
      </>}
    </fieldset>
    <p className="text-xs text-amber-400">Estimativa do vídeo: US$ {(duration * (model === 'gen4_turbo' ? .05 : .12)).toFixed(2)} por geração, sem impostos ou novas tentativas. Valores indicativos; confira a tabela Runway. {narrate ? `Mais ${narrationText.trim().length} caracteres de voz ElevenLabs, cobrados conforme sua conta.` : 'Sem narração selecionada. Escrever PT-BR na descrição da cena não adiciona voz.'}</p>
    <p className="text-xs text-muted-foreground">Gerar consome créditos da API Runway, separados da assinatura do site. O vídeo será armazenado no projeto e inserido neste slide. Não feche o Editor durante o envio; após receber a tarefa, você pode voltar depois para acompanhar.</p>
    {error && <p role="alert" className="text-sm text-red-400">{typeof error === 'string' ? error : 'Confira os parâmetros enviados.'}</p>}
    <Button className="w-full" onClick={generate} disabled={busy || !configured || !prompt.trim() || (model === 'gen4_turbo' && !image) || (music && (!musicReady || !musicPrompt.trim())) || (narrate && (!narrationText.trim() || !voiceId || !narrationReady || !narrationAllowed))} data-testid="generate-runway-video">{busy ? 'Aguarde…' : music ? 'Gerar vídeo com trilha sonora' : narrate ? 'Gerar vídeo com narração PT-BR' : 'Gerar vídeo com Runway'}</Button>
    <section className="border-t pt-3 space-y-2" aria-label="Biblioteca Runway do projeto">
      <div className="flex items-center justify-between gap-2"><h3 className="text-sm font-semibold">Biblioteca Runway deste projeto</h3><Button size="sm" variant="outline" disabled={busy} onClick={refresh}>Atualizar tarefas</Button></div>
      {!jobs.length && <p className="text-xs text-muted-foreground">Nenhum vídeo Runway neste projeto.</p>}
      {jobs.map(job => <div key={job.id} className="rounded border p-2 text-sm space-y-2">
        <p>{job.title} · {({completed:'Concluído',failed:'Falhou',unknown:'Envio não confirmado',submitting:'Enviando',submitted:'Na fila',processing:'Processando',narrating:'Gerando narração PT-BR',music:'Gerando trilha sonora',composing:'Compondo áudio e vídeo'})[job.status] || 'Salvando'}{job.narration && ' · Narração PT-BR'}{job.music && ' · Trilha sonora'}{job.durationActual ? ` · ${Number(job.durationActual).toFixed(1)} s` : ''}</p>
        {job.error && <p role="status" className="text-xs text-amber-400">{job.error}</p>}
        {job.videoUrl && <><video src={getApiUrl() + job.videoUrl} controls preload="none" className="w-full max-h-40" /><Button size="sm" disabled={busy} onClick={() => handleUseVideo(job)}>Inserir este vídeo no slide</Button></>}
        {job.audioUrl && <audio aria-label="Narração gerada" src={getApiUrl() + job.audioUrl} controls preload="none" className="w-full" />}
        {job.musicUrl && <audio aria-label="Trilha gerada" src={getApiUrl() + job.musicUrl} controls preload="none" className="w-full" />}
      </div>)}
    </section>
  </div>;
}
