import React, { useRef, useState, useEffect } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Button } from '../../../components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../../../components/ui/dropdown-menu';
import { GripVertical, MoreVertical, Copy, Trash2 } from 'lucide-react';
import { getThumbAssetUrl } from '../utils';
import SlideThumbnailContent from './SlideThumbnailContent';

const SortableSlideItem = ({ slide, index, isActive, onClick, onDuplicate, onDelete }) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: slide.id });

  const thumbRef = useRef(null);
  const [thumbScale, setThumbScale] = useState(0.24);

  useEffect(() => {
    if (!thumbRef.current) return;
    const updateScale = () => {
      const containerW = thumbRef.current?.offsetWidth || 232;
      setThumbScale(containerW / (slide.width || 960));
    };
    updateScale();
    const ro = new ResizeObserver(updateScale);
    ro.observe(thumbRef.current);
    return () => ro.disconnect();
  }, [slide.width]);

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 1000 : 'auto',
  };

  const hasElements = slide.elements && slide.elements.length > 0;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`slide-thumbnail relative group ${isActive ? 'active' : ''} ${isDragging ? 'ring-2 ring-primary' : ''}`}
      onClick={onClick}
      data-testid={`slide-${index}`}
    >
      <div
        {...attributes}
        {...listeners}
        className="absolute left-1 top-1/2 -translate-y-1/2 cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-100 z-10 p-1 bg-background/80 rounded"
        onClick={(e) => e.stopPropagation()}
      >
        <GripVertical className="w-3 h-3 text-muted-foreground" />
      </div>
      
      <div
        ref={thumbRef}
        className="w-full h-full relative"
        style={{
          ...(slide.background?.includes?.('gradient')
            ? { background: slide.background }
            : { backgroundColor: slide.background || '#fff' }),
        }}
      >
        {slide.backgroundImage && (
          <img
            src={getThumbAssetUrl(slide.backgroundImage)}
            alt=""
            className="absolute inset-0 w-full h-full object-cover pointer-events-none"
            style={{ zIndex: 0, opacity: slide.backgroundOpacity != null ? slide.backgroundOpacity : 1 }}
            loading="lazy"
            draggable={false}
            onError={(e) => { e.target.onerror = null; e.target.style.display = 'none'; }}
          />
        )}
        {hasElements && (
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: slide.width || 960,
              height: slide.height || 540,
              transformOrigin: 'top left',
              transform: `scale(${thumbScale})`,
              pointerEvents: 'none',
            }}
          >
            <SlideThumbnailContent slide={slide} />
          </div>
        )}
        {!hasElements && (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
            {index + 1}
          </div>
        )}
        {hasElements && (
          <div className="absolute bottom-0.5 left-0.5 px-1 rounded text-[9px] font-medium text-muted-foreground/60 bg-background/40">
            {index + 1}
          </div>
        )}
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="absolute top-1 right-1 h-6 w-6 opacity-0 group-hover:opacity-100"
            onClick={(e) => e.stopPropagation()}
          >
            <MoreVertical className="w-3 h-3" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => onDuplicate(slide.id)}>
            <Copy className="w-4 h-4 mr-2" />
            Duplicar
          </DropdownMenuItem>
          <DropdownMenuItem
            className="text-destructive"
            onClick={() => onDelete(slide.id)}
          >
            <Trash2 className="w-4 h-4 mr-2" />
            Excluir
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
};

export default SortableSlideItem;
