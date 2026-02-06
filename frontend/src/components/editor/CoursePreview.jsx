import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Button } from '../ui/button';
import { ScrollArea } from '../ui/scroll-area';
import { Slider } from '../ui/slider';
import {
  X,
  ChevronLeft,
  ChevronRight,
  Menu,
  Volume2,
  VolumeX,
  Play,
  Pause,
  SkipBack,
  Maximize,
  Minimize,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Helper to get full asset URL
const getAssetUrl = (src, projectId) => {
  if (!src) return '';
  if (src.startsWith('http')) return src;
  if (src.startsWith('/api/')) return `${API_URL}${src}`;
  // For relative paths stored in course data
  if (src.startsWith('assets/')) return `${API_URL}/api/projects/${projectId}/assets/${src.replace('assets/', '')}`;
  return src;
};

// Helper to process HTML content and fix image URLs
const processHtmlContent = (htmlContent, projectId) => {
  if (!htmlContent) return '<p>HTML</p>';
  
  // Fix image src URLs that start with /api/ or assets/
  let processed = htmlContent;
  
  // Replace /api/ URLs with full API_URL
  processed = processed.replace(/src="(\/api\/[^"]+)"/g, `src="${API_URL}$1"`);
  
  // Replace assets/ URLs
  processed = processed.replace(
    /src="(assets\/[^"]+)"/g, 
    (match, path) => `src="${API_URL}/api/projects/${projectId}/assets/${path.replace('assets/', '')}"`
  );
  
  return processed;
};

const CoursePreview = ({ course, projectId, onClose }) => {
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [showSidebar, setShowSidebar] = useState(false);
  const [volume, setVolume] = useState(0.7);
  const [isMuted, setIsMuted] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [slideScale, setSlideScale] = useState(1);
  
  const containerRef = useRef(null);
  const globalAudioRef = useRef(null);
  const slideAudiosRef = useRef([]);
  const timelineRef = useRef(null);
  const slideContainerRef = useRef(null);
  const slideWrapperRef = useRef(null);
  
  const slides = course?.slides || [];
  const currentSlide = slides[currentSlideIndex];
  const slideDuration = currentSlide?.duration || 10;
  
  // Calculate slide scale to fit in the available space
  const calculateScale = useCallback(() => {
    if (!slideWrapperRef.current || !currentSlide) return;
    
    const wrapper = slideWrapperRef.current;
    const wrapperRect = wrapper.getBoundingClientRect();
    const slideWidth = currentSlide.width || 960;
    const slideHeight = currentSlide.height || 540;
    
    // Account for padding
    const availableWidth = wrapperRect.width - 48; // p-6 = 24px * 2
    const availableHeight = wrapperRect.height - 48;
    
    const scaleX = availableWidth / slideWidth;
    const scaleY = availableHeight / slideHeight;
    const scale = Math.min(scaleX, scaleY, 1);
    
    setSlideScale(scale);
  }, [currentSlide]);
  
  // Update scale on mount, resize, and slide change
  useEffect(() => {
    calculateScale();
    window.addEventListener('resize', calculateScale);
    return () => window.removeEventListener('resize', calculateScale);
  }, [calculateScale, currentSlideIndex]);
  
  // Initialize global audio
  useEffect(() => {
    if (course?.globalAudio?.src) {
      const audioUrl = getAssetUrl(course.globalAudio.src, projectId);
      globalAudioRef.current = new Audio(audioUrl);
      globalAudioRef.current.loop = true;
      globalAudioRef.current.volume = (course.globalAudio.volume || 0.5) * volume;
    }
    
    return () => {
      if (globalAudioRef.current) {
        globalAudioRef.current.pause();
        globalAudioRef.current = null;
      }
    };
  }, [course?.globalAudio, projectId, volume]);
  
  // Update global audio volume when volume changes
  useEffect(() => {
    if (globalAudioRef.current) {
      globalAudioRef.current.volume = isMuted ? 0 : (course?.globalAudio?.volume || 0.5) * volume;
    }
    slideAudiosRef.current.forEach(audio => {
      if (audio) {
        audio.volume = isMuted ? 0 : volume;
      }
    });
  }, [volume, isMuted, course?.globalAudio?.volume]);
  
  // Handle slide change - stop audio and clear timeline
  const prevSlideIndexRef = useRef(currentSlideIndex);
  useEffect(() => {
    // Only run on actual slide change, not initial mount
    if (prevSlideIndexRef.current !== currentSlideIndex) {
      prevSlideIndexRef.current = currentSlideIndex;
      
      // Stop all slide audios
      slideAudiosRef.current.forEach(audio => {
        if (audio) {
          audio.pause();
          audio.currentTime = 0;
        }
      });
      slideAudiosRef.current = [];
      
      // Clear timeline interval
      if (timelineRef.current) {
        clearInterval(timelineRef.current);
        timelineRef.current = null;
      }
    }
  }, [currentSlideIndex]);

  // Initialize slide audios when slide changes
  useEffect(() => {
    if (currentSlide?.audio && currentSlide.audio.length > 0) {
      // Create audio elements for this slide
      const audios = currentSlide.audio.map(audioData => {
        if (audioData.src) {
          const audioUrl = getAssetUrl(audioData.src, projectId);
          const audio = new Audio(audioUrl);
          audio.volume = isMuted ? 0 : (audioData.volume || 1) * volume;
          audio.preload = 'auto';
          // Store the startTime for this audio
          audio.dataset.startTime = audioData.startTime || 0;
          return audio;
        }
        return null;
      }).filter(Boolean);
      
      slideAudiosRef.current = audios;
    }
    
    return () => {
      // Cleanup audios when slide changes
      slideAudiosRef.current.forEach(audio => {
        if (audio) {
          audio.pause();
          audio.src = '';
        }
      });
    };
  }, [currentSlide?.audio, projectId, volume, isMuted]);
  
  // Timeline playback
  useEffect(() => {
    if (isPlaying) {
      timelineRef.current = setInterval(() => {
        setCurrentTime(prev => {
          const newTime = prev + 0.1;
          if (newTime >= slideDuration) {
            // Auto-advance to next slide
            if (currentSlideIndex < slides.length - 1) {
              setCurrentSlideIndex(currentSlideIndex + 1);
            } else {
              setIsPlaying(false);
            }
            return 0;
          }
          return newTime;
        });
      }, 100);
    } else {
      if (timelineRef.current) {
        clearInterval(timelineRef.current);
        timelineRef.current = null;
      }
    }
    
    return () => {
      if (timelineRef.current) {
        clearInterval(timelineRef.current);
      }
    };
  }, [isPlaying, slideDuration, currentSlideIndex, slides.length]);
  
  // Start/stop global audio with playback
  useEffect(() => {
    if (globalAudioRef.current) {
      if (isPlaying) {
        globalAudioRef.current.play().catch(() => {});
      } else {
        globalAudioRef.current.pause();
      }
    }
  }, [isPlaying]);
  
  const goToSlide = (index) => {
    if (index >= 0 && index < slides.length) {
      setCurrentSlideIndex(index);
      setCurrentTime(0);
      setIsPlaying(false);
    }
  };
  
  const prevSlide = () => goToSlide(currentSlideIndex - 1);
  const nextSlide = () => goToSlide(currentSlideIndex + 1);
  
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };
  
  // Listen for fullscreen changes
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);
  
  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'ArrowLeft') {
        setCurrentSlideIndex(prev => Math.max(0, prev - 1));
        setCurrentTime(0);
        setIsPlaying(false);
      } else if (e.key === 'ArrowRight') {
        setCurrentSlideIndex(prev => Math.min(slides.length - 1, prev + 1));
        setCurrentTime(0);
        setIsPlaying(false);
      } else if (e.key === 'Escape') {
        onClose();
      } else if (e.key === ' ') {
        e.preventDefault();
        setIsPlaying(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [slides.length, onClose]);
  
  // Check if element should be visible based on timeline
  const isElementVisible = (element) => {
    const startTime = element.startTime != null ? element.startTime : 0;
    const endTime = element.endTime != null ? element.endTime : slideDuration;
    const isVisible = currentTime >= startTime - 0.05 && currentTime <= endTime + 0.05;
    return isVisible;
  };
  
  // Get animation styles for element based on current time
  const getElementAnimationStyle = (element) => {
    const startTime = element.startTime != null ? element.startTime : 0;
    const endTime = element.endTime != null ? element.endTime : slideDuration;
    const entranceAnim = element.animation?.entrance;
    const exitAnim = element.animation?.exit;
    const animDuration = 0.5; // Animation duration in seconds
    
    let animStyle = {};
    
    // Entrance animation (first 0.5s after startTime)
    if (entranceAnim && currentTime >= startTime && currentTime < startTime + animDuration) {
      const progress = (currentTime - startTime) / animDuration;
      switch (entranceAnim) {
        case 'fadeIn':
          animStyle = { opacity: progress };
          break;
        case 'slideFromLeft':
          animStyle = { transform: `translateX(${(1 - progress) * -100}%)`, opacity: progress };
          break;
        case 'slideFromRight':
          animStyle = { transform: `translateX(${(1 - progress) * 100}%)`, opacity: progress };
          break;
        case 'slideFromTop':
          animStyle = { transform: `translateY(${(1 - progress) * -100}%)`, opacity: progress };
          break;
        case 'slideFromBottom':
          animStyle = { transform: `translateY(${(1 - progress) * 100}%)`, opacity: progress };
          break;
        case 'zoomIn':
          animStyle = { transform: `scale(${0.5 + progress * 0.5})`, opacity: progress };
          break;
        default:
          break;
      }
    }
    // Exit animation (last 0.5s before endTime)
    else if (exitAnim && currentTime > endTime - animDuration && currentTime <= endTime) {
      const progress = (endTime - currentTime) / animDuration;
      switch (exitAnim) {
        case 'fadeOut':
          animStyle = { opacity: progress };
          break;
        case 'slideToLeft':
          animStyle = { transform: `translateX(${(1 - progress) * -100}%)`, opacity: progress };
          break;
        case 'slideToRight':
          animStyle = { transform: `translateX(${(1 - progress) * 100}%)`, opacity: progress };
          break;
        case 'slideToTop':
          animStyle = { transform: `translateY(${(1 - progress) * -100}%)`, opacity: progress };
          break;
        case 'slideToBottom':
          animStyle = { transform: `translateY(${(1 - progress) * 100}%)`, opacity: progress };
          break;
        case 'zoomOut':
          animStyle = { transform: `scale(${0.5 + progress * 0.5})`, opacity: progress };
          break;
        default:
          break;
      }
    }
    
    return animStyle;
  };
  
  if (!course || !currentSlide) {
    return (
      <div className="fixed inset-0 z-[9999] bg-black flex items-center justify-center">
        <p className="text-white">Nenhum curso para visualizar</p>
        <Button variant="ghost" className="absolute top-4 right-4 text-white" onClick={onClose}>
          <X className="w-6 h-6" />
        </Button>
      </div>
    );
  }
  
  const slideWidth = currentSlide.width || 960;
  const slideHeight = currentSlide.height || 540;
  
  return (
    <div 
      ref={containerRef}
      className="fixed inset-0 z-[9999] bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex flex-col"
      data-testid="course-preview"
    >
      {/* Header */}
      <div className="h-12 bg-black/50 backdrop-blur-sm flex items-center justify-between px-4 border-b border-white/10">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            className="text-white/80 hover:text-white hover:bg-white/10"
            onClick={() => setShowSidebar(!showSidebar)}
          >
            <Menu className="w-5 h-5" />
          </Button>
          <h2 className="text-white font-medium truncate max-w-[300px]">
            {course.metadata?.title || 'Visualização do Curso'}
          </h2>
        </div>
        
        <div className="flex items-center gap-2">
          <span className="text-white/60 text-sm">
            Slide {currentSlideIndex + 1} de {slides.length}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="text-white/80 hover:text-white hover:bg-white/10"
            onClick={toggleFullscreen}
          >
            {isFullscreen ? <Minimize className="w-5 h-5" /> : <Maximize className="w-5 h-5" />}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="text-white/80 hover:text-white hover:bg-white/10"
            onClick={onClose}
          >
            <X className="w-5 h-5" />
          </Button>
        </div>
      </div>
      
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <div className={`
          ${showSidebar ? 'w-64' : 'w-0'} 
          transition-all duration-300 overflow-hidden
          bg-black/30 backdrop-blur-sm border-r border-white/10
        `}>
          <ScrollArea className="h-full">
            <div className="p-3 space-y-2">
              <h3 className="text-white/60 text-xs uppercase tracking-wider mb-3">Navegação</h3>
              {slides.map((slide, index) => (
                <div
                  key={slide.id}
                  className={`
                    relative rounded-lg overflow-hidden cursor-pointer
                    transition-all duration-200 group
                    ${index === currentSlideIndex 
                      ? 'ring-2 ring-cyan-500 ring-offset-2 ring-offset-slate-900' 
                      : 'hover:ring-2 hover:ring-white/30'}
                  `}
                  onClick={() => goToSlide(index)}
                >
                  <div 
                    className="aspect-video bg-slate-800"
                    style={{
                      backgroundImage: slide.backgroundImage 
                        ? `url(${getAssetUrl(slide.backgroundImage, projectId)})` 
                        : undefined,
                      backgroundSize: 'cover',
                      backgroundPosition: 'center',
                      backgroundColor: slide.background || '#fff',
                    }}
                  />
                  <div className="absolute inset-0 flex items-end p-2 bg-gradient-to-t from-black/70 to-transparent">
                    <div className="flex items-center gap-2 w-full">
                      <span className={`
                        w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold
                        ${index === currentSlideIndex 
                          ? 'bg-cyan-500 text-white' 
                          : index < currentSlideIndex 
                            ? 'bg-green-500 text-white' 
                            : 'bg-white/20 text-white/60'}
                      `}>
                        {index < currentSlideIndex ? '✓' : index + 1}
                      </span>
                      <span className="text-white text-xs truncate flex-1">
                        {slide.title || `Slide ${index + 1}`}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
        
        {/* Main Slide Area */}
        <div 
          ref={slideWrapperRef}
          className="flex-1 flex items-center justify-center p-6 overflow-hidden"
        >
          <div 
            ref={slideContainerRef}
            className="relative shadow-2xl rounded-lg overflow-hidden"
            style={{
              width: currentSlide?.width || 960,
              height: currentSlide?.height || 540,
              backgroundColor: currentSlide?.background || '#FFFFFF',
              transform: `scale(${slideScale})`,
              transformOrigin: 'center center',
            }}
          >
            {/* Background Image */}
            {currentSlide?.backgroundImage && (
              <img
                src={getAssetUrl(currentSlide.backgroundImage, projectId)}
                alt=""
                className="absolute inset-0 w-full h-full object-contain"
                style={{ zIndex: 0 }}
              />
            )}
            
            {/* Elements - positioned absolutely within slide dimensions */}
            {currentSlide?.elements?.filter(el => el.visible !== false && isElementVisible(el)).map((element) => {
              const animStyle = getElementAnimationStyle(element);
              // Use element opacity only if > 0, otherwise default to 1
              const elementOpacity = element.style?.opacity != null && element.style.opacity > 0 
                ? element.style.opacity 
                : 1;
              return (
              <div
                key={element.id}
                className="absolute transition-all duration-100"
                style={{
                  left: `${element.x || 0}px`,
                  top: `${element.y || 0}px`,
                  width: `${element.width || 100}px`,
                  height: `${element.height || 100}px`,
                  zIndex: (element.zIndex || 0) + 1,
                  opacity: animStyle.opacity ?? elementOpacity,
                  transform: animStyle.transform || (element.rotation ? `rotate(${element.rotation}deg)` : undefined),
                }}
              >
                {/* Text */}
                {element.type === 'text' && (
                  <div
                    className="w-full h-full p-2 whitespace-pre-wrap overflow-hidden"
                    style={{
                      fontSize: element.style?.fontSize || 16,
                      fontFamily: element.style?.fontFamily || 'inherit',
                      fontWeight: element.style?.fontWeight || 'normal',
                      color: element.style?.fontColor || '#000000',
                      textAlign: element.style?.textAlign || 'left',
                      backgroundColor: 'rgba(255,255,255,0.9)',
                      borderRadius: 4,
                    }}
                  >
                    {element.content}
                  </div>
                )}
                
                {/* Image */}
                {element.type === 'image' && (
                  <img
                    src={getAssetUrl(element.src, projectId)}
                    alt=""
                    className="w-full h-full"
                    style={{ objectFit: element.objectFit || 'contain' }}
                  />
                )}
                
                {/* Shape */}
                {element.type === 'shape' && (
                  <div
                    className="w-full h-full flex items-center justify-center"
                    style={{
                      backgroundColor: element.style?.fill || '#7C3AED',
                      border: element.style?.stroke ? `2px solid ${element.style.stroke}` : 'none',
                      borderRadius: element.shapeType === 'ellipse' ? '50%' : 
                                    element.shapeType === 'rounded_rectangle' ? 8 : 0,
                    }}
                  >
                    {element.content && (
                      <span style={{ color: element.style?.fontColor || '#fff', fontSize: element.style?.fontSize || 14 }}>
                        {element.content}
                      </span>
                    )}
                  </div>
                )}
                
                {/* Video */}
                {element.type === 'video' && (
                  <div 
                    className="w-full h-full rounded overflow-hidden"
                    style={{ background: 'transparent' }}
                  >
                    {element.embedUrl ? (
                      <iframe
                        src={element.embedUrl}
                        className="w-full h-full border-0"
                        style={{ background: 'transparent' }}
                        allow="autoplay; fullscreen"
                        title="Video"
                      />
                    ) : element.src ? (
                      <video
                        src={getAssetUrl(element.src, projectId)}
                        autoPlay
                        loop
                        muted={isMuted}
                        playsInline
                        className="w-full h-full"
                        style={{ 
                          objectFit: 'contain', 
                          background: 'transparent',
                          backgroundColor: 'transparent'
                        }}
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-white">
                        Vídeo
                      </div>
                    )}
                  </div>
                )}
                
                {/* Button */}
                {element.type === 'button' && (
                  <a
                    href={element.buttonUrl}
                    target={element.openInNewTab ? '_blank' : '_self'}
                    rel="noopener noreferrer"
                    className="w-full h-full flex items-center justify-center"
                  >
                    <button
                      className={`px-6 py-3 rounded-lg font-semibold flex items-center gap-2 transition-all ${
                        element.buttonStyle === 'primary' 
                          ? 'bg-gradient-to-r from-purple-600 to-cyan-500 text-white' 
                          : element.buttonStyle === 'secondary'
                          ? 'bg-gray-600 text-white'
                          : element.buttonStyle === 'outline'
                          ? 'border-2 border-purple-600 text-purple-600 bg-transparent'
                          : 'bg-transparent text-gray-700'
                      }`}
                      style={{ fontSize: element.style?.fontSize || 16 }}
                    >
                      {element.buttonIcon && <span>{element.buttonIcon}</span>}
                      {element.buttonText || 'Clique aqui'}
                    </button>
                  </a>
                )}
                
                {/* HTML */}
                {element.type === 'html' && (
                  <iframe
                    srcDoc={`
                      <html>
                        <head>
                          <style>
                            body {
                              margin: 0;
                              padding: 8px;
                              background: transparent !important;
                              font-family: Arial, sans-serif;
                              color: #f1f5f9;
                              line-height: 1.6;
                              overflow: auto;
                            }
                            * { background: transparent !important; }
                            /* Thin scrollbar */
                            html, body {
                              scrollbar-width: thin;
                              scrollbar-color: rgba(100,116,139,0.3) transparent;
                            }
                            ::-webkit-scrollbar { width: 4px; height: 4px; }
                            ::-webkit-scrollbar-track { background: transparent; }
                            ::-webkit-scrollbar-thumb { background: rgba(100,116,139,0.3); border-radius: 4px; }
                            ::-webkit-scrollbar-thumb:hover { background: rgba(100,116,139,0.5); }
                            /* Remove borders/outlines from all images */
                            img { border: none !important; outline: none !important; box-shadow: none !important; }
                            /* Image float styles */
                            img.rtf-image-float-left, body img.rtf-image-float-left {
                              float: left !important;
                              clear: left !important;
                              max-width: 45% !important;
                              height: auto !important;
                              border-radius: 4px !important;
                              margin: 0 16px 12px 0 !important;
                              display: block !important;
                              border: none !important;
                              outline: none !important;
                            }
                            img.rtf-image-float-right, body img.rtf-image-float-right {
                              float: right !important;
                              clear: right !important;
                              max-width: 45% !important;
                              height: auto !important;
                              border-radius: 4px !important;
                              margin: 0 0 12px 16px !important;
                              display: block !important;
                              border: none !important;
                              outline: none !important;
                            }
                            img.rtf-image-center { display: inline-block !important; max-width: 80% !important; border: none !important; outline: none !important; }
                            img.rtf-image-inline { display: block !important; max-width: 100% !important; margin: 8px 0 !important; border: none !important; outline: none !important; }
                            img[style*="float: left"] { float: left !important; margin-right: 16px !important; margin-bottom: 12px !important; border: none !important; outline: none !important; }
                            img[style*="float: right"] { float: right !important; margin-left: 16px !important; margin-bottom: 12px !important; border: none !important; outline: none !important; }
                            body::after { content: ''; display: table; clear: both; }
                            p, div, span, ul, ol, li, h1, h2, h3, h4, h5, h6 { overflow: visible !important; }
                            /* Typography */
                            h1 { font-size: 1.5rem; font-weight: bold; margin-bottom: 1rem; }
                            h2 { font-size: 1.25rem; font-weight: bold; margin-bottom: 0.75rem; }
                            h3 { font-size: 1.1rem; font-weight: bold; margin-bottom: 0.5rem; }
                            p { margin-bottom: 0.75rem; }
                            ul { list-style: disc; padding-left: 1.5rem; margin-bottom: 0.75rem; }
                            ol { list-style: decimal; padding-left: 1.5rem; margin-bottom: 0.75rem; }
                            li { margin-bottom: 0.25rem; }
                            /* Table styles */
                            table {
                              border-collapse: separate;
                              border-spacing: 0;
                              width: 100%;
                              margin: 1rem 0;
                              border-radius: 8px;
                              overflow: hidden;
                              box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
                            }
                            th {
                              background: linear-gradient(to bottom, #475569, #334155);
                              border-bottom: 2px solid #22d3ee;
                              padding: 0.75rem 1rem;
                              font-weight: 600;
                              text-align: left;
                              color: #f1f5f9;
                            }
                            td {
                              border-bottom: 1px solid #334155;
                              padding: 0.75rem 1rem;
                              background: #1e293b;
                              color: #e2e8f0;
                            }
                            tr:nth-child(even) td { background: #1a2433; }
                          </style>
                        </head>
                        <body>${processHtmlContent(element.htmlContent, projectId)}</body>
                      </html>
                    `}
                    className="w-full h-full border-0 rounded"
                    style={{ background: 'transparent', overflow: 'auto' }}
                    sandbox="allow-scripts allow-same-origin"
                    title="HTML Content"
                  />
                )}
                
                {/* Flipbook */}
                {element.type === 'flipbook' && element.flipbookUrl && (
                  <iframe
                    src={element.flipbookUrl}
                    className="w-full h-full border-0 bg-gray-100 rounded"
                    allow="fullscreen"
                    title="Flipbook"
                  />
                )}
              </div>
            );
            })}
            
            {/* Annotations */}
            <svg
              className="absolute inset-0 pointer-events-none"
              style={{ width: '100%', height: '100%', zIndex: 100 }}
              viewBox={`0 0 ${slideWidth} ${slideHeight}`}
              preserveAspectRatio="none"
            >
              {currentSlide.annotations?.filter(a => {
                const startTime = a.startTime || 0;
                const endTime = a.endTime ?? slideDuration;
                return currentTime >= startTime && currentTime < endTime;
              }).map((annotation) => (
                <g key={annotation.id}>
                  {annotation.type === 'freehand' && annotation.points?.length > 0 && (
                    <path
                      d={`M ${annotation.points[0].x} ${annotation.points[0].y} ${annotation.points.slice(1).map(p => `L ${p.x} ${p.y}`).join(' ')}`}
                      stroke={annotation.color || '#EF4444'}
                      strokeWidth={annotation.strokeWidth || 3}
                      fill="none"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  )}
                  {annotation.type === 'arrow' && annotation.points?.length >= 2 && (
                    <>
                      <defs>
                        <marker
                          id={`preview-arrow-${annotation.id}`}
                          markerWidth="10"
                          markerHeight="7"
                          refX="9"
                          refY="3.5"
                          orient="auto"
                        >
                          <polygon points="0 0, 10 3.5, 0 7" fill={annotation.color || '#EF4444'} />
                        </marker>
                      </defs>
                      <line
                        x1={annotation.points[0].x}
                        y1={annotation.points[0].y}
                        x2={annotation.points[1].x}
                        y2={annotation.points[1].y}
                        stroke={annotation.color || '#EF4444'}
                        strokeWidth={annotation.strokeWidth || 3}
                        markerEnd={`url(#preview-arrow-${annotation.id})`}
                      />
                    </>
                  )}
                  {annotation.type === 'circle' && annotation.points?.length >= 2 && (() => {
                    const cx = (annotation.points[0].x + annotation.points[1].x) / 2;
                    const cy = (annotation.points[0].y + annotation.points[1].y) / 2;
                    const rx = Math.abs(annotation.points[1].x - annotation.points[0].x) / 2;
                    const ry = Math.abs(annotation.points[1].y - annotation.points[0].y) / 2;
                    return (
                      <ellipse
                        cx={cx}
                        cy={cy}
                        rx={rx}
                        ry={ry}
                        stroke={annotation.color || '#EF4444'}
                        strokeWidth={annotation.strokeWidth || 3}
                        fill="none"
                      />
                    );
                  })()}
                  {annotation.type === 'rectangle' && annotation.points?.length >= 2 && (
                    <rect
                      x={Math.min(annotation.points[0].x, annotation.points[1].x)}
                      y={Math.min(annotation.points[0].y, annotation.points[1].y)}
                      width={Math.abs(annotation.points[1].x - annotation.points[0].x)}
                      height={Math.abs(annotation.points[1].y - annotation.points[0].y)}
                      stroke={annotation.color || '#EF4444'}
                      strokeWidth={annotation.strokeWidth || 3}
                      fill="none"
                    />
                  )}
                </g>
              ))}
            </svg>
          </div>
        </div>
      </div>
      
      {/* Controls Bar */}
      <div className="h-20 bg-black/50 backdrop-blur-sm border-t border-white/10 flex flex-col">
        {/* Progress Bar */}
        <div className="h-1 bg-white/10 relative cursor-pointer" onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const x = e.clientX - rect.left;
          const percent = x / rect.width;
          setCurrentTime(percent * slideDuration);
        }}>
          <div 
            className="h-full bg-gradient-to-r from-purple-500 to-cyan-500 transition-all"
            style={{ width: `${(currentTime / slideDuration) * 100}%` }}
          />
        </div>
        
        <div className="flex-1 flex items-center justify-between px-6">
          {/* Left controls */}
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="text-white/80 hover:text-white hover:bg-white/10"
              onClick={() => { setCurrentTime(0); setIsPlaying(false); }}
            >
              <SkipBack className="w-5 h-5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="text-white/80 hover:text-white hover:bg-white/10 w-12 h-12"
              onClick={() => setIsPlaying(!isPlaying)}
            >
              {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6" />}
            </Button>
            <span className="text-white/60 text-sm font-mono min-w-[80px]">
              {currentTime.toFixed(1)}s / {slideDuration}s
            </span>
          </div>
          
          {/* Center - Navigation */}
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              className="border-white/20 text-white hover:bg-white/10"
              onClick={prevSlide}
              disabled={currentSlideIndex === 0}
            >
              <ChevronLeft className="w-4 h-4 mr-1" />
              Anterior
            </Button>
            <div className="flex items-center gap-2">
              {slides.map((_, index) => (
                <button
                  key={index}
                  className={`w-2.5 h-2.5 rounded-full transition-all ${
                    index === currentSlideIndex 
                      ? 'bg-cyan-500 scale-125' 
                      : 'bg-white/30 hover:bg-white/50'
                  }`}
                  onClick={() => goToSlide(index)}
                />
              ))}
            </div>
            <Button
              variant="outline"
              className="border-white/20 text-white hover:bg-white/10"
              onClick={nextSlide}
              disabled={currentSlideIndex === slides.length - 1}
            >
              Próximo
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
          
          {/* Right - Volume */}
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="text-white/80 hover:text-white hover:bg-white/10"
              onClick={() => setIsMuted(!isMuted)}
            >
              {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
            </Button>
            <Slider
              value={[isMuted ? 0 : volume * 100]}
              min={0}
              max={100}
              step={1}
              onValueChange={(v) => { setVolume(v[0] / 100); setIsMuted(false); }}
              className="w-24"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default CoursePreview;
