import React from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../../components/ui/dialog';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import {
  Loader2, Plus, Sparkles, User, Check,
} from 'lucide-react';

export function HeygenDialog({
  open, onOpenChange,
  heygenLoading, heygenGenerating,
  heygenAvatars, heygenVoices,
  heygenConfig, setHeygenConfig,
  heygenAvatarGenderFilter, setHeygenAvatarGenderFilter, reloadHeygenAvatars,
  heygenVoiceLanguageFilter, setHeygenVoiceLanguageFilter,
  heygenVoiceGenderFilter, setHeygenVoiceGenderFilter, reloadHeygenVoices,
  heygenAvailableLanguages,
  heygenCredits, heygenCreditsLoading,
  heygenVideoUrl, heygenVideoStatus, heygenElapsedTime,
  scriptMode, setScriptMode,
  aiScriptTopic, setAiScriptTopic,
  aiScriptStyle, setAiScriptStyle,
  aiScriptDuration, setAiScriptDuration,
  aiGeneratingScript,
  heygenOcrStyle, setHeygenOcrStyle,
  heygenOcrLoading, heygenOcrOptions,
  handleGenerateHeygenVideo, handleAddHeygenVideoToSlide,
  handleGenerateAiScript, handleHeygenOcrGenerate, handleSelectHeygenOcrOption,
  formatTime, currentSlide,
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <User className="w-5 h-5" />
            Criar Vídeo com Avatar (HeyGen)
          </DialogTitle>
        </DialogHeader>

        {/* Credits Display */}
        {heygenCreditsLoading ? (
          <div className="flex items-center justify-center p-3 rounded-lg border bg-slate-500/10 border-slate-500/30">
            <Loader2 className="w-4 h-4 animate-spin mr-2" />
            <span className="text-sm text-slate-400">Verificando créditos...</span>
          </div>
        ) : heygenCredits ? (
          <div className={`flex items-center justify-between p-3 rounded-lg border ${heygenCredits.has_credits ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">{heygenCredits.has_credits ? '✅' : '⚠️'} Créditos HeyGen:</span>
              <span className={`font-bold ${heygenCredits.has_credits ? 'text-green-500' : 'text-red-500'}`}>
                {heygenCredits.has_credits ? `${heygenCredits.remaining_quota} créditos API` : heygenCredits.has_plan_credits ? `API: 0 | Plano: ${heygenCredits.plan_credit}` : 'Sem créditos'}
              </span>
            </div>
            {!heygenCredits.has_credits && heygenCredits.has_plan_credits && (
              <p className="text-xs text-amber-400 mt-1">Seus créditos do plano ({heygenCredits.plan_credit}) são para o Studio web. Para usar a API, verifique se sua chave API tem créditos habilitados em app.heygen.com</p>
            )}
            {!heygenCredits.has_credits && <span className="text-xs text-red-500">Recarregue para gerar vídeos</span>}
          </div>
        ) : null}

        {heygenLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
            <span className="ml-3">Carregando avatares e vozes...</span>
          </div>
        ) : (
          <div className="space-y-6 py-4">
            {/* Avatar Selection */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium">Selecionar Avatar</label>
                <select className="text-xs px-2 py-1 rounded border bg-background" value={heygenAvatarGenderFilter}
                  onChange={(e) => { setHeygenAvatarGenderFilter(e.target.value); reloadHeygenAvatars(e.target.value); }}
                  data-testid="heygen-avatar-gender-filter">
                  <option value="all">Todos</option><option value="male">Masculino</option><option value="female">Feminino</option>
                </select>
              </div>
              <div className="grid grid-cols-4 gap-2 max-h-48 overflow-y-auto p-2 border rounded-lg">
                {heygenAvatars.map((avatar) => (
                  <div key={avatar.avatar_id}
                    className={`cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${heygenConfig.avatarId === avatar.avatar_id ? 'border-purple-500 ring-2 ring-purple-500/30' : 'border-transparent hover:border-gray-300'}`}
                    onClick={() => setHeygenConfig({ ...heygenConfig, avatarId: avatar.avatar_id })}>
                    <div className="relative">
                      <img src={avatar.preview_image_url} alt={avatar.avatar_name} className="w-full aspect-square object-cover" />
                      <span className="absolute top-1 right-1 text-xs bg-black/50 px-1 rounded">{avatar.gender === 'male' ? '♂' : avatar.gender === 'female' ? '♀' : ''}</span>
                    </div>
                    <div className="text-xs text-center py-1 truncate px-1">{avatar.avatar_name}</div>
                  </div>
                ))}
                {heygenAvatars.length === 0 && <div className="col-span-4 text-center py-8 text-muted-foreground">Nenhum avatar disponível. Verifique sua API Key.</div>}
              </div>
              <div className="text-xs text-muted-foreground mt-1">{heygenAvatars.length} avatares disponíveis</div>
            </div>

            {/* Voice Selection */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium">Selecionar Voz</label>
                <div className="flex gap-2">
                  <select className="text-xs px-2 py-1 rounded border bg-background" value={heygenVoiceLanguageFilter}
                    onChange={(e) => { setHeygenVoiceLanguageFilter(e.target.value); reloadHeygenVoices(e.target.value, heygenVoiceGenderFilter); }}
                    data-testid="heygen-voice-language-filter">
                    <option value="all">Todos idiomas</option>
                    {heygenAvailableLanguages.map((lang) => (<option key={lang.value} value={lang.value}>{lang.label}</option>))}
                  </select>
                  <select className="text-xs px-2 py-1 rounded border bg-background" value={heygenVoiceGenderFilter}
                    onChange={(e) => { setHeygenVoiceGenderFilter(e.target.value); reloadHeygenVoices(heygenVoiceLanguageFilter, e.target.value); }}
                    data-testid="heygen-voice-gender-filter">
                    <option value="all">Todos</option><option value="male">Masculino</option><option value="female">Feminino</option>
                  </select>
                </div>
              </div>
              <select className="w-full h-10 px-3 rounded-md border bg-background" value={heygenConfig.voiceId}
                onChange={(e) => setHeygenConfig({ ...heygenConfig, voiceId: e.target.value })} data-testid="heygen-voice-select">
                <option value="">Selecione uma voz...</option>
                {heygenVoices.map((voice) => (
                  <option key={voice.voice_id} value={voice.voice_id}>
                    {voice.country_flag} {voice.name} ({voice.language}) - {voice.gender === 'male' ? '♂ Masc' : voice.gender === 'female' ? '♀ Fem' : voice.gender}
                  </option>
                ))}
              </select>
              <div className="text-xs text-muted-foreground mt-1">{heygenVoices.length} vozes disponíveis</div>
            </div>

            {/* Script Input */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium">Script do Vídeo <span className="text-muted-foreground ml-2 text-xs">({heygenConfig.script.length}/5000 caracteres)</span></label>
                <div className="flex gap-1 bg-muted rounded-lg p-1">
                  {[['manual', 'Digitar'], ['ocr', null], ['ai', 'Tema Livre']].map(([mode, label]) => (
                    <button key={mode}
                      className={`px-3 py-1 text-xs rounded-md transition-all ${scriptMode === mode ? (mode === 'manual' ? 'bg-background shadow-sm font-medium' : 'bg-gradient-to-r from-purple-500 to-cyan-500 text-white font-medium') : 'text-muted-foreground hover:text-foreground'}`}
                      onClick={() => setScriptMode(mode)} data-testid={mode === 'ocr' ? 'heygen-ocr-tab' : undefined}>
                      {mode === 'ocr' ? <><Sparkles className="w-3 h-3 inline mr-1" />Ler Slide</> : label}
                    </button>
                  ))}
                </div>
              </div>

              {scriptMode === 'manual' ? (
                <>
                  <textarea className="w-full h-40 p-3 rounded-md border bg-background text-sm"
                    placeholder="Digite o texto que o avatar irá narrar..."
                    value={heygenConfig.script}
                    onChange={(e) => setHeygenConfig({ ...heygenConfig, script: e.target.value.slice(0, 5000) })}
                    data-testid="heygen-script-input" />
                  <p className="text-xs text-muted-foreground mt-1">Dica: Escreva de forma natural, como se estivesse conversando. O avatar irá falar com sincronismo labial realista.</p>
                </>
              ) : scriptMode === 'ocr' ? (
                <div className="space-y-3 p-4 border rounded-lg bg-gradient-to-br from-purple-500/5 to-cyan-500/5">
                  <p className="text-sm text-muted-foreground">A IA irá ler o conteúdo do slide atual (textos, imagens) e sugerir 3 opções de script para o avatar narrar.</p>
                  <div className="flex items-center gap-3">
                    <select data-testid="heygen-ocr-style-select" className="text-sm px-3 py-2 rounded-md border bg-background flex-1" value={heygenOcrStyle} onChange={(e) => setHeygenOcrStyle(e.target.value)}>
                      <option value="educational">Educativo</option><option value="conversational">Conversacional</option><option value="formal">Formal</option><option value="friendly">Amigável</option>
                    </select>
                    <Button data-testid="heygen-ocr-generate-btn" onClick={handleHeygenOcrGenerate} disabled={heygenOcrLoading || !currentSlide} className="bg-gradient-to-r from-purple-600 to-cyan-500 gap-2">
                      {heygenOcrLoading ? <><Loader2 className="w-4 h-4 animate-spin" />Lendo slide...</> : <><Sparkles className="w-4 h-4" />Ler Slide e Gerar</>}
                    </Button>
                  </div>
                  {heygenOcrLoading && (
                    <div className="flex items-center justify-center py-6 border rounded-lg bg-purple-500/5 border-purple-500/20">
                      <Loader2 className="w-5 h-5 animate-spin text-purple-400 mr-2" />
                      <span className="text-sm text-purple-300">Analisando slide com Gemini Vision...</span>
                    </div>
                  )}
                  {heygenOcrOptions.length > 0 && (
                    <div data-testid="heygen-ocr-options" className="space-y-2">
                      <p className="text-xs font-medium text-muted-foreground">Escolha uma opção:</p>
                      {heygenOcrOptions.map((option, idx) => (
                        <div key={idx} data-testid={`heygen-ocr-option-${idx}`} onClick={() => handleSelectHeygenOcrOption(option)}
                          className="cursor-pointer p-3 border rounded-lg transition-all hover:border-purple-500/60 hover:bg-purple-500/10 group">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1"><span className="text-xs font-semibold text-purple-400 mb-1 block">Opção {idx + 1}</span><p className="text-sm leading-relaxed">{option}</p></div>
                            <Check className="w-4 h-4 text-purple-400 opacity-0 group-hover:opacity-100 transition-opacity mt-1 shrink-0" />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-4 p-4 border rounded-lg bg-gradient-to-br from-purple-500/5 to-cyan-500/5">
                  <div>
                    <label className="text-sm font-medium mb-1 block">Tema do Vídeo</label>
                    <textarea className="w-full h-24 p-3 rounded-md border bg-background text-sm"
                      placeholder="Descreva o tema do vídeo. Ex: Explique os benefícios do trabalho em equipe..."
                      value={aiScriptTopic} onChange={(e) => setAiScriptTopic(e.target.value)} data-testid="ai-script-topic" />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium mb-1 block">Estilo</label>
                      <select className="w-full h-10 px-3 rounded-md border bg-background text-sm" value={aiScriptStyle} onChange={(e) => setAiScriptStyle(e.target.value)}>
                        <option value="educational">Educativo</option><option value="conversational">Conversacional</option><option value="formal">Formal</option><option value="friendly">Amigável</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-sm font-medium mb-1 block">Duração</label>
                      <select className="w-full h-10 px-3 rounded-md border bg-background text-sm" value={aiScriptDuration} onChange={(e) => setAiScriptDuration(e.target.value)}>
                        <option value="short">Curto (30s-1min)</option><option value="medium">Médio (1-2min)</option><option value="long">Longo (3-5min)</option>
                      </select>
                    </div>
                  </div>
                  <Button onClick={handleGenerateAiScript} disabled={aiGeneratingScript || !aiScriptTopic.trim()} className="w-full bg-gradient-to-r from-purple-600 to-cyan-500" data-testid="generate-ai-script-btn">
                    {aiGeneratingScript ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Gerando script...</> : <><Sparkles className="w-4 h-4 mr-2" />Gerar Script com IA</>}
                  </Button>
                  {heygenConfig.script && (
                    <div className="mt-3 p-3 bg-background rounded-md border">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium text-green-600">Script gerado</span>
                        <button className="text-xs text-muted-foreground hover:text-foreground" onClick={() => setScriptMode('manual')}>Editar →</button>
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-3">{heygenConfig.script.slice(0, 200)}...</p>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Video Title */}
            <div>
              <label className="text-sm font-medium">Título do Vídeo</label>
              <Input placeholder="Ex: Introdução ao Curso" value={heygenConfig.title}
                onChange={(e) => setHeygenConfig({ ...heygenConfig, title: e.target.value })} data-testid="heygen-title-input" />
            </div>

            {/* Transparent Background Option */}
            <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
              <input type="checkbox" id="transparent-bg" checked={heygenConfig.transparentBackground}
                onChange={(e) => setHeygenConfig({ ...heygenConfig, transparentBackground: e.target.checked })}
                className="w-4 h-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500" data-testid="heygen-transparent-bg" />
              <label htmlFor="transparent-bg" className="flex-1 cursor-pointer">
                <span className="text-sm font-medium">Fundo Transparente</span>
                <p className="text-xs text-muted-foreground">Gera o vídeo com fundo transparente (WebM) para sobrepor em slides</p>
              </label>
            </div>

            {/* Status Display */}
            {heygenGenerating && (
              <div className="bg-purple-500/10 border border-purple-500/30 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <Loader2 className="w-5 h-5 animate-spin text-purple-500" />
                  <div className="flex-1">
                    <div className="font-medium text-purple-700">Gerando vídeo com avatar...</div>
                    <div className="text-sm text-muted-foreground">Status: <span className="capitalize">{heygenVideoStatus === 'processing' ? 'Processando' : heygenVideoStatus || 'Iniciando...'}</span></div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-mono font-bold text-purple-600">{formatTime(heygenElapsedTime)}</div>
                    <div className="text-xs text-muted-foreground">decorrido</div>
                  </div>
                </div>
                <div className="mt-3 space-y-2">
                  <div className="h-1.5 bg-purple-200 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-purple-500 to-cyan-500 rounded-full animate-pulse" style={{ width: '100%', animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite' }} />
                  </div>
                  <div className="flex items-start gap-2 text-xs text-muted-foreground">
                    <span className="text-amber-600">⏱️</span>
                    <span>A HeyGen está renderizando seu vídeo. Isso geralmente leva de <strong>2 a 10 minutos</strong>. Você pode minimizar esta janela e continuar editando.</span>
                  </div>
                </div>
                {heygenElapsedTime > 120 && (
                  <div className="mt-3 p-2 bg-blue-500/10 rounded text-xs text-blue-700"><strong>Dica:</strong> Vídeos mais longos podem levar mais tempo. O tempo limite máximo é de 15 minutos.</div>
                )}
              </div>
            )}

            {/* Video Ready */}
            {heygenVideoUrl && !heygenGenerating && (
              <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center text-white">✓</div>
                  <div className="font-medium text-green-700">Vídeo gerado com sucesso!</div>
                </div>
                <video src={heygenVideoUrl} controls className="w-full rounded-lg" style={{ maxHeight: '200px' }} />
              </div>
            )}
          </div>
        )}

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          {heygenVideoUrl ? (
            <Button onClick={handleAddHeygenVideoToSlide} className="bg-gradient-to-r from-purple-600 to-cyan-500" data-testid="add-heygen-video-btn">
              <Plus className="w-4 h-4 mr-2" /> Adicionar ao Slide
            </Button>
          ) : (
            <Button onClick={handleGenerateHeygenVideo}
              disabled={heygenGenerating || !heygenConfig.avatarId || !heygenConfig.voiceId || !heygenConfig.script}
              className="bg-gradient-to-r from-purple-600 to-cyan-500" data-testid="generate-heygen-video-btn">
              {heygenGenerating ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Gerando...</> : <><Sparkles className="w-4 h-4 mr-2" />Gerar Vídeo</>}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
