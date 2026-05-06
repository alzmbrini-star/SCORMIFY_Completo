import React, { useState, useEffect } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Label } from './ui/label';
import { Building2, Loader2 } from 'lucide-react';
import axios from 'axios';
import { getApiUrl } from '../utils/apiUrl';
import { useAuth } from '../contexts/AuthContext';

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
  testIdPrefix = 'company-selector', disabled = false,
}) {
  const { user, isSuperAdmin } = useAuth();
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!isSuperAdmin) return;
    setLoading(true);
    axios.get(`${API_URL}/api/companies`)
      .then((res) => {
        if (cancelled) return;
        const list = Array.isArray(res.data) ? res.data : (res.data?.companies || []);
        setCompanies(list);
        // Default to current user's company on first load if no value is set yet
        if (!value && user?.companyId) {
          onChange?.(user.companyId);
        }
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSuperAdmin]);

  // Hide for non-super-admin — they can only attribute to their own company
  if (!isSuperAdmin) return null;

  return (
    <div className="space-y-2" data-testid={`${testIdPrefix}-wrapper`}>
      <Label className="text-xs text-slate-300 font-medium flex items-center gap-1.5">
        <Building2 className="w-3.5 h-3.5" /> {label}
      </Label>
      <Select
        value={value || ''}
        onValueChange={onChange}
        disabled={disabled || loading || companies.length === 0}
      >
        <SelectTrigger className="h-9 text-sm" data-testid={`${testIdPrefix}-trigger`}>
          {loading ? (
            <span className="flex items-center gap-2 text-slate-400">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Carregando empresas...
            </span>
          ) : (
            <SelectValue placeholder="Selecione a empresa..." />
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
      </Select>
      <p className="text-[10px] text-slate-500">
        Como super-admin, você pode atribuir cursos a qualquer empresa cliente para depois identificar custos no relatório.
      </p>
    </div>
  );
}
