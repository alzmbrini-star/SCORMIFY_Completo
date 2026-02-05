import React, { useCallback, useState } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import TextStyle from '@tiptap/extension-text-style';
import Color from '@tiptap/extension-color';
import Link from '@tiptap/extension-link';
import Image from '@tiptap/extension-image';
import Table from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';
import Placeholder from '@tiptap/extension-placeholder';
import { 
  Bold, Italic, Underline as UnderlineIcon, Strikethrough,
  AlignLeft, AlignCenter, AlignRight, AlignJustify,
  List, ListOrdered, Link as LinkIcon, Image as ImageIcon,
  Table as TableIcon, Undo, Redo, Heading1, Heading2, Heading3,
  Sparkles, Loader2, Palette
} from 'lucide-react';
import { Button } from './ui/button';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';

const MenuButton = ({ onClick, isActive, disabled, children, title }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    title={title}
    className={`p-1.5 rounded hover:bg-slate-700 transition-colors ${
      isActive ? 'bg-slate-700 text-cyan-400' : 'text-slate-300'
    } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
  >
    {children}
  </button>
);

const COLORS = [
  '#ffffff', '#000000', '#ef4444', '#f97316', '#eab308', 
  '#22c55e', '#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899'
];

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

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3],
        },
      }),
      Underline,
      TextAlign.configure({
        types: ['heading', 'paragraph'],
      }),
      TextStyle,
      Color,
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: 'text-cyan-400 underline cursor-pointer',
        },
      }),
      Image.configure({
        inline: true,
        allowBase64: true,
      }),
      Table.configure({
        resizable: true,
      }),
      TableRow,
      TableCell,
      TableHeader,
      Placeholder.configure({
        placeholder,
      }),
    ],
    content: content || '',
    onUpdate: ({ editor }) => {
      onChange?.(editor.getHTML());
    },
  });

  const handleAIGenerate = useCallback(async () => {
    if (!aiPrompt.trim() || !onGenerateAI) return;
    
    try {
      const generatedContent = await onGenerateAI(aiPrompt);
      if (generatedContent && editor) {
        editor.commands.setContent(generatedContent);
      }
      setShowAIPrompt(false);
      setAIPrompt('');
    } catch (error) {
      console.error('Error generating AI content:', error);
    }
  }, [aiPrompt, onGenerateAI, editor]);

  const addLink = useCallback(() => {
    if (!linkUrl.trim()) return;
    
    editor
      .chain()
      .focus()
      .extendMarkRange('link')
      .setLink({ href: linkUrl })
      .run();
    
    setLinkUrl('');
    setShowLinkInput(false);
  }, [editor, linkUrl]);

  const addImage = useCallback(() => {
    if (!imageUrl.trim()) return;
    
    editor.chain().focus().setImage({ src: imageUrl }).run();
    
    setImageUrl('');
    setShowImageInput(false);
  }, [editor, imageUrl]);

  const insertTable = useCallback(() => {
    editor
      .chain()
      .focus()
      .insertTable({ rows: 3, cols: 3, withHeaderRow: true })
      .run();
  }, [editor]);

  if (!editor) {
    return null;
  }

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
        <MenuButton
          onClick={() => editor.chain().focus().undo().run()}
          disabled={!editor.can().undo()}
          title="Desfazer"
        >
          <Undo className="w-4 h-4" />
        </MenuButton>
        <MenuButton
          onClick={() => editor.chain().focus().redo().run()}
          disabled={!editor.can().redo()}
          title="Refazer"
        >
          <Redo className="w-4 h-4" />
        </MenuButton>

        <div className="w-px h-6 bg-slate-700 mx-1" />

        {/* Headings */}
        <MenuButton
          onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
          isActive={editor.isActive('heading', { level: 1 })}
          title="Título 1"
        >
          <Heading1 className="w-4 h-4" />
        </MenuButton>
        <MenuButton
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
          isActive={editor.isActive('heading', { level: 2 })}
          title="Título 2"
        >
          <Heading2 className="w-4 h-4" />
        </MenuButton>
        <MenuButton
          onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
          isActive={editor.isActive('heading', { level: 3 })}
          title="Título 3"
        >
          <Heading3 className="w-4 h-4" />
        </MenuButton>

        <div className="w-px h-6 bg-slate-700 mx-1" />

        {/* Text formatting */}
        <MenuButton
          onClick={() => editor.chain().focus().toggleBold().run()}
          isActive={editor.isActive('bold')}
          title="Negrito"
        >
          <Bold className="w-4 h-4" />
        </MenuButton>
        <MenuButton
          onClick={() => editor.chain().focus().toggleItalic().run()}
          isActive={editor.isActive('italic')}
          title="Itálico"
        >
          <Italic className="w-4 h-4" />
        </MenuButton>
        <MenuButton
          onClick={() => editor.chain().focus().toggleUnderline().run()}
          isActive={editor.isActive('underline')}
          title="Sublinhado"
        >
          <UnderlineIcon className="w-4 h-4" />
        </MenuButton>
        <MenuButton
          onClick={() => editor.chain().focus().toggleStrike().run()}
          isActive={editor.isActive('strike')}
          title="Riscado"
        >
          <Strikethrough className="w-4 h-4" />
        </MenuButton>

        {/* Color picker */}
        <Popover>
          <PopoverTrigger asChild>
            <button className="p-1.5 rounded hover:bg-slate-700 text-slate-300" title="Cor do texto">
              <Palette className="w-4 h-4" />
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-auto bg-slate-800 border-slate-700 p-2">
            <div className="grid grid-cols-5 gap-1">
              {COLORS.map((color) => (
                <button
                  key={color}
                  onClick={() => editor.chain().focus().setColor(color).run()}
                  className="w-6 h-6 rounded border border-slate-600 hover:scale-110 transition-transform"
                  style={{ backgroundColor: color }}
                  title={color}
                />
              ))}
            </div>
          </PopoverContent>
        </Popover>

        <div className="w-px h-6 bg-slate-700 mx-1" />

        {/* Alignment */}
        <MenuButton
          onClick={() => editor.chain().focus().setTextAlign('left').run()}
          isActive={editor.isActive({ textAlign: 'left' })}
          title="Alinhar à esquerda"
        >
          <AlignLeft className="w-4 h-4" />
        </MenuButton>
        <MenuButton
          onClick={() => editor.chain().focus().setTextAlign('center').run()}
          isActive={editor.isActive({ textAlign: 'center' })}
          title="Centralizar"
        >
          <AlignCenter className="w-4 h-4" />
        </MenuButton>
        <MenuButton
          onClick={() => editor.chain().focus().setTextAlign('right').run()}
          isActive={editor.isActive({ textAlign: 'right' })}
          title="Alinhar à direita"
        >
          <AlignRight className="w-4 h-4" />
        </MenuButton>
        <MenuButton
          onClick={() => editor.chain().focus().setTextAlign('justify').run()}
          isActive={editor.isActive({ textAlign: 'justify' })}
          title="Justificar"
        >
          <AlignJustify className="w-4 h-4" />
        </MenuButton>

        <div className="w-px h-6 bg-slate-700 mx-1" />

        {/* Lists */}
        <MenuButton
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          isActive={editor.isActive('bulletList')}
          title="Lista"
        >
          <List className="w-4 h-4" />
        </MenuButton>
        <MenuButton
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          isActive={editor.isActive('orderedList')}
          title="Lista numerada"
        >
          <ListOrdered className="w-4 h-4" />
        </MenuButton>

        <div className="w-px h-6 bg-slate-700 mx-1" />

        {/* Link */}
        <Popover open={showLinkInput} onOpenChange={setShowLinkInput}>
          <PopoverTrigger asChild>
            <button
              className={`p-1.5 rounded hover:bg-slate-700 transition-colors ${
                editor.isActive('link') ? 'bg-slate-700 text-cyan-400' : 'text-slate-300'
              }`}
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
              <div className="flex gap-2">
                <Button onClick={addLink} size="sm" className="flex-1">
                  Inserir
                </Button>
                {editor.isActive('link') && (
                  <Button
                    onClick={() => editor.chain().focus().unsetLink().run()}
                    variant="destructive"
                    size="sm"
                  >
                    Remover
                  </Button>
                )}
              </div>
            </div>
          </PopoverContent>
        </Popover>

        {/* Image */}
        <Popover open={showImageInput} onOpenChange={setShowImageInput}>
          <PopoverTrigger asChild>
            <button className="p-1.5 rounded hover:bg-slate-700 text-slate-300" title="Inserir imagem">
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
              <Button onClick={addImage} size="sm" className="w-full">
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
      <EditorContent 
        editor={editor} 
        className="prose prose-invert max-w-none p-4 min-h-[200px] focus:outline-none
          [&_.ProseMirror]:min-h-[180px] [&_.ProseMirror]:outline-none
          [&_.ProseMirror_p.is-editor-empty:first-child::before]:content-[attr(data-placeholder)]
          [&_.ProseMirror_p.is-editor-empty:first-child::before]:text-slate-500
          [&_.ProseMirror_p.is-editor-empty:first-child::before]:float-left
          [&_.ProseMirror_p.is-editor-empty:first-child::before]:pointer-events-none
          [&_.ProseMirror_table]:border-collapse [&_.ProseMirror_table]:w-full
          [&_.ProseMirror_th]:bg-slate-700 [&_.ProseMirror_th]:border [&_.ProseMirror_th]:border-slate-600 [&_.ProseMirror_th]:p-2
          [&_.ProseMirror_td]:border [&_.ProseMirror_td]:border-slate-600 [&_.ProseMirror_td]:p-2
          [&_.ProseMirror_img]:max-w-full [&_.ProseMirror_img]:rounded
          [&_.ProseMirror_h1]:text-2xl [&_.ProseMirror_h1]:font-bold [&_.ProseMirror_h1]:mb-4
          [&_.ProseMirror_h2]:text-xl [&_.ProseMirror_h2]:font-bold [&_.ProseMirror_h2]:mb-3
          [&_.ProseMirror_h3]:text-lg [&_.ProseMirror_h3]:font-bold [&_.ProseMirror_h3]:mb-2
          [&_.ProseMirror_ul]:list-disc [&_.ProseMirror_ul]:pl-5
          [&_.ProseMirror_ol]:list-decimal [&_.ProseMirror_ol]:pl-5
        "
      />
    </div>
  );
};

export default RichTextEditor;
