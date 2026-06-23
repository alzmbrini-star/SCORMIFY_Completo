import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Button } from '../ui/button';
import { ScrollArea } from '../ui/scroll-area';
import {
  Check,
  X,
  ChevronRight,
  ChevronLeft,
  RotateCcw,
  Trophy,
  AlertCircle,
  CheckCircle,
  XCircle,
} from 'lucide-react';

// Shuffle array helper
function shuffleArray(array) {
  const shuffled = [...array];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

export default function QuizPlayer({
  quizConfig,
  questions = [],
  onComplete,
  embedded = false,
  darkMode = true,
  transparentBackground = false,
}) {
  // Quiz state
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [answers, setAnswers] = useState([]);
  const [isComplete, setIsComplete] = useState(false);
  const [results, setResults] = useState(null);

  // Prepare questions (shuffle if configured)
  const preparedQuestions = useMemo(() => {
    let questionsToUse = questions;
    
    // Shuffle questions if enabled
    if (quizConfig?.shuffleQuestions) {
      questionsToUse = shuffleArray(questionsToUse);
    }
    
    // Limit to questionCount
    const count = quizConfig?.questionCount || questionsToUse.length;
    questionsToUse = questionsToUse.slice(0, count);
    
    // Shuffle alternatives if enabled
    if (quizConfig?.shuffleAlternatives) {
      questionsToUse = questionsToUse.map(q => ({
        ...q,
        alternatives: shuffleArray(q.alternatives || []),
      }));
    }
    
    return questionsToUse;
  }, [questions, quizConfig]);

  const currentQuestion = preparedQuestions[currentIndex];
  const totalQuestions = preparedQuestions.length;

  const handleSelectAnswer = (alternativeId) => {
    if (showFeedback) return;
    setSelectedAnswer(alternativeId);
  };

  const handleConfirmAnswer = () => {
    if (!selectedAnswer || !currentQuestion) return;

    const selectedAlt = currentQuestion.alternatives?.find(a => a.id === selectedAnswer);
    const isCorrect = selectedAlt?.isCorrect || false;

    const answerRecord = {
      questionId: currentQuestion.id,
      selectedAlternativeId: selectedAnswer,
      isCorrect,
    };

    setAnswers(prev => [...prev, answerRecord]);

    if (quizConfig?.showFeedback) {
      setShowFeedback(true);
    } else {
      // Auto-advance to next question
      moveToNext();
    }
  };

  const moveToNext = useCallback(() => {
    setShowFeedback(false);
    setSelectedAnswer(null);

    if (currentIndex < totalQuestions - 1) {
      setCurrentIndex(prev => prev + 1);
    } else {
      // Quiz complete - calculate results
      calculateResults();
    }
  }, [currentIndex, totalQuestions]); // eslint-disable-line react-hooks/exhaustive-deps

  const calculateResults = useCallback(() => {
    const updatedAnswers = [...answers];
    if (selectedAnswer && currentQuestion) {
      const selectedAlt = currentQuestion.alternatives?.find(a => a.id === selectedAnswer);
      updatedAnswers.push({
        questionId: currentQuestion.id,
        selectedAlternativeId: selectedAnswer,
        isCorrect: selectedAlt?.isCorrect || false,
      });
    }

    const correctCount = updatedAnswers.filter(a => a.isCorrect).length;
    const totalPoints = updatedAnswers.length;
    const percentage = totalPoints > 0 ? (correctCount / totalPoints) * 100 : 0;
    const score = percentage / 10; // Convert to 0-10 scale
    const passingScore = quizConfig?.passingScore || 60;
    const passed = percentage >= passingScore;

    const quizResults = {
      score: Math.round(score * 10) / 10,
      percentage: Math.round(percentage * 10) / 10,
      correctCount,
      totalQuestions: totalPoints,
      passed,
      answers: updatedAnswers,
    };

    setResults(quizResults);
    setIsComplete(true);

    // Call onComplete callback if provided
    if (onComplete) {
      onComplete(quizResults);
    }
  }, [answers, selectedAnswer, currentQuestion, quizConfig, onComplete]);

  const handleRestart = () => {
    setCurrentIndex(0);
    setSelectedAnswer(null);
    setShowFeedback(false);
    setAnswers([]);
    setIsComplete(false);
    setResults(null);
  };

  // Styles based on theme
  const useTransparent = transparentBackground || quizConfig?.transparentBackground === true;
  const bgColor = useTransparent ? 'bg-transparent' : (darkMode ? 'bg-slate-800' : 'bg-white');
  const textColor = darkMode ? 'text-white' : 'text-slate-900';
  const mutedColor = darkMode ? 'text-slate-400' : 'text-slate-500';
  const borderColor = darkMode ? 'border-slate-600' : 'border-slate-200';

  // Results screen
  if (isComplete && results) {
    return (
      <div className={`w-full h-full ${bgColor} ${textColor} flex flex-col items-center justify-center p-4 overflow-auto`}>
        <div className={`max-w-sm w-full ${darkMode ? 'bg-slate-700' : 'bg-slate-100'} rounded-xl p-5 text-center`}>
          {/* Score Icon */}
          <div className={`w-14 h-14 mx-auto mb-3 rounded-full flex items-center justify-center ${
            results.passed 
              ? 'bg-green-500/20' 
              : 'bg-red-500/20'
          }`}>
            {results.passed ? (
              <Trophy className="w-8 h-8 text-green-500" />
            ) : (
              <AlertCircle className="w-8 h-8 text-red-500" />
            )}
          </div>

          {/* Title */}
          <h2 className="text-xl font-bold mb-1">
            {results.passed ? 'Parabéns!' : 'Não foi dessa vez'}
          </h2>
          <p className={`text-sm ${mutedColor}`}>
            {results.passed 
              ? 'Você atingiu a nota mínima' 
              : 'Tente novamente para melhorar'}
          </p>

          {/* Score Display */}
          <div className="my-4">
            <div className="text-5xl font-bold" style={{
              color: results.passed ? '#22c55e' : '#ef4444'
            }}>
              {results.score}
            </div>
            <p className={`text-xs ${mutedColor}`}>de 10</p>
          </div>

          {/* Stats */}
          <div className={`grid grid-cols-2 gap-3 mb-4 p-3 rounded-lg ${darkMode ? 'bg-slate-800' : 'bg-white'}`}>
            <div>
              <p className="text-xl font-bold text-green-500">{results.correctCount}</p>
              <p className={`text-xs ${mutedColor}`}>Corretas</p>
            </div>
            <div>
              <p className="text-xl font-bold text-red-500">{results.totalQuestions - results.correctCount}</p>
              <p className={`text-xs ${mutedColor}`}>Incorretas</p>
            </div>
          </div>

          {/* Percentage Bar */}
          <div className="mb-4">
            <div className="flex justify-between text-xs mb-1">
              <span>Aproveitamento</span>
              <span>{results.percentage}%</span>
            </div>
            <div className={`h-2 rounded-full ${darkMode ? 'bg-slate-600' : 'bg-slate-200'}`}>
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  results.passed ? 'bg-green-500' : 'bg-red-500'
                }`}
                style={{ width: `${results.percentage}%` }}
              />
            </div>
            <p className={`text-xs mt-1 ${mutedColor}`}>
              Nota mínima: {quizConfig?.passingScore || 60}%
            </p>
          </div>

          {/* Restart Button */}
          <Button
            onClick={handleRestart}
            className="w-full gap-2"
            size="sm"
            variant={darkMode ? 'default' : 'outline'}
            data-testid="quiz-restart-btn"
          >
            <RotateCcw className="w-4 h-4" />
            Tentar Novamente
          </Button>
        </div>
      </div>
    );
  }

  // Question screen
  if (!currentQuestion) {
    return (
      <div className={`w-full h-full ${bgColor} ${textColor} flex items-center justify-center`}>
        <p>Nenhuma questão disponível</p>
      </div>
    );
  }

  const correctAlt = currentQuestion.alternatives?.find(a => a.isCorrect);
  const selectedAlt = currentQuestion.alternatives?.find(a => a.id === selectedAnswer);

  return (
    <div className={`w-full h-full ${bgColor} ${textColor} flex flex-col`} data-testid="quiz-player">
      {/* Progress Header */}
      <div className={`px-4 py-3 border-b ${borderColor}`}>
        <div className="flex justify-between items-center mb-1.5">
          <span className="font-medium text-sm">{quizConfig?.title || 'Quiz'}</span>
          <span className={`text-sm ${mutedColor}`}>
            Questão {currentIndex + 1} de {totalQuestions}
          </span>
        </div>
        <div className={`h-1.5 rounded-full ${darkMode ? 'bg-slate-700' : 'bg-slate-200'}`}>
          <div
            className="h-full rounded-full bg-cyan-500 transition-all duration-300"
            style={{ width: `${((currentIndex + 1) / totalQuestions) * 100}%` }}
          />
        </div>
      </div>

      {/* Question Content */}
      <div className="flex-1 px-4 py-4 overflow-auto">
        {/* Question Type Badge */}
        <div className="mb-3">
          <span className={`px-2 py-0.5 text-xs rounded-full ${
            currentQuestion.type === 'true_false'
              ? 'bg-purple-500/20 text-purple-400'
              : 'bg-cyan-500/20 text-cyan-400'
          }`}>
            {currentQuestion.type === 'true_false' ? 'Verdadeiro ou Falso' : 'Múltipla Escolha'}
          </span>
        </div>

        {/* Question Text */}
        <h3 
          className="font-semibold mb-4"
          style={{ fontSize: `${(quizConfig?.fontSize || 16) * 1.125}px` }}
        >
          {currentQuestion.text}
        </h3>

        {/* Alternatives */}
        <div className="space-y-2">
          {currentQuestion.alternatives?.map((alt, idx) => {
            const isSelected = selectedAnswer === alt.id;
            const isCorrectAlt = alt.isCorrect;
            
            let altStyles = `px-3 py-2.5 rounded-lg border-2 cursor-pointer transition-all ${borderColor}`;
            
            if (showFeedback) {
              if (isCorrectAlt) {
                altStyles = `px-3 py-2.5 rounded-lg border-2 bg-green-500/20 border-green-500 ${textColor}`;
              } else if (isSelected && !isCorrectAlt) {
                altStyles = `px-3 py-2.5 rounded-lg border-2 bg-red-500/20 border-red-500 ${textColor}`;
              } else {
                altStyles = `px-3 py-2.5 rounded-lg border-2 ${borderColor} opacity-50`;
              }
            } else if (isSelected) {
              altStyles = `px-3 py-2.5 rounded-lg border-2 border-cyan-500 bg-cyan-500/10 ${textColor}`;
            } else {
              altStyles = `px-3 py-2.5 rounded-lg border-2 ${borderColor} hover:border-cyan-500/50 ${textColor}`;
            }

            return (
              <button
                key={alt.id || idx}
                className={altStyles}
                onClick={() => handleSelectAnswer(alt.id)}
                disabled={showFeedback}
                data-testid={`quiz-alt-${idx}`}
              >
                <div className="flex items-center gap-2.5">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                    showFeedback && isCorrectAlt ? 'bg-green-500 text-white' :
                    showFeedback && isSelected && !isCorrectAlt ? 'bg-red-500 text-white' :
                    isSelected ? 'bg-cyan-500 text-white' :
                    darkMode ? 'bg-slate-600' : 'bg-slate-200'
                  }`}>
                    {showFeedback && isCorrectAlt && <Check className="w-3.5 h-3.5" />}
                    {showFeedback && isSelected && !isCorrectAlt && <X className="w-3.5 h-3.5" />}
                    {!showFeedback && String.fromCharCode(65 + idx)}
                  </div>
                  <span 
                    className="flex-1 text-left"
                    style={{ fontSize: `${quizConfig?.fontSize || 16}px` }}
                  >
                    {alt.text}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Feedback / Explanation */}
        {showFeedback && (
          <div className={`mt-4 p-3 rounded-lg ${
            selectedAlt?.isCorrect 
              ? 'bg-green-500/10 border border-green-500/30' 
              : 'bg-red-500/10 border border-red-500/30'
          }`}>
            <div className="flex items-center gap-2 mb-1">
              {selectedAlt?.isCorrect ? (
                <CheckCircle className="w-4 h-4 text-green-500" />
              ) : (
                <XCircle className="w-4 h-4 text-red-500" />
              )}
              <span className={`font-semibold text-sm ${selectedAlt?.isCorrect ? 'text-green-500' : 'text-red-500'}`}>
                {selectedAlt?.isCorrect ? 'Correto!' : 'Incorreto'}
              </span>
            </div>
            {currentQuestion.explanation && (
              <p className={`text-sm ${mutedColor}`}>{currentQuestion.explanation}</p>
            )}
            {!selectedAlt?.isCorrect && correctAlt && (
              <p className={`mt-1 text-sm ${mutedColor}`}>
                Resposta correta: <span className="text-green-400 font-medium">{correctAlt.text}</span>
              </p>
            )}
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className={`p-3 border-t ${borderColor}`}>
        <div className="flex justify-between items-center">
          <Button
            variant="ghost"
            size="sm"
            disabled={currentIndex === 0 || showFeedback}
            onClick={() => {
              if (currentIndex > 0 && !showFeedback) {
                setCurrentIndex(prev => prev - 1);
                setSelectedAnswer(answers[currentIndex - 1]?.selectedAlternativeId || null);
              }
            }}
            data-testid="quiz-prev-btn"
          >
            <ChevronLeft className="w-4 h-4 mr-1" />
            Anterior
          </Button>

          {showFeedback ? (
            <Button
              onClick={moveToNext}
              className="gap-2"
              data-testid="quiz-next-btn"
            >
              {currentIndex < totalQuestions - 1 ? (
                <>
                  Próxima
                  <ChevronRight className="w-4 h-4" />
                </>
              ) : (
                <>
                  Ver Resultado
                  <Trophy className="w-4 h-4" />
                </>
              )}
            </Button>
          ) : (
            <Button
              onClick={handleConfirmAnswer}
              disabled={!selectedAnswer}
              className="gap-2"
              data-testid="quiz-confirm-btn"
            >
              Confirmar
              <Check className="w-4 h-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
