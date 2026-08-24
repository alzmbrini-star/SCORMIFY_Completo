import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Brain, Gamepad2, Loader2, Search, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { authHeaders } from '../../contexts/AuthContext';
import { getApiUrl } from '../../utils/apiUrl';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../ui/dialog';
import { generateEducationalGameHtml } from './gameTemplates';

const API = getApiUrl();
const TYPES = [
  { id: 'penalty', icon: '⚽', name: 'Pênalti Educativo', text: 'Respostas corretas viram gols com torcida e partículas.' },
  { id: 'quiz_show', icon: '🎤', name: 'Quiz Show', text: 'Programa de TV com cronômetro, XP e multiplicadores.' },
  { id: 'memory', icon: '🧠', name: 'Memória Educativa', text: 'Associe cada pergunta à resposta correta.' },
  { id: 'hangman', icon: '🔤', name: 'Forca Inteligente', text: 'Descubra os termos usando as perguntas como dicas.' },
];

export default function EducationalGameDialog({ open, onOpenChange, onGameCreated, projectId }) {
  const [type, setType] = useState('penalty');
  const [title, setTitle] = useState('Desafio do Conhecimento');
  const [filters, setFilters] = useState({ subject: '', topic: '', difficulty: '' });
  const [facets, setFacets] = useState({});
  const [questions, setQuestions] = useState([]);
  const [selected, setSelected] = useState([]);
  const [count, setCount] = useState(5);
  const [config, setConfig] = useState({ lives: 3, time: 30, shuffle: true });
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState('');

  const load = useCallback(async () => {
    if (!open) return;
    setLoading(true);
    try {
      if (!projectId) throw new Error('Salve o projeto antes de consultar o banco de questões.');
      const p = new URLSearchParams({ projectId, pageSize: '200' });
      Object.entries(filters).forEach(([key, value]) => value && p.set(key, value));
      const response = await fetch(`${API}/api/game-questions/catalog?${p}`, { headers: authHeaders(), credentials: 'include' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Não foi possível consultar o banco de questões');
      setQuestions(data.items || []);
      setFacets(data.facets || {});
    } catch (error) { toast.error(error.message); }
    finally { setLoading(false); }
  }, [open, filters, projectId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setSelected((prev) => prev.filter((id) => questions.some((q) => q.id === id))); }, [questions]);

  const chosen = useMemo(() => {
    const explicit = questions.filter((q) => selected.includes(q.id));
    return (explicit.length ? explicit : questions).slice(0, count);
  }, [questions, selected, count]);

  const build = () => {
    if (chosen.length < (type === 'memory' ? 4 : 1)) {
      toast.error(type === 'memory' ? 'Selecione pelo menos 4 questões para o jogo da memória.' : 'Cadastre ou selecione questões para criar o jogo.');
      return '';
    }
    const html = generateEducationalGameHtml({ gameType: type, title, questions: chosen, config });
    setPreview(html);
    return html;
  };

  const add = () => {
    const html = preview || build();
    if (!html) return;
    onGameCreated({ type: 'html', x: 0, y: 0, width: 1920, height: 1080, htmlContent: html, gameType: type, interactiveType: 'game', gameConfig: { title, filters, ...config, questionIds: chosen.map((q) => q.id) } });
    onOpenChange(false);
  };

  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="max-w-6xl max-h-[92vh] overflow-y-auto bg-slate-950 border-slate-700 text-white">
      <DialogHeader><DialogTitle className="flex items-center gap-2 text-xl"><Gamepad2 className="text-cyan-400" /> Criar Jogo Educativo</DialogTitle><DialogDescription className="text-slate-400">Monte um minijogo premium usando o banco central de questões da empresa.</DialogDescription></DialogHeader>
      <div className="grid gap-5 lg:grid-cols-[1fr_1.25fr]">
        <div className="space-y-5">
          <div><label className="text-sm font-semibold">Modelo do jogo</label><div className="mt-2 grid grid-cols-2 gap-2">{TYPES.map((item) => <button key={item.id} type="button" onClick={() => { setType(item.id); setPreview(''); }} className={`rounded-xl border p-3 text-left transition ${type === item.id ? 'border-cyan-400 bg-cyan-500/15' : 'border-slate-700 bg-slate-900 hover:border-slate-500'}`}><span className="text-2xl">{item.icon}</span><strong className="ml-2 text-sm">{item.name}</strong><p className="mt-1 text-xs text-slate-400">{item.text}</p></button>)}</div></div>
          <div><label className="text-sm font-semibold">Título</label><Input value={title} onChange={(e) => setTitle(e.target.value)} className="mt-2 bg-slate-900 border-slate-700" /></div>
          <div><div className="mb-2 flex items-center gap-2 text-sm font-semibold"><Search className="h-4 w-4" /> Filtros do banco</div><div className="grid grid-cols-3 gap-2">{['subject','topic','difficulty'].map((field) => <select key={field} value={filters[field]} onChange={(e) => { setFilters((v) => ({ ...v, [field]: e.target.value })); setPreview(''); }} className="rounded-md border border-slate-700 bg-slate-900 px-2 py-2 text-xs"><option value="">{field === 'subject' ? 'Disciplina' : field === 'topic' ? 'Tema' : 'Dificuldade'}</option>{(facets[field] || []).map((value) => <option key={value}>{value}</option>)}</select>)}</div></div>
          <div className="grid grid-cols-3 gap-3"><label className="text-xs text-slate-400">Questões<Input type="number" min="1" max="12" value={count} onChange={(e) => { setCount(Number(e.target.value)); setPreview(''); }} className="mt-1 bg-slate-900 border-slate-700" /></label><label className="text-xs text-slate-400">Vidas<Input type="number" min="1" max="10" value={config.lives} onChange={(e) => setConfig((v) => ({ ...v, lives: Number(e.target.value) }))} className="mt-1 bg-slate-900 border-slate-700" /></label><label className="text-xs text-slate-400">Tempo/rodada<Input type="number" min="10" max="120" value={config.time} onChange={(e) => setConfig((v) => ({ ...v, time: Number(e.target.value) }))} className="mt-1 bg-slate-900 border-slate-700" /></label></div>
          <div><div className="mb-2 flex items-center justify-between"><span className="text-sm font-semibold">Questões disponíveis</span><span className="text-xs text-cyan-300">{selected.length ? `${selected.length} selecionadas` : `sorteio das primeiras ${count}`}</span></div><div className="max-h-52 space-y-1 overflow-y-auto rounded-xl border border-slate-800 p-2">{loading ? <div className="flex justify-center p-7"><Loader2 className="animate-spin" /></div> : questions.length ? questions.map((q) => <label key={q.id} className="flex cursor-pointer gap-2 rounded-lg p-2 text-xs hover:bg-white/5"><input type="checkbox" checked={selected.includes(q.id)} onChange={() => { setSelected((v) => v.includes(q.id) ? v.filter((id) => id !== q.id) : [...v, q.id]); setPreview(''); }} /><span><b>{q.question}</b><small className="block text-slate-500">{q.subject} · {q.topic} · {q.difficulty}</small></span></label>) : <p className="p-6 text-center text-sm text-slate-500">Nenhuma questão encontrada. Importe questões em Administração → Questões dos Jogos.</p>}</div></div>
        </div>
        <div className="space-y-3"><div className="flex items-center justify-between"><span className="flex items-center gap-2 text-sm font-semibold"><Brain className="h-4 w-4 text-violet-400" /> Pré-visualização</span><Button type="button" variant="outline" onClick={build} className="border-cyan-500/40"><Sparkles className="mr-2 h-4 w-4" /> Gerar prévia</Button></div><div className="aspect-video overflow-hidden rounded-xl border border-slate-700 bg-slate-900">{preview ? <iframe title="Prévia do jogo" srcDoc={preview} className="h-full w-full border-0" sandbox="allow-scripts" /> : <div className="grid h-full place-items-center text-sm text-slate-500">Configure o jogo e clique em Gerar prévia</div>}</div><p className="text-xs text-slate-500">As questões serão incorporadas ao jogo para funcionar também no HTML e no SCORM sem acesso ao banco.</p></div>
      </div>
      <DialogFooter><Button variant="ghost" onClick={() => onOpenChange(false)}>Cancelar</Button><Button onClick={add} disabled={!questions.length} className="bg-gradient-to-r from-cyan-500 to-violet-600"><Gamepad2 className="mr-2 h-4 w-4" /> Adicionar jogo ao slide</Button></DialogFooter>
    </DialogContent>
  </Dialog>;
}
