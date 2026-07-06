import React, { useEffect, useMemo, useState } from 'react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Package, Download, Loader2, RefreshCw, CheckCircle2, XCircle, Search } from 'lucide-react';
import { toast } from 'sonner';
import { authHeaders } from '../../contexts/AuthContext';
import { getApiUrl } from '../../utils/apiUrl';

const API_URL = getApiUrl();

/**
 * Batch SCORM Export panel — visible to super_admin and company_admin only.
 * List of courses is filtered by the backend (`GET /api/projects`) via role.
 *
 * Flow:
 *   1. Load projects (already RBAC-filtered by /api/projects).
 *   2. User picks N via checkbox, clicks "Exportar SCORM em Lote".
 *   3. POST /api/admin/batch-export-scorm — returns child jobIds.
 *   4. Poll each child job via /api/job/{id} every 3s; render per-row progress.
 *   5. When status === "completed", render a Download link built from
 *      `result.downloadUrl` (already served by /api/exports/{filename}).
 */
export default function BatchExportPanel() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState({});   // { projectId: true }
  const [starting, setStarting] = useState(false);
  const [batchJobs, setBatchJobs] = useState([]); // [{projectId, jobId, name, status, progress, message, downloadUrl}]

  const loadProjects = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/projects`, {
        headers: authHeaders(),
        credentials: 'include',
      });
      if (!res.ok) throw new Error(String(res.status));
      const data = await res.json();
      setProjects(Array.isArray(data) ? data : []);
    } catch (e) {
      toast.error('Erro ao carregar cursos');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadProjects(); }, []);

  // Poll active batch jobs until every child finishes.
  useEffect(() => {
    if (!batchJobs.length) return undefined;
    const active = batchJobs.some(j => j.status !== 'completed' && j.status !== 'failed');
    if (!active) return undefined;

    const tick = async () => {
      const updated = await Promise.all(
        batchJobs.map(async (j) => {
          if (j.status === 'completed' || j.status === 'failed') return j;
          try {
            const r = await fetch(`${API_URL}/api/job/${j.jobId}`, {
              headers: authHeaders(), credentials: 'include',
            });
            if (!r.ok) return j;
            const doc = await r.json();
            return {
              ...j,
              status: doc.status || j.status,
              progress: typeof doc.progress === 'number' ? doc.progress : j.progress,
              message: doc.message || j.message,
              downloadUrl: doc.result?.downloadUrl || j.downloadUrl,
            };
          } catch { return j; }
        })
      );
      setBatchJobs(updated);
    };
    const id = setInterval(tick, 3000);
    // First tick immediately so the UI feels responsive.
    tick();
    return () => clearInterval(id);
  }, [batchJobs]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter(p => (p.name || '').toLowerCase().includes(q));
  }, [projects, search]);

  const selectedIds = useMemo(
    () => Object.keys(selected).filter(k => selected[k]),
    [selected]
  );

  const toggleAll = () => {
    if (selectedIds.length === filtered.length) {
      setSelected({});
    } else {
      const next = {};
      filtered.forEach(p => { next[p.id] = true; });
      setSelected(next);
    }
  };

  const startBatch = async () => {
    if (!selectedIds.length) {
      toast.warning('Selecione pelo menos um curso');
      return;
    }
    if (selectedIds.length > 100) {
      toast.error('Máximo 100 cursos por lote');
      return;
    }
    setStarting(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/batch-export-scorm`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        credentials: 'include',
        body: JSON.stringify({ projectIds: selectedIds }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setBatchJobs((data.jobs || []).map(j => ({
        ...j, status: 'queued', progress: 0, message: 'Na fila...', downloadUrl: null,
      })));
      setSelected({});
      if (data.denied?.length) {
        toast.warning(`${data.denied.length} curso(s) ignorado(s) por permissão`);
      }
      toast.success(`Lote iniciado com ${data.total} curso(s)`);
    } catch (e) {
      toast.error(`Erro ao iniciar lote: ${e.message}`);
    } finally {
      setStarting(false);
    }
  };

  const anyActive = batchJobs.some(j => j.status !== 'completed' && j.status !== 'failed');

  return (
    <div className="space-y-6" data-testid="batch-export-panel">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Package className="w-6 h-6 text-indigo-400" />
            Exportação SCORM em Lote
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Selecione múltiplos cursos e gere pacotes SCORM sequencialmente. Cada curso vira um ZIP baixável.
          </p>
        </div>
        <Button variant="outline" onClick={loadProjects} disabled={loading} className="gap-2" data-testid="batch-refresh-projects">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Atualizar
        </Button>
      </div>

      {/* Search + bulk action */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 space-y-3">
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <Input
              placeholder="Buscar por nome do curso..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
              data-testid="batch-search"
            />
          </div>
          <Button variant="outline" onClick={toggleAll} disabled={!filtered.length} data-testid="batch-toggle-all">
            {selectedIds.length === filtered.length && filtered.length > 0 ? 'Desmarcar tudo' : 'Selecionar todos'}
          </Button>
          <Button
            onClick={startBatch}
            disabled={starting || !selectedIds.length || anyActive}
            className="gap-2 bg-indigo-600 hover:bg-indigo-500"
            data-testid="batch-start"
          >
            {starting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Package className="w-4 h-4" />}
            Exportar SCORM ({selectedIds.length})
          </Button>
        </div>
        {anyActive && (
          <p className="text-xs text-amber-400" data-testid="batch-active-hint">
            ⏳ Um lote já está em execução. Aguarde todos os cursos concluírem antes de iniciar outro.
          </p>
        )}
      </div>

      {/* Projects list */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
        <div className="grid grid-cols-[40px_1fr_140px_100px] gap-3 px-4 py-2 text-xs uppercase tracking-wide text-slate-400 border-b border-slate-700 bg-slate-900/50">
          <div>Sel</div>
          <div>Curso</div>
          <div>Empresa</div>
          <div className="text-right">Slides</div>
        </div>
        {loading ? (
          <div className="p-8 text-center text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />
            Carregando cursos...
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-slate-500">Nenhum curso encontrado.</div>
        ) : (
          <div className="max-h-[420px] overflow-y-auto divide-y divide-slate-700/50">
            {filtered.map((p) => (
              <label
                key={p.id}
                className="grid grid-cols-[40px_1fr_140px_100px] gap-3 px-4 py-2.5 items-center hover:bg-slate-700/30 cursor-pointer"
                data-testid={`batch-row-${p.id}`}
              >
                <input
                  type="checkbox"
                  className="w-4 h-4 accent-indigo-500"
                  checked={!!selected[p.id]}
                  onChange={(e) => setSelected(s => ({ ...s, [p.id]: e.target.checked }))}
                  data-testid={`batch-check-${p.id}`}
                />
                <div>
                  <p className="text-sm font-medium text-slate-100 truncate">{p.name || '(sem nome)'}</p>
                  <p className="text-[11px] text-slate-500 truncate">{p.id}</p>
                </div>
                <div className="text-xs text-slate-400 truncate">{p.companyId || '—'}</div>
                <div className="text-right text-xs text-slate-300">{p.course?.slidesCount ?? '—'}</div>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Batch progress */}
      {batchJobs.length > 0 && (
        <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden" data-testid="batch-jobs-panel">
          <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-200">
              Progresso do lote
              <span className="ml-2 text-xs text-slate-500">
                ({batchJobs.filter(j => j.status === 'completed').length} de {batchJobs.length} concluídos)
              </span>
            </h3>
            {!anyActive && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setBatchJobs([])}
                data-testid="batch-clear-history"
              >
                Limpar
              </Button>
            )}
          </div>
          <div className="divide-y divide-slate-700/50 max-h-[360px] overflow-y-auto">
            {batchJobs.map((j) => {
              const done = j.status === 'completed';
              const failed = j.status === 'failed';
              return (
                <div key={j.jobId} className="px-4 py-3 grid grid-cols-[1fr_120px_140px] gap-3 items-center" data-testid={`batch-job-${j.jobId}`}>
                  <div className="min-w-0">
                    <p className="text-sm text-slate-100 truncate">{j.name}</p>
                    <p className="text-[11px] text-slate-500 truncate">{j.message}</p>
                    {!done && !failed && (
                      <div className="mt-1 h-1 bg-slate-700 rounded-full overflow-hidden">
                        <div className="h-full bg-indigo-500 transition-all" style={{ width: `${j.progress || 0}%` }} />
                      </div>
                    )}
                  </div>
                  <div className="text-xs">
                    {done && <span className="text-emerald-400 inline-flex items-center gap-1"><CheckCircle2 className="w-4 h-4" /> Pronto</span>}
                    {failed && <span className="text-red-400 inline-flex items-center gap-1"><XCircle className="w-4 h-4" /> Falhou</span>}
                    {!done && !failed && <span className="text-amber-300">{j.status === 'queued' ? 'Na fila' : `${j.progress || 0}%`}</span>}
                  </div>
                  <div className="text-right">
                    {done && j.downloadUrl && (
                      <a
                        href={`${API_URL}${j.downloadUrl}`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 px-3 py-1.5 text-xs rounded-md bg-emerald-600 hover:bg-emerald-500 text-white"
                        data-testid={`batch-download-${j.projectId}`}
                      >
                        <Download className="w-3 h-3" /> Baixar
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
