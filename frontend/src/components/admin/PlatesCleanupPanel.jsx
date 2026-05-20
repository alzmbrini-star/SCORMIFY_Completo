import React, { useState, useCallback } from 'react';
import { getApiUrl } from '../../utils/apiUrl';
import { authHeaders } from '../../contexts/AuthContext';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import { toast } from 'sonner';
import { Eraser, Loader2, AlertTriangle, CheckCircle2, Trash2, Square } from 'lucide-react';

const API = getApiUrl();

/**
 * Cleanup panel for legacy aesthetic plates + island plate backgrounds.
 *
 * Wraps two admin migrations:
 *   - POST /api/admin/cleanup-aesthetic-plates  — strips legacy
 *     `textBackgroundColor` rgba/solid plates left over from v3-v5 of
 *     the Aesthetic Analyzer.
 *   - POST /api/admin/strip-html-container-backgrounds — strips
 *     full-bleed wrapper `<div>` backgrounds inside htmlContent that
 *     conflict with `slide.background`.
 *
 * Each migration shows a dry-run preview first, then asks for explicit
 * confirmation before writing to the DB.
 */
function MigrationCard({
  title,
  description,
  endpoint,
  icon: Icon,
  testIdPrefix,
  countLabel,
}) {
  const [scanning, setScanning] = useState(false);
  const [applying, setApplying] = useState(false);
  const [report, setReport] = useState(null);
  const [applied, setApplied] = useState(null);

  const run = useCallback(async (dryRun) => {
    const setLoading = dryRun ? setScanning : setApplying;
    setLoading(true);
    try {
      const res = await fetch(`${API}${endpoint}?dryRun=${dryRun}`, {
        method: 'POST',
        headers: authHeaders(),
        credentials: 'include',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Erro ${res.status}`);
      }
      const data = await res.json();
      if (dryRun) {
        setReport(data);
        setApplied(null);
        toast.success(`Scan: ${data.mutatedProjects} projetos afetados`);
      } else {
        setApplied(data);
        setReport(null);
        toast.success(data.message || 'Migracao aplicada');
      }
    } catch (e) {
      toast.error(e.message || 'Erro na migracao');
    }
    setLoading(false);
  }, [endpoint]);

  const renderReport = (data, isApplied) => (
    <div
      className={`border rounded-lg p-4 mt-3 ${
        isApplied
          ? 'border-emerald-700/50 bg-emerald-950/20'
          : 'border-amber-700/50 bg-amber-950/20'
      }`}
    >
      <div className="flex items-center gap-2 mb-3">
        {isApplied ? (
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
        ) : (
          <AlertTriangle className="w-5 h-5 text-amber-400" />
        )}
        <span
          className={`font-semibold ${
            isApplied ? 'text-emerald-200' : 'text-amber-200'
          }`}
        >
          {data.message}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-slate-800/40 rounded px-3 py-2">
          <div className="text-[10px] text-slate-400 uppercase">Escaneados</div>
          <div className="text-2xl font-semibold text-white">
            {data.scannedProjects}
          </div>
        </div>
        <div className="bg-slate-800/40 rounded px-3 py-2">
          <div className="text-[10px] text-slate-400 uppercase">
            {isApplied ? 'Atualizados' : 'A atualizar'}
          </div>
          <div className="text-2xl font-semibold text-amber-300">
            {data.mutatedProjects}
          </div>
        </div>
        <div className="bg-slate-800/40 rounded px-3 py-2">
          <div className="text-[10px] text-slate-400 uppercase">
            {countLabel}
          </div>
          <div className="text-2xl font-semibold text-cyan-300">
            {data.mutatedElements ?? data.totalContainersStripped ?? 0}
          </div>
        </div>
      </div>
      {data.sampleProjects?.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-slate-300 mb-2">
            {isApplied ? 'Projetos atualizados' : 'Projetos com pendencias'}
          </h4>
          <ScrollArea className="max-h-48">
            <div className="space-y-1 pr-2">
              {data.sampleProjects.map((p) => (
                <div
                  key={p.projectId}
                  className="flex items-center justify-between text-[11px] bg-slate-900/30 rounded px-2 py-1.5"
                >
                  <span className="text-slate-300 truncate flex-1 mr-2">
                    {p.name || p.projectId}
                  </span>
                  <Badge className="bg-amber-900/40 text-amber-200 text-[10px]">
                    {p.elementsCleaned} elem
                  </Badge>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
      )}
    </div>
  );

  return (
    <div className="border border-slate-700 rounded-lg p-4 bg-slate-900/30">
      <div className="flex items-start gap-3 mb-3">
        <div className="p-2 rounded bg-slate-800/60">
          <Icon className="w-5 h-5 text-cyan-300" />
        </div>
        <div className="flex-1 min-w-0">
          <h3
            className="text-lg font-semibold text-white"
            data-testid={`${testIdPrefix}-title`}
          >
            {title}
          </h3>
          <p className="text-sm text-slate-400 mt-1">{description}</p>
        </div>
      </div>

      <div className="flex gap-2">
        <Button
          onClick={() => run(true)}
          disabled={scanning || applying}
          variant="outline"
          className="border-cyan-700/50 text-cyan-300 hover:bg-cyan-900/20"
          data-testid={`${testIdPrefix}-scan-btn`}
        >
          {scanning ? (
            <Loader2 className="w-4 h-4 animate-spin mr-2" />
          ) : (
            <Eraser className="w-4 h-4 mr-2" />
          )}
          Scan (Dry Run)
        </Button>
        <Button
          onClick={() => {
            if (!report) return;
            if (
              !window.confirm(
                `Vai aplicar em ${report.mutatedProjects} projetos. Continuar?`
              )
            )
              return;
            run(false);
          }}
          disabled={applying || !report || report.mutatedProjects === 0}
          className="bg-emerald-600 hover:bg-emerald-700 text-white"
          data-testid={`${testIdPrefix}-apply-btn`}
        >
          {applying ? (
            <Loader2 className="w-4 h-4 animate-spin mr-2" />
          ) : (
            <Trash2 className="w-4 h-4 mr-2" />
          )}
          Aplicar
        </Button>
      </div>

      {report && !applied && renderReport(report, false)}
      {applied && renderReport(applied, true)}
    </div>
  );
}

export default function PlatesCleanupPanel() {
  return (
    <div className="space-y-4 max-w-4xl" data-testid="plates-cleanup-panel">
      <div className="flex items-center gap-2 mb-2">
        <Eraser className="w-6 h-6 text-cyan-400" />
        <h2 className="text-2xl font-bold text-white">
          Limpeza de Metadados Antigos
        </h2>
      </div>
      <p className="text-sm text-slate-400">
        Remove artefatos visuais legados que sobraram de versoes antigas do
        Analisador de Estetica e do AI Agent gerador de slides. Cada migracao
        e idempotente — pode rodar varias vezes sem efeito colateral.
      </p>

      <MigrationCard
        title="Plates do Analisador (versoes v3-v5)"
        description="Strip de textBackgroundColor (rgba/solid), padding/borderRadius/border auto-injetados, e style tags <style data-aesthetic-fix> antigos."
        endpoint="/api/admin/cleanup-aesthetic-plates"
        icon={Eraser}
        testIdPrefix="cleanup-plates"
        countLabel="Elementos limpos"
      />

      <MigrationCard
        title="Island Plates do AI Agent (wrappers full-bleed)"
        description="Strip de background em <div> wrappers full-bleed (width:100% + height:100%) que viraram retangulos coloridos quando o slide.background foi alterado. Preserva badges, chips, table cells e barras decorativas."
        endpoint="/api/admin/strip-html-container-backgrounds"
        icon={Square}
        testIdPrefix="strip-containers"
        countLabel="Containers limpos"
      />
    </div>
  );
}
