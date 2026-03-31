import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useProject } from '../contexts/ProjectContext';
import { useTheme } from '../contexts/ThemeContext';
import { authHeaders } from '../contexts/AuthContext';
import { resolveAssetUrls } from '../utils/htmlUtils';
import { getApiUrl } from '../utils/apiUrl';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import { Slider } from '../components/ui/slider';
import { Switch } from '../components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/dialog';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '../components/ui/sheet';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../components/ui/tooltip';
import { toast } from 'sonner';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import {
  ArrowLeft,
  Sun,
  Moon,
  Save,
  Download,
  Play,
  Plus,
  Copy,
  Clipboard,
  Trash2,
  Type,
  Image,
  Square,
  Circle,
  Video,
  Music,
  Mic,
  MicOff,
  Pencil,
  ArrowUpRight,
  ArrowRight,
  Minus,
  MousePointer,
  Undo2,
  Redo2,
  Layers,
  Settings,
  ChevronUp,
  ChevronDown,
  Link,
  Loader2,
  Pause,
  StopCircle,
  Volume2,
  ExternalLink,
  Code,
  BookOpen,
  User,
  Sparkles,
  Eye,
  X,
  ChevronLeft,
  ChevronRight,
  SkipBack,
  Menu,
  Check,
  Film,
  RefreshCw,
  Clock,
  FileText,
  HelpCircle,
  Maximize2,
  Palette,
  Presentation,
  AlertTriangle,
  GitBranch,
  Trophy,
  Wrench,
} from 'lucide-react';
import SlideCanvas from '../components/editor/SlideCanvas';
import Timeline from '../components/editor/Timeline';
import AnnotationToolbar from '../components/editor/AnnotationToolbar';
import CoursePreview from '../components/editor/CoursePreview';
import SplitPreview from '../components/editor/SplitPreview';
import RichTextEditor from '../components/RichTextEditor';
import QuizGenerator from '../components/quiz/QuizGenerator';
import ScenarioCreator from '../components/scenario/ScenarioCreator';
import GamificationPanel from '../components/editor/GamificationPanel';

// Extracted components and hooks
import { getThumbAssetUrl, formatDuration, formatDateTime, formatTime, getStatusBadge } from './Editor/utils';
import SortableSlideItem from './Editor/components/SortableSlideItem';
import SortableLayerItem from './Editor/components/SortableLayerItem';
import { ElementProperties } from './Editor/components/ElementProperties';
import { SlideProperties } from './Editor/components/SlideProperties';
import { useHeygenIntegration } from './Editor/hooks/useHeygenIntegration';
import { useEditorExport } from './Editor/hooks/useEditorExport';
import { useEditorTTS } from './Editor/hooks/useEditorTTS';
import { useEditorAudio } from './Editor/hooks/useEditorAudio';
import { useEditorAI } from './Editor/hooks/useEditorAI';

// Extracted dialogs
import {
  ExportDialog, HeygenDialog, SlideVideoDialog, VideoLibraryDialog,
  TTSDialog, MediaDialog, AudioDialog, ButtonDialog, HtmlDialog,
  BulkTextColorDialog, DesignTemplateDialog, ImageGalleryDialog,
  FlipbookDialog, RichTextDialog,
} from './Editor/dialogs';

export default function Editor() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const {
    currentProject,
    currentSlideIndex,
    currentSlide,
    selectedElementId,
    selectedElement,
    loading,
    setCurrentSlideIndex,
    setSelectedElementId,
    fetchProject,
    saveCourse,
    addSlide,
    updateSlide,
    deleteSlide,
    duplicateSlide,
    reorderSlides,
    addElement,
    updateElement,
    deleteElement,
    uploadMedia,
    uploadSlideAudio,
    setGlobalAudio,
    removeGlobalAudio,
    updateGlobalAudioVolume,
    removeSlideAudio,
    updateSlideAudioVolume,
    updateSlideAudioTiming,
    updateAnnotation,
    deleteAnnotation,
    exportScorm,
  } = useProject();

  // ── Extracted Hooks ──
  const exportHook = useEditorExport({ currentProject, exportScorm, fetchProject });
  const {
    showExportDialog, setShowExportDialog, exportLoading, downloadUrl, downloadFilename,
    videoExportJobId, videoExportProgress, videoExportMessage,
    handleExport, handleExportHTML, handleExportVideo, resetExportDialog,
  } = exportHook;

  const heygenHook = useHeygenIntegration({ currentProject, currentSlide, projectId, addElement });
  const {
    showHeygenDialog, setShowHeygenDialog,
    heygenAvatars, heygenVoices, heygenLoading, heygenCreditsLoading, heygenGenerating,
    heygenVideoId, heygenVideoStatus, heygenVideoUrl, heygenElapsedTime, heygenCredits,
    heygenAvatarGenderFilter, setHeygenAvatarGenderFilter,
    heygenVoiceLanguageFilter, setHeygenVoiceLanguageFilter,
    heygenVoiceGenderFilter, setHeygenVoiceGenderFilter,
    heygenAvailableGenders, heygenAvailableLanguages,
    heygenConfig, setHeygenConfig,
    loadHeygenData, reloadHeygenAvatars, reloadHeygenVoices,
    handleOpenHeygenDialog, handleGenerateHeygenVideo,
    handleAddHeygenVideoToSlide, handleAddLibraryVideoToSlide,
    handleDeleteLibraryVideo, handleOpenVideoLibrary,
    scriptMode, setScriptMode,
    aiScriptTopic, setAiScriptTopic,
    aiScriptStyle, setAiScriptStyle,
    aiScriptDuration, setAiScriptDuration,
    aiGeneratingScript, handleGenerateAiScript,
    heygenOcrLoading, heygenOcrOptions, heygenOcrStyle, setHeygenOcrStyle,
    handleHeygenOcrGenerate, handleSelectHeygenOcrOption,
    showVideoLibrary, setShowVideoLibrary,
    videoLibraryItems, videoLibraryLoading, refreshingVideoId,
    loadVideoLibrary, refreshVideoStatus,
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
  } = heygenHook;

  const ttsHook = useEditorTTS({ currentProject, currentSlide, fetchProject, updateSlide });
  const {
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
  } = ttsHook;

  const audioHook = useEditorAudio({
    currentProject, currentSlide, currentSlideIndex,
    uploadSlideAudio, setGlobalAudio, removeGlobalAudio, removeSlideAudio,
    updateGlobalAudioVolume, updateSlideAudioVolume,
  });
  const {
    isRecording, recordingTime,
    showAudioDialog, setShowAudioDialog,
    audioFile, setAudioFile, audioTarget, setAudioTarget,
    playingAudioId, globalAudioVolume, slideAudioVolumes,
    getAudioUrl, playAudio, stopAudio,
    handleStartRecording, handleStopRecording,
    handleAudioUpload, handleRemoveGlobalAudio, handleRemoveSlideAudio,
    handleGlobalVolumeChange, handleGlobalVolumeCommit,
    handleSlideAudioVolumeChange, handleSlideAudioVolumeCommit,
  } = audioHook;

  const aiHook = useEditorAI({ currentProject, currentSlide, addElement, updateElement, fetchProject });
  const {
    showRichTextDialog, setShowRichTextDialog,
    richTextContent, setRichTextContent,
    richTextGenerating, richTextImageGenerating,
    editingHtmlElementId, editingHtmlSlideId, rtfSaveFailed,
    generateTextWithAI, generateImageWithAI,
    handleAddRichTextToSlide, handleEditHtmlElement,
    handleOpenRichText, handleCloseRichText,
  } = aiHook;

  // ── Local State ──
  const [showMediaDialog, setShowMediaDialog] = useState(false);
  const [mediaType, setMediaType] = useState('image');
  const [videoUrl, setVideoUrl] = useState('');
  const [annotationMode, setAnnotationMode] = useState(null);
  const [selectedAnnotationId, setSelectedAnnotationId] = useState(null);
  const [showTimeline, setShowTimeline] = useState(true);
  const [showTimelineExpanded, setShowTimelineExpanded] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [showSplitPreview, setShowSplitPreview] = useState(false);
  const [showButtonDialog, setShowButtonDialog] = useState(false);
  const [showHtmlDialog, setShowHtmlDialog] = useState(false);
  const [showFlipbookDialog, setShowFlipbookDialog] = useState(false);
  const [showBulkTextColorDialog, setShowBulkTextColorDialog] = useState(false);
  const [bulkTextColor, setBulkTextColor] = useState('#ffffff');
  const [bulkFontFamily, setBulkFontFamily] = useState('');
  const [bulkFontSize, setBulkFontSize] = useState('');
  const [buttonConfig, setButtonConfig] = useState({
    text: 'Clique aqui', url: '', icon: '', style: 'primary', openInNewTab: true,
  });
  const [htmlConfig, setHtmlConfig] = useState({ content: '' });
  const [aiHtmlPrompt, setAiHtmlPrompt] = useState('');
  const [aiHtmlResult, setAiHtmlResult] = useState('');
  const [aiHtmlLoading, setAiHtmlLoading] = useState(false);
  const [htmlDialogTab, setHtmlDialogTab] = useState('paste');
  const [flipbookConfig, setFlipbookConfig] = useState({ type: 'external', url: '', pages: [] });
  const [timelineTime, setTimelineTime] = useState(0);
  const [timelineIsPlaying, setTimelineIsPlaying] = useState(false);
  const [showQuizDialog, setShowQuizDialog] = useState(false);
  const [showScenarioDialog, setShowScenarioDialog] = useState(false);
  const [showGamificationPanel, setShowGamificationPanel] = useState(false);
  const [showDesignTemplateDialog, setShowDesignTemplateDialog] = useState(false);
  const [designTemplates, setDesignTemplates] = useState([]);
  const [applyingTemplate, setApplyingTemplate] = useState(false);
  const [showEditorGallery, setShowEditorGallery] = useState(false);
  const [galleryImages, setGalleryImages] = useState([]);
  const [galleryLoading, setGalleryLoading] = useState(false);
  const [gallerySearch, setGallerySearch] = useState('');
  const [copiedElement, setCopiedElement] = useState(null);
  const [fixingSimulators, setFixingSimulators] = useState(false);

  const fileInputRef = useRef(null);
  const API_URL = getApiUrl();
  const slides = currentProject?.course?.slides || [];

  // DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Handle drag end for slide reordering
  const handleDragEnd = useCallback(async (event) => {
    const { active, over } = event;
    
    if (!over || active.id === over.id) return;
    
    const slides = currentProject?.course?.slides || [];
    const oldIndex = slides.findIndex(s => s.id === active.id);
    const newIndex = slides.findIndex(s => s.id === over.id);
    
    if (oldIndex === -1 || newIndex === -1) return;
    
    // Create new order
    const newSlides = arrayMove(slides, oldIndex, newIndex);
    const newSlideIds = newSlides.map(s => s.id);
    
    try {
      await reorderSlides(newSlideIds);
      // Update current slide index if needed
      if (currentSlideIndex === oldIndex) {
        setCurrentSlideIndex(newIndex);
      } else if (currentSlideIndex > oldIndex && currentSlideIndex <= newIndex) {
        setCurrentSlideIndex(currentSlideIndex - 1);
      } else if (currentSlideIndex < oldIndex && currentSlideIndex >= newIndex) {
        setCurrentSlideIndex(currentSlideIndex + 1);
      }
      toast.success('Slides reordenados');
    } catch (err) {
      toast.error('Erro ao reordenar slides');
    }
  }, [currentProject, currentSlideIndex, reorderSlides, setCurrentSlideIndex]);

  // Copy element handler
  const handleCopyElement = useCallback((element) => {
    if (!element) return;
    // Store a deep copy of the element (without id)
    const { id, ...elementData } = element;
    setCopiedElement({
      ...elementData,
      // Store original slide reference for cross-slide paste
      sourceSlideId: currentSlide?.id
    });
    toast.success('Elemento copiado! Use Ctrl+V para colar');
  }, [currentSlide?.id]);

  // Paste element handler
  const handlePasteElement = useCallback(async () => {
    if (!copiedElement || !currentSlide?.id) return;
    
    try {
      // Create new element with offset position
      const newElement = {
        ...copiedElement,
        // Offset position slightly so pasted element is visible
        x: Math.min((copiedElement.x || 0) + 20, 900),
        y: Math.min((copiedElement.y || 0) + 20, 500),
        // Remove source reference
        sourceSlideId: undefined,
      };
      
      // Call API to create new element
      const response = await axios.post(
        `${API_URL}/api/projects/${currentProject?.id}/slides/${currentSlide.id}/elements`,
        newElement
      );
      
      if (response.data) {
        // Refresh project to get updated elements
        await fetchProject(currentProject?.id);
        setSelectedElementId(response.data.id);
        toast.success('Elemento colado!');
      }
    } catch (err) {
      console.error('Paste error:', err);
      toast.error('Erro ao colar elemento');
    }
  }, [copiedElement, currentSlide?.id, currentProject?.id, API_URL, fetchProject, setSelectedElementId]);

  // Handle layer reordering (zIndex)
  const handleLayerDragEnd = useCallback(async (event) => {
    const { active, over } = event;
    
    if (!over || active.id === over.id || !currentSlide) return;
    
    const elements = currentSlide.elements || [];
    // Sort by zIndex descending (top to bottom in UI)
    const sortedElements = [...elements].sort((a, b) => (b.zIndex || 0) - (a.zIndex || 0));
    
    const oldIndex = sortedElements.findIndex(e => e.id === active.id);
    const newIndex = sortedElements.findIndex(e => e.id === over.id);
    
    if (oldIndex === -1 || newIndex === -1) return;
    
    // Reorder the array
    const reorderedElements = arrayMove(sortedElements, oldIndex, newIndex);
    
    // Assign new zIndex values (higher index = lower in list = lower zIndex)
    const updates = reorderedElements.map((el, idx) => ({
      id: el.id,
      zIndex: reorderedElements.length - idx // Top item gets highest zIndex
    }));
    
    // Update each element's zIndex
    try {
      for (const update of updates) {
        await updateElement(currentSlide.id, update.id, { zIndex: update.zIndex });
      }
      toast.success('Camadas reordenadas');
    } catch (err) {
      toast.error('Erro ao reordenar camadas');
    }
  }, [currentSlide, updateElement]);

  useEffect(() => {
    if (projectId) {
      fetchProject(projectId);
    }
  }, [projectId, fetchProject]);

  // Apply design template to current project
  const handleApplyDesignTemplate = async (templateId) => {
    if (!currentProject?.id || !templateId) return;
    setApplyingTemplate(true);
    try {
      const res = await axios.post(`${API_URL}/api/projects/${currentProject.id}/apply-design-template`, {
        designTemplateId: templateId,
      });
      if (res.data?.status === 'ok') {
        toast.success(`Tema "${res.data.templateName}" aplicado a ${res.data.updatedSlides} slides!`);
        await fetchProject(currentProject.id);
        setShowDesignTemplateDialog(false);
      }
    } catch (e) {
      toast.error('Erro ao aplicar template: ' + (e.response?.data?.detail || e.message));
    } finally {
      setApplyingTemplate(false);
    }
  };

  // Open gallery and load images
  const handleOpenGallery = async () => {
    setShowEditorGallery(true);
    setGalleryLoading(true);
    try {
      const res = await axios.get(`${API_URL}/api/gallery/images`);
      setGalleryImages(res.data?.images || []);
    } catch (e) {
      toast.error('Erro ao carregar galeria');
    } finally {
      setGalleryLoading(false);
    }
  };

  // Add gallery image to current slide
  const handleSelectGalleryImage = async (img) => {
    if (!currentSlide) {
      toast.error('Selecione um slide primeiro');
      return;
    }
    try {
      const slideWidth = currentSlide?.width || 960;
      const slideHeight = currentSlide?.height || 540;
      await addElement(currentSlide.id, {
        type: 'image',
        x: Math.round(slideWidth * 0.55),
        y: Math.round(slideHeight * 0.1),
        width: Math.round(slideWidth * 0.4),
        height: Math.round(slideHeight * 0.5),
        src: img.imageUrl,
        objectFit: 'contain',
        style: { borderRadius: '12px' },
      });
      setShowEditorGallery(false);
      toast.success('Imagem da galeria adicionada ao slide!');
    } catch (e) {
      toast.error('Erro ao adicionar imagem: ' + e.message);
    }
  };

  // Reset timeline when slide changes
  useEffect(() => {
    setTimelineTime(0);
    setTimelineIsPlaying(false);
  }, [currentSlideIndex]);

  // (Volume sync and audio cleanup now in useEditorAudio hook)

  const handleSave = async () => {
    try {
      setIsSaving(true);
      await saveCourse();
      toast.success('Project saved!');
    } catch (err) {
      toast.error('Failed to save project');
    } finally {
      setIsSaving(false);
    }
  };

  const handleFixSimulators = async () => {
    if (!currentProject?.id) return;
    setFixingSimulators(true);
    try {
      const res = await fetch(`${API_URL}/api/projects/${currentProject.id}/fix-simulators`, {
        method: 'POST',
        credentials: 'include',
      });
      const data = await res.json();
      if (res.ok) {
        toast.success(data.message || `Simuladores corrigidos: ${data.fixed || 0}`);
        if (data.fixed > 0) {
          window.location.reload();
        }
      } else {
        toast.error(data.detail || 'Erro ao corrigir simuladores');
      }
    } catch (err) {
      toast.error('Erro ao conectar com o servidor');
    } finally {
      setFixingSimulators(false);
    }
  };

  const handleAddSlide = async () => {
    try {
      await addSlide();
      toast.success('Slide added');
    } catch (err) {
      toast.error('Failed to add slide');
    }
  };

  const handleDeleteSlide = async (slideId) => {
    if (currentProject?.course?.slides?.length <= 1) {
      toast.error('Cannot delete the last slide');
      return;
    }
    try {
      await deleteSlide(slideId);
      toast.success('Slide deleted');
    } catch (err) {
      toast.error('Failed to delete slide');
    }
  };

  const handleDuplicateSlide = async (slideId) => {
    try {
      await duplicateSlide(slideId);
      toast.success('Slide duplicated');
    } catch (err) {
      toast.error('Failed to duplicate slide');
    }
  };

  const handleDeleteAnnotation = async (annotationId) => {
    if (!currentSlide) return;
    try {
      await deleteAnnotation(currentSlide.id, annotationId);
      setSelectedAnnotationId(null);
      toast.success('Anotação excluída');
    } catch (err) {
      toast.error('Falha ao excluir anotação');
    }
  };

  const handleDeleteElement = async (elementId) => {
    if (!currentSlide) return;
    
    // First, clear the selection to prevent React from trying to reconcile removed DOM nodes
    setSelectedElementId(null);
    
    // Use requestAnimationFrame to ensure the selection update is processed first
    requestAnimationFrame(async () => {
      try {
        await deleteElement(currentSlide.id, elementId);
        toast.success('Elemento excluído');
      } catch (err) {
        toast.error('Falha ao excluir elemento');
      }
    });
  };

  const handleAddElement = async (type) => {
    if (!currentSlide) return;
    
    const elementData = {
      type,
      x: 100,
      y: 100,
      width: type === 'text' ? 300 : 200,
      height: type === 'text' ? 100 : 200,
      content: type === 'text' ? 'Double-click to edit' : null,
    };

    if (type === 'shape') {
      elementData.shapeType = 'rectangle';
      elementData.style = { fill: '#7C3AED', stroke: '#5B21B6' };
    }

    try {
      const element = await addElement(currentSlide.id, elementData);
      setSelectedElementId(element.id);
    } catch (err) {
      toast.error('Failed to add element');
    }
  };

  const handleAddMedia = async () => {
    if (mediaType === 'video') {
      if (!videoUrl.trim()) {
        toast.error('Please enter a video URL');
        return;
      }
      
      let embedUrl = videoUrl;
      let embedType = 'youtube';
      
      // Parse YouTube URL
      const youtubeMatch = videoUrl.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&]+)/);
      if (youtubeMatch) {
        embedUrl = `https://www.youtube.com/embed/${youtubeMatch[1]}?autoplay=1&rel=0`;
        embedType = 'youtube';
      }
      
      // Parse Vimeo URL
      const vimeoMatch = videoUrl.match(/vimeo\.com\/(\d+)/);
      if (vimeoMatch) {
        embedUrl = `https://player.vimeo.com/video/${vimeoMatch[1]}?autoplay=1`;
        embedType = 'vimeo';
      }

      // Get slide dimensions - video fills 100% of slide
      const slideWidth = currentSlide?.width || 960;
      const slideHeight = currentSlide?.height || 540;

      try {
        await addElement(currentSlide.id, {
          type: 'video',
          x: 0,
          y: 0,
          width: slideWidth,
          height: slideHeight,
          embedUrl,
          embedType,
        });
        setShowMediaDialog(false);
        setVideoUrl('');
        toast.success('Vídeo adicionado (100% do slide)');
      } catch (err) {
        toast.error('Failed to add video');
      }
    }
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      console.log('Starting image upload for slide:', currentSlide?.id);
      const media = await uploadMedia(file);
      console.log('Upload successful:', media);
      
      // Get slide dimensions for full coverage
      const slideWidth = currentSlide?.width || 960;
      const slideHeight = currentSlide?.height || 540;
      
      // Add image element that covers 100% of the slide
      // Using actual pixel dimensions (same as slide) for proper drag/resize support
      await addElement(currentSlide.id, {
        type: 'image',
        x: 0,
        y: 0,
        width: slideWidth,
        height: slideHeight,
        src: media.url,  // Store relative URL to prevent broken links after forks
        objectFit: 'contain', // Maintain aspect ratio within the container
      });
      toast.success('Imagem adicionada (100% do slide)');
    } catch (err) {
      console.error('Image upload error:', err);
      toast.error('Falha ao enviar imagem: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Add Button element
  const handleAddButton = async () => {
    if (!buttonConfig.url) {
      toast.error('Por favor, insira uma URL para o botão');
      return;
    }

    try {
      await addElement(currentSlide.id, {
        type: 'button',
        x: 100,
        y: 100,
        width: 200,
        height: 50,
        buttonText: buttonConfig.text || 'Clique aqui',
        buttonIcon: buttonConfig.icon,
        buttonStyle: buttonConfig.style,
        buttonUrl: buttonConfig.url,
        openInNewTab: buttonConfig.openInNewTab,
        style: {
          fontSize: 16,
          fontWeight: 'bold',
          borderRadius: 8,
        },
      });
      setShowButtonDialog(false);
      setButtonConfig({
        text: 'Clique aqui',
        url: '',
        icon: '',
        style: 'primary',
        openInNewTab: true,
      });
      toast.success('Botão adicionado');
    } catch (err) {
      toast.error('Falha ao adicionar botão');
    }
  };

  // Add HTML element
  const handleAddHtml = async () => {
    if (!htmlConfig.content) {
      toast.error('Por favor, insira o código HTML');
      return;
    }

    try {
      await addElement(currentSlide.id, {
        type: 'html',
        x: 50,
        y: 50,
        width: 400,
        height: 300,
        htmlContent: htmlConfig.content,
      });
      setShowHtmlDialog(false);
      setHtmlConfig({ content: '' });
      setAiHtmlPrompt('');
      setAiHtmlResult('');
      setHtmlDialogTab('paste');
      toast.success('Elemento HTML adicionado');
    } catch (err) {
      toast.error('Falha ao adicionar HTML');
    }
  };

  // Generate HTML with AI
  const handleGenerateHtmlAI = async () => {
    if (!aiHtmlPrompt.trim()) {
      toast.error('Digite uma descrição do que deseja gerar');
      return;
    }
    setAiHtmlLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/generate-html`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        credentials: 'include',
        body: JSON.stringify({
          prompt: aiHtmlPrompt,
          courseContext: currentProject?.title || '',
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Erro ao gerar HTML');
      }
      const data = await res.json();
      setAiHtmlResult(data.html || '');
      toast.success('HTML gerado com sucesso!');
    } catch (err) {
      toast.error(err.message || 'Erro ao gerar HTML');
    } finally {
      setAiHtmlLoading(false);
    }
  };

  // Insert AI-generated HTML
  const handleInsertAiHtml = async () => {
    if (!aiHtmlResult) {
      toast.error('Nenhum HTML gerado para inserir');
      return;
    }
    setHtmlConfig({ content: aiHtmlResult });
    try {
      await addElement(currentSlide.id, {
        type: 'html',
        x: 50,
        y: 50,
        width: 400,
        height: 300,
        htmlContent: aiHtmlResult,
      });
      setShowHtmlDialog(false);
      setHtmlConfig({ content: '' });
      setAiHtmlPrompt('');
      setAiHtmlResult('');
      setHtmlDialogTab('paste');
      toast.success('Elemento HTML adicionado');
    } catch (err) {
      toast.error('Falha ao adicionar HTML');
    }
  };

  // Add Flipbook element

  const handleBulkTextColorChange = async () => {
    if (!bulkTextColor && !bulkFontFamily && !bulkFontSize) return;
    const fontSizeNum = bulkFontSize ? parseFloat(bulkFontSize) : null;
    try {
      const updatedSlides = slides.map(slide => ({
        ...slide,
        elements: slide.elements.map(el => {
          if (el.type === 'text' || el.type === 'html') {
            const newStyle = { ...el.style };
            if (bulkTextColor) newStyle.color = bulkTextColor;
            if (bulkFontFamily) newStyle.fontFamily = bulkFontFamily;
            if (fontSizeNum) newStyle.fontSize = fontSizeNum;
            let newHtmlContent = el.htmlContent || '';
            if (newHtmlContent) {
              if (bulkTextColor) {
                newHtmlContent = newHtmlContent.replace(/color:\s*#[a-fA-F0-9]{3,8}/g, `color:${bulkTextColor}`);
                newHtmlContent = newHtmlContent.replace(/color:\s*rgba?\([^)]+\)/g, `color:${bulkTextColor}`);
              }
              if (bulkFontFamily) {
                newHtmlContent = newHtmlContent.replace(/font-family:\s*[^;}"]+/g, `font-family:${bulkFontFamily}`);
              }
              if (bulkFontSize) {
                newHtmlContent = newHtmlContent.replace(/font-size:\s*[^;}"]+/g, `font-size:${bulkFontSize}`);
              }
            }
            return { ...el, style: newStyle, htmlContent: newHtmlContent };
          }
          return el;
        }),
      }));
      for (const slide of updatedSlides) {
        for (const el of slide.elements) {
          const origEl = slides.find(s => s.id === slide.id)?.elements.find(e => e.id === el.id);
          if (origEl && (origEl.style?.color !== el.style?.color || origEl.style?.fontFamily !== el.style?.fontFamily || origEl.style?.fontSize !== el.style?.fontSize || origEl.htmlContent !== el.htmlContent)) {
            await updateElement(slide.id, el.id, { style: el.style, htmlContent: el.htmlContent });
          }
        }
      }
      const changes = [bulkTextColor && `cor ${bulkTextColor}`, bulkFontFamily && `fonte ${bulkFontFamily}`, bulkFontSize && `tamanho ${bulkFontSize}`].filter(Boolean).join(', ');
      toast.success(`Texto alterado (${changes}) em todos os slides`);
      setShowBulkTextColorDialog(false);
    } catch (err) {
      toast.error('Erro ao alterar texto: ' + err.message);
    }
  };


  const handleAddFlipbook = async () => {
    if (flipbookConfig.type === 'external' && !flipbookConfig.url) {
      toast.error('Por favor, insira a URL do flipbook');
      return;
    }

    try {
      await addElement(currentSlide.id, {
        type: 'flipbook',
        x: 50,
        y: 50,
        width: 600,
        height: 400,
        flipbookType: flipbookConfig.type,
        flipbookUrl: flipbookConfig.url,
        flipbookPages: flipbookConfig.pages,
      });
      setShowFlipbookDialog(false);
      setFlipbookConfig({ type: 'external', url: '', pages: [] });
      toast.success('Flipbook adicionado');
    } catch (err) {
      toast.error('Falha ao adicionar flipbook');
    }
  };

  // Add Quiz element
  const handleQuizCreated = async (quizData) => {
    try {
      await addElement(currentSlide.id, quizData);
      toast.success('Quiz adicionado ao slide!');
    } catch (err) {
      console.error('Failed to add quiz:', err);
      toast.error('Falha ao adicionar quiz');
    }
  };

  // Add Scenario element
  const handleScenarioCreated = async (scenario) => {
    if (!currentSlide) return;
    try {
      const slideWidth = currentSlide?.width || 1920;
      const slideHeight = currentSlide?.height || 820;
      await addElement(currentSlide.id, {
        type: 'scenario',
        x: 0,
        y: 0,
        width: slideWidth,
        height: slideHeight,
        content: scenario.id,
        scenarioData: scenario,
      });
      toast.success('Cenário adicionado ao slide!');
    } catch (err) {
      console.error('Failed to add scenario:', err);
      toast.error('Falha ao adicionar cenário');
    }
  };

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <TooltipProvider>
      {/* Course Preview Modal */}
      {showPreview && (
        <CoursePreview
          course={currentProject?.course}
          projectId={currentProject?.id}
          onClose={() => setShowPreview(false)}
        />
      )}
      
      <div className="h-screen w-screen overflow-hidden flex flex-col bg-background">
        {/* Header */}
        <header className="h-16 border-b border-border bg-card flex items-center px-4 justify-between z-50">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => navigate('/')} data-testid="back-btn">
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <Separator orientation="vertical" className="h-8" />
            <img 
              src="/didaxis-logo.png" 
              alt="Didaxis" 
              className="h-12 object-contain"
            />
            <span className="text-sm font-medium text-muted-foreground">Scormify</span>
            <Separator orientation="vertical" className="h-8" />
            <h1 className="font-semibold truncate max-w-[200px]">
              {currentProject?.name || 'Loading...'}
            </h1>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleSave}
              disabled={isSaving}
              className="gap-2"
              data-testid="save-btn"
            >
              {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Save
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              data-testid="theme-toggle-editor"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </Button>
            <Button 
              variant={showSplitPreview ? "secondary" : "outline"}
              className="gap-2" 
              onClick={() => setShowSplitPreview(!showSplitPreview)}
              data-testid="preview-btn"
            >
              <Eye className="w-4 h-4" />
              Visualizar
            </Button>
            <Button className="gap-2 btn-primary" onClick={() => setShowExportDialog(true)} data-testid="export-btn">
              <Download className="w-4 h-4" />
              Exportar
            </Button>
            <Button
              variant="outline"
              className="gap-2 border-cyan-700/50 text-cyan-300 hover:bg-cyan-900/20"
              onClick={() => navigate(`/agent?editMedia=${projectId}`)}
              data-testid="edit-media-btn"
            >
              <Settings className="w-4 h-4" />
              Editar Mídia
            </Button>
            <Button
              variant="outline"
              className="gap-2 border-amber-700/50 text-amber-300 hover:bg-amber-900/20"
              onClick={() => setShowBulkTextColorDialog(true)}
              data-testid="bulk-text-color-btn"
            >
              <Type className="w-4 h-4" />
              Cor do Texto
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  className="gap-2 border-slate-600/50 text-slate-300 hover:bg-slate-800/40"
                  data-testid="tools-menu-btn"
                >
                  <Wrench className="w-4 h-4" />
                  Ferramentas
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  onClick={handleFixSimulators}
                  disabled={fixingSimulators}
                  data-testid="fix-simulators-btn"
                >
                  {fixingSimulators ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4 mr-2" />
                  )}
                  {fixingSimulators ? 'Corrigindo...' : 'Corrigir Simuladores'}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <ExportDialog
              open={showExportDialog}
              onOpenChange={setShowExportDialog}
              resetExportDialog={resetExportDialog}
              downloadUrl={downloadUrl}
              downloadFilename={downloadFilename}
              exportLoading={exportLoading}
              videoExportJobId={videoExportJobId}
              videoExportProgress={videoExportProgress}
              videoExportMessage={videoExportMessage}
              handleExport={handleExport}
              handleExportHTML={handleExportHTML}
              handleExportVideo={handleExportVideo}
              currentProject={currentProject}
              fetchProject={fetchProject}
            />
          </div>
        </header>

        <div className="flex-1 flex overflow-hidden">
          {/* Left Sidebar - Slides (collapsible when split preview is active) */}
          <div className={`${showSplitPreview ? 'w-12' : 'w-64'} border-r border-border bg-card flex flex-col transition-all duration-300 shrink-0`}>
            {showSplitPreview ? (
              <>
                <div className="p-1.5 border-b border-border flex items-center justify-center">
                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setShowSplitPreview(false)} data-testid="expand-slides-btn">
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
                <ScrollArea className="flex-1">
                  <div className="py-1 space-y-1 flex flex-col items-center">
                    {slides.map((slide, index) => (
                      <button
                        key={slide.id}
                        className={`w-8 h-8 rounded text-xs font-medium transition-all ${
                          index === currentSlideIndex
                            ? 'bg-primary text-primary-foreground'
                            : 'text-muted-foreground hover:bg-muted'
                        }`}
                        onClick={() => setCurrentSlideIndex(index)}
                        data-testid={`collapsed-slide-${index}`}
                      >
                        {index + 1}
                      </button>
                    ))}
                  </div>
                </ScrollArea>
              </>
            ) : (
              <>
                <div className="p-3 border-b border-border flex items-center justify-between">
                  <span className="text-sm font-medium">Slides</span>
                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleAddSlide} data-testid="add-slide-btn">
                    <Plus className="w-4 h-4" />
                  </Button>
                </div>
                <ScrollArea className="flex-1">
                  <div className="p-3 space-y-2">
                    <DndContext
                      sensors={sensors}
                      collisionDetection={closestCenter}
                      onDragEnd={handleDragEnd}
                    >
                      <SortableContext
                        items={slides.map(s => s.id)}
                        strategy={verticalListSortingStrategy}
                      >
                        {slides.map((slide, index) => (
                          <SortableSlideItem
                            key={slide.id}
                            slide={slide}
                            index={index}
                            isActive={index === currentSlideIndex}
                            onClick={() => setCurrentSlideIndex(index)}
                            onDuplicate={handleDuplicateSlide}
                            onDelete={handleDeleteSlide}
                          />
                        ))}
                      </SortableContext>
                    </DndContext>
                  </div>
                </ScrollArea>
              </>
            )}
          </div>

          {/* Main Canvas Area */}
          <div className={`${showSplitPreview ? 'w-1/2 min-w-0' : 'flex-1'} flex flex-col overflow-hidden`}>
            {/* Toolbar */}
            <div className="h-12 border-b border-border bg-card/50 flex items-center px-4 gap-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant={annotationMode === null ? 'secondary' : 'ghost'}
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setAnnotationMode(null)}
                  >
                    <MousePointer className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Select</TooltipContent>
              </Tooltip>

              <Separator orientation="vertical" className="h-6" />

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => handleAddElement('text')}
                    data-testid="add-text-btn"
                  >
                    <Type className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Add Text</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-purple-400 hover:text-purple-300"
                    onClick={handleOpenRichText}
                    data-testid="add-rich-text-btn"
                  >
                    <Sparkles className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Texto com IA</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => fileInputRef.current?.click()}
                    data-testid="add-image-btn"
                  >
                    <Image className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Add Image</TooltipContent>
              </Tooltip>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleImageUpload}
              />

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => handleAddElement('shape')}
                    data-testid="add-shape-btn"
                  >
                    <Square className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Add Shape</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => {
                      setMediaType('video');
                      setShowMediaDialog(true);
                    }}
                    data-testid="add-video-btn"
                  >
                    <Video className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Add Video</TooltipContent>
              </Tooltip>

              <Separator orientation="vertical" className="h-6" />

              {/* New Elements: Button, HTML, Flipbook */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setShowButtonDialog(true)}
                    data-testid="add-button-btn"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Adicionar Botão/Link</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setShowHtmlDialog(true)}
                    data-testid="add-html-btn"
                  >
                    <Code className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Adicionar HTML</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setShowFlipbookDialog(true)}
                    data-testid="add-flipbook-btn"
                  >
                    <BookOpen className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Adicionar Flipbook</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 bg-gradient-to-r from-amber-500/10 to-orange-500/10 hover:from-amber-500/20 hover:to-orange-500/20"
                    onClick={() => {
                      if (designTemplates.length === 0) {
                        fetch(`${API_URL}/api/agent/design-templates`)
                          .then(r => r.json())
                          .then(setDesignTemplates)
                          .catch(() => toast.error('Erro ao carregar templates'));
                      }
                      setShowDesignTemplateDialog(true);
                    }}
                    data-testid="apply-template-btn"
                  >
                    <Palette className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Aplicar Tema Visual</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 bg-gradient-to-r from-yellow-500/10 to-amber-500/10 hover:from-yellow-500/20 hover:to-amber-500/20"
                    onClick={handleOpenGallery}
                    data-testid="gallery-btn"
                  >
                    <Image className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Galeria de Imagens IA</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 bg-gradient-to-r from-green-500/10 to-cyan-500/10 hover:from-green-500/20 hover:to-cyan-500/20"
                    onClick={() => setShowQuizDialog(true)}
                    data-testid="add-quiz-btn"
                  >
                    <HelpCircle className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>📝 Adicionar Quiz</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 bg-gradient-to-r from-cyan-500/10 to-blue-500/10 hover:from-cyan-500/20 hover:to-blue-500/20"
                    onClick={() => setShowScenarioDialog(true)}
                    data-testid="add-scenario-btn"
                  >
                    <GitBranch className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Cenário Interativo (IA)</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 bg-gradient-to-r from-yellow-500/10 to-orange-500/10 hover:from-yellow-500/20 hover:to-orange-500/20"
                    onClick={() => setShowGamificationPanel(true)}
                    data-testid="gamification-btn"
                  >
                    <Trophy className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Gamificação (Badges e Feedback)</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 bg-gradient-to-r from-purple-500/10 to-cyan-500/10 hover:from-purple-500/20 hover:to-cyan-500/20"
                    onClick={handleOpenHeygenDialog}
                    data-testid="add-avatar-btn"
                  >
                    <User className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>🎭 Criar Vídeo com Avatar (HeyGen)</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 bg-gradient-to-r from-amber-500/10 to-rose-500/10 hover:from-amber-500/20 hover:to-rose-500/20"
                    onClick={handleOpenSlideVideoDialog}
                    data-testid="slide-video-btn"
                  >
                    <Presentation className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Slides para Vídeo com Avatar</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 bg-gradient-to-r from-cyan-500/10 to-green-500/10 hover:from-cyan-500/20 hover:to-green-500/20"
                    onClick={handleOpenVideoLibrary}
                    data-testid="video-library-btn"
                  >
                    <Film className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>📹 Biblioteca de Vídeos</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 bg-gradient-to-r from-orange-500/10 to-amber-500/10 hover:from-orange-500/20 hover:to-amber-500/20"
                    onClick={handleOpenTTSDialog}
                    data-testid="tts-btn"
                  >
                    <Volume2 className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>🔊 Text-to-Speech (ElevenLabs)</TooltipContent>
              </Tooltip>

              <Separator orientation="vertical" className="h-6" />

              <AnnotationToolbar
                annotationMode={annotationMode}
                setAnnotationMode={setAnnotationMode}
              />

              <Separator orientation="vertical" className="h-6" />

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant={isRecording ? 'destructive' : 'ghost'}
                    size="icon"
                    className="h-8 w-8"
                    onClick={isRecording ? handleStopRecording : handleStartRecording}
                    data-testid="record-btn"
                  >
                    {isRecording ? <StopCircle className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>{isRecording ? 'Stop Recording' : 'Record Narration'}</TooltipContent>
              </Tooltip>
              
              {isRecording && (
                <span className="text-sm text-destructive font-mono animate-pulse">
                  {formatTime(recordingTime)}
                </span>
              )}
            </div>

            {/* Canvas */}
            <div className={`flex-1 bg-muted/30 overflow-auto flex items-center justify-center ${showSplitPreview ? 'p-2' : 'p-8'}`}>
              <SlideCanvas
                slide={currentSlide}
                selectedElementId={selectedElementId}
                onSelectElement={setSelectedElementId}
                onUpdateElement={(elementId, data) => {
                  if (currentSlide?.id) {
                    updateElement(currentSlide.id, elementId, data);
                  } else {
                    console.error('Cannot update element: currentSlide.id is undefined');
                  }
                }}
                onDeleteElement={(elementId) => {
                  handleDeleteElement(elementId);
                }}
                onCopyElement={handleCopyElement}
                onPasteElement={handlePasteElement}
                copiedElement={copiedElement}
                annotationMode={annotationMode}
                timelineTime={timelineTime}
                timelineIsPlaying={timelineIsPlaying}
                onEditHtmlElement={handleEditHtmlElement}
              />
            </div>

            {/* Timeline */}
            {showTimeline && (
              <Timeline
                slide={currentSlide}
                onUpdateSlide={(data) => updateSlide(currentSlide?.id, data)}
                onUpdateElement={(elementId, data) => updateElement(currentSlide?.id, elementId, data)}
                onUpdateAnnotation={(annotationId, data) => updateAnnotation(currentSlide?.id, annotationId, data)}
                onUpdateAudio={(audioId, data) => updateSlideAudioTiming(currentSlide?.id, audioId, data)}
                currentTime={timelineTime}
                isPlaying={timelineIsPlaying}
                onTimeChange={setTimelineTime}
                onPlayPause={setTimelineIsPlaying}
                onExpand={() => setShowTimelineExpanded(true)}
                onToggle={() => setShowTimeline(false)}
              />
            )}
            
            {/* Collapsed Timeline Bar */}
            {!showTimeline && (
              <div className="h-8 border-t border-border bg-card flex items-center px-4">
                <span className="text-xs text-muted-foreground">Timeline (oculta)</span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-auto h-6"
                  onClick={() => setShowTimeline(true)}
                >
                  <ChevronUp className="w-4 h-4 mr-1" />
                  Mostrar
                </Button>
              </div>
            )}
          </div>

          {/* Right Panel - Properties or Split Preview */}
          {showSplitPreview ? (
            <div className="w-1/2 min-w-0 border-l border-border flex flex-col">
              <SplitPreview
                course={currentProject?.course}
                projectId={currentProject?.id}
                currentSlideIndex={currentSlideIndex}
                onSlideChange={setCurrentSlideIndex}
                onExpandFullscreen={() => { setShowSplitPreview(false); setShowPreview(true); }}
                onClose={() => setShowSplitPreview(false)}
              />
            </div>
          ) : (
          <div className="w-72 border-l border-border bg-card flex flex-col">
            <Tabs defaultValue="properties" className="flex-1 flex flex-col">
              <TabsList className="w-full justify-start rounded-none border-b h-10 bg-transparent p-0">
                <TabsTrigger value="properties" className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary">
                  Properties
                </TabsTrigger>
                <TabsTrigger value="layers" className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary">
                  Layers
                </TabsTrigger>
                <TabsTrigger value="media" className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary">
                  Media
                </TabsTrigger>
              </TabsList>

              <TabsContent value="properties" className="flex-1 mt-0 overflow-hidden">
                <ScrollArea className="h-[calc(100vh-200px)]">
                  {selectedElement ? (
                    <ElementProperties
                      element={selectedElement}
                      onUpdate={(data) => updateElement(currentSlide?.id, selectedElement.id, data)}
                      slideWidth={currentSlide?.width || 960}
                      slideHeight={currentSlide?.height || 540}
                    />
                  ) : currentSlide ? (
                    <SlideProperties
                      slide={currentSlide}
                      onUpdate={(data) => updateSlide(currentSlide.id, data)}
                    />
                  ) : (
                    <div className="p-4 text-center text-muted-foreground">
                      Select a slide or element
                    </div>
                  )}
                </ScrollArea>
              </TabsContent>

              <TabsContent value="layers" className="flex-1 mt-0 overflow-hidden">
                <ScrollArea className="h-[calc(100vh-200px)]">
                  {(currentSlide?.elements?.length > 0 || currentSlide?.annotations?.length > 0) ? (
                    <div className="p-2 space-y-1">
                      {/* Elements - Sortable */}
                      {currentSlide.elements?.length > 0 && (
                        <div className="mb-2">
                          <div className="text-xs font-medium text-muted-foreground px-2 py-1 flex items-center justify-between">
                            <span>Elementos</span>
                            <span className="text-[10px] opacity-60">Arraste para reordenar</span>
                          </div>
                          <DndContext
                            sensors={sensors}
                            collisionDetection={closestCenter}
                            onDragEnd={handleLayerDragEnd}
                          >
                            <SortableContext
                              items={[...currentSlide.elements].sort((a, b) => (b.zIndex || 0) - (a.zIndex || 0)).map(e => e.id)}
                              strategy={verticalListSortingStrategy}
                            >
                              {[...currentSlide.elements]
                                .sort((a, b) => (b.zIndex || 0) - (a.zIndex || 0))
                                .map((element, index) => (
                                  <SortableLayerItem
                                    key={element.id}
                                    element={element}
                                    index={index}
                                    isSelected={selectedElementId === element.id}
                                    onClick={() => setSelectedElementId(element.id)}
                                    onDelete={() => handleDeleteElement(element.id)}
                                  />
                                ))}
                            </SortableContext>
                          </DndContext>
                        </div>
                      )}
                      
                      {/* Annotations */}
                      {currentSlide.annotations?.length > 0 && (
                        <div>
                          <div className="text-xs font-medium text-muted-foreground px-2 py-1">Anotações</div>
                          {currentSlide.annotations.map((annotation, idx) => (
                            <div
                              key={annotation.id}
                              className={`flex items-center gap-2 p-2 rounded cursor-pointer group ${
                                selectedAnnotationId === annotation.id ? 'bg-primary/10' : 'hover:bg-muted'
                              }`}
                              onClick={() => setSelectedAnnotationId(annotation.id)}
                            >
                              {annotation.type === 'arrow' && <ArrowRight className="w-4 h-4 text-orange-500" />}
                              {annotation.type === 'circle' && <Circle className="w-4 h-4 text-blue-500" />}
                              {annotation.type === 'rectangle' && <Square className="w-4 h-4 text-green-500" />}
                              {annotation.type === 'line' && <Minus className="w-4 h-4 text-purple-500" />}
                              {annotation.type === 'freehand' && <Pencil className="w-4 h-4 text-red-500" />}
                              <span className="text-sm truncate flex-1">
                                {annotation.type === 'arrow' ? 'Seta' :
                                 annotation.type === 'circle' ? 'Círculo' :
                                 annotation.type === 'rectangle' ? 'Retângulo' :
                                 annotation.type === 'line' ? 'Linha' :
                                 annotation.type === 'freehand' ? 'Desenho Livre' :
                                 `Anotação ${idx + 1}`}
                              </span>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6 opacity-0 group-hover:opacity-100"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteAnnotation(annotation.id);
                                }}
                              >
                                <Trash2 className="w-3 h-3 text-destructive" />
                              </Button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="p-4 text-center text-muted-foreground">
                      Nenhum elemento ou anotação
                    </div>
                  )}
                </ScrollArea>
              </TabsContent>

              <TabsContent value="media" className="flex-1 mt-0 overflow-hidden">
                <ScrollArea className="h-[calc(100vh-200px)]">
                  <div className="p-4 space-y-4">
                    {/* Audio Upload Section */}
                    <div>
                      <label className="text-sm font-medium mb-2 block">Add Audio</label>
                      <div className="space-y-3">
                        {/* Upload audio file button */}
                        <label className="block">
                          <div className="border border-dashed rounded-lg p-4 text-center cursor-pointer hover:border-primary/50 hover:bg-primary/5 transition-colors">
                            <Music className="w-8 h-8 mx-auto text-muted-foreground mb-2" />
                            <span className="text-sm font-medium">Upload Audio File</span>
                            <p className="text-xs text-muted-foreground mt-1">MP3, WAV, OGG</p>
                          </div>
                          <input
                            type="file"
                            accept="audio/*"
                            className="hidden"
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (file) {
                                setAudioFile(file);
                                setShowAudioDialog(true);
                              }
                              e.target.value = '';
                            }}
                            data-testid="audio-upload-input"
                          />
                        </label>
                      </div>
                    </div>

                    <Separator />

                    {/* Global Soundtrack */}
                    <div>
                      <label className="text-sm font-medium mb-2 flex items-center gap-2">
                        <Music className="w-4 h-4 text-primary" />
                        Trilha Sonora Global
                      </label>
                      {currentProject?.course?.globalAudio ? (
                        <div className="p-3 bg-primary/10 border border-primary/30 rounded-lg space-y-3">
                          <div className="flex items-center gap-2">
                            {/* Play/Stop Button */}
                            <Button
                              variant="ghost"
                              size="icon"
                              className={`h-8 w-8 flex-shrink-0 rounded-full ${
                                playingAudioId === 'global' 
                                  ? 'bg-primary text-primary-foreground hover:bg-primary/90' 
                                  : 'bg-primary/20 hover:bg-primary/30'
                              }`}
                              onClick={() => playAudio(
                                getAudioUrl(currentProject.course.globalAudio),
                                'global'
                              )}
                              data-testid="play-global-audio"
                            >
                              {playingAudioId === 'global' ? (
                                <Square className="w-3 h-3" />
                              ) : (
                                <Play className="w-3 h-3 ml-0.5" />
                              )}
                            </Button>
                            <div className="flex-1 min-w-0 overflow-hidden">
                              <p className="text-sm font-medium truncate max-w-[120px]">
                                {currentProject.course.globalAudio.filename}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                Toca em todos os slides
                              </p>
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 flex-shrink-0 text-destructive hover:text-destructive hover:bg-destructive/10"
                              onClick={handleRemoveGlobalAudio}
                              data-testid="remove-global-audio"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                          
                          {/* Volume Control */}
                          <div className="space-y-1">
                            <div className="flex items-center justify-between">
                              <label className="text-xs text-muted-foreground flex items-center gap-1">
                                <Volume2 className="w-3 h-3" />
                                Volume
                              </label>
                              <span className="text-xs font-medium">
                                {Math.round(globalAudioVolume * 100)}%
                              </span>
                            </div>
                            <Slider
                              value={[globalAudioVolume]}
                              min={0}
                              max={1}
                              step={0.05}
                              onValueChange={handleGlobalVolumeChange}
                              onValueCommit={handleGlobalVolumeCommit}
                              className="w-full"
                              data-testid="global-audio-volume"
                            />
                            <p className="text-xs text-muted-foreground">
                              Reduza para não sobrepor a narração
                            </p>
                          </div>
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground p-2 bg-muted/50 rounded">
                          Nenhuma trilha sonora definida
                        </p>
                      )}
                    </div>

                    <Separator />

                    {/* Current Slide Audio */}
                    <div>
                      <label className="text-sm font-medium mb-2 flex items-center gap-2">
                        <Mic className="w-4 h-4 text-slate-500" />
                        Áudio do Slide {currentSlideIndex + 1}
                      </label>
                      {currentSlide?.audio?.length > 0 ? (
                        <div className="space-y-3">
                          {currentSlide.audio.map((audio) => (
                            <div key={audio.id} className="p-3 bg-slate-500/10 border border-slate-500/30 rounded-lg space-y-2">
                              <div className="flex items-center gap-2">
                                {/* Play/Stop Button */}
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className={`h-8 w-8 flex-shrink-0 rounded-full ${
                                    playingAudioId === audio.id 
                                      ? 'bg-slate-500 text-white hover:bg-slate-600' 
                                      : 'bg-slate-500/20 hover:bg-slate-500/30'
                                  }`}
                                  onClick={() => playAudio(
                                    getAudioUrl(audio),
                                    audio.id
                                  )}
                                  data-testid={`play-slide-audio-${audio.id}`}
                                >
                                  {playingAudioId === audio.id ? (
                                    <Square className="w-3 h-3" />
                                  ) : (
                                    <Play className="w-3 h-3 ml-0.5" />
                                  )}
                                </Button>
                                <div className="flex-1 min-w-0 overflow-hidden">
                                  <p className="text-sm font-medium truncate max-w-[100px]">
                                    {audio.filename || audio.type}
                                  </p>
                                  <p className="text-xs text-muted-foreground">
                                    {audio.type === 'narration' ? 'Narração' : 'Música de fundo'}
                                  </p>
                                </div>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-8 w-8 flex-shrink-0 text-destructive hover:text-destructive hover:bg-destructive/10"
                                  onClick={() => handleRemoveSlideAudio(audio.id)}
                                  data-testid={`remove-slide-audio-${audio.id}`}
                                >
                                  <Trash2 className="w-4 h-4" />
                                </Button>
                              </div>
                              
                              {/* Volume Control for Slide Audio */}
                              <div className="space-y-1">
                                <div className="flex items-center justify-between">
                                  <label className="text-xs text-muted-foreground flex items-center gap-1">
                                    <Volume2 className="w-3 h-3" />
                                    Volume
                                  </label>
                                  <span className="text-xs font-medium">
                                    {Math.round((slideAudioVolumes[audio.id] ?? audio.volume ?? 1) * 100)}%
                                  </span>
                                </div>
                                <Slider
                                  value={[slideAudioVolumes[audio.id] ?? audio.volume ?? 1]}
                                  min={0}
                                  max={1}
                                  step={0.05}
                                  onValueChange={(value) => handleSlideAudioVolumeChange(audio.id, value)}
                                  onValueCommit={(value) => handleSlideAudioVolumeCommit(audio.id, value)}
                                  className="w-full"
                                  data-testid={`slide-audio-volume-${audio.id}`}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground p-2 bg-muted/50 rounded">
                          Nenhum áudio neste slide
                        </p>
                      )}
                    </div>
                  </div>
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </div>
          )}
        </div>

        <MediaDialog
          open={showMediaDialog} onOpenChange={setShowMediaDialog}
          videoUrl={videoUrl} setVideoUrl={setVideoUrl} handleAddMedia={handleAddMedia}
        />

        <AudioDialog
          open={showAudioDialog} onOpenChange={setShowAudioDialog}
          audioFile={audioFile} setAudioFile={setAudioFile}
          audioTarget={audioTarget} setAudioTarget={setAudioTarget}
          handleAudioUpload={handleAudioUpload}
        />

        <ButtonDialog
          open={showButtonDialog} onOpenChange={setShowButtonDialog}
          buttonConfig={buttonConfig} setButtonConfig={setButtonConfig}
          handleAddButton={handleAddButton}
        />

        <HtmlDialog
          open={showHtmlDialog} onOpenChange={setShowHtmlDialog}
          htmlConfig={htmlConfig} setHtmlConfig={setHtmlConfig}
          htmlDialogTab={htmlDialogTab} setHtmlDialogTab={setHtmlDialogTab}
          aiHtmlPrompt={aiHtmlPrompt} setAiHtmlPrompt={setAiHtmlPrompt}
          aiHtmlResult={aiHtmlResult} setAiHtmlResult={setAiHtmlResult}
          aiHtmlLoading={aiHtmlLoading}
          handleAddHtml={handleAddHtml} handleGenerateHtmlAI={handleGenerateHtmlAI} handleInsertAiHtml={handleInsertAiHtml}
        />

        <BulkTextColorDialog
          open={showBulkTextColorDialog} onOpenChange={setShowBulkTextColorDialog}
          bulkTextColor={bulkTextColor} setBulkTextColor={setBulkTextColor}
          bulkFontFamily={bulkFontFamily} setBulkFontFamily={setBulkFontFamily}
          bulkFontSize={bulkFontSize} setBulkFontSize={setBulkFontSize}
          slides={slides} handleBulkTextColorChange={handleBulkTextColorChange}
        />

        <DesignTemplateDialog
          open={showDesignTemplateDialog} onOpenChange={setShowDesignTemplateDialog}
          designTemplates={designTemplates} applyingTemplate={applyingTemplate}
          handleApplyDesignTemplate={handleApplyDesignTemplate}
        />

        <ImageGalleryDialog
          open={showEditorGallery} onOpenChange={setShowEditorGallery}
          galleryImages={galleryImages} galleryLoading={galleryLoading}
          gallerySearch={gallerySearch} setGallerySearch={setGallerySearch}
          handleSelectGalleryImage={handleSelectGalleryImage}
          API_URL={API_URL}
        />

        <FlipbookDialog
          open={showFlipbookDialog} onOpenChange={setShowFlipbookDialog}
          flipbookConfig={flipbookConfig} setFlipbookConfig={setFlipbookConfig}
          handleAddFlipbook={handleAddFlipbook}
        />

        <HeygenDialog
          open={showHeygenDialog} onOpenChange={setShowHeygenDialog}
          heygenLoading={heygenLoading} heygenGenerating={heygenGenerating}
          heygenAvatars={heygenAvatars} heygenVoices={heygenVoices}
          heygenConfig={heygenConfig} setHeygenConfig={setHeygenConfig}
          heygenAvatarGenderFilter={heygenAvatarGenderFilter} setHeygenAvatarGenderFilter={setHeygenAvatarGenderFilter} reloadHeygenAvatars={reloadHeygenAvatars}
          heygenVoiceLanguageFilter={heygenVoiceLanguageFilter} setHeygenVoiceLanguageFilter={setHeygenVoiceLanguageFilter}
          heygenVoiceGenderFilter={heygenVoiceGenderFilter} setHeygenVoiceGenderFilter={setHeygenVoiceGenderFilter} reloadHeygenVoices={reloadHeygenVoices}
          heygenAvailableLanguages={heygenAvailableLanguages}
          heygenCredits={heygenCredits} heygenCreditsLoading={heygenCreditsLoading}
          heygenVideoUrl={heygenVideoUrl} heygenVideoStatus={heygenVideoStatus} heygenElapsedTime={heygenElapsedTime}
          scriptMode={scriptMode} setScriptMode={setScriptMode}
          aiScriptTopic={aiScriptTopic} setAiScriptTopic={setAiScriptTopic}
          aiScriptStyle={aiScriptStyle} setAiScriptStyle={setAiScriptStyle}
          aiScriptDuration={aiScriptDuration} setAiScriptDuration={setAiScriptDuration}
          aiGeneratingScript={aiGeneratingScript}
          heygenOcrStyle={heygenOcrStyle} setHeygenOcrStyle={setHeygenOcrStyle}
          heygenOcrLoading={heygenOcrLoading} heygenOcrOptions={heygenOcrOptions}
          handleGenerateHeygenVideo={handleGenerateHeygenVideo} handleAddHeygenVideoToSlide={handleAddHeygenVideoToSlide}
          handleGenerateAiScript={handleGenerateAiScript} handleHeygenOcrGenerate={handleHeygenOcrGenerate} handleSelectHeygenOcrOption={handleSelectHeygenOcrOption}
          formatTime={formatTime} currentSlide={currentSlide}
        />

        <SlideVideoDialog
          open={showSlideVideoDialog} onOpenChange={setShowSlideVideoDialog}
          heygenLoading={heygenLoading} heygenAvatars={heygenAvatars} heygenVoices={heygenVoices}
          heygenConfig={heygenConfig} setHeygenConfig={setHeygenConfig}
          heygenCredits={heygenCredits}
          slideVideoStep={slideVideoStep} setSlideVideoStep={setSlideVideoStep}
          slideVideoScripts={slideVideoScripts} setSlideVideoScripts={setSlideVideoScripts}
          slideVideoScriptsLoading={slideVideoScriptsLoading}
          slideVideoGenerating={slideVideoGenerating} slideVideoBatchId={slideVideoBatchId} slideVideoBatchPolling={slideVideoBatchPolling}
          avatarSearch={avatarSearch} setAvatarSearch={setAvatarSearch}
          avatarGenderFilter={avatarGenderFilter} setAvatarGenderFilter={setAvatarGenderFilter}
          voiceLanguageFilter={voiceLanguageFilter} setVoiceLanguageFilter={setVoiceLanguageFilter}
          voiceGenderFilter={voiceGenderFilter} setVoiceGenderFilter={setVoiceGenderFilter}
          handleGenerateAllScripts={handleGenerateAllScripts} handleGenerateBatchSlideVideos={handleGenerateBatchSlideVideos}
        />

        <VideoLibraryDialog
          open={showVideoLibrary} onOpenChange={setShowVideoLibrary}
          videoLibraryItems={videoLibraryItems} videoLibraryLoading={videoLibraryLoading} refreshingVideoId={refreshingVideoId}
          loadVideoLibrary={loadVideoLibrary} refreshVideoStatus={refreshVideoStatus}
          handleAddLibraryVideoToSlide={handleAddLibraryVideoToSlide} handleDeleteLibraryVideo={handleDeleteLibraryVideo}
        />

        <TTSDialog
          open={showTTSDialog} onOpenChange={setShowTTSDialog}
          ttsVoices={ttsVoices} ttsLoading={ttsLoading} ttsGenerating={ttsGenerating}
          ttsGenderFilter={ttsGenderFilter} ttsSelectedVoice={ttsSelectedVoice} setTTSSelectedVoice={setTTSSelectedVoice}
          ttsText={ttsText} setTTSText={setTTSText}
          ttsAudioUrl={ttsAudioUrl}
          aiNarrationLoading={aiNarrationLoading} aiNarrationOptions={aiNarrationOptions} aiNarrationStyle={aiNarrationStyle} setAiNarrationStyle={setAiNarrationStyle}
          showAiNarrationOptions={showAiNarrationOptions} setShowAiNarrationOptions={setShowAiNarrationOptions} setAiNarrationOptions={setAiNarrationOptions}
          handleTTSGenderFilterChange={handleTTSGenderFilterChange}
          handleGenerateTTS={handleGenerateTTS} handleAddTTSToSlide={handleAddTTSToSlide}
          handleGenerateAiNarration={handleGenerateAiNarration} handleSelectAiNarration={handleSelectAiNarration}
          currentSlide={currentSlide}
        />

        <RichTextDialog
          open={showRichTextDialog} onOpenChange={setShowRichTextDialog}
          richTextContent={richTextContent} setRichTextContent={setRichTextContent}
          richTextGenerating={richTextGenerating} richTextImageGenerating={richTextImageGenerating}
          editingHtmlElementId={editingHtmlElementId}
          generateTextWithAI={generateTextWithAI} generateImageWithAI={generateImageWithAI}
          handleAddRichTextToSlide={handleAddRichTextToSlide} handleCloseRichText={handleCloseRichText}
        />

        {/* Quiz Generator Dialog */}
        <QuizGenerator
          open={showQuizDialog}
          onOpenChange={setShowQuizDialog}
          projectId={currentProject?.id}
          onQuizCreated={handleQuizCreated}
        />

        {/* Scenario Creator Dialog */}
        <ScenarioCreator
          open={showScenarioDialog}
          onOpenChange={setShowScenarioDialog}
          projectId={currentProject?.id}
          onScenarioCreated={handleScenarioCreated}
        />

        {/* Gamification Panel Dialog */}
        <Dialog open={showGamificationPanel} onOpenChange={setShowGamificationPanel}>
          <DialogContent className="max-w-3xl bg-slate-900 border-slate-700">
            <GamificationPanel 
              projectId={currentProject?.id}
              onClose={() => setShowGamificationPanel(false)}
            />
          </DialogContent>
        </Dialog>

        {/* Timeline Expandida - Sheet from bottom */}
        <Sheet open={showTimelineExpanded} onOpenChange={setShowTimelineExpanded}>
          <SheetContent 
            side="bottom" 
            className="h-[70vh] p-0 flex flex-col"
            data-testid="timeline-expanded-sheet"
          >
            <SheetHeader className="px-6 py-4 border-b shrink-0">
              <div className="flex items-center justify-between">
                <div>
                  <SheetTitle className="flex items-center gap-2">
                    <Clock className="w-5 h-5" />
                    Timeline Expandida
                  </SheetTitle>
                  <SheetDescription>
                    Arraste os elementos para configurar quando aparecem no slide
                  </SheetDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowTimelineExpanded(false)}
                  data-testid="close-timeline-expanded-btn"
                >
                  <X className="w-4 h-4 mr-2" />
                  Fechar
                </Button>
              </div>
            </SheetHeader>
            <div className="flex-1 overflow-hidden">
              <Timeline
                slide={currentSlide}
                onUpdateSlide={(data) => updateSlide(currentSlide?.id, data)}
                onUpdateElement={(elementId, data) => updateElement(currentSlide?.id, elementId, data)}
                onUpdateAnnotation={(annotationId, data) => updateAnnotation(currentSlide?.id, annotationId, data)}
                onUpdateAudio={(audioId, data) => updateSlideAudioTiming(currentSlide?.id, audioId, data)}
                currentTime={timelineTime}
                isPlaying={timelineIsPlaying}
                onTimeChange={setTimelineTime}
                onPlayPause={setTimelineIsPlaying}
                expanded={true}
              />
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </TooltipProvider>
  );
}

// ElementProperties and SlideProperties are now imported from ./Editor/components/

