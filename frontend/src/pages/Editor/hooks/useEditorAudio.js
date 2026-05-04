import { useState, useRef, useEffect } from 'react';
import { toast } from 'sonner';
import { getApiUrl } from '../../../utils/apiUrl';

export function useEditorAudio({
  currentProject, currentSlide, currentSlideIndex,
  uploadSlideAudio, setGlobalAudio, removeGlobalAudio, removeSlideAudio,
  updateGlobalAudioVolume, updateSlideAudioVolume,
}) {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [showAudioDialog, setShowAudioDialog] = useState(false);
  const [audioFile, setAudioFile] = useState(null);
  const [audioTarget, setAudioTarget] = useState('slide');
  // Slide-scoped audio type: narration | sfx | background
  // - narration: auto-plays when section is active (default for voiceovers)
  // - sfx: one-shot sound effect fired on section enter
  // - background: course-wide ambient loop (first `background` audio wins)
  const [audioType, setAudioType] = useState('narration');
  const [playingAudioId, setPlayingAudioId] = useState(null);
  const [globalAudioVolume, setGlobalAudioVolumeState] = useState(0.5);
  const [slideAudioVolumes, setSlideAudioVolumes] = useState({});

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recordingIntervalRef = useRef(null);
  const audioPlayerRef = useRef(null);
  const isRecordingRef = useRef(false);

  const API_URL = getApiUrl();

  // Reset on slide change
  useEffect(() => {
    if (isRecordingRef.current && mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      isRecordingRef.current = false;
      clearInterval(recordingIntervalRef.current);
      toast.info('Gravacao salva automaticamente ao trocar de slide');
    }
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current.currentTime = 0;
    }
  }, [currentSlideIndex]);

  // Sync volume states
  useEffect(() => {
    if (currentProject?.course?.globalAudio) {
      setGlobalAudioVolumeState(currentProject.course.globalAudio.volume ?? 0.5);
    }
    if (currentSlide?.audio) {
      const volumes = {};
      currentSlide.audio.forEach(audio => {
        volumes[audio.id] = audio.volume ?? 1;
      });
      setSlideAudioVolumes(volumes);
    }
  }, [currentProject?.course?.globalAudio, currentSlide?.audio]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
        audioPlayerRef.current = null;
      }
    };
  }, []);

  const getAudioUrl = (audioOrFilename) => {
    if (!audioOrFilename) return '';
    if (typeof audioOrFilename === 'object') {
      const path = audioOrFilename.url || audioOrFilename.src;
      if (path) return path.startsWith('http') ? path : `${API_URL}${path}`;
      if (!currentProject) return '';
      return `${API_URL}/api/projects/${currentProject.id}/assets/${audioOrFilename.filename}`;
    }
    if (!currentProject) return '';
    return `${API_URL}/api/projects/${currentProject.id}/assets/${audioOrFilename}`;
  };

  const playAudio = (audioUrl, audioId) => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current = null;
    }
    if (playingAudioId === audioId) {
      setPlayingAudioId(null);
      return;
    }
    const audio = new Audio(audioUrl);
    audio.volume = audioId === 'global' ? globalAudioVolume : (slideAudioVolumes[audioId] ?? 1);
    audio.onended = () => { setPlayingAudioId(null); audioPlayerRef.current = null; };
    audio.onerror = () => { toast.error('Erro ao reproduzir audio'); setPlayingAudioId(null); audioPlayerRef.current = null; };
    audioPlayerRef.current = audio;
    audio.play();
    setPlayingAudioId(audioId);
  };

  const stopAudio = () => {
    if (audioPlayerRef.current) { audioPlayerRef.current.pause(); audioPlayerRef.current = null; }
    setPlayingAudioId(null);
  };

  const handleStartRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];
      mediaRecorderRef.current.ondataavailable = (e) => { audioChunksRef.current.push(e.data); };
      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const file = new File([audioBlob], 'narration.webm', { type: 'audio/webm' });
        try {
          await uploadSlideAudio(currentSlide.id, file, 'narration');
          toast.success('Narration saved');
        } catch (err) { toast.error('Failed to save narration'); }
        stream.getTracks().forEach(track => track.stop());
      };
      mediaRecorderRef.current.start();
      setIsRecording(true);
      isRecordingRef.current = true;
      setRecordingTime(0);
      recordingIntervalRef.current = setInterval(() => { setRecordingTime(prev => prev + 1); }, 1000);
    } catch (err) { toast.error('Could not access microphone'); }
  };

  const handleStopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      isRecordingRef.current = false;
      clearInterval(recordingIntervalRef.current);
    }
  };

  const handleAudioUpload = async () => {
    if (!audioFile) return;
    try {
      if (audioTarget === 'global') {
        await setGlobalAudio(audioFile);
        toast.success('Trilha sonora global adicionada!');
      } else {
        // Slide-scoped upload uses the user-selected audio type
        // (narration / sfx / background) so the Single Page export can
        // render it correctly.
        await uploadSlideAudio(currentSlide.id, audioFile, audioType);
        const typeLabels = { narration: 'Narração', sfx: 'Efeito sonoro (SFX)', background: 'Música ambiente' };
        toast.success(`${typeLabels[audioType] || 'Áudio'} adicionado ao slide!`);
      }
      setShowAudioDialog(false);
      setAudioFile(null);
      setAudioTarget('slide');
      setAudioType('narration');
    } catch (err) { toast.error('Erro ao fazer upload do audio'); }
  };

  const handleRemoveGlobalAudio = async () => {
    if (!currentProject) return;
    try { await removeGlobalAudio(); toast.success('Trilha sonora removida'); }
    catch (err) { toast.error('Erro ao remover audio'); }
  };

  const handleRemoveSlideAudio = async (audioId) => {
    if (!currentSlide) return;
    if (playingAudioId === audioId) stopAudio();
    try { await removeSlideAudio(currentSlide.id, audioId); toast.success('Audio removido do slide'); }
    catch (err) { toast.error('Erro ao remover audio'); }
  };

  const handleGlobalVolumeChange = (value) => {
    const newVolume = value[0];
    setGlobalAudioVolumeState(newVolume);
    if (audioPlayerRef.current && playingAudioId === 'global') audioPlayerRef.current.volume = newVolume;
  };

  const handleGlobalVolumeCommit = async (value) => {
    if (!currentProject?.course?.globalAudio) return;
    try { await updateGlobalAudioVolume(value[0]); toast.success('Volume atualizado'); }
    catch (err) { console.error('Error updating volume:', err); toast.error('Erro ao atualizar volume'); }
  };

  const handleSlideAudioVolumeChange = (audioId, value) => {
    const newVolume = value[0];
    setSlideAudioVolumes(prev => ({ ...prev, [audioId]: newVolume }));
    if (audioPlayerRef.current && playingAudioId === audioId) audioPlayerRef.current.volume = newVolume;
  };

  const handleSlideAudioVolumeCommit = async (audioId, value) => {
    if (!currentSlide) return;
    try { await updateSlideAudioVolume(currentSlide.id, audioId, value[0]); toast.success('Volume atualizado'); }
    catch (err) { console.error('Error updating volume:', err); toast.error('Erro ao atualizar volume'); }
  };

  return {
    isRecording, recordingTime,
    showAudioDialog, setShowAudioDialog,
    audioFile, setAudioFile, audioTarget, setAudioTarget,
    audioType, setAudioType,
    playingAudioId, globalAudioVolume, slideAudioVolumes,
    getAudioUrl, playAudio, stopAudio,
    handleStartRecording, handleStopRecording,
    handleAudioUpload, handleRemoveGlobalAudio, handleRemoveSlideAudio,
    handleGlobalVolumeChange, handleGlobalVolumeCommit,
    handleSlideAudioVolumeChange, handleSlideAudioVolumeCommit,
  };
}
