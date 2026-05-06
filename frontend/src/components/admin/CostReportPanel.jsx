import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import {
  Loader2, RefreshCw, FileText, Image as ImageIcon, MessageSquare,
  Mic, Video, DollarSign, Building2,
} from 'lucide-react';
import { getApiUrl } from '../../utils/apiUrl';

const API_URL = getApiUrl();

/**
 * Cost Report Panel — super_admin only.
 * Aggregates per-company AI usage so service-providers can identify which
 * costs belong to which client company.
 *
 * GET /api/admin/cost-report?from=YYYY-MM-DD&to=YYYY-MM-DD
 */
export default function CostReportPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = {};
      if (from) params.from = from;
      if (to) params.to = to;
      const res = await axios.get(`${API_URL}/api/admin/cost-report`, { params });
      setData(res.data);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Erro ao carregar relatório');
    } finally {
      setLoading(false);
    }
  }, [from, to]);

  useEffect(() => { load(); }, [load]);

  const totalAcrossCompanies = (data?.companies || []).reduce(
    (acc, c) => ({
      projects: acc.projects + (c.projects?.total || 0),
      krea: acc.krea + (c.krea?.total || 0),
      leonardo: acc.leonardo + (c.leonardo?.total || 0),
      tutor: acc.tutor + (c.tutor?.total || 0),
      elevenlabs: acc.elevenlabs + (c.elevenlabs?.total || 0),
      heygen: acc.heygen + (c.heygen?.total || 0),
    }),
    { projects: 0, krea: 0, leonardo: 0, tutor: 0, elevenlabs: 0, heygen: 0 },
  );

  return (
    <div className="space-y-6" data-testid="cost-report-panel">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <DollarSign className="w-6 h-6 text-emerald-400" />
            Custos por Empresa
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Agregação de uso de IA por empresa cliente — para identificar gastos no faturamento.
          </p>
        </div>
        <Button
          variant="outline" size="sm"
          onClick={load} disabled={loading}
          className="gap-2"
          data-testid="cost-report-refresh-btn"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Atualizar
        </Button>
      </div>

      <Card className="bg-slate-900/40 border-slate-800">
        <CardContent className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-1">
            <Label htmlFor="cost-from" className="text-xs text-slate-400">De (inclusive)</Label>
            <Input
              id="cost-from" type="date"
              value={from} onChange={(e) => setFrom(e.target.value)}
              className="bg-slate-900 border-slate-700"
              data-testid="cost-from-input"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="cost-to" className="text-xs text-slate-400">Até (exclusive)</Label>
            <Input
              id="cost-to" type="date"
              value={to} onChange={(e) => setTo(e.target.value)}
              className="bg-slate-900 border-slate-700"
              data-testid="cost-to-input"
            />
          </div>
          <div className="flex items-end">
            <Button onClick={load} disabled={loading} className="w-full gap-2" data-testid="cost-apply-filters-btn">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              Aplicar filtros
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300" data-testid="cost-report-error">
          {error}
        </div>
      )}

      {/* Totals strip */}
      {data?.companies && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3" data-testid="cost-totals">
          <SummaryTile icon={FileText} label="Cursos" value={totalAcrossCompanies.projects} color="emerald" />
          <SummaryTile icon={ImageIcon} label="Krea" value={totalAcrossCompanies.krea} color="rose" />
          <SummaryTile icon={ImageIcon} label="Leonardo" value={totalAcrossCompanies.leonardo} color="fuchsia" />
          <SummaryTile icon={MessageSquare} label="Tutor" value={totalAcrossCompanies.tutor} color="indigo" />
          <SummaryTile icon={Mic} label="ElevenLabs" value={totalAcrossCompanies.elevenlabs} color="amber" />
          <SummaryTile icon={Video} label="HeyGen" value={totalAcrossCompanies.heygen} color="sky" />
        </div>
      )}

      {/* Per-company table */}
      <Card className="bg-slate-900/40 border-slate-800">
        <CardHeader>
          <CardTitle className="text-base text-slate-200 flex items-center gap-2">
            <Building2 className="w-4 h-4" /> Por Empresa
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-800 bg-slate-900/60">
                <tr className="text-left text-xs text-slate-400">
                  <th className="px-4 py-2.5 font-medium">Empresa</th>
                  <th className="px-3 py-2.5 font-medium text-right">Cursos</th>
                  <th className="px-3 py-2.5 font-medium text-right">Krea</th>
                  <th className="px-3 py-2.5 font-medium text-right">Leonardo</th>
                  <th className="px-3 py-2.5 font-medium text-right">Tutor</th>
                  <th className="px-3 py-2.5 font-medium text-right">ElevenLabs</th>
                  <th className="px-3 py-2.5 font-medium text-right">HeyGen</th>
                </tr>
              </thead>
              <tbody>
                {(data?.companies || []).map((c) => (
                  <tr key={c.companyId} className="border-b border-slate-800/60 hover:bg-slate-800/30 transition-colors" data-testid={`cost-row-${c.companyId}`}>
                    <td className="px-4 py-3">
                      <div className="font-medium text-white truncate max-w-[260px]">{c.companyName || '(sem nome)'}</div>
                      <div className="text-[10px] text-slate-500 font-mono">{c.companyId}</div>
                      {c.projects && Object.keys(c.projects).length > 1 && (
                        <div className="flex gap-1 mt-1.5">
                          {Object.entries(c.projects).filter(([k]) => k !== 'total').map(([src, n]) => (
                            <Badge key={src} variant="outline" className="text-[9px] py-0 h-4 border-slate-700 text-slate-400">
                              {src}: {n}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-3 text-right text-emerald-300 font-semibold">{c.projects?.total ?? 0}</td>
                    <td className="px-3 py-3 text-right text-rose-300">{c.krea?.total ?? 0}</td>
                    <td className="px-3 py-3 text-right text-fuchsia-300">{c.leonardo?.total ?? 0}</td>
                    <td className="px-3 py-3 text-right text-indigo-300">{c.tutor?.total ?? 0}</td>
                    <td className="px-3 py-3 text-right text-amber-300">{c.elevenlabs?.total ?? 0}</td>
                    <td className="px-3 py-3 text-right text-sky-300">{c.heygen?.total ?? 0}</td>
                  </tr>
                ))}
                {!loading && (data?.companies || []).length === 0 && (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-500 text-sm">
                    Nenhuma empresa encontrada para o período selecionado.
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {data?.generatedAt && (
        <p className="text-[11px] text-slate-500 text-right">
          Relatório gerado em {new Date(data.generatedAt).toLocaleString('pt-BR')}.
        </p>
      )}
    </div>
  );
}

function SummaryTile({ icon: Icon, label, value, color }) {
  const colorMap = {
    emerald: 'text-emerald-300 border-emerald-700/30 bg-emerald-900/10',
    rose: 'text-rose-300 border-rose-700/30 bg-rose-900/10',
    fuchsia: 'text-fuchsia-300 border-fuchsia-700/30 bg-fuchsia-900/10',
    indigo: 'text-indigo-300 border-indigo-700/30 bg-indigo-900/10',
    amber: 'text-amber-300 border-amber-700/30 bg-amber-900/10',
    sky: 'text-sky-300 border-sky-700/30 bg-sky-900/10',
  };
  return (
    <div className={`rounded-lg border p-3 ${colorMap[color] || ''}`}>
      <div className="flex items-center gap-1.5 text-[10px] uppercase font-semibold tracking-wider opacity-80">
        <Icon className="w-3 h-3" />
        {label}
      </div>
      <div className="text-2xl font-bold mt-1">{value.toLocaleString('pt-BR')}</div>
    </div>
  );
}
