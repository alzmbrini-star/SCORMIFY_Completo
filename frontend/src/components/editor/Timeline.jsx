import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Button } from '../ui/button';
import { Slider } from '../ui/slider';
import { Input } from '../ui/input';
import {
  Play,
  Pause,
  SkipBack,
  Volume2,
  VolumeX,
  GripHorizontal,
  Clock,
  Type,
  Image,
  Square,
  Video,
  Music,
  Circle,
  ArrowRight,
  Pencil,
} from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '../ui/tooltip';

const Timeline = ({ 
  slide, 
  onUpdateSlide, 
  onUpdateElement,
  onUpdateAnnotation,
  currentTime: externalTime,
  isPlaying: externalIsPlaying,
  onTimeChange,
  onPlayPause,
}) => {
  const [localTime, setLocalTime] = useState(0);
  const [localIsPlaying, setLocalIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isDraggingClip, setIsDraggingClip] = useState(null);
  const [dragType, setDragType] = useState(null); // 'move', 'start', 'end'
  const [dragItemType, setDragItemType] = useState(null); // 'element' or 'annotation'
  const [dragStartX, setDragStartX] = useState(0);
  const [dragStartTime, setDragStartTime] = useState({ start: 0, end: 0 });
  const timelineRef = useRef(null);
  const tracksRef = useRef(null);
  const animationRef = useRef(null);
  const audioRefs = useRef({});

  // Use external time/play state if provided, otherwise use local state
  const currentTime = externalTime !== undefined ? externalTime : localTime;
  const isPlaying = externalIsPlaying !== undefined ? externalIsPlaying : localIsPlaying;
  const setCurrentTime = onTimeChange || setLocalTime;
  const setIsPlaying = onPlayPause || setLocalIsPlaying;

  const duration = slide?.duration || 10;
  const elements = slide?.elements || [];
  const annotations = slide?.annotations || [];
  const audioList = slide?.audio || [];

  // Animation loop
  useEffect(() => {
    if (isPlaying) {
      const startTime = Date.now() - currentTime * 1000;
      
      const animate = () => {
        const elapsed = (Date.now() - startTime) / 1000;
        if (elapsed >= duration) {
          setCurrentTime(0);
          setIsPlaying(false);
        } else {
          setCurrentTime(elapsed);
          animationRef.current = requestAnimationFrame(animate);
        }
      };
      
      animationRef.current = requestAnimationFrame(animate);
    }
    
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isPlaying, duration]);

  // Handle audio playback
  useEffect(() => {
    if (!isMuted && audioList.length > 0) {
      audioList.forEach((audio) => {
        const audioElement = audioRefs.current[audio.id];
        if (!audioElement) return;

        const audioStart = audio.startTime || 0;
        const audioDuration = audio.duration || duration;
        const audioEnd = audioStart + audioDuration;

        if (isPlaying && currentTime >= audioStart && currentTime < audioEnd) {
          if (audioElement.paused) {
            audioElement.currentTime = currentTime - audioStart;
            audioElement.volume = audio.volume || 1;
            audioElement.play().catch(() => {});
          }
        } else {
          if (!audioElement.paused) {
            audioElement.pause();
          }
        }
      });
    } else {
      // Pause all audio when muted or not playing
      Object.values(audioRefs.current).forEach(audio => {
        if (audio && !audio.paused) {
          audio.pause();
        }
      });
    }
  }, [isPlaying, currentTime, isMuted, audioList, duration]);

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      Object.values(audioRefs.current).forEach(audio => {
        if (audio) {
          audio.pause();
          audio.src = '';
        }
      });
    };
  }, []);

  const handlePlayPause = () => {
    setIsPlaying(!isPlaying);
  };

  const handleReset = () => {
    setCurrentTime(0);
    setIsPlaying(false);
  };

  const handleSeek = (value) => {
    setCurrentTime(value[0]);
    if (isPlaying) {
      setIsPlaying(false);
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 10);
    return `${mins}:${secs.toString().padStart(2, '0')}.${ms}`;
  };

  const getTimeFromX = useCallback((clientX) => {
    if (!tracksRef.current) return 0;
    const rect = tracksRef.current.getBoundingClientRect();
    const x = clientX - rect.left;
    const percentage = Math.max(0, Math.min(1, x / rect.width));
    return percentage * duration;
  }, [duration]);

  const handleTrackClick = (e) => {
    if (isDraggingClip) return;
    const newTime = getTimeFromX(e.clientX);
    setCurrentTime(Math.max(0, Math.min(duration, newTime)));
    if (isPlaying) {
      setIsPlaying(false);
    }
  };

  // Clip dragging handlers
  const handleClipMouseDown = (e, element, type) => {
    e.stopPropagation();
    e.preventDefault();
    setIsDraggingClip(element.id);
    setDragType(type);
    setDragStartX(e.clientX);
    setDragStartTime({
      start: element.startTime || 0,
      end: element.endTime ?? duration,
    });
  };

  const handleMouseMove = useCallback((e) => {
    if (!isDraggingClip || !tracksRef.current) return;

    const rect = tracksRef.current.getBoundingClientRect();
    const deltaX = e.clientX - dragStartX;
    const deltaTime = (deltaX / rect.width) * duration;

    const element = elements.find(el => el.id === isDraggingClip);
    if (!element) return;

    const minDuration = 0.5; // Minimum clip duration

    let newStartTime = dragStartTime.start;
    let newEndTime = dragStartTime.end;

    if (dragType === 'move') {
      const clipDuration = dragStartTime.end - dragStartTime.start;
      newStartTime = Math.max(0, Math.min(duration - clipDuration, dragStartTime.start + deltaTime));
      newEndTime = newStartTime + clipDuration;
    } else if (dragType === 'start') {
      newStartTime = Math.max(0, Math.min(dragStartTime.end - minDuration, dragStartTime.start + deltaTime));
    } else if (dragType === 'end') {
      newEndTime = Math.max(dragStartTime.start + minDuration, Math.min(duration, dragStartTime.end + deltaTime));
    }

    // Update element timing
    if (onUpdateElement) {
      onUpdateElement(element.id, {
        startTime: parseFloat(newStartTime.toFixed(2)),
        endTime: parseFloat(newEndTime.toFixed(2)),
      });
    }
  }, [isDraggingClip, dragType, dragStartX, dragStartTime, duration, elements, onUpdateElement]);

  const handleMouseUp = useCallback(() => {
    setIsDraggingClip(null);
    setDragType(null);
  }, []);

  useEffect(() => {
    if (isDraggingClip) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDraggingClip, handleMouseMove, handleMouseUp]);

  const getElementIcon = (type) => {
    switch (type) {
      case 'text': return <Type className="w-3 h-3" />;
      case 'image': return <Image className="w-3 h-3" />;
      case 'shape': return <Square className="w-3 h-3" />;
      case 'video': return <Video className="w-3 h-3" />;
      default: return <Square className="w-3 h-3" />;
    }
  };

  const getClipColor = (type) => {
    switch (type) {
      case 'text': return 'bg-blue-500/40 border-blue-500/60';
      case 'image': return 'bg-purple-500/40 border-purple-500/60';
      case 'shape': return 'bg-amber-500/40 border-amber-500/60';
      case 'video': return 'bg-rose-500/40 border-rose-500/60';
      default: return 'bg-slate-500/40 border-slate-500/60';
    }
  };

  // Update slide duration
  const handleDurationChange = (e) => {
    const newDuration = parseFloat(e.target.value) || 5;
    if (onUpdateSlide && newDuration >= 1 && newDuration <= 300) {
      onUpdateSlide({ duration: newDuration });
    }
  };

  return (
    <div className="h-52 border-t border-border bg-card flex flex-col" data-testid="timeline">
      {/* Timeline Controls */}
      <div className="h-10 border-b border-border flex items-center px-4 gap-3 flex-shrink-0">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={handleReset}
          data-testid="timeline-reset-btn"
        >
          <SkipBack className="w-4 h-4" />
        </Button>
        <Button
          variant={isPlaying ? 'secondary' : 'ghost'}
          size="icon"
          className="h-7 w-7"
          onClick={handlePlayPause}
          data-testid="timeline-play-btn"
        >
          {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        </Button>

        <span className="text-xs font-mono text-muted-foreground min-w-[80px]">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>

        <div className="flex-1 mx-4">
          <Slider
            value={[currentTime]}
            max={duration}
            step={0.1}
            onValueChange={handleSeek}
            className="cursor-pointer"
            data-testid="timeline-scrubber"
          />
        </div>

        <Button
          variant={isMuted ? 'destructive' : 'ghost'}
          size="icon"
          className="h-7 w-7"
          onClick={() => setIsMuted(!isMuted)}
          data-testid="timeline-mute-btn"
        >
          {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
        </Button>

        <div className="flex items-center gap-1 ml-2">
          <Clock className="w-3 h-3 text-muted-foreground" />
          <Input
            type="number"
            value={duration}
            onChange={handleDurationChange}
            className="w-16 h-7 text-xs"
            min={1}
            max={300}
            step={1}
            data-testid="timeline-duration-input"
          />
          <span className="text-xs text-muted-foreground">s</span>
        </div>
      </div>

      {/* Timeline Tracks */}
      <div className="flex-1 overflow-auto flex">
        {/* Track Labels */}
        <div className="w-28 flex-shrink-0 border-r border-border bg-muted/30">
          {/* Audio Track Labels */}
          {audioList.map((audio, index) => (
            <div key={audio.id} className="h-10 flex items-center px-2 border-b border-border/50">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground truncate">
                <Music className="w-3 h-3 text-green-500 flex-shrink-0" />
                <span className="truncate">{audio.type === 'narration' ? 'Narração' : 'Áudio'}</span>
              </div>
            </div>
          ))}
          
          {/* Element Track Labels */}
          {elements.map((element, index) => (
            <div key={element.id} className="h-10 flex items-center px-2 border-b border-border/50">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground truncate">
                {getElementIcon(element.type)}
                <span className="truncate capitalize">
                  {element.type} {index + 1}
                </span>
              </div>
            </div>
          ))}

          {/* Empty state */}
          {elements.length === 0 && audioList.length === 0 && (
            <div className="h-10 flex items-center px-2 text-xs text-muted-foreground">
              Sem elementos
            </div>
          )}
        </div>

        {/* Tracks Area */}
        <div 
          ref={tracksRef}
          className="flex-1 relative overflow-x-auto"
          onClick={handleTrackClick}
        >
          {/* Time ruler */}
          <div className="h-5 border-b border-border bg-muted/20 flex sticky top-0 z-10">
            {Array.from({ length: Math.ceil(duration) + 1 }).map((_, i) => (
              <div 
                key={i} 
                className="flex-shrink-0 text-[10px] text-muted-foreground border-l border-border/30 pl-1"
                style={{ width: `${100 / duration}%` }}
              >
                {i}s
              </div>
            ))}
          </div>

          {/* Audio Tracks */}
          {audioList.map((audio) => {
            const startPercent = ((audio.startTime || 0) / duration) * 100;
            const clipDuration = audio.duration || duration;
            const widthPercent = Math.min((clipDuration / duration) * 100, 100 - startPercent);
            
            return (
              <div key={audio.id} className="h-10 relative border-b border-border/30">
                <div
                  className="absolute h-7 top-1.5 bg-green-500/30 border border-green-500/50 rounded flex items-center px-2"
                  style={{
                    left: `${startPercent}%`,
                    width: `${widthPercent}%`,
                    minWidth: '20px',
                  }}
                >
                  <Music className="w-3 h-3 text-green-600 mr-1 flex-shrink-0" />
                  <span className="text-[10px] truncate text-green-800 dark:text-green-200">
                    {audio.filename?.slice(0, 15) || audio.type}
                  </span>
                </div>
                
                {/* Hidden audio element for playback */}
                <audio
                  ref={el => audioRefs.current[audio.id] = el}
                  src={audio.src}
                  preload="auto"
                />
              </div>
            );
          })}

          {/* Element Tracks */}
          {elements.map((element) => {
            const startTime = element.startTime || 0;
            const endTime = element.endTime ?? duration;
            const startPercent = (startTime / duration) * 100;
            const widthPercent = ((endTime - startTime) / duration) * 100;
            const isActive = currentTime >= startTime && currentTime < endTime;
            const isDragging = isDraggingClip === element.id;

            return (
              <div key={element.id} className="h-10 relative border-b border-border/30">
                {/* Element clip */}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div
                      className={`absolute h-7 top-1.5 rounded border flex items-center group ${getClipColor(element.type)} ${
                        isActive ? 'ring-2 ring-cyan-400 ring-offset-1' : ''
                      } ${isDragging ? 'opacity-75' : ''}`}
                      style={{
                        left: `${startPercent}%`,
                        width: `${widthPercent}%`,
                        minWidth: '30px',
                        cursor: isDragging ? 'grabbing' : 'grab',
                      }}
                      onMouseDown={(e) => handleClipMouseDown(e, element, 'move')}
                      data-testid={`timeline-clip-${element.id}`}
                    >
                      {/* Start handle */}
                      <div
                        className="absolute left-0 top-0 bottom-0 w-3 cursor-ew-resize hover:bg-white/40 rounded-l flex items-center justify-center z-10"
                        onMouseDown={(e) => handleClipMouseDown(e, element, 'start')}
                      >
                        <div className="w-0.5 h-4 bg-current opacity-70" />
                      </div>

                      {/* Content */}
                      <div className="flex-1 flex items-center px-4 min-w-0">
                        {getElementIcon(element.type)}
                        <span className="text-[10px] ml-1 truncate">
                          {element.content?.slice(0, 10) || element.type}
                        </span>
                      </div>

                      {/* End handle */}
                      <div
                        className="absolute right-0 top-0 bottom-0 w-3 cursor-ew-resize hover:bg-white/40 rounded-r flex items-center justify-center z-10"
                        onMouseDown={(e) => handleClipMouseDown(e, element, 'end')}
                      >
                        <div className="w-0.5 h-4 bg-current opacity-70" />
                      </div>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    <p className="text-xs">
                      {formatTime(startTime)} → {formatTime(endTime)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Arraste para mover • Bordas para ajustar
                    </p>
                  </TooltipContent>
                </Tooltip>
              </div>
            );
          })}

          {/* Empty state tracks area */}
          {elements.length === 0 && audioList.length === 0 && (
            <div className="h-20 flex items-center justify-center text-muted-foreground text-sm">
              Adicione elementos para ver na timeline
            </div>
          )}

          {/* Playhead */}
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-cyan-500 pointer-events-none z-20"
            style={{
              left: `${(currentTime / duration) * 100}%`,
              transition: isPlaying ? 'none' : 'left 0.1s',
            }}
          >
            <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-3 h-3 bg-cyan-500 rotate-45" />
          </div>
        </div>
      </div>

      {/* Info bar */}
      <div className="h-6 border-t border-border flex items-center px-4 gap-4 text-[10px] text-muted-foreground bg-muted/20 flex-shrink-0">
        <span>Dica: Arraste os clipes para definir quando cada elemento aparece</span>
        <span className="ml-auto">
          {elements.length} elemento{elements.length !== 1 ? 's' : ''} • {audioList.length} áudio{audioList.length !== 1 ? 's' : ''}
        </span>
      </div>
    </div>
  );
};

export default Timeline;
