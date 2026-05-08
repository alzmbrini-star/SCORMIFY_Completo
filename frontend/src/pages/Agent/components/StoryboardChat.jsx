import React, { useState, useRef, useEffect, useCallback } from 'react';
import { getApiUrl } from '../../../utils/apiUrl';
import { authHeaders } from '../../../contexts/AuthContext';
import { Button } from '../../../components/ui/button';
import { Textarea } from '../../../components/ui/textarea';
import { ScrollArea } from '../../../components/ui/scroll-area';
import { Badge } from '../../../components/ui/badge';
import { toast } from 'sonner';
import { Loader2, Send, Sparkles, User as UserIcon, CheckCheck } from 'lucide-react';

const API = getApiUrl();

/**
 * Conversational chat for the Storyboard review step.
 * Lets the user issue natural-language edits ("reescreva a narracao do slide 3
 * em tom mais informal", "adicione um slide sobre exemplos", "remova o slide
 * final"). The backend interprets via LLM and applies structured ops.
 */
export default function StoryboardChat({ sessionId, onStoryboardUpdate }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  // Autoscroll to bottom on new message
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [messages]);

  const suggestions = [
    'Reescreva a narracao do slide 1 em tom mais informal',
    'Adicione um slide de exemplos praticos depois do slide 2',
    'Torne o titulo do slide final mais impactante',
    'Remova o ultimo slide',
  ];

  const send = useCallback(async (text) => {
    const msg = (text || input || '').trim();
    if (!msg || sending || !sessionId) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: msg, at: Date.now() }]);
    setSending(true);
    try {
      // History = prior turns (trimmed to keep context lean)
      const history = messages.slice(-6).map(m => ({ role: m.role, content: m.content }));
      const res = await fetch(`${API}/api/agent/sessions/${sessionId}/storyboard-chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        credentials: 'include',
        body: JSON.stringify({ message: msg, history }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Erro ${res.status}`);
      }
      const data = await res.json();
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.reply || '',
        ops: data.ops || [],
        at: Date.now(),
      }]);
      if (data.ops && data.ops.length > 0) {
        toast.success(`${data.ops.length} alteracao(oes) aplicada(s)!`);
        // Refresh parent storyboard so UI reflects edits
        if (onStoryboardUpdate) onStoryboardUpdate(data.storyboard);
      }
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Erro: ${e.message || 'falha ao processar'}`,
        error: true,
        at: Date.now(),
      }]);
    }
    setSending(false);
  }, [input, sending, sessionId, messages, onStoryboardUpdate]);

  return (
    <div className="flex flex-col h-full" data-testid="storyboard-chat">
      {/* Header */}
      <div className="px-3 py-2 border-b border-slate-800 flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-violet-400" />
        <span className="text-sm font-semibold text-white">Chat com Agente IA</span>
        <Badge className="bg-violet-900/30 text-violet-300 text-[9px] ml-auto">Storyboard</Badge>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1" ref={scrollRef}>
        <div className="p-3 space-y-3">
          {messages.length === 0 ? (
            <div className="space-y-3">
              <p className="text-xs text-slate-400 leading-relaxed">
                Peca alteracoes no storyboard em linguagem natural. Sugestoes:
              </p>
              <div className="space-y-1.5">
                {suggestions.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => send(s)}
                    className="w-full text-left text-[11px] bg-slate-800/50 hover:bg-violet-900/20 border border-slate-700 hover:border-violet-600/40 rounded px-2.5 py-1.5 text-slate-300 transition-colors"
                    data-testid={`storyboard-chat-suggestion-${i}`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, i) => (
              <div
                key={i}
                className={`flex gap-2 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                data-testid={`storyboard-chat-msg-${i}`}
              >
                {m.role === 'assistant' && (
                  <div className="w-6 h-6 rounded-full bg-violet-900/40 flex items-center justify-center shrink-0">
                    <Sparkles className="w-3 h-3 text-violet-300" />
                  </div>
                )}
                <div className={`max-w-[85%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-cyan-900/30 text-cyan-100 border border-cyan-700/30'
                    : m.error
                      ? 'bg-rose-900/30 text-rose-200 border border-rose-700/30'
                      : 'bg-slate-800/60 text-slate-200 border border-slate-700'
                }`}>
                  <div className="whitespace-pre-wrap">{m.content}</div>
                  {m.ops && m.ops.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-slate-700/50 flex items-center gap-1.5 text-[10px] text-emerald-300">
                      <CheckCheck className="w-3 h-3" />
                      {m.ops.length} operacao(oes) aplicada(s)
                    </div>
                  )}
                </div>
                {m.role === 'user' && (
                  <div className="w-6 h-6 rounded-full bg-cyan-900/40 flex items-center justify-center shrink-0">
                    <UserIcon className="w-3 h-3 text-cyan-300" />
                  </div>
                )}
              </div>
            ))
          )}
          {sending && (
            <div className="flex items-center gap-2 text-xs text-violet-300 pl-8">
              <Loader2 className="w-3 h-3 animate-spin" /> Pensando...
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="p-3 border-t border-slate-800 bg-slate-900/50">
        <div className="flex gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="Ex: reescreva o slide 2 em tom informal..."
            rows={2}
            disabled={sending}
            className="flex-1 text-xs bg-slate-950 border-slate-700 text-slate-100 resize-none"
            data-testid="storyboard-chat-input"
          />
          <Button
            onClick={() => send()}
            disabled={sending || !input.trim()}
            size="sm"
            className="bg-violet-600 hover:bg-violet-700 self-end h-9"
            data-testid="storyboard-chat-send"
          >
            {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
          </Button>
        </div>
        <p className="text-[9px] text-slate-500 mt-1.5">
          Enter envia, Shift+Enter quebra linha. Indices de slide sao 1-based na fala (voce diz "slide 3").
        </p>
      </div>
    </div>
  );
}
