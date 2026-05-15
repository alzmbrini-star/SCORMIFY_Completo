import React, { useState } from 'react';
import { Input } from '../../../components/ui/input';
import { Switch } from '../../../components/ui/switch';
import { Button } from '../../../components/ui/button';
import { Layers, ImagePlus, X as XIcon, Sparkles } from 'lucide-react';
import BrandLibraryPicker from '../dialogs/BrandLibraryPicker';
import DensitySuggestionsDialog from '../../../components/DensitySuggestionsDialog';

export function SlideProperties({ slide, onUpdate, project }) {
  const extractSlideText = () => {
    const texts = (slide.elements || [])
      .filter(el => el.type === 'text' && el.content)
      .map(el => {
        if (el.htmlContent) {
          const tmp = document.createElement('div');
          tmp.innerHTML = el.htmlContent;
          return tmp.textContent || tmp.innerText || '';
        }
        return el.content;
      })
      .filter(t => t.trim());
    return texts.join('. ').trim();
  };

  const handleAutoFill = () => {
    const text = extractSlideText();
    if (text) {
      onUpdate({ librasScript: text });
    }
  };

  const slideText = extractSlideText();

  // Brand Library: per-slide picker + per-slide override of the project-wide
  // useBrandLibrary preference. Three states for `brandLibraryOverride`:
  //   - undefined → inherit project setting (default)
  //   - "force"    → use the library on this slide regardless of project flag
  //   - "skip"     → never use the library on this slide (use AI or none)
  const [brandPickerOpen, setBrandPickerOpen] = useState(false);
  const slideOverride = slide.brandLibraryOverride; // undefined | "force" | "skip"

  // Density Analysis state — opens the suggestions dialog with this slide's
  // text + bullets. The dialog calls back into onUpdate when the author
  // applies a suggestion, so the slide refreshes immediately.
  const [densityOpen, setDensityOpen] = useState(false);

  // Compute bullets + body text from the slide's elements for the density
  // analyzer. Mirrors the backend `analyze_slide()` heuristic.
  const collectDensityInput = () => {
    const texts = [];
    const bullets = [];
    let hasImage = !!slide.backgroundImage;
    (slide.elements || []).forEach((el) => {
      if (el.isBrandLogo) return;
      const t = (el.type || '').toLowerCase();
      if (t === 'text') {
        const content = (el.htmlContent
          ? (() => { const d = document.createElement('div'); d.innerHTML = el.htmlContent; return d.textContent || d.innerText || ''; })()
          : (el.content || el.text || ''));
        const lines = content.split('\n').map(l => l.trim()).filter(Boolean);
        const bs = lines.filter(l => l.startsWith('•') || l.startsWith('-') || l.startsWith('*'))
          .map(l => l.replace(/^[•\-*]\s*/, '').trim());
        if (bs.length) bullets.push(...bs);
        const nb = lines.filter(l => !l.startsWith('•') && !l.startsWith('-') && !l.startsWith('*'));
        if (nb.length) texts.push(nb.join(' '));
      } else if (['image', 'video', 'avatar', 'iframe', 'flipbook'].includes(t)) {
        hasImage = true;
      }
    });
    return {
      title: slide.title || '',
      text: texts.join(' '),
      bullets,
      hasImage,
    };
  };

  // Smart Avatar toggle is only relevant when the slide has a HeyGen (or
  // transparent) avatar video element AND a scene background image.
  const hasAvatar = (slide.elements || []).some((el) => {
    if (!el) return false;
    const etype = (el.type || '').toLowerCase();
    if (etype !== 'video' && etype !== 'avatar') return false;
    const src = (el.src || el.videoUrl || el.avatarVideoUrl || el.content || '').toLowerCase();
    return src.includes('heygen') || src.includes('-transparent') || src.endsWith('.webm');
  });
  const hasSceneBg = !!slide.backgroundImage
    || (slide.elements || []).some(el => (el?.type === 'image') && (el.width || 0) >= 800);
  const showSmartAvatarToggle = hasAvatar && hasSceneBg;

  return (
    <div className="p-4 space-y-4">
      <div className="panel-section">
        <h4 className="text-sm font-medium mb-3">Slide Settings</h4>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground">Title</label>
            <Input
              value={slide.title || ''}
              onChange={(e) => onUpdate({ title: e.target.value })}
              className="h-8"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Background</label>
            {slide.background?.includes('gradient') ? (
              <div className="space-y-1">
                <div className="h-8 rounded border" style={{ background: slide.background }} />
                <p className="text-[10px] text-muted-foreground">Degrade (definido pelo agente)</p>
                <Input
                  type="color"
                  value="#ffffff"
                  onChange={(e) => onUpdate({ background: e.target.value })}
                  className="h-7 p-1"
                />
                <p className="text-[10px] text-muted-foreground">Substituir por cor solida</p>
              </div>
            ) : (
              <Input
                type="color"
                value={slide.background || '#FFFFFF'}
                onChange={(e) => onUpdate({ background: e.target.value })}
                className="h-8 p-1"
              />
            )}
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Duration (seconds)</label>
            <Input
              type="number"
              value={slide.duration || 5}
              onChange={(e) => onUpdate({ duration: parseFloat(e.target.value) })}
              className="h-8"
            />
          </div>
        </div>
      </div>

      {/* Brand Library — per-slide picker + override of project-wide setting */}
      <div className="panel-section" data-testid="brand-library-slide-section">
        <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
          <Layers className="w-4 h-4 text-indigo-500" />
          Biblioteca de Marca
        </h4>
        <div className="space-y-2">
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start"
            onClick={() => setBrandPickerOpen(true)}
            disabled={!project?.companyId}
            data-testid="brand-library-pick-button"
          >
            <ImagePlus className="w-4 h-4 mr-2 text-indigo-500" />
            {slide.backgroundImage && slide.backgroundImageSource === 'brand_library'
              ? 'Trocar imagem da biblioteca'
              : 'Usar imagem da biblioteca'}
          </Button>
          {!project?.companyId && (
            <p className="text-[10px] text-amber-500">
              Este projeto nao esta vinculado a uma empresa. Defina o `companyId` para acessar a biblioteca.
            </p>
          )}

          {slide.backgroundImage && slide.backgroundImageSource === 'brand_library' && (
            <div className="flex items-center justify-between gap-2 rounded border px-2 py-1.5 bg-muted/30">
              <span className="text-[11px] text-muted-foreground truncate">
                Fundo: imagem da biblioteca aplicada
              </span>
              <button
                type="button"
                onClick={() => onUpdate({ backgroundImage: null, backgroundImageSource: null })}
                title="Remover imagem da biblioteca"
                className="text-muted-foreground hover:text-red-500"
                data-testid="brand-library-clear-button"
              >
                <XIcon className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <div className="rounded border p-2 space-y-1">
            <p className="text-[11px] text-muted-foreground">
              Estrategia neste slide
            </p>
            <div className="grid grid-cols-3 gap-1">
              {[
                { value: undefined, label: 'Herdar', testId: 'bl-override-inherit' },
                { value: 'force', label: 'Forcar', testId: 'bl-override-force' },
                { value: 'skip', label: 'Ignorar', testId: 'bl-override-skip' },
              ].map((opt) => (
                <button
                  key={opt.label}
                  type="button"
                  onClick={() => onUpdate({ brandLibraryOverride: opt.value })}
                  data-testid={opt.testId}
                  className={`text-[11px] rounded px-2 py-1 border ${slideOverride === opt.value ? 'bg-indigo-500 text-white border-indigo-500' : 'bg-background hover:bg-muted'}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-muted-foreground leading-tight">
              <strong>Herdar</strong>: usa a config do projeto. <strong>Forcar</strong>: usa biblioteca mesmo se o projeto estiver desligado. <strong>Ignorar</strong>: pula biblioteca neste slide.
            </p>
          </div>
        </div>
      </div>

      <div className="panel-section">
        <h4 className="text-sm font-medium mb-3">Notes</h4>
        <textarea
          className="w-full h-24 p-2 text-sm bg-background border rounded resize-none"
          placeholder="Presenter notes..."
          value={slide.notes || ''}
          onChange={(e) => onUpdate({ notes: e.target.value })}
        />
      </div>

      {showSmartAvatarToggle && (
        <div className="panel-section" data-testid="smart-avatar-section">
          <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>
            </svg>
            Posicionamento Inteligente
          </h4>
          <div className="flex items-start justify-between gap-3 p-3 bg-muted/50 rounded-lg border">
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-foreground">Smart Avatar Position</p>
              <p className="text-[10px] text-muted-foreground mt-1 leading-relaxed">
                Na exportação Single Page, analisa o cenário e posiciona o avatar automaticamente
                na área mais escura (chão/mesa/sombra). Ignora as coordenadas manuais deste slide.
              </p>
            </div>
            <Switch
              data-testid="smart-avatar-toggle"
              checked={!!slide.smartAvatar}
              onCheckedChange={(v) => onUpdate({ smartAvatar: v })}
            />
          </div>
          {slide.smartAvatar && (
            <p className="text-[10px] text-emerald-600 dark:text-emerald-400 mt-1.5">
              ✓ Ativo — coords manuais serão ignoradas na exportação.
            </p>
          )}
        </div>
      )}

      <div className="panel-section">
        <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 11v8a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-8"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/><path d="M14 11h3a1 1 0 0 1 1 1v1a2 2 0 0 1-2 2h-2"/><path d="M14 15v5a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1v-5"/></svg>
          Script LIBRAS
        </h4>
        <textarea
          data-testid="libras-script-input"
          className="w-full h-28 p-2 text-sm bg-background border rounded resize-none"
          placeholder="Digite aqui o texto da narracao deste slide para traducao automatica em LIBRAS..."
          value={slide.librasScript || ''}
          onChange={(e) => onUpdate({ librasScript: e.target.value })}
        />
        {slideText && !slide.librasScript && (
          <button
            data-testid="libras-autofill-btn"
            onClick={handleAutoFill}
            className="mt-2 w-full text-xs px-3 py-1.5 bg-primary/10 text-primary hover:bg-primary/20 rounded transition-colors flex items-center justify-center gap-1.5"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"/><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.855.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z"/></svg>
            Preencher com texto do slide
          </button>
        )}
        <p className="text-[10px] text-muted-foreground mt-1">
          {slide.librasScript 
            ? 'O avatar VLibras traduzira este texto automaticamente quando o slide for exibido.'
            : 'Preenchido automaticamente ao gerar narracao (TTS). Ou clique no botao acima para usar o texto do slide.'}
        </p>
      </div>

      {/* Visual Density Analyzer — Agent IA opina sobre o slide */}
      <div className="panel-section" data-testid="density-section">
        <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-fuchsia-500" />
          Analise Visual (Agente IA)
        </h4>
        <Button
          variant="outline"
          size="sm"
          className="w-full justify-start"
          onClick={() => setDensityOpen(true)}
          data-testid="density-analyze-button"
        >
          <Sparkles className="w-4 h-4 mr-2 text-fuchsia-500" />
          Analisar densidade e sugerir melhorias
        </Button>
        <p className="text-[10px] text-muted-foreground mt-1">
          O agente verifica se o slide esta muito textual e sugere alternativas mais visuais.
        </p>
      </div>

      {/* Brand Library picker — mounted at the root of SlideProperties so
          the dialog overlays the entire editor instead of being clipped. */}
      <BrandLibraryPicker
        open={brandPickerOpen}
        onClose={() => setBrandPickerOpen(false)}
        companyId={project?.companyId}
        onPick={(asset) => {
          // Apply the chosen asset as the slide's backgroundImage and tag it
          // so the renderer + future export pipelines know its provenance.
          onUpdate({
            backgroundImage: asset.url,
            backgroundImageSource: 'brand_library',
            backgroundImageAssetId: asset.id,
          });
        }}
      />

      {/* Density Suggestions Dialog — applies a chosen rewrite to the slide.
          We REPLACE the content of the first text-like element (type ∈
          {text, html, paragraph, title}) instead of adding a new one — so
          the rewritten prose visibly replaces the original on the canvas
          rather than overlaying it. Position/style/animation of the host
          element are preserved. */}
      <DensitySuggestionsDialog
        open={densityOpen}
        onClose={() => setDensityOpen(false)}
        {...collectDensityInput()}
        onApply={(sug) => {
          const elements = [...(slide.elements || [])];
          const TEXTUAL_TYPES = ['text', 'html', 'paragraph', 'title', 'heading'];
          // Find ALL textual elements. AI-Agent slides often have a small
          // HEADER strip at index 0 (1920x50 banner) and the BODY at index 1
          // (1760x700). We MUST pick the largest as survivor — otherwise the
          // new prose would be squashed into the header strip (broken UX).
          const textualEls = elements
            .map((el, i) => ({ el, i }))
            .filter(({ el }) => TEXTUAL_TYPES.includes((el.type || '').toLowerCase()) && !el.isBrandLogo);

          const plainText = sug.transformedText
            || (sug.transformedBullets?.length
                ? sug.transformedBullets.map(b => `• ${b}`).join('\n')
                : '');
          // Build HTML version too — useful when the host element renders
          // rich HTML (which is the case for AI-Agent-generated slides).
          const escape = (s) => String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
          let htmlContent = '';
          if (sug.transformedBullets?.length) {
            htmlContent = `<ul style="margin:0;padding-left:1.2em;font-size:24px;line-height:1.5">${sug.transformedBullets
              .map(b => `<li style="margin-bottom:.6em">${escape(b)}</li>`)
              .join('')}</ul>`;
            if (sug.transformedText) {
              htmlContent = `<p style="margin:0 0 .8em 0;font-size:28px;line-height:1.4;font-weight:600">${escape(sug.transformedText)}</p>` + htmlContent;
            }
          } else if (sug.transformedText) {
            // Preserve paragraph breaks
            htmlContent = sug.transformedText
              .split(/\n\n+/)
              .map(p => `<p style="margin:0 0 .8em 0;font-size:26px;line-height:1.5">${escape(p).replace(/\n/g, '<br/>')}</p>`)
              .join('');
          }

          if (textualEls.length > 0) {
            // Pick the LARGEST textual element by area as the survivor.
            const survivor = textualEls.reduce((best, cur) => {
              const aB = (best.el.width || 0) * (best.el.height || 0);
              const aC = (cur.el.width || 0) * (cur.el.height || 0);
              return aC > aB ? cur : best;
            });
            // UNION bounding box of all textual elements → the survivor's box
            // expands to fit the merged area so the new prose isn't squashed.
            const xs = textualEls.map(({ el }) => el.x || 0);
            const ys = textualEls.map(({ el }) => el.y || 0);
            const rights = textualEls.map(({ el }) => (el.x || 0) + (el.width || 0));
            const bottoms = textualEls.map(({ el }) => (el.y || 0) + (el.height || 0));
            const ux = Math.min(...xs);
            const uy = Math.min(...ys);
            const uw = Math.max(...rights) - ux;
            const uh = Math.max(...bottoms) - uy;

            const isHtmlType = (survivor.el.type || '').toLowerCase() === 'html';
            elements[survivor.i] = {
              ...survivor.el,
              x: ux, y: uy, width: uw, height: uh,
              // Update BOTH content and htmlContent so whichever the renderer
              // reads (depends on slide template), the new prose shows.
              content: plainText,
              htmlContent: isHtmlType || survivor.el.htmlContent ? htmlContent : undefined,
            };
            // Drop the OTHER textual elements so the new content isn't
            // competing with the old prose. We keep non-text elements
            // (images, shapes, audio, etc) untouched.
            const toRemove = new Set(textualEls.filter(t => t.i !== survivor.i).map(t => t.i));
            const cleaned = elements.filter((_, i) => !toRemove.has(i));
            onUpdate({ elements: cleaned });
          } else {
            elements.push({
              id: `text-${Date.now()}`,
              type: 'text',
              content: plainText,
              htmlContent,
              x: 80, y: 80, width: 1760, height: 600,
              style: { fontSize: '28px', color: '#FFFFFF' },
            });
            onUpdate({ elements });
          }
          // Confirm visually so the author knows something happened
          try {
            // sonner is available app-wide; soft import to avoid coupling
            // eslint-disable-next-line global-require
            const { toast } = require('sonner');
            toast.success('Sugestao aplicada ao slide. O conteudo foi substituido.');
          } catch (_e) { /* no toast lib — silent */ }
        }}
      />
    </div>
  );
}
