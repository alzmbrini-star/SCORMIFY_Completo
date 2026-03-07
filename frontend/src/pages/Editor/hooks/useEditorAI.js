import { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { getApiUrl } from '../../../utils/apiUrl';
import { sanitizeHtmlContent, stripDomainFromAssetUrls, resolveAssetUrls } from '../../../utils/htmlUtils';

export function useEditorAI({ currentProject, currentSlide, addElement, updateElement, fetchProject }) {
  const [showRichTextDialog, setShowRichTextDialog] = useState(false);
  const [richTextContent, setRichTextContent] = useState('');
  const [richTextGenerating, setRichTextGenerating] = useState(false);
  const [richTextImageGenerating, setRichTextImageGenerating] = useState(false);
  const [editingHtmlElementId, setEditingHtmlElementId] = useState(null);
  const [editingHtmlSlideId, setEditingHtmlSlideId] = useState(null);
  const [rtfSaveFailed, setRtfSaveFailed] = useState(false);

  const API_URL = getApiUrl();

  const generateTextWithAI = async (prompt) => {
    setRichTextGenerating(true);
    try {
      const response = await axios.post(`${API_URL}/api/ai/generate-text`, { prompt, format: 'html' });
      if (response.data.success && response.data.content) {
        setRichTextContent(response.data.content);
        toast.success('Texto gerado com sucesso!');
        return response.data.content;
      } else {
        throw new Error('No content returned');
      }
    } catch (err) {
      console.error('Error generating text:', err);
      toast.error(err.response?.data?.detail || 'Falha ao gerar texto com IA');
      throw err;
    } finally {
      setRichTextGenerating(false);
    }
  };

  const generateImageWithAI = async (prompt) => {
    setRichTextImageGenerating(true);
    try {
      const response = await axios.post(`${API_URL}/api/ai/generate-image`, { prompt, size: '1024x1024' });
      if (response.data.success && response.data.imageUrl) {
        toast.success('Imagem gerada com sucesso!');
        return response.data.imageUrl;
      } else {
        throw new Error('No image returned');
      }
    } catch (err) {
      console.error('Error generating image:', err);
      toast.error(err.response?.data?.detail || 'Falha ao gerar imagem com IA');
      throw err;
    } finally {
      setRichTextImageGenerating(false);
    }
  };

  const handleAddRichTextToSlide = async () => {
    if (!richTextContent.trim()) {
      toast.error('Escreva ou gere um texto primeiro');
      return;
    }
    const targetSlideId = editingHtmlElementId ? editingHtmlSlideId : currentSlide?.id;
    if (!targetSlideId) {
      toast.error('Erro: nenhum slide selecionado. Feche e tente novamente.');
      return;
    }
    const cleanContent = stripDomainFromAssetUrls(sanitizeHtmlContent(richTextContent));
    try {
      if (editingHtmlElementId) {
        const targetSlide = currentProject?.course?.slides?.find(s => s.id === targetSlideId);
        const elementExists = targetSlide?.elements?.some(e => e.id === editingHtmlElementId);
        if (!elementExists) {
          toast.info('Elemento original foi removido. Criando novo elemento...');
          await addElement(targetSlideId, { type: 'html', x: 50, y: 50, width: 600, height: 400, htmlContent: cleanContent });
          toast.success('Novo texto criado no slide!');
        } else {
          await updateElement(targetSlideId, editingHtmlElementId, { htmlContent: cleanContent });
          toast.success('Texto atualizado!');
        }
      } else {
        await addElement(targetSlideId, { type: 'html', x: 50, y: 50, width: 600, height: 400, htmlContent: cleanContent });
        toast.success('Texto adicionado ao slide!');
      }
      setRtfSaveFailed(false);
      setShowRichTextDialog(false);
      setRichTextContent('');
      setEditingHtmlElementId(null);
      setEditingHtmlSlideId(null);
    } catch (err) {
      console.error('RTF save error:', err);
      setRtfSaveFailed(true);
      const detail = err?.response?.data?.detail || err?.message || '';
      toast.error('Falha ao salvar texto' + (detail ? ': ' + detail : ''));
    }
  };

  const handleEditHtmlElement = (element) => {
    if (element.type === 'html' && element.htmlContent) {
      setRichTextContent(resolveAssetUrls(element.htmlContent));
      setEditingHtmlElementId(element.id);
      setEditingHtmlSlideId(currentSlide?.id);
      setRtfSaveFailed(false);
      setShowRichTextDialog(true);
    }
  };

  const handleOpenRichText = () => {
    setRichTextContent('');
    setEditingHtmlElementId(null);
    setEditingHtmlSlideId(null);
    setRtfSaveFailed(false);
    setShowRichTextDialog(true);
  };

  const handleCloseRichText = () => {
    setShowRichTextDialog(false);
    setRichTextContent('');
    setEditingHtmlElementId(null);
    setEditingHtmlSlideId(null);
    setRtfSaveFailed(false);
  };

  return {
    showRichTextDialog, setShowRichTextDialog,
    richTextContent, setRichTextContent,
    richTextGenerating, richTextImageGenerating,
    editingHtmlElementId, editingHtmlSlideId,
    rtfSaveFailed,
    generateTextWithAI, generateImageWithAI,
    handleAddRichTextToSlide, handleEditHtmlElement,
    handleOpenRichText, handleCloseRichText,
  };
}
