import React from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../../../components/ui/dialog';
import { Button } from '../../../components/ui/button';
import {
  Loader2, Check, X, Play, ArrowRight, AlertTriangle, Sparkles, User, Presentation,
} from 'lucide-react';

export function SlideVideoDialog({
  open, onOpenChange,
  heygenLoading, heygenAvatars, heygenVoices,
  heygenConfig, setHeygenConfig,
  heygenCredits,
  slideVideoStep, setSlideVideoStep,
  slideVideoScripts, setSlideVideoScripts,
  slideVideoScriptsLoading,
  slideVideoGenerating, slideVideoBatchId, slideVideoBatchPolling,
  avatarSearch, setAvatarSearch,
  avatarGenderFilter, setAvatarGenderFilter,
  voiceLanguageFilter, setVoiceLanguageFilter,
  voiceGenderFilter, setVoiceGenderFilter,
  handleGenerateAllScripts, handleGenerateBatchSlideVideos,
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-5xl max-h-[88vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Presentation className="w-5 h-5 text-amber-500" />
            Slides para Vídeo com Avatar
          </DialogTitle>
          <DialogDescription>Gere vídeos com avatar narrando cada slide do curso</DialogDescription>
        </DialogHeader>

        {/* Step indicator */}
        <div className="flex items-center gap-2 px-1">
          {['setup', 'scripts', 'generate'].map((step, i) => (
            <button key={step} onClick={() => setSlideVideoStep(step)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${slideVideoStep === step ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' : 'text-muted-foreground hover:text-foreground'}`}>
              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${slideVideoStep === step ? 'bg-amber-500 text-black' : 'bg-muted'}`}>{i + 1}</span>
              {step === 'setup' ? 'Avatar e Voz' : step === 'scripts' ? 'Scripts' : 'Gerar'}
            </button>
          ))}
          {heygenCredits && (
            <div className={`ml-auto flex items-center gap-1.5 px-3 py-1 rounded-full text-xs ${heygenCredits.has_credits ? 'bg-green-500/10 text-green-400' : heygenCredits.has_plan_credits ? 'bg-amber-500/10 text-amber-400' : 'bg-red-500/10 text-red-400'}`}>
              {heygenCredits.has_credits ? '✅' : '⚠️'}
              {heygenCredits.has_credits ? `${heygenCredits.remaining_quota} créditos API` : heygenCredits.has_plan_credits ? `API: 0 | Plano: ${heygenCredits.plan_credit}` : '0 créditos'}
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto space-y-3 pr-1">
          {/* ===== STEP 1: AVATAR & VOICE SELECTION ===== */}
          {slideVideoStep === 'setup' && (
            <>
              {/* Avatar Section */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium">Avatar</label>
                  <div className="flex items-center gap-1.5">
                    <input type="text" placeholder="Buscar..." value={avatarSearch} onChange={e => setAvatarSearch(e.target.value)}
                      className="h-7 w-36 rounded-md border border-input bg-background px-2 text-xs" data-testid="avatar-search-input" />
                    {['all', 'male', 'female'].map(g => (
                      <button key={g} onClick={() => setAvatarGenderFilter(g)}
                        className={`px-2 py-1 rounded text-[11px] font-medium transition-all ${avatarGenderFilter === g ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' : 'text-muted-foreground border border-transparent hover:border-border'}`}
                        data-testid={`avatar-filter-${g}`}>
                        {g === 'all' ? 'Todos' : g === 'male' ? 'Masculino' : 'Feminino'}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="grid grid-cols-5 sm:grid-cols-6 md:grid-cols-8 gap-2 max-h-[240px] overflow-y-auto p-1" data-testid="avatar-grid">
                  {heygenLoading && heygenAvatars.length === 0 && (
                    <div className="col-span-full flex items-center justify-center py-8 text-sm text-muted-foreground">
                      <Loader2 className="w-5 h-5 animate-spin mr-2" /> Carregando avatares...
                    </div>
                  )}
                  {heygenAvatars
                    .filter(a => avatarGenderFilter === 'all' || a.gender === avatarGenderFilter)
                    .filter(a => !avatarSearch || (a.avatar_name || '').toLowerCase().includes(avatarSearch.toLowerCase()))
                    .slice(0, 48)
                    .map(a => (
                      <button key={a.avatar_id}
                        onClick={() => setHeygenConfig(prev => ({ ...prev, avatarId: a.avatar_id }))}
                        className={`group relative rounded-lg overflow-hidden border-2 transition-all aspect-[3/4] ${heygenConfig.avatarId === a.avatar_id ? 'border-amber-500 ring-2 ring-amber-500/30 scale-[1.02]' : 'border-transparent hover:border-amber-500/40'}`}
                        data-testid={`avatar-card-${a.avatar_id}`}>
                        {a.preview_image_url ? (
                          <img src={a.preview_image_url} alt={a.avatar_name} className="w-full h-full object-cover" loading="lazy" />
                        ) : (
                          <div className="w-full h-full bg-muted flex items-center justify-center"><User className="w-6 h-6 text-muted-foreground" /></div>
                        )}
                        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-1.5">
                          <p className="text-[9px] text-white font-medium truncate leading-tight">{a.avatar_name}</p>
                          <p className="text-[8px] text-white/60">{a.gender === 'male' ? 'M' : 'F'}</p>
                        </div>
                        {heygenConfig.avatarId === a.avatar_id && (
                          <div className="absolute top-1 right-1 w-5 h-5 rounded-full bg-amber-500 flex items-center justify-center"><Check className="w-3 h-3 text-black" /></div>
                        )}
                      </button>
                    ))}
                </div>
                {heygenConfig.avatarId && (
                  <p className="text-xs text-amber-400">Selecionado: {heygenAvatars.find(a => a.avatar_id === heygenConfig.avatarId)?.avatar_name || heygenConfig.avatarId}</p>
                )}
              </div>

              {/* Voice Section */}
              <div className="space-y-2 border-t border-border pt-3">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium">Voz</label>
                  <div className="flex items-center gap-1.5">
                    <select value={voiceLanguageFilter} onChange={e => setVoiceLanguageFilter(e.target.value)}
                      className="h-7 rounded-md border border-input bg-background px-2 text-xs" data-testid="voice-language-filter">
                      <option value="">Todos idiomas</option>
                      <option value="Portuguese">Português</option><option value="English">Inglês</option>
                      <option value="Spanish">Espanhol</option><option value="French">Francês</option>
                      <option value="German">Alemão</option><option value="Italian">Italiano</option>
                    </select>
                    {['all', 'male', 'female'].map(g => (
                      <button key={g} onClick={() => setVoiceGenderFilter(g)}
                        className={`px-2 py-1 rounded text-[11px] font-medium transition-all ${voiceGenderFilter === g ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'text-muted-foreground border border-transparent hover:border-border'}`}
                        data-testid={`voice-filter-${g}`}>
                        {g === 'all' ? 'Todos' : g === 'male' ? 'Masculino' : 'Feminino'}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 max-h-[180px] overflow-y-auto" data-testid="voice-list">
                  {heygenLoading && heygenVoices.length === 0 && (
                    <div className="col-span-full flex items-center justify-center py-6 text-sm text-muted-foreground">
                      <Loader2 className="w-5 h-5 animate-spin mr-2" /> Carregando vozes...
                    </div>
                  )}
                  {heygenVoices
                    .filter(v => !voiceLanguageFilter || (v.language || '').includes(voiceLanguageFilter))
                    .filter(v => voiceGenderFilter === 'all' || v.gender === voiceGenderFilter)
                    .slice(0, 60)
                    .map(v => (
                      <button key={v.voice_id}
                        onClick={() => setHeygenConfig(prev => ({ ...prev, voiceId: v.voice_id }))}
                        className={`flex items-center gap-2 px-2.5 py-2 rounded-lg border text-left transition-all ${heygenConfig.voiceId === v.voice_id ? 'border-cyan-500 bg-cyan-500/10' : 'border-border/50 hover:border-cyan-500/40'}`}
                        data-testid={`voice-card-${v.voice_id}`}>
                        <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${v.gender === 'male' ? 'bg-blue-500/20 text-blue-400' : 'bg-pink-500/20 text-pink-400'}`}>
                          {v.gender === 'male' ? 'M' : 'F'}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium truncate">{v.display_name || v.name}</p>
                          <p className="text-[10px] text-muted-foreground">{v.language}</p>
                        </div>
                        {v.preview_audio && (
                          <span role="button" onClick={e => { e.stopPropagation(); new Audio(v.preview_audio).play(); }}
                            className="text-cyan-400 hover:text-cyan-300 shrink-0 cursor-pointer"><Play className="w-3 h-3" /></span>
                        )}
                        {heygenConfig.voiceId === v.voice_id && <Check className="w-3.5 h-3.5 text-cyan-400 shrink-0" />}
                      </button>
                    ))}
                </div>
              </div>
            </>
          )}

          {/* ===== STEP 2: SCRIPTS ===== */}
          {slideVideoStep === 'scripts' && (
            <>
              <div className="flex items-center gap-2 flex-wrap">
                <Button onClick={handleGenerateAllScripts} disabled={slideVideoScriptsLoading} variant="outline" size="sm" data-testid="generate-all-scripts-btn">
                  {slideVideoScriptsLoading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Sparkles className="w-4 h-4 mr-1" />}
                  {slideVideoScriptsLoading ? 'Gerando...' : 'Gerar Scripts com IA'}
                </Button>
                <button onClick={() => setSlideVideoScripts(prev => prev.map(s => ({ ...s, enabled: true })))} className="text-[11px] text-amber-400 hover:underline">Selecionar todos</button>
                <button onClick={() => setSlideVideoScripts(prev => prev.map(s => ({ ...s, enabled: false })))} className="text-[11px] text-muted-foreground hover:underline">Desmarcar todos</button>
                <span className="ml-auto text-xs text-muted-foreground">{slideVideoScripts.filter(s => s.enabled).length} selecionados | {slideVideoScripts.filter(s => s.script.trim()).length} com script</span>
              </div>
              <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1" data-testid="slide-video-list">
                {slideVideoScripts.map((s, i) => (
                  <div key={i}
                    className={`rounded-lg border p-3 transition-all ${s.status === 'completed' ? 'border-green-500/40 bg-green-500/5' : s.status === 'processing' ? 'border-amber-500/40 bg-amber-500/5' : s.status === 'failed' ? 'border-red-500/40 bg-red-500/5' : s.enabled ? 'border-border' : 'border-border/30 opacity-50'}`}
                    data-testid={`slide-video-row-${i}`}>
                    <div className="flex items-center gap-2 mb-2">
                      <input type="checkbox" checked={s.enabled}
                        onChange={() => setSlideVideoScripts(prev => prev.map((ss, ii) => ii === i ? { ...ss, enabled: !ss.enabled } : ss))} className="rounded" />
                      <span className="text-sm font-medium flex-1 truncate">{i + 1}. {s.title}</span>
                      {s.status === 'processing' && <Loader2 className="w-3 h-3 animate-spin text-amber-500" />}
                      {s.status === 'completed' && <Check className="w-3 h-3 text-green-500" />}
                      {s.status === 'failed' && <X className="w-3 h-3 text-red-500" />}
                      {s.videoUrl && <a href={s.videoUrl} target="_blank" rel="noreferrer" className="text-xs text-cyan-400 hover:text-cyan-300 underline">Assistir</a>}
                    </div>
                    {s.enabled && (
                      <>
                        <textarea value={s.script}
                          onChange={e => setSlideVideoScripts(prev => prev.map((ss, ii) => ii === i ? { ...ss, script: e.target.value } : ss))}
                          placeholder="Script de narração..." rows={2}
                          className="w-full text-xs bg-background border border-input rounded-md p-2 resize-none"
                          disabled={s.status === 'processing' || s.status === 'completed'}
                          data-testid={`slide-video-script-${i}`} />
                        {s.script && <span className="text-[10px] text-muted-foreground">{s.script.length} caracteres</span>}
                      </>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}

          {/* ===== STEP 3: GENERATE ===== */}
          {slideVideoStep === 'generate' && (
            <>
              <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
                <h3 className="text-sm font-semibold">Resumo da Geração</h3>
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div className="rounded-lg bg-background p-3 border">
                    <p className="text-2xl font-bold text-amber-400">{slideVideoScripts.filter(s => s.enabled && s.script.trim()).length}</p>
                    <p className="text-[10px] text-muted-foreground">Slides com vídeo</p>
                  </div>
                  <div className="rounded-lg bg-background p-3 border">
                    <p className="text-sm font-medium truncate text-cyan-400">{heygenAvatars.find(a => a.avatar_id === heygenConfig.avatarId)?.avatar_name || 'Não selecionado'}</p>
                    <p className="text-[10px] text-muted-foreground">Avatar</p>
                  </div>
                  <div className="rounded-lg bg-background p-3 border">
                    <p className="text-sm font-medium truncate text-cyan-400">{heygenVoices.find(v => v.voice_id === heygenConfig.voiceId)?.name || 'Não selecionada'}</p>
                    <p className="text-[10px] text-muted-foreground">Voz</p>
                  </div>
                </div>
                {(!heygenConfig.avatarId || !heygenConfig.voiceId) && (
                  <p className="text-xs text-red-400 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> Volte ao passo 1 e selecione avatar e voz.</p>
                )}
                {slideVideoScripts.filter(s => s.enabled && s.script.trim()).length === 0 && (
                  <p className="text-xs text-red-400 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> Volte ao passo 2 e gere scripts para os slides.</p>
                )}
              </div>
              {slideVideoBatchId && (
                <div className="rounded-lg bg-muted/50 p-3 border" data-testid="slide-video-batch-progress">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Progresso</span>
                    <span className="text-xs text-muted-foreground">
                      {slideVideoScripts.filter(s => s.status === 'completed').length}/{slideVideoScripts.filter(s => s.enabled && s.script.trim()).length} concluídos
                    </span>
                  </div>
                  <div className="w-full bg-muted rounded-full h-2">
                    <div className="bg-green-500 h-2 rounded-full transition-all"
                      style={{ width: `${(slideVideoScripts.filter(s => s.status === 'completed').length / Math.max(slideVideoScripts.filter(s => s.enabled && s.script.trim()).length, 1)) * 100}%` }} />
                  </div>
                  {slideVideoBatchPolling && (
                    <p className="text-xs text-amber-400 mt-2 flex items-center gap-1"><Loader2 className="w-3 h-3 animate-spin" /> Aguardando processamento do HeyGen...</p>
                  )}
                  <div className="mt-3 space-y-1">
                    {slideVideoScripts.filter(s => s.enabled && s.script.trim()).map(s => (
                      <div key={s.index} className="flex items-center gap-2 text-xs py-1">
                        {s.status === 'completed' ? <Check className="w-3 h-3 text-green-500" /> :
                         s.status === 'processing' ? <Loader2 className="w-3 h-3 animate-spin text-amber-500" /> :
                         s.status === 'failed' ? <X className="w-3 h-3 text-red-500" /> :
                         <div className="w-3 h-3 rounded-full border border-muted-foreground" />}
                        <span className="flex-1 truncate">{s.index + 1}. {s.title}</span>
                        {s.videoUrl && <a href={s.videoUrl} target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline">Assistir</a>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Fechar</Button>
          {slideVideoStep === 'setup' && (
            <Button onClick={() => setSlideVideoStep('scripts')} disabled={!heygenConfig.avatarId || !heygenConfig.voiceId} className="bg-amber-600 hover:bg-amber-700">
              Próximo: Scripts <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          )}
          {slideVideoStep === 'scripts' && (
            <Button onClick={() => setSlideVideoStep('generate')} disabled={slideVideoScripts.filter(s => s.enabled && s.script.trim()).length === 0} className="bg-amber-600 hover:bg-amber-700">
              Próximo: Gerar <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          )}
          {slideVideoStep === 'generate' && (
            <Button onClick={handleGenerateBatchSlideVideos}
              disabled={slideVideoGenerating || slideVideoBatchPolling || !heygenConfig.avatarId || !heygenConfig.voiceId || slideVideoScripts.filter(s => s.enabled && s.script.trim()).length === 0}
              className="bg-gradient-to-r from-amber-500 to-rose-500 hover:from-amber-600 hover:to-rose-600" data-testid="generate-batch-videos-btn">
              {slideVideoGenerating ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Play className="w-4 h-4 mr-1" />}
              Gerar {slideVideoScripts.filter(s => s.enabled && s.script.trim()).length} Vídeos
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
