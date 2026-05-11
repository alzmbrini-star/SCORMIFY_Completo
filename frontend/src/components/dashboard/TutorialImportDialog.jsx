import React, { useState, useEffect, useCallback } from 'react';
import { getApiUrl } from '../../utils/apiUrl';
import { authHeaders } from '../../contexts/AuthContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../ui/dialog';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import { Input } from '../ui/input';
import { toast } from 'sonner';
import { Loader2, Download, FileText, CheckCircle2, Clock, AlertCircle } from 'lucide-react';

const API = getApiUrl();

/**
 * Dialog to browse and import tutorials from the external Tutorial Agent
 * (https://auto-instructor-1.preview.emergentagent.com).
 * Each tutorial becomes a Scormify project with one slide per step.
 */
export default function TutorialImportDialog({ open, onOpenChange, onProjectCreated }) {
  const [loading, setLoading] = useState(false);
  const [tutorials, setTutorials] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [importing, setImporting] = useState(false);
  const [customName, setCustomName] = useState('');
  const [error, setError] = useState(null);

  const fetchTutorials = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/tutorial-integration/list`, {
        headers: authHeaders(),
        credentials: 'include',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Erro ${res.status}`);
      }
      const data = await res.json();
      const list = Array.isArray(data) ? data : (data.tutorials || []);
      setTutorials(list);
    } catch (e) {
      setError(e.message || 'Falha ao listar tutoriais');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (open) {
      fetchTutorials();
      setSelectedId(null);
      setCustomName('');
    }
  }, [open, fetchTutorials]);

  const handleImport = useCallback(async () => {
    if (!selectedId) return;
    setImporting(true);
    try {
      const res = await fetch(`${API}/api/tutorial-integration/import/${selectedId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        credentials: 'include',
        body: JSON.stringify({
          mode: 'new',
          name: customName.trim() || undefined,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Erro ${res.status}`);
      }
      const data = await res.json();
      toast.success(`Curso criado com ${data.addedSlides} slide(s)!`);
      if (onProjectCreated) onProjectCreated(data.projectId);
      onOpenChange(false);
    } catch (e) {
      toast.error(e.message || 'Erro ao importar tutorial');
    }
    setImporting(false);
  }, [selectedId, customName, onOpenChange, onProjectCreated]);

  const statusBadge = (status) => {
    if (status === 'completed') {
      return <Badge className="bg-emerald-900/40 text-emerald-300 text-[10px]"><CheckCircle2 className="w-3 h-3 mr-1" />Pronto</Badge>;
    }
    if (status === 'generating') {
      return <Badge className="bg-amber-900/40 text-amber-300 text-[10px]"><Clock className="w-3 h-3 mr-1" />Gerando</Badge>;
    }
    if (status === 'error') {
      return <Badge className="bg-rose-900/40 text-rose-300 text-[10px]"><AlertCircle className="w-3 h-3 mr-1" />Erro</Badge>;
    }
    return <Badge className="bg-slate-700 text-slate-300 text-[10px]">{status || 'rascunho'}</Badge>;
  };

  const selected = tutorials.find(t => t.id === selectedId);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl bg-slate-950 border-slate-800" data-testid="tutorial-import-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-white">
            <Download className="w-5 h-5 text-cyan-400" />
            Importar Tutorial do Auto-Instructor
          </DialogTitle>
        </DialogHeader>

        <p className="text-xs text-slate-400 leading-relaxed">
          Selecione um tutorial gerado pelo seu Agente de Tutoriais. Cada passo vira um slide com
          screenshot, hotspot circular na posicao do clique e narracao automatica.
        </p>

        {error && (
          <div className="bg-rose-900/30 border border-rose-700/50 text-rose-200 text-xs p-3 rounded">
            <AlertCircle className="w-4 h-4 inline mr-1" />
            {error}
            <Button size="sm" variant="ghost" onClick={fetchTutorials} className="ml-2 text-xs h-6 text-rose-200">
              Tentar novamente
            </Button>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-12 text-slate-400 text-sm">
            <Loader2 className="w-5 h-5 animate-spin mr-2" /> Carregando tutoriais...
          </div>
        ) : (
          <ScrollArea className="max-h-[400px]">
            <div className="space-y-2 pr-2">
              {tutorials.length === 0 && !error && (
                <div className="text-center text-slate-500 text-sm py-8">
                  Nenhum tutorial encontrado no Agente.
                </div>
              )}
              {tutorials.map((t) => (
                <button
                  key={t.id}
                  onClick={() => t.status === 'completed' && setSelectedId(t.id)}
                  disabled={t.status !== 'completed'}
                  className={`w-full text-left p-3 rounded border transition-colors ${
                    selectedId === t.id
                      ? 'border-cyan-500 bg-cyan-900/20'
                      : t.status === 'completed'
                        ? 'border-slate-700 bg-slate-900/40 hover:border-slate-600 hover:bg-slate-800/50 cursor-pointer'
                        : 'border-slate-800 bg-slate-900/20 opacity-60 cursor-not-allowed'
                  }`}
                  data-testid={`tutorial-card-${t.id}`}
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <span className="text-sm font-medium text-slate-100 flex-1 truncate">{t.title}</span>
                    {statusBadge(t.status)}
                  </div>
                  <p className="text-[11px] text-slate-400 line-clamp-2 mb-1">{t.description || ''}</p>
                  <div className="flex items-center gap-3 text-[10px] text-slate-500">
                    <span className="flex items-center gap-1">
                      <FileText className="w-3 h-3" />
                      {t.steps_count || 0} passos
                    </span>
                    {t.updated_at && (
                      <span>{new Date(t.updated_at).toLocaleDateString('pt-BR')}</span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </ScrollArea>
        )}

        {selected && (
          <div className="space-y-2 pt-2 border-t border-slate-800">
            <label className="text-xs text-slate-400">Nome do projeto (opcional):</label>
            <Input
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              placeholder={selected.title}
              className="bg-slate-900 border-slate-700 text-slate-100 text-sm"
              data-testid="tutorial-import-name"
            />
          </div>
        )}

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={importing}>
            Cancelar
          </Button>
          <Button
            onClick={handleImport}
            disabled={!selectedId || importing}
            className="bg-cyan-600 hover:bg-cyan-700"
            data-testid="tutorial-import-confirm"
          >
            {importing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Download className="w-4 h-4 mr-2" />}
            Importar como novo curso
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
