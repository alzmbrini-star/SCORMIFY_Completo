/**
 * DensityBadge — Compact pill that surfaces a slide / section's text density.
 *
 * Variants:
 *   - light  → no badge rendered (returns null) - signal-to-noise
 *   - medium → amber "Pouco visual" pill
 *   - heavy  → red "Muito textual" pill with pulse animation
 *
 * Click handler opens a `DensitySuggestionsDialog`. The badge is intentionally
 * passive (just a button) so the same component can be reused in storyboards,
 * post-generation analysis, and the Editor without leaking layout opinions.
 */
import { AlertTriangle, Lightbulb } from "lucide-react";

const VARIANTS = {
  light: null,
  medium: {
    icon: Lightbulb,
    label: "Pouco visual",
    className:
      "bg-amber-500/15 text-amber-300 border-amber-500/40 hover:bg-amber-500/25",
  },
  heavy: {
    icon: AlertTriangle,
    label: "Muito textual",
    className:
      "bg-red-500/15 text-red-300 border-red-500/50 hover:bg-red-500/25 animate-pulse-slow",
  },
};

export default function DensityBadge({ label, score, onClick, size = "sm", testId }) {
  const v = VARIANTS[label] || null;
  if (!v) return null;
  const Icon = v.icon;
  const sizing = size === "xs"
    ? "text-[10px] px-1.5 py-0.5 gap-1"
    : "text-xs px-2 py-1 gap-1.5";
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId || `density-badge-${label}`}
      title={`Densidade visual: ${score}/100. Clique para ver sugestoes.`}
      className={`inline-flex items-center rounded-full border ${v.className} ${sizing} font-medium transition`}
    >
      <Icon className={size === "xs" ? "w-2.5 h-2.5" : "w-3 h-3"} />
      <span>{v.label}</span>
      <span className="opacity-70">·</span>
      <span className="tabular-nums">{score}</span>
    </button>
  );
}
