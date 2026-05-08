import React, { useState, useCallback } from 'react';
import { getApiUrl } from '../../utils/apiUrl';
import { authHeaders } from '../../contexts/AuthContext';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import { toast } from 'sonner';
import { Database, Loader2, AlertTriangle, CheckCircle2, Wrench } from 'lucide-react';

const API = getApiUrl();

const CATEGORY_LABELS = {
  slide_dims: 'Dimensões de slide (width/height)',
  slide_durations: 'Durações de slide',
  element_pos_size: 'Posição/tamanho de elementos',
  element_styles: 'Estilos numéricos (fontSize, opacity, etc.)',
  audio_props: 'Propriedades de áudio',
  annotation_pos: 'Posição de anotações',
};

export default function DataMigrationPanel() {
  const [scanning, setScanning] = useState(false);
  const [applying, setApplying] = useState(false);
  const [report, setReport] = useState(null);
  const [appliedReport, setAppliedReport] = useState(null);

  const runMigration = useCallback(async (dryRun) => {
    const setLoading = dryRun ? setScanning : setApplying;
    setLoading(true);
    try {
      const res = await fetch(
        `${API}/api/admin/normalize-numeric-fields?dryRun=${dryRun}`,
        { method: 'POST', headers: authHeaders(), credentials: 'include' }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Erro ${res.status}`);
      }
      const data = await res.json();
      if (dryRun) {
        setReport(data);
        toast.success(`Scan concluído: ${data.fixedProjects} projetos com dados sujos`);
      } else {
        setAppliedReport(data);
        setReport(null);
        toast.success(`Migração aplicada: ${data.totalFieldsCoerced} campos corrigidos`);
      }
    } catch (e) {
      toast.error(e.message || 'Erro na migração');
    }
    setLoading(false);
  }, []);

  const renderReport = (data, isApplied) => (
    <div className={`border rounded-lg p-4 ${isApplied ? 'border-emerald-700/50 bg-emerald-950/20' : 'border-amber-700/50 bg-amber-950/20'}`}>
      <div className="flex items-center gap-2 mb-3">
        {isApplied ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : <AlertTriangle className="w-5 h-5 text-amber-400" />}
        <span className={`font-semibold ${isApplied ? 'text-emerald-200' : 'text-amber-200'}`}>{data.message}</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
        <div className="bg-slate-800/40 rounded px-3 py-2">
          <div className="text-[10px] text-slate-400 uppercase">Projetos escaneados</div>
          <div className="text-2xl font-semibold text-white">{data.scanned}</div>
        </div>
        <div className="bg-slate-800/40 rounded px-3 py-2">
          <div className="text-[10px] text-slate-400 uppercase">{isApplied ? 'Atualizados' : 'A atualizar'}</div>
          <div className="text-2xl font-semibold text-amber-300">{data.fixedProjects}</div>
        </div>
        <div className="bg-slate-800/40 rounded px-3 py-2">
          <div className="text-[10px] text-slate-400 uppercase">Campos corrigidos</div>
          <div className="text-2xl font-semibold text-cyan-300">{data.totalFieldsCoerced}</div>
        </div>
      </div>
      <div className="space-y-2 mb-4">
        <h4 className="text-xs font-semibold text-slate-300">Breakdown por categoria</h4>
        {Object.entries(data.breakdown || {}).filter(([, v]) => v > 0).map(([k, v]) => (
          <div key={k} className="flex items-center justify-between text-xs bg-slate-900/40 rounded px-3 py-2">
            <span className="text-slate-300">{CATEGORY_LABELS[k] || k}</span>
            <Badge className="bg-slate-700 text-slate-200">{v}</Badge>
          </div>
        ))}
      </div>
      {data.sampleProjects && data.sampleProjects.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-slate-300 mb-2">
            {isApplied ? 'Top 50 projetos atualizados' : 'Top 50 projetos com dados sujos'}
          </h4>
          <ScrollArea className="max-h-48">
            <div className="space-y-1 pr-2">
              {data.sampleProjects.map(p => (
                <div key={p.projectId} className="flex items-center justify-between text-[11px] bg-slate-900/30 rounded px-2 py-1.5">
                  <span className="text-slate-300 truncate flex-1 mr-2">{p.name}</span>
                  <Badge className="bg-amber-900/40 text-amber-200 text-[10px]">{p.totalChanges} campos</Badge>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-4 max-w-4xl" data-testid="data-migration-panel">
      <div className="flex items-center gap-2 mb-2">
        <Database className="w-6 h-6 text-cyan-400" />
        <h2 className="text-2xl font-bold text-white">Migração de Dados</h2>
      </div>
      <p className="text-sm text-slate-400">
        Normaliza campos numéricos sujos (strings como <code>"1280"</code> ou floats como <code>1280.5</code>) em projetos importados de PPT
        para os tipos canônicos. Use o <strong>Scan (Dry Run)</strong> primeiro para ver o que seria alterado, depois <strong>Aplicar</strong> para gravar.
      </p>

      <div className="flex gap-2">
        <Button
          onClick={() => runMigration(true)}
          disabled={scanning || applying}
          variant="outline"
          className="border-cyan-700/50 text-cyan-300 hover:bg-cyan-900/20"
          data-testid="data-migration-scan"
        >
          {scanning ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Database className="w-4 h-4 mr-2" />}
          Scan (Dry Run)
        </Button>
        <Button
          onClick={() => {
            if (!report) return;
            if (!window.confirm(
              `Esta acao vai escrever em ${report.fixedProjects} projetos do banco, corrigindo ${report.totalFieldsCoerced} campos. ` +
              `Continuar?`
            )) return;
            runMigration(false);
          }}
          disabled={applying || !report || report.fixedProjects === 0}
          className="bg-emerald-600 hover:bg-emerald-700 text-white"
          data-testid="data-migration-apply"
        >
          {applying ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Wrench className="w-4 h-4 mr-2" />}
          Aplicar Migração
        </Button>
      </div>

      {report && !appliedReport && renderReport(report, false)}
      {appliedReport && renderReport(appliedReport, true)}
    </div>
  );
}
