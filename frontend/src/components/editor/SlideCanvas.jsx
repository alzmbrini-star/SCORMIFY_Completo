import React, { useRef, useState, useEffect, useCallback } from 'react';
import { useProject } from '../../contexts/ProjectContext';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Helper to get full asset URL
const getAssetUrl = (src) => {
  if (!src) return '';
  if (src.startsWith('http')) return src;
  if (src.startsWith('/api/')) return `${API_URL}${src}`;
  return src;
};

const SlideCanvas = ({
  slide,
  selectedElementId,
  onSelectElement,
  onUpdateElement,
  onDeleteElement,
  annotationMode,
}) => {
  const canvasRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [resizeHandle, setResizeHandle] = useState(null);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [elementStart, setElementStart] = useState({ x: 0, y: 0, width: 0, height: 0 });
  const [isDrawing, setIsDrawing] = useState(false);
  const [annotationPoints, setAnnotationPoints] = useState([]);
  const [editingElementId, setEditingElementId] = useState(null);

  const { addAnnotation } = useProject();

  const canvasWidth = slide?.width || 960;
  const canvasHeight = slide?.height || 540;

  const handleMouseDown = useCallback((e, element) => {
    if (annotationMode) return;
    
    e.stopPropagation();
    onSelectElement(element.id);
    
    const rect = canvasRef.current.getBoundingClientRect();
    const scale = rect.width / canvasWidth;
    
    setIsDragging(true);
    setDragStart({
      x: (e.clientX - rect.left) / scale,
      y: (e.clientY - rect.top) / scale,
    });
    setElementStart({
      x: element.x,
      y: element.y,
      width: element.width,
      height: element.height,
    });
  }, [annotationMode, canvasWidth, onSelectElement]);

  const handleResizeMouseDown = useCallback((e, element, handle) => {
    e.stopPropagation();
    
    const rect = canvasRef.current.getBoundingClientRect();
    const scale = rect.width / canvasWidth;
    
    setIsResizing(true);
    setResizeHandle(handle);
    setDragStart({
      x: (e.clientX - rect.left) / scale,
      y: (e.clientY - rect.top) / scale,
    });
    setElementStart({
      x: element.x,
      y: element.y,
      width: element.width,
      height: element.height,
    });
  }, [canvasWidth]);

  const handleMouseMove = useCallback((e) => {
    if (!canvasRef.current) return;
    
    const rect = canvasRef.current.getBoundingClientRect();
    const scale = rect.width / canvasWidth;
    const currentX = (e.clientX - rect.left) / scale;
    const currentY = (e.clientY - rect.top) / scale;

    if (isDrawing && annotationMode) {
      setAnnotationPoints(prev => [...prev, { x: currentX, y: currentY }]);
      return;
    }

    if (isDragging && selectedElementId) {
      const deltaX = currentX - dragStart.x;
      const deltaY = currentY - dragStart.y;
      
      onUpdateElement(selectedElementId, {
        x: Math.max(0, Math.min(canvasWidth - elementStart.width, elementStart.x + deltaX)),
        y: Math.max(0, Math.min(canvasHeight - elementStart.height, elementStart.y + deltaY)),
      });
    }

    if (isResizing && selectedElementId) {
      const deltaX = currentX - dragStart.x;
      const deltaY = currentY - dragStart.y;

      let newX = elementStart.x;
      let newY = elementStart.y;
      let newWidth = elementStart.width;
      let newHeight = elementStart.height;

      switch (resizeHandle) {
        case 'se':
          newWidth = Math.max(50, elementStart.width + deltaX);
          newHeight = Math.max(50, elementStart.height + deltaY);
          break;
        case 'sw':
          newX = elementStart.x + deltaX;
          newWidth = Math.max(50, elementStart.width - deltaX);
          newHeight = Math.max(50, elementStart.height + deltaY);
          break;
        case 'ne':
          newY = elementStart.y + deltaY;
          newWidth = Math.max(50, elementStart.width + deltaX);
          newHeight = Math.max(50, elementStart.height - deltaY);
          break;
        case 'nw':
          newX = elementStart.x + deltaX;
          newY = elementStart.y + deltaY;
          newWidth = Math.max(50, elementStart.width - deltaX);
          newHeight = Math.max(50, elementStart.height - deltaY);
          break;
        default:
          break;
      }

      onUpdateElement(selectedElementId, {
        x: newX,
        y: newY,
        width: newWidth,
        height: newHeight,
      });
    }
  }, [
    isDrawing, annotationMode, isDragging, isResizing, selectedElementId,
    dragStart, elementStart, canvasWidth, canvasHeight, resizeHandle, onUpdateElement
  ]);

  const handleMouseUp = useCallback(async () => {
    setIsDragging(false);
    setIsResizing(false);
    setResizeHandle(null);

    if (isDrawing && annotationMode && annotationPoints.length > 2) {
      try {
        await addAnnotation(slide.id, {
          type: annotationMode,
          points: annotationPoints,
          color: '#EF4444',
          strokeWidth: 2,
          includeInExport: false,
        });
      } catch (err) {
        console.error('Failed to save annotation');
      }
    }
    setIsDrawing(false);
    setAnnotationPoints([]);
  }, [isDrawing, annotationMode, annotationPoints, slide?.id, addAnnotation]);

  const handleCanvasMouseDown = useCallback((e) => {
    if (annotationMode === 'freehand') {
      const rect = canvasRef.current.getBoundingClientRect();
      const scale = rect.width / canvasWidth;
      const x = (e.clientX - rect.left) / scale;
      const y = (e.clientY - rect.top) / scale;
      
      setIsDrawing(true);
      setAnnotationPoints([{ x, y }]);
    } else {
      onSelectElement(null);
    }
  }, [annotationMode, canvasWidth, onSelectElement]);

  const handleDoubleClick = useCallback((e, element) => {
    if (element.type === 'text') {
      setEditingElementId(element.id);
    }
  }, []);

  const handleTextChange = useCallback((e, elementId) => {
    onUpdateElement(elementId, { content: e.target.value });
  }, [onUpdateElement]);

  const handleTextBlur = useCallback(() => {
    setEditingElementId(null);
  }, []);

  const handleKeyDown = useCallback((e) => {
    if ((e.key === 'Delete' || e.key === 'Backspace') && selectedElementId && editingElementId !== selectedElementId) {
      e.preventDefault();
      onDeleteElement(selectedElementId);
    }
    if (e.key === 'Escape') {
      onSelectElement(null);
      setEditingElementId(null);
    }
  }, [selectedElementId, editingElementId, onDeleteElement, onSelectElement]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  useEffect(() => {
    window.addEventListener('mouseup', handleMouseUp);
    window.addEventListener('mousemove', handleMouseMove);
    return () => {
      window.removeEventListener('mouseup', handleMouseUp);
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, [handleMouseUp, handleMouseMove]);

  if (!slide) {
    return (
      <div className="flex items-center justify-center w-full h-full text-muted-foreground">
        No slide selected
      </div>
    );
  }

  return (
    <div
      ref={canvasRef}
      className="relative shadow-2xl"
      style={{
        width: canvasWidth,
        height: canvasHeight,
        maxWidth: '100%',
        maxHeight: 'calc(100vh - 200px)',
        aspectRatio: `${canvasWidth} / ${canvasHeight}`,
        backgroundColor: slide.background || '#FFFFFF',
        backgroundImage: slide.backgroundImage ? `url(${getAssetUrl(slide.backgroundImage)})` : 'none',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        cursor: annotationMode ? 'crosshair' : 'default',
      }}
      onMouseDown={handleCanvasMouseDown}
      data-testid="slide-canvas"
    >
      {/* Elements */}
      {slide.elements?.map((element) => (
        <div
          key={element.id}
          className={`canvas-element ${selectedElementId === element.id ? 'selected' : ''}`}
          style={{
            left: element.x,
            top: element.y,
            width: element.width,
            height: element.height,
            transform: element.rotation ? `rotate(${element.rotation}deg)` : undefined,
            zIndex: element.zIndex || 0,
            opacity: element.style?.opacity ?? 1,
          }}
          onMouseDown={(e) => handleMouseDown(e, element)}
          onDoubleClick={(e) => handleDoubleClick(e, element)}
          data-testid={`element-${element.id}`}
        >
          {/* Text Element */}
          {element.type === 'text' && (
            editingElementId === element.id ? (
              <textarea
                className="w-full h-full p-2 bg-transparent resize-none outline-none border-none"
                style={{
                  fontSize: element.style?.fontSize || 16,
                  fontFamily: element.style?.fontFamily || 'inherit',
                  fontWeight: element.style?.fontWeight || 'normal',
                  color: element.style?.fontColor || '#000000',
                  textAlign: element.style?.textAlign || 'left',
                }}
                value={element.content || ''}
                onChange={(e) => handleTextChange(e, element.id)}
                onBlur={handleTextBlur}
                autoFocus
              />
            ) : (
              <div
                className="w-full h-full p-2 whitespace-pre-wrap overflow-hidden"
                style={{
                  fontSize: element.style?.fontSize || 16,
                  fontFamily: element.style?.fontFamily || 'inherit',
                  fontWeight: element.style?.fontWeight || 'normal',
                  color: element.style?.fontColor || '#000000',
                  textAlign: element.style?.textAlign || 'left',
                }}
              >
                {element.content}
              </div>
            )
          )}

          {/* Image Element */}
          {element.type === 'image' && (
            <img
              src={getAssetUrl(element.src)}
              alt=""
              className="w-full h-full object-contain pointer-events-none"
              draggable={false}
            />
          )}

          {/* Shape Element */}
          {element.type === 'shape' && (
            <div
              className="w-full h-full flex items-center justify-center"
              style={{
                backgroundColor: element.style?.fill || '#7C3AED',
                border: element.style?.stroke ? `2px solid ${element.style.stroke}` : 'none',
                borderRadius: element.shapeType === 'ellipse' || element.shapeType === 'oval' ? '50%' : 
                              element.shapeType === 'rounded_rectangle' ? '8px' : '0',
              }}
            >
              {element.content && (
                <span
                  style={{
                    fontSize: element.style?.fontSize || 14,
                    color: element.style?.fontColor || '#FFFFFF',
                  }}
                >
                  {element.content}
                </span>
              )}
            </div>
          )}

          {/* Video Element */}
          {element.type === 'video' && (
            element.embedUrl ? (
              <iframe
                src={element.embedUrl}
                className="w-full h-full border-0"
                allow="autoplay; fullscreen"
                title="Video"
              />
            ) : element.src ? (
              <video src={element.src} controls className="w-full h-full" />
            ) : null
          )}

          {/* Resize Handles */}
          {selectedElementId === element.id && !annotationMode && (
            <>
              <div
                className="resize-handle -top-1.5 -left-1.5 cursor-nw-resize"
                onMouseDown={(e) => handleResizeMouseDown(e, element, 'nw')}
              />
              <div
                className="resize-handle -top-1.5 -right-1.5 cursor-ne-resize"
                onMouseDown={(e) => handleResizeMouseDown(e, element, 'ne')}
              />
              <div
                className="resize-handle -bottom-1.5 -left-1.5 cursor-sw-resize"
                onMouseDown={(e) => handleResizeMouseDown(e, element, 'sw')}
              />
              <div
                className="resize-handle -bottom-1.5 -right-1.5 cursor-se-resize"
                onMouseDown={(e) => handleResizeMouseDown(e, element, 'se')}
              />
            </>
          )}
        </div>
      ))}

      {/* Annotations */}
      <svg
        className="absolute inset-0 pointer-events-none"
        style={{ width: '100%', height: '100%' }}
      >
        {slide.annotations?.map((annotation) => (
          <path
            key={annotation.id}
            d={annotation.points?.length > 0
              ? `M ${annotation.points[0].x} ${annotation.points[0].y} ${annotation.points.slice(1).map(p => `L ${p.x} ${p.y}`).join(' ')}`
              : ''
            }
            stroke={annotation.color}
            strokeWidth={annotation.strokeWidth}
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}

        {/* Current drawing */}
        {isDrawing && annotationPoints.length > 0 && (
          <path
            d={`M ${annotationPoints[0].x} ${annotationPoints[0].y} ${annotationPoints.slice(1).map(p => `L ${p.x} ${p.y}`).join(' ')}`}
            stroke="#EF4444"
            strokeWidth={2}
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
      </svg>
    </div>
  );
};

export default SlideCanvas;
