/**
 * Helpers shared by the density-suggestion "Aplicar" flow in both
 * SlideProperties (Editor) and GeneratedPanel (Agent post-gen view).
 *
 * Why this lives in /lib instead of inlined in the components: both call
 * sites need IDENTICAL text-color resolution. The user reported that the
 * applied prose was coming out white-on-white when the slide background
 * was light. The fix is to inject an explicit `color` into every <p>/<ul>
 * /<li> we emit, computed from the slide's existing color signals (and
 * falling back to a dark default that works on light/medium backgrounds —
 * NEVER white, which is the renderer's iframe default).
 */

const escapeHtml = (s) => String(s)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;');

/** Parse a color string into [r,g,b] (0-255). Accepts #rgb, #rrggbb,
 *  rgb(...). Returns null when input is unparsable so callers can fall
 *  back. */
const _parseColor = (raw) => {
  if (!raw || typeof raw !== 'string') return null;
  const s = raw.trim().toLowerCase();
  // #rgb / #rrggbb
  const hex = s.match(/^#?([0-9a-f]{3}|[0-9a-f]{6})$/);
  if (hex) {
    let h = hex[1];
    if (h.length === 3) h = h.split('').map(c => c + c).join('');
    return [
      parseInt(h.slice(0, 2), 16),
      parseInt(h.slice(2, 4), 16),
      parseInt(h.slice(4, 6), 16),
    ];
  }
  const rgb = s.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
  if (rgb) return [+rgb[1], +rgb[2], +rgb[3]];
  return null;
};

/** WCAG relative luminance for an [r,g,b] triplet. 0 = pure black, 1 = pure
 *  white. We use this to decide whether the slide background is light or
 *  dark and pick a contrasting text color. */
const _relativeLuminance = ([r, g, b]) => {
  const ch = (c) => {
    const v = c / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b);
};

/**
 * Pick a readable text color for a density-suggestion rewrite.
 *
 * Priority (high → low):
 *  1. Survivor element's explicit `style.color` or `style.fontColor`.
 *     Authors who hand-tuned the slide's text color expect that to stick.
 *  2. Slide-level `globalTextColor` (set by background-picker analysis).
 *  3. Slide's `backgroundColor` → compute luminance, pick contrasting.
 *  4. Default: `#0f172a` (very dark slate). Works on creme/white/grey
 *     backgrounds (the most common AI-Agent slide styles). NEVER returns
 *     a white-ish value as the default — that's the white-on-white bug
 *     the renderer's iframe already inherits.
 */
export function pickReadableTextColor(slide, survivor) {
  const explicit = survivor?.style?.color || survivor?.style?.fontColor;
  if (explicit && _parseColor(explicit)) return explicit;
  if (slide?.globalTextColor && _parseColor(slide.globalTextColor)) return slide.globalTextColor;
  const bg = slide?.backgroundColor;
  const bgRgb = _parseColor(bg);
  if (bgRgb) {
    const L = _relativeLuminance(bgRgb);
    return L > 0.55 ? '#0f172a' : '#f1f5f9';
  }
  // No explicit background → default to dark (safer for light/creme/
  // brand-asset images which are the common case).
  return '#0f172a';
}

/**
 * Build the HTML markup for a density suggestion's transformed content.
 * Embeds the resolved text color in every block-level element so the
 * iframe's default white text color is overridden.
 */
export function buildSuggestionHtml(sug, color) {
  const c = color || '#0f172a';
  let html = '';
  if (sug.transformedBullets?.length) {
    html = `<ul style="margin:0;padding-left:1.2em;font-size:24px;line-height:1.5;color:${c}">` +
      sug.transformedBullets.map(b =>
        `<li style="margin-bottom:.6em;color:${c}">${escapeHtml(b)}</li>`
      ).join('') +
      '</ul>';
    if (sug.transformedText) {
      html = `<p style="margin:0 0 .8em 0;font-size:28px;line-height:1.4;font-weight:600;color:${c}">${escapeHtml(sug.transformedText)}</p>` + html;
    }
  } else if (sug.transformedText) {
    html = sug.transformedText
      .split(/\n\n+/)
      .map(p =>
        `<p style="margin:0 0 .8em 0;font-size:26px;line-height:1.5;color:${c}">${escapeHtml(p).replace(/\n/g, '<br/>')}</p>`
      )
      .join('');
  }
  return html;
}

export function buildSuggestionPlainText(sug) {
  return sug.transformedText
    || (sug.transformedBullets?.length
        ? sug.transformedBullets.map(b => `• ${b}`).join('\n')
        : '');
}
