import React, { useMemo } from 'react';
import { Input } from '../ui/input';

/**
 * TextShadowControls — reusable text-shadow editor.
 *
 * Props:
 *   value    string | null   Current CSS value ("2px 2px 4px #000000") or null
 *   onChange (str|null) => void  Called with the new CSS string, or null when disabled
 *   compact  bool           Denser layout (single-column sliders)
 *
 * The string is emitted in the canonical CSS format `${x}px ${y}px ${blur}px ${color}`,
 * or an empty string when explicitly disabled (which downstream renderers treat as
 * `text-shadow: none`).
 */
export default function TextShadowControls({ value, onChange, compact = false }) {
  const parsed = useMemo(() => parseShadow(value), [value]);
  const enabled = !!value && value !== 'none';

  const emit = (next) => onChange(buildShadow(next));

  const setField = (key, v) => {
    emit({ ...parsed, [key]: v });
  };

  return (
    <div className="space-y-2" data-testid="text-shadow-controls">
      <label className="flex items-center gap-2 text-xs cursor-pointer">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => {
            if (!e.target.checked) {
              onChange('');   // explicit disable — 'text-shadow: none' downstream
            } else {
              emit({ x: 2, y: 2, blur: 4, color: '#000000' });
            }
          }}
          className="w-4 h-4"
          data-testid="text-shadow-toggle"
        />
        <span className="font-medium">Sombra do texto</span>
      </label>

      {enabled && (
        <div className={compact ? 'space-y-1.5' : 'grid grid-cols-2 gap-2'}>
          <div>
            <label className="text-[10px] text-muted-foreground block">Cor</label>
            <Input
              type="color"
              value={parsed.color}
              onChange={(e) => setField('color', e.target.value)}
              className="h-7 p-0.5 w-full"
              data-testid="text-shadow-color"
            />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground block">Blur ({parsed.blur}px)</label>
            <input
              type="range" min={0} max={30} value={parsed.blur}
              onChange={(e) => setField('blur', parseInt(e.target.value, 10) || 0)}
              className="w-full h-7 accent-indigo-500"
              data-testid="text-shadow-blur"
            />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground block">Offset X ({parsed.x}px)</label>
            <input
              type="range" min={-10} max={10} value={parsed.x}
              onChange={(e) => setField('x', parseInt(e.target.value, 10) || 0)}
              className="w-full h-7 accent-indigo-500"
              data-testid="text-shadow-x"
            />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground block">Offset Y ({parsed.y}px)</label>
            <input
              type="range" min={-10} max={10} value={parsed.y}
              onChange={(e) => setField('y', parseInt(e.target.value, 10) || 0)}
              className="w-full h-7 accent-indigo-500"
              data-testid="text-shadow-y"
            />
          </div>

          {/* Live preview swatch — proves the current settings look right */}
          <div className="col-span-full bg-slate-800/60 rounded p-2 text-center text-white text-sm"
            style={{ textShadow: buildShadow(parsed), fontWeight: 700, fontSize: 16 }}
            data-testid="text-shadow-preview"
          >
            Exemplo
          </div>
        </div>
      )}
    </div>
  );
}

// --- helpers exported for reuse (SlideProperties bulk-apply, Editor toolbar) ---

/** Parse `"2px 2px 4px #000000"` → `{x:2, y:2, blur:4, color:"#000000"}`. */
export function parseShadow(s) {
  const fallback = { x: 2, y: 2, blur: 4, color: '#000000' };
  if (!s || typeof s !== 'string' || s === 'none') return fallback;
  // Extract hex color first so it doesn't conflict with px extraction
  const colorMatch = s.match(/#[0-9a-fA-F]{3,8}/);
  const color = colorMatch ? colorMatch[0] : '#000000';
  const nums = (s.match(/-?\d+(\.\d+)?/g) || []).map(Number);
  const [x, y, blur] = nums;
  return {
    x: Number.isFinite(x) ? x : fallback.x,
    y: Number.isFinite(y) ? y : fallback.y,
    blur: Number.isFinite(blur) ? Math.max(0, blur) : fallback.blur,
    color,
  };
}

/** Build canonical CSS string. */
export function buildShadow({ x = 2, y = 2, blur = 4, color = '#000000' }) {
  return `${x}px ${y}px ${blur}px ${color}`;
}
