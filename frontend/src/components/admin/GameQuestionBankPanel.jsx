import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Database, FileSpreadsheet, Filter, Search, Trash2, Upload, Zap } from 'lucide-react';
import { toast } from 'sonner';
import { authHeaders } from '../../contexts/AuthContext';
import { getApiUrl } from '../../utils/apiUrl';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

const API = getApiUrl();

export default function GameQuestionBankPanel({ user, isSuperAdmin, companies = [] }) {
  const [companyId, setCompanyId] = useState(isSuperAdmin ? (companies[0]?.id || '') : (user?.companyId || ''));
  const [data, setData] = useState({ items: [], total: 0, facets: {} });
  const [filters, setFilters] = useState({ search: '', grade: '', subject: '', topic: '', difficulty: '' });
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    if (!companyId && isSuperAdmin && companies[0]?.id) setCompanyId(companies[0].id);
  }, [companyId, companies, isSuperAdmin]);

  const params = useMemo(() => {
    const p = new URLSearchParams({ companyId, pageSize: '100' });
    Object.entries(filters).forEach(([key, value]) => value && p.set(key, value));
    return p.toString();
  }, [companyId, filters]);

  const load = useCallback(async () => {
    if (!companyId) return;
    setLoading(true);
    try {
      const response = await fetch(`${API}/api/game-questions?${params}`, { headers: authHeaders(), credentials: 'include' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Falha ao consultar questões');
      setData(payload);
    } catch (error) {
      toast.error(error.message);
    } finally {
      setLoading(false);
    }
  }, [companyId, params]);

  useEffect(() => { load(); }, [load]);

  const importFile = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || !companyId) return;
    setImporting(true);
    try {
      const body = new FormData();
      body.append('file', file);
      const response = await fetch(`${API}/api/game-questions/import?companyId=${encodeURIComponent(companyId)}`, {
        method: 'POST', headers: authHeaders(), credentials: 'include', body,
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Falha na importação');
      toast.success(`${payload.imported} questões importadas${payload.rejected ? `; ${payload.rejected} rejeitadas` : ''}.`);
      await load();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setImporting(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm('Remover esta questão do banco de jogos?')) return;
    const response = await fetch(`${API}/api/game-questions/${id}?companyId=${encodeURIComponent(companyId)}`, {
      method: 'DELETE', headers: authHeaders(), credentials: 'include',
    });
    if (response.ok) {
      toast.success('Questão removida.');
      load();
    } else toast.error('Não foi possível remover a questão.');
  };

  const FilterSelect = ({ field, label }) => (
    <select
      value={filters[field]}
      onChange={(event) => setFilters((current) => ({ ...current, [field]: event.target.value }))}
      className="h-10 rounded-md border border-slate-700 bg-slate-900 px-3 text-sm text-slate-200"
    >
      <option value="">{label}: todos</option>
      {(data.facets?.[field] || []).map((value) => <option key={value} value={value}>{value}</option>)}
    </select>
  );

  return (
    <section className="space-y-5" data-testid="game-question-bank">
      <div className="overflow-hidden rounded-2xl border border-violet-500/20 bg-gradient-to-br from-slate-800 to-slate-900 p-6 shadow-2xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-cyan-400"><Zap className="h-4 w-4" /> QuestionEngine</div>
            <h2 className="text-2xl font-black text-white">Banco de Questões dos Jogos</h2>
            <p className="mt-1 text-sm text-slate-400">Uma única base alimenta pênalti, batalha, corrida, memória, forca e futuros minijogos.</p>
          </div>
          <div className="flex items-center gap-3">
            {isSuperAdmin && (
              <select value={companyId} onChange={(event) => setCompanyId(event.target.value)} className="h-10 rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-white">
                <option value="">Selecione a empresa</option>
                {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
              </select>
            )}
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-violet-600 px-4 py-2 text-sm font-bold text-white transition hover:bg-violet-500">
              {importing ? <span className="animate-pulse">Importando…</span> : <><Upload className="h-4 w-4" /> Importar Excel/CSV/JSON</>}
              <input type="file" className="hidden" accept=".xlsx,.csv,.json,text/csv,application/json" onChange={importFile} disabled={importing} />
            </label>
          </div>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-cyan-400/15 bg-cyan-400/5 p-4"><Database className="mb-2 h-5 w-5 text-cyan-400" /><strong className="block text-2xl text-white">{data.total || 0}</strong><span className="text-xs text-slate-400">questões disponíveis</span></div>
          <div className="rounded-xl border border-violet-400/15 bg-violet-400/5 p-4"><FileSpreadsheet className="mb-2 h-5 w-5 text-violet-400" /><strong className="block text-2xl text-white">{data.facets?.subject?.length || 0}</strong><span className="text-xs text-slate-400">disciplinas</span></div>
          <div className="rounded-xl border border-emerald-400/15 bg-emerald-400/5 p-4"><Filter className="mb-2 h-5 w-5 text-emerald-400" /><strong className="block text-2xl text-white">{data.facets?.topic?.length || 0}</strong><span className="text-xs text-slate-400">temas catalogados</span></div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-700 bg-slate-800 p-4">
        <div className="flex flex-wrap gap-2">
          <div className="relative min-w-64 flex-1"><Search className="absolute left-3 top-3 h-4 w-4 text-slate-500" /><Input value={filters.search} onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))} placeholder="Buscar pergunta ou tema…" className="border-slate-700 bg-slate-900 pl-9 text-white" /></div>
          <FilterSelect field="grade" label="Série" /><FilterSelect field="subject" label="Disciplina" /><FilterSelect field="topic" label="Tema" /><FilterSelect field="difficulty" label="Dificuldade" />
          <Button variant="outline" onClick={() => setFilters({ search: '', grade: '', subject: '', topic: '', difficulty: '' })}>Limpar</Button>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-700 bg-slate-800">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900/70 text-xs uppercase text-slate-400"><tr><th className="p-4">Pergunta</th><th className="p-4">Disciplina / tema</th><th className="p-4">Nível</th><th className="p-4">Uso</th><th className="p-4"></th></tr></thead>
            <tbody className="divide-y divide-slate-700">
              {loading && <tr><td colSpan="5" className="p-10 text-center text-slate-400">Carregando banco…</td></tr>}
              {!loading && data.items?.map((question) => (
                <tr key={question.id} className="transition hover:bg-slate-700/30">
                  <td className="max-w-xl p-4"><div className="font-semibold text-white">{question.question}</div><div className="mt-1 line-clamp-1 text-xs text-slate-500">{question.explanation || 'Sem explicação cadastrada'}</div></td>
                  <td className="p-4 text-slate-300">{question.subject}<div className="text-xs text-slate-500">{question.topic}{question.grade ? ` · ${question.grade}` : ''}</div></td>
                  <td className="p-4"><span className={`rounded-full px-2 py-1 text-xs font-bold ${question.difficulty === 'dificil' ? 'bg-rose-500/15 text-rose-300' : question.difficulty === 'facil' ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'}`}>{question.difficulty}</span></td>
                  <td className="p-4 text-slate-300">{question.timesAnswered || 0} respostas</td>
                  <td className="p-4"><Button size="icon" variant="ghost" onClick={() => remove(question.id)} className="text-slate-400 hover:text-rose-400"><Trash2 className="h-4 w-4" /></Button></td>
                </tr>
              ))}
              {!loading && !data.items?.length && <tr><td colSpan="5" className="p-12 text-center text-slate-400">Importe uma planilha para começar. Use colunas: ID, Série, Disciplina, Tema, Dificuldade, Pergunta, Alternativa A–D, Resposta correta e Explicação.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
