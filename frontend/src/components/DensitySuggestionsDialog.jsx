/**
 * DensitySuggestionsDialog — Shared modal that fetches text-density
 * suggestions for a piece of content and lets the author apply one with a
 * single click.
 *
 * Used in three places:
 *   - StoryboardPanel        → applies the chosen rewrite to a storyboard section
 *   - GeneratedPanel         → applies to a generated slide via project patch
 *   - Editor SlideProperties → applies to the currently edited slide
 *
 * The caller controls *how* the transformation lands on the underlying data
 * via `onApply(suggestion)` — this component only knows about fetching and
 * rendering.
 */
import { useEffect, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "./ui/dialog";
import { Button } from "./ui/button";
import {
  Sparkles, Lightbulb, AlertTriangle, Scissors, ListChecks,
  Columns2, LayoutGrid, GitBranch, Loader2,
} from "lucide-react";

const API_URL = process.env.REACT_APP_BACKEND_URL;

const TYPE_ICONS = {
  summarize: Sparkles,
  split: Scissors,
  bullets: ListChecks,
  comparison: Columns2,
  infographic: LayoutGrid,
  diagram: GitBranch,
};

const TYPE_LABELS = {
  summarize: "Resumir",
  split: "Dividir em 2 slides",
  bullets: "Converter em bullets",
  comparison: "Tabela de comparacao",
  infographic: "Infografico com icones",
  diagram: "Diagrama / fluxograma",
};

const LABEL_STYLES = {
  light: { color: "text-emerald-400", icon: Lightbulb, header: "Conteudo equilibrado" },
  medium: { color: "text-amber-400", icon: Lightbulb, header: "Pode ficar mais visual" },
  heavy: { color: "text-red-400", icon: AlertTriangle, header: "Conteudo muito textual" },
};

export default function DensitySuggestionsDialog({
  open,
  onClose,
  // Source content to analyze
  title = "",
  text = "",
  bullets = [],
  hasImage = false,
  // Caller-controlled apply
  onApply,
  // Optional pre-loaded density (skip the analyze roundtrip)
  preloadedDensity = null,
}) {
  const [density, setDensity] = useState(preloadedDensity);
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [applyingId, setApplyingId] = useState(null);

  // Image-generation provider selector. Only relevant for suggestions
  // with requiresImage=true. We default to "gemini" (Emergent universal
  // key, no user setup) and offer "krea" when admin has configured the
  // Krea API key. Stored separately from kreaModelId so users can switch
  // models without losing their provider preference.
  const [providers, setProviders] = useState([]);
  const [imageProvider, setImageProvider] = useState("gemini");
  // Default to Flux 1 Dev — it's the most broadly compatible Krea model
  // for the keys our customers typically have. When the model can't render
  // text legibly (Flux family), the BACKEND automatically strips text
  // instructions from the prompt and forces an icon-only visual, which
  // produces a clean infographic instead of gibberish words.
  const [kreaModelId, setKreaModelId] = useState("flux-1-dev");

  const token = typeof window !== "undefined" ? localStorage.getItem("scormify_auth_token") : "";

  // Load available image providers on dialog open. Lightweight call —
  // returns instantly. We do it once per open so admin-side toggles
  // (e.g. adding KREA_API_KEY) are picked up without a page refresh.
  useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const r = await fetch(`${API_URL}/api/density/image-providers`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) return;
        const data = await r.json();
        setProviders(data?.providers || []);
      } catch (_e) { /* fallthrough — UI degrades to gemini-only */ }
    })();
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setError("");
    setLoading(true);
    (async () => {
      try {
        const r = await fetch(`${API_URL}/api/density/suggestions`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ title, text, bullets, hasImage }),
        });
        if (!r.ok) throw new Error("Falha ao analisar");
        const data = await r.json();
        if (cancelled) return;
        setDensity(data.density);
        setSuggestions(data.suggestions || []);
      } catch (e) {
        if (!cancelled) setError(e.message || "Erro");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [open, title, text, JSON.stringify(bullets), hasImage]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleApply = async (sug) => {
    if (!onApply) return;
    setApplyingId(sug.id);
    try {
      // Pass the provider choice through to the caller so the apply chain
      // can hit the right backend lane. Suggestions without requiresImage
      // simply ignore these fields.
      const enriched = sug.requiresImage
        ? { ...sug, imageProvider, kreaModelId }
        : sug;
      await Promise.resolve(onApply(enriched));
      onClose?.();
    } finally {
      setApplyingId(null);
    }
  };

  // Detect whether any suggestion needs an image — we only render the
  // provider picker when at least one card promises "Inclui imagem".
  const anySuggestionNeedsImage = suggestions.some(s => s.requiresImage);
  const kreaProvider = providers.find(p => p.id === "krea");

  const headerStyle = density ? LABEL_STYLES[density.label] : LABEL_STYLES.light;
  const HeaderIcon = headerStyle.icon;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent
        className="max-w-3xl max-h-[85vh] overflow-y-auto bg-slate-900 border-slate-700 text-white"
        data-testid="density-dialog"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <HeaderIcon className={`w-5 h-5 ${headerStyle.color}`} />
            <span>{headerStyle.header}</span>
            {density && (
              <span className={`text-xs ml-2 ${headerStyle.color} tabular-nums`}>
                {density.score}/100
              </span>
            )}
          </DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            O Agente IA analisou este conteudo. Veja sugestoes para torna-lo mais visual.
          </DialogDescription>
        </DialogHeader>

        {/* Diagnostics — why we flagged this slide */}
        {density?.reasons?.length > 0 && (
          <div className="bg-slate-800/50 rounded p-3 border border-slate-700" data-testid="density-reasons">
            <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Diagnostico</p>
            <ul className="space-y-0.5">
              {density.reasons.map((r, i) => (
                <li key={i} className="text-xs text-slate-300">• {r}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Suggestions */}
        {loading && (
          <div className="flex items-center justify-center py-12 text-slate-400">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            Gerando sugestoes com o Agente IA...
          </div>
        )}
        {error && !loading && (
          <div className="text-center text-sm text-red-400 py-4">{error}</div>
        )}
        {!loading && !error && suggestions.length === 0 && density?.label === "light" && (
          <div className="text-center py-6 text-slate-400">
            <p className="text-sm">Este conteudo ja esta equilibrado.</p>
            <p className="text-xs mt-1">Nenhuma sugestao adicional necessaria.</p>
          </div>
        )}

        {!loading && suggestions.length > 0 && anySuggestionNeedsImage && (
          <div className="bg-violet-500/5 border border-violet-500/30 rounded p-3 space-y-2" data-testid="density-provider-picker">
            <div className="flex items-center gap-2">
              <LayoutGrid className="w-4 h-4 text-violet-300" />
              <span className="text-xs font-semibold text-violet-300 uppercase tracking-wider">Gerador de imagens</span>
              <span className="text-[10px] text-slate-500">para sugestoes com "Inclui imagem"</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setImageProvider("gemini")}
                className={`text-left rounded p-2 border transition ${imageProvider === "gemini" ? "border-violet-400 bg-violet-500/15" : "border-slate-700 hover:border-slate-600 bg-slate-800/50"}`}
                data-testid="density-provider-gemini"
              >
                <div className="text-xs font-semibold text-white">Gemini Nano Banana</div>
                <div className="text-[10px] text-slate-400 mt-0.5">Rapido (~5s) • Incluso na chave universal</div>
              </button>
              <button
                type="button"
                onClick={() => kreaProvider && setImageProvider("krea")}
                disabled={!kreaProvider}
                className={`text-left rounded p-2 border transition ${imageProvider === "krea" ? "border-violet-400 bg-violet-500/15" : "border-slate-700 hover:border-slate-600 bg-slate-800/50"} ${!kreaProvider ? "opacity-50 cursor-not-allowed" : ""}`}
                data-testid="density-provider-krea"
                title={!kreaProvider ? "Configure KREA_API_KEY no admin para habilitar" : ""}
              >
                <div className="text-xs font-semibold text-white">Krea AI {!kreaProvider && <span className="text-[10px] text-amber-400">(nao configurado)</span>}</div>
                <div className="text-[10px] text-slate-400 mt-0.5">Mais modelos (Flux, Imagen) • Sua conta Krea</div>
              </button>
            </div>
            {imageProvider === "krea" && kreaProvider && (
              <div className="pt-1">
                <label className="text-[10px] text-slate-400 mb-1 block">Modelo Krea</label>
                <select
                  value={kreaModelId}
                  onChange={(e) => setKreaModelId(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-white"
                  data-testid="density-krea-model"
                >
                  {(kreaProvider.models || []).map(m => {
                    const tr = m.textRendering || "poor";
                    const trMark = tr === "excellent" ? "[texto OK]"
                      : tr === "good" ? "[texto OK]"
                      : "[so icones]";
                    return (
                      <option key={m.id} value={m.id}>
                        {trMark} {m.label} {m.approxTimeSeconds ? `(~${m.approxTimeSeconds}s` : ""}
                        {m.approxCostUSD ? ` $${m.approxCostUSD.toFixed(2)})` : (m.approxTimeSeconds ? ")" : "")}
                      </option>
                    );
                  })}
                </select>
                {(() => {
                  const m = (kreaProvider.models || []).find(mm => mm.id === kreaModelId);
                  const tr = m?.textRendering || "poor";
                  if (tr === "poor") {
                    return (
                      <p className="text-[10px] text-amber-400 mt-1 leading-tight">
                        Este modelo nao desenha palavras com fidelidade. O backend
                        forca um visual de icones/simbolos (sem rotulos textuais).
                        Para texto legivel em portugues, escolha
                        <strong className="text-amber-200"> Ideogram 3.0</strong> ou
                        <strong className="text-amber-200"> Imagen 4</strong>.
                      </p>
                    );
                  }
                  return (
                    <p className="text-[10px] text-emerald-400 mt-1 leading-tight">
                      Este modelo desenha texto em portugues de forma legivel.
                    </p>
                  );
                })()}
              </div>
            )}
          </div>
        )}

        {!loading && suggestions.length > 0 && (
          <div className="space-y-3" data-testid="density-suggestions-list">
            {suggestions.map((sug, i) => {
              const Icon = TYPE_ICONS[sug.type] || Sparkles;
              return (
                <div
                  key={sug.id}
                  className="bg-slate-800/70 border border-slate-700 hover:border-indigo-500/50 rounded-lg p-3 transition"
                  data-testid={`density-suggestion-${i}`}
                >
                  <div className="flex items-start gap-3">
                    <div className="bg-indigo-500/15 text-indigo-300 rounded p-1.5 mt-0.5">
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] uppercase tracking-wider text-indigo-400">
                          {TYPE_LABELS[sug.type] || sug.type}
                        </span>
                        {sug.requiresImage && (
                          <span className="text-[10px] bg-violet-500/20 text-violet-300 rounded px-1.5">
                            Inclui imagem
                          </span>
                        )}
                      </div>
                      <h4 className="text-sm font-semibold text-white">{sug.title}</h4>
                      <p className="text-xs text-slate-400 mt-1">{sug.description}</p>

                      {/* Preview of transformed content */}
                      {(sug.transformedText || sug.transformedBullets?.length > 0) && (
                        <div className="mt-2 bg-slate-950/50 border border-slate-700/50 rounded p-2 text-xs text-slate-300 max-h-32 overflow-y-auto">
                          {sug.transformedText && <p className="whitespace-pre-wrap">{sug.transformedText}</p>}
                          {sug.transformedBullets?.length > 0 && (
                            <ul className="space-y-0.5 mt-1">
                              {sug.transformedBullets.map((b, idx) => (
                                <li key={idx}>• {b}</li>
                              ))}
                            </ul>
                          )}
                        </div>
                      )}
                    </div>
                    <Button
                      size="sm"
                      onClick={() => handleApply(sug)}
                      disabled={applyingId === sug.id || !onApply}
                      data-testid={`density-apply-${i}`}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white shrink-0"
                    >
                      {applyingId === sug.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        "Aplicar"
                      )}
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
