import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Button } from '../../../components/ui/button';
import { GripVertical, Type, Image, Square, Video, ExternalLink, Code, BookOpen, Trash2 } from 'lucide-react';

const SortableLayerItem = ({ element, index, isSelected, onClick, onDelete }) => {
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

  return (
    <div
      ref={setNodeRef}
      style={style}
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
      <span className="text-sm truncate flex-1">
        {element.type === 'button' ? (element.buttonText || 'Botao') : 
         element.type === 'html' ? 'HTML' :
         element.type === 'flipbook' ? 'Flipbook' :
         element.type === 'video' ? 'Video' :
         element.type === 'image' ? 'Imagem' :
         element.type === 'text' ? 'Texto' :
         `${element.type} ${element.id.slice(0, 4)}`}
      </span>
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 opacity-0 group-hover:opacity-100"
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
      >
        <Trash2 className="w-3 h-3 text-destructive" />
      </Button>
    </div>
  );
};

export default SortableLayerItem;
