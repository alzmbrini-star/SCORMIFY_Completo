import React from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../../../components/ui/dialog';
import { Button } from '../../../components/ui/button';
import { Loader2, Volume2, Sparkles, Plus, Check, X } from 'lucide-react';

export function TTSDialog({
  open, onOpenChange,
  ttsVoices, ttsLoading, ttsGenerating,
  ttsGenderFilter, ttsSelectedVoice, setTTSSelectedVoice,
  ttsText, setTTSText,
  ttsAudioUrl,
  aiNarrationLoading, aiNarrationOptions, aiNarrationStyle, setAiNarrationStyle,
  showAiNarrationOptions, setShowAiNarrationOptions, setAiNarrationOptions,
  handleTTSGenderFilterChange,
  handleGenerateTTS, handleAddTTSToSlide,
  handleGenerateAiNarration, handleSelectAiNarration,
  currentSlide,
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Volume2 className="w-5 h-5 text-orange-500" />
            Text-to-Speech (ElevenLabs)
          </DialogTitle>
          <DialogDescription>Converta texto em narração. Todas as vozes suportam Português, Inglês e Espanhol.</DialogDescription>
        </DialogHeader>

        {ttsLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-orange-500" />
            <span className="ml-3">Carregando vozes...</span>
          </div>
        ) : (
          <div className="space-y-6 py-4">
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium">Selecionar Voz ({ttsVoices.length})</label>
                <select className="text-xs px-2 py-1 rounded border bg-background" value={ttsGenderFilter}
                  onChange={(e) => handleTTSGenderFilterChange(e.target.value)}>
                  <option value="all">Todos</option>
                  <option value="male">Masculino</option>
                  <option value="female">Feminino</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto p-2 border rounded-lg">
                {ttsVoices.map((voice) => (
                  <div key={voice.voice_id}
                    className={`cursor-pointer p-3 rounded-lg border-2 transition-all ${
                      ttsSelectedVoice?.voice_id === voice.voice_id ? 'border-orange-500 bg-orange-500/10' : 'border-transparent hover:border-gray-300 hover:bg-muted/50'
                    }`}
                    onClick={() => setTTSSelectedVoice(voice)}>
                    <div className="flex items-center gap-2">
                      <span>{voice.gender === 'male' ? '👨' : voice.gender === 'female' ? '👩' : '🧑'}</span>
                      <div>
                        <p className="font-medium text-sm">{voice.name}</p>
                        <p className="text-xs text-muted-foreground truncate max-w-[140px]">{voice.accent || 'Multilíngue'}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium">Texto para Narração</label>
                <div className="flex items-center gap-2">
                  <select data-testid="ai-narration-style-select" className="text-xs px-2 py-1 rounded border bg-background"
                    value={aiNarrationStyle} onChange={(e) => setAiNarrationStyle(e.target.value)}>
                    <option value="educational">Educativo</option>
                    <option value="conversational">Conversacional</option>
                    <option value="formal">Formal</option>
                    <option value="friendly">Amigável</option>
                  </select>
                  <Button data-testid="ai-generate-narration-btn" size="sm" variant="outline"
                    onClick={handleGenerateAiNarration} disabled={aiNarrationLoading || !currentSlide}
                    className="text-xs border-purple-500/50 text-purple-400 hover:bg-purple-500/10 hover:text-purple-300">
                    {aiNarrationLoading ? (<><Loader2 className="w-3 h-3 mr-1 animate-spin" />Gerando...</>) : (<><Sparkles className="w-3 h-3 mr-1" />Gerar com IA</>)}
                  </Button>
                </div>
              </div>

              {showAiNarrationOptions && (
                <div data-testid="ai-narration-options" className="mb-3 space-y-2">
                  {aiNarrationLoading ? (
                    <div className="flex items-center justify-center py-6 border rounded-lg bg-purple-500/5 border-purple-500/20">
                      <Loader2 className="w-5 h-5 animate-spin text-purple-400 mr-2" />
                      <span className="text-sm text-purple-300">Gerando 3 opções com Gemini...</span>
                    </div>
                  ) : aiNarrationOptions.length > 0 ? (
                    <>
                      <p className="text-xs text-muted-foreground">Escolha uma das opções geradas pela IA:</p>
                      {aiNarrationOptions.map((option, idx) => (
                        <div key={idx} data-testid={`ai-narration-option-${idx}`}
                          onClick={() => handleSelectAiNarration(option)}
                          className="cursor-pointer p-3 border rounded-lg transition-all hover:border-purple-500/60 hover:bg-purple-500/10 group">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1">
                              <span className="text-xs font-semibold text-purple-400 mb-1 block">Opção {idx + 1}</span>
                              <p className="text-sm leading-relaxed">{option}</p>
                            </div>
                            <Check className="w-4 h-4 text-purple-400 opacity-0 group-hover:opacity-100 transition-opacity mt-1 shrink-0" />
                          </div>
                        </div>
                      ))}
                      <Button size="sm" variant="ghost" onClick={() => { setShowAiNarrationOptions(false); setAiNarrationOptions([]); }} className="text-xs text-muted-foreground">
                        <X className="w-3 h-3 mr-1" />Fechar opções
                      </Button>
                    </>
                  ) : null}
                </div>
              )}

              <textarea data-testid="tts-text-input" className="w-full h-32 p-3 border rounded-lg bg-background resize-none"
                placeholder="Digite o texto ou gere com IA..." value={ttsText} onChange={(e) => setTTSText(e.target.value)} />
            </div>

            {ttsAudioUrl && (
              <div className="p-4 border rounded-lg bg-green-500/10 border-green-500/30">
                <span className="text-sm font-medium text-green-400 block mb-2">Áudio Gerado</span>
                <audio src={ttsAudioUrl} controls className="w-full" />
              </div>
            )}
          </div>
        )}

        <DialogFooter className="flex justify-between gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <div className="flex gap-2">
            <Button onClick={handleGenerateTTS} disabled={ttsGenerating || !ttsText.trim() || !ttsSelectedVoice} className="bg-orange-600 hover:bg-orange-700">
              {ttsGenerating ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Gerando...</> : <><Volume2 className="w-4 h-4 mr-2" />Gerar Áudio</>}
            </Button>
            {ttsAudioUrl && (
              <Button onClick={handleAddTTSToSlide} className="bg-green-600 hover:bg-green-700">
                <Plus className="w-4 h-4 mr-2" />Adicionar ao Slide
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
