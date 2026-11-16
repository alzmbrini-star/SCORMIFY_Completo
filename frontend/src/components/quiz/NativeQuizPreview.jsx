import React, {useEffect, useState} from 'react';
import axios from 'axios';
import QuizPlayer from './QuizPlayer';
import {getApiUrl} from '../../utils/apiUrl';
import {authHeaders} from '../../contexts/AuthContext';

// Read compatibility only: never rewrite the saved bank or learner grades.
export function previewQuestion(question) {
  return {...question, text: question.text || question.questionText || question.question || '',
    alternatives: (question.alternatives || []).map((alt, index) => ({...alt,
      id: alt.id || `${question.id}-alternative-${index}`,
      isCorrect: typeof alt.isCorrect === 'boolean' ? alt.isCorrect : alt.is_correct === true,
    }))};
}

export default function NativeQuizPreview({quizConfig, projectId}) {
  const [state, setState] = useState({loading:true, questions:[], error:false});
  useEffect(() => {
    let active = true;
    setState({loading:true, questions:[], error:false});
    const load = async () => {
      try {
        const ids = quizConfig?.questionIds || [];
        if (!ids.length) {
          if (active) setState({loading:false, questions:[], error:false});
          return;
        }
        const response = await axios.get(`${getApiUrl()}/api/questions`, {
          params:{project_id:projectId}, headers:authHeaders(), withCredentials:true,
        });
        const rows = Array.isArray(response.data) ? response.data : [];
        const questions = ids.map(id => rows.find(q => q.id === id)).filter(Boolean).map(previewQuestion);
        if (active) setState({loading:false, questions, error:questions.length !== ids.length});
      } catch {
        if (active) setState({loading:false, questions:[], error:true});
      }
    };
    load();
    return () => { active = false; };
  }, [quizConfig, projectId]);
  if (state.loading) return <div role="status">Carregando quiz...</div>;
  if (state.error) return <div role="alert">Não foi possível carregar todas as questões deste quiz. Feche e reabra a prévia.</div>;
  if (!state.questions.length) return <div role="status">Nenhuma questão disponível</div>;
  return <QuizPlayer key={`${projectId}:${quizConfig.questionIds.join(',')}`} quizConfig={quizConfig}
    questions={state.questions} embedded onComplete={()=>{}} transparentBackground={quizConfig.transparentBackground === true}/>;
}
