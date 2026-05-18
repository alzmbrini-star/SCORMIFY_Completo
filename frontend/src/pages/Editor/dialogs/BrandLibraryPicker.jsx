/**
 * BrandLibraryPicker — Modal grid that lets an Editor author choose an image
 * from their company's Brand Library and apply it as a slide's background.
 *
 * Usage:
 *   <BrandLibraryPicker
 *     open={open}
 *     onClose={() => setOpen(false)}
 *     companyId={project.companyId}
 *     onPick={(asset) => setBackgroundImage(asset.url)}
 *   />
 *
 * Includes:
 *   - Type & Category filters (same vocabulary as the Admin dialog).
 *   - Inline empty/error states so the author understands why no images show.
 *   - Click-to-pick — single confirmation, no extra "Confirm" button.
 */
import React, { useEffect, useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../../components/ui/dialog';
import { Button } from '../../../components/ui/button';
import { Layers, Image as ImageIcon, RefreshCw } from 'lucide-react';
import { getApiUrl } from '../../../utils/apiUrl';

const API_URL = getApiUrl();

const TYPE_OPTIONS = [
  { value: '', label: 'Todos' },
  { value: 'background', label: 'Fundo' },
  { value: 'illustration', label: 'Ilustração' },
  { value: 'icon', label: 'Ícone' },
  { value: 'logo', label: 'Logo' },
  { value: 'cover', label: 'Capa' },
];

const CATEGORY_OPTIONS = [
  { value: '', label: 'Todas' },
  { value: 'intro', label: 'Abertura' },
  { value: 'content', label: 'Conteúdo' },
  { value: 'transition', label: 'Transição' },
  { value: 'conclusion', label: 'Conclusão' },
  { value: 'light_bg', label: 'Fundo Claro' },
  { value: 'dark_bg', label: 'Fundo Escuro' },
  { value: 'generic', label: 'Genérico' },
];

export default function BrandLibraryPicker({ open, onClose, companyId, onPick, onPickForAll, defaultType = 'background' }) {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [filterType, setFilterType] = useState(defaultType);
  const [filterCategory, setFilterCategory] = useState('');
  // When true, picking an image applies it to EVERY slide of the project
  // (not just the currently-open one). Defaults OFF so the existing
  // single-slide behavior is preserved. The parent passes a `onPickForAll`
  // callback to opt in to the bulk path; without it the toggle hides.
  const [applyToAll, setApplyToAll] = useState(false);

  const token = typeof window !== 'undefined' ? localStorage.getItem('scormify_auth_token') : '';

  const load = async () => {
    if (!companyId) {
      setError('Este projeto nao esta vinculado a uma empresa.');
      setAssets([]);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const qs = new URLSearchParams();
      if (filterType) qs.set('type', filterType);
      if (filterCategory) qs.set('category', filterCategory);
      const r = await fetch(
        `${API_URL}/api/companies/${companyId}/assets?${qs.toString()}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!r.ok) {
        if (r.status === 403) setError('Voce nao tem acesso a biblioteca desta empresa.');
        else setError('Nao foi possivel carregar a biblioteca.');
        setAssets([]);
        return;
      }
      const d = await r.json();
      setAssets(d.assets || []);
    } catch (_e) {
      setError('Erro de rede.');
      setAssets([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, companyId, filterType, filterCategory]);

  const handlePick = (asset) => {
    // The asset's `url` is already a full path (`/api/companies/.../file`).
    // The editor / runtime resolves it against the current API base.
    if (applyToAll && onPickForAll) {
      // Bulk apply — parent is responsible for hitting
      // POST /api/projects/{pid}/apply-background-all with the asset url.
      onPickForAll(asset);
    } else {
      onPick?.(asset);
    }
    onClose?.();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent
        className="max-w-4xl max-h-[85vh] overflow-y-auto"
        data-testid="brand-library-picker"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-indigo-500" />
            Biblioteca de Marca — Selecionar Imagem
          </DialogTitle>
        </DialogHeader>

        {/* Apply-to-all toggle — only shows when the parent provided an
            onPickForAll handler. Lets the author broadcast the picked
            image to every slide of the project in a single click. */}
        {onPickForAll && (
          <label
            className="flex items-center gap-2 p-2.5 rounded border border-indigo-500/40 bg-indigo-500/10 cursor-pointer transition hover:border-indigo-400"
            data-testid="blp-apply-to-all-toggle"
          >
            <input
              type="checkbox"
              checked={applyToAll}
              onChange={(e) => setApplyToAll(e.target.checked)}
              className="w-4 h-4 accent-indigo-500 cursor-pointer"
            />
            <span className="text-xs flex-1">
              <strong className="text-indigo-400">Aplicar em TODOS os slides do curso</strong>
              <span className="text-muted-foreground"> — ao inves de so neste slide</span>
            </span>
            {applyToAll && (
              <span className="text-[10px] text-indigo-300 font-semibold">SELECIONE A IMAGEM →</span>
            )}
          </label>
        )}

        {/* Filters */}
        <div className="flex flex-wrap gap-2 items-center">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            data-testid="blp-filter-type"
            className="border rounded px-2 py-1 text-sm bg-background"
          >
            {TYPE_OPTIONS.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            data-testid="blp-filter-category"
            className="border rounded px-2 py-1 text-sm bg-background"
          >
            {CATEGORY_OPTIONS.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
          <Button
            variant="outline"
            size="sm"
            onClick={load}
            disabled={loading}
            data-testid="blp-reload"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1 ${loading ? 'animate-spin' : ''}`} />
            Recarregar
          </Button>
        </div>

        {/* Body */}
        {error ? (
          <div className="text-center py-12 text-muted-foreground border border-dashed rounded">
            <p className="text-sm">{error}</p>
            <p className="text-xs mt-1">Peca ao administrador da empresa para popular a biblioteca em /admin.</p>
          </div>
        ) : loading ? (
          <div className="text-center py-12 text-muted-foreground">Carregando...</div>
        ) : assets.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground border border-dashed rounded">
            <ImageIcon className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p>Nenhuma imagem encontrada com esses filtros.</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3" data-testid="blp-grid">
            {assets.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => handlePick(a)}
                data-testid={`blp-pick-${a.id}`}
                className="group border rounded overflow-hidden hover:ring-2 hover:ring-indigo-500 transition"
                title={a.description || a.originalFilename}
              >
                <div className="relative aspect-video bg-muted">
                  <img
                    src={`${API_URL}${a.url}`}
                    alt={a.originalFilename}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                </div>
                <div className="p-2 text-left">
                  <p className="text-[11px] truncate font-medium">
                    {a.originalFilename || a.filename}
                  </p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {a.category && a.category !== 'generic' && (
                      <span className="text-[9px] bg-slate-200 dark:bg-slate-700 rounded px-1">
                        {CATEGORY_OPTIONS.find((c) => c.value === a.category)?.label || a.category}
                      </span>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
