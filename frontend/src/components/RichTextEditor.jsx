import React, { useState, useRef, useCallback, useEffect } from 'react';
import { 
  Bold, Italic, Underline as UnderlineIcon, Strikethrough,
  AlignLeft, AlignCenter, AlignRight, AlignJustify,
  List, ListOrdered, Link as LinkIcon, Image as ImageIcon,
  Table as TableIcon, Undo, Redo, Heading1, Heading2, Heading3,
  Sparkles, Loader2, Grid3X3
} from 'lucide-react';
import { Button } from './ui/button';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';

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
  isGenerating = false,
  placeholder = 'Digite ou gere texto com IA...',
  className = ''
}) => {
  const [showAIPrompt, setShowAIPrompt] = useState(false);
  const [aiPrompt, setAIPrompt] = useState('');
  const [linkUrl, setLinkUrl] = useState('');
  const [showLinkInput, setShowLinkInput] = useState(false);
  const [imageUrl, setImageUrl] = useState('');
  const [showImageInput, setShowImageInput] = useState(false);
  const [showTableConfig, setShowTableConfig] = useState(false);
  const [tableRows, setTableRows] = useState(3);
  const [tableCols, setTableCols] = useState(3);
  const [selectedImage, setSelectedImage] = useState(null);
  const [isResizing, setIsResizing] = useState(false);
  const [resizeStart, setResizeStart] = useState({ x: 0, y: 0, width: 0, height: 0 });
  const editorRef = useRef(null);
  const lastContentRef = useRef(content);
  const initialContentRef = useRef(content);

  // Initialize content on mount
  useEffect(() => {
    if (editorRef.current && initialContentRef.current) {
      editorRef.current.innerHTML = initialContentRef.current;
    }
  }, []);

  // Handle content prop changes after init
  useEffect(() => {
    if (editorRef.current && content !== lastContentRef.current) {
      editorRef.current.innerHTML = content || '';
      lastContentRef.current = content;
    }
  }, [content]);

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

  const addImage = useCallback(() => {
    if (!imageUrl.trim()) return;
    
    // Focus the editor first
    if (editorRef.current) {
      editorRef.current.focus();
    }
    
    // Use insertHTML with an img tag for better control
    const imgHtml = `<img src="${imageUrl}" alt="image" style="max-width: 100%; height: auto; border-radius: 4px; margin: 8px 0;" />`;
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
            >
              <ImageIcon className="w-4 h-4" />
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-64 bg-slate-800 border-slate-700">
            <div className="space-y-2">
              <Input
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                placeholder="URL da imagem..."
                className="bg-slate-900 border-slate-700"
              />
              <Button onClick={addImage} size="sm" type="button" className="w-full">
                Inserir Imagem
              </Button>
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
      <div
        ref={editorRef}
        contentEditable="true"
        onInput={handleInput}
        onPaste={handlePaste}
        onClick={handleEditorClick}
        className="rich-text-editor p-4 min-h-[300px] outline-none text-slate-100 relative"
        style={{ lineHeight: '1.6' }}
        data-placeholder={placeholder}
        suppressContentEditableWarning={true}
      />
      
      {/* Image Resize Handles */}
      {selectedImage && !isResizing && (
        <div 
          className="resize-handles-container"
          style={{
            position: 'absolute',
            pointerEvents: 'none'
          }}
        >
          <div 
            className="resize-handle resize-handle-se"
            onMouseDown={(e) => handleResizeStart(e, 'corner')}
            style={{
              position: 'fixed',
              width: '12px',
              height: '12px',
              background: '#22d3ee',
              border: '2px solid #0e7490',
              borderRadius: '2px',
              cursor: 'nwse-resize',
              pointerEvents: 'auto',
              left: selectedImage.getBoundingClientRect().right - 6,
              top: selectedImage.getBoundingClientRect().bottom - 6,
              zIndex: 9999
            }}
          />
        </div>
      )}

      {/* Custom styles */}
      <style>{`
        .rich-text-editor:empty:before {
          content: attr(data-placeholder);
          color: #64748b;
          pointer-events: none;
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
