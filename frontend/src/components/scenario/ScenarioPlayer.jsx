import React, { useState, useCallback, useMemo } from 'react';
import { Button } from '../ui/button';
import { ScrollArea } from '../ui/scroll-area';
import {
  GitBranch, ChevronRight, RotateCcw, Trophy, AlertTriangle,
  CheckCircle, XCircle, Star, ArrowRight, User
} from 'lucide-react';

/**
 * Format the LLM-generated scenario narrative into readable React nodes.
 * The model often emits walls of text with embedded dialogue (email replies,
 * quoted conversations). We split on blank lines and extract quoted blocks
 * into highlighted cards so dialogue pops visually.
 */
function ScenarioNarrative({ text, fontSize = 14 }) {
  const paragraphs = useMemo(() => {
    if (!text) return [];
    const t = String(text).replace(/\r\n/g, '\n').trim();
    let list = t.split(/\n{2,}/).map(p => p.trim()).filter(Boolean);
    // Single mega-paragraph: try to split around a long quoted chunk
    if (list.length === 1) {
      const m = list[0].match(/(['"\u2018\u2019\u201C\u201D])([^'"\u2018\u2019\u201C\u201D]{40,})\1/);
      if (m) {
        const before = list[0].slice(0, m.index).trim();
        const quote = m[2].trim();
        const after = list[0].slice(m.index + m[0].length).trim();
        list = [];
        if (before) list.push(before);
        list.push({ quoted: quote });
        if (after) list.push(after);
      }
    } else {
      list = list.map(p => {
        const f = p.charAt(0), l = p.charAt(p.length - 1);
        if (p.length > 30 && '"\u201C\u2018\''.includes(f) && '"\u201D\u2019\''.includes(l)) {
          return { quoted: p.slice(1, -1).trim() };
        }
        return p;
      });
    }
    return list;
  }, [text]);

  return (
    <div className="space-y-2">
      {paragraphs.map((p, i) => {
        if (typeof p === 'object' && p.quoted) {
          return (
            <div
              key={i}
              className="bg-indigo-500/10 border-l-[3px] border-indigo-500 pl-4 pr-3 py-3 rounded-r italic text-slate-300 leading-relaxed whitespace-pre-line"
              style={{ fontSize: `${fontSize * 0.85}px` }}
            >
              {p.quoted}
            </div>
          );
        }
        return (
          <p
            key={i}
            className="text-slate-300 leading-relaxed whitespace-pre-line"
            style={{ fontSize: `${fontSize * 0.875}px` }}
          >
            {p}
          </p>
        );
      })}
    </div>
  );
}

/**
 * ScenarioPlayer renders an interactive decision-tree scenario.
 * Props:
 *   - scenarioData: { title, description, context, characters, nodes, start_node_id, fontSize }
 *   - onComplete: (result) => void  -- called when player reaches an ending
 */
export default function ScenarioPlayer({ scenarioData, onComplete }) {
  const fontSize = scenarioData?.fontSize || 16;
  const scale = fontSize / 16; // 1.0 at 16px base
  const [currentNodeId, setCurrentNodeId] = useState(scenarioData?.start_node_id || scenarioData?.nodes?.[0]?.id);
  const [history, setHistory] = useState([]);
  const [selectedChoice, setSelectedChoice] = useState(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [finalNode, setFinalNode] = useState(null);

  const nodesMap = useMemo(() => {
    const map = {};
    (scenarioData?.nodes || []).forEach(n => { map[n.id] = n; });
    return map;
  }, [scenarioData]);

  const [optimalCount, setOptimalCount] = useState(0);
  const [totalDecisions, setTotalDecisions] = useState(0);

  const totalPoints = totalDecisions > 0 ? Math.round((optimalCount / totalDecisions) * 100) : 0;

  const currentNode = nodesMap[currentNodeId];

  const handleChoiceSelect = useCallback((choice) => {
    setSelectedChoice(choice);
    setShowFeedback(true);
    setTotalDecisions(prev => prev + 1);
    if (choice.is_optimal) setOptimalCount(prev => prev + 1);
  }, []);

  const handleProceed = useCallback(() => {
    if (!selectedChoice) return;

    const nextId = selectedChoice.next_node_id;
    setHistory(prev => [...prev, { nodeId: currentNodeId, choiceId: selectedChoice.id }]);
    setSelectedChoice(null);
    setShowFeedback(false);

    if (!nextId || !nodesMap[nextId]) {
      // No next node - treat current as ending
      setCompleted(true);
      setFinalNode(currentNode);
      onComplete?.({ score: totalPoints, history, node: currentNode });
      return;
    }

    const nextNode = nodesMap[nextId];
    setCurrentNodeId(nextId);

    if (nextNode.is_ending) {
      setCompleted(true);
      setFinalNode(nextNode);
      onComplete?.({ score: nextNode.score || totalPoints, history: [...history, { nodeId: currentNodeId, choiceId: selectedChoice.id }], node: nextNode });
    }
  }, [selectedChoice, currentNodeId, nodesMap, currentNode, history, totalPoints, onComplete]);

  const handleRestart = useCallback(() => {
    setCurrentNodeId(scenarioData?.start_node_id || scenarioData?.nodes?.[0]?.id);
    setHistory([]);
    setSelectedChoice(null);
    setShowFeedback(false);
    setOptimalCount(0);
    setTotalDecisions(0);
    setCompleted(false);
    setFinalNode(null);
  }, [scenarioData]);

  if (!scenarioData || !scenarioData.nodes?.length) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-slate-900/80 rounded-lg p-4">
        <p className="text-slate-400 text-sm">Nenhum cenário carregado</p>
      </div>
    );
  }

  // Ending screen
  if (completed && finalNode) {
    // Calculate score based on optimal decisions (5/5 ideal = 100%)
    const calculatedScore = totalDecisions > 0 
      ? Math.round((optimalCount / totalDecisions) * 100)
      : 0;
    const endingColor = calculatedScore >= 80 ? 'text-emerald-400' :
      calculatedScore >= 50 ? 'text-amber-400' : 'text-red-400';
    const EndingIcon = calculatedScore >= 80 ? Trophy :
      calculatedScore >= 50 ? AlertTriangle : XCircle;

    return (
      <div className="w-full h-full flex flex-col bg-gradient-to-b from-slate-900 to-slate-800 rounded-lg overflow-hidden">
        <ScrollArea className="flex-1 p-4">
          <div className="flex flex-col items-center justify-center min-h-full text-center space-y-4 py-6">
            <EndingIcon className={`${endingColor}`} style={{ width: 48 * scale, height: 48 * scale }} />
            <h2 className={`font-bold ${endingColor}`} style={{ fontSize: `${fontSize * 1.25}px` }}>{finalNode.title}</h2>
            <div className="max-w-md w-full">
              <ScenarioNarrative text={finalNode.narrative} fontSize={fontSize} />
            </div>

            {/* Dynamic score based on optimal decisions */}
            <div className="flex items-center gap-2 bg-slate-700/50 px-4 py-2 rounded-full">
              <Star className="w-4 h-4 text-amber-400" />
              <span className="text-white font-semibold" style={{ fontSize: `${fontSize}px` }}>Pontuação: {calculatedScore}%</span>
            </div>

            {/* Clear breakdown */}
            <div className="flex flex-col items-center gap-1" style={{ fontSize: `${fontSize * 0.75}px` }}>
              <span className="text-slate-400">
                Decisões ideais: {optimalCount} de {totalDecisions}
              </span>
            </div>

            <Button
              onClick={handleRestart}
              variant="outline"
              className="mt-4 border-cyan-500/50 text-cyan-400 hover:bg-cyan-500/10"
              style={{ fontSize: `${fontSize}px` }}
              data-testid="scenario-restart-btn"
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              Tentar Novamente
            </Button>
          </div>
        </ScrollArea>
      </div>
    );
  }

  if (!currentNode) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-slate-900/80 rounded-lg">
        <p className="text-slate-400 text-sm">Nó não encontrado</p>
      </div>
    );
  }

  // Active scene
  return (
    <div className="w-full h-full flex flex-col bg-gradient-to-b from-slate-900 to-slate-800 rounded-lg overflow-hidden" data-testid="scenario-player">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-slate-800/80 border-b border-slate-700/50">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-cyan-400" />
          <span className="font-medium text-slate-300 truncate max-w-[200px]" style={{ fontSize: `${fontSize * 0.75}px` }}>{scenarioData.title}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-slate-500" style={{ fontSize: `${fontSize * 0.75}px` }}>
            Cena {history.length + 1}
          </span>
          <div className="flex items-center gap-1 text-amber-400" style={{ fontSize: `${fontSize * 0.75}px` }}>
            <Star style={{ width: 12 * scale, height: 12 * scale }} />
            {totalPoints} pts
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1 p-4">
        {/* Character speaking */}
        {currentNode.character_speaking && (
          <div className="flex items-center gap-2 mb-3">
            <div className="rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shrink-0" style={{ width: 28 * scale, height: 28 * scale }}>
              <User style={{ width: 14 * scale, height: 14 * scale }} className="text-white" />
            </div>
            <span className="font-medium text-cyan-300" style={{ fontSize: `${fontSize * 0.75}px` }}>{currentNode.character_speaking}</span>
          </div>
        )}

        {/* Scene title */}
        <h3 className="font-semibold text-white mb-2" style={{ fontSize: `${fontSize}px` }}>{currentNode.title}</h3>

        {/* Narrative */}
        <div className="mb-4">
          <ScenarioNarrative text={currentNode.narrative} fontSize={fontSize} />
        </div>

        {/* Choices */}
        {!showFeedback && currentNode.choices?.length > 0 && (
          <div className="space-y-2">
            <p className="font-medium text-slate-400 mb-1" style={{ fontSize: `${fontSize * 0.75}px` }}>O que você faria?</p>
            {currentNode.choices.map((choice, idx) => (
              <button
                key={choice.id}
                onClick={() => handleChoiceSelect(choice)}
                className="w-full text-left px-3 py-2.5 rounded-lg border border-slate-600/50 bg-slate-800/50 hover:bg-slate-700/70 hover:border-cyan-500/40 transition-all text-slate-200 flex items-center gap-2 group"
                style={{ fontSize: `${fontSize * 0.875}px` }}
                data-testid={`scenario-choice-${idx}`}
              >
                <span className="rounded-full bg-slate-700 group-hover:bg-cyan-600/30 flex items-center justify-center shrink-0 font-bold text-slate-400 group-hover:text-cyan-300 transition-colors" style={{ width: 24 * scale, height: 24 * scale, fontSize: `${fontSize * 0.7}px` }}>
                  {String.fromCharCode(65 + idx)}
                </span>
                <span className="flex-1">{choice.text}</span>
                <ChevronRight style={{ width: 16 * scale, height: 16 * scale }} className="text-slate-500 group-hover:text-cyan-400 transition-colors" />
              </button>
            ))}
          </div>
        )}

        {/* Feedback */}
        {showFeedback && selectedChoice && (
          <div className="space-y-3 mt-2">
            <div className="px-3 py-2 rounded-lg bg-slate-700/40 border border-slate-600/40">
              <p className="font-medium text-slate-400 mb-1" style={{ fontSize: `${fontSize * 0.75}px` }}>Sua escolha:</p>
              <p className="text-white" style={{ fontSize: `${fontSize * 0.875}px` }}>{selectedChoice.text}</p>
            </div>

            <div className={`px-3 py-2.5 rounded-lg border ${selectedChoice.is_optimal ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-amber-500/10 border-amber-500/30'}`}>
              <div className="flex items-center gap-1.5 mb-1">
                {selectedChoice.is_optimal ? (
                  <CheckCircle style={{ width: 14 * scale, height: 14 * scale }} className="text-emerald-400" />
                ) : (
                  <AlertTriangle style={{ width: 14 * scale, height: 14 * scale }} className="text-amber-400" />
                )}
                <span className={`font-medium ${selectedChoice.is_optimal ? 'text-emerald-400' : 'text-amber-400'}`} style={{ fontSize: `${fontSize * 0.75}px` }}>
                  {selectedChoice.is_optimal ? 'Excelente escolha!' : 'Considere outras perspectivas'}
                </span>
                {selectedChoice.points > 0 && (
                  <span className="ml-auto text-amber-300" style={{ fontSize: `${fontSize * 0.75}px` }}>+{selectedChoice.points} pts</span>
                )}
              </div>
              <p className="text-slate-300 leading-relaxed" style={{ fontSize: `${fontSize * 0.875}px` }}>{selectedChoice.feedback}</p>
            </div>

            <Button
              onClick={handleProceed}
              className="w-full bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white"
              style={{ fontSize: `${fontSize}px` }}
              data-testid="scenario-proceed-btn"
            >
              Continuar
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
