import React, { useState } from 'react';
import { Button } from '../ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '../ui/tooltip';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '../ui/popover';
import { Input } from '../ui/input';
import { Slider } from '../ui/slider';
import {
  Pencil,
  ArrowUpRight,
  Circle,
  Square,
  Eraser,
  Palette,
} from 'lucide-react';

const AnnotationToolbar = ({ annotationMode, setAnnotationMode }) => {
  const [annotationColor, setAnnotationColor] = useState('#EF4444');
  const [strokeWidth, setStrokeWidth] = useState(2);

  const tools = [
    { id: 'freehand', icon: Pencil, label: 'Pen' },
    { id: 'arrow', icon: ArrowUpRight, label: 'Arrow' },
    { id: 'circle', icon: Circle, label: 'Circle' },
    { id: 'rectangle', icon: Square, label: 'Rectangle' },
  ];

  return (
    <>
      {tools.map((tool) => (
        <Tooltip key={tool.id}>
          <TooltipTrigger asChild>
            <Button
              variant={annotationMode === tool.id ? 'secondary' : 'ghost'}
              size="icon"
              className="h-8 w-8"
              onClick={() => setAnnotationMode(annotationMode === tool.id ? null : tool.id)}
              data-testid={`annotation-${tool.id}`}
            >
              <tool.icon className="w-4 h-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{tool.label}</TooltipContent>
        </Tooltip>
      ))}

      {annotationMode && (
        <>
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <div
                  className="w-4 h-4 rounded-full border border-border"
                  style={{ backgroundColor: annotationColor }}
                />
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-3">
              <div className="space-y-3">
                <div className="flex gap-2">
                  {['#EF4444', '#F59E0B', '#10B981', '#3B82F6', '#8B5CF6', '#000000'].map((color) => (
                    <button
                      key={color}
                      className={`w-6 h-6 rounded-full border-2 ${
                        annotationColor === color ? 'border-primary' : 'border-transparent'
                      }`}
                      style={{ backgroundColor: color }}
                      onClick={() => setAnnotationColor(color)}
                    />
                  ))}
                </div>
                <Input
                  type="color"
                  value={annotationColor}
                  onChange={(e) => setAnnotationColor(e.target.value)}
                  className="h-8 w-full p-1"
                />
              </div>
            </PopoverContent>
          </Popover>

          <Popover>
            <PopoverTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <div className="w-4 h-0.5 bg-current" style={{ height: strokeWidth }} />
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-48 p-3">
              <div className="space-y-2">
                <label className="text-xs">Stroke Width: {strokeWidth}px</label>
                <Slider
                  value={[strokeWidth]}
                  min={1}
                  max={10}
                  step={1}
                  onValueChange={(v) => setStrokeWidth(v[0])}
                />
              </div>
            </PopoverContent>
          </Popover>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => setAnnotationMode(null)}
              >
                <Eraser className="w-4 h-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Cancel</TooltipContent>
          </Tooltip>
        </>
      )}
    </>
  );
};

export default AnnotationToolbar;
