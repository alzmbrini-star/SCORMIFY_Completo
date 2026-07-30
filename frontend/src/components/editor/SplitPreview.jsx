import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { Button } from '../ui/button';
import { ScrollArea } from '../ui/scroll-area';
import {
  ChevronLeft,
  ChevronRight,
  Play,
  Pause,
  SkipBack,
  Maximize,
  X,
  Volume2,
  VolumeX,
  Menu,
  Check,
  Trophy,
  AlertCircle,
  RotateCcw,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import QuizPlayer from '../quiz/QuizPlayer';
import ScenarioPlayer from '../scenario/ScenarioPlayer';
import { sanitizeHtmlForDisplay, getRtfContentStyles, wrapInteractiveFullbleed } from '../../utils/htmlUtils';

import { getApiUrl } from '../../utils/apiUrl';
const API_URL = getApiUrl();

const getAssetUrl = (src, projectId) => {
  if (!src) return '';
  if (src.startsWith('http')) {
    const assetMatch = src.match(/https?:\/\/[^/]+\/api\/projects\/([^/]+)\/assets\/(.+)/);
    if (assetMatch) return `${API_URL}/api/projects/${assetMatch[1]}/assets/${assetMatch[2]}`;
    return src;
  }
  if (src.startsWith('/api/')) return `${API_URL}${src}`;
  if (src.startsWith('assets/')) return `${API_URL}/api/projects/${projectId}/assets/${src.replace('assets/', '')}`;
  return src;
};

const processHtmlContent = (htmlContent, projectId) => {
  if (!htmlContent || typeof htmlContent !== 'string') return '<p>HTML</p>';
  let processed = htmlContent;
  processed = processed.replace(/src="(https?:\/\/[^"]+\/api\/assets\/[^"]+)"/g, (match, url) => {
    const m = url.match(/https?:\/\/[^/]+\/api\/assets\/(.+)/);
    return m ? `src="${API_URL}/api/assets/${m[1]}"` : match;
  });
  processed = processed.replace(/src="(https?:\/\/[^"]+\/api\/projects\/[^"]+\/assets\/[^"]+)"/g, (match, url) => {
    const m = url.match(/https?:\/\/[^/]+\/api\/projects\/([^/]+)\/assets\/(.+)/);
    return m ? `src="${API_URL}/api/projects/${m[1]}/assets/${m[2]}"` : match;
  });
  processed = processed.replace(/src="(\/api\/assets\/[^"]+)"/g, `src="${API_URL}$1"`);
  processed = processed.replace(/src="(\/api\/projects\/[^"]+)"/g, `src="${API_URL}$1"`);
  processed = processed.replace(/src="(assets\/[^"]+)"/g, (match, path) => `src="${API_URL}/api/projects/${projectId}/assets/${path.replace('assets/', '')}"`);
  processed = processed.replace(/--tw-[^;:]+:[^;]*;?\s*/g, '');
  processed = processed.replace(/outline-style:\s*dashed\s*;?\s*/g, '');
  processed = processed.replace(/style="\s*;?\s*"/g, '');
  return processed;
};

// Inline Quiz Player for split preview
const QuizPreviewPlayer = ({ quizConfig, projectId }) => {
  const [questions, setQuestions] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [score, setScore] = useState(0);
  const [isFinished, setIsFinished] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadQuestions = async () => {
      try {
        const ids = quizConfig.questionIds || [];
        if (ids.length === 0) { setLoading(false); return; }
        const resp = await axios.get(`${API_URL}/api/questions`, { params: { project_id: projectId } });
        let qs = (resp.data || []).filter(q => ids.includes(q.id));
        if (quizConfig.shuffleQuestions) qs = qs.sort(() => Math.random() - 0.5);
        if (quizConfig.questionCount && quizConfig.questionCount < qs.length) qs = qs.slice(0, quizConfig.questionCount);
        setQuestions(qs);
      } catch { }
      setLoading(false);
    };
    loadQuestions();
  }, [quizConfig, projectId]);

  if (loading) return <div className="flex items-center justify-center h-full text-xs text-white/60">Carregando quiz...</div>;
  if (questions.length === 0) return <div className="flex items-center justify-center h-full text-xs text-white/60">Nenhuma questão</div>;

  if (isFinished) {
    const finalScore = ((score / questions.length) * 10).toFixed(1);
    const passed = parseFloat(finalScore) >= (quizConfig.passingScore || 7);
    return (
      <div className="flex flex-col items-center justify-center h-full p-3 text-center">
        <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 ${passed ? 'bg-green-500/20' : 'bg-red-500/20'}`}>
          {passed ? <Trophy className="w-5 h-5 text-green-400" /> : <AlertCircle className="w-5 h-5 text-red-400" />}
        </div>
        <p className="text-lg font-bold text-white">{finalScore}</p>
        <p className="text-xs text-white/60 mb-2">{passed ? 'Aprovado!' : 'Tente novamente'}</p>
        <Button size="sm" variant="outline" className="text-xs border-white/20 text-white" onClick={() => { setCurrentQuestion(0); setScore(0); setSelectedAnswer(null); setShowFeedback(false); setIsFinished(false); }}>
          <RotateCcw className="w-3 h-3 mr-1" /> Refazer
        </Button>
      </div>
    );
  }

  const q = questions[currentQuestion];
  const handleAnswer = (altIndex) => {
    if (showFeedback) return;
    setSelectedAnswer(altIndex);
    setShowFeedback(true);
    if (q.alternatives[altIndex]?.is_correct) setScore(s => s + 1);
  };

  const handleNext = () => {
    if (currentQuestion < questions.length - 1) {
      setCurrentQuestion(c => c + 1);
      setSelectedAnswer(null);
      setShowFeedback(false);
    } else {
      setIsFinished(true);
    }
  };

  return (
    <div className="flex flex-col h-full p-2 text-white overflow-auto" style={{ scrollbarWidth: 'thin' }}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] text-white/50 uppercase tracking-wider">{q.type === 'true_false' ? 'V/F' : 'Quiz'}</span>
        <span className="text-[10px] text-white/50">{currentQuestion + 1}/{questions.length}</span>
      </div>
      <div className="w-full h-0.5 bg-white/10 mb-2 rounded-full"><div className="h-full bg-cyan-500 rounded-full transition-all" style={{ width: `${((currentQuestion + 1) / questions.length) * 100}%` }} /></div>
      <p className="text-xs font-medium mb-2 leading-relaxed">{q.question}</p>
      <div className="space-y-1.5 flex-1">
        {q.alternatives?.map((alt, i) => (
          <button key={i} onClick={() => handleAnswer(i)} className={`w-full text-left text-[11px] p-2 rounded-md border transition-all ${
            showFeedback ? (alt.is_correct ? 'border-green-500 bg-green-500/20' : selectedAnswer === i ? 'border-red-500 bg-red-500/20' : 'border-white/10 opacity-50')
            : selectedAnswer === i ? 'border-cyan-500 bg-cyan-500/10' : 'border-white/10 hover:border-white/30'
          }`}>
            <span className="flex items-center gap-1.5">
              {showFeedback && alt.is_correct && <CheckCircle className="w-3 h-3 text-green-400 shrink-0" />}
              {showFeedback && !alt.is_correct && selectedAnswer === i && <XCircle className="w-3 h-3 text-red-400 shrink-0" />}
              {alt.text}
            </span>
          </button>
        ))}
      </div>
      {showFeedback && (
        <Button size="sm" className="mt-2 w-full text-xs h-7" onClick={handleNext}>
          {currentQuestion < questions.length - 1 ? 'Próxima' : 'Ver Resultado'}
        </Button>
      )}
    </div>
  );
};

const SplitPreview = ({ course, projectId, currentSlideIndex, onSlideChange, onExpandFullscreen, onClose }) => {
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [slideScale, setSlideScale] = useState(1);
  const [showMiniSidebar, setShowMiniSidebar] = useState(false);

  const slideWrapperRef = useRef(null);
  const timelineRef = useRef(null);
  const globalAudioRef = useRef(null);
  const slideAudiosRef = useRef([]);

  const slides = course?.slides || [];
  const currentSlide = slides[currentSlideIndex];
  const slideDuration = currentSlide?.duration || 10;
  const slideWidth = currentSlide?.width || 960;
  const slideHeight = currentSlide?.height || 540;

  // Calculate scale to fit panel
  const calculateScale = useCallback(() => {
    if (!slideWrapperRef.current || !currentSlide) return;
    const wrapper = slideWrapperRef.current;
    const rect = wrapper.getBoundingClientRect();
    const availW = rect.width - 8;
    const availH = rect.height - 8;
    const scaleX = availW / (currentSlide.width || 960);
    const scaleY = availH / (currentSlide.height || 540);
    setSlideScale(Math.min(scaleX, scaleY, 1));
  }, [currentSlide]);

  useEffect(() => {
    calculateScale();
    window.addEventListener('resize', calculateScale);
    return () => window.removeEventListener('resize', calculateScale);
  }, [calculateScale, currentSlideIndex]);

  // Recalculate when mini sidebar toggles
  useEffect(() => {
    const t = setTimeout(calculateScale, 350);
    return () => clearTimeout(t);
  }, [showMiniSidebar, calculateScale]);

  // Global audio
  useEffect(() => {
    if (course?.globalAudio?.src) {
      const url = getAssetUrl(course.globalAudio.src, projectId);
      globalAudioRef.current = new Audio(url);
      globalAudioRef.current.loop = true;
      globalAudioRef.current.volume = (course.globalAudio.volume || 0.5) * 0.7;
    }
    return () => { if (globalAudioRef.current) { globalAudioRef.current.pause(); globalAudioRef.current = null; } };
  }, [course?.globalAudio, projectId]);

  // Reset timeline on slide change
  useEffect(() => {
    setCurrentTime(0);
    setIsPlaying(false);
    slideAudiosRef.current.forEach(a => { if (a) { a.pause(); a.currentTime = 0; } });
    slideAudiosRef.current = [];
    if (timelineRef.current) { clearInterval(timelineRef.current); timelineRef.current = null; }
  }, [currentSlideIndex]);

  // Timeline playback
  useEffect(() => {
    if (isPlaying) {
      timelineRef.current = setInterval(() => {
        setCurrentTime(prev => {
          const next = prev + 0.1;
          if (next >= slideDuration) {
            if (currentSlideIndex < slides.length - 1) onSlideChange(currentSlideIndex + 1);
            else setIsPlaying(false);
            return 0;
          }
          return next;
        });
      }, 100);
    } else {
      if (timelineRef.current) { clearInterval(timelineRef.current); timelineRef.current = null; }
    }
    return () => { if (timelineRef.current) clearInterval(timelineRef.current); };
  }, [isPlaying, slideDuration, currentSlideIndex, slides.length, onSlideChange]);

  // Element visibility check based on timeline
  const isElementVisible = (el) => {
    const start = el.startTime || 0;
    const end = el.endTime ?? slideDuration;
    return currentTime >= start && currentTime < end;
  };

  const prevSlide = () => { if (currentSlideIndex > 0) onSlideChange(currentSlideIndex - 1); };
  const nextSlide = () => { if (currentSlideIndex < slides.length - 1) onSlideChange(currentSlideIndex + 1); };

  if (!course || !currentSlide) {
    return (
      <div className="h-full flex items-center justify-center bg-slate-900/50">
        <p className="text-sm text-muted-foreground">Nenhum curso para visualizar</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900" data-testid="split-preview">
      {/* Header */}
      <div className="h-10 flex items-center justify-between px-3 border-b border-white/10 shrink-0">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" className="h-6 w-6 text-white/60 hover:text-white hover:bg-white/10" onClick={() => setShowMiniSidebar(!showMiniSidebar)}>
            <Menu className="w-3.5 h-3.5" />
          </Button>
          <span className="text-xs font-medium text-white/80">Preview</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-white/50 mr-1">{currentSlideIndex + 1}/{slides.length}</span>
          <Button variant="ghost" size="icon" className="h-6 w-6 text-white/60 hover:text-white hover:bg-white/10" onClick={onExpandFullscreen} data-testid="expand-preview-btn">
            <Maximize className="w-3.5 h-3.5" />
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6 text-white/60 hover:text-white hover:bg-white/10" onClick={onClose} data-testid="close-split-preview-btn">
            <X className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Mini sidebar */}
        {showMiniSidebar && (
          <div className="w-28 border-r border-white/10 bg-black/20 shrink-0">
            <ScrollArea className="h-full">
              <div className="p-1.5 space-y-1.5">
                {slides.map((slide, index) => (
                  <div
                    key={slide.id}
                    className={`relative rounded cursor-pointer overflow-hidden transition-all ${
                      index === currentSlideIndex ? 'ring-1.5 ring-cyan-500' : 'hover:ring-1 hover:ring-white/30 opacity-70'
                    }`}
                    style={{ aspectRatio: `${slide.width || 960}/${slide.height || 540}` }}
                    onClick={() => onSlideChange(index)}
                    data-testid={`split-preview-slide-${index}`}
                  >
                    {slide.backgroundImage ? (
                      <img src={getAssetUrl(slide.backgroundImage, projectId)} alt="" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full" style={{ backgroundColor: slide.background || '#fff' }} />
                    )}
                    <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-[8px] text-white/80 text-center py-0.5">
                      {index + 1}
                    </div>
                    {index < currentSlideIndex && (
                      <div className="absolute top-0.5 right-0.5 w-3 h-3 bg-green-500 rounded-full flex items-center justify-center">
                        <Check className="w-2 h-2 text-white" />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}

        {/* Slide area */}
        <div ref={slideWrapperRef} className="flex-1 flex items-center justify-center p-1 overflow-hidden">
          <div style={{
            width: `${slideWidth * slideScale}px`,
            height: `${slideHeight * slideScale}px`,
            flexShrink: 0,
            overflow: 'hidden',
            borderRadius: '0.375rem',
            boxShadow: '0 20px 25px -5px rgba(0,0,0,0.3)',
          }}>
            <div
              className="relative"
              style={{
                width: slideWidth,
                height: slideHeight,
                backgroundColor: currentSlide.background || '#FFFFFF',
                transform: `scale(${slideScale})`,
                transformOrigin: 'top left',
              }}
            >
            {/* Background */}
            {currentSlide.backgroundImage && (
              <img src={getAssetUrl(currentSlide.backgroundImage, projectId)} alt="" className="absolute inset-0 w-full h-full" style={{ zIndex: 0, objectFit: 'fill', opacity: currentSlide.backgroundImageOpacity != null ? currentSlide.backgroundImageOpacity : 1 }} />
            )}

            {/* Elements */}
            {currentSlide.elements?.filter(el => el.visible !== false && isElementVisible(el)).map((element) => {
              const elOpacity = element.style?.opacity != null && element.style.opacity > 0 ? element.style.opacity : 1;
              const isFullscreen = element.objectFit === 'cover' && element.width >= slideWidth * 0.95 && element.height >= slideHeight * 0.95;
              return (
                <div key={element.id} className="absolute" style={{
                  left: `${element.x || 0}px`, top: `${element.y || 0}px`,
                  width: `${element.width || 100}px`, height: `${element.height || 100}px`,
                  zIndex: (element.zIndex || 0) + 1, opacity: elOpacity,
                  transform: element.rotation ? `rotate(${element.rotation}deg)` : undefined,
                }}>
                  {element.type === 'text' && (
                    <div className="w-full h-full p-2 whitespace-pre-wrap overflow-hidden" style={{
                      fontSize: element.style?.fontSize || 16, fontFamily: element.style?.fontFamily || 'inherit',
                      fontWeight: element.style?.fontWeight || 'normal', color: element.style?.fontColor || '#000000',
                      textAlign: element.style?.textAlign || 'left',
                      backgroundColor: element.style?.transparentBackground ? 'transparent' : (element.style?.textBackgroundColor || element.style?.backgroundColor || 'rgba(255,255,255,0.9)'),
                      padding: element.style?.padding,
                      borderRadius: element.style?.borderRadius || 4,
                      textShadow: element.style?.textShadow,
                    }}>
                      {element.content}
                    </div>
                  )}
                  {element.type === 'image' && (
                    <img src={getAssetUrl(element.src || element.imageUrl, projectId)} alt="" style={{ width: '100%', height: '100%', objectFit: element.objectFit || 'contain', display: 'block' }} />
                  )}
                  {element.type === 'shape' && (
                    <div className="w-full h-full flex items-center justify-center" style={{
                      backgroundColor: element.style?.fill || '#7C3AED',
                      border: element.style?.stroke ? `2px solid ${element.style.stroke}` : 'none',
                      borderRadius: element.shapeType === 'ellipse' ? '50%' : element.shapeType === 'rounded_rectangle' ? 8 : 0,
                    }}>
                      {element.content && <span style={{ color: element.style?.fontColor || '#fff', fontSize: element.style?.fontSize || 14 }}>{element.content}</span>}
                    </div>
                  )}
                  {element.type === 'video' && (
                    <div className="w-full h-full rounded overflow-hidden" style={{ background: 'transparent' }}>
                      {element.embedUrl ? (
                        <iframe src={getAssetUrl(element.embedUrl, projectId)} className="w-full h-full border-0" style={{ background: 'transparent' }} allow="accelerometer; gyroscope; autoplay; encrypted-media; picture-in-picture; fullscreen" allowFullScreen loading="lazy" referrerPolicy="strict-origin-when-cross-origin" title="Video" />
                      ) : element.src ? (
                        <video src={getAssetUrl(element.src, projectId)} autoPlay loop muted playsInline className="w-full h-full" style={{ objectFit: element.objectFit || 'contain', background: 'transparent' }} />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-white/40 text-xs">Video</div>
                      )}
                    </div>
                  )}
                  {element.type === 'button' && (
                    <div className="w-full h-full flex items-center justify-center">
                      <button className={`px-4 py-2 rounded-lg font-semibold text-sm flex items-center gap-1.5 ${
                        element.buttonStyle === 'primary' ? 'bg-gradient-to-r from-purple-600 to-cyan-500 text-white'
                        : element.buttonStyle === 'secondary' ? 'bg-gray-600 text-white'
                        : element.buttonStyle === 'outline' ? 'border-2 border-purple-600 text-purple-400 bg-transparent'
                        : 'bg-transparent text-gray-400'
                      }`} style={{ fontSize: element.style?.fontSize || 14 }}>
                        {element.buttonIcon && <span>{element.buttonIcon}</span>}
                        {element.buttonText || 'Clique aqui'}
                      </button>
                    </div>
                  )}
                  {element.type === 'html' && (
                    <iframe
                      srcDoc={(() => {
                        const raw = processHtmlContent(element.htmlContent, projectId);
                        const isFullDoc = /<!doctype\s+html|<html[\s>]/i.test(raw);
                        if (isFullDoc) return wrapInteractiveFullbleed(raw, element.htmlDisplayMode || 'page');
                        return `<html><head><style>
                        ${getRtfContentStyles({ textColor: '#f1f5f9', backgroundColor: 'transparent' })}
                        body { padding: ${isFullscreen ? '0' : '8px'}; overflow: ${isFullscreen ? 'hidden' : 'auto'}; }
                        html, body { background: transparent !important; }
                        html, body { scrollbar-width: none; -ms-overflow-style: none; }
                        ::-webkit-scrollbar { display: none; }
                        table { border-collapse: separate; border-spacing: 0; border-radius: 8px; overflow: hidden; }
                        th { background: linear-gradient(to bottom, #475569, #334155); border-bottom: 2px solid #22d3ee; padding: 0.5rem; color: #f1f5f9; }
                        td { border-bottom: 1px solid #334155; padding: 0.5rem; background: #1e293b; color: #e2e8f0; }
                        tr:nth-child(even) td { background: #1a2433; }
                        a { color: #22d3ee; }
                      </style></head><body>${raw}</body></html>`;
                      })()}
                      className="w-full h-full border-0 rounded"
                      style={{ background: 'transparent', scrollbarWidth: 'none' }}
                      sandbox="allow-scripts"
                      title="HTML Content"
                    />
                  )}
                  {element.type === 'flipbook' && element.pdfDisplay === 'pages' && element.pdfPages?.length > 0 ? (
                    <div className="w-full h-full overflow-auto" style={{ background: 'transparent' }}>
                      {element.pdfPages.map((p, i) => (
                        <img key={i} src={getAssetUrl(p, projectId)} alt={`Página ${i + 1}`} className="w-full h-auto block" style={{ marginBottom: 8, borderRadius: 6 }} />
                      ))}
                    </div>
                  ) : element.type === 'flipbook' && element.flipbookUrl ? (
                    <iframe src={getAssetUrl(element.flipbookUrl, projectId) + (element.pdfDisplay === 'clean' ? '#toolbar=0&navpanes=0&scrollbar=0' : '')} className="w-full h-full border-0 bg-gray-100 rounded" allow="fullscreen" title="Flipbook" />
                  ) : null}
                  {element.type === 'quiz' && element.quizConfig && (
                    <div className="w-full h-full">
                      <QuizPreviewPlayer quizConfig={element.quizConfig} projectId={projectId} />
                    </div>
                  )}
                  {element.type === 'scenario' && element.scenarioData && (
                    <div className="w-full h-full">
                      <ScenarioPlayer scenarioData={element.scenarioData} />
                    </div>
                  )}
                </div>
              );
            })}

            {/* Annotations */}
            <svg className="absolute inset-0 pointer-events-none" style={{ width: '100%', height: '100%', zIndex: 100 }} viewBox={`0 0 ${slideWidth} ${slideHeight}`} preserveAspectRatio="none">
              {currentSlide.annotations?.filter(a => {
                const s = a.startTime || 0; const e = a.endTime ?? slideDuration;
                return currentTime >= s && currentTime < e;
              }).map((ann) => (
                <g key={ann.id}>
                  {ann.type === 'freehand' && ann.points?.length > 0 && (
                    <path d={`M ${ann.points[0].x} ${ann.points[0].y} ${ann.points.slice(1).map(p => `L ${p.x} ${p.y}`).join(' ')}`}
                      stroke={ann.color || '#EF4444'} strokeWidth={ann.strokeWidth || 3} fill="none" strokeLinecap="round" strokeLinejoin="round" />
                  )}
                  {ann.type === 'arrow' && ann.points?.length >= 2 && (
                    <>
                      <defs>
                        <marker id={`sp-arrow-${ann.id}`} markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                          <polygon points="0 0, 10 3.5, 0 7" fill={ann.color || '#EF4444'} />
                        </marker>
                      </defs>
                      <line x1={ann.points[0].x} y1={ann.points[0].y} x2={ann.points[1].x} y2={ann.points[1].y}
                        stroke={ann.color || '#EF4444'} strokeWidth={ann.strokeWidth || 3} markerEnd={`url(#sp-arrow-${ann.id})`} />
                    </>
                  )}
                  {ann.type === 'circle' && ann.points?.length >= 2 && (() => {
                    const cx = (ann.points[0].x + ann.points[1].x) / 2;
                    const cy = (ann.points[0].y + ann.points[1].y) / 2;
                    const rx = Math.abs(ann.points[1].x - ann.points[0].x) / 2;
                    const ry = Math.abs(ann.points[1].y - ann.points[0].y) / 2;
                    return <ellipse cx={cx} cy={cy} rx={rx} ry={ry} stroke={ann.color || '#EF4444'} strokeWidth={ann.strokeWidth || 3} fill="none" />;
                  })()}
                  {ann.type === 'rectangle' && ann.points?.length >= 2 && (
                    <rect x={Math.min(ann.points[0].x, ann.points[1].x)} y={Math.min(ann.points[0].y, ann.points[1].y)}
                      width={Math.abs(ann.points[1].x - ann.points[0].x)} height={Math.abs(ann.points[1].y - ann.points[0].y)}
                      stroke={ann.color || '#EF4444'} strokeWidth={ann.strokeWidth || 3} fill="none" />
                  )}
                </g>
              ))}
            </svg>
          </div>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="shrink-0 border-t border-white/10 bg-black/30">
        {/* Timeline progress */}
        <div className="h-0.5 bg-white/10 cursor-pointer" onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          setCurrentTime((e.clientX - rect.left) / rect.width * slideDuration);
        }}>
          <div className="h-full bg-gradient-to-r from-purple-500 to-cyan-500 transition-all" style={{ width: `${(currentTime / slideDuration) * 100}%` }} />
        </div>
        <div className="flex items-center justify-between px-2 py-1.5">
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" className="h-6 w-6 text-white/60 hover:text-white hover:bg-white/10" onClick={() => { setCurrentTime(0); setIsPlaying(false); }}>
              <SkipBack className="w-3 h-3" />
            </Button>
            <Button variant="ghost" size="icon" className="h-7 w-7 text-white/60 hover:text-white hover:bg-white/10" onClick={() => setIsPlaying(!isPlaying)} data-testid="split-preview-play-btn">
              {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            </Button>
            <span className="text-[10px] text-white/40 font-mono ml-1">{currentTime.toFixed(1)}s</span>
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" className="h-6 w-6 text-white/60 hover:text-white hover:bg-white/10" onClick={prevSlide} disabled={currentSlideIndex === 0} data-testid="split-preview-prev-btn">
              <ChevronLeft className="w-3.5 h-3.5" />
            </Button>
            <div className="flex gap-0.5">
              {slides.length <= 12 ? slides.map((_, i) => (
                <button key={i} className={`w-1.5 h-1.5 rounded-full transition-all ${i === currentSlideIndex ? 'bg-cyan-500 scale-125' : 'bg-white/25 hover:bg-white/40'}`} onClick={() => onSlideChange(i)} />
              )) : (
                <span className="text-[10px] text-white/50">{currentSlideIndex + 1}/{slides.length}</span>
              )}
            </div>
            <Button variant="ghost" size="icon" className="h-6 w-6 text-white/60 hover:text-white hover:bg-white/10" onClick={nextSlide} disabled={currentSlideIndex === slides.length - 1} data-testid="split-preview-next-btn">
              <ChevronRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SplitPreview;
