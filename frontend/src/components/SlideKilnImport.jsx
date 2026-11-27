import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { getApiUrl } from '../utils/apiUrl';
import { Button } from './ui/button';

const brl = n => Number(n).toLocaleString('pt-BR', {style:'currency', currency:'BRL'});
const running = job => ['processing','recovering'].includes(job?.status);
const labels = {awaiting_approval:'Aguardando aprovação',processing:'Em andamento',recovering:'Recuperando pacote',
  completed:'Concluído',recoverable:'Importação precisa de atenção',unknown:'Sem confirmação',
  failed:'Falha',interrupted:'Processamento interrompido',expired:'Orçamento expirado'};

export default function SlideKilnImport({ companyId, onComplete }) {
  const [config,setConfig]=useState(null),[job,setJob]=useState(null),[jobs,setJobs]=useState([]),[busy,setBusy]=useState(false);
  const [error,setError]=useState(''),[cost,setCost]=useState(false),[rights,setRights]=useState(false);
  const alive=useRef(true), timer=useRef(), current=useRef(null);
  const api=getApiUrl()+'/api/ppt/slidekiln';
  const remember = value => {current.current=value;if(alive.current)setJob(value);};
  const refreshHistory=async()=>{
    const r=await axios.get(api+'/jobs');
    const list=Array.isArray(r.data)?r.data:[];
    if(alive.current)setJobs(list);
    return list;
  };
  const poll=async(id,openWhenComplete=false)=>{
    clearTimeout(timer.current);
    try {
      const r=await axios.get(api+'/'+id);
      if(!alive.current||current.current?.id!==id)return;
      remember(r.data);
      if(r.data.status==='completed') {
        await refreshHistory();
        if(openWhenComplete&&alive.current)onComplete(r.data.projectId);
      } else if(running(r.data))timer.current=setTimeout(()=>poll(id,openWhenComplete),2000);
      else await refreshHistory();
    } catch {
      if(alive.current)setError('Não foi possível atualizar o status. Use Atualizar acompanhamento; não envie o PPT novamente.');
    }
  };
  useEffect(()=>{
    alive.current=true;
    axios.get(api+'/config').then(r=>{if(alive.current)setConfig(r.data);}).catch(()=>{if(alive.current)setError('Não foi possível consultar a integração.');});
    refreshHistory().then(list=>{
      if(!alive.current||current.current)return;
      const latest=list.find(item=>!['completed','expired'].includes(item.status));
      if(latest){remember(latest);if(running(latest))poll(latest.id);}
    }).catch(()=>{if(alive.current)setError('Não foi possível carregar o acompanhamento. Use Atualizar acompanhamento antes de reenviar o PPT.');});
    return()=>{alive.current=false;clearTimeout(timer.current);};
    // State changes must not restart the subscription.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[api]);
  const selectJob=value=>{setError('');clearTimeout(timer.current);setCost(false);setRights(false);remember(value);poll(value.id);};
  const refresh=async()=>{
    setError('');
    try {await refreshHistory();if(current.current)await poll(current.current.id);}
    catch {if(alive.current)setError('Não foi possível atualizar o acompanhamento. Nenhuma conversão foi solicitada.');}
  };
  const upload=async e=>{
    const f=e.target.files?.[0];e.target.value='';if(!f)return;
    setError('');setCost(false);setRights(false);
    if(!f.name.toLowerCase().endsWith('.pptx')||f.size>32*1024*1024){setError('Envie um PPTX de até 32 MB. Para PPT legado, use o ConvertAPI.');return;}
    setBusy(true);clearTimeout(timer.current);
    try {
      const data=new FormData();data.append('file',f);if(companyId)data.append('company_id',companyId);
      const r=await axios.post(api+'/quote',data);
      if(alive.current){remember(r.data);await refreshHistory();if(running(r.data))poll(r.data.id);}
    } catch(err){if(alive.current)setError(typeof err.response?.data?.detail==='string'?err.response.data.detail:'Não foi possível preparar o orçamento. Nenhuma conversão foi solicitada.');}
    finally{if(alive.current)setBusy(false);}
  };
  const approve=async()=>{
    setBusy(true);setError('');
    try {const r=await axios.post(api+'/'+job.id+'/approve',{approveCost:cost,confirmRights:rights});if(alive.current){remember(r.data);poll(job.id,true);}}
    catch(err){if(alive.current)setError(typeof err.response?.data?.detail==='string'?err.response.data.detail:'Não foi possível confirmar. Atualize o acompanhamento antes de tentar outra conversão.');}
    finally{if(alive.current)setBusy(false);}
  };
  const recover=async()=>{
    setBusy(true);setError('');
    try {const r=await axios.post(api+'/'+job.id+'/recover');if(alive.current){remember(r.data);poll(job.id,true);}}
    catch(err){if(alive.current)setError(typeof err.response?.data?.detail==='string'?err.response.data.detail:'Não foi possível recuperar. Nenhuma nova conversão foi solicitada.');}
    finally{if(alive.current)setBusy(false);}
  };
  const attention=job&&!['awaiting_approval','processing','recovering','completed','expired'].includes(job.status);
  return <section className="space-y-3 text-sm" aria-label="Importar PPTX com SlideKiln">
    <p>Preserva a apresentação em <strong>um bloco interativo</strong>, com navegação interna. Não separa objetos ou slides nativos do Editor. Seus cursos atuais não são alterados.</p>
    <p className="text-muted-foreground">PPTX até 32 MB; ZIP convertido até 24 MB e pacote autocontido até 32 MB. Pacotes maiores usam armazenamento em blocos, sem reduzir a qualidade das mídias. Compatibilidade varia conforme o arquivo.</p>
    {!config?<p>Consultando configuração…</p>:!config.configured?<p role="status">Configure SLIDEKILN_API_KEY no Render. Nunca informe a chave aqui. O ConvertAPI continua disponível.</p>:<>
      {!running(job)&&<label className="block">Preparar orçamento (ainda não converte)<input className="block w-full mt-2" type="file" accept=".pptx" disabled={busy} onChange={upload}/></label>}
    </>}
    <div className="border rounded p-3 space-y-2" aria-label="Acompanhamento das importações SlideKiln">
      <div className="flex flex-wrap items-center justify-between gap-2"><strong>Minhas importações recentes</strong><Button disabled={busy} onClick={refresh}>Atualizar acompanhamento</Button></div>
      <p>As últimas 20 tentativas ficam disponíveis nesta conta após fechar a janela ou recarregar a página. Fechar não cancela o servidor. Atualizar consulta o status e não reconverte.</p>
      {jobs.length===0?<p>Nenhuma tentativa recente encontrada.</p>:<ul className="space-y-2">{jobs.map(item=><li key={item.id} className="flex flex-wrap items-center justify-between gap-2">
        <span className="min-w-0 break-words">{item.filename} — {labels[item.status]||item.status}</span>
        <Button disabled={busy} onClick={()=>selectJob(item)}>Acompanhar {item.filename}</Button>
      </li>)}</ul>}
    </div>
    {job&&<div className={'border rounded p-3 space-y-2 '+(attention?'border-amber-500':'')} aria-label="Detalhes da importação">
      <p><strong>{job.filename}</strong> — {job.slides} slides dentro do bloco.</p>
      <p><strong>{labels[job.status]||job.status}</strong></p>
      {job.status==='awaiting_approval'&&job.budget&&<>
        <p>Limite estimado: <strong>{brl(job.budget.maxBrl)}</strong> (US$ {Number(job.budget.maxUsd).toFixed(2)}).</p>
        <p>US$ 1 = {brl(job.budget.exchange.rate)} · cotação {job.budget.exchange.asOfDate} · Banco Central{job.budget.exchange.stale?' · última consulta válida':''}.</p>
        <p>{job.budget.notice}</p>
        <label className="flex gap-2"><input type="checkbox" checked={cost} onChange={e=>setCost(e.target.checked)}/>Aprovo esta conversão e o limite estimado acima, mesmo se exceder a franquia.</label>
        <label className="flex gap-2"><input type="checkbox" checked={rights} onChange={e=>setRights(e.target.checked)}/>Tenho os direitos necessários para enviar o conteúdo, fontes e mídias ao SlideKiln.</label>
        <Button disabled={busy||!cost||!rights||!config?.configured||!config?.canApprove} onClick={approve}>{busy?'Confirmando…':'Aprovar e converter este arquivo'}</Button>
        {!config?.canApprove&&<p>A aprovação de uso da conta requer Super Admin.</p>}
      </>}
      {job.status!=='awaiting_approval'&&<p role={attention?'alert':'status'}>{job.message||'Consultando o processamento…'}</p>}
      <p className="break-all">Identificador: {job.id}</p>
      {job.canRecover&&<><p>A recuperação reutiliza o resultado anterior e cria somente um novo projeto. Não solicita outra conversão ao SlideKiln. O pacote precisa estar salvo no SCORMIFY ou ainda disponível no prazo de retenção de 24 horas do provedor.</p><Button disabled={busy} onClick={recover}>Recuperar pacote existente — sem reconverter</Button></>}
      {job.status==='completed'&&job.projectId&&<Button onClick={()=>onComplete(job.projectId)}>Abrir novo projeto no Editor</Button>}
      {running(job)&&<p>Não envie novamente. Fechar a janela não cancela a operação; reabra Import PPT → SlideKiln para acompanhar.</p>}
    </div>}
    {error&&<p role="alert" className="text-red-400">{error}</p>}
  </section>;
}
