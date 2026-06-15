import React, { useState } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Button } from '../../../components/ui/button';
import { GripVertical, Type, Image, Square, Video, ExternalLink, Code, BookOpen, Trash2, ChevronDown, ChevronRight } from 'lucide-react';

const SortableLayerItem = ({ element, index, isSelected, onClick, onDelete, onUpdateOpacity }) => {
  const [expanded, setExpanded] = useState(false);
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: element.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 1000 : 1,
  };

  const currentOpacity = element.style?.opacity != null ? element.style.opacity : 1;

  // Prefer a user-set `name` (e.g. Whiteboard generations save the dialog
  // Título here, so the Layers list reads "Aula 1" instead of "Imagem").
  // Falls back to type-specific labels for legacy elements.
  const label = (element.name && String(element.name).trim()) ||
    (element.type === 'button' ? (element.buttonText || 'Botao') :
    element.type === 'html' ? 'HTML' :
    element.type === 'flipbook' ? 'Flipbook' :
    element.type === 'video' ? 'Video' :
    element.type === 'image' ? 'Imagem' :
    element.type === 'text' ? 'Texto' :
    `${element.type} ${element.id.slice(0, 4)}`);

  return (
    <div ref={setNodeRef} style={style}>
      <div
        className={`flex items-center gap-2 p-2 rounded cursor-pointer group ${
          isSelected ? 'bg-primary/10' : 'hover:bg-muted'
        } ${isDragging ? 'shadow-lg bg-card' : ''}`}
        onClick={onClick}
      >
        <div {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing">
          <GripVertical className="w-4 h-4 text-muted-foreground" />
        </div>
        {element.type === 'text' && <Type className="w-4 h-4" />}
        {element.type === 'image' && <Image className="w-4 h-4" />}
        {element.type === 'shape' && <Square className="w-4 h-4" />}
        {element.type === 'video' && <Video className="w-4 h-4" />}
        {element.type === 'button' && <ExternalLink className="w-4 h-4" />}
        {element.type === 'html' && <Code className="w-4 h-4" />}
        {element.type === 'flipbook' && <BookOpen className="w-4 h-4" />}
        <span className="text-sm truncate flex-1">{label}</span>
        <span className="text-[10px] text-muted-foreground font-mono mr-1">
          {Math.round(currentOpacity * 100)}%
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="h-5 w-5"
          onClick={(e) => {
            e.stopPropagation();
            setExpanded(!expanded);
          }}
          data-testid={`layer-expand-${element.id}`}
        >
          {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-5 w-5 opacity-0 group-hover:opacity-100"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
        >
          <Trash2 className="w-3 h-3 text-destructive" />
        </Button>
      </div>
      {expanded && (
        <div className="ml-8 mr-2 mb-1 px-2 py-1.5 bg-muted/30 rounded-b flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground whitespace-nowrap">Opacidade</span>
          <input
            type="range"
            min="0"
            max="100"
            value={Math.round(currentOpacity * 100)}
            onChange={(e) => {
              const val = parseInt(e.target.value) / 100;
              if (onUpdateOpacity) onUpdateOpacity(element.id, val);
            }}
            className="flex-1 h-1.5 accent-blue-500 cursor-pointer"
            data-testid={`layer-opacity-${element.id}`}
          />
          <span className="text-[10px] text-muted-foreground font-mono w-8 text-right">
            {Math.round(currentOpacity * 100)}%
          </span>
        </div>
      )}
    </div>
  );
};

export default SortableLayerItem;
