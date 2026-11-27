import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { getApiUrl } from '../utils/apiUrl';
import { Button } from './ui/button';

const brl = n => Number(n).toLocaleString('pt-BR', {style:'currency', currency:'BRL'});
export default function SlideKilnImport({ companyId, onComplete }) {
  const [config,setConfig]=useState(null),[job,setJob]=useState(null),[busy,setBusy]=useState(false);
  const [error,setError]=useState(''),[cost,setCost]=useState(false),[rights,setRights]=useState(false);
  const alive=useRef(true), timer=useRef();
  const api=getApiUrl()+'/api/ppt/slidekiln';
  useEffect(()=>{alive.current=true;axios.get(api+'/config').then(r=>{if(alive.current)setConfig(r.data);}).catch(()=>{if(alive.current)setError('Não foi possível consultar a integração.');});return()=>{alive.current=false;clearTimeout(timer.current);};},[api]);
  const poll=async id=>{try{const r=await axios.get(api+'/'+id);if(!alive.current)return;setJob(r.data);if(r.data.status==='completed'){onComplete(r.data.projectId);return;}if(r.data.status==='processing')timer.current=setTimeout(()=>poll(id),2000);}catch{if(alive.current)setError('Sem confirmação. Não envie novamente: anote o identificador e confira o histórico SlideKiln.');}};
  const upload=async e=>{const f=e.target.files?.[0];e.target.value='';if(!f)return;setError('');setCost(false);setRights(false);if(!f.name.toLowerCase().endsWith('.pptx')||f.size>32*1024*1024){setError('Envie um PPTX de até 32 MB. Para PPT legado, use o ConvertAPI.');return;}setBusy(true);try{const data=new FormData();data.append('file',f);if(companyId)data.append('company_id',companyId);const r=await axios.post(api+'/quote',data);if(alive.current)setJob(r.data);}catch(err){if(alive.current)setError(typeof err.response?.data?.detail==='string'?err.response.data.detail:'Não foi possível preparar o orçamento. Nenhuma conversão foi solicitada.');}finally{if(alive.current)setBusy(false);}};
  const approve=async()=>{setBusy(true);setError('');try{const r=await axios.post(api+'/'+job.id+'/approve',{approveCost:cost,confirmRights:rights});if(alive.current){setJob(r.data);poll(job.id);}}catch(err){if(alive.current)setError(typeof err.response?.data?.detail==='string'?err.response.data.detail:'Não foi possível confirmar. Consulte o histórico antes de tentar outra conversão.');}finally{if(alive.current)setBusy(false);}};
  return <section className="space-y-3 text-sm" aria-label="Importar PPTX com SlideKiln">
    <p>Preserva a apresentação em <strong>um bloco interativo</strong>, com navegação interna. Não separa objetos ou slides nativos do Editor. Seus cursos atuais não são alterados.</p>
    <p className="text-muted-foreground">PPTX até 32 MB; pacote final autocontido até 10 MB. Vídeos grandes podem exceder esse limite após conversão. Compatibilidade varia conforme o arquivo.</p>
    {!config?<p>Consultando configuração…</p>:!config.configured?<p role="status">Configure SLIDEKILN_API_KEY no Render. Nunca informe a chave aqui. O ConvertAPI continua disponível.</p>:<>
      {(!job||job.status==='awaiting_approval')&&<label className="block">Preparar orçamento (ainda não converte)<input className="block w-full mt-2" type="file" accept=".pptx" disabled={busy} onChange={upload}/></label>}
      {job&&<div className="border rounded p-3 space-y-2">
        <p><strong>{job.filename}</strong> — {job.slides} slides dentro do bloco.</p>
        <p>Limite estimado: <strong>{brl(job.budget.maxBrl)}</strong> (US$ {job.budget.maxUsd.toFixed(2)}).</p>
        <p>US$ 1 = {brl(job.budget.exchange.rate)} · cotação {job.budget.exchange.asOfDate} · Banco Central{job.budget.exchange.stale?' · última consulta válida':''}.</p>
        <p>{job.budget.notice}</p>
        {job.status==='awaiting_approval'?<>
          <label className="flex gap-2"><input type="checkbox" checked={cost} onChange={e=>setCost(e.target.checked)}/>Aprovo esta conversão e o limite estimado acima, mesmo se exceder a franquia.</label>
          <label className="flex gap-2"><input type="checkbox" checked={rights} onChange={e=>setRights(e.target.checked)}/>Tenho os direitos necessários para enviar o conteúdo, fontes e mídias ao SlideKiln.</label>
          <Button disabled={busy||!cost||!rights||!config.canApprove} onClick={approve}>{busy?'Confirmando…':'Aprovar e converter este arquivo'}</Button>
          {!config.canApprove&&<p>A aprovação de uso da conta requer Super Admin.</p>}
        </>:<><p role="status">{job.message||'Processando a conversão autorizada…'}</p><p>Identificador: {job.id}</p><p>Não envie novamente. Fechar a janela não cancela a chamada já autorizada.</p></>}
      </div>}
    </>}
    {error&&<p role="alert" className="text-red-400">{error}</p>}
  </section>;
}
