import React from 'react';
import { Input } from '../../../components/ui/input';

export function SlideProperties({ slide, onUpdate }) {
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

      <div className="panel-section">
        <h4 className="text-sm font-medium mb-3">Notes</h4>
        <textarea
          className="w-full h-24 p-2 text-sm bg-background border rounded resize-none"
          placeholder="Presenter notes..."
          value={slide.notes || ''}
          onChange={(e) => onUpdate({ notes: e.target.value })}
        />
      </div>

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
    </div>
  );
}
