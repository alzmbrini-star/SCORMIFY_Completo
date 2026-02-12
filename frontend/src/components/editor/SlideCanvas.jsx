import React, { useRef, useState, useEffect, useCallback } from 'react';
import { useProject } from '../../contexts/ProjectContext';
import { Trash2, Move, RotateCw } from 'lucide-react';
import { sanitizeHtmlForDisplay, getRtfContentStyles } from '../../utils/htmlUtils';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Helper to get full asset URL
const getAssetUrl = (src) => {
  if (!src) return '';
  
  // Replace old domain with current domain for assets
  if (src.startsWith('http')) {
    // Check if it's an asset URL from an old/different domain
    const assetMatch = src.match(/https?:\/\/[^/]+\/api\/projects\/([^/]+)\/assets\/(.+)/);
    if (assetMatch) {
      // Redirect to current server
      return `${API_URL}/api/projects/${assetMatch[1]}/assets/${assetMatch[2]}`;
    }
    // Check if it's a global asset URL from an old domain
    const globalAssetMatch = src.match(/https?:\/\/[^/]+\/api\/assets\/(.+)/);
    if (globalAssetMatch) {
      return `${API_URL}/api/assets/${globalAssetMatch[1]}`;
    }
    return src;
  }
  
  if (src.startsWith('/api/')) return `${API_URL}${src}`;
  return src;
};

// Helper to resolve all asset URLs in HTML content
const resolveHtmlContentUrls = (htmlContent) => {
  if (!htmlContent) return htmlContent;
  
  // Replace relative /api/assets/ URLs with full URLs
  let resolved = htmlContent.replace(
    /src=["']\/api\/assets\/([^"']+)["']/g,
    `src="${API_URL}/api/assets/$1"`
  );
  
  // Replace old absolute domain URLs with current domain
  resolved = resolved.replace(
    /src=["']https?:\/\/[^/]+\/api\/assets\/([^"']+)["']/g,
    `src="${API_URL}/api/assets/$1"`
  );
  
  return resolved;
};

// Debounce helper
const debounce = (func, wait) => {
  let timeout;
  return (...args) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
};

const SlideCanvas = ({
  slide,
  selectedElementId,
  onSelectElement,
  onUpdateElement,
  onDeleteElement,
  onCopyElement,
  onPasteElement,
  copiedElement,
  annotationMode,
  timelineTime = 0,
  timelineIsPlaying = false,
  onEditHtmlElement, // New prop for editing HTML elements
}) => {
  const canvasRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [resizeHandle, setResizeHandle] = useState(null);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [elementStart, setElementStart] = useState({ x: 0, y: 0, width: 0, height: 0 });
  const [isDrawing, setIsDrawing] = useState(false);
  const [annotationPoints, setAnnotationPoints] = useState([]);
  // Track pending update for final save
  const pendingUpdateRef = useRef(null);
  const [editingElementId, setEditingElementId] = useState(null);
  const [scale, setScale] = useState(1);
  const [selectedAnnotationId, setSelectedAnnotationId] = useState(null);
  
  // Local state for element positions during drag/resize (optimistic updates)
  const [localElementUpdates, setLocalElementUpdates] = useState({});

  const { addAnnotation, deleteAnnotation } = useProject();

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
    // Calculate scale dynamically for accurate coordinates
    const currentScale = rect.width / canvasWidth;
    return {
      x: (e.clientX - rect.left) / currentScale,
      y: (e.clientY - rect.top) / currentScale,
    };
  }, [canvasWidth]);

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
      if (annotationMode === 'freehand') {
        // For freehand, collect all points
        setAnnotationPoints(prev => [...prev, coords]);
      } else {
        // For shapes (arrow, circle, rectangle), just update end point
        setAnnotationPoints(prev => {
          if (prev.length === 0) return [coords];
          return [prev[0], coords];
        });
      }
      return;
    }

    // Dragging element - use local state only, API call happens on mouseUp
    if (isDragging && selectedElementId) {
      const deltaX = coords.x - dragStart.x;
      const deltaY = coords.y - dragStart.y;
      
      const newX = Math.max(0, Math.min(canvasWidth - elementStart.width, elementStart.x + deltaX));
      const newY = Math.max(0, Math.min(canvasHeight - elementStart.height, elementStart.y + deltaY));
      
      // Store pending update for mouseUp and update local state immediately (no API call)
      pendingUpdateRef.current = { x: newX, y: newY };
      setLocalElementUpdates(prev => ({
        ...prev,
        [selectedElementId]: { ...prev[selectedElementId], x: newX, y: newY }
      }));
    }

    // Resizing element - use local state only, API call happens on mouseUp
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

      // Store pending update for mouseUp and update local state immediately (no API call)
      pendingUpdateRef.current = {
        x: newX,
        y: newY,
        width: newWidth,
        height: newHeight,
      };
      setLocalElementUpdates(prev => ({
        ...prev,
        [selectedElementId]: { ...prev[selectedElementId], ...pendingUpdateRef.current }
      }));
    }
  }, [
    isDrawing, annotationMode, isDragging, isResizing, selectedElementId,
    dragStart, elementStart, canvasWidth, canvasHeight, resizeHandle,
    getCanvasCoords
  ]);

  const handleMouseUp = useCallback(async () => {
    // Ensure final position is saved when drag/resize ends - only ONE API call here
    if ((isDragging || isResizing) && selectedElementId && pendingUpdateRef.current) {
      // Force a final save with the last known position
      try {
        await onUpdateElement(selectedElementId, pendingUpdateRef.current);
        console.log('Final position saved:', pendingUpdateRef.current);
      } catch (err) {
        console.error('Failed to save final position:', err);
      }
      pendingUpdateRef.current = null;
      // Clear local updates for this element after successful save
      setLocalElementUpdates(prev => {
        const newState = { ...prev };
        delete newState[selectedElementId];
        return newState;
      });
    }
    
    // Save annotation when drawing ends
    // For shapes (arrow, circle, rectangle) we need at least 2 points
    // For freehand we need more points to make a meaningful drawing
    const minPoints = annotationMode === 'freehand' ? 3 : 2;
    if (isDrawing && annotationMode && annotationPoints.length >= minPoints && slide) {
      try {
        await addAnnotation(slide.id, {
          type: annotationMode,
          points: annotationPoints,
          color: '#EF4444',
          strokeWidth: 3,
          includeInExport: true,
        });
        console.log('Annotation saved:', annotationMode, annotationPoints.length, 'points');
      } catch (err) {
        console.error('Failed to save annotation:', err);
      }
    }
    
    setIsDragging(false);
    setIsResizing(false);
    setResizeHandle(null);
    setIsDrawing(false);
    setAnnotationPoints([]);
  }, [isDragging, isResizing, isDrawing, annotationMode, annotationPoints, slide, addAnnotation, selectedElementId, onUpdateElement]);

  const handleCanvasMouseDown = useCallback((e) => {
    if (annotationMode) {
      const coords = getCanvasCoords(e);
      setIsDrawing(true);
      setAnnotationPoints([coords]);
    } else {
      onSelectElement(null);
      setEditingElementId(null);
      setSelectedAnnotationId(null); // Deselect annotation when clicking on canvas
    }
  }, [annotationMode, getCanvasCoords, onSelectElement]);

  const handleDoubleClick = useCallback((e, element) => {
    e.stopPropagation();
    if (element.type === 'text') {
      setEditingElementId(element.id);
    } else if (element.type === 'html' && onEditHtmlElement) {
      // Open RTF editor for HTML elements
      onEditHtmlElement(element);
    }
  }, [onEditHtmlElement]);

  const handleTextChange = useCallback((e, elementId) => {
    onUpdateElement(elementId, { content: e.target.value });
  }, [onUpdateElement]);

  const handleTextBlur = useCallback(() => {
    setEditingElementId(null);
  }, []);

  const handleDeleteElement = useCallback((e, elementId) => {
    e.stopPropagation();
    if (!elementId) {
      console.error('handleDeleteElement: No elementId provided');
      return;
    }
    console.log('handleDeleteElement: Deleting element', elementId);
    onDeleteElement(elementId);
  }, [onDeleteElement]);

  const handleKeyDown = useCallback((e) => {
    // Copy element (Ctrl+C / Cmd+C)
    if ((e.ctrlKey || e.metaKey) && e.key === 'c' && selectedElementId && !editingElementId) {
      e.preventDefault();
      const element = slide?.elements?.find(el => el.id === selectedElementId);
      if (element && onCopyElement) {
        onCopyElement(element);
      }
    }
    // Paste element (Ctrl+V / Cmd+V)
    if ((e.ctrlKey || e.metaKey) && e.key === 'v' && copiedElement && !editingElementId) {
      e.preventDefault();
      if (onPasteElement) {
        onPasteElement();
      }
    }
    // Duplicate element (Ctrl+D / Cmd+D)
    if ((e.ctrlKey || e.metaKey) && e.key === 'd' && selectedElementId && !editingElementId) {
      e.preventDefault();
      const element = slide?.elements?.find(el => el.id === selectedElementId);
      if (element && onCopyElement && onPasteElement) {
        onCopyElement(element);
        setTimeout(() => onPasteElement(), 50);
      }
    }
    if ((e.key === 'Delete' || e.key === 'Backspace') && selectedElementId && editingElementId !== selectedElementId) {
      e.preventDefault();
      onDeleteElement(selectedElementId);
    }
    // Delete selected annotation with Delete/Backspace key
    if ((e.key === 'Delete' || e.key === 'Backspace') && selectedAnnotationId && !selectedElementId) {
      e.preventDefault();
      deleteAnnotation(slide.id, selectedAnnotationId);
      setSelectedAnnotationId(null);
    }
    if (e.key === 'Escape') {
      onSelectElement(null);
      setEditingElementId(null);
      setSelectedAnnotationId(null);
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
  }, [selectedElementId, editingElementId, selectedAnnotationId, slide, canvasWidth, canvasHeight, onDeleteElement, onSelectElement, onUpdateElement, deleteAnnotation, setSelectedAnnotationId, onCopyElement, onPasteElement, copiedElement]);

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
      {slide.elements?.filter(el => {
        // During timeline playback, filter by time and visibility
        if (timelineIsPlaying) {
          if (el.visible === false) return false;
          const startTime = el.startTime || 0;
          const endTime = el.endTime ?? (slide.duration || 10);
          return timelineTime >= startTime && timelineTime < endTime;
        }
        
        // When not playing, show all elements (even invisible ones for editing)
        return true;
      }).map((element) => {
        const isSelected = selectedElementId === element.id;
        const isEditing = editingElementId === element.id;
        
        // Merge local updates with element data during drag/resize (optimistic UI)
        const localUpdate = localElementUpdates[element.id];
        const displayElement = localUpdate 
          ? { ...element, ...localUpdate }
          : element;
        
        // Handle percentage or pixel values for dimensions
        const getScaledValue = (value, slideSize) => {
          if (typeof value === 'string' && value.endsWith('%')) {
            return value; // Keep percentage as-is
          }
          return (value || 0) * scale;
        };
        
        const getPositionValue = (value) => {
          if (typeof value === 'string' && value.endsWith('%')) {
            return value;
          }
          return (value || 0) * scale;
        };
        
        const elementWidth = typeof displayElement.width === 'string' && displayElement.width.endsWith('%') 
          ? displayElement.width 
          : (displayElement.width || 100) * scale;
        const elementHeight = typeof displayElement.height === 'string' && displayElement.height.endsWith('%')
          ? displayElement.height
          : (displayElement.height || 100) * scale;
        const elementX = typeof displayElement.x === 'string' && displayElement.x.endsWith('%')
          ? displayElement.x
          : (displayElement.x || 0) * scale;
        const elementY = typeof displayElement.y === 'string' && displayElement.y.endsWith('%')
          ? displayElement.y
          : (displayElement.y || 0) * scale;
        
        return (
          <div
            key={element.id}
            className={`absolute group ${isSelected ? 'ring-2 ring-cyan-500 ring-offset-1' : ''} ${element.visible === false ? 'border border-dashed border-yellow-500' : ''}`}
            style={{
              left: elementX,
              top: elementY,
              width: elementWidth,
              height: elementHeight,
              transform: displayElement.rotation ? `rotate(${displayElement.rotation}deg)` : undefined,
              zIndex: (displayElement.zIndex || 0) + 1,
              // Show at least 30% opacity for hidden elements during editing
              opacity: displayElement.visible === false ? Math.max(0.3, displayElement.style?.opacity ?? 1) : (displayElement.style?.opacity ?? 1),
              cursor: isDragging && isSelected ? 'grabbing' : 'grab',
            }}
            onMouseDown={(e) => handleElementMouseDown(e, element)}
            onDoubleClick={(e) => handleDoubleClick(e, element)}
            data-testid={`element-${element.id}`}
          >
            {/* Drag indicator showing position */}
            {isDragging && isSelected && (
              <div className="absolute -top-8 left-0 px-2 py-1 bg-cyan-600 text-white text-xs rounded shadow-lg pointer-events-none z-50 whitespace-nowrap">
                X: {Math.round(displayElement.x)} | Y: {Math.round(displayElement.y)}
              </div>
            )}
            
            {/* Move hint on hover */}
            {isSelected && !isDragging && !isResizing && (
              <div className="absolute -top-8 left-1/2 -translate-x-1/2 px-2 py-1 bg-slate-700 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap">
                ✥ Arraste para mover
              </div>
            )}
            
            {/* Element Content */}
            <div className="w-full h-full overflow-hidden">
              {/* Text Element */}
              {element.type === 'text' && (
                isEditing ? (
                  <textarea
                    className="w-full h-full p-2 resize-none outline-none border-2 border-cyan-500 rounded"
                    style={{
                      fontSize: element.style?.fontSize || 16,
                      fontFamily: element.style?.fontFamily || 'inherit',
                      fontWeight: element.style?.fontWeight || 'normal',
                      color: element.style?.fontColor || '#000000',
                      textAlign: element.style?.textAlign || 'left',
                      backgroundColor: element.style?.transparentBackground ? 'transparent' : (element.style?.backgroundColor || 'rgba(255,255,255,0.9)'),
                    }}
                    value={element.content || ''}
                    onChange={(e) => handleTextChange(e, element.id)}
                    onBlur={handleTextBlur}
                    autoFocus
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <div
                    className="w-full h-full p-2 whitespace-pre-wrap overflow-hidden rounded"
                    style={{
                      fontSize: element.style?.fontSize || 16,
                      fontFamily: element.style?.fontFamily || 'inherit',
                      fontWeight: element.style?.fontWeight || 'normal',
                      color: element.style?.fontColor || '#000000',
                      textAlign: element.style?.textAlign || 'left',
                      backgroundColor: element.style?.transparentBackground ? 'transparent' : (element.style?.backgroundColor || 'rgba(255,255,255,0.8)'),
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
                  className="w-full h-full pointer-events-none select-none"
                  style={{
                    objectFit: element.objectFit || 'contain',
                  }}
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
                    (() => {
                      // Extract video ID for YouTube thumbnail
                      const isYouTube = element.embedUrl.includes('youtube') || element.embedUrl.includes('youtu.be');
                      const ytMatch = element.embedUrl.match(/(?:embed\/|v=|youtu\.be\/)([^?&"'>]+)/);
                      const videoId = ytMatch ? ytMatch[1] : null;
                      
                      // For YouTube in editor, show thumbnail preview (more reliable, no embed restrictions)
                      if (isYouTube && videoId) {
                        return (
                          <div className="w-full h-full bg-black relative">
                            <img 
                              src={`https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`}
                              onError={(e) => { e.target.src = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`; }}
                              alt="YouTube Video"
                              className="w-full h-full object-cover"
                            />
                            {/* YouTube Play Button */}
                            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                              <div className="bg-red-600 rounded-xl px-4 py-3 flex items-center justify-center shadow-lg">
                                <svg className="w-8 h-8 text-white ml-1" fill="currentColor" viewBox="0 0 24 24">
                                  <path d="M8 5v14l11-7z"/>
                                </svg>
                              </div>
                            </div>
                          </div>
                        );
                      }
                      
                      // For Vimeo or other embeds, use iframe
                      return (
                        <iframe
                          src={element.embedUrl}
                          className="w-full h-full border-0"
                          allow="autoplay; fullscreen"
                          title="Video"
                          style={{ pointerEvents: 'none', objectFit: element.objectFit || 'contain' }}
                        />
                      );
                    })()
                  ) : element.src ? (
                    <video 
                      src={getAssetUrl(element.src)} 
                      controls={false}
                      className="w-full h-full"
                      style={{ 
                        pointerEvents: 'none',
                        objectFit: element.objectFit || 'contain'
                      }}
                    />
                  ) : (
                    <div className="w-full h-full bg-gray-800 flex items-center justify-center text-white">
                      Video
                    </div>
                  )}
                  {/* Overlay to capture all mouse events */}
                  <div 
                    className="absolute inset-0 bg-transparent"
                    style={{ zIndex: 1, cursor: isSelected ? 'grab' : 'pointer' }}
                  />
                  {/* Video indicator badge - hide when fullscreen */}
                  {element.objectFit !== 'cover' && (
                    <div className="absolute top-2 left-2 px-2 py-1 bg-black/70 text-white text-xs rounded flex items-center gap-1 pointer-events-none">
                      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M8 5v14l11-7z"/>
                      </svg>
                      {element.embedType === 'youtube' ? 'YouTube' : element.embedType === 'vimeo' ? 'Vimeo' : 'Video'}
                    </div>
                  )}
                  {/* Selected state info */}
                  {isSelected && (
                    <div className="absolute bottom-2 left-2 px-2 py-1 bg-slate-500/90 text-white text-xs rounded pointer-events-none">
                      Double-click to play • Drag corners to resize
                    </div>
                  )}
                </div>
              )}

              {/* Button Element */}
              {element.type === 'button' && (
                <div className="w-full h-full flex items-center justify-center relative">
                  <button
                    className={`px-6 py-3 rounded-lg font-semibold flex items-center gap-2 transition-all ${
                      element.buttonStyle === 'primary' 
                        ? 'bg-gradient-to-r from-purple-600 to-cyan-500 text-white hover:opacity-90' 
                        : element.buttonStyle === 'secondary'
                        ? 'bg-gray-600 text-white hover:bg-gray-700'
                        : element.buttonStyle === 'outline'
                        ? 'border-2 border-purple-600 text-purple-600 bg-transparent hover:bg-purple-50'
                        : 'bg-transparent text-gray-700 hover:bg-gray-100'
                    }`}
                    style={{
                      fontSize: element.style?.fontSize || 16,
                      borderRadius: element.style?.borderRadius || 8,
                      pointerEvents: 'none',
                    }}
                  >
                    {element.buttonIcon && <span>{element.buttonIcon}</span>}
                    {element.buttonText || 'Clique aqui'}
                  </button>
                  {/* Overlay to capture mouse events for drag/resize */}
                  <div 
                    className="absolute inset-0 bg-transparent"
                    style={{ zIndex: 1, cursor: isSelected ? 'grab' : 'pointer' }}
                  />
                  {isSelected && (
                    <div className="absolute bottom-2 left-2 px-2 py-1 bg-purple-600/90 text-white text-xs rounded pointer-events-none z-10">
                      Link: {element.buttonUrl?.slice(0, 30)}...
                    </div>
                  )}
                </div>
              )}

              {/* HTML Element */}
              {element.type === 'html' && (
                <div className={`w-full h-full relative ${element.objectFit === 'cover' ? '' : 'rounded'}`} style={{ background: 'transparent', overflow: 'hidden' }}>
                  <iframe
                    srcDoc={`
                      <html>
                        <head>
                          <style>
                            ${getRtfContentStyles({ textColor: '#f1f5f9', backgroundColor: 'transparent' })}
                            /* SlideCanvas-specific overrides */
                            html, body { 
                              overflow: hidden;
                              ${element.objectFit === 'cover' ? 'display: flex; align-items: center; justify-content: center;' : ''}
                            }
                            .content-wrapper {
                              padding: ${element.objectFit === 'cover' ? '0' : '12px'};
                            }
                            * { background: transparent !important; }
                            img {
                              ${element.objectFit === 'cover' ? 'width: 100% !important; height: 100% !important; object-fit: cover !important; max-width: none !important;' : ''}
                            }
                            /* Dark theme table styles */
                            table {
                              border-collapse: separate;
                              border-spacing: 0;
                              border-radius: 8px;
                              overflow: hidden;
                              box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
                            }
                            th {
                              background: linear-gradient(to bottom, #475569, #334155);
                              border-bottom: 2px solid #22d3ee;
                              color: #f1f5f9;
                            }
                            td {
                              border-bottom: 1px solid #334155;
                              background: #1e293b;
                              color: #e2e8f0;
                            }
                            tr:nth-child(even) td { background: #1a2433; }
                            a { color: #22d3ee; }
                          </style>
                        </head>
                        <body><div class="content-wrapper">${sanitizeHtmlForDisplay(resolveHtmlContentUrls(element.htmlContent)) || '<p>HTML Content</p>'}</div></body>
                      </html>
                    `}
                    className="w-full h-full border-0"
                    sandbox="allow-scripts allow-same-origin"
                    title="HTML Content"
                    style={{ pointerEvents: 'none', background: 'transparent' }}
                  />
                  {/* Overlay to capture mouse events for drag/resize */}
                  <div 
                    className="absolute inset-0 bg-transparent"
                    style={{ zIndex: 1, cursor: isSelected ? 'grab' : 'pointer' }}
                  />
                  {isSelected && element.objectFit !== 'cover' && (
                    <div className="absolute top-2 left-2 px-2 py-1 bg-blue-600/90 text-white text-xs rounded flex items-center gap-1 pointer-events-none z-10">
                      <span className="font-mono">&lt;/&gt;</span> HTML
                    </div>
                  )}
                </div>
              )}

              {/* Flipbook Element */}
              {element.type === 'flipbook' && (
                <div className="w-full h-full bg-gray-100 rounded overflow-hidden relative">
                  {element.flipbookType === 'external' && element.flipbookUrl ? (
                    <iframe
                      src={element.flipbookUrl}
                      className="w-full h-full border-0"
                      allow="fullscreen"
                      title="Flipbook"
                      style={{ pointerEvents: 'none' }}
                    />
                  ) : element.flipbookType === 'pdf' && element.flipbookUrl ? (
                    <iframe
                      src={element.flipbookUrl}
                      className="w-full h-full border-0"
                      title="PDF Viewer"
                      style={{ pointerEvents: 'none' }}
                    />
                  ) : element.flipbookType === 'images' && element.flipbookPages?.length > 0 ? (
                    <div className="w-full h-full flex items-center justify-center bg-gray-800 text-white">
                      <span className="text-sm">Flipbook ({element.flipbookPages.length} páginas)</span>
                    </div>
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-gray-200 text-gray-600">
                      <span className="text-sm">Flipbook</span>
                    </div>
                  )}
                  {/* Overlay to capture mouse events for drag/resize */}
                  <div 
                    className="absolute inset-0 bg-transparent"
                    style={{ zIndex: 1, cursor: isSelected ? 'grab' : 'pointer' }}
                  />
                  {isSelected && (
                    <div className="absolute top-2 left-2 px-2 py-1 bg-green-600/90 text-white text-xs rounded flex items-center gap-1 pointer-events-none z-10">
                      📖 Flipbook
                    </div>
                  )}
                </div>
              )}

              {/* Quiz Element */}
              {element.type === 'quiz' && (
                <div className={`w-full h-full bg-gradient-to-br from-slate-800 to-slate-900 overflow-hidden relative ${element.objectFit === 'cover' ? '' : 'rounded-lg border-2 border-cyan-500/30'}`}>
                  <div className={`w-full h-full flex flex-col items-center justify-center ${element.objectFit === 'cover' ? 'p-0' : 'p-6'}`}>
                    <div className="text-6xl mb-4">📝</div>
                    <h3 className="text-xl font-bold text-white mb-2">
                      {element.quizConfig?.title || 'Quiz'}
                    </h3>
                    <p className="text-slate-400 text-sm text-center mb-4">
                      {element.quizConfig?.questionIds?.length || 0} questões selecionadas
                    </p>
                    <div className="flex flex-wrap gap-2 justify-center">
                      {element.quizConfig?.shuffleQuestions && (
                        <span className="px-2 py-1 text-xs bg-cyan-500/20 text-cyan-400 rounded-full">
                          Embaralhar questões
                        </span>
                      )}
                      {element.quizConfig?.shuffleAlternatives && (
                        <span className="px-2 py-1 text-xs bg-purple-500/20 text-purple-400 rounded-full">
                          Embaralhar alternativas
                        </span>
                      )}
                      {element.quizConfig?.showFeedback && (
                        <span className="px-2 py-1 text-xs bg-green-500/20 text-green-400 rounded-full">
                          Feedback ativo
                        </span>
                      )}
                    </div>
                    <div className="mt-4 text-xs text-slate-500">
                      Nota mínima: {element.quizConfig?.passingScore || 60}%
                    </div>
                  </div>
                  {/* Overlay to capture mouse events for drag/resize */}
                  <div 
                    className="absolute inset-0 bg-transparent"
                    style={{ zIndex: 1, cursor: isSelected ? 'grab' : 'pointer' }}
                  />
                  {isSelected && element.objectFit !== 'cover' && (
                    <div className="absolute top-2 left-2 px-2 py-1 bg-cyan-600/90 text-white text-xs rounded flex items-center gap-1 pointer-events-none z-10">
                      📝 Quiz
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
                  className="absolute -top-10 right-0 w-8 h-8 bg-red-500 hover:bg-red-600 rounded-full flex items-center justify-center text-white shadow-lg transition-colors z-50"
                  onClick={(e) => handleDeleteElement(e, element.id)}
                  title="Delete element (Del)"
                  data-testid={`delete-element-${element.id}`}
                >
                  <Trash2 className="w-4 h-4" />
                </button>

                {/* Move indicator */}
                <div className="absolute -top-10 left-0 px-2 py-1 bg-slate-500 text-white text-xs rounded flex items-center gap-1 z-50">
                  <Move className="w-3 h-3" />
                  Drag to move
                </div>

                {/* Corner Resize Handles - Larger and easier to grab */}
                <div
                  className="absolute -top-2 -left-2 w-4 h-4 bg-slate-500 rounded-full cursor-nw-resize border-2 border-white shadow-lg hover:bg-slate-400 hover:scale-125 transition-transform z-50"
                  onMouseDown={(e) => handleResizeMouseDown(e, element, 'nw')}
                  data-testid={`resize-nw-${element.id}`}
                />
                <div
                  className="absolute -top-2 -right-2 w-4 h-4 bg-slate-500 rounded-full cursor-ne-resize border-2 border-white shadow-lg hover:bg-slate-400 hover:scale-125 transition-transform z-50"
                  onMouseDown={(e) => handleResizeMouseDown(e, element, 'ne')}
                  data-testid={`resize-ne-${element.id}`}
                />
                <div
                  className="absolute -bottom-2 -left-2 w-4 h-4 bg-slate-500 rounded-full cursor-sw-resize border-2 border-white shadow-lg hover:bg-slate-400 hover:scale-125 transition-transform z-50"
                  onMouseDown={(e) => handleResizeMouseDown(e, element, 'sw')}
                  data-testid={`resize-sw-${element.id}`}
                />
                <div
                  className="absolute -bottom-2 -right-2 w-4 h-4 bg-slate-500 rounded-full cursor-se-resize border-2 border-white shadow-lg hover:bg-slate-400 hover:scale-125 transition-transform z-50"
                  onMouseDown={(e) => handleResizeMouseDown(e, element, 'se')}
                  data-testid={`resize-se-${element.id}`}
                />

                {/* Edge Resize Handles - Larger */}
                <div
                  className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-8 h-3 bg-slate-500 rounded cursor-n-resize border border-white shadow-lg hover:bg-slate-400 z-50"
                  onMouseDown={(e) => handleResizeMouseDown(e, element, 'n')}
                  data-testid={`resize-n-${element.id}`}
                />
                <div
                  className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-8 h-3 bg-slate-500 rounded cursor-s-resize border border-white shadow-lg hover:bg-slate-400 z-50"
                  onMouseDown={(e) => handleResizeMouseDown(e, element, 's')}
                  data-testid={`resize-s-${element.id}`}
                />
                <div
                  className="absolute top-1/2 -left-1.5 -translate-y-1/2 w-3 h-8 bg-slate-500 rounded cursor-w-resize border border-white shadow-lg hover:bg-slate-400 z-50"
                  onMouseDown={(e) => handleResizeMouseDown(e, element, 'w')}
                  data-testid={`resize-w-${element.id}`}
                />
                <div
                  className="absolute top-1/2 -right-1.5 -translate-y-1/2 w-3 h-8 bg-slate-500 rounded cursor-e-resize border border-white shadow-lg hover:bg-slate-400 z-50"
                  onMouseDown={(e) => handleResizeMouseDown(e, element, 'e')}
                  data-testid={`resize-e-${element.id}`}
                />
              </>
            )}
          </div>
        );
      })}

      {/* Annotations SVG Layer */}
      <svg
        className="absolute inset-0"
        style={{ width: '100%', height: '100%', zIndex: 10, pointerEvents: 'none' }}
        viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}
        preserveAspectRatio="none"
      >
        {/* Existing annotations - filter by timeline when playing */}
        {slide.annotations?.filter(annotation => {
          // During timeline playback, filter by time
          if (timelineIsPlaying) {
            const startTime = annotation.startTime || 0;
            const endTime = annotation.endTime ?? (slide.duration || 10);
            return timelineTime >= startTime && timelineTime < endTime;
          }
          // When not playing, show all annotations
          return true;
        }).map((annotation) => {
          const isSelected = selectedAnnotationId === annotation.id;
          
          // Calculate bounding box for selection highlight
          let bounds = { minX: 0, minY: 0, maxX: 0, maxY: 0 };
          if (annotation.points?.length >= 2) {
            bounds.minX = Math.min(...annotation.points.map(p => p.x));
            bounds.minY = Math.min(...annotation.points.map(p => p.y));
            bounds.maxX = Math.max(...annotation.points.map(p => p.x));
            bounds.maxY = Math.max(...annotation.points.map(p => p.y));
          }
          
          return (
          <g 
            key={annotation.id}
            style={{ cursor: annotationMode ? 'default' : 'pointer', pointerEvents: annotationMode ? 'none' : 'all' }}
            onClick={(e) => {
              if (annotationMode) return;
              e.stopPropagation();
              setSelectedAnnotationId(isSelected ? null : annotation.id);
              onSelectElement(null); // Deselect any element
            }}
          >
            {/* Invisible hit area for click detection */}
            <rect
              x={bounds.minX - 10}
              y={bounds.minY - 10}
              width={bounds.maxX - bounds.minX + 20}
              height={bounds.maxY - bounds.minY + 20}
              fill="transparent"
              stroke="none"
            />
            {annotation.type === 'freehand' && (
              <path
                d={annotation.points?.length > 0
                  ? `M ${annotation.points[0].x} ${annotation.points[0].y} ${annotation.points.slice(1).map(p => `L ${p.x} ${p.y}`).join(' ')}`
                  : ''
                }
                stroke={annotation.color}
                strokeWidth={annotation.strokeWidth}
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ pointerEvents: 'none' }}
              />
            )}
            {annotation.type === 'arrow' && annotation.points?.length >= 2 && (
              <>
                <defs>
                  <marker
                    id={`arrowhead-${annotation.id}`}
                    markerWidth="10"
                    markerHeight="7"
                    refX="9"
                    refY="3.5"
                    orient="auto"
                  >
                    <polygon
                      points="0 0, 10 3.5, 0 7"
                      fill={annotation.color}
                    />
                  </marker>
                </defs>
                <line
                  x1={annotation.points[0].x}
                  y1={annotation.points[0].y}
                  x2={annotation.points[1].x}
                  y2={annotation.points[1].y}
                  stroke={annotation.color}
                  strokeWidth={annotation.strokeWidth}
                  markerEnd={`url(#arrowhead-${annotation.id})`}
                  style={{ pointerEvents: 'none' }}
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
                  stroke={annotation.color}
                  strokeWidth={annotation.strokeWidth}
                  fill="none"
                  style={{ pointerEvents: 'none' }}
                />
              );
            })()}
            {annotation.type === 'rectangle' && annotation.points?.length >= 2 && (
              <rect
                x={Math.min(annotation.points[0].x, annotation.points[1].x)}
                y={Math.min(annotation.points[0].y, annotation.points[1].y)}
                width={Math.abs(annotation.points[1].x - annotation.points[0].x)}
                height={Math.abs(annotation.points[1].y - annotation.points[0].y)}
                stroke={annotation.color}
                strokeWidth={annotation.strokeWidth}
                fill="none"
                style={{ pointerEvents: 'none' }}
              />
            )}
            
            {/* Selection highlight */}
            {isSelected && (
              <rect
                x={bounds.minX - 5}
                y={bounds.minY - 5}
                width={bounds.maxX - bounds.minX + 10}
                height={bounds.maxY - bounds.minY + 10}
                stroke="#3B82F6"
                strokeWidth={2}
                strokeDasharray="5,5"
                fill="none"
                style={{ pointerEvents: 'none' }}
              />
            )}
          </g>
        );
        })}

        {/* Current drawing preview */}
        {isDrawing && annotationPoints.length > 0 && (
          <g>
            {annotationMode === 'freehand' && (
              <path
                d={`M ${annotationPoints[0].x} ${annotationPoints[0].y} ${annotationPoints.slice(1).map(p => `L ${p.x} ${p.y}`).join(' ')}`}
                stroke="#EF4444"
                strokeWidth={2}
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            )}
            {annotationMode === 'arrow' && annotationPoints.length >= 2 && (
              <>
                <defs>
                  <marker
                    id="arrowhead-preview"
                    markerWidth="10"
                    markerHeight="7"
                    refX="9"
                    refY="3.5"
                    orient="auto"
                  >
                    <polygon points="0 0, 10 3.5, 0 7" fill="#EF4444" />
                  </marker>
                </defs>
                <line
                  x1={annotationPoints[0].x}
                  y1={annotationPoints[0].y}
                  x2={annotationPoints[1].x}
                  y2={annotationPoints[1].y}
                  stroke="#EF4444"
                  strokeWidth={2}
                  markerEnd="url(#arrowhead-preview)"
                />
              </>
            )}
            {annotationMode === 'circle' && annotationPoints.length >= 2 && (() => {
              const cx = (annotationPoints[0].x + annotationPoints[1].x) / 2;
              const cy = (annotationPoints[0].y + annotationPoints[1].y) / 2;
              const rx = Math.abs(annotationPoints[1].x - annotationPoints[0].x) / 2;
              const ry = Math.abs(annotationPoints[1].y - annotationPoints[0].y) / 2;
              return (
                <ellipse
                  cx={cx}
                  cy={cy}
                  rx={rx}
                  ry={ry}
                  stroke="#EF4444"
                  strokeWidth={2}
                  fill="none"
                />
              );
            })()}
            {annotationMode === 'rectangle' && annotationPoints.length >= 2 && (
              <rect
                x={Math.min(annotationPoints[0].x, annotationPoints[1].x)}
                y={Math.min(annotationPoints[0].y, annotationPoints[1].y)}
                width={Math.abs(annotationPoints[1].x - annotationPoints[0].x)}
                height={Math.abs(annotationPoints[1].y - annotationPoints[0].y)}
                stroke="#EF4444"
                strokeWidth={2}
                fill="none"
              />
            )}
          </g>
        )}
      </svg>

      {/* Delete button for selected annotation */}
      {selectedAnnotationId && slide.annotations && (() => {
        const annotation = slide.annotations.find(a => a.id === selectedAnnotationId);
        if (!annotation || !annotation.points?.length) return null;
        
        const minX = Math.min(...annotation.points.map(p => p.x));
        const minY = Math.min(...annotation.points.map(p => p.y));
        
        return (
          <button
            className="absolute bg-red-500 hover:bg-red-600 text-white rounded-full p-1.5 shadow-lg transition-colors z-50"
            style={{
              left: `${(minX - 15) * scale}px`,
              top: `${(minY - 15) * scale}px`,
            }}
            onMouseDown={(e) => {
              e.stopPropagation(); // Prevent canvas mousedown from deselecting
            }}
            onClick={async (e) => {
              e.stopPropagation();
              e.preventDefault();
              
              const annotationIdToDelete = selectedAnnotationId;
              const slideIdToUse = slide.id;
              
              if (!slideIdToUse || !annotationIdToDelete) {
                console.error('Missing slide.id or annotationId');
                return;
              }
              
              try {
                await deleteAnnotation(slideIdToUse, annotationIdToDelete);
                setSelectedAnnotationId(null);
              } catch (err) {
                console.error('Failed to delete annotation:', err);
              }
            }}
            title="Apagar anotação"
            data-testid="delete-annotation-btn"
          >
            <Trash2 className="w-4 h-4 pointer-events-none" />
          </button>
        );
      })()}

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
