import React from 'react';
import { Card, CardContent } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { Badge } from '../../../components/ui/badge';
import { UserCircle, Loader2, ArrowRight, Check, X } from 'lucide-react';

export default function HeygenStatusCard({ enabled, status, busy, onRefresh }) {
  if (!enabled) return null;
  const videos=status?.videos || [], failures=videos.filter(v=>v.status==='failed').length;
  const allReady=videos.length>0 && videos.every(v=>v.status==='completed');
  return <Card className="bg-purple-900/10 border-purple-800/30 text-left mx-auto max-w-md" data-testid="heygen-status-card"><CardContent className="p-4 space-y-3">
    <div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-purple-300 flex items-center gap-2"><UserCircle className="w-4 h-4" />Vídeos Avatar HeyGen</h3>
      <Button variant="ghost" size="sm" onClick={onRefresh} disabled={busy} className="text-xs text-purple-400" data-testid="refresh-heygen-btn">{busy?<Loader2 className="w-3 h-3 animate-spin" />:<ArrowRight className="w-3 h-3" />} Atualizar</Button>
    </div>
    {videos.map((v,i)=><div key={v.slideId || i} className="space-y-1" data-testid={`heygen-video-status-${i}`}>
      <div className="flex items-center gap-2 text-xs">{v.status==='completed'?<Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />:v.status==='failed'?<X className="w-3.5 h-3.5 text-red-400 shrink-0" />:<Loader2 className="w-3.5 h-3.5 text-purple-400 animate-spin shrink-0" />}
        <span className="text-slate-300 truncate flex-1">{v.title}</span><Badge variant="outline" className={`text-[9px] ${v.status==='completed'?'border-emerald-700 text-emerald-400':v.status==='failed'?'border-red-700 text-red-400':'border-purple-700 text-purple-400'}`}>{v.status==='completed'?'Pronto':v.status==='failed'?'Falhou':'Processando...'}</Badge>
      </div>{v.error && <p role="alert" className="text-xs text-amber-300 break-words">{v.error}</p>}
    </div>)}
    {allReady && <p className="text-xs text-emerald-300 text-center">Todos os vídeos estão prontos e vinculados. Abra o Editor e revise as perguntas e os tempos de pausa.</p>}
    {failures>0 && <p role="status" className="text-xs text-amber-300">{failures} vídeo(s) com falha ou pendência de vínculo. O curso foi preservado; não é necessário gerá-lo novamente.</p>}
    <p className="text-xs text-slate-400">Atualizar consulta os vídeos existentes e tenta reconectá-los aos slides originais, preservando as perguntas. Não solicita nova geração nem créditos de geração.</p>
  </CardContent></Card>;
}
