import React, { useState, useEffect, useCallback } from 'react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { authHeaders } from '../contexts/AuthContext';
import { getApiUrl } from '../utils/apiUrl';
import {
  Activity,
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
  Database,
  Sparkles,
  Image as ImageIcon,
  Video,
  Mic,
  Mail,
  FileText,
  Loader2,
} from 'lucide-react';

const API_URL = getApiUrl();

const INTEGRATION_META = {
  mongodb: { label: 'MongoDB', icon: Database, description: 'Banco de dados principal' },
  openai: { label: 'OpenAI', icon: Sparkles, description: 'Geracao de texto e IA' },
  leonardo: { label: 'Leonardo AI', icon: ImageIcon, description: 'Geracao de imagens' },
  krea: { label: 'Krea AI', icon: ImageIcon, description: 'Geracao de imagens (40+ modelos)' },
  heygen: { label: 'HeyGen', icon: Video, description: 'Geracao de videos com avatar' },
  kling: { label: 'Kling AI', icon: Video, description: 'Videos educativos a partir de storyboards' },
  elevenlabs: { label: 'ElevenLabs', icon: Mic, description: 'Text-to-speech' },
  resend: { label: 'Resend', icon: Mail, description: 'Envio de emails transacionais' },
  convertapi: { label: 'ConvertAPI', icon: FileText, description: 'Conversao de PPT/documentos' },
};

const STATUS_META = {
  ok: { color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/30', icon: CheckCircle2, label: 'Online' },
  error: { color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30', icon: XCircle, label: 'Erro' },
  not_configured: { color: 'text-slate-400', bg: 'bg-slate-500/10', border: 'border-slate-500/30', icon: AlertCircle, label: 'Nao configurado' },
};

function formatBalance(name, balance) {
  if (!balance) return null;
  if (name === 'leonardo') {
    const paid = balance.apiPaidTokens ?? 0;
    const sub = balance.subscriptionTokens ?? 0;
    return `${paid.toLocaleString('pt-BR')} tokens pagos + ${sub} assinatura`;
  }
  if (name === 'heygen') {
    if (balance.remainingQuota != null) return `${balance.remainingQuota.toLocaleString('pt-BR')} creditos restantes`;
    return `${balance.voicesAvailable} vozes disponiveis`;
  }
  if (name === 'elevenlabs') {
    const used = balance.charactersUsed ?? 0;
    const limit = balance.characterLimit ?? 0;
    const pct = limit > 0 ? Math.round((used / limit) * 100) : 0;
    return `${used.toLocaleString('pt-BR')} / ${limit.toLocaleString('pt-BR')} caracteres (${pct}%)`;
  }
  if (name === 'convertapi') {
    return `${balance.secondsLeft?.toLocaleString('pt-BR') ?? '?'} segundos restantes`;
  }
  if (name === 'krea') {
    if (balance.modelsAvailable != null) return `${balance.modelsAvailable} modelos de imagem disponiveis`;
    return null;
  }
  if (name === 'kling') {
    return `${balance.model || 'kling-3.0'} · ate ${balance.maxDurationSeconds || 15}s por cena`;
  }
  return null;
}

export default function IntegrationsHealthPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchHealth = useCallback(async (forceRefresh = false) => {
    if (forceRefresh) setRefreshing(true); else setLoading(true);
    try {
      // Add timestamp to bust the cache on server-side if forced
      const url = forceRefresh
        ? `${API_URL}/api/admin/integrations-health?_t=${Date.now()}`
        : `${API_URL}/api/admin/integrations-health`;
      const res = await fetch(url, { headers: authHeaders() });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const body = await res.json();
      setData(body);
    } catch (e) {
      setData({ error: e.message, integrations: {}, overall: 'error' });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    // Auto-refresh every 60s while panel is visible
    const id = setInterval(() => fetchHealth(), 60000);
    return () => clearInterval(id);
  }, [fetchHealth]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-400 gap-3" data-testid="integrations-loading">
        <Loader2 className="w-6 h-6 animate-spin" />
        <span>Verificando integracoes...</span>
      </div>
    );
  }

  const integrations = data?.integrations || {};
  const overall = data?.overall || 'unknown';
  const checkedAt = data?.checkedAt ? new Date(data.checkedAt) : null;
  const cached = data?.cached;

  return (
    <div className="space-y-6" data-testid="integrations-health-panel">
      {/* Header with overall status */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold text-white">Saude das Integracoes</h2>
            <Badge
              variant="outline"
              className={`${
                overall === 'ok'
                  ? 'border-green-500/50 text-green-300 bg-green-500/10'
                  : overall === 'degraded'
                  ? 'border-amber-500/50 text-amber-300 bg-amber-500/10'
                  : 'border-slate-500/50 text-slate-300'
              } uppercase text-xs tracking-wide`}
              data-testid="overall-status-badge"
            >
              {overall === 'ok' ? 'Tudo OK' : overall === 'degraded' ? 'Degradado' : overall}
            </Badge>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            {checkedAt ? (
              <>
                Verificado {checkedAt.toLocaleTimeString('pt-BR')}
                {cached && <span className="text-slate-500"> (cache de {data.cacheAgeSeconds}s)</span>}
              </>
            ) : 'Status das integracoes externas'}
          </p>
        </div>
        <Button
          onClick={() => fetchHealth(true)}
          disabled={refreshing}
          variant="outline"
          className="gap-2"
          data-testid="refresh-health-btn"
        >
          {refreshing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          {refreshing ? 'Atualizando...' : 'Atualizar agora'}
        </Button>
      </div>

      {/* Integration cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.entries(INTEGRATION_META).map(([key, meta]) => {
          const result = integrations[key] || { status: 'not_configured' };
          const status = result.status || 'unknown';
          const sMeta = STATUS_META[status] || STATUS_META.not_configured;
          const StatusIcon = sMeta.icon;
          const MetaIcon = meta.icon;
          const balance = formatBalance(key, result.balance);

          return (
            <Card
              key={key}
              className={`p-5 bg-slate-900/50 border-2 ${sMeta.border} transition hover:bg-slate-900/70`}
              data-testid={`integration-card-${key}`}
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${sMeta.bg}`}>
                    <MetaIcon className={`w-5 h-5 ${sMeta.color}`} />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white text-sm">{meta.label}</h3>
                    <p className="text-xs text-slate-500">{meta.description}</p>
                  </div>
                </div>
                <StatusIcon className={`w-5 h-5 flex-shrink-0 ${sMeta.color}`} />
              </div>

              <div className="flex items-center justify-between text-xs">
                <span className={`${sMeta.color} font-medium`}>{sMeta.label}</span>
                {result.latencyMs != null && (
                  <span className="text-slate-500 flex items-center gap-1">
                    <Activity className="w-3 h-3" />
                    {result.latencyMs}ms
                  </span>
                )}
              </div>

              {balance && (
                <div className="mt-3 pt-3 border-t border-slate-800">
                  <p className="text-xs text-slate-400">
                    <span className="text-slate-500">Saldo: </span>
                    <span className="text-slate-300 font-medium">{balance}</span>
                  </p>
                </div>
              )}

              {key === 'openai' && result.status === 'ok' && (
                <div className="mt-3 pt-3 border-t border-slate-800">
                  <p className="text-xs text-slate-400">
                    <span className="text-slate-500">Modelo: </span>
                    <span className="text-slate-300 font-medium">{result.model || 'configurado no servidor'}</span>
                  </p>
                </div>
              )}

              {result.error && (
                <div className="mt-3 pt-3 border-t border-slate-800">
                  <p className="text-xs text-red-400 break-all" data-testid={`integration-error-${key}`}>
                    {result.error}
                  </p>
                </div>
              )}
            </Card>
          );
        })}
      </div>

      {data?.error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-300 text-sm">
          Erro ao carregar status: {data.error}
        </div>
      )}

      <p className="text-xs text-slate-500 text-center">
        Atualizacao automatica a cada 60 segundos. Resultados cacheados por 60s no servidor para economizar chamadas pagas.
      </p>
    </div>
  );
}
