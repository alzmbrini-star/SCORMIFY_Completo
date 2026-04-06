import React, { useState, useEffect, useCallback } from 'react';
import { getApiUrl } from '../../../utils/apiUrl';
import { authHeaders } from '../../../contexts/AuthContext';
import { useAuth } from '../../../contexts/AuthContext';
import { Button } from '../../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { ScrollArea } from '../../../components/ui/scroll-area';
import { Textarea } from '../../../components/ui/textarea';
import { toast } from 'sonner';
import {
  BookOpen, Clock, Check, Loader2, ArrowLeft, ArrowRight,
  Eye, Pencil, Send, X, RefreshCw, CheckCircle, XCircle,
  User, FileText, Volume2, Play, Save,
} from 'lucide-react';

const API = getApiUrl();

export default function ApprovalQueuePanel({ onResumeSession }) {
  const { user, isSuperAdmin, isAprovador } = useAuth();
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedSession, setSelectedSession] = useState(null);
  const [activeSlide, setActiveSlide] = useState(0);
  const [editedSlides, setEditedSlides] = useState({});
  const [saving, setSaving] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [showRejectDialog, setShowRejectDialog] = useState(false);

  const fetchQueue = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/agent/approval-queue`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setQueue(data);
      }
    } catch {
      toast.error('Erro ao carregar fila de aprovacao');
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchQueue(); }, [fetchQueue]);

  const handleSelectSession = async (session) => {
    // Fetch full session with storyboard
    try {
      const res = await fetch(`${API}/api/agent/sessions/${session.id}`, { headers: authHeaders() });
      if (res.ok) {
        const full = await res.json();
        setSelectedSession(full);
        setActiveSlide(0);
        setEditedSlides({});
      }
    } catch {
      toast.error('Erro ao carregar sessao');
    }
  };

  const handleTextEdit = (slideIdx, field, value) => {
    setEditedSlides(prev => {
      const slide = prev[slideIdx] || {};
      return { ...prev, [slideIdx]: { ...slide, [field]: value } };
    });
  };

  const handleElementEdit = (slideIdx, elIdx, content) => {
    setEditedSlides(prev => {
      const slide = prev[slideIdx] || {};
      const elements = slide.elements || [];
      const existing = elements.find(e => e.index === elIdx);
      const updated = existing
        ? elements.map(e => e.index === elIdx ? { ...e, content } : e)
        : [...elements, { index: elIdx, content }];
      return { ...prev, [slideIdx]: { ...slide, elements: updated } };
    });
  };

  const hasEdits = Object.keys(editedSlides).length > 0;

  const handleSaveEdits = async () => {
    if (!selectedSession || !hasEdits) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/agent/sessions/${selectedSession.id}/update-storyboard-text`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ edits: editedSlides }),
      });
      if (res.ok) {
        toast.success('Textos salvos com sucesso');
        // Refresh session data
        const updated = await fetch(`${API}/api/agent/sessions/${selectedSession.id}`, { headers: authHeaders() });
        if (updated.ok) setSelectedSession(await updated.json());
        setEditedSlides({});
      } else {
        toast.error('Erro ao salvar edicoes');
      }
    } catch {
      toast.error('Erro ao salvar');
    }
    setSaving(false);
  };

  const handleApprove = async () => {
    if (!selectedSession) return;
    // Save pending edits first
    if (hasEdits) await handleSaveEdits();
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/agent/sessions/${selectedSession.id}/approve-storyboard`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({}),
      });
      if (res.ok) {
        toast.success('Storyboard aprovado!');
        setSelectedSession(null);
        fetchQueue();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Erro ao aprovar');
      }
    } catch {
      toast.error('Erro ao aprovar');
    }
    setSaving(false);
  };

  const handleReject = async () => {
    if (!selectedSession) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/agent/sessions/${selectedSession.id}/reject-storyboard`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ reason: rejectionReason }),
      });
      if (res.ok) {
        toast.success('Storyboard devolvido para revisao');
        setSelectedSession(null);
        setShowRejectDialog(false);
        setRejectionReason('');
        fetchQueue();
      } else {
        toast.error('Erro ao rejeitar');
      }
    } catch {
      toast.error('Erro ao rejeitar');
    }
    setSaving(false);
  };

  const handleResume = async (session) => {
    if (onResumeSession) {
      onResumeSession(session);
    }
  };

  // Detailed view of a storyboard session
  if (selectedSession) {
    const storyboard = selectedSession.storyboard;
    const slides = storyboard?.slides || [];
    const slide = slides[activeSlide];
    const slideEdits = editedSlides[activeSlide] || {};

    return (
      <div className="space-y-4" data-testid="approval-detail-panel">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => setSelectedSession(null)} data-testid="back-to-queue">
            <ArrowLeft className="w-4 h-4 mr-1" /> Voltar
          </Button>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-amber-400" />
            Revisar Storyboard
          </h2>
          <Badge className="bg-amber-600/20 text-amber-300 text-xs">
            {selectedSession.config?.title || 'Sem titulo'}
          </Badge>
        </div>

        {/* Slide selector pills */}
        <div className="flex gap-1 flex-wrap">
          {slides.map((s, i) => (
            <button key={i} onClick={() => setActiveSlide(i)}
              className={`px-2 py-1 rounded text-xs transition-colors ${
                i === activeSlide ? 'bg-amber-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              } ${editedSlides[i] ? 'ring-1 ring-amber-400' : ''}`}
              data-testid={`approval-slide-btn-${i}`}
            >
              {i + 1}
              {editedSlides[i] && <span className="ml-0.5 text-amber-300">*</span>}
            </button>
          ))}
        </div>

        {/* Slide editor */}
        {slide && (
          <Card className="bg-slate-900/50 border-slate-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Badge className="text-xs bg-slate-700 text-slate-300">{slide.type || 'content'}</Badge>
                Slide {activeSlide + 1}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* Editable title */}
              <div>
                <label className="text-xs text-slate-400 mb-1 block flex items-center gap-1">
                  <Pencil className="w-3 h-3" /> Titulo
                </label>
                <input
                  type="text"
                  value={slideEdits.title ?? slide.title ?? ''}
                  onChange={e => handleTextEdit(activeSlide, 'title', e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:border-amber-500 focus:outline-none"
                  data-testid={`approval-slide-title-${activeSlide}`}
                />
              </div>

              {/* Editable elements */}
              {slide.elements?.map((el, elIdx) => (
                <div key={elIdx}>
                  <label className="text-xs text-slate-400 mb-1 block flex items-center gap-1">
                    <FileText className="w-3 h-3" /> Conteudo {elIdx + 1}
                  </label>
                  <Textarea
                    value={
                      (slideEdits.elements?.find(e => e.index === elIdx)?.content) ??
                      (el.content || '')
                    }
                    onChange={e => handleElementEdit(activeSlide, elIdx, e.target.value)}
                    className="bg-slate-800 border-slate-700 text-sm text-white min-h-[80px] focus:border-amber-500"
                    data-testid={`approval-slide-element-${activeSlide}-${elIdx}`}
                  />
                </div>
              ))}

              {/* Editable narration script */}
              {slide.narrationScript && (
                <div>
                  <label className="text-xs text-slate-400 mb-1 block flex items-center gap-1">
                    <Volume2 className="w-3 h-3" /> Roteiro de Narracao
                  </label>
                  <Textarea
                    value={slideEdits.narrationScript ?? slide.narrationScript}
                    onChange={e => handleTextEdit(activeSlide, 'narrationScript', e.target.value)}
                    className="bg-slate-800 border-slate-700 text-sm text-white min-h-[60px] focus:border-amber-500"
                    data-testid={`approval-narration-${activeSlide}`}
                  />
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Slide navigation */}
        <div className="flex justify-between items-center">
          <Button variant="outline" size="sm" onClick={() => setActiveSlide(Math.max(0, activeSlide - 1))} disabled={activeSlide === 0}>
            <ArrowLeft className="w-4 h-4 mr-1" /> Anterior
          </Button>
          <span className="text-xs text-slate-400">{activeSlide + 1} / {slides.length}</span>
          <Button variant="outline" size="sm" onClick={() => setActiveSlide(Math.min(slides.length - 1, activeSlide + 1))} disabled={activeSlide >= slides.length - 1}>
            Proxima <ArrowRight className="w-4 h-4 ml-1" />
          </Button>
        </div>

        {/* Action buttons */}
        <div className="space-y-2 pt-2 border-t border-slate-800">
          {hasEdits && (
            <Button onClick={handleSaveEdits} disabled={saving} className="w-full bg-blue-600 hover:bg-blue-700" data-testid="save-storyboard-edits">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Save className="w-4 h-4 mr-1" />}
              Salvar Edicoes ({Object.keys(editedSlides).length} slides)
            </Button>
          )}

          {selectedSession.step === 'pending_approval' && (
            <div className="flex gap-2">
              <Button onClick={handleApprove} disabled={saving} className="flex-1 bg-emerald-600 hover:bg-emerald-700" data-testid="approve-storyboard-queue">
                {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <CheckCircle className="w-4 h-4 mr-1" />}
                Aprovar
              </Button>
              <Button onClick={() => setShowRejectDialog(true)} disabled={saving} variant="outline" className="flex-1 border-red-700 text-red-400 hover:bg-red-900/20" data-testid="reject-storyboard-queue">
                <XCircle className="w-4 h-4 mr-1" /> Devolver
              </Button>
            </div>
          )}
        </div>

        {/* Rejection dialog */}
        {showRejectDialog && (
          <Card className="bg-slate-900 border-red-800/40">
            <CardContent className="p-4 space-y-3">
              <p className="text-sm text-red-300">Motivo da devolucao (opcional):</p>
              <Textarea
                value={rejectionReason}
                onChange={e => setRejectionReason(e.target.value)}
                placeholder="Descreva o que precisa ser alterado..."
                className="bg-slate-800 border-slate-700 text-sm text-white"
                data-testid="rejection-reason-input"
              />
              <div className="flex gap-2">
                <Button onClick={handleReject} disabled={saving} className="bg-red-600 hover:bg-red-700" data-testid="confirm-reject">
                  {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
                  Confirmar Devolucao
                </Button>
                <Button variant="outline" onClick={() => { setShowRejectDialog(false); setRejectionReason(''); }}>
                  Cancelar
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    );
  }

  // Queue list view
  return (
    <div className="space-y-6" data-testid="approval-queue-panel">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-amber-400" />
          Fila de Aprovacao
        </h2>
        <Button variant="outline" size="sm" onClick={fetchQueue} disabled={loading} data-testid="refresh-queue">
          <RefreshCw className={`w-4 h-4 mr-1 ${loading ? 'animate-spin' : ''}`} /> Atualizar
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-amber-400" />
        </div>
      ) : queue.length === 0 ? (
        <Card className="bg-slate-900/50 border-slate-800">
          <CardContent className="p-8 text-center">
            <CheckCircle className="w-10 h-10 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-400">Nenhum storyboard pendente de aprovacao.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {queue.map(session => (
            <Card key={session.id} className={`bg-slate-900/50 border-slate-800 hover:border-amber-700/40 transition-colors ${session.step === 'approved' ? 'border-emerald-800/30' : ''}`}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge className={`text-[10px] ${session.step === 'pending_approval' ? 'bg-amber-600/20 text-amber-300' : 'bg-emerald-600/20 text-emerald-300'}`}>
                        {session.step === 'pending_approval' ? 'Pendente' : 'Aprovado'}
                      </Badge>
                      <span className="text-sm font-medium truncate">
                        {session.config?.title || session.storyboard?.title || 'Curso sem titulo'}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-slate-400">
                      <span className="flex items-center gap-1">
                        <User className="w-3 h-3" /> {session.userName || 'Desconhecido'}
                      </span>
                      {session.targetCompanyName && (
                        <span className="flex items-center gap-1 text-amber-400/70">
                          Empresa: {session.targetCompanyName}
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <BookOpen className="w-3 h-3" /> {session.storyboard?.slides?.length || 0} slides
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" /> {new Date(session.updatedAt).toLocaleDateString('pt-BR')}
                      </span>
                    </div>
                    {session.approvedByName && (
                      <p className="text-xs text-emerald-400/70 mt-1">
                        Aprovado por: {session.approvedByName}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2 shrink-0 ml-3">
                    {session.step === 'pending_approval' && (isAprovador || isSuperAdmin) && (
                      <Button size="sm" onClick={() => handleSelectSession(session)} data-testid={`review-session-${session.id}`}>
                        <Eye className="w-4 h-4 mr-1" /> Revisar
                      </Button>
                    )}
                    {session.step === 'approved' && isSuperAdmin && (
                      <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={() => handleResume(session)} data-testid={`resume-session-${session.id}`}>
                        <Play className="w-4 h-4 mr-1" /> Retomar
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
