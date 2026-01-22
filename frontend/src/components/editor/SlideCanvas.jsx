import React, { useRef, useState, useEffect, useCallback } from 'react';
import { useProject } from '../../contexts/ProjectContext';
import { Trash2, Move, RotateCw } from 'lucide-react';

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
  const [scale, setScale] = useState(1);

  const { addAnnotation } = useProject();

  const canvasWidth = slide?.width || 960;
  const canvasHeight = slide?.height || 540;

  // Calculate scale when canvas size changes
  useEffect(() => {
    const updateScale = () => {
      if (canvasRef.current) {
        const rect = canvasRef.current.getBoundingClientRect();
        setScale(rect.width / canvasWidth);
      }
    };
    updateScale();
    window.addEventListener('resize', updateScale);
    return () => window.removeEventListener('resize', updateScale);
  }, [canvasWidth]);

  const getCanvasCoords = useCallback((e) => {
    if (!canvasRef.current) return { x: 0, y: 0 };
    const rect = canvasRef.current.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) / scale,
      y: (e.clientY - rect.top) / scale,
    };
  }, [scale]);

  const handleElementMouseDown = useCallback((e, element) => {
    if (annotationMode || element.locked) return;
    
    e.stopPropagation();
    e.preventDefault();
    
    onSelectElement(element.id);
    
    const coords = getCanvasCoords(e);
    setIsDragging(true);
    setDragStart(coords);
    setElementStart({
      x: element.x,
      y: element.y,
      width: element.width,
      height: element.height,
    });
  }, [annotationMode, getCanvasCoords, onSelectElement]);

  const handleResizeMouseDown = useCallback((e, element, handle) => {
    e.stopPropagation();
    e.preventDefault();
    
    const coords = getCanvasCoords(e);
    setIsResizing(true);
    setResizeHandle(handle);
    setDragStart(coords);
    setElementStart({
      x: element.x,
      y: element.y,
      width: element.width,
      height: element.height,
    });
  }, [getCanvasCoords]);

  const handleMouseMove = useCallback((e) => {
    if (!canvasRef.current) return;
    
    const coords = getCanvasCoords(e);

    // Drawing annotations
    if (isDrawing && annotationMode) {
      setAnnotationPoints(prev => [...prev, coords]);
      return;
    }

    // Dragging element
    if (isDragging && selectedElementId) {
      const deltaX = coords.x - dragStart.x;
      const deltaY = coords.y - dragStart.y;
      
      const newX = Math.max(0, Math.min(canvasWidth - elementStart.width, elementStart.x + deltaX));
      const newY = Math.max(0, Math.min(canvasHeight - elementStart.height, elementStart.y + deltaY));
      
      onUpdateElement(selectedElementId, { x: newX, y: newY });
    }

    // Resizing element
    if (isResizing && selectedElementId) {
      const deltaX = coords.x - dragStart.x;
      const deltaY = coords.y - dragStart.y;
      const minSize = 30;

      let newX = elementStart.x;
      let newY = elementStart.y;
      let newWidth = elementStart.width;
      let newHeight = elementStart.height;

      switch (resizeHandle) {
        case 'se':
          newWidth = Math.max(minSize, elementStart.width + deltaX);
          newHeight = Math.max(minSize, elementStart.height + deltaY);
          break;
        case 'sw':
          newX = Math.min(elementStart.x + elementStart.width - minSize, elementStart.x + deltaX);
          newWidth = Math.max(minSize, elementStart.width - deltaX);
          newHeight = Math.max(minSize, elementStart.height + deltaY);
          break;
        case 'ne':
          newY = Math.min(elementStart.y + elementStart.height - minSize, elementStart.y + deltaY);
          newWidth = Math.max(minSize, elementStart.width + deltaX);
          newHeight = Math.max(minSize, elementStart.height - deltaY);
          break;
        case 'nw':
          newX = Math.min(elementStart.x + elementStart.width - minSize, elementStart.x + deltaX);
          newY = Math.min(elementStart.y + elementStart.height - minSize, elementStart.y + deltaY);
          newWidth = Math.max(minSize, elementStart.width - deltaX);
          newHeight = Math.max(minSize, elementStart.height - deltaY);
          break;
        case 'n':
          newY = Math.min(elementStart.y + elementStart.height - minSize, elementStart.y + deltaY);
          newHeight = Math.max(minSize, elementStart.height - deltaY);
          break;
        case 's':
          newHeight = Math.max(minSize, elementStart.height + deltaY);
          break;
        case 'e':
          newWidth = Math.max(minSize, elementStart.width + deltaX);
          break;
        case 'w':
          newX = Math.min(elementStart.x + elementStart.width - minSize, elementStart.x + deltaX);
          newWidth = Math.max(minSize, elementStart.width - deltaX);
          break;
        default:
          break;
      }

      // Constrain to canvas bounds
      newX = Math.max(0, newX);
      newY = Math.max(0, newY);
      newWidth = Math.min(newWidth, canvasWidth - newX);
      newHeight = Math.min(newHeight, canvasHeight - newY);

      onUpdateElement(selectedElementId, {
        x: newX,
        y: newY,
        width: newWidth,
        height: newHeight,
      });
    }
  }, [
    isDrawing, annotationMode, isDragging, isResizing, selectedElementId,
    dragStart, elementStart, canvasWidth, canvasHeight, resizeHandle,
    onUpdateElement, getCanvasCoords
  ]);

  const handleMouseUp = useCallback(async () => {
    if (isDrawing && annotationMode && annotationPoints.length > 2 && slide) {
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
    
    setIsDragging(false);
    setIsResizing(false);
    setResizeHandle(null);
    setIsDrawing(false);
    setAnnotationPoints([]);
  }, [isDrawing, annotationMode, annotationPoints, slide, addAnnotation]);

  const handleCanvasMouseDown = useCallback((e) => {
    if (annotationMode === 'freehand') {
      const coords = getCanvasCoords(e);
      setIsDrawing(true);
      setAnnotationPoints([coords]);
    } else {
      onSelectElement(null);
      setEditingElementId(null);
    }
  }, [annotationMode, getCanvasCoords, onSelectElement]);

  const handleDoubleClick = useCallback((e, element) => {
    e.stopPropagation();
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

  const handleDeleteElement = useCallback((e, elementId) => {
    e.stopPropagation();
    onDeleteElement(elementId);
  }, [onDeleteElement]);

  const handleKeyDown = useCallback((e) => {
    if ((e.key === 'Delete' || e.key === 'Backspace') && selectedElementId && editingElementId !== selectedElementId) {
      e.preventDefault();
      onDeleteElement(selectedElementId);
    }
    if (e.key === 'Escape') {
      onSelectElement(null);
      setEditingElementId(null);
    }
    // Arrow key movement
    if (selectedElementId && !editingElementId) {
      const step = e.shiftKey ? 10 : 1;
      const element = slide?.elements?.find(el => el.id === selectedElementId);
      if (element) {
        switch (e.key) {
          case 'ArrowUp':
            e.preventDefault();
            onUpdateElement(selectedElementId, { y: Math.max(0, element.y - step) });
            break;
          case 'ArrowDown':
            e.preventDefault();
            onUpdateElement(selectedElementId, { y: Math.min(canvasHeight - element.height, element.y + step) });
            break;
          case 'ArrowLeft':
            e.preventDefault();
            onUpdateElement(selectedElementId, { x: Math.max(0, element.x - step) });
            break;
          case 'ArrowRight':
            e.preventDefault();
            onUpdateElement(selectedElementId, { x: Math.min(canvasWidth - element.width, element.x + step) });
            break;
          default:
            break;
        }
      }
    }
  }, [selectedElementId, editingElementId, slide, canvasWidth, canvasHeight, onDeleteElement, onSelectElement, onUpdateElement]);

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

  const selectedElement = slide.elements?.find(el => el.id === selectedElementId);

  return (
    <div
      ref={canvasRef}
      className="relative shadow-2xl overflow-hidden"
      style={{
        width: canvasWidth,
        height: canvasHeight,
        maxWidth: '100%',
        maxHeight: 'calc(100vh - 200px)',
        aspectRatio: `${canvasWidth} / ${canvasHeight}`,
        backgroundColor: slide.background || '#FFFFFF',
        cursor: annotationMode ? 'crosshair' : 'default',
      }}
      onMouseDown={handleCanvasMouseDown}
      data-testid="slide-canvas"
    >
      {/* Background Image Layer */}
      {slide.backgroundImage && (
        <img
          src={getAssetUrl(slide.backgroundImage)}
          alt=""
          className="absolute inset-0 w-full h-full object-contain pointer-events-none select-none"
          style={{ zIndex: 0 }}
          draggable={false}
        />
      )}
      
      {/* Elements */}
      {slide.elements?.filter(el => el.visible !== false).map((element) => {
        const isSelected = selectedElementId === element.id;
        const isEditing = editingElementId === element.id;
        
        return (
          <div
            key={element.id}
            className={`absolute group ${isSelected ? 'ring-2 ring-cyan-500 ring-offset-1' : ''}`}
            style={{
              left: element.x,
              top: element.y,
              width: element.width,
              height: element.height,
              transform: element.rotation ? `rotate(${element.rotation}deg)` : undefined,
              zIndex: (element.zIndex || 0) + 1,
              opacity: element.style?.opacity ?? 1,
              cursor: isDragging && isSelected ? 'grabbing' : 'grab',
            }}
            onMouseDown={(e) => handleElementMouseDown(e, element)}
            onDoubleClick={(e) => handleDoubleClick(e, element)}
            data-testid={`element-${element.id}`}
          >
            {/* Element Content */}
            <div className="w-full h-full overflow-hidden">
              {/* Text Element */}
              {element.type === 'text' && (
                isEditing ? (
                  <textarea
                    className="w-full h-full p-2 bg-white/90 resize-none outline-none border-2 border-cyan-500 rounded"
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
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <div
                    className="w-full h-full p-2 whitespace-pre-wrap overflow-hidden bg-white/80 rounded"
                    style={{
                      fontSize: element.style?.fontSize || 16,
                      fontFamily: element.style?.fontFamily || 'inherit',
                      fontWeight: element.style?.fontWeight || 'normal',
                      color: element.style?.fontColor || '#000000',
                      textAlign: element.style?.textAlign || 'left',
                    }}
                  >
                    {element.content || 'Double-click to edit'}
                  </div>
                )
              )}

              {/* Image Element */}
              {element.type === 'image' && (
                <img
                  src={getAssetUrl(element.src)}
                  alt=""
                  className="w-full h-full object-contain pointer-events-none select-none"
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
                      className="text-center px-2"
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
                <div className="relative w-full h-full">
                  {element.embedUrl ? (
                    <iframe
                      src={element.embedUrl}
                      className="w-full h-full border-0"
                      allow="autoplay; fullscreen"
                      title="Video"
                      style={{ pointerEvents: isSelected ? 'none' : 'auto' }}
                    />
                  ) : element.src ? (
                    <video 
                      src={getAssetUrl(element.src)} 
                      controls={!isSelected}
                      className="w-full h-full"
                      style={{ pointerEvents: isSelected ? 'none' : 'auto' }}
                    />
                  ) : (
                    <div className="w-full h-full bg-gray-800 flex items-center justify-center text-white">
                      Video
                    </div>
                  )}
                  {/* Overlay to capture mouse events when selected */}
                  {isSelected && (
                    <div 
                      className="absolute inset-0 bg-transparent cursor-grab"
                      style={{ zIndex: 1 }}
                    />
                  )}
                  {/* Video indicator badge */}
                  {!isSelected && (
                    <div className="absolute top-2 left-2 px-2 py-1 bg-black/60 text-white text-xs rounded flex items-center gap-1">
                      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M8 5v14l11-7z"/>
                      </svg>
                      {element.embedType === 'youtube' ? 'YouTube' : element.embedType === 'vimeo' ? 'Vimeo' : 'Video'}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Selection Controls - Only show when selected */}
            {isSelected && !isEditing && !annotationMode && (
              <>
                {/* Delete Button */}
                <button
                  className="absolute -top-10 right-0 w-8 h-8 bg-red-500 hover:bg-red-600 rounded-full flex items-center justify-center text-white shadow-lg transition-colors"
                  onClick={(e) => handleDeleteElement(e, element.id)}
                  title="Delete element (Del)"
                  data-testid={`delete-element-${element.id}`}
                >
                  <Trash2 className="w-4 h-4" />
                </button>

                {/* Move indicator */}
                <div className="absolute -top-10 left-0 px-2 py-1 bg-cyan-500 text-white text-xs rounded flex items-center gap-1">
                  <Move className="w-3 h-3" />
                  Drag to move
                </div>

                {/* Corner Resize Handles */}
                <div
                  className="absolute -top-1.5 -left-1.5 w-3 h-3 bg-cyan-500 rounded-full cursor-nw-resize border-2 border-white shadow"
                  onMouseDown={(e) => handleResizeMouseDown(e, element, 'nw')}
                />
                <div
                  className="absolute -top-1.5 -right-1.5 w-3 h-3 bg-cyan-500 rounded-full cursor-ne-resize border-2 border-white shadow"
                  onMouseDown={(e) => handleResizeMouseDown(e, element, 'ne')}
                />
                <div
                  className="absolute -bottom-1.5 -left-1.5 w-3 h-3 bg-cyan-500 rounded-full cursor-sw-resize border-2 border-white shadow"
                  onMouseDown={(e) => handleResizeMouseDown(e, element, 'sw')}
                />
                <div
                  className="absolute -bottom-1.5 -right-1.5 w-3 h-3 bg-cyan-500 rounded-full cursor-se-resize border-2 border-white shadow"
                  onMouseDown={(e) => handleResizeMouseDown(e, element, 'se')}
                />

                {/* Edge Resize Handles */}
                <div
                  className="absolute -top-1 left-1/2 -translate-x-1/2 w-6 h-2 bg-cyan-500 rounded cursor-n-resize border border-white shadow"
                  onMouseDown={(e) => handleResizeMouseDown(e, element, 'n')}
                />
                <div
                  className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-6 h-2 bg-cyan-500 rounded cursor-s-resize border border-white shadow"
                  onMouseDown={(e) => handleResizeMouseDown(e, element, 's')}
                />
                <div
                  className="absolute top-1/2 -left-1 -translate-y-1/2 w-2 h-6 bg-cyan-500 rounded cursor-w-resize border border-white shadow"
                  onMouseDown={(e) => handleResizeMouseDown(e, element, 'w')}
                />
                <div
                  className="absolute top-1/2 -right-1 -translate-y-1/2 w-2 h-6 bg-cyan-500 rounded cursor-e-resize border border-white shadow"
                  onMouseDown={(e) => handleResizeMouseDown(e, element, 'e')}
                />
              </>
            )}
          </div>
        );
      })}

      {/* Annotations SVG Layer */}
      <svg
        className="absolute inset-0 pointer-events-none"
        style={{ width: '100%', height: '100%', zIndex: 1000 }}
      >
        {/* Existing annotations */}
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

      {/* Instructions overlay when no elements */}
      {(!slide.elements || slide.elements.length === 0) && !slide.backgroundImage && (
        <div className="absolute inset-0 flex items-center justify-center text-muted-foreground pointer-events-none">
          <div className="text-center">
            <p className="text-lg mb-2">Empty Slide</p>
            <p className="text-sm">Use the toolbar to add elements</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default SlideCanvas;
