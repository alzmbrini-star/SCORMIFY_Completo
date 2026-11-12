import React, { useState } from 'react';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../ui/dialog';

export default function HtmlSourceEditor({ element, onUpdate }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  async function save() {
    setSaving(true); setError('');
    try { await onUpdate({ htmlContent: draft }); setOpen(false); }
    catch (_) { setError('Não foi possível salvar. Seu rascunho continua aberto.'); }
    finally { setSaving(false); }
  }
  return <>
    <Button type="button" variant="outline" className="w-full" onClick={() => {
      setDraft(element.htmlContent || ''); setError(''); setOpen(true);
    }}>Editar código HTML</Button>
    <Dialog open={open} onOpenChange={value => { if (!saving) setOpen(value); }}>
      <DialogContent className="sm:max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>Editar código HTML do bloco</DialogTitle>
          <DialogDescription>Altera somente o conteúdo deste bloco. Posição, tamanho e outros slides são preservados. Código avançado: mantenha as funções e use apenas conteúdo de confiança.</DialogDescription>
        </DialogHeader>
        <label htmlFor="block-html-source">Código HTML</label>
        <textarea id="block-html-source" value={draft} onChange={event => setDraft(event.target.value)}
          spellCheck={false} className="w-full h-[50vh] p-3 rounded border bg-background font-mono text-sm" disabled={saving} />
        {error && <p role="alert">{error}</p>}
        <DialogFooter><Button variant="outline" disabled={saving} onClick={() => setOpen(false)}>Cancelar</Button>
          <Button disabled={saving || !draft.trim()} onClick={save}>{saving ? 'Salvando…' : 'Salvar código HTML'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </>;
}
