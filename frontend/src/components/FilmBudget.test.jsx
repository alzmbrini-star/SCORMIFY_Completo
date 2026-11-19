import React,{act,useState} from 'react';
import {createRoot} from 'react-dom/client';
import FilmBudget,{brlCeiling,usdWithinBrl} from './FilmBudget';
jest.mock('./ui/button',()=>({Button:({variant,...p})=><button {...p}/>}));
let host,root,request,approve;
const fx={available:true,rate:5.8102,asOfDate:'2026-11-18',stale:false};
const quote={id:'q',duration:60,ratesVersion:'test',estimatedUsd:.01,suggestedCeilingUsd:.02,
 items:[{label:'Voz PT-BR',quantity:84,unit:'caracteres',usd:.01},{label:'Mídias reaproveitadas',quantity:20,unit:'mídias',usd:0}],disclaimer:'Estimativa em USD.'};
function View({q=quote,locked=false}){const [consent,setConsent]=useState(false);return <FilmBudget quote={q} locked={locked} request={request} onApprove={approve} budgetConsent={consent} setBudgetConsent={setConsent} inputClass=""/>;}
beforeEach(()=>{global.IS_REACT_ACT_ENVIRONMENT=true;host=document.createElement('div');document.body.appendChild(host);root=createRoot(host);request=jest.fn(async()=>fx);approve=jest.fn();});
afterEach(()=>{act(()=>root.unmount());host.remove();jest.restoreAllMocks();});
async function render(props={}){await act(async()=>root.render(<View {...props}/>));}
function enter(value){act(()=>{const e=host.querySelector('[aria-label="Limite do orçamento do filme"]');Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value').set.call(e,value);e.dispatchEvent(new Event('input',{bubbles:true}));});}
function confirm(){act(()=>host.querySelector('[aria-label="Confirmar orçamento do filme"]').click());}

test('reais are primary, USD is preserved and source and effective date are explicit',async()=>{
 await render();expect(host.textContent).toMatch(/Estimativa restante: R\$\s*0,06/);
 expect(host.textContent).toMatch(/Referência: US\$\s*0,01/);
 expect(host.textContent).toContain('5,8102');expect(host.textContent).toContain('18/11/2026');expect(host.textContent).toContain('Banco Central');
 expect(host.querySelector('[aria-label="Limite do orçamento do filme"]').value).toBe('0.12');
 expect(request.mock.calls).toEqual([['/films/exchange-rate']]);expect(approve).not.toHaveBeenCalled();
 expect(host.querySelector('[data-testid="film-approve-budget"]').disabled).toBe(true);
});

test('explicit approval sends only the USD equivalent, never the reais amount',async()=>{
 await render();enter('10.00');confirm();
 await act(async()=>host.querySelector('[data-testid="film-approve-budget"]').click());
 expect(approve).toHaveBeenCalledWith(1.72);
 expect(1.72*fx.rate).toBeLessThanOrEqual(10);
});

test('invalid, empty and under-budget BRL limits never authorize, including zero quotes',async()=>{
 await render();for(const value of ['', '-1','0.01']){enter(value);confirm();expect(host.querySelector('[data-testid="film-approve-budget"]').disabled).toBe(true);}
 expect(approve).not.toHaveBeenCalled();
});

test('zero estimate still needs an explicit budget confirmation',async()=>{
 await render({q:{...quote,id:'zero',estimatedUsd:0,suggestedCeilingUsd:0}});
 expect(host.querySelector('[aria-label="Limite do orçamento do filme"]').value).toBe('0.00');
 expect(host.querySelector('[data-testid="film-approve-budget"]').disabled).toBe(true);
 confirm();expect(host.querySelector('[data-testid="film-approve-budget"]').disabled).toBe(false);
 enter('');confirm();expect(host.querySelector('[data-testid="film-approve-budget"]').disabled).toBe(true);
});

test('failed currency lookup shows no fabricated BRL conversion and blocks a new approval',async()=>{
 request.mockRejectedValue(new Error('unavailable'));await render();
 expect(host.textContent).toContain('Cotação indisponível');expect(host.textContent).toMatch(/US\$\s*0,01/);
 expect(host.querySelector('[aria-label="Limite do orçamento do filme"]').disabled).toBe(true);
 expect(host.querySelector('[data-testid="film-approve-budget"]').disabled).toBe(true);expect(approve).not.toHaveBeenCalled();
});

test('refresh clears local confirmation without posting or changing the storyboard',async()=>{
 await render();confirm();expect(host.querySelector('[aria-label="Confirmar orçamento do filme"]').checked).toBe(true);
 await act(async()=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent==='Consultar cotação novamente').click());
 expect(host.querySelector('[aria-label="Confirmar orçamento do filme"]').checked).toBe(false);
 expect(request.mock.calls.every(args=>args.length===1&&args[0]==='/films/exchange-rate')).toBe(true);expect(approve).not.toHaveBeenCalled();
});

test('stale valid reference is labeled and locked films cannot approve',async()=>{
 request.mockResolvedValue({...fx,stale:true,notice:'Última consulta válida; confira a data.'});await render({locked:true});
 expect(host.textContent).toContain('Última consulta válida');expect(host.querySelector('[data-testid="film-approve-budget"]').disabled).toBe(true);
});

test('cent rounding never enlarges a typed BRL spending limit',()=>{
 for(const rate of [4.5,5,5.8102,5.907,6.7899])for(const cents of [0,1,2,6,12,120,1000,10000]){
  const brl=cents/100,usd=usdWithinBrl(String(brl),rate);
  expect(usd*rate).toBeLessThanOrEqual(brl+1e-8);
 }
 expect(brlCeiling(.02,5.8102)).toBe('0.12');expect(usdWithinBrl('',5.8)).toBeNull();
});
