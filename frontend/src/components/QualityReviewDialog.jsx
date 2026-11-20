import React, { useEffect, useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { authHeaders } from '../contexts/AuthContext';
import { getApiUrl } from '../utils/apiUrl';

export default function QualityReviewDialog({ projectId, onClose, onSaved }) {
  const [review, setReview] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch(getApiUrl() + '/api/projects/' + encodeURIComponent(projectId) + '/quality-review',
      { headers: authHeaders(), signal: controller.signal })
      .then(async r => { const data = await r.json(); if (!r.ok) throw Error(data.detail || 'Falha ao conferir o curso.'); return data; })
      .then(setReview).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => controller.abort();
  }, [projectId]);
  const download = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify({ projectId, ...review }, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = 'scormify-revisao-' + projectId + '.json';
    document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const apply = async () => {
    setBusy(true); setError('');
    try {
      const r = await fetch(getApiUrl() + '/api/projects/' + encodeURIComponent(projectId) + '/quality-review', {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ fingerprint: review.fingerprint })
      });
      const data = await r.json(); if (!r.ok) throw Error(data.detail || 'Não foi possível aplicar os ajustes.');
      await onSaved(); onClose();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return <Dialog open onOpenChange={v => { if (!v && !busy) onClose(); }}>
    <DialogContent className="sm:max-w-3xl max-h-[88vh] overflow-y-auto">
      <DialogHeader><DialogTitle>Revisar qualidade do curso</DialogTitle>
        <DialogDescription>Ajustes determinísticos, sem gerar mídias ou usar créditos. Só o curso aberto será alterado após sua confirmação.</DialogDescription></DialogHeader>
      <p>Preserva slides, perguntas, gabaritos, notas e interações. Reaproveita imagens do próprio curso se uma imagem falhar; melhora leitura dos cartões e legendas. Não verifica a exatidão pedagógica de todo o conteúdo.</p>
      {review && <><p>{review.slides} slides · {review.questions} perguntas · {review.changes.length} slides com ajustes disponíveis</p>
        <ul>{review.changes.map(row => <li key={row.slide}>Slide {row.slide}: {row.title}</li>)}</ul>
        <Button variant="outline" disabled={busy} onClick={download}>Baixar referência de segurança (JSON)</Button>
        <p className="text-sm">A referência contém conteúdo do curso; revise antes de compartilhar. Ao aplicar, o servidor também guarda uma cópia de segurança e bloqueia edições simultâneas. Depois, confira a prévia e reexporte HTML/SCORM.</p></>}
      {error && <p role="alert" className="text-red-500">{error}</p>}
      <div className="flex justify-end gap-2"><Button variant="outline" disabled={busy} onClick={onClose}>Fechar sem alterar</Button>
        <Button disabled={!review?.fields || busy} onClick={apply}>{busy ? 'Salvando…' : 'Aplicar ajustes somente neste curso'}</Button></div>
    </DialogContent>
  </Dialog>;
}
