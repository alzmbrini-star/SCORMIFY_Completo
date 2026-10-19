import React, { useEffect, useRef, useState } from 'react';
import { Button } from '../../../components/ui/button';
import { Textarea } from '../../../components/ui/textarea';
import { authHeaders } from '../../../contexts/AuthContext';
import { getApiUrl } from '../../../utils/apiUrl';

export default function KlingVideoForm({ onGenerate, context, onBusyChange }) {
  const [configured, setConfigured] = useState(null);
  const [prompt, setPrompt] = useState('');
  const [duration, setDuration] = useState(5);
  const [resolution, setResolution] = useState('720p');
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const [audio, setAudio] = useState('off');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const submitting = useRef(false);
  useEffect(() => {
    let active = true;
    fetch(`${getApiUrl()}/api/kling/status`, { headers: authHeaders() })
      .then(async response => {
        if (!response.ok) throw new Error('Não foi possível consultar a configuração do Kling.');
        return response.json();
      }).then(result => { if (active) setConfigured(Boolean(result.configured)); })
      .catch(err => { if (active) { setConfigured(false); setError(err.message); } });
    return () => { active = false; };
  }, []);
  const generate = async () => {
    if (submitting.current || !configured || !prompt.trim()) return;
    submitting.current = true; setBusy(true); onBusyChange(true); setError('');
    try {
      await onGenerate({ prompt:prompt.trim(), duration:Number(duration), resolution, aspectRatio, audio });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : err.message || 'Não foi possível iniciar o vídeo.');
    } finally {
      submitting.current = false; setBusy(false); onBusyChange(false);
    }
  };
  return <div className="space-y-4 py-3" data-testid="kling-video-form">
    {configured === null && <p className="text-xs text-muted-foreground">Verificando integração Kling…</p>}
    {configured === false && !error && <p role="alert" className="text-sm text-amber-400">Kling não configurado. Um administrador deve configurar KLING_API_KEY no backend. Não cole chaves aqui.</p>}
    <label className="block text-sm">Descreva a cena
      <Textarea value={prompt} onChange={e => setPrompt(e.target.value)} maxLength={3000} disabled={busy}
        className="mt-2 min-h-[120px]" placeholder="Descreva personagens, ambiente, ações, enquadramento e objetivo didático." data-testid="kling-prompt" />
    </label>
    <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
      <Button type="button" size="sm" variant="outline" disabled={busy || !context} onClick={() => setPrompt(`${context}\n\nCena: `.slice(0,3000))}>Usar contexto do slide</Button>
      <span>{prompt.length}/3000</span>
    </div>
    <div className="grid grid-cols-2 gap-3">
      {[
        ['Duração', duration, setDuration, [['5','5 segundos'],['10','10 segundos'],['15','15 segundos']]],
        ['Resolução', resolution, setResolution, [['720p','720p'],['1080p','1080p']]],
        ['Formato', aspectRatio, setAspectRatio, [['16:9','Horizontal · 16:9'],['9:16','Vertical · 9:16'],['1:1','Quadrado · 1:1']]],
        ['Áudio', audio, setAudio, [['off','Sem áudio'],['native','Áudio nativo Kling']]],
      ].map(([label,value,change,options]) => <label key={label} className="text-xs">{label}
        <select aria-label={label} className="mt-1 w-full rounded border border-input bg-background p-2" value={value} onChange={e => change(e.target.value)} disabled={busy}>
          {options.map(([id,text]) => <option key={id} value={id}>{text}</option>)}
        </select>
      </label>)}
    </div>
    <p className="text-xs text-amber-400">Ao clicar em Gerar, você solicita uma geração que pode consumir créditos Kling conforme sua conta. Pode levar alguns minutos. O vídeo será salvo no projeto e inserido neste slide; não é necessário manter este diálogo aberto após o envio.</p>
    {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
    <Button type="button" className="w-full" disabled={busy || !configured || !prompt.trim()} onClick={generate} data-testid="generate-kling-video">
      {busy ? 'Enviando ao Kling…' : 'Gerar vídeo com Kling'}
    </Button>
  </div>;
}
