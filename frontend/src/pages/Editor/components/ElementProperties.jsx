import React, { useState } from 'react';
import { Input } from '../../../components/ui/input';
import { Button } from '../../../components/ui/button';
import { Maximize2, Sparkles, Scissors, RotateCcw } from 'lucide-react';
import { AnimPreviewButton } from '../../../components/AnimPreviewButton';
import RemoveBackgroundDialog from '../dialogs/RemoveBackgroundDialog';

export function ElementProperties({ element, onUpdate, slideWidth = 960, slideHeight = 540, projectId }) {
  const style = element.style || {};
  const [bgRemoverOpen, setBgRemoverOpen] = useState(false);

  const handleStyleChange = (key, value) => {
    const newStyle = { ...style, [key]: value };
    onUpdate({ style: newStyle });
  };

  // Safe numeric input handler. The previous implementation piped
  // `parseFloat('')` straight into onUpdate, which writes NaN into the
  // element and visually "deletes" it (NaN x/y/width/height = nothing
  // renders). We now:
  //   - Ignore empty strings (keeps last valid value, lets the user type
  //     a replacement without losing the element).
  //   - Drop NaN / non-finite results.
  //   - Enforce a minimum of 10px on width/height so the element stays
  //     visible/selectable even at the smallest size.
  const handleNumericChange = (key, rawValue) => {
    if (rawValue === '' || rawValue == null) return; // user mid-edit
    const v = parseFloat(rawValue);
    if (!Number.isFinite(v)) return;
    let safe = v;
    if (key === 'width' || key === 'height') {
      safe = Math.max(10, v);
    }
    onUpdate({ [key]: safe });
  };

  // Recovery affordance: if an element ended up with NaN/zero/off-canvas
  // coords (e.g. a previous bug or accidental clear), one click puts it
  // back in a reasonable centered spot. Picks ~half the slide so big
  // assets (whiteboards) still fit and small ones remain manageable.
  const handleResetTransform = () => {
    const w = Math.round(slideWidth * 0.5);
    const h = Math.round(slideHeight * 0.5);
    onUpdate({
      x: Math.round((slideWidth - w) / 2),
      y: Math.round((slideHeight - h) / 2),
      width: w,
      height: h,
    });
  };

  return (
    <div className="p-4 space-y-4">
      <div className="panel-section">
        <h4 className="text-sm font-medium mb-3">Position & Size</h4>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-xs text-muted-foreground">X</label>
            <Input
              type="number"
              value={Number.isFinite(element.x) ? Math.round(element.x) : 0}
              onChange={(e) => handleNumericChange('x', e.target.value)}
              className="h-8"
              data-testid="prop-input-x"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Y</label>
            <Input
              type="number"
              value={Number.isFinite(element.y) ? Math.round(element.y) : 0}
              onChange={(e) => handleNumericChange('y', e.target.value)}
              className="h-8"
              data-testid="prop-input-y"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Width</label>
            <Input
              type="number"
              min={10}
              value={Number.isFinite(element.width) && element.width > 0 ? Math.round(element.width) : 0}
              onChange={(e) => handleNumericChange('width', e.target.value)}
              className="h-8"
              data-testid="prop-input-width"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Height</label>
            <Input
              type="number"
              min={10}
              value={Number.isFinite(element.height) && element.height > 0 ? Math.round(element.height) : 0}
              onChange={(e) => handleNumericChange('height', e.target.value)}
              className="h-8"
              data-testid="prop-input-height"
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 mt-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onUpdate({ x: 0, y: 0, width: slideWidth, height: slideHeight, objectFit: 'cover' })}
            className="gap-2"
            data-testid="element-fullscreen-btn"
          >
            <Maximize2 className="w-4 h-4" />
            Fullscreen
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleResetTransform}
            className="gap-2"
            title="Centraliza no slide com tamanho seguro — útil para recuperar elementos que sumiram após valores inválidos."
            data-testid="element-reset-transform-btn"
          >
            <RotateCcw className="w-4 h-4" />
            Resetar
          </Button>
        </div>
      </div>

      {element.type === 'image' && (
        <div className="panel-section">
          <label>Imagem</label>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setBgRemoverOpen(true)}
            className="w-full border-slate-700 text-slate-200 hover:bg-slate-800 gap-2"
            data-testid="image-remove-bg-btn"
          >
            <Scissors className="w-4 h-4 text-emerald-400" />
            Remover Fundo
          </Button>
          <RemoveBackgroundDialog
            open={bgRemoverOpen}
            imageUrl={element.src || element.content || ''}
            projectId={projectId}
            onApply={(newUrl) => {
              onUpdate({ src: newUrl, content: newUrl });
            }}
            onClose={() => setBgRemoverOpen(false)}
          />
        </div>
      )}

      {element.type === 'text' && (
        <div className="panel-section">
          <h4 className="text-sm font-medium mb-3">Text</h4>
          <div className="space-y-2">
            <div>
              <label className="text-xs text-muted-foreground">Font Family</label>
              <select
                data-testid="font-family-select"
                value={style.fontFamily || ''}
                onChange={(e) => handleStyleChange('fontFamily', e.target.value || null)}
                className="flex h-8 w-full rounded-md border border-input bg-background px-2 py-1 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                style={{ fontFamily: style.fontFamily || 'inherit' }}
              >
                <option value="">Padrao</option>
                <optgroup label="Sans-Serif">
                  <option value="Arial" style={{fontFamily: 'Arial'}}>Arial</option>
                  <option value="Helvetica" style={{fontFamily: 'Helvetica'}}>Helvetica</option>
                  <option value="Inter" style={{fontFamily: 'Inter'}}>Inter</option>
                  <option value="Lato" style={{fontFamily: 'Lato'}}>Lato</option>
                  <option value="Montserrat" style={{fontFamily: 'Montserrat'}}>Montserrat</option>
                  <option value="Nunito" style={{fontFamily: 'Nunito'}}>Nunito</option>
                  <option value="Open Sans" style={{fontFamily: 'Open Sans'}}>Open Sans</option>
                  <option value="Oswald" style={{fontFamily: 'Oswald'}}>Oswald</option>
                  <option value="Poppins" style={{fontFamily: 'Poppins'}}>Poppins</option>
                  <option value="PT Sans" style={{fontFamily: 'PT Sans'}}>PT Sans</option>
                  <option value="Raleway" style={{fontFamily: 'Raleway'}}>Raleway</option>
                  <option value="Roboto" style={{fontFamily: 'Roboto'}}>Roboto</option>
                  <option value="Source Sans 3" style={{fontFamily: 'Source Sans 3'}}>Source Sans 3</option>
                  <option value="Trebuchet MS" style={{fontFamily: 'Trebuchet MS'}}>Trebuchet MS</option>
                  <option value="Ubuntu" style={{fontFamily: 'Ubuntu'}}>Ubuntu</option>
                  <option value="Verdana" style={{fontFamily: 'Verdana'}}>Verdana</option>
                </optgroup>
                <optgroup label="Serif">
                  <option value="Georgia" style={{fontFamily: 'Georgia'}}>Georgia</option>
                  <option value="Merriweather" style={{fontFamily: 'Merriweather'}}>Merriweather</option>
                  <option value="Playfair Display" style={{fontFamily: 'Playfair Display'}}>Playfair Display</option>
                  <option value="Times New Roman" style={{fontFamily: 'Times New Roman'}}>Times New Roman</option>
                </optgroup>
                <optgroup label="Monospace">
                  <option value="Courier New" style={{fontFamily: 'Courier New'}}>Courier New</option>
                </optgroup>
              </select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Font Size</label>
              <Input
                type="number"
                value={style.fontSize || 16}
                onChange={(e) => handleStyleChange('fontSize', parseFloat(e.target.value))}
                className="h-8"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Color</label>
              <Input
                type="color"
                value={style.fontColor || '#000000'}
                onChange={(e) => handleStyleChange('fontColor', e.target.value)}
                className="h-8 p-1"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Background Color</label>
              <div className="flex gap-2 items-center">
                <Input
                  type="color"
                  value={style.backgroundColor || '#FFFFFF'}
                  onChange={(e) => handleStyleChange('backgroundColor', e.target.value)}
                  className="h-8 p-1 flex-1"
                  disabled={style.transparentBackground}
                />
                <label className="flex items-center gap-1 text-xs cursor-pointer">
                  <input
                    type="checkbox"
                    checked={style.transparentBackground || false}
                    onChange={(e) => handleStyleChange('transparentBackground', e.target.checked)}
                    className="w-4 h-4"
                  />
                  Transparent
                </label>
              </div>
            </div>
          </div>
        </div>
      )}

      {element.type === 'shape' && (
        <div className="panel-section">
          <h4 className="text-sm font-medium mb-3">Fill & Stroke</h4>
          <div className="space-y-2">
            <div>
              <label className="text-xs text-muted-foreground">Fill</label>
              <Input
                type="color"
                value={style.fill || '#7C3AED'}
                onChange={(e) => handleStyleChange('fill', e.target.value)}
                className="h-8 p-1"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Stroke</label>
              <Input
                type="color"
                value={style.stroke || '#000000'}
                onChange={(e) => handleStyleChange('stroke', e.target.value)}
                className="h-8 p-1"
              />
            </div>
          </div>
        </div>
      )}

      {element.type === 'quiz' && (
        <div className="panel-section">
          <h4 className="text-sm font-medium mb-3">Configuracoes do Quiz</h4>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-muted-foreground">Titulo</label>
              <Input
                value={element.quizConfig?.title || 'Quiz'}
                onChange={(e) => onUpdate({ quizConfig: { ...element.quizConfig, title: e.target.value } })}
                className="h-8"
                data-testid="quiz-title-input"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Tamanho da Fonte</label>
              <select
                value={element.quizConfig?.fontSize || 16}
                onChange={(e) => onUpdate({ quizConfig: { ...element.quizConfig, fontSize: parseInt(e.target.value) } })}
                className="w-full h-8 rounded-md border border-input bg-background px-3 text-sm"
                data-testid="quiz-font-size-select"
              >
                <option value="12">12px - Pequeno</option>
                <option value="14">14px - Medio</option>
                <option value="16">16px - Normal</option>
                <option value="18">18px - Grande</option>
                <option value="20">20px - Muito Grande</option>
                <option value="24">24px - Extra Grande</option>
                <option value="28">28px - Gigante</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Nota minima (%)</label>
              <select
                value={element.quizConfig?.passingScore || 60}
                onChange={(e) => onUpdate({ quizConfig: { ...element.quizConfig, passingScore: parseInt(e.target.value) } })}
                className="w-full h-8 rounded-md border border-input bg-background px-3 text-sm"
                data-testid="quiz-passing-score-select"
              >
                <option value="50">50%</option>
                <option value="60">60%</option>
                <option value="70">70%</option>
                <option value="80">80%</option>
                <option value="90">90%</option>
                <option value="100">100%</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" id="shuffle-questions" checked={element.quizConfig?.shuffleQuestions !== false}
                onChange={(e) => onUpdate({ quizConfig: { ...element.quizConfig, shuffleQuestions: e.target.checked } })} className="w-4 h-4" />
              <label htmlFor="shuffle-questions" className="text-xs text-muted-foreground cursor-pointer">Embaralhar questoes</label>
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" id="shuffle-alternatives" checked={element.quizConfig?.shuffleAlternatives !== false}
                onChange={(e) => onUpdate({ quizConfig: { ...element.quizConfig, shuffleAlternatives: e.target.checked } })} className="w-4 h-4" />
              <label htmlFor="shuffle-alternatives" className="text-xs text-muted-foreground cursor-pointer">Embaralhar alternativas</label>
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" id="show-feedback" checked={element.quizConfig?.showFeedback !== false}
                onChange={(e) => onUpdate({ quizConfig: { ...element.quizConfig, showFeedback: e.target.checked } })} className="w-4 h-4" />
              <label htmlFor="show-feedback" className="text-xs text-muted-foreground cursor-pointer">Mostrar feedback apos resposta</label>
            </div>
            <p className="text-xs text-muted-foreground mt-2">{element.questions?.length || 0} questoes neste quiz</p>
          </div>
        </div>
      )}

      {element.type === 'scenario' && (
        <div className="panel-section">
          <h4 className="text-sm font-medium mb-3">Configuracoes do Cenario</h4>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-muted-foreground">Titulo</label>
              <Input
                value={element.scenarioData?.title || 'Cenario Interativo'}
                onChange={(e) => onUpdate({ scenarioData: { ...element.scenarioData, title: e.target.value } })}
                className="h-8"
                data-testid="scenario-title-input"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Tamanho da Fonte</label>
              <select
                value={element.scenarioData?.fontSize || 16}
                onChange={(e) => onUpdate({ scenarioData: { ...element.scenarioData, fontSize: parseInt(e.target.value) } })}
                className="w-full h-8 rounded-md border border-input bg-background px-3 text-sm"
                data-testid="scenario-font-size-select"
              >
                <option value="12">12px - Pequeno</option>
                <option value="14">14px - Medio</option>
                <option value="16">16px - Normal</option>
                <option value="18">18px - Grande</option>
                <option value="20">20px - Muito Grande</option>
                <option value="24">24px - Extra Grande</option>
                <option value="28">28px - Gigante</option>
              </select>
            </div>
            <div className="text-xs text-muted-foreground space-y-1 mt-2">
              <p>{element.scenarioData?.nodes?.length || 0} cenas</p>
              <p>{element.scenarioData?.characters?.length || 0} personagens</p>
              <p>{(element.scenarioData?.nodes || []).filter(n => n.is_ending).length} finais possiveis</p>
            </div>
          </div>
        </div>
      )}

      {/* Animation */}
      <div className="panel-section">
        <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-amber-400" /> Animacao de Entrada
        </h4>
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-1.5">
            <AnimPreviewButton animId="" label="Nenhuma" selected={!element.animation?.effect} onClick={() => onUpdate({ animation: null })} testId="anim-none" />
            {[
              { id: 'fadeIn', label: 'Fade In' },
              { id: 'slideInLeft', label: 'Slide Esq.' },
              { id: 'slideInRight', label: 'Slide Dir.' },
              { id: 'slideInUp', label: 'Slide Baixo' },
              { id: 'slideInDown', label: 'Slide Cima' },
              { id: 'zoomIn', label: 'Zoom In' },
              { id: 'typewriter', label: 'Typewriter' },
              { id: 'bounce', label: 'Bounce' },
            ].map(a => (
              <AnimPreviewButton
                key={a.id}
                animId={a.id}
                label={a.label}
                selected={element.animation?.effect === a.id}
                onClick={() => onUpdate({ animation: { type: 'entrance', effect: a.id, duration: element.animation?.duration || 0.5, delay: 0 } })}
                testId={`anim-${a.id}`}
              />
            ))}
          </div>
          {element.animation?.effect && (
            <div>
              <label className="text-xs text-muted-foreground">Duracao: {element.animation?.duration || 0.5}s</label>
              <input
                type="range" min="0.2" max="2" step="0.1"
                value={element.animation?.duration || 0.5}
                onChange={(e) => onUpdate({ animation: { ...element.animation, duration: parseFloat(e.target.value) } })}
                className="w-full h-1.5 accent-amber-500"
                data-testid="anim-duration-slider"
              />
            </div>
          )}
        </div>
      </div>

      <div className="panel-section">
        <h4 className="text-sm font-medium mb-3">Hyperlink</h4>
        <Input
          placeholder="https://..."
          value={element.hyperlink || ''}
          onChange={(e) => onUpdate({ hyperlink: e.target.value })}
          className="h-8"
        />
      </div>
    </div>
  );
}
