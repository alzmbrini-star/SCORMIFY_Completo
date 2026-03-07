import { useState, useRef, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { getApiUrl } from '../../../utils/apiUrl';

const API_URL = getApiUrl();

export function useHeygenIntegration({ currentProject, currentSlide, projectId }) {
  // HeyGen Avatar Video states
  const [showHeygenDialog, setShowHeygenDialog] = useState(false);
  const [heygenAvatars, setHeygenAvatars] = useState([]);
  const [heygenVoices, setHeygenVoices] = useState([]);
  const [heygenLoading, setHeygenLoading] = useState(false);
  const [heygenCreditsLoading, setHeygenCreditsLoading] = useState(false);
  const [heygenGenerating, setHeygenGenerating] = useState(false);
  const [heygenVideoId, setHeygenVideoId] = useState(null);
  const [heygenVideoStatus, setHeygenVideoStatus] = useState(null);
  const [heygenVideoUrl, setHeygenVideoUrl] = useState(null);
  const [heygenElapsedTime, setHeygenElapsedTime] = useState(0);
  const [heygenCredits, setHeygenCredits] = useState(null);
  const [heygenAvatarGenderFilter, setHeygenAvatarGenderFilter] = useState('all');
  const [heygenVoiceLanguageFilter, setHeygenVoiceLanguageFilter] = useState('all');
  const [heygenVoiceGenderFilter, setHeygenVoiceGenderFilter] = useState('all');
  const [heygenAvailableGenders, setHeygenAvailableGenders] = useState([]);
  const [heygenAvailableLanguages, setHeygenAvailableLanguages] = useState([]);
  const [heygenConfig, setHeygenConfig] = useState({
    avatarId: '',
    voiceId: '',
    script: '',
    title: 'Avatar Video',
    transparentBackground: true,
  });
  const heygenTimerRef = useRef(null);

  // Video Library states
  const [showVideoLibrary, setShowVideoLibrary] = useState(false);
  const [videoLibraryItems, setVideoLibraryItems] = useState([]);
  const [videoLibraryLoading, setVideoLibraryLoading] = useState(false);
  const [refreshingVideoId, setRefreshingVideoId] = useState(null);

  // AI Script Generation states
  const [scriptMode, setScriptMode] = useState('manual');
  const [aiScriptTopic, setAiScriptTopic] = useState('');
  const [aiScriptStyle, setAiScriptStyle] = useState('educational');
  const [aiScriptDuration, setAiScriptDuration] = useState('medium');
  const [aiGeneratingScript, setAiGeneratingScript] = useState(false);
  const [heygenOcrLoading, setHeygenOcrLoading] = useState(false);
  const [heygenOcrOptions, setHeygenOcrOptions] = useState([]);
  const [heygenOcrStyle, setHeygenOcrStyle] = useState('educational');

  // Slide Video Generation states
  const [showSlideVideoDialog, setShowSlideVideoDialog] = useState(false);
  const [slideVideoScripts, setSlideVideoScripts] = useState([]);
  const [slideVideoGenerating, setSlideVideoGenerating] = useState(false);
  const [slideVideoScriptsLoading, setSlideVideoScriptsLoading] = useState(false);
  const [slideVideoBatchId, setSlideVideoBatchId] = useState(null);
  const [slideVideoBatchResults, setSlideVideoBatchResults] = useState([]);
  const [slideVideoBatchPolling, setSlideVideoBatchPolling] = useState(false);
  const [avatarGenderFilter, setAvatarGenderFilter] = useState('all');
  const [avatarSearch, setAvatarSearch] = useState('');
  const [voiceGenderFilter, setVoiceGenderFilter] = useState('all');
  const [voiceLanguageFilter, setVoiceLanguageFilter] = useState('Portuguese');
  const [slideVideoStep, setSlideVideoStep] = useState('setup');

  // Load HeyGen data
  const loadHeygenData = useCallback(async () => {
    setHeygenLoading(true);
    setHeygenCreditsLoading(true);
    try {
      const avatarParams = heygenAvatarGenderFilter !== 'all' ? `?gender=${heygenAvatarGenderFilter}` : '';
      const voiceParams = new URLSearchParams();
      if (heygenVoiceLanguageFilter !== 'all') voiceParams.append('language', heygenVoiceLanguageFilter);
      if (heygenVoiceGenderFilter !== 'all') voiceParams.append('gender', heygenVoiceGenderFilter);
      const voiceQuery = voiceParams.toString() ? `?${voiceParams.toString()}` : '';

      const [avatarsRes, voicesRes] = await Promise.all([
        axios.get(`${API_URL}/api/heygen/avatars${avatarParams}`),
        axios.get(`${API_URL}/api/heygen/voices${voiceQuery}`)
      ]);

      setHeygenAvatars(avatarsRes.data.avatars || []);
      setHeygenVoices(voicesRes.data.voices || []);
      if (avatarsRes.data.available_genders) setHeygenAvailableGenders(avatarsRes.data.available_genders);
      if (voicesRes.data.available_languages) setHeygenAvailableLanguages(voicesRes.data.available_languages);

      if (avatarsRes.data.avatars?.length > 0 && !heygenConfig.avatarId) {
        setHeygenConfig(prev => ({ ...prev, avatarId: avatarsRes.data.avatars[0].avatar_id }));
      }
      if (voicesRes.data.voices?.length > 0 && !heygenConfig.voiceId) {
        setHeygenConfig(prev => ({ ...prev, voiceId: voicesRes.data.voices[0].voice_id }));
      }
      setHeygenLoading(false);

      try {
        const creditsRes = await axios.get(`${API_URL}/api/heygen/credits`);
        if (creditsRes.data) setHeygenCredits(creditsRes.data);
      } catch (creditsErr) {
        console.warn('Could not load HeyGen credits:', creditsErr);
      } finally {
        setHeygenCreditsLoading(false);
      }
    } catch (err) {
      console.error('Error loading HeyGen data:', err);
      toast.error('Falha ao carregar dados do HeyGen. Verifique a API Key.');
      setHeygenLoading(false);
      setHeygenCreditsLoading(false);
    }
  }, [heygenAvatarGenderFilter, heygenVoiceLanguageFilter, heygenVoiceGenderFilter, heygenConfig.avatarId, heygenConfig.voiceId]);

  const reloadHeygenAvatars = async (gender) => {
    try {
      const params = gender !== 'all' ? `?gender=${gender}` : '';
      const response = await axios.get(`${API_URL}/api/heygen/avatars${params}`);
      setHeygenAvatars(response.data.avatars || []);
      if (heygenConfig.avatarId && !response.data.avatars?.find(a => a.avatar_id === heygenConfig.avatarId)) {
        setHeygenConfig(prev => ({ ...prev, avatarId: response.data.avatars?.[0]?.avatar_id || '' }));
      }
    } catch (err) {
      console.error('Error reloading avatars:', err);
    }
  };

  const reloadHeygenVoices = async (language, gender) => {
    try {
      const params = new URLSearchParams();
      if (language !== 'all') params.append('language', language);
      if (gender !== 'all') params.append('gender', gender);
      const query = params.toString() ? `?${params.toString()}` : '';
      const response = await axios.get(`${API_URL}/api/heygen/voices${query}`);
      setHeygenVoices(response.data.voices || []);
      if (heygenConfig.voiceId && !response.data.voices?.find(v => v.voice_id === heygenConfig.voiceId)) {
        setHeygenConfig(prev => ({ ...prev, voiceId: response.data.voices?.[0]?.voice_id || '' }));
      }
    } catch (err) {
      console.error('Error reloading voices:', err);
    }
  };

  // Open HeyGen single video dialog
  const handleOpenHeygenDialog = () => {
    setShowHeygenDialog(true);
    loadHeygenData();
    setHeygenVideoId(null);
    setHeygenVideoStatus(null);
    setHeygenVideoUrl(null);
    setHeygenElapsedTime(0);
    if (heygenTimerRef.current) {
      clearInterval(heygenTimerRef.current);
      heygenTimerRef.current = null;
    }
  };

  // Open Slide Video dialog
  const handleOpenSlideVideoDialog = () => {
    setShowSlideVideoDialog(true);
    loadHeygenData();
    const slides = currentProject?.course?.slides || [];
    setSlideVideoScripts(slides.map((s, i) => ({
      index: i, title: s.title || `Slide ${i + 1}`, script: '', enabled: true, status: 'pending',
    })));
    setSlideVideoBatchId(null);
    setSlideVideoBatchResults([]);
    setSlideVideoStep('setup');
    setAvatarGenderFilter('all');
    setAvatarSearch('');
    setVoiceLanguageFilter('Portuguese');
    setVoiceGenderFilter('all');
  };

  // Generate scripts for selected slides
  const handleGenerateAllScripts = async () => {
    const selectedIndices = slideVideoScripts.filter(s => s.enabled).map(s => s.index);
    if (selectedIndices.length === 0) { toast.error('Selecione pelo menos um slide'); return; }
    setSlideVideoScriptsLoading(true);
    try {
      const response = await axios.post(`${API_URL}/api/heygen/generate-all-slide-scripts?project_id=${currentProject.id}`, { selectedIndices });
      const scripts = response.data.scripts || [];
      setSlideVideoScripts(prev => prev.map(s => {
        const generated = scripts.find(g => g.index === s.index);
        return generated ? { ...s, script: generated.script, charCount: generated.charCount } : s;
      }));
      toast.success(`${scripts.length} scripts gerados com sucesso!`);
    } catch (err) {
      console.error('Error generating scripts:', err);
      toast.error('Falha ao gerar scripts');
    }
    setSlideVideoScriptsLoading(false);
  };

  // Generate batch slide videos
  const handleGenerateBatchSlideVideos = async () => {
    if (!heygenConfig.avatarId || !heygenConfig.voiceId) { toast.error('Selecione um avatar e uma voz'); return; }
    const enabledSlides = slideVideoScripts.filter(s => s.enabled && s.script.trim());
    if (enabledSlides.length === 0) { toast.error('Nenhum slide com script habilitado'); return; }

    setSlideVideoGenerating(true);
    try {
      toast.info('Preparando slides visuais...');
      try {
        await axios.post(`${API_URL}/api/heygen/render-all-slides/${currentProject.id}`, {
          selectedIndices: enabledSlides.map(s => s.index),
        });
      } catch (renderErr) { console.warn('Slide rendering warning:', renderErr); }

      toast.info('Enviando para HeyGen...');
      const response = await axios.post(`${API_URL}/api/heygen/generate-batch-slide-videos`, {
        project_id: currentProject.id,
        avatar_id: heygenConfig.avatarId,
        voice_id: heygenConfig.voiceId,
        slides: enabledSlides.map(s => ({ index: s.index, script: s.script, title: s.title })),
      });
      const data = response.data;
      setSlideVideoBatchId(data.batch_id);
      setSlideVideoBatchResults(data.results || []);
      setSlideVideoScripts(prev => prev.map(s => {
        const result = data.results?.find(r => r.slide_index === s.index);
        return result ? { ...s, status: result.status, videoId: result.video_id } : s;
      }));
      toast.success(`${data.processing} vídeos em processamento!`);
      setSlideVideoBatchPolling(true);
    } catch (err) {
      console.error('Error generating batch videos:', err);
      toast.error('Falha ao gerar vídeos em lote');
    }
    setSlideVideoGenerating(false);
  };

  // Poll batch status
  useEffect(() => {
    if (!slideVideoBatchId || !slideVideoBatchPolling) return;
    const interval = setInterval(async () => {
      try {
        const updatedScripts = [...slideVideoScripts];
        let allDone = true;
        for (const s of updatedScripts) {
          if (s.videoId && s.status === 'processing') {
            try {
              const res = await axios.get(`${API_URL}/api/heygen/videos/${s.videoId}/refresh`);
              s.status = res.data.status;
              s.videoUrl = res.data.video_url;
              s.thumbnailUrl = res.data.thumbnail_url;
              s.duration = res.data.duration;
              if (s.status === 'processing') allDone = false;
            } catch (e) { allDone = false; }
          }
        }
        setSlideVideoScripts(updatedScripts);
        if (allDone) {
          setSlideVideoBatchPolling(false);
          toast.success(`${updatedScripts.filter(s => s.status === 'completed').length} vídeos concluídos!`);
        }
      } catch (err) { console.error('Batch polling error:', err); }
    }, 8000);
    return () => clearInterval(interval);
  }, [slideVideoBatchId, slideVideoBatchPolling, slideVideoScripts]);

  // AI Script Generation
  const handleGenerateAiScript = async () => {
    if (!aiScriptTopic.trim()) { toast.error('Por favor, descreva o tema do vídeo'); return; }
    setAiGeneratingScript(true);
    try {
      const response = await axios.post(`${API_URL}/api/ai/generate-script`, {
        topic: aiScriptTopic, style: aiScriptStyle, duration: aiScriptDuration, language: 'português brasileiro'
      });
      setHeygenConfig(prev => ({ ...prev, script: response.data.script }));
      toast.success('Script gerado com sucesso!');
      setScriptMode('manual');
    } catch (err) {
      console.error('Error generating script:', err);
      toast.error(err.response?.data?.detail || 'Falha ao gerar script');
    } finally { setAiGeneratingScript(false); }
  };

  // HeyGen OCR
  const handleHeygenOcrGenerate = async () => {
    if (!currentSlide || !currentProject) return;
    setHeygenOcrLoading(true);
    setHeygenOcrOptions([]);
    try {
      const response = await axios.post(
        `${API_URL}/api/projects/${currentProject.id}/slides/${currentSlide.id}/generate-narration`,
        { slide_content: '', style: heygenOcrStyle, language: 'português brasileiro' }
      );
      setHeygenOcrOptions(response.data.options || []);
    } catch (err) {
      console.error('Error generating OCR script:', err);
      toast.error(err.response?.data?.detail || 'Falha ao ler slide e gerar script');
    } finally { setHeygenOcrLoading(false); }
  };

  const handleSelectHeygenOcrOption = (text) => {
    setHeygenConfig(prev => ({ ...prev, script: text }));
    setHeygenOcrOptions([]);
    setScriptMode('manual');
    toast.success('Script selecionado!');
  };

  // Generate single HeyGen video
  const handleGenerateHeygenVideo = async () => {
    if (!heygenConfig.avatarId || !heygenConfig.voiceId || !heygenConfig.script) {
      toast.error('Por favor, preencha todos os campos'); return;
    }
    if (heygenCredits && !heygenCredits.has_credits) {
      toast.error('Você não possui créditos suficientes na HeyGen.'); return;
    }
    setHeygenGenerating(true);
    setHeygenVideoStatus('processing');
    try {
      const response = await axios.post(`${API_URL}/api/heygen/generate-video`, {
        avatar_id: heygenConfig.avatarId, voice_id: heygenConfig.voiceId,
        script: heygenConfig.script, title: heygenConfig.title,
        aspect_ratio: '16:9', transparent_background: heygenConfig.transparentBackground,
        project_id: projectId
      });
      setHeygenVideoId(response.data.video_id);
      toast.success('Geração de vídeo iniciada! Aguarde...');
      try {
        const creditsRes = await axios.get(`${API_URL}/api/heygen/credits`);
        setHeygenCredits(creditsRes.data);
      } catch (e) {}
      pollHeygenVideoStatus(response.data.video_id);
    } catch (err) {
      console.error('Error generating video:', err);
      toast.error(err.response?.data?.detail || 'Falha ao gerar vídeo');
      setHeygenGenerating(false);
      setHeygenVideoStatus(null);
    }
  };

  const pollHeygenVideoStatus = async (videoId) => {
    setHeygenElapsedTime(0);
    if (heygenTimerRef.current) clearInterval(heygenTimerRef.current);
    heygenTimerRef.current = setInterval(() => setHeygenElapsedTime(prev => prev + 1), 1000);
    const stopTimer = () => { if (heygenTimerRef.current) { clearInterval(heygenTimerRef.current); heygenTimerRef.current = null; } };

    try {
      const eventSource = new EventSource(`${API_URL}/api/heygen/video-events/${videoId}`);
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === 'ping') return;
          if (data.status) setHeygenVideoStatus(data.status);
          if (data.status === 'completed' && data.video_url) {
            stopTimer(); setHeygenVideoUrl(data.video_url); setHeygenGenerating(false);
            toast.success('Vídeo gerado com sucesso!'); eventSource.close();
          } else if (data.status === 'failed' || data.status === 'error') {
            stopTimer(); setHeygenGenerating(false);
            toast.error('Falha na geração do vídeo.'); eventSource.close();
          } else if (data.event === 'timeout') {
            stopTimer(); setHeygenGenerating(false);
            toast.error('Tempo limite excedido (15 min).'); eventSource.close();
          }
        } catch (e) { console.error('Error parsing SSE event:', e); }
      };
      eventSource.onerror = () => { eventSource.close(); fallbackToPoll(videoId, stopTimer); };
    } catch (e) {
      console.error('Error setting up SSE:', e);
      fallbackToPoll(videoId, stopTimer);
    }
  };

  const fallbackToPoll = async (videoId, stopTimer) => {
    let attempts = 0;
    const poll = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/heygen/video-status/${videoId}`);
        const status = response.data.status;
        setHeygenVideoStatus(status);
        if (status === 'completed') {
          stopTimer(); setHeygenVideoUrl(response.data.video_url); setHeygenGenerating(false);
          toast.success('Vídeo gerado com sucesso!'); return;
        } else if (status === 'failed' || status === 'error') {
          stopTimer(); setHeygenGenerating(false);
          toast.error('Falha na geração do vídeo.'); return;
        }
        attempts++;
        if (attempts < 180) setTimeout(poll, 5000);
        else { stopTimer(); setHeygenGenerating(false); toast.error('Tempo limite excedido.'); }
      } catch (err) {
        attempts++;
        if (attempts < 180) setTimeout(poll, 5000);
        else { stopTimer(); setHeygenGenerating(false); }
      }
    };
    poll();
  };

  // Video Library
  const loadVideoLibrary = async () => {
    setVideoLibraryLoading(true);
    try {
      const response = await axios.get(`${API_URL}/api/heygen/videos`);
      setVideoLibraryItems(response.data.videos || []);
    } catch (err) {
      console.error('Error loading video library:', err);
      toast.error('Falha ao carregar biblioteca de vídeos');
    } finally { setVideoLibraryLoading(false); }
  };

  const refreshVideoStatus = async (videoId) => {
    setRefreshingVideoId(videoId);
    try {
      const response = await axios.get(`${API_URL}/api/heygen/videos/${videoId}/refresh`);
      setVideoLibraryItems(prev => prev.map(v => v.video_id === videoId ? { ...v, ...response.data } : v));
      if (response.data.status === 'completed') toast.success('Vídeo pronto!');
    } catch (err) {
      console.error('Error refreshing video:', err);
    } finally { setRefreshingVideoId(null); }
  };

  return {
    // HeyGen Dialog
    showHeygenDialog, setShowHeygenDialog,
    heygenAvatars, heygenVoices, heygenLoading, heygenCreditsLoading, heygenGenerating,
    heygenVideoId, heygenVideoStatus, heygenVideoUrl, heygenElapsedTime, heygenCredits,
    heygenAvatarGenderFilter, setHeygenAvatarGenderFilter,
    heygenVoiceLanguageFilter, setHeygenVoiceLanguageFilter,
    heygenVoiceGenderFilter, setHeygenVoiceGenderFilter,
    heygenAvailableGenders, heygenAvailableLanguages,
    heygenConfig, setHeygenConfig,
    // HeyGen Actions
    loadHeygenData, reloadHeygenAvatars, reloadHeygenVoices,
    handleOpenHeygenDialog, handleGenerateHeygenVideo,
    // AI Script
    scriptMode, setScriptMode,
    aiScriptTopic, setAiScriptTopic,
    aiScriptStyle, setAiScriptStyle,
    aiScriptDuration, setAiScriptDuration,
    aiGeneratingScript, handleGenerateAiScript,
    // OCR
    heygenOcrLoading, heygenOcrOptions, heygenOcrStyle, setHeygenOcrStyle,
    handleHeygenOcrGenerate, handleSelectHeygenOcrOption,
    // Video Library
    showVideoLibrary, setShowVideoLibrary,
    videoLibraryItems, videoLibraryLoading, refreshingVideoId,
    loadVideoLibrary, refreshVideoStatus,
    // Slide Video
    showSlideVideoDialog, setShowSlideVideoDialog,
    slideVideoScripts, setSlideVideoScripts,
    slideVideoGenerating, slideVideoScriptsLoading,
    slideVideoBatchId, slideVideoBatchPolling,
    avatarGenderFilter, setAvatarGenderFilter,
    avatarSearch, setAvatarSearch,
    voiceGenderFilter, setVoiceGenderFilter,
    voiceLanguageFilter, setVoiceLanguageFilter,
    slideVideoStep, setSlideVideoStep,
    handleOpenSlideVideoDialog, handleGenerateAllScripts, handleGenerateBatchSlideVideos,
  };
}
