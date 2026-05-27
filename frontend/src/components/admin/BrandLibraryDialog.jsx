/**
 * BrandLibraryDialog — Super-admin manager for a company's Brand Library.
 *
 * Two side-by-side tabs:
 *   • Imagens — upload / list / filter / delete corporate imagery the AI
 *     Agent can use as slide backgrounds, illustrations, icons, logos.
 *   • Identidade — color palette (primary/secondary/accent) and font family
 *     applied automatically by the Agent when generating slides.
 *
 * Persists to /api/companies/{id}/assets and /api/companies/{id}/brand-kit.
 */
import { useState, useEffect, useRef } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Textarea } from "../ui/textarea";
import { Label } from "../ui/label";
import { toast } from "sonner";
import {
  Upload, Trash2, Tag, Layers, Palette, Image as ImageIcon, X,
} from "lucide-react";
import { getApiUrl } from "../../utils/apiUrl";

const API_URL = getApiUrl();

const ASSET_TYPES = [
  { value: "background", label: "Fundo" },
  { value: "illustration", label: "Ilustração" },
  { value: "icon", label: "Ícone" },
  { value: "logo", label: "Logo" },
  { value: "cover", label: "Capa" },
  { value: "other", label: "Outro" },
];

const CATEGORIES = [
  { value: "intro", label: "Abertura" },
  { value: "content", label: "Conteúdo" },
  { value: "transition", label: "Transição" },
  { value: "conclusion", label: "Conclusão" },
  { value: "light_bg", label: "Fundo Claro" },
  { value: "dark_bg", label: "Fundo Escuro" },
  { value: "generic", label: "Genérico" },
];

export default function BrandLibraryDialog({ open, onClose, company }) {
  const [tab, setTab] = useState("assets");
  const [assets, setAssets] = useState([]);
  const [filterType, setFilterType] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [loading, setLoading] = useState(false);
  const [brandKit, setBrandKit] = useState({
    primaryColor: "", secondaryColor: "", accentColor: "", fontFamily: "", logoUrl: "",
    logoPlacement: "bottom-right", logoSize: 96,
  });
  // Upload form state
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadType, setUploadType] = useState("background");
  const [uploadCategory, setUploadCategory] = useState("generic");
  const [uploadTags, setUploadTags] = useState("");
  const [uploadDesc, setUploadDesc] = useState("");
  const fileInputRef = useRef(null);

  const token = localStorage.getItem("scormify_auth_token");

  // -------- fetchers -------------------------------------------------------
  const loadAssets = async () => {
    if (!company?.id) return;
    setLoading(true);
    try {
      const qs = new URLSearchParams();
      if (filterType) qs.set("type", filterType);
      if (filterCategory) qs.set("category", filterCategory);
      const r = await fetch(
        `${API_URL}/api/companies/${company.id}/assets?${qs.toString()}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const d = await r.json();
      setAssets(d.assets || []);
    } catch (e) {
      toast.error("Erro ao carregar biblioteca");
    } finally {
      setLoading(false);
    }
  };

  const loadBrandKit = async () => {
    if (!company?.id) return;
    try {
      const r = await fetch(
        `${API_URL}/api/companies/${company.id}/brand-kit`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const d = await r.json();
      setBrandKit({
        primaryColor: d.primaryColor || "",
        secondaryColor: d.secondaryColor || "",
        accentColor: d.accentColor || "",
        fontFamily: d.fontFamily || "",
        logoUrl: d.logoUrl || "",
        logoPlacement: d.logoPlacement || "bottom-right",
        logoSize: Number.isFinite(d.logoSize) ? d.logoSize : 96,
      });
    } catch (e) {
      // ignore — empty kit is a normal state
    }
  };

  useEffect(() => {
    if (open && company) {
      loadAssets();
      loadBrandKit();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, company, filterType, filterCategory]);

  // -------- handlers -------------------------------------------------------
  const handleUpload = async (file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("type", uploadType);
    fd.append("category", uploadCategory);
    fd.append("tags", uploadTags);
    fd.append("description", uploadDesc);
    try {
      const r = await fetch(
        `${API_URL}/api/companies/${company.id}/assets`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: fd,
        },
      );
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || "Falha no upload");
      }
      toast.success("Imagem adicionada à biblioteca");
      setUploadOpen(false);
      setUploadTags("");
      setUploadDesc("");
      loadAssets();
    } catch (e) {
      toast.error(e.message || "Erro no upload");
    }
  };

  const handleDelete = async (asset) => {
    if (!confirm(`Remover "${asset.originalFilename || asset.filename}" da biblioteca?`)) return;
    try {
      const r = await fetch(
        `${API_URL}/api/companies/${company.id}/assets/${asset.id}`,
        { method: "DELETE", headers: { Authorization: `Bearer ${token}` } },
      );
      if (!r.ok) throw new Error();
      toast.success("Imagem removida");
      setAssets((s) => s.filter((a) => a.id !== asset.id));
    } catch (e) {
      toast.error("Erro ao remover");
    }
  };

  const handleSaveBrandKit = async () => {
    try {
      const r = await fetch(
        `${API_URL}/api/companies/${company.id}/brand-kit`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(brandKit),
        },
      );
      if (!r.ok) throw new Error();
      toast.success("Identidade visual salva");
    } catch (e) {
      toast.error("Erro ao salvar identidade");
    }
  };

  // -------- render ---------------------------------------------------------
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent
        className="max-w-5xl max-h-[90vh] overflow-y-auto bg-slate-900 border-slate-700 text-white"
        data-testid="brand-library-dialog"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Layers className="w-5 h-5 text-indigo-400" />
            Biblioteca de Marca — {company?.name}
          </DialogTitle>
        </DialogHeader>

        {/* Tabs */}
        <div className="flex gap-2 border-b border-slate-700 -mt-2">
          <button
            onClick={() => setTab("assets")}
            data-testid="bl-tab-assets"
            className={`px-4 py-2 text-sm font-medium ${tab === "assets" ? "text-indigo-400 border-b-2 border-indigo-400" : "text-slate-400"}`}
          >
            <ImageIcon className="w-4 h-4 inline-block mr-1" />
            Imagens
          </button>
          <button
            onClick={() => setTab("kit")}
            data-testid="bl-tab-kit"
            className={`px-4 py-2 text-sm font-medium ${tab === "kit" ? "text-indigo-400 border-b-2 border-indigo-400" : "text-slate-400"}`}
          >
            <Palette className="w-4 h-4 inline-block mr-1" />
            Identidade
          </button>
        </div>

        {tab === "assets" && (
          <div className="space-y-4 pt-2">
            {/* Filters + Upload */}
            <div className="flex flex-wrap gap-2 items-center justify-between">
              <div className="flex flex-wrap gap-2">
                <select
                  value={filterType}
                  onChange={(e) => setFilterType(e.target.value)}
                  data-testid="bl-filter-type"
                  className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-white"
                >
                  <option value="">Todos os tipos</option>
                  {ASSET_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
                <select
                  value={filterCategory}
                  onChange={(e) => setFilterCategory(e.target.value)}
                  data-testid="bl-filter-category"
                  className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-white"
                >
                  <option value="">Todas as categorias</option>
                  {CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
              <Button
                onClick={() => setUploadOpen(true)}
                data-testid="bl-open-upload"
                className="bg-indigo-600 hover:bg-indigo-700"
              >
                <Upload className="w-4 h-4 mr-1" /> Adicionar Imagem
              </Button>
            </div>

            {/* Upload panel */}
            {uploadOpen && (
              <div className="bg-slate-800 border border-slate-700 rounded p-4 space-y-3" data-testid="bl-upload-panel">
                <div className="flex items-center justify-between">
                  <h4 className="font-medium">Nova imagem</h4>
                  <Button variant="ghost" size="icon" onClick={() => setUploadOpen(false)}>
                    <X className="w-4 h-4" />
                  </Button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <Label className="text-slate-300">Tipo</Label>
                    <select
                      value={uploadType}
                      onChange={(e) => setUploadType(e.target.value)}
                      data-testid="bl-upload-type"
                      className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-2 text-sm text-white"
                    >
                      {ASSET_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <Label className="text-slate-300">Categoria</Label>
                    <select
                      value={uploadCategory}
                      onChange={(e) => setUploadCategory(e.target.value)}
                      data-testid="bl-upload-category"
                      className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-2 text-sm text-white"
                    >
                      {CATEGORIES.map((c) => (
                        <option key={c.value} value={c.value}>{c.label}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div>
                  <Label className="text-slate-300">Tags (vírgulas)</Label>
                  <Input
                    value={uploadTags}
                    onChange={(e) => setUploadTags(e.target.value)}
                    placeholder="industrial, seguranca, treinamento"
                    data-testid="bl-upload-tags"
                    className="bg-slate-900 border-slate-700 text-white"
                  />
                </div>
                <div>
                  <Label className="text-slate-300">Descrição</Label>
                  <Textarea
                    value={uploadDesc}
                    onChange={(e) => setUploadDesc(e.target.value)}
                    placeholder="Descreva o que aparece na imagem e o contexto recomendado de uso (o agente IA usa isso para escolher)."
                    rows={2}
                    data-testid="bl-upload-desc"
                    className="bg-slate-900 border-slate-700 text-white"
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    data-testid="bl-upload-file"
                    onChange={(e) => handleUpload(e.target.files?.[0])}
                  />
                  <Button
                    onClick={() => fileInputRef.current?.click()}
                    data-testid="bl-upload-confirm"
                    className="bg-emerald-600 hover:bg-emerald-700"
                  >
                    <Upload className="w-4 h-4 mr-1" /> Selecionar arquivo e enviar
                  </Button>
                </div>
              </div>
            )}

            {/* Asset grid */}
            {loading ? (
              <div className="text-center py-8 text-slate-400">Carregando...</div>
            ) : assets.length === 0 ? (
              <div className="text-center py-12 text-slate-400 border border-dashed border-slate-700 rounded">
                <ImageIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>Nenhuma imagem cadastrada ainda.</p>
                <p className="text-xs mt-1">Clique em "Adicionar Imagem" para começar.</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="bl-assets-grid">
                {assets.map((a) => (
                  <div
                    key={a.id}
                    className="bg-slate-800 border border-slate-700 rounded overflow-hidden group hover:border-indigo-500 transition-colors"
                    data-testid={`bl-asset-${a.id}`}
                  >
                    <div className="relative aspect-video bg-slate-950">
                      <img
                        src={`${API_URL}${a.url}`}
                        alt={a.originalFilename || a.filename}
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                      <button
                        onClick={() => handleDelete(a)}
                        className="absolute top-1 right-1 bg-red-600/80 hover:bg-red-600 text-white rounded p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                        data-testid={`bl-delete-${a.id}`}
                        title="Remover"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    <div className="p-2 space-y-1">
                      <p className="text-xs text-white truncate" title={a.originalFilename}>
                        {a.originalFilename || a.filename}
                      </p>
                      <div className="flex flex-wrap gap-1">
                        <span className="text-[10px] bg-indigo-900/50 text-indigo-300 px-1.5 py-0.5 rounded">
                          {ASSET_TYPES.find((t) => t.value === a.type)?.label || a.type}
                        </span>
                        <span className="text-[10px] bg-slate-700 text-slate-300 px-1.5 py-0.5 rounded">
                          {CATEGORIES.find((c) => c.value === a.category)?.label || a.category}
                        </span>
                      </div>
                      {a.tags?.length > 0 && (
                        <p className="text-[10px] text-slate-400 flex items-start gap-1">
                          <Tag className="w-3 h-3 mt-0.5 flex-shrink-0" />
                          <span className="truncate">{a.tags.join(", ")}</span>
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "kit" && (
          <div className="space-y-4 pt-2" data-testid="bl-brand-kit">
            <p className="text-sm text-slate-400">
              Cores e fonte que o Agente IA aplicará automaticamente ao gerar cursos para esta empresa.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                { key: "primaryColor", label: "Cor Primária" },
                { key: "secondaryColor", label: "Cor Secundária" },
                { key: "accentColor", label: "Cor de Destaque" },
              ].map((f) => (
                <div key={f.key}>
                  <Label className="text-slate-300">{f.label}</Label>
                  <div className="flex gap-2 items-center">
                    <input
                      type="color"
                      value={brandKit[f.key] || "#1e40af"}
                      onChange={(e) => setBrandKit({ ...brandKit, [f.key]: e.target.value })}
                      data-testid={`bl-kit-${f.key}-color`}
                      className="w-12 h-10 rounded cursor-pointer bg-transparent border border-slate-700"
                    />
                    <Input
                      value={brandKit[f.key] || ""}
                      onChange={(e) => setBrandKit({ ...brandKit, [f.key]: e.target.value })}
                      placeholder="#1e40af"
                      data-testid={`bl-kit-${f.key}-hex`}
                      className="bg-slate-900 border-slate-700 text-white"
                    />
                  </div>
                </div>
              ))}
            </div>
            <div>
              <Label className="text-slate-300">Fonte</Label>
              <Input
                value={brandKit.fontFamily}
                onChange={(e) => setBrandKit({ ...brandKit, fontFamily: e.target.value })}
                placeholder="Inter, Roboto, Open Sans..."
                data-testid="bl-kit-font"
                className="bg-slate-900 border-slate-700 text-white"
              />
            </div>

            {/* Logo upload — applied as a watermark on the bottom-right of
                every AI-generated slide (when use_brand_library=True). */}
            <div className="border-t border-slate-800 pt-4 space-y-2" data-testid="bl-kit-logo-section">
              <Label className="text-slate-300">Logo da Marca (marca d'agua nos slides)</Label>
              {brandKit.logoUrl ? (
                <div className="flex items-center gap-3 bg-slate-800/50 border border-slate-700 rounded p-3">
                  <div className="w-32 h-16 bg-slate-950 rounded border border-slate-700 flex items-center justify-center overflow-hidden">
                    <img
                      src={brandKit.logoUrl.startsWith('/') ? `${API_URL}${brandKit.logoUrl}` : brandKit.logoUrl}
                      alt="logo"
                      className="max-w-full max-h-full object-contain"
                      data-testid="bl-kit-logo-preview"
                    />
                  </div>
                  <div className="flex-1 text-xs text-slate-400 break-all">{brandKit.logoUrl}</div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setBrandKit({ ...brandKit, logoUrl: "" })}
                    data-testid="bl-kit-logo-remove"
                    className="text-red-400 hover:text-red-300"
                  >
                    Remover
                  </Button>
                </div>
              ) : (
                <p className="text-xs text-slate-500">
                  Nenhum logo configurado. Suba uma imagem PNG/SVG (transparente preferencialmente) para aparecer como marca d'agua em todos os slides gerados pelo Agente IA.
                </p>
              )}
              <input
                ref={(el) => { window.__brandKitLogoFileInput = el; }}
                type="file"
                accept="image/png,image/svg+xml,image/webp"
                className="hidden"
                data-testid="bl-kit-logo-file"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  // Upload as a logo-typed asset, then write its public URL into brandKit.logoUrl
                  const fd = new FormData();
                  fd.append('file', file);
                  fd.append('type', 'logo');
                  fd.append('category', 'generic');
                  fd.append('tags', 'logo,brand-kit');
                  fd.append('description', "Logo oficial da marca - aplicado como marca d'agua nos slides");
                  try {
                    const r = await fetch(`${API_URL}/api/companies/${company.id}/assets`, {
                      method: 'POST',
                      headers: { Authorization: `Bearer ${token}` },
                      body: fd,
                    });
                    if (!r.ok) throw new Error('upload failed');
                    const asset = await r.json();
                    setBrandKit({ ...brandKit, logoUrl: asset.url });
                    toast.success("Logo carregado. Lembre de clicar em Salvar Identidade.");
                    // Refresh the assets tab so the logo also appears in the library grid.
                    loadAssets();
                  } catch (_err) {
                    toast.error("Falha ao subir logo.");
                  }
                  e.target.value = ""; // allow re-upload of the same file
                }}
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.__brandKitLogoFileInput?.click()}
                data-testid="bl-kit-logo-upload"
                className="bg-slate-800 border-slate-700 text-white hover:bg-slate-700"
              >
                <Upload className="w-3.5 h-3.5 mr-2" />
                {brandKit.logoUrl ? "Trocar logo" : "Subir logo"}
              </Button>

              {/* Placement selector — only shown once a logo is configured.
                  Four visual cards, each with a tiny preview rectangle
                  illustrating WHERE the watermark will land. */}
              {brandKit.logoUrl && (
                <div className="mt-3 space-y-2" data-testid="bl-kit-logo-placement-section">
                  <Label className="text-slate-300 text-xs">Posicao do logo nos slides</Label>
                  <div className="grid grid-cols-4 gap-2">
                    {[
                      { value: "bottom-right", label: "Inferior Dir.", dotX: 80, dotY: 40 },
                      { value: "bottom-left", label: "Inferior Esq.", dotX: 12, dotY: 40 },
                      { value: "bottom-center", label: "Inferior Centro", dotX: 46, dotY: 40 },
                      { value: "intro-conclusion-only", label: "So 1\u00ba/Ultimo", dotX: 80, dotY: 40, isSpecial: true },
                    ].map((opt) => {
                      const active = (brandKit.logoPlacement || "bottom-right") === opt.value;
                      return (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => setBrandKit({ ...brandKit, logoPlacement: opt.value })}
                          data-testid={`bl-kit-placement-${opt.value}`}
                          className={`flex flex-col items-center gap-1 p-2 rounded border ${active ? "bg-indigo-900/30 border-indigo-500 text-indigo-300" : "bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-500"}`}
                        >
                          {/* Mini slide preview (1.85:1 = 100x54) with a dot
                              showing where the logo will sit. */}
                          <div className="relative w-[100px] h-[54px] bg-slate-950 rounded border border-slate-700">
                            <div
                              className={`absolute rounded-sm ${active ? "bg-indigo-400" : "bg-slate-500"}`}
                              style={{ left: opt.dotX, top: opt.dotY, width: 12, height: 6 }}
                            />
                            {opt.isSpecial && (
                              <span className="absolute top-1 left-1 text-[8px] font-bold text-slate-500">
                                1/{"\u2026"}/N
                              </span>
                            )}
                          </div>
                          <span className="text-[10px] text-center leading-tight">{opt.label}</span>
                        </button>
                      );
                    })}
                  </div>
                  <p className="text-[10px] text-slate-500 leading-tight">
                    {brandKit.logoPlacement === "intro-conclusion-only"
                      ? "O logo aparecera apenas no primeiro e ultimo slide do curso."
                      : "O logo aparecera em todos os slides."}
                  </p>

                  {/* Logo size control: presets + numeric input. Drives both the
                      static export pipeline (apply_brand_logo_to_slides) and
                      the Editor Chat `apply_brand_identity` op when no per-op
                      override is provided. */}
                  <div className="mt-4 space-y-2" data-testid="bl-kit-logo-size-section">
                    <Label className="text-slate-300 text-xs">Tamanho do logo (px)</Label>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { value: 64, label: "Pequeno", short: "64px" },
                        { value: 96, label: "Medio", short: "96px" },
                        { value: 160, label: "Grande", short: "160px" },
                      ].map((opt) => {
                        const active = (brandKit.logoSize || 96) === opt.value;
                        return (
                          <button
                            key={opt.value}
                            type="button"
                            onClick={() => setBrandKit({ ...brandKit, logoSize: opt.value })}
                            data-testid={`bl-kit-logo-size-${opt.value}`}
                            className={`flex flex-col items-center gap-0.5 py-2 rounded border ${active ? "bg-indigo-900/30 border-indigo-500 text-indigo-300" : "bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-500"}`}
                          >
                            <span className="text-xs">{opt.label}</span>
                            <span className="text-[10px] text-slate-500">{opt.short}</span>
                          </button>
                        );
                      })}
                    </div>
                    <div className="flex items-center gap-2 pt-1">
                      <span className="text-[10px] text-slate-500">Personalizado:</span>
                      <Input
                        type="number"
                        min={32}
                        max={320}
                        step={4}
                        value={brandKit.logoSize ?? 96}
                        onChange={(e) => {
                          const n = parseInt(e.target.value, 10);
                          if (Number.isFinite(n)) {
                            setBrandKit({ ...brandKit, logoSize: Math.max(32, Math.min(320, n)) });
                          }
                        }}
                        className="h-7 w-20 bg-slate-900 border-slate-700 text-xs"
                        data-testid="bl-kit-logo-size-input"
                      />
                      <span className="text-[10px] text-slate-500">px (32–320)</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end">
              <Button
                onClick={handleSaveBrandKit}
                data-testid="bl-kit-save"
                className="bg-indigo-600 hover:bg-indigo-700"
              >
                Salvar Identidade
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
