import { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { getApiUrl } from '../../../utils/apiUrl';

export function useEditorTTS({ currentProject, currentSlide, fetchProject, updateSlide }) {
  const [showTTSDialog, setShowTTSDialog] = useState(false);
  const [ttsVoices, setTTSVoices] = useState([]);
  const [ttsLoading, setTTSLoading] = useState(false);
  const [ttsGenerating, setTTSGenerating] = useState(false);
  const [ttsGenderFilter, setTTSGenderFilter] = useState('all');
  const [ttsSelectedVoice, setTTSSelectedVoice] = useState(null);
  const [ttsText, setTTSText] = useState('');
  const [ttsPreviewUrl, setTTSPreviewUrl] = useState(null);
  const [ttsAudioUrl, setTTSAudioUrl] = useState(null);

  // AI Narration
  const [aiNarrationLoading, setAiNarrationLoading] = useState(false);
  const [aiNarrationOptions, setAiNarrationOptions] = useState([]);
  const [aiNarrationStyle, setAiNarrationStyle] = useState('educational');
  const [showAiNarrationOptions, setShowAiNarrationOptions] = useState(false);

  const API_URL = getApiUrl();

  const loadTTSVoices = async () => {
    setTTSLoading(true);
    try {
      const params = ttsGenderFilter !== 'all' ? `?gender=${ttsGenderFilter}` : '';
      const response = await axios.get(`${API_URL}/api/elevenlabs/voices${params}`);
      setTTSVoices(response.data.voices || []);
      if (response.data.voices?.length > 0 && !ttsSelectedVoice) {
        setTTSSelectedVoice(response.data.voices[0]);
      }
    } catch (err) {
      console.error('Error loading TTS voices:', err);
      toast.error('Falha ao carregar vozes do ElevenLabs');
    } finally {
      setTTSLoading(false);
    }
  };

  const handleOpenTTSDialog = () => {
    setShowTTSDialog(true);
    loadTTSVoices();
    setTTSText('');
    setTTSAudioUrl(null);
    setAiNarrationOptions([]);
    setShowAiNarrationOptions(false);
  };

  const handleTTSGenderFilterChange = async (gender) => {
    setTTSGenderFilter(gender);
    try {
      const params = gender !== 'all' ? `?gender=${gender}` : '';
      const response = await axios.get(`${API_URL}/api/elevenlabs/voices${params}`);
      setTTSVoices(response.data.voices || []);
      if (ttsSelectedVoice && !response.data.voices?.find(v => v.voice_id === ttsSelectedVoice.voice_id)) {
        setTTSSelectedVoice(response.data.voices?.[0] || null);
      }
    } catch (err) {
      console.error('Error reloading voices:', err);
    }
  };

  const handleGenerateTTS = async () => {
    if (!ttsText.trim() || !ttsSelectedVoice) return;
    setTTSGenerating(true);
    try {
      const response = await axios.post(`${API_URL}/api/elevenlabs/generate-speech`, {
        text: ttsText,
        voice_id: ttsSelectedVoice.voice_id,
        stability: 0.5,
        similarity_boost: 0.75,
      });
      if (response.data.success) {
        setTTSAudioUrl(response.data.audio_base64);
        toast.success('Audio gerado com sucesso!');
      }
    } catch (err) {
      console.error('Error generating TTS:', err);
      toast.error(err.response?.data?.detail || 'Falha ao gerar audio');
    } finally {
      setTTSGenerating(false);
    }
  };

  const handleAddTTSToSlide = async () => {
    if (!ttsAudioUrl || !currentSlide || !currentProject) return;
    try {
      const base64Data = ttsAudioUrl.split(',')[1];
      const byteCharacters = atob(base64Data);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: 'audio/mpeg' });
      const formData = new FormData();
      formData.append('file', blob, 'narration.mp3');
      formData.append('audio_type', 'narration');
      await axios.post(
        `${API_URL}/api/projects/${currentProject.id}/slides/${currentSlide.id}/audio`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      if (ttsText.trim() && !currentSlide.librasScript) {
        await updateSlide(currentSlide.id, { librasScript: ttsText.trim() });
        toast.success('Narracao adicionada ao slide! Script LIBRAS preenchido automaticamente.');
      } else {
        toast.success('Narracao adicionada ao slide!');
      }
      await fetchProject(currentProject.id);
      setShowTTSDialog(false);
      setTTSAudioUrl(null);
      setTTSText('');
    } catch (err) {
      console.error('Error adding audio to slide:', err);
      toast.error('Falha ao adicionar audio ao slide');
    }
  };

  const handlePlayTTSPreview = (previewUrl) => {
    setTTSPreviewUrl(ttsPreviewUrl === previewUrl ? null : previewUrl);
  };

  const handleGenerateAiNarration = async () => {
    if (!currentSlide || !currentProject) return;
    setAiNarrationLoading(true);
    setAiNarrationOptions([]);
    setShowAiNarrationOptions(true);
    try {
      const response = await axios.post(
        `${API_URL}/api/projects/${currentProject.id}/slides/${currentSlide.id}/generate-narration`,
        { slide_content: '', style: aiNarrationStyle, language: 'portugues brasileiro' }
      );
      setAiNarrationOptions(response.data.options || []);
    } catch (err) {
      console.error('Error generating AI narration:', err);
      toast.error(err.response?.data?.detail || 'Falha ao gerar narracao com IA');
      setShowAiNarrationOptions(false);
    } finally {
      setAiNarrationLoading(false);
    }
  };

  const handleSelectAiNarration = (text) => {
    setTTSText(text);
    setShowAiNarrationOptions(false);
    setAiNarrationOptions([]);
    toast.success('Texto de narracao selecionado!');
  };

  return {
    showTTSDialog, setShowTTSDialog,
    ttsVoices, ttsLoading, ttsGenerating,
    ttsGenderFilter, ttsSelectedVoice, setTTSSelectedVoice,
    ttsText, setTTSText,
    ttsPreviewUrl, ttsAudioUrl,
    aiNarrationLoading, aiNarrationOptions, aiNarrationStyle, setAiNarrationStyle,
    showAiNarrationOptions, setShowAiNarrationOptions, setAiNarrationOptions,
    handleOpenTTSDialog, handleTTSGenderFilterChange,
    handleGenerateTTS, handleAddTTSToSlide, handlePlayTTSPreview,
    handleGenerateAiNarration, handleSelectAiNarration,
  };
}
