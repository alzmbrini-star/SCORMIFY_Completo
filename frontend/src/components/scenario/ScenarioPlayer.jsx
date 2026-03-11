import React, { useState, useCallback, useMemo } from 'react';
import { Button } from '../ui/button';
import { ScrollArea } from '../ui/scroll-area';
import {
  GitBranch, ChevronRight, RotateCcw, Trophy, AlertTriangle,
  CheckCircle, XCircle, Star, ArrowRight, User
} from 'lucide-react';

/**
 * ScenarioPlayer renders an interactive decision-tree scenario.
 * Props:
 *   - scenarioData: { title, description, context, characters, nodes, start_node_id }
 *   - onComplete: (result) => void  -- called when player reaches an ending
 */
export default function ScenarioPlayer({ scenarioData, onComplete }) {
  const [currentNodeId, setCurrentNodeId] = useState(scenarioData?.start_node_id || scenarioData?.nodes?.[0]?.id);
  const [history, setHistory] = useState([]);
  const [selectedChoice, setSelectedChoice] = useState(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [totalPoints, setTotalPoints] = useState(0);
  const [completed, setCompleted] = useState(false);
  const [finalNode, setFinalNode] = useState(null);

  const nodesMap = useMemo(() => {
    const map = {};
    (scenarioData?.nodes || []).forEach(n => { map[n.id] = n; });
    return map;
  }, [scenarioData]);

  const currentNode = nodesMap[currentNodeId];

  const handleChoiceSelect = useCallback((choice) => {
    setSelectedChoice(choice);
    setShowFeedback(true);
    setTotalPoints(prev => prev + (choice.points || 0));
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
    setTotalPoints(0);
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
    const endingColor = finalNode.ending_type === 'good' ? 'text-emerald-400' :
      finalNode.ending_type === 'bad' ? 'text-red-400' : 'text-amber-400';
    const EndingIcon = finalNode.ending_type === 'good' ? Trophy :
      finalNode.ending_type === 'bad' ? XCircle : AlertTriangle;

    return (
      <div className="w-full h-full flex flex-col bg-gradient-to-b from-slate-900 to-slate-800 rounded-lg overflow-hidden">
        <ScrollArea className="flex-1 p-4">
          <div className="flex flex-col items-center justify-center min-h-full text-center space-y-4 py-6">
            <EndingIcon className={`w-12 h-12 ${endingColor}`} />
            <h2 className={`text-xl font-bold ${endingColor}`}>{finalNode.title}</h2>
            <p className="text-slate-300 text-sm max-w-md leading-relaxed">{finalNode.narrative}</p>

            {finalNode.score != null && (
              <div className="flex items-center gap-2 bg-slate-700/50 px-4 py-2 rounded-full">
                <Star className="w-4 h-4 text-amber-400" />
                <span className="text-white font-semibold">Pontuação: {finalNode.score}/100</span>
              </div>
            )}

            <div className="text-xs text-slate-500 mt-2">
              Pontos acumulados nas decisões: {totalPoints}
            </div>

            <Button
              onClick={handleRestart}
              variant="outline"
              className="mt-4 border-cyan-500/50 text-cyan-400 hover:bg-cyan-500/10"
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
          <span className="text-xs font-medium text-slate-300 truncate max-w-[200px]">{scenarioData.title}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">
            Cena {history.length + 1}
          </span>
          <div className="flex items-center gap-1 text-xs text-amber-400">
            <Star className="w-3 h-3" />
            {totalPoints} pts
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1 p-4">
        {/* Character speaking */}
        {currentNode.character_speaking && (
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shrink-0">
              <User className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="text-xs font-medium text-cyan-300">{currentNode.character_speaking}</span>
          </div>
        )}

        {/* Scene title */}
        <h3 className="text-base font-semibold text-white mb-2">{currentNode.title}</h3>

        {/* Narrative */}
        <p className="text-sm text-slate-300 leading-relaxed mb-4 whitespace-pre-line">{currentNode.narrative}</p>

        {/* Choices */}
        {!showFeedback && currentNode.choices?.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-slate-400 mb-1">O que você faria?</p>
            {currentNode.choices.map((choice, idx) => (
              <button
                key={choice.id}
                onClick={() => handleChoiceSelect(choice)}
                className="w-full text-left px-3 py-2.5 rounded-lg border border-slate-600/50 bg-slate-800/50 hover:bg-slate-700/70 hover:border-cyan-500/40 transition-all text-sm text-slate-200 flex items-center gap-2 group"
                data-testid={`scenario-choice-${idx}`}
              >
                <span className="w-6 h-6 rounded-full bg-slate-700 group-hover:bg-cyan-600/30 flex items-center justify-center shrink-0 text-xs font-bold text-slate-400 group-hover:text-cyan-300 transition-colors">
                  {String.fromCharCode(65 + idx)}
                </span>
                <span className="flex-1">{choice.text}</span>
                <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 transition-colors" />
              </button>
            ))}
          </div>
        )}

        {/* Feedback */}
        {showFeedback && selectedChoice && (
          <div className="space-y-3 mt-2">
            <div className="px-3 py-2 rounded-lg bg-slate-700/40 border border-slate-600/40">
              <p className="text-xs font-medium text-slate-400 mb-1">Sua escolha:</p>
              <p className="text-sm text-white">{selectedChoice.text}</p>
            </div>

            <div className={`px-3 py-2.5 rounded-lg border ${selectedChoice.is_optimal ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-amber-500/10 border-amber-500/30'}`}>
              <div className="flex items-center gap-1.5 mb-1">
                {selectedChoice.is_optimal ? (
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                )}
                <span className={`text-xs font-medium ${selectedChoice.is_optimal ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {selectedChoice.is_optimal ? 'Excelente escolha!' : 'Considere outras perspectivas'}
                </span>
                {selectedChoice.points > 0 && (
                  <span className="ml-auto text-xs text-amber-300">+{selectedChoice.points} pts</span>
                )}
              </div>
              <p className="text-sm text-slate-300 leading-relaxed">{selectedChoice.feedback}</p>
            </div>

            <Button
              onClick={handleProceed}
              className="w-full bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white"
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
