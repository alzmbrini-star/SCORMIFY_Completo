import React, { useState, useRef, useCallback, useEffect } from 'react';
import { 
  Bold, Italic, Underline as UnderlineIcon, Strikethrough,
  AlignLeft, AlignCenter, AlignRight, AlignJustify,
  List, ListOrdered, Link as LinkIcon, Image as ImageIcon,
  Table as TableIcon, Undo, Redo, Heading1, Heading2, Heading3,
  Sparkles, Loader2
} from 'lucide-react';
import { Button } from './ui/button';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';

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
  const editorRef = useRef(null);
  const lastContentRef = useRef(content);
  const initializedRef = useRef(false);

  // Initialize content on mount
  useEffect(() => {
    if (editorRef.current && !initializedRef.current) {
      if (content) {
        editorRef.current.innerHTML = content;
        lastContentRef.current = content;
      }
      initializedRef.current = true;
    }
  }, []);

  // Handle content prop changes after init
  useEffect(() => {
    if (editorRef.current && initializedRef.current) {
      if (content !== lastContentRef.current) {
        editorRef.current.innerHTML = content || '';
        lastContentRef.current = content;
      }
    }
  }, [content]);

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
    execCommand('createLink', linkUrl);
    setLinkUrl('');
    setShowLinkInput(false);
  }, [linkUrl, execCommand]);

  const addImage = useCallback(() => {
    if (!imageUrl.trim()) return;
    execCommand('insertImage', imageUrl);
    setImageUrl('');
    setShowImageInput(false);
  }, [imageUrl, execCommand]);

  const insertTable = useCallback(() => {
    const table = `
      <table style="border-collapse: collapse; width: 100%; margin: 1rem 0;">
        <thead>
          <tr>
            <th style="background: #334155; border: 1px solid #475569; padding: 0.5rem;">Coluna 1</th>
            <th style="background: #334155; border: 1px solid #475569; padding: 0.5rem;">Coluna 2</th>
            <th style="background: #334155; border: 1px solid #475569; padding: 0.5rem;">Coluna 3</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style="border: 1px solid #475569; padding: 0.5rem;">Dado 1</td>
            <td style="border: 1px solid #475569; padding: 0.5rem;">Dado 2</td>
            <td style="border: 1px solid #475569; padding: 0.5rem;">Dado 3</td>
          </tr>
          <tr>
            <td style="border: 1px solid #475569; padding: 0.5rem;">Dado 4</td>
            <td style="border: 1px solid #475569; padding: 0.5rem;">Dado 5</td>
            <td style="border: 1px solid #475569; padding: 0.5rem;">Dado 6</td>
          </tr>
        </tbody>
      </table>
    `;
    execCommand('insertHTML', table);
  }, [execCommand]);

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
        <MenuButton onClick={insertTable} title="Inserir tabela">
          <TableIcon className="w-4 h-4" />
        </MenuButton>
      </div>

      {/* Editor Content */}
      <div
        ref={editorRef}
        contentEditable="true"
        onInput={handleInput}
        onPaste={handlePaste}
        className="rich-text-editor p-4 min-h-[300px] outline-none text-slate-100"
        style={{ lineHeight: '1.6' }}
        data-placeholder={placeholder}
        suppressContentEditableWarning={true}
      />

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
        }
        .rich-text-editor table {
          border-collapse: collapse;
          width: 100%;
          margin: 1rem 0;
        }
        .rich-text-editor th {
          background: #334155;
          border: 1px solid #475569;
          padding: 0.5rem;
          font-weight: bold;
          text-align: left;
        }
        .rich-text-editor td {
          border: 1px solid #475569;
          padding: 0.5rem;
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
