import React, { useState, useRef, useCallback, useEffect } from 'react';
import { 
  Bold, Italic, Underline as UnderlineIcon, Strikethrough,
  AlignLeft, AlignCenter, AlignRight, AlignJustify,
  List, ListOrdered, Link as LinkIcon, Image as ImageIcon,
  Table as TableIcon, Undo, Redo, Heading1, Heading2, Heading3,
  Sparkles, Loader2, Grid3X3, Type, Palette, Trash2, Move, Maximize2
} from 'lucide-react';
import { Button } from './ui/button';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';

// Available fonts
const FONTS = [
  { name: 'Arial', value: 'Arial, sans-serif' },
  { name: 'Helvetica', value: 'Helvetica, sans-serif' },
  { name: 'Verdana', value: 'Verdana, sans-serif' },
  { name: 'Tahoma', value: 'Tahoma, sans-serif' },
  { name: 'Trebuchet MS', value: '"Trebuchet MS", sans-serif' },
  { name: 'Georgia', value: 'Georgia, serif' },
  { name: 'Times New Roman', value: '"Times New Roman", serif' },
  { name: 'Courier New', value: '"Courier New", monospace' },
  { name: 'Impact', value: 'Impact, sans-serif' },
  { name: 'Comic Sans MS', value: '"Comic Sans MS", cursive' },
];

// Font sizes
const FONT_SIZES = [
  { name: '10px', value: '1' },
  { name: '12px', value: '2' },
  { name: '14px', value: '3' },
  { name: '16px', value: '4' },
  { name: '18px', value: '5' },
  { name: '24px', value: '6' },
  { name: '36px', value: '7' },
];

// Preset colors
const COLORS = [
  '#FFFFFF', '#000000', '#FF0000', '#00FF00', '#0000FF',
  '#FFFF00', '#FF00FF', '#00FFFF', '#FFA500', '#800080',
  '#008000', '#000080', '#808080', '#C0C0C0', '#FFD700',
  '#22d3ee', '#a855f7', '#ec4899', '#f97316', '#84cc16',
];

const MenuButton = ({ onClick, isActive, disabled, children, title }) => (
  <button
    onClick={(e) => {
      e.preventDefault();
      onClick?.();
    }}
    disabled={disabled}
    title={title}
    type="button"
    className={`p-1.5 rounded hover:bg-slate-700 transition-colors ${
      isActive ? 'bg-slate-700 text-cyan-400' : 'text-slate-300'
    } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
  >
    {children}
  </button>
);

export const RichTextEditor = ({ 
  content, 
  onChange, 
  onGenerateAI,
  onGenerateAIImage,
  isGenerating = false,
  isGeneratingImage = false,
  placeholder = 'Digite ou gere texto com IA...',
  className = ''
}) => {
  const [showAIPrompt, setShowAIPrompt] = useState(false);
  const [aiPrompt, setAIPrompt] = useState('');
  const [showAIImagePrompt, setShowAIImagePrompt] = useState(false);
  const [aiImagePrompt, setAIImagePrompt] = useState('');
  const [aiImagePreview, setAIImagePreview] = useState(null); // URL da imagem gerada para preview
  const [aiImageStep, setAIImageStep] = useState('prompt'); // 'prompt' | 'preview'
  const [linkUrl, setLinkUrl] = useState('');
  const [showLinkInput, setShowLinkInput] = useState(false);
  const [imageUrl, setImageUrl] = useState('');
  const [showImageInput, setShowImageInput] = useState(false);
  const [showTableConfig, setShowTableConfig] = useState(false);
  const [tableRows, setTableRows] = useState(3);
  const [tableCols, setTableCols] = useState(3);
  const [selectedImage, setSelectedImage] = useState(null);
  const [isResizing, setIsResizing] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0, imgX: 0, imgY: 0 });
  const [resizeStart, setResizeStart] = useState({ x: 0, y: 0, width: 0, height: 0 });
  const [showFontSelect, setShowFontSelect] = useState(false);
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [showFontSizeSelect, setShowFontSizeSelect] = useState(false);
  const [currentFont, setCurrentFont] = useState('Arial, sans-serif');
  const [currentColor, setCurrentColor] = useState('#FFFFFF');
  const [currentFontSize, setCurrentFontSize] = useState('3');
  const [customColor, setCustomColor] = useState('#FFFFFF');
  const [imageControlsPosition, setImageControlsPosition] = useState({ top: 0, left: 0, width: 0 });
  const editorRef = useRef(null);
  const lastContentRef = useRef(content);
  const initialContentRef = useRef(content);
  const isMountedRef = useRef(false);

  // Initialize content on mount - use requestAnimationFrame to avoid React conflicts
  useEffect(() => {
    isMountedRef.current = true;
    
    if (editorRef.current && initialContentRef.current) {
      // Use RAF to ensure this runs outside React's render cycle
      requestAnimationFrame(() => {
        if (isMountedRef.current && editorRef.current) {
          editorRef.current.innerHTML = initialContentRef.current;
        }
      });
    }
    
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Handle content prop changes after init
  useEffect(() => {
    if (!isMountedRef.current) return;
    
    if (editorRef.current && content !== lastContentRef.current) {
      // Use RAF to ensure this runs outside React's render cycle
      requestAnimationFrame(() => {
        if (isMountedRef.current && editorRef.current && content !== lastContentRef.current) {
          editorRef.current.innerHTML = content || '';
          lastContentRef.current = content;
        }
      });
    }
  }, [content]);

  // Update image controls position when image is selected
  useEffect(() => {
    if (selectedImage && editorRef.current) {
      const updatePosition = () => {
        const imgRect = selectedImage.getBoundingClientRect();
        const editorRect = editorRef.current.getBoundingClientRect();
        setImageControlsPosition({
          top: imgRect.top - editorRect.top,
          left: imgRect.left - editorRect.left,
          width: imgRect.width,
          height: imgRect.height
        });
      };
      updatePosition();
      // Update on scroll/resize
      window.addEventListener('scroll', updatePosition);
      window.addEventListener('resize', updatePosition);
      return () => {
        window.removeEventListener('scroll', updatePosition);
        window.removeEventListener('resize', updatePosition);
      };
    }
  }, [selectedImage, isResizing]);

  // Delete selected image
  const deleteSelectedImage = useCallback(() => {
    if (!selectedImage || !editorRef.current) return;
    
    // Check if image is inside a wrapper div (for centered images)
    const parentDiv = selectedImage.parentElement;
    if (parentDiv && parentDiv.tagName === 'DIV' && parentDiv.style.textAlign === 'center') {
      parentDiv.remove();
    } else {
      selectedImage.remove();
    }
    
    setSelectedImage(null);
    
    // Update content
    const newContent = editorRef.current.innerHTML;
    lastContentRef.current = newContent;
    onChange?.(newContent);
  }, [selectedImage, onChange]);

  // Change image alignment/wrap
  const changeImageAlignment = useCallback((alignment) => {
    if (!selectedImage || !editorRef.current) return;
    
    const currentSrc = selectedImage.src;
    const currentAlt = selectedImage.alt || 'image';
    const currentWidth = selectedImage.style.width || selectedImage.width;
    const currentMaxWidth = selectedImage.style.maxWidth;
    
    // Store the position to insert at
    const range = document.createRange();
    const parentDiv = selectedImage.parentElement;
    
    // Remove current image and its container if any
    if (parentDiv && parentDiv.tagName === 'DIV' && parentDiv.style.textAlign === 'center') {
      range.setStartBefore(parentDiv);
      parentDiv.remove();
    } else {
      range.setStartBefore(selectedImage);
      selectedImage.remove();
    }
    
    // Set selection to insertion point
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    
    // Create style with preserved width
    const widthStyle = currentWidth ? `width: ${typeof currentWidth === 'number' ? currentWidth + 'px' : currentWidth};` : '';
    const maxWidthStyle = currentMaxWidth || '';
    
    // Create new image with desired alignment
    let newImgHtml;
    switch (alignment) {
      case 'left':
        // Float left - text wraps around on the right
        newImgHtml = `<img src="${currentSrc}" alt="${currentAlt}" class="rtf-image-float-left" style="float: left; ${widthStyle || 'max-width: 45%;'} height: auto; border-radius: 4px; margin: 0 16px 12px 0;" />`;
        break;
      case 'right':
        // Float right - text wraps around on the left
        newImgHtml = `<img src="${currentSrc}" alt="${currentAlt}" class="rtf-image-float-right" style="float: right; ${widthStyle || 'max-width: 45%;'} height: auto; border-radius: 4px; margin: 0 0 12px 16px;" />`;
        break;
      case 'center':
        // Centered image - no text wrap
        newImgHtml = `<div style="text-align: center; width: 100%; margin: 12px 0; clear: both;"><img src="${currentSrc}" alt="${currentAlt}" class="rtf-image-center" style="${widthStyle || 'max-width: 80%;'} height: auto; border-radius: 4px; display: inline-block;" /></div>`;
        break;
      case 'inline':
      default:
        // Inline/block image - no float
        newImgHtml = `<img src="${currentSrc}" alt="${currentAlt}" class="rtf-image-inline" style="${widthStyle || 'max-width: 100%;'} height: auto; border-radius: 4px; margin: 8px 0; display: block; clear: both;" />`;
        break;
    }
    
    // Insert at cursor position
    document.execCommand('insertHTML', false, newImgHtml);
    
    setSelectedImage(null);
    
    // Update content
    const newContent = editorRef.current.innerHTML;
    lastContentRef.current = newContent;
    onChange?.(newContent);
  }, [selectedImage, onChange]);

  // Handle image click for selection
  const handleEditorClick = useCallback((e) => {
    const img = e.target.closest('img');
    if (img && editorRef.current?.contains(img)) {
      e.preventDefault();
      // Remove selection from all images
      editorRef.current.querySelectorAll('img.selected-image').forEach(i => {
        i.classList.remove('selected-image');
      });
      // Select this image
      img.classList.add('selected-image');
      setSelectedImage(img);
    } else if (!e.target.closest('.resize-handle')) {
      // Deselect if clicking outside
      if (selectedImage) {
        selectedImage.classList.remove('selected-image');
        setSelectedImage(null);
      }
    }
  }, [selectedImage]);

  // Handle image resize start
  const handleResizeStart = useCallback((e, direction) => {
    e.preventDefault();
    e.stopPropagation();
    if (!selectedImage) return;
    
    const rect = selectedImage.getBoundingClientRect();
    setIsResizing(true);
    setResizeStart({
      x: e.clientX,
      y: e.clientY,
      width: rect.width,
      height: rect.height,
      direction
    });
  }, [selectedImage]);

  // Handle image drag start
  const handleDragStart = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!selectedImage) return;
    
    // Get current position
    const currentLeft = parseInt(selectedImage.style.left) || 0;
    const currentTop = parseInt(selectedImage.style.top) || 0;
    
    setIsDragging(true);
    setDragStart({
      x: e.clientX,
      y: e.clientY,
      imgX: currentLeft,
      imgY: currentTop
    });
  }, [selectedImage]);

  // Handle mouse move for drag
  useEffect(() => {
    if (!isDragging || !selectedImage) return;

    const handleMouseMove = (e) => {
      const dx = e.clientX - dragStart.x;
      const dy = e.clientY - dragStart.y;
      
      const newX = dragStart.imgX + dx;
      const newY = dragStart.imgY + dy;
      
      // Update position
      selectedImage.style.left = `${newX}px`;
      selectedImage.style.top = `${newY}px`;
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      // Update content after drag
      if (editorRef.current) {
        const newContent = editorRef.current.innerHTML;
        lastContentRef.current = newContent;
        onChange?.(newContent);
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, selectedImage, dragStart, onChange]);

  // Handle mouse move for resize
  useEffect(() => {
    if (!isResizing || !selectedImage) return;

    const handleMouseMove = (e) => {
      const dx = e.clientX - resizeStart.x;
      const dy = e.clientY - resizeStart.y;
      const aspectRatio = resizeStart.width / resizeStart.height;
      
      let newWidth = resizeStart.width;
      let newHeight = resizeStart.height;
      
      // Maintain aspect ratio while resizing
      if (resizeStart.direction === 'se' || resizeStart.direction === 'corner') {
        newWidth = Math.max(50, resizeStart.width + dx);
        newHeight = newWidth / aspectRatio;
      } else if (resizeStart.direction === 'e') {
        newWidth = Math.max(50, resizeStart.width + dx);
      } else if (resizeStart.direction === 's') {
        newHeight = Math.max(50, resizeStart.height + dy);
      }
      
      selectedImage.style.width = `${newWidth}px`;
      selectedImage.style.height = `${newHeight}px`;
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      // Update content after resize
      if (editorRef.current) {
        const newContent = editorRef.current.innerHTML;
        lastContentRef.current = newContent;
        onChange?.(newContent);
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, selectedImage, resizeStart, onChange]);

  const saveSelection = useCallback(() => {
    const selection = window.getSelection();
    if (selection && selection.rangeCount > 0) {
      return selection.getRangeAt(0).cloneRange();
    }
    return null;
  }, []);

  const restoreSelection = useCallback((range) => {
    if (range) {
      const selection = window.getSelection();
      if (selection) {
        selection.removeAllRanges();
        selection.addRange(range);
      }
    }
  }, []);

  const execCommand = useCallback((command, value = null) => {
    const savedRange = saveSelection();
    document.execCommand(command, false, value);
    restoreSelection(savedRange);
    
    // Update content after command
    setTimeout(() => {
      if (editorRef.current) {
        const newContent = editorRef.current.innerHTML;
        lastContentRef.current = newContent;
        onChange?.(newContent);
      }
    }, 0);
  }, [onChange, saveSelection, restoreSelection]);

  const handleAIGenerate = useCallback(async () => {
    if (!aiPrompt.trim() || !onGenerateAI) return;
    
    try {
      const generatedContent = await onGenerateAI(aiPrompt);
      if (generatedContent) {
        if (editorRef.current) {
          editorRef.current.innerHTML = generatedContent;
        }
        lastContentRef.current = generatedContent;
        onChange?.(generatedContent);
      }
      setShowAIPrompt(false);
      setAIPrompt('');
    } catch (error) {
      console.error('Error generating AI content:', error);
    }
  }, [aiPrompt, onGenerateAI, onChange]);

  const handleAIImageGenerate = useCallback(async () => {
    if (!aiImagePrompt.trim() || !onGenerateAIImage) return;
    
    try {
      const imageUrl = await onGenerateAIImage(aiImagePrompt);
      if (imageUrl) {
        // Mostrar preview em vez de inserir direto
        setAIImagePreview(imageUrl);
        setAIImageStep('preview');
      }
    } catch (error) {
      console.error('Error generating AI image:', error);
    }
  }, [aiImagePrompt, onGenerateAIImage]);

  const handleInsertAIImage = useCallback(() => {
    if (!aiImagePreview || !editorRef.current) return;
    
    // Create the image HTML
    const imgHtml = `<div style="text-align: center; width: 100%; margin: 12px 0; clear: both;"><img src="${aiImagePreview}" alt="${aiImagePrompt}" class="rtf-image-center ai-generated" style="max-width: 80%; height: auto; border-radius: 4px; display: inline-block;" /></div>`;
    
    // Append the image to the end of the existing content
    const currentContent = editorRef.current.innerHTML || '';
    const newContent = currentContent + imgHtml;
    
    // Update the editor content
    editorRef.current.innerHTML = newContent;
    lastContentRef.current = newContent;
    onChange?.(newContent);
    
    // Scroll to the bottom to show the new image
    editorRef.current.scrollTop = editorRef.current.scrollHeight;
    
    // Reset state
    setShowAIImagePrompt(false);
    setAIImagePrompt('');
    setAIImagePreview(null);
    setAIImageStep('prompt');
  }, [aiImagePreview, aiImagePrompt, onChange]);

  const handleRegenerateAIImage = useCallback(() => {
    // Voltar para gerar novamente com o mesmo prompt
    setAIImagePreview(null);
    setAIImageStep('prompt');
    // Disparar a geração automaticamente
    setTimeout(() => {
      handleAIImageGenerate();
    }, 100);
  }, [handleAIImageGenerate]);

  const handleEditAIImagePrompt = useCallback(() => {
    // Voltar para editar o prompt
    setAIImagePreview(null);
    setAIImageStep('prompt');
  }, []);

  const handleCancelAIImage = useCallback(() => {
    setShowAIImagePrompt(false);
    setAIImagePrompt('');
    setAIImagePreview(null);
    setAIImageStep('prompt');
  }, []);

  const addLink = useCallback(() => {
    if (!linkUrl.trim()) return;
    
    // Focus the editor first
    if (editorRef.current) {
      editorRef.current.focus();
    }
    
    // Get the selected text
    const selection = window.getSelection();
    if (selection && selection.toString()) {
      // Wrap selected text with link
      document.execCommand('createLink', false, linkUrl);
    } else {
      // Insert link with URL as text
      const linkHtml = `<a href="${linkUrl}" target="_blank" style="color: #22d3ee; text-decoration: underline;">${linkUrl}</a>`;
      document.execCommand('insertHTML', false, linkHtml);
    }
    
    // Update content
    if (editorRef.current) {
      const newContent = editorRef.current.innerHTML;
      lastContentRef.current = newContent;
      onChange?.(newContent);
    }
    
    setLinkUrl('');
    setShowLinkInput(false);
  }, [linkUrl, onChange]);

  const addImage = useCallback((alignment = 'inline') => {
    if (!imageUrl.trim()) return;
    
    // Focus the editor first
    if (editorRef.current) {
      editorRef.current.focus();
    }
    
    let imgHtml;
    switch (alignment) {
      case 'left':
        // Float left - text wraps around on the right
        imgHtml = `<img src="${imageUrl}" alt="image" class="rtf-image-float-left" style="float: left; max-width: 45%; height: auto; border-radius: 4px; margin: 0 16px 12px 0; clear: left;" />`;
        break;
      case 'right':
        // Float right - text wraps around on the left
        imgHtml = `<img src="${imageUrl}" alt="image" class="rtf-image-float-right" style="float: right; max-width: 45%; height: auto; border-radius: 4px; margin: 0 0 12px 16px; clear: right;" />`;
        break;
      case 'center':
        // Centered image - text above and below only
        imgHtml = `<div style="text-align: center; width: 100%; margin: 12px 0; clear: both;"><img src="${imageUrl}" alt="image" class="rtf-image-center" style="max-width: 80%; height: auto; border-radius: 4px; display: inline-block;" /></div>`;
        break;
      case 'inline':
      default:
        // Inline image - follows text flow
        imgHtml = `<img src="${imageUrl}" alt="image" class="rtf-image-inline" style="max-width: 100%; height: auto; border-radius: 4px; margin: 8px 0; display: block;" />`;
        break;
    }
    document.execCommand('insertHTML', false, imgHtml);
    
    // Update content
    if (editorRef.current) {
      const newContent = editorRef.current.innerHTML;
      lastContentRef.current = newContent;
      onChange?.(newContent);
    }
    
    setImageUrl('');
    setShowImageInput(false);
  }, [imageUrl, onChange]);

  const insertTable = useCallback(() => {
    const rows = Math.max(1, Math.min(10, tableRows));
    const cols = Math.max(1, Math.min(10, tableCols));
    
    let headerCells = '';
    let bodyCells = '';
    
    for (let c = 0; c < cols; c++) {
      headerCells += `<th>Coluna ${c + 1}</th>`;
    }
    
    for (let r = 0; r < rows - 1; r++) {
      let rowCells = '';
      for (let c = 0; c < cols; c++) {
        rowCells += `<td>Dado ${r * cols + c + 1}</td>`;
      }
      bodyCells += `<tr>${rowCells}</tr>`;
    }
    
    const table = `<table class="rtf-table"><thead><tr>${headerCells}</tr></thead><tbody>${bodyCells}</tbody></table><p><br></p>`;
    
    // Focus editor first
    if (editorRef.current) {
      editorRef.current.focus();
    }
    
    // Small delay to ensure focus, then insert
    setTimeout(() => {
      document.execCommand('insertHTML', false, table);
      // Update content
      if (editorRef.current) {
        const newContent = editorRef.current.innerHTML;
        lastContentRef.current = newContent;
        onChange?.(newContent);
      }
    }, 50);
    
    setShowTableConfig(false);
  }, [onChange, tableRows, tableCols]);

  // Apply font family to selection
  const applyFont = useCallback((fontFamily) => {
    if (editorRef.current) {
      editorRef.current.focus();
    }
    document.execCommand('fontName', false, fontFamily);
    setCurrentFont(fontFamily);
    setShowFontSelect(false);
    
    // Update content
    if (editorRef.current) {
      const newContent = editorRef.current.innerHTML;
      lastContentRef.current = newContent;
      onChange?.(newContent);
    }
  }, [onChange]);

  // Apply text color to selection
  const applyColor = useCallback((color) => {
    if (editorRef.current) {
      editorRef.current.focus();
    }
    document.execCommand('foreColor', false, color);
    setCurrentColor(color);
    setShowColorPicker(false);
    
    // Update content
    if (editorRef.current) {
      const newContent = editorRef.current.innerHTML;
      lastContentRef.current = newContent;
      onChange?.(newContent);
    }
  }, [onChange]);

  // Apply font size to selection
  const applyFontSize = useCallback((size) => {
    if (editorRef.current) {
      editorRef.current.focus();
    }
    document.execCommand('fontSize', false, size);
    setCurrentFontSize(size);
    setShowFontSizeSelect(false);
    
    // Update content
    if (editorRef.current) {
      const newContent = editorRef.current.innerHTML;
      lastContentRef.current = newContent;
      onChange?.(newContent);
    }
  }, [onChange]);

  const formatBlock = useCallback((tag) => {
    execCommand('formatBlock', tag);
  }, [execCommand]);

  const handleInput = useCallback((e) => {
    const newContent = e.currentTarget.innerHTML;
    lastContentRef.current = newContent;
    onChange?.(newContent);
  }, [onChange]);

  const handlePaste = useCallback((e) => {
    // Allow default paste behavior - it works correctly
  }, []);

  return (
    <div className={`border rounded-lg overflow-hidden bg-slate-900 ${className}`}>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-0.5 p-2 border-b bg-slate-800/50">
        {/* AI Generate Button */}
        <Popover open={showAIPrompt} onOpenChange={setShowAIPrompt}>
          <PopoverTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              type="button"
              className="gap-1 text-purple-400 hover:text-purple-300 hover:bg-purple-500/20"
              disabled={isGenerating}
            >
              {isGenerating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
              Gerar com IA
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-80 bg-slate-800 border-slate-700">
            <div className="space-y-3">
              <h4 className="font-medium text-sm">Descreva o que deseja gerar</h4>
              <Textarea
                value={aiPrompt}
                onChange={(e) => setAIPrompt(e.target.value)}
                placeholder="Ex: Crie um texto explicando os benefícios de..."
                className="bg-slate-900 border-slate-700 min-h-[80px]"
              />
              <div className="flex gap-2">
                <Button
                  onClick={handleAIGenerate}
                  disabled={!aiPrompt.trim() || isGenerating}
                  type="button"
                  className="flex-1 bg-purple-600 hover:bg-purple-700"
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Gerando...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4 mr-2" />
                      Gerar
                    </>
                  )}
                </Button>
                <Button
                  variant="ghost"
                  type="button"
                  onClick={() => setShowAIPrompt(false)}
                >
                  Cancelar
                </Button>
              </div>
            </div>
          </PopoverContent>
        </Popover>

        {/* AI Image Generate Button */}
        <Popover open={showAIImagePrompt} onOpenChange={setShowAIImagePrompt}>
          <PopoverTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              type="button"
              className="gap-1 text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/20"
              disabled={isGeneratingImage}
              title="Gerar imagem com IA"
            >
              {isGeneratingImage ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ImageIcon className="w-4 h-4" />
              )}
              <Sparkles className="w-3 h-3" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-80 bg-slate-800 border-slate-700">
            <div className="space-y-3">
              <h4 className="font-medium text-sm">Gerar imagem com IA</h4>
              <p className="text-xs text-slate-400">Descreva a imagem que deseja criar</p>
              <Textarea
                value={aiImagePrompt}
                onChange={(e) => setAIImagePrompt(e.target.value)}
                placeholder="Ex: Um gráfico de crescimento profissional, um ícone de educação, uma ilustração corporativa..."
                className="bg-slate-900 border-slate-700 min-h-[80px]"
              />
              <div className="flex gap-2">
                <Button
                  onClick={handleAIImageGenerate}
                  disabled={!aiImagePrompt.trim() || isGeneratingImage}
                  type="button"
                  className="flex-1 bg-cyan-600 hover:bg-cyan-700"
                >
                  {isGeneratingImage ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Gerando...
                    </>
                  ) : (
                    <>
                      <ImageIcon className="w-4 h-4 mr-2" />
                      Gerar Imagem
                    </>
                  )}
                </Button>
                <Button
                  variant="ghost"
                  type="button"
                  onClick={() => setShowAIImagePrompt(false)}
                >
                  Cancelar
                </Button>
              </div>
            </div>
          </PopoverContent>
        </Popover>

        <div className="w-px h-6 bg-slate-700 mx-1" />
        <Popover open={showFontSelect} onOpenChange={setShowFontSelect}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="p-1.5 rounded hover:bg-slate-700 text-slate-300 flex items-center gap-1"
              title="Fonte"
            >
              <Type className="w-4 h-4" />
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-48 bg-slate-800 border-slate-700 p-2">
            <div className="space-y-1">
              <Label className="text-xs text-slate-400">Selecionar Fonte</Label>
              <div className="max-h-48 overflow-y-auto space-y-1">
                {FONTS.map((font) => (
                  <button
                    key={font.name}
                    type="button"
                    onClick={() => applyFont(font.value)}
                    className={`w-full text-left px-2 py-1.5 rounded text-sm hover:bg-slate-700 ${
                      currentFont === font.value ? 'bg-slate-700 text-cyan-400' : 'text-slate-200'
                    }`}
                    style={{ fontFamily: font.value }}
                  >
                    {font.name}
                  </button>
                ))}
              </div>
            </div>
          </PopoverContent>
        </Popover>

        {/* Color Picker */}
        <Popover open={showColorPicker} onOpenChange={setShowColorPicker}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="p-1.5 rounded hover:bg-slate-700 text-slate-300 flex items-center gap-1"
              title="Cor do texto"
            >
              <Palette className="w-4 h-4" />
              <div 
                className="w-3 h-3 rounded-sm border border-slate-500" 
                style={{ backgroundColor: currentColor }}
              />
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-56 bg-slate-800 border-slate-700 p-3">
            <div className="space-y-3">
              <Label className="text-xs text-slate-400">Cor do Texto</Label>
              <div className="grid grid-cols-5 gap-1.5">
                {COLORS.map((color) => (
                  <button
                    key={color}
                    type="button"
                    onClick={() => applyColor(color)}
                    className={`w-8 h-8 rounded border-2 transition-transform hover:scale-110 ${
                      currentColor === color ? 'border-cyan-400 ring-2 ring-cyan-400/50' : 'border-slate-600'
                    }`}
                    style={{ backgroundColor: color }}
                    title={color}
                  />
                ))}
              </div>
              <div className="flex items-center gap-2">
                <Input
                  type="color"
                  value={customColor}
                  onChange={(e) => setCustomColor(e.target.value)}
                  className="w-10 h-8 p-0 border-slate-600 cursor-pointer"
                />
                <Input
                  type="text"
                  value={customColor}
                  onChange={(e) => setCustomColor(e.target.value)}
                  placeholder="#FFFFFF"
                  className="flex-1 h-8 bg-slate-900 border-slate-600 text-xs"
                />
                <Button 
                  size="sm" 
                  type="button"
                  onClick={() => applyColor(customColor)}
                  className="h-8 px-2 text-xs"
                >
                  Aplicar
                </Button>
              </div>
            </div>
          </PopoverContent>
        </Popover>

        {/* Font Size Selector */}
        <Popover open={showFontSizeSelect} onOpenChange={setShowFontSizeSelect}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="p-1.5 rounded hover:bg-slate-700 text-slate-300 flex items-center gap-1 text-xs font-medium min-w-[40px] justify-center"
              title="Tamanho da fonte"
            >
              {FONT_SIZES.find(s => s.value === currentFontSize)?.name || '14px'}
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-28 bg-slate-800 border-slate-700 p-2">
            <div className="space-y-1">
              <Label className="text-xs text-slate-400">Tamanho</Label>
              <div className="space-y-1">
                {FONT_SIZES.map((size) => (
                  <button
                    key={size.value}
                    type="button"
                    onClick={() => applyFontSize(size.value)}
                    className={`w-full text-left px-2 py-1 rounded text-sm hover:bg-slate-700 ${
                      currentFontSize === size.value ? 'bg-slate-700 text-cyan-400' : 'text-slate-200'
                    }`}
                  >
                    {size.name}
                  </button>
                ))}
              </div>
            </div>
          </PopoverContent>
        </Popover>

        <div className="w-px h-6 bg-slate-700 mx-1" />

        {/* Undo/Redo */}
        <MenuButton onClick={() => execCommand('undo')} title="Desfazer">
          <Undo className="w-4 h-4" />
        </MenuButton>
        <MenuButton onClick={() => execCommand('redo')} title="Refazer">
          <Redo className="w-4 h-4" />
        </MenuButton>

        <div className="w-px h-6 bg-slate-700 mx-1" />

        {/* Headings */}
        <MenuButton onClick={() => formatBlock('h1')} title="Título 1">
          <Heading1 className="w-4 h-4" />
        </MenuButton>
        <MenuButton onClick={() => formatBlock('h2')} title="Título 2">
          <Heading2 className="w-4 h-4" />
        </MenuButton>
        <MenuButton onClick={() => formatBlock('h3')} title="Título 3">
          <Heading3 className="w-4 h-4" />
        </MenuButton>

        <div className="w-px h-6 bg-slate-700 mx-1" />

        {/* Text formatting */}
        <MenuButton onClick={() => execCommand('bold')} title="Negrito">
          <Bold className="w-4 h-4" />
        </MenuButton>
        <MenuButton onClick={() => execCommand('italic')} title="Itálico">
          <Italic className="w-4 h-4" />
        </MenuButton>
        <MenuButton onClick={() => execCommand('underline')} title="Sublinhado">
          <UnderlineIcon className="w-4 h-4" />
        </MenuButton>
        <MenuButton onClick={() => execCommand('strikeThrough')} title="Riscado">
          <Strikethrough className="w-4 h-4" />
        </MenuButton>

        <div className="w-px h-6 bg-slate-700 mx-1" />

        {/* Alignment */}
        <MenuButton onClick={() => execCommand('justifyLeft')} title="Alinhar à esquerda">
          <AlignLeft className="w-4 h-4" />
        </MenuButton>
        <MenuButton onClick={() => execCommand('justifyCenter')} title="Centralizar">
          <AlignCenter className="w-4 h-4" />
        </MenuButton>
        <MenuButton onClick={() => execCommand('justifyRight')} title="Alinhar à direita">
          <AlignRight className="w-4 h-4" />
        </MenuButton>
        <MenuButton onClick={() => execCommand('justifyFull')} title="Justificar">
          <AlignJustify className="w-4 h-4" />
        </MenuButton>

        <div className="w-px h-6 bg-slate-700 mx-1" />

        {/* Lists */}
        <MenuButton onClick={() => execCommand('insertUnorderedList')} title="Lista">
          <List className="w-4 h-4" />
        </MenuButton>
        <MenuButton onClick={() => execCommand('insertOrderedList')} title="Lista numerada">
          <ListOrdered className="w-4 h-4" />
        </MenuButton>

        <div className="w-px h-6 bg-slate-700 mx-1" />

        {/* Link */}
        <Popover open={showLinkInput} onOpenChange={setShowLinkInput}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="p-1.5 rounded hover:bg-slate-700 text-slate-300"
              title="Inserir link"
            >
              <LinkIcon className="w-4 h-4" />
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-64 bg-slate-800 border-slate-700">
            <div className="space-y-2">
              <Input
                value={linkUrl}
                onChange={(e) => setLinkUrl(e.target.value)}
                placeholder="https://..."
                className="bg-slate-900 border-slate-700"
              />
              <Button onClick={addLink} size="sm" type="button" className="w-full">
                Inserir Link
              </Button>
            </div>
          </PopoverContent>
        </Popover>

        {/* Image */}
        <Popover open={showImageInput} onOpenChange={setShowImageInput}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="p-1.5 rounded hover:bg-slate-700 text-slate-300"
              title="Inserir imagem"
              data-testid="rtf-image-btn"
            >
              <ImageIcon className="w-4 h-4" />
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-80 bg-slate-800 border-slate-700">
            <div className="space-y-3">
              <h4 className="font-medium text-sm text-slate-100">Inserir Imagem</h4>
              <Input
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                placeholder="URL da imagem..."
                className="bg-slate-900 border-slate-700"
                data-testid="rtf-image-url-input"
              />
              
              {/* Image Alignment Options */}
              <div className="space-y-2">
                <Label className="text-xs text-slate-400">Posicionamento</Label>
                <div className="grid grid-cols-2 gap-2">
                  <Button 
                    onClick={() => addImage('inline')} 
                    size="sm" 
                    type="button" 
                    variant="outline"
                    className="text-xs h-auto py-2 flex flex-col items-center gap-1"
                    disabled={!imageUrl.trim()}
                    data-testid="rtf-image-inline-btn"
                  >
                    <div className="w-8 h-6 border border-slate-500 rounded flex items-center justify-center">
                      <div className="w-4 h-3 bg-slate-500 rounded-sm"></div>
                    </div>
                    Em linha
                  </Button>
                  <Button 
                    onClick={() => addImage('center')} 
                    size="sm" 
                    type="button" 
                    variant="outline"
                    className="text-xs h-auto py-2 flex flex-col items-center gap-1"
                    disabled={!imageUrl.trim()}
                    data-testid="rtf-image-center-btn"
                  >
                    <div className="w-8 h-6 border border-slate-500 rounded flex flex-col items-center justify-center gap-0.5">
                      <div className="w-6 h-0.5 bg-slate-600 rounded"></div>
                      <div className="w-4 h-2 bg-cyan-500 rounded-sm"></div>
                      <div className="w-6 h-0.5 bg-slate-600 rounded"></div>
                    </div>
                    Centralizada
                  </Button>
                  <Button 
                    onClick={() => addImage('left')} 
                    size="sm" 
                    type="button" 
                    className="text-xs h-auto py-2 flex flex-col items-center gap-1 bg-cyan-600 hover:bg-cyan-700"
                    disabled={!imageUrl.trim()}
                    data-testid="rtf-image-float-left-btn"
                  >
                    <div className="w-8 h-6 border border-cyan-400 rounded flex items-start gap-0.5 p-0.5">
                      <div className="w-2 h-3 bg-cyan-400 rounded-sm flex-shrink-0"></div>
                      <div className="flex flex-col gap-0.5 flex-1">
                        <div className="w-full h-0.5 bg-slate-400 rounded"></div>
                        <div className="w-full h-0.5 bg-slate-400 rounded"></div>
                        <div className="w-full h-0.5 bg-slate-400 rounded"></div>
                      </div>
                    </div>
                    Flutuar Esquerda
                  </Button>
                  <Button 
                    onClick={() => addImage('right')} 
                    size="sm" 
                    type="button" 
                    className="text-xs h-auto py-2 flex flex-col items-center gap-1 bg-cyan-600 hover:bg-cyan-700"
                    disabled={!imageUrl.trim()}
                    data-testid="rtf-image-float-right-btn"
                  >
                    <div className="w-8 h-6 border border-cyan-400 rounded flex items-start gap-0.5 p-0.5">
                      <div className="flex flex-col gap-0.5 flex-1">
                        <div className="w-full h-0.5 bg-slate-400 rounded"></div>
                        <div className="w-full h-0.5 bg-slate-400 rounded"></div>
                        <div className="w-full h-0.5 bg-slate-400 rounded"></div>
                      </div>
                      <div className="w-2 h-3 bg-cyan-400 rounded-sm flex-shrink-0"></div>
                    </div>
                    Flutuar Direita
                  </Button>
                </div>
              </div>
              
              <div className="border-t border-slate-700 pt-2">
                <p className="text-xs text-slate-400">
                  <strong>Em linha:</strong> segue o fluxo do texto<br/>
                  <strong>Centralizada:</strong> imagem centralizada com texto acima/abaixo<br/>
                  <strong>Flutuar Esquerda/Direita:</strong> texto contorna a imagem
                </p>
              </div>
            </div>
          </PopoverContent>
        </Popover>

        {/* Table */}
        <Popover open={showTableConfig} onOpenChange={setShowTableConfig}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="p-1.5 rounded hover:bg-slate-700 text-slate-300"
              title="Inserir tabela"
            >
              <TableIcon className="w-4 h-4" />
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-64 bg-slate-800 border-slate-700">
            <div className="space-y-3">
              <h4 className="font-medium text-sm text-slate-100">Configurar Tabela</h4>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs text-slate-400">Linhas</Label>
                  <Input
                    type="number"
                    min={1}
                    max={10}
                    value={tableRows}
                    onChange={(e) => setTableRows(parseInt(e.target.value) || 2)}
                    className="bg-slate-900 border-slate-700 h-8"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs text-slate-400">Colunas</Label>
                  <Input
                    type="number"
                    min={1}
                    max={10}
                    value={tableCols}
                    onChange={(e) => setTableCols(parseInt(e.target.value) || 2)}
                    className="bg-slate-900 border-slate-700 h-8"
                  />
                </div>
              </div>
              {/* Visual preview */}
              <div className="flex justify-center py-2">
                <div className="grid gap-0.5" style={{ gridTemplateColumns: `repeat(${Math.min(tableCols, 5)}, 1fr)` }}>
                  {Array.from({ length: Math.min(tableRows, 4) * Math.min(tableCols, 5) }).map((_, i) => (
                    <div 
                      key={i} 
                      className={`w-4 h-3 border border-slate-600 ${i < Math.min(tableCols, 5) ? 'bg-slate-600' : 'bg-slate-700'}`}
                    />
                  ))}
                </div>
              </div>
              <Button onClick={insertTable} size="sm" type="button" className="w-full">
                <Grid3X3 className="w-4 h-4 mr-2" />
                Inserir Tabela
              </Button>
            </div>
          </PopoverContent>
        </Popover>
      </div>

      {/* Editor Content */}
      <div className="relative">
        <div
          ref={editorRef}
          contentEditable="true"
          onInput={handleInput}
          onPaste={handlePaste}
          onClick={handleEditorClick}
          onMouseDown={(e) => {
            const img = e.target.closest('img.selected-image');
            if (img && selectedImage === img) {
              const rect = img.getBoundingClientRect();
              const x = e.clientX - rect.left;
              const y = e.clientY - rect.top;
              
              // Check if in bottom-right corner (resize zone - 20px)
              if (x > rect.width - 20 && y > rect.height - 20) {
                handleResizeStart(e, 'corner');
              } 
              // Check if it's a floating image - allow drag
              else if (img.classList.contains('floating-image')) {
                handleDragStart(e);
              }
            }
          }}
          className="rich-text-editor p-4 min-h-[300px] outline-none text-slate-100 relative"
          style={{ lineHeight: '1.6', position: 'relative', backgroundColor: 'transparent' }}
          data-placeholder={placeholder}
          suppressContentEditableWarning={true}
        />

        {/* Image Controls Overlay - shown when image is selected */}
        {selectedImage && !isResizing && imageControlsPosition.width > 0 && (
          <div 
            className="absolute pointer-events-none"
            style={{
              top: imageControlsPosition.top,
              left: imageControlsPosition.left,
              width: imageControlsPosition.width,
              height: imageControlsPosition.height
            }}
          >
            {/* Delete Button */}
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                deleteSelectedImage();
              }}
              className="absolute -top-3 -right-3 w-7 h-7 bg-red-500 hover:bg-red-600 rounded-full flex items-center justify-center shadow-lg transition-colors pointer-events-auto z-50"
              title="Excluir imagem"
              data-testid="rtf-image-delete-btn"
            >
              <Trash2 className="w-4 h-4 text-white" />
            </button>

            {/* Resize Handle - Bottom Right Corner */}
            <div
              onMouseDown={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleResizeStart(e, 'corner');
              }}
              className="absolute -bottom-2 -right-2 w-5 h-5 bg-cyan-500 hover:bg-cyan-400 rounded-sm cursor-nwse-resize flex items-center justify-center shadow-lg pointer-events-auto z-50"
              title="Redimensionar"
              data-testid="rtf-image-resize-handle"
            >
              <Maximize2 className="w-3 h-3 text-white" />
            </div>

            {/* Move Indicator for floating images */}
            {selectedImage?.classList?.contains('floating-image') && (
              <div
                onMouseDown={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  handleDragStart(e);
                }}
                className="absolute -top-3 left-1/2 -translate-x-1/2 w-7 h-7 bg-slate-600 hover:bg-slate-500 rounded-full flex items-center justify-center shadow-lg cursor-move pointer-events-auto z-50"
                title="Mover imagem"
                data-testid="rtf-image-move-handle"
              >
                <Move className="w-4 h-4 text-white" />
              </div>
            )}
            
            {/* Alignment/Wrap Controls - Toolbar below image */}
            <div 
              className="absolute -bottom-12 left-1/2 -translate-x-1/2 flex items-center gap-1 bg-slate-800 rounded-lg p-1 shadow-lg pointer-events-auto z-50 border border-slate-700"
            >
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  changeImageAlignment('left');
                }}
                className="w-8 h-8 flex items-center justify-center rounded hover:bg-slate-700 transition-colors"
                title="Alinhar à esquerda (Text Wrap)"
                data-testid="rtf-image-align-left"
              >
                <AlignLeft className="w-4 h-4 text-cyan-400" />
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  changeImageAlignment('center');
                }}
                className="w-8 h-8 flex items-center justify-center rounded hover:bg-slate-700 transition-colors"
                title="Centralizar"
                data-testid="rtf-image-align-center"
              >
                <AlignCenter className="w-4 h-4 text-cyan-400" />
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  changeImageAlignment('right');
                }}
                className="w-8 h-8 flex items-center justify-center rounded hover:bg-slate-700 transition-colors"
                title="Alinhar à direita (Text Wrap)"
                data-testid="rtf-image-align-right"
              >
                <AlignRight className="w-4 h-4 text-cyan-400" />
              </button>
              <div className="w-px h-6 bg-slate-600 mx-1" />
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  changeImageAlignment('inline');
                }}
                className="w-8 h-8 flex items-center justify-center rounded hover:bg-slate-700 transition-colors"
                title="Imagem em bloco (sem wrap)"
                data-testid="rtf-image-inline"
              >
                <ImageIcon className="w-4 h-4 text-slate-400" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Custom styles */}
      <style>{`
        .rich-text-editor {
          background-color: transparent !important;
        }
        .rich-text-editor:empty:before {
          content: attr(data-placeholder);
          color: #64748b;
          pointer-events: none;
        }
        .rich-text-editor *,
        .rich-text-editor p,
        .rich-text-editor span,
        .rich-text-editor div,
        .rich-text-editor font,
        .rich-text-editor b,
        .rich-text-editor i,
        .rich-text-editor u,
        .rich-text-editor strong,
        .rich-text-editor em {
          background-color: transparent !important;
          background: transparent !important;
        }
        .rich-text-editor h1 {
          font-size: 1.5rem;
          font-weight: bold;
          margin-bottom: 1rem;
          color: #f1f5f9;
        }
        .rich-text-editor h2 {
          font-size: 1.25rem;
          font-weight: bold;
          margin-bottom: 0.75rem;
          color: #f1f5f9;
        }
        .rich-text-editor h3 {
          font-size: 1.1rem;
          font-weight: bold;
          margin-bottom: 0.5rem;
          color: #f1f5f9;
        }
        .rich-text-editor p {
          margin-bottom: 0.75rem;
        }
        .rich-text-editor ul {
          list-style: disc;
          padding-left: 1.5rem;
          margin-bottom: 0.75rem;
        }
        .rich-text-editor ol {
          list-style: decimal;
          padding-left: 1.5rem;
          margin-bottom: 0.75rem;
        }
        .rich-text-editor li {
          margin-bottom: 0.25rem;
        }
        .rich-text-editor a {
          color: #22d3ee;
          text-decoration: underline;
        }
        .rich-text-editor img {
          max-width: 100%;
          border-radius: 0.25rem;
          margin: 0.5rem 0;
          cursor: pointer;
          transition: box-shadow 0.2s, outline 0.2s;
        }
        .rich-text-editor img:hover {
          outline: 2px dashed #64748b;
          outline-offset: 2px;
        }
        .rich-text-editor img.selected-image {
          outline: 3px solid #22d3ee;
          outline-offset: 2px;
          box-shadow: 0 0 0 4px rgba(34, 211, 238, 0.2);
          cursor: nwse-resize;
        }
        /* Float Left Image - text wraps on right */
        .rich-text-editor img.rtf-image-float-left {
          float: left;
          clear: left;
          margin: 0 16px 12px 0;
          max-width: 45%;
          shape-outside: margin-box;
        }
        .rich-text-editor img.rtf-image-float-left:hover {
          outline: 2px dashed #22d3ee;
          outline-offset: 2px;
        }
        /* Float Right Image - text wraps on left */
        .rich-text-editor img.rtf-image-float-right {
          float: right;
          clear: right;
          margin: 0 0 12px 16px;
          max-width: 45%;
          shape-outside: margin-box;
        }
        .rich-text-editor img.rtf-image-float-right:hover {
          outline: 2px dashed #22d3ee;
          outline-offset: 2px;
        }
        /* Center Image - full width block */
        .rich-text-editor img.rtf-image-center {
          display: inline-block;
          max-width: 80%;
        }
        .rich-text-editor img.rtf-image-center:hover {
          outline: 2px dashed #22d3ee;
          outline-offset: 2px;
        }
        /* Inline Image */
        .rich-text-editor img.rtf-image-inline {
          display: block;
          max-width: 100%;
          margin: 8px 0;
        }
        /* Floating image styles (legacy - absolute positioned) */
        .rich-text-editor img.floating-image {
          position: absolute;
          cursor: move;
          z-index: 10;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        .rich-text-editor img.floating-image:hover {
          outline: 2px dashed #22d3ee;
          outline-offset: 2px;
        }
        .rich-text-editor img.floating-image.selected-image {
          outline: 3px solid #22d3ee;
          outline-offset: 2px;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3), 0 0 0 4px rgba(34, 211, 238, 0.2);
          cursor: move;
        }
        /* Clear float after floated images */
        .rich-text-editor::after {
          content: '';
          display: table;
          clear: both;
        }
        /* Enhanced Table Styles */
        .rich-text-editor table,
        .rich-text-editor table.rtf-table {
          border-collapse: separate;
          border-spacing: 0;
          width: 100%;
          margin: 1rem 0;
          border-radius: 8px;
          overflow: hidden;
          box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2);
        }
        .rich-text-editor th {
          background: linear-gradient(to bottom, #475569, #334155);
          border: none;
          border-bottom: 2px solid #22d3ee;
          padding: 0.75rem 1rem;
          font-weight: 600;
          text-align: left;
          color: #f1f5f9;
          font-size: 0.875rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .rich-text-editor th:first-child {
          border-top-left-radius: 8px;
        }
        .rich-text-editor th:last-child {
          border-top-right-radius: 8px;
        }
        .rich-text-editor td {
          border: none;
          border-bottom: 1px solid #334155;
          padding: 0.75rem 1rem;
          background: #1e293b;
          color: #e2e8f0;
          transition: background-color 0.2s;
        }
        .rich-text-editor tr:hover td {
          background: #263347;
        }
        .rich-text-editor tr:last-child td {
          border-bottom: none;
        }
        .rich-text-editor tr:last-child td:first-child {
          border-bottom-left-radius: 8px;
        }
        .rich-text-editor tr:last-child td:last-child {
          border-bottom-right-radius: 8px;
        }
        .rich-text-editor tr:nth-child(even) td {
          background: #1a2433;
        }
        .rich-text-editor tr:nth-child(even):hover td {
          background: #243247;
        }
        .rich-text-editor strong {
          font-weight: bold;
        }
        .rich-text-editor em {
          font-style: italic;
        }
      `}</style>
    </div>
  );
};

export default RichTextEditor;
