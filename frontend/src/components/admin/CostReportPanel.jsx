import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../ui/dialog';
import {
  Loader2, RefreshCw, FileText, Image as ImageIcon, MessageSquare,
  Mic, Video, DollarSign, Building2, Settings as SettingsIcon, Wand2,
} from 'lucide-react';
import { toast } from 'sonner';
import { getApiUrl } from '../../utils/apiUrl';

const API_URL = getApiUrl();

const fmtMoney = (v, currency) =>
  v.toLocaleString('pt-BR', { style: 'currency', currency, minimumFractionDigits: 2 });

/**
 * Cost Report Panel — super_admin only.
 * Shows aggregated AI usage + monetary estimates (USD + BRL) per client company.
 */
export default function CostReportPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [currency, setCurrency] = useState('BRL'); // BRL | USD
  const [showPricing, setShowPricing] = useState(false);

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

  const totals = (data?.companies || []).reduce(
    (acc, c) => ({
      projects: acc.projects + (c.projects?.total || 0),
      krea: acc.krea + (c.krea?.total || 0),
      leonardo: acc.leonardo + (c.leonardo?.total || 0),
      tutor: acc.tutor + (c.tutor?.total || 0),
      elevenlabs: acc.elevenlabs + (c.elevenlabs?.total || 0),
      heygen: acc.heygen + (c.heygen?.total || 0),
      usd: acc.usd + (c.totalUsd || 0),
      brl: acc.brl + (c.totalBrl || 0),
    }),
    { projects: 0, krea: 0, leonardo: 0, tutor: 0, elevenlabs: 0, heygen: 0, usd: 0, brl: 0 },
  );
  const moneyKey = currency === 'USD' ? 'usd' : 'brl';

  return (
    <div className="space-y-6" data-testid="cost-report-panel">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <DollarSign className="w-6 h-6 text-emerald-400" />
            Custos por Empresa
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Estimativas de custo de IA por empresa cliente para faturamento.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-slate-800 rounded-md p-1" role="group">
            {['BRL', 'USD'].map((cur) => (
              <button
                key={cur} type="button"
                onClick={() => setCurrency(cur)}
                aria-pressed={currency === cur}
                className={`px-2.5 py-1 rounded text-[11px] font-bold transition-colors ${
                  currency === cur ? 'bg-emerald-500/20 text-emerald-300' : 'text-slate-400 hover:text-slate-200'
                }`}
                data-testid={`cost-currency-${cur}`}
              >
                {cur}
              </button>
            ))}
          </div>
          <Button
            variant="outline" size="sm"
            onClick={() => setShowPricing(true)}
            className="gap-2"
            data-testid="cost-edit-pricing-btn"
          >
            <SettingsIcon className="w-4 h-4" />
            Tabela de preços
          </Button>
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
      </div>

      <Card className="bg-slate-900/40 border-slate-800">
        <CardContent className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-1">
            <Label htmlFor="cost-from" className="text-xs text-slate-400">De (inclusive)</Label>
            <Input id="cost-from" type="date" value={from}
                   onChange={(e) => setFrom(e.target.value)}
                   className="bg-slate-900 border-slate-700"
                   data-testid="cost-from-input"/>
          </div>
          <div className="space-y-1">
            <Label htmlFor="cost-to" className="text-xs text-slate-400">Até (exclusive)</Label>
            <Input id="cost-to" type="date" value={to}
                   onChange={(e) => setTo(e.target.value)}
                   className="bg-slate-900 border-slate-700"
                   data-testid="cost-to-input"/>
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
        <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {data?.companies && (
        <Card className="bg-gradient-to-r from-emerald-900/30 to-emerald-800/20 border-emerald-700/40" data-testid="cost-grand-total">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-wider text-emerald-300 font-bold">Custo total estimado</div>
              <div className="text-3xl font-bold text-emerald-300 mt-1">
                {fmtMoney(totals[moneyKey], currency)}
              </div>
              <div className="text-[11px] text-emerald-200/60 mt-1">
                {currency === 'BRL'
                  ? `≈ ${fmtMoney(totals.usd, 'USD')} • cotação ${data.pricing?.usdToBrl || 5.0} R$/US$`
                  : `≈ ${fmtMoney(totals.brl, 'BRL')}`}
              </div>
            </div>
            <DollarSign className="w-12 h-12 text-emerald-500/30" />
          </CardContent>
        </Card>
      )}

      {data?.companies && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3" data-testid="cost-totals">
          <SummaryTile icon={FileText} label="Cursos" value={totals.projects} color="emerald" />
          <SummaryTile icon={ImageIcon} label="Krea" value={totals.krea} color="rose" />
          <SummaryTile icon={ImageIcon} label="Leonardo" value={totals.leonardo} color="fuchsia" />
          <SummaryTile icon={MessageSquare} label="Tutor" value={totals.tutor} color="indigo" />
          <SummaryTile icon={Mic} label="ElevenLabs" value={totals.elevenlabs} color="amber" />
          <SummaryTile icon={Video} label="HeyGen" value={totals.heygen} color="sky" />
        </div>
      )}

      <Card className="bg-slate-900/40 border-slate-800">
        <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
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
                  <th className="px-3 py-2.5 font-medium text-right">11Labs</th>
                  <th className="px-3 py-2.5 font-medium text-right">HeyGen</th>
                  <th className="px-3 py-2.5 font-bold text-right text-emerald-400">Total {currency}</th>
                </tr>
              </thead>
              <tbody>
                {(data?.companies || []).map((c) => (
                  <tr key={c.companyId} className="border-b border-slate-800/60 hover:bg-slate-800/30 transition-colors" data-testid={`cost-row-${c.companyId}`}>
                    <td className="px-4 py-3">
                      <div className="font-medium text-white truncate max-w-[260px]">{c.companyName || '(sem nome)'}</div>
                      <div className="text-[10px] text-slate-500 font-mono">{c.companyId}</div>
                      {c.projects && Object.keys(c.projects).length > 1 && (
                        <div className="flex gap-1 mt-1.5 flex-wrap">
                          {Object.entries(c.projects).filter(([k]) => k !== 'total').map(([src, n]) => (
                            <Badge key={src} variant="outline" className="text-[9px] py-0 h-4 border-slate-700 text-slate-400">
                              {src}: {n}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-3 text-right text-emerald-300 font-semibold">{c.projects?.total ?? 0}</td>
                    <CountAndCost cell={c.krea} currency={currency} color="rose" />
                    <CountAndCost cell={c.leonardo} currency={currency} color="fuchsia" />
                    <CountAndCost cell={c.tutor} currency={currency} color="indigo" />
                    <CountAndCost cell={c.elevenlabs} currency={currency} color="amber" />
                    <CountAndCost cell={c.heygen} currency={currency} color="sky" />
                    <td className="px-3 py-3 text-right font-bold text-emerald-300 text-base">
                      {fmtMoney(currency === 'USD' ? c.totalUsd : c.totalBrl, currency)}
                    </td>
                  </tr>
                ))}
                {!loading && (data?.companies || []).length === 0 && (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-500 text-sm">
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

      <PricingDialog open={showPricing} onClose={() => { setShowPricing(false); load(); }} />
    </div>
  );
}

function CountAndCost({ cell, currency, color }) {
  if (!cell) return <td className="px-3 py-3 text-right text-slate-500">—</td>;
  const colorMap = {
    rose: 'text-rose-300', fuchsia: 'text-fuchsia-300',
    indigo: 'text-indigo-300', amber: 'text-amber-300', sky: 'text-sky-300',
  };
  const cost = currency === 'USD' ? cell.usd : cell.brl;
  return (
    <td className="px-3 py-3 text-right">
      <div className={`${colorMap[color]} font-semibold`}>{cell.total}</div>
      {cost > 0 && (
        <div className="text-[10px] text-slate-500">{fmtMoney(cost || 0, currency)}</div>
      )}
    </td>
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

const RATE_LABELS = {
  leonardo: 'Leonardo AI (por imagem)',
  krea_default: 'Krea AI (fallback - quando modelo desconhecido)',
  tutor: 'AI Tutor (por mensagem)',
  elevenlabs: 'ElevenLabs (por geração)',
  heygen: 'HeyGen (por vídeo de avatar)',
};

function PricingDialog({ open, onClose }) {
  const [pricing, setPricing] = useState(null);
  const [rates, setRates] = useState({});
  const [usdToBrl, setUsdToBrl] = useState(5);
  const [kreaOverrides, setKreaOverrides] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    axios.get(`${API_URL}/api/admin/cost-pricing`).then((r) => {
      setPricing(r.data);
      setRates(r.data.rates || {});
      setUsdToBrl(r.data.usdToBrl || 5);
      setKreaOverrides(r.data.kreaOverrides || {});
    }).catch(() => {});
  }, [open]);

  const onSave = async () => {
    setSaving(true);
    try {
      await axios.put(`${API_URL}/api/admin/cost-pricing`, {
        rates, usdToBrl, kreaOverrides,
      });
      toast.success('Tabela de preços atualizada');
      onClose();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Erro ao salvar preços');
    } finally {
      setSaving(false);
    }
  };

  const setRate = (k, v) => setRates((p) => ({ ...p, [k]: parseFloat(v) || 0 }));
  const setKreaOverride = (id, v) => setKreaOverrides((p) => {
    if (v === '' || v === null || v === undefined) { const c = { ...p }; delete c[id]; return c; }
    return { ...p, [id]: parseFloat(v) || 0 };
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="pricing-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <SettingsIcon className="w-5 h-5 text-emerald-400" /> Tabela de Preços
          </DialogTitle>
          <DialogDescription>
            Ajuste o custo unitário (USD) de cada integração. Os valores afetam o cálculo
            de custos no relatório. Cotação USD → BRL aplica-se ao total.
          </DialogDescription>
        </DialogHeader>

        {!pricing ? (
          <div className="py-6 flex items-center justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
          </div>
        ) : (
          <div className="space-y-6 py-2">
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-200">Preços padrão (USD)</h3>
              <div className="grid md:grid-cols-2 gap-3">
                {Object.keys(RATE_LABELS).map((k) => (
                  <div key={k} className="space-y-1">
                    <Label className="text-xs text-slate-400">{RATE_LABELS[k]}</Label>
                    <Input
                      type="number" step="0.001" min="0"
                      value={rates[k] ?? ''}
                      onChange={(e) => setRate(k, e.target.value)}
                      placeholder={`default: $${pricing.defaults[k]}`}
                      className="bg-slate-900 border-slate-700"
                      data-testid={`pricing-rate-${k}`}
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-xs text-slate-400">Cotação USD → BRL</Label>
              <Input
                type="number" step="0.01" min="0.01"
                value={usdToBrl}
                onChange={(e) => setUsdToBrl(parseFloat(e.target.value) || 0)}
                className="bg-slate-900 border-slate-700 max-w-[200px]"
                data-testid="pricing-usd-brl"
              />
              <p className="text-[11px] text-slate-500">
                Default: {pricing.defaultUsdToBrl} R$/US$
              </p>
            </div>

            {pricing.kreaCatalog?.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                  <Wand2 className="w-4 h-4 text-rose-400" /> Krea AI — preços por modelo
                </h3>
                <p className="text-[11px] text-slate-500">
                  Sobrescreve o catálogo padrão. Deixe em branco para usar o valor do catálogo.
                </p>
                <div className="grid md:grid-cols-2 gap-3 max-h-[300px] overflow-y-auto pr-2">
                  {pricing.kreaCatalog.map((m) => (
                    <div key={m.id} className="flex items-center gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-slate-200 truncate flex items-center gap-1.5">
                          {m.label}
                          <span className="text-[9px]">{m.tier === 'premium' ? '⭐' : '⚡'}</span>
                        </div>
                        <div className="text-[10px] text-slate-500">catálogo: ${m.default}</div>
                      </div>
                      <Input
                        type="number" step="0.001" min="0"
                        value={kreaOverrides[m.id] ?? ''}
                        onChange={(e) => setKreaOverride(m.id, e.target.value)}
                        placeholder="—"
                        className="bg-slate-900 border-slate-700 w-24 text-xs"
                        data-testid={`pricing-krea-${m.id}`}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button onClick={onSave} disabled={saving} data-testid="pricing-save-btn">
            {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
            Salvar tabela de preços
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
