import React, { useState, useEffect } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Label } from './ui/label';
import { Building2, Loader2 } from 'lucide-react';
import axios from 'axios';
import { getApiUrl } from '../utils/apiUrl';
import { useAuth, authHeaders } from '../contexts/AuthContext';

const API_URL = getApiUrl();

/**
 * CompanySelector — dropdown for super_admins to pick which client company
 * a new course belongs to. Hidden for non-super-admin users.
 *
 * Default value = current user's companyId (avoids accidental misattribution).
 *
 * Props:
 *   value           — current companyId (controlled)
 *   onChange(id)    — handler called with the picked companyId
 *   label           — optional override (defaults to "Empresa cliente")
 *   testIdPrefix    — prefix for data-testid attrs (default "company-selector")
 *   disabled        — passed to inner Select
 */
export default function CompanySelector({
  value, onChange, label = 'Empresa cliente',
  testIdPrefix = 'company-selector', disabled = false, native = false,
}) {
  const { user, isSuperAdmin } = useAuth();
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    if (!isSuperAdmin) return;
    setLoading(true);
    setError('');
    axios.get(`${API_URL}/api/companies`, {headers: authHeaders(), timeout: 30000})
      .then((res) => {
        if (cancelled) return;
        const list = (Array.isArray(res.data) ? res.data : (res.data?.companies || [])).filter(c => typeof c?.id === 'string' && c.id);
        setCompanies(list);
        // Default to current user's company on first load if no value is set yet
        if (!value && user?.companyId && list.some(c => c.id === user.companyId)) {
          onChange?.(user.companyId);
        }
      })
      .catch(() => {if (!cancelled) setError('Não foi possível carregar as empresas. Verifique sua conexão e tente novamente.');})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSuperAdmin, attempt]);

  // Hide for non-super-admin — they can only attribute to their own company
  if (!isSuperAdmin) return null;

  return (
    <div className="space-y-2" data-testid={`${testIdPrefix}-wrapper`}>
      <Label htmlFor={`${testIdPrefix}-select`} className="text-xs text-slate-300 font-medium flex items-center gap-1.5">
        <Building2 className="w-3.5 h-3.5" /> {label}
      </Label>
      {native ? <select id={`${testIdPrefix}-select`} aria-label={label} data-testid={`${testIdPrefix}-trigger`}
        className="h-10 w-full rounded-md border border-input px-3 text-sm bg-background text-foreground disabled:opacity-50"
        value={value || ''} disabled={disabled || loading || companies.length === 0} onChange={event => onChange?.(event.target.value)}>
        <option value="" disabled>{loading ? 'Carregando empresas...' : error ? 'Falha ao carregar empresas' : companies.length ? 'Selecione a empresa...' : 'Nenhuma empresa disponível'}</option>
        {companies.map(c => <option key={c.id} value={c.id}>{c.name || '(sem nome)'}{c.id === user?.companyId ? ' (sua empresa)' : ''}</option>)}
      </select> : <Select
        value={value || ''}
        onValueChange={onChange}
        disabled={disabled || loading || companies.length === 0}
      >
        <SelectTrigger id={`${testIdPrefix}-select`} className="h-9 text-sm" data-testid={`${testIdPrefix}-trigger`}>
          {loading ? (
            <span className="flex items-center gap-2 text-slate-400">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Carregando empresas...
            </span>
          ) : (
            <SelectValue placeholder={error ? 'Falha ao carregar empresas' : companies.length ? 'Selecione a empresa...' : 'Nenhuma empresa disponível'} />
          )}
        </SelectTrigger>
        <SelectContent>
          {companies.map((c) => (
            <SelectItem key={c.id} value={c.id} data-testid={`${testIdPrefix}-option-${c.id}`}>
              <div className="flex items-center gap-2">
                <span>{c.name || '(sem nome)'}</span>
                {c.id === user?.companyId && (
                  <span className="text-[10px] text-amber-400 font-semibold">
                    (sua empresa)
                  </span>
                )}
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>}
      {error && <div role="alert" className="text-xs text-amber-300 space-y-1"><p>{error}</p><button type="button" className="underline font-semibold" disabled={disabled || loading} onClick={() => setAttempt(previous => previous + 1)}>Tentar novamente</button></div>}
      {!loading && !error && companies.length === 0 && <p role="status" className="text-xs text-amber-300">Não há empresas cadastradas disponíveis para seleção. Confira Administração → Empresas.</p>}
      <p className="text-[10px] text-slate-500">
        Como super-admin, você pode atribuir cursos a qualquer empresa cliente para depois identificar custos no relatório.
      </p>
    </div>
  );
}
