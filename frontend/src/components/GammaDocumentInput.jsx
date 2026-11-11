import React, {useEffect, useRef, useState} from 'react';
import {authHeaders} from '../contexts/AuthContext';
import {getApiUrl} from '../utils/apiUrl';
import {Button} from './ui/button';

export default function GammaDocumentInput({value, onChange, disabled, onBusy}) {
  const [reading, setReading] = useState(false), [draft, setDraft] = useState(null), [error, setError] = useState('');
  const abort = useRef(null), serial = useRef(0);
  useEffect(() => () => {serial.current += 1; abort.current?.abort(); onBusy(false);}, [onBusy]);
  useEffect(() => {onBusy(reading || !!draft);}, [reading, draft, onBusy]);
  async function upload(event) {
    const file = event.target.files?.[0]; event.target.value = '';
    if (!file || reading || disabled) return;
    setError(''); setDraft(null);
    if (!/\.(docx|pdf|pptx)$/i.test(file.name)) {setError('Use .docx, .pdf ou .pptx. Salve arquivos .doc/.ppt antigos no formato atual.'); return;}
    if (!file.size || file.size > 20*1024*1024) {setError('Envie um arquivo não vazio de até 20 MB.'); return;}
    const current = ++serial.current, controller = new AbortController(); abort.current = controller;
    setReading(true); onBusy(true);
    const timeout = setTimeout(() => controller.abort(), 90000);
    try {
      const form = new FormData(); form.append('file', file);
      const response = await fetch(`${getApiUrl()}/api/gamma/extract-document`, {method:'POST', credentials:'include', headers:authHeaders(), body:form, signal:controller.signal});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível extrair o arquivo.');
      if (current === serial.current) setDraft({...data, name:file.name});
    } catch (e) {if (current === serial.current) setError(e.name==='AbortError'?'A leitura foi interrompida. Seu conteúdo anterior foi preservado.':e.message);}
    finally {clearTimeout(timeout); if (current === serial.current) {setReading(false); onBusy(false);}}
  }
  const combined = draft ? [value.trim(), draft.text.trim()].filter(Boolean).join('\n\n') : '';
  return <fieldset className="gamma-document" disabled={disabled || reading}>
    <legend>Ou use um documento</legend>
    <label className="gamma-file-label">Word, PDF ou PowerPoint
      <input aria-label="Arquivo de conteúdo Gamma" type="file" accept=".docx,.pdf,.pptx" onChange={upload}/>
    </label>
    <p className="gamma-help">DOCX, PDF com texto ou PPTX · até 20 MB e 300 páginas/slides. A leitura é local ao servidor SCORMIFY, sem créditos de IA. O conteúdo só será enviado ao Gamma ao clicar em Gerar.</p>
    {reading && <p role="status">Lendo documento… Seu texto atual será preservado.</p>}
    {error && <p role="alert" className="gamma-error">{error}</p>}
    {draft && <div className="gamma-document-review">
      <strong>{draft.name}</strong><p className="gamma-help">{draft.warning}</p>
      <details open><summary>Revisar texto extraído · {draft.text.length.toLocaleString('pt-BR')} caracteres</summary>
        <textarea aria-label="Texto extraído do arquivo Gamma" value={draft.text} onChange={e=>setDraft({...draft,text:e.target.value})}/>
      </details>
      {combined.length>100000 && <p role="alert" className="gamma-error">O conteúdo combinado excede 100.000 caracteres. Reduza o texto antes de adicionar; nada será cortado.</p>}
      <div className="gamma-document-actions"><Button type="button" disabled={!draft.text.trim() || combined.length>100000} onClick={()=>{onChange(combined);setDraft(null);}}>Adicionar ao conteúdo</Button>
      <Button type="button" variant="outline" onClick={()=>setDraft(null)}>Descartar arquivo</Button></div>
    </div>}
  </fieldset>;
}
