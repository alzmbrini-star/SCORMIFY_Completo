import React, { useState, useRef, useEffect } from 'react';
import { Button } from '../ui/button';
import { Slider } from '../ui/slider';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
} from 'lucide-react';

const Timeline = ({ slide, onUpdateSlide }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const timelineRef = useRef(null);
  const animationRef = useRef(null);

  const duration = slide?.duration || 5;
  const elements = slide?.elements || [];
  const audioList = slide?.audio || [];

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
  }, [isPlaying, duration, currentTime]);

  const handlePlayPause = () => {
    setIsPlaying(!isPlaying);
  };

  const handleReset = () => {
    setCurrentTime(0);
    setIsPlaying(false);
  };

  const handleSeek = (value) => {
    setCurrentTime(value[0]);
    setIsPlaying(false);
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 10);
    return `${mins}:${secs.toString().padStart(2, '0')}.${ms}`;
  };

  const handleTimelineClick = (e) => {
    if (!timelineRef.current) return;
    
    const rect = timelineRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    const newTime = percentage * duration;
    
    setCurrentTime(Math.max(0, Math.min(duration, newTime)));
    setIsPlaying(false);
  };

  return (
    <div className="h-48 border-t border-border bg-card flex flex-col" data-testid="timeline">
      {/* Timeline Controls */}
      <div className="h-10 border-b border-border flex items-center px-4 gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={handleReset}
        >
          <SkipBack className="w-4 h-4" />
        </Button>
        <Button
          variant="ghost"
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
          />
        </div>

        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={() => setIsMuted(!isMuted)}
        >
          {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
        </Button>
      </div>

      {/* Timeline Tracks */}
      <div className="flex-1 overflow-auto" ref={timelineRef} onClick={handleTimelineClick}>
        <div className="min-h-full p-2 space-y-2">
          {/* Audio Track */}
          {audioList.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs w-20 text-muted-foreground truncate">Audio</span>
              <div className="flex-1 h-8 bg-secondary/50 rounded relative">
                {audioList.map((audio, index) => (
                  <div
                    key={audio.id}
                    className="absolute h-full bg-green-500/30 border border-green-500/50 rounded"
                    style={{
                      left: `${(audio.startTime || 0) / duration * 100}%`,
                      width: `${Math.min((audio.duration || duration) / duration * 100, 100)}%`,
                    }}
                  >
                    <span className="text-[10px] p-1 truncate block">{audio.type}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Element Animation Tracks */}
          {elements.map((element, index) => (
            <div key={element.id} className="flex items-center gap-2">
              <span className="text-xs w-20 text-muted-foreground truncate">
                {element.type} {index + 1}
              </span>
              <div className="flex-1 h-8 bg-secondary/50 rounded relative">
                {/* Element clip */}
                <div
                  className="timeline-clip absolute h-full flex items-center px-2"
                  style={{
                    left: '0%',
                    width: '100%',
                  }}
                >
                  <span className="text-[10px] truncate">
                    {element.content?.slice(0, 20) || element.type}
                  </span>
                </div>

                {/* Animation markers */}
                {element.animations?.map((anim) => (
                  <div
                    key={anim.id}
                    className="absolute top-0 w-1 h-full bg-cyan-500"
                    style={{
                      left: `${((anim.startTime || anim.delay || 0) / duration) * 100}%`,
                    }}
                    title={`${anim.effect} (${anim.type})`}
                  />
                ))}
              </div>
            </div>
          ))}

          {/* Empty state */}
          {elements.length === 0 && audioList.length === 0 && (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              Add elements to see them on the timeline
            </div>
          )}
        </div>

        {/* Playhead */}
        <div
          className="playhead"
          style={{
            left: `${(currentTime / duration) * 100}%`,
            transition: isPlaying ? 'none' : 'left 0.1s',
          }}
        />
      </div>
    </div>
  );
};

export default Timeline;
