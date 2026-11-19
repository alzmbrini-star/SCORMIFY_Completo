import React,{useEffect,useState} from 'react';
import {Button} from './ui/button';

const money=(value,currency)=>new Intl.NumberFormat('pt-BR',{style:'currency',currency}).format(value);
export const brlCeiling=(usd,rate)=>(Math.ceil((usd*rate-1e-9)*100)/100).toFixed(2);
export function usdWithinBrl(value,rate){
 if(value===''||!Number.isFinite(Number(value))||Number(value)<0||!Number.isFinite(rate)||rate<=0)return null;
 return Math.floor((Number(value)/rate+1e-9)*100)/100;
}

export default function FilmBudget({quote,locked,request,budgetConsent,setBudgetConsent,onApprove,inputClass}){
 const [fx,setFx]=useState(null),[loading,setLoading]=useState(true);
 const [usdLimit,setUsdLimit]=useState(quote.suggestedCeilingUsd),[brlLimit,setBrlLimit]=useState('');
 const valid=fx?.available&&Number.isFinite(fx.rate)&&fx.rate>=.1&&fx.rate<=100&&/^\d{4}-\d{2}-\d{2}$/.test(fx.asOfDate||'');
 const acceptRate=data=>{setFx(data);setBrlLimit(data.available&&Number.isFinite(data.rate)&&usdLimit!==null?brlCeiling(usdLimit,data.rate):'');};
 useEffect(()=>{
  let active=true;
  request('/films/exchange-rate').then(data=>{if(active)acceptRate(data);})
   .catch(()=>{if(active)setFx({available:false,notice:'Não foi possível consultar a cotação. Tente novamente.'});})
   .finally(()=>{if(active)setLoading(false);});
  return()=>{active=false;};
  // Quote changes remount the component; merely reading currency never edits the film.
  // eslint-disable-next-line react-hooks/exhaustive-deps
 },[]);
 async function refreshRate(){
  setLoading(true);setBudgetConsent(false);
  try{acceptRate(await request('/films/exchange-rate'));}
  catch(_){setFx({available:false,notice:'Não foi possível consultar a cotação. Tente novamente.'});}
  finally{setLoading(false);}
 }
 const asBrl=value=>valid?money(value*fx.rate,'BRL'):'Cotação indisponível';
 const canApprove=valid&&!loading&&!locked&&budgetConsent&&usdLimit!==null&&Number.isFinite(usdLimit)&&usdLimit>=quote.estimatedUsd&&usdLimit<=1000;
 return <div className="space-y-3" data-testid="film-budget-brl">
  <p className="text-sm">{quote.duration}s · tabela {quote.ratesVersion}</p>
  <div className="rounded border border-amber-700/70 bg-slate-950/60 p-3 text-xs space-y-2" aria-label="Cotação usada no orçamento">
   {loading?<p role="status">Consultando cotação oficial, sem gerar mídias…</p>:valid?<>
    <p className="font-semibold text-amber-100">Cotação: US$ 1 = R$ {fx.rate.toLocaleString('pt-BR',{minimumFractionDigits:4,maximumFractionDigits:4})}</p>
    <p>Data da cotação: {fx.asOfDate.split('-').reverse().join('/')}. Pode ser o último dia útil disponível.</p>
    <a href="https://dadosabertos.bcb.gov.br/dataset/1-taxa-de-cambio---livre---dolar-americano-venda---diario" target="_blank" rel="noreferrer" className="underline">Banco Central do Brasil · dólar venda (SGS 1)</a>
    {fx.stale&&<p role="status" className="text-amber-200">{fx.notice}</p>}
   </>:<p role="status" className="text-amber-200">{fx?.notice || 'Cotação em reais indisponível. Não será usada uma taxa fixa.'}</p>}
   <Button type="button" variant="outline" disabled={locked||loading} onClick={refreshRate}>Consultar cotação novamente</Button>
   <p className="text-slate-400">Consulta compartilhada por até 10 minutos. Referência estimada, não câmbio do cartão.</p>
  </div>
  {quote.items.map(item=><div key={item.label} className="text-xs flex justify-between gap-2"><span>{item.label}<small className="block text-slate-400">{item.quantity} {item.unit}</small></span><span className="text-right shrink-0"><strong className="block text-sm">{asBrl(item.usd)}</strong><small className="block text-slate-400">{money(item.usd,'USD')}</small></span></div>)}
  <div className="rounded bg-amber-950/50 p-3"><p className="font-bold text-lg" data-testid="film-budget-total-brl">Estimativa restante: {asBrl(quote.estimatedUsd)}</p><p className="text-xs text-slate-300">Referência: {money(quote.estimatedUsd,'USD')}</p></div>
  <p className="text-xs text-slate-300">Conversão aproximada, sem IOF, spread, impostos ou infraestrutura. Os provedores cobram em dólares; a fatura em reais pode variar. {quote.disclaimer}</p>
  <label className="block text-sm font-semibold">Limite para aprovação (R$)<input aria-label="Limite do orçamento do filme" className={inputClass} type="number" min={valid?brlCeiling(quote.estimatedUsd,fx.rate):0} max={valid?brlCeiling(1000,fx.rate):0} step="0.01" disabled={locked||loading||!valid} value={brlLimit} onChange={e=>{setBrlLimit(e.target.value);setUsdLimit(usdWithinBrl(e.target.value,fx?.rate));setBudgetConsent(false);}}/></label>
  <p className="text-xs text-slate-300" data-testid="film-budget-limit-usd">Limite equivalente enviado ao servidor: {usdLimit===null?'—':money(usdLimit,'USD')}. A conversão do limite digitado é arredondada para baixo em centavos de dólar, sem exceder o valor em reais informado.</p>
  <label className="flex gap-2 text-xs"><input aria-label="Confirmar orçamento do filme" type="checkbox" checked={budgetConsent} disabled={locked||loading||!valid} onChange={e=>setBudgetConsent(e.target.checked)}/>Li a estimativa em reais, a cotação e o limite equivalente em dólares. Autorizo as chamadas planejadas desta versão até esse limite em USD; a fatura em reais pode variar.</label>
  <Button data-testid="film-approve-budget" disabled={!canApprove} onClick={()=>onApprove(usdLimit)}>Aprovar orçamento — ainda não gera mídias</Button>
 </div>;
}
