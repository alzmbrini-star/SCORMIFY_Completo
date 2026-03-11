import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useProject } from '../contexts/ProjectContext';
import { useTheme } from '../contexts/ThemeContext';
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
} from 'lucide-react';
import SlideCanvas from '../components/editor/SlideCanvas';
import Timeline from '../components/editor/Timeline';
import AnnotationToolbar from '../components/editor/AnnotationToolbar';
import CoursePreview from '../components/editor/CoursePreview';
import SplitPreview from '../components/editor/SplitPreview';
import RichTextEditor from '../components/RichTextEditor';
import QuizGenerator from '../components/quiz/QuizGenerator';
import ScenarioCreator from '../components/scenario/ScenarioCreator';

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
    showExportDialog, setShowExportDialog, exportLoading, downloadUrl,
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
  const [buttonConfig, setButtonConfig] = useState({
    text: 'Clique aqui', url: '', icon: '', style: 'primary', openInNewTab: true,
  });
  const [htmlConfig, setHtmlConfig] = useState({ content: '' });
  const [flipbookConfig, setFlipbookConfig] = useState({ type: 'external', url: '', pages: [] });
  const [timelineTime, setTimelineTime] = useState(0);
  const [timelineIsPlaying, setTimelineIsPlaying] = useState(false);
  const [showQuizDialog, setShowQuizDialog] = useState(false);
  const [showScenarioDialog, setShowScenarioDialog] = useState(false);
  const [showDesignTemplateDialog, setShowDesignTemplateDialog] = useState(false);
  const [designTemplates, setDesignTemplates] = useState([]);
  const [applyingTemplate, setApplyingTemplate] = useState(false);
  const [showEditorGallery, setShowEditorGallery] = useState(false);
  const [galleryImages, setGalleryImages] = useState([]);
  const [galleryLoading, setGalleryLoading] = useState(false);
  const [gallerySearch, setGallerySearch] = useState('');
  const [copiedElement, setCopiedElement] = useState(null);

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
      toast.success('Elemento HTML adicionado');
    } catch (err) {
      toast.error('Falha ao adicionar HTML');
    }
  };

  // Add Flipbook element

  const handleBulkTextColorChange = async () => {
    if (!bulkTextColor) return;
    try {
      const updatedSlides = slides.map(slide => ({
        ...slide,
        elements: slide.elements.map(el => {
          if (el.type === 'text' || el.type === 'html') {
            // Update text color in style
            const newStyle = { ...el.style, color: bulkTextColor };
            // Also update htmlContent if it contains color styles
            let newHtmlContent = el.htmlContent || '';
            if (newHtmlContent) {
              // Replace color in inline styles
              newHtmlContent = newHtmlContent.replace(/color:\s*#[a-fA-F0-9]{3,8}/g, `color:${bulkTextColor}`);
              newHtmlContent = newHtmlContent.replace(/color:\s*rgba?\([^)]+\)/g, `color:${bulkTextColor}`);
            }
            return { ...el, style: newStyle, htmlContent: newHtmlContent };
          }
          return el;
        }),
      }));
      // Save all slides via API
      for (const slide of updatedSlides) {
        for (const el of slide.elements) {
          const origEl = slides.find(s => s.id === slide.id)?.elements.find(e => e.id === el.id);
          if (origEl && (origEl.style?.color !== el.style?.color || origEl.htmlContent !== el.htmlContent)) {
            await updateElement(slide.id, el.id, { style: el.style, htmlContent: el.htmlContent });
          }
        }
      }
      toast.success(`Cor de texto alterada para ${bulkTextColor} em todos os slides`);
      setShowBulkTextColorDialog(false);
    } catch (err) {
      toast.error('Erro ao alterar cor de texto: ' + err.message);
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
            <Dialog open={showExportDialog} onOpenChange={(open) => {
              setShowExportDialog(open);
              if (!open) {
                resetExportDialog();
              }
            }}>
              <DialogContent className="max-w-md">
                <DialogHeader>
                  <DialogTitle>Exportar Curso</DialogTitle>
                  <DialogDescription>
                    Escolha o formato de exportação do seu curso.
                  </DialogDescription>
                </DialogHeader>
                <div className="py-4 space-y-4">
                  {downloadUrl ? (
                    <div className="text-center">
                      <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4">
                        <Download className="w-8 h-8 text-green-500" />
                      </div>
                      <p className="mb-4">Seu arquivo está pronto!</p>
                      <Button 
                        className="w-full"
                        data-testid="download-export-btn"
                        onClick={async () => {
                          try {
                            // Fetch the file as blob to bypass iframe sandbox restrictions
                            const response = await fetch(downloadUrl);
                            const blob = await response.blob();
                            
                            // Get filename from URL
                            const filename = downloadUrl.split('/').pop() || 'export';
                            
                            // Create object URL and trigger download
                            const url = window.URL.createObjectURL(blob);
                            const link = document.createElement('a');
                            link.href = url;
                            link.download = filename;
                            document.body.appendChild(link);
                            link.click();
                            document.body.removeChild(link);
                            window.URL.revokeObjectURL(url);
                          } catch (error) {
                            console.error('Download error:', error);
                            // Fallback: open in new tab
                            window.open(downloadUrl, '_blank');
                          }
                        }}
                      >
                        Baixar Arquivo
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {/* Accessibility Settings */}
                      <div className="flex items-center justify-between p-3 border rounded-lg bg-muted/30">
                        <div className="flex items-center gap-2">
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 11v8a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-8"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/><path d="M14 11h3a1 1 0 0 1 1 1v1a2 2 0 0 1-2 2h-2"/><path d="M14 15v5a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1v-5"/></svg>
                          <div>
                            <span className="text-sm font-medium">Plugin LIBRAS (VLibras)</span>
                            <p className="text-[10px] text-muted-foreground">Avatar de acessibilidade em Língua de Sinais</p>
                          </div>
                        </div>
                        <Switch
                          data-testid="vlibras-toggle"
                          key={`vlibras-${currentProject?.enableVlibras}`}
                          defaultChecked={currentProject?.enableVlibras !== false}
                          onCheckedChange={(newVal) => {
                            fetch(`${getApiUrl()}/api/projects/${currentProject.id}`, {
                              method: 'PUT',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ enableVlibras: newVal })
                            }).then(() => fetchProject(currentProject.id))
                              .catch(err => console.error('VLibras toggle error:', err));
                          }}
                        />
                      </div>
                      
                      {/* SCORM Export Option */}
                      <div className="p-4 border rounded-lg hover:border-primary/50 transition-colors">
                        <div className="flex items-start gap-3">
                          <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center shrink-0">
                            <span className="text-xl">📦</span>
                          </div>
                          <div className="flex-1">
                            <h4 className="font-medium mb-1">SCORM 1.2</h4>
                            <p className="text-sm text-muted-foreground mb-3">
                              Pacote compatível com LMS (Moodle, Blackboard, etc.)
                            </p>
                            <Button
                              onClick={handleExport}
                              disabled={exportLoading}
                              className="w-full gap-2"
                              size="sm"
                              data-testid="generate-scorm-btn"
                            >
                              {exportLoading ? (
                                <>
                                  <Loader2 className="w-4 h-4 animate-spin" />
                                  Gerando...
                                </>
                              ) : (
                                <>
                                  <Download className="w-4 h-4" />
                                  Gerar SCORM
                                </>
                              )}
                            </Button>
                          </div>
                        </div>
                      </div>
                      
                      {/* HTML Standalone Export Option */}
                      <div className="p-4 border rounded-lg hover:border-primary/50 transition-colors">
                        <div className="flex items-start gap-3">
                          <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center shrink-0">
                            <span className="text-xl">🌐</span>
                          </div>
                          <div className="flex-1">
                            <h4 className="font-medium mb-1">HTML Standalone</h4>
                            <p className="text-sm text-muted-foreground mb-3">
                              Arquivo único para visualizar em qualquer navegador
                            </p>
                            <Button
                              onClick={handleExportHTML}
                              disabled={exportLoading}
                              variant="outline"
                              className="w-full gap-2"
                              size="sm"
                              data-testid="generate-html-btn"
                            >
                              {exportLoading ? (
                                <>
                                  <Loader2 className="w-4 h-4 animate-spin" />
                                  Gerando...
                                </>
                              ) : (
                                <>
                                  <Download className="w-4 h-4" />
                                  Gerar HTML
                                </>
                              )}
                            </Button>
                          </div>
                        </div>
                      </div>

                      {/* Video Export Option */}
                      <div className="p-4 border rounded-lg hover:border-primary/50 transition-colors">
                        <div className="flex items-start gap-3">
                          <div className="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center shrink-0">
                            <Film className="w-5 h-5 text-red-400" />
                          </div>
                          <div className="flex-1">
                            <h4 className="font-medium mb-1">Vídeo</h4>
                            <p className="text-sm text-muted-foreground mb-3">
                              Exportar como vídeo com narrações e vídeos HeyGen/YouTube
                            </p>
                            {videoExportJobId ? (
                              <div data-testid="video-export-progress">
                                <div className="w-full bg-muted rounded-full h-2 mb-2">
                                  <div
                                    className="bg-red-500 h-2 rounded-full transition-all duration-500"
                                    style={{ width: `${videoExportProgress}%` }}
                                  />
                                </div>
                                <p className="text-xs text-muted-foreground">{videoExportMessage}</p>
                              </div>
                            ) : (
                              <div className="flex gap-2">
                                <Button
                                  onClick={() => handleExportVideo('mp4')}
                                  disabled={exportLoading}
                                  variant="outline"
                                  className="flex-1 gap-2 border-red-500/30 text-red-400 hover:bg-red-500/10"
                                  size="sm"
                                  data-testid="generate-mp4-btn"
                                >
                                  <Film className="w-4 h-4" />
                                  MP4
                                </Button>
                                <Button
                                  onClick={() => handleExportVideo('webm')}
                                  disabled={exportLoading}
                                  variant="outline"
                                  className="flex-1 gap-2 border-orange-500/30 text-orange-400 hover:bg-orange-500/10"
                                  size="sm"
                                  data-testid="generate-webm-btn"
                                >
                                  <Film className="w-4 h-4" />
                                  WebM
                                </Button>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </DialogContent>
            </Dialog>
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

        {/* Media Dialog */}
        <Dialog open={showMediaDialog} onOpenChange={setShowMediaDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Video</DialogTitle>
            </DialogHeader>
            <div className="py-4">
              <Input
                placeholder="YouTube or Vimeo URL"
                value={videoUrl}
                onChange={(e) => setVideoUrl(e.target.value)}
                data-testid="video-url-input"
              />
              <p className="text-xs text-muted-foreground mt-2">
                Paste a YouTube or Vimeo URL to embed the video
              </p>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowMediaDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleAddMedia} data-testid="add-video-confirm-btn">
                Add Video
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Audio Upload Dialog */}
        <Dialog open={showAudioDialog} onOpenChange={(open) => {
          setShowAudioDialog(open);
          if (!open) {
            setAudioFile(null);
            setAudioTarget('slide');
          }
        }}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Adicionar Áudio</DialogTitle>
            </DialogHeader>
            <div className="py-4 space-y-4">
              {audioFile && (
                <div className="flex items-center gap-3 p-3 bg-muted rounded-lg">
                  <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
                    <Music className="w-5 h-5 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{audioFile.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {(audioFile.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                </div>
              )}
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Aplicar áudio em:</label>
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    type="button"
                    variant={audioTarget === 'slide' ? 'default' : 'outline'}
                    className="h-auto py-3 flex flex-col gap-1"
                    onClick={() => setAudioTarget('slide')}
                    data-testid="audio-target-slide"
                  >
                    <Mic className="w-5 h-5" />
                    <span className="text-xs">Slide Atual</span>
                  </Button>
                  <Button
                    type="button"
                    variant={audioTarget === 'global' ? 'default' : 'outline'}
                    className="h-auto py-3 flex flex-col gap-1"
                    onClick={() => setAudioTarget('global')}
                    data-testid="audio-target-global"
                  >
                    <Music className="w-5 h-5" />
                    <span className="text-xs">Todos os Slides</span>
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  {audioTarget === 'slide' 
                    ? 'O áudio será reproduzido apenas neste slide.' 
                    : 'O áudio será a trilha sonora de fundo para todo o curso.'}
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => {
                setShowAudioDialog(false);
                setAudioFile(null);
                setAudioTarget('slide');
              }}>
                Cancelar
              </Button>
              <Button 
                onClick={handleAudioUpload} 
                disabled={!audioFile}
                data-testid="confirm-audio-upload"
              >
                Adicionar Áudio
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Button Dialog */}
        <Dialog open={showButtonDialog} onOpenChange={setShowButtonDialog}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Adicionar Botão/Link</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <label className="text-sm font-medium">Texto do Botão</label>
                <Input
                  placeholder="Clique aqui"
                  value={buttonConfig.text}
                  onChange={(e) => setButtonConfig({ ...buttonConfig, text: e.target.value })}
                  data-testid="button-text-input"
                />
              </div>
              <div>
                <label className="text-sm font-medium">URL de Destino *</label>
                <Input
                  placeholder="https://exemplo.com"
                  value={buttonConfig.url}
                  onChange={(e) => setButtonConfig({ ...buttonConfig, url: e.target.value })}
                  data-testid="button-url-input"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Ícone (emoji ou texto)</label>
                <Input
                  placeholder="🔗 ou →"
                  value={buttonConfig.icon}
                  onChange={(e) => setButtonConfig({ ...buttonConfig, icon: e.target.value })}
                  data-testid="button-icon-input"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Estilo do Botão</label>
                <select
                  className="w-full h-10 px-3 rounded-md border bg-background"
                  value={buttonConfig.style}
                  onChange={(e) => setButtonConfig({ ...buttonConfig, style: e.target.value })}
                  data-testid="button-style-select"
                >
                  <option value="primary">Primário (Colorido)</option>
                  <option value="secondary">Secundário (Cinza)</option>
                  <option value="outline">Contorno</option>
                  <option value="ghost">Transparente</option>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="openNewTab"
                  checked={buttonConfig.openInNewTab}
                  onChange={(e) => setButtonConfig({ ...buttonConfig, openInNewTab: e.target.checked })}
                  className="rounded"
                />
                <label htmlFor="openNewTab" className="text-sm">Abrir em nova aba</label>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowButtonDialog(false)}>
                Cancelar
              </Button>
              <Button onClick={handleAddButton} data-testid="confirm-add-button">
                Adicionar Botão
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* HTML Dialog */}
        <Dialog open={showHtmlDialog} onOpenChange={setShowHtmlDialog}>
          <DialogContent className="sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle>Adicionar HTML Personalizado</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <label className="text-sm font-medium">Código HTML</label>
                <textarea
                  className="w-full h-64 p-3 rounded-md border bg-background font-mono text-sm"
                  placeholder="<div>Seu código HTML aqui...</div>"
                  value={htmlConfig.content}
                  onChange={(e) => setHtmlConfig({ ...htmlConfig, content: e.target.value })}
                  data-testid="html-content-input"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Suporta HTML, CSS inline e JavaScript básico. O código será renderizado dentro de um iframe isolado.
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowHtmlDialog(false)}>
                Cancelar
              </Button>
              <Button onClick={handleAddHtml} data-testid="confirm-add-html">
                Adicionar HTML
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Flipbook Dialog */}
        {/* Bulk Text Color Dialog */}
        <Dialog open={showBulkTextColorDialog} onOpenChange={setShowBulkTextColorDialog}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Alterar Cor do Texto — Todos os Slides</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <p className="text-sm text-muted-foreground">
                A cor selecionada será aplicada a todos os textos em todos os {slides.length} slides do curso.
              </p>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={bulkTextColor}
                  onChange={e => setBulkTextColor(e.target.value)}
                  className="w-12 h-12 rounded cursor-pointer border-0 bg-transparent"
                  data-testid="bulk-text-color-picker"
                />
                <Input
                  value={bulkTextColor}
                  onChange={e => setBulkTextColor(e.target.value)}
                  placeholder="#ffffff"
                  className="flex-1"
                  data-testid="bulk-text-color-hex"
                />
              </div>
              {/* Quick presets */}
              <div className="flex gap-2 flex-wrap">
                {['#ffffff', '#f1f5f9', '#e2e8f0', '#1e293b', '#0f172a', '#000000', '#fbbf24', '#34d399', '#60a5fa', '#f472b6'].map(c => (
                  <button
                    key={c}
                    onClick={() => setBulkTextColor(c)}
                    className={`w-8 h-8 rounded-full border-2 transition-transform hover:scale-110 ${bulkTextColor === c ? 'border-cyan-400 ring-2 ring-cyan-400/30' : 'border-slate-600'}`}
                    style={{ background: c }}
                    title={c}
                  />
                ))}
              </div>
              {/* Preview */}
              <div className="flex gap-2">
                {(slides.slice(0, 3)).map((s, i) => (
                  <div key={i} className="flex-1 h-12 rounded border border-slate-700 flex items-center justify-center text-xs font-medium" style={{ background: s.background || '#1e293b', color: bulkTextColor }}>
                    Slide {i + 1}
                  </div>
                ))}
              </div>
            </div>
            <div className="flex gap-3 justify-end">
              <Button variant="outline" onClick={() => setShowBulkTextColorDialog(false)}>Cancelar</Button>
              <Button onClick={handleBulkTextColorChange} className="bg-amber-600 hover:bg-amber-700" data-testid="apply-bulk-text-color">
                Aplicar a Todos os Slides
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Design Template Dialog */}
        <Dialog open={showDesignTemplateDialog} onOpenChange={setShowDesignTemplateDialog}>
          <DialogContent className="sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Palette className="w-5 h-5 text-amber-400" />
                Aplicar Tema Visual
              </DialogTitle>
            </DialogHeader>
            <div className="py-4">
              <p className="text-sm text-slate-400 mb-4">Selecione um tema para aplicar cores, fontes e estilos a todos os slides do curso</p>
              <div className="grid grid-cols-3 gap-3" data-testid="editor-design-template-grid">
                {designTemplates.map(dt => {
                  const p = dt.palette || {};
                  return (
                    <button
                      key={dt.id}
                      disabled={applyingTemplate}
                      onClick={() => handleApplyDesignTemplate(dt.id)}
                      className="relative overflow-hidden rounded-xl border border-slate-700 hover:border-amber-500 transition-all text-left group disabled:opacity-50"
                      data-testid={`editor-design-template-${dt.id}`}
                    >
                      <div className="aspect-[16/9] relative" style={{ background: p.primary || '#0f172a' }}>
                        <div className="absolute top-0 left-0 right-0 h-[6px]" style={{ background: p.accent || '#10b981' }} />
                        <div className="absolute bottom-0 left-0 right-0 h-[55%] mx-2 mb-1 rounded-t-sm" style={{ background: p.contentBg || '#f0fdf4' }}>
                          <div className="p-2 space-y-1">
                            <div className="h-1 rounded-full w-[60%]" style={{ background: (p.text || '#1e293b') + '88' }} />
                            <div className="h-0.5 rounded-full w-[80%]" style={{ background: (p.text || '#1e293b') + '44' }} />
                            <div className="h-0.5 rounded-full w-[50%]" style={{ background: (p.text || '#1e293b') + '44' }} />
                          </div>
                        </div>
                        <div className="absolute top-2 left-2 right-2 text-center">
                          <span style={{ fontFamily: dt.fonts?.heading, color: '#fff', fontSize: '11px', fontWeight: 700 }}>Aa</span>
                        </div>
                        <div className="absolute inset-0 bg-amber-500/0 group-hover:bg-amber-500/10 transition-colors flex items-center justify-center">
                          <span className="opacity-0 group-hover:opacity-100 transition-opacity text-xs text-white font-semibold bg-amber-600/80 px-3 py-1 rounded-full">Aplicar</span>
                        </div>
                      </div>
                      <div className="p-2 bg-slate-900/80">
                        <p className="font-medium text-xs" style={{ fontFamily: dt.fonts?.heading }}>{dt.name}</p>
                        <p className="text-[10px] text-slate-500 truncate">{dt.description}</p>
                      </div>
                    </button>
                  );
                })}
              </div>
              {applyingTemplate && (
                <div className="flex items-center justify-center gap-2 mt-4 text-amber-400">
                  <div className="w-4 h-4 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm">Aplicando tema...</span>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>

        {/* Image Gallery Dialog */}
        <Dialog open={showEditorGallery} onOpenChange={setShowEditorGallery}>
          <DialogContent className="sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Image className="w-5 h-5 text-amber-400" />
                Galeria de Imagens IA
              </DialogTitle>
            </DialogHeader>
            <div className="py-2">
              <Input
                value={gallerySearch}
                onChange={e => setGallerySearch(e.target.value)}
                placeholder="Buscar por palavras-chave ou projeto..."
                className="mb-3"
                data-testid="editor-gallery-search"
              />
              {galleryLoading ? (
                <div className="flex items-center justify-center py-12 text-muted-foreground">
                  <div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />
                  Carregando...
                </div>
              ) : galleryImages.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Image className="w-10 h-10 mx-auto mb-3 opacity-40" />
                  <p className="text-sm">Nenhuma imagem na galeria ainda.</p>
                  <p className="text-xs mt-1 opacity-60">As imagens geradas por IA serão salvas aqui automaticamente.</p>
                </div>
              ) : (
                <div className="grid grid-cols-3 gap-3 max-h-[50vh] overflow-y-auto">
                  {galleryImages
                    .filter(img => !gallerySearch || (img.keywords || '').toLowerCase().includes(gallerySearch.toLowerCase()) || (img.projectName || '').toLowerCase().includes(gallerySearch.toLowerCase()))
                    .map(img => (
                    <button
                      key={img.id}
                      onClick={() => handleSelectGalleryImage(img)}
                      className="group relative rounded-lg overflow-hidden border border-border hover:border-amber-500 transition-all aspect-[4/3]"
                      data-testid={`editor-gallery-img-${img.id}`}
                    >
                      <img
                        src={img.imageUrl.startsWith('/') ? `${API_URL}${img.imageUrl}` : img.imageUrl}
                        alt={img.keywords || ''}
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-2">
                        <p className="text-[10px] text-white/90 truncate">{img.keywords || 'Sem palavras-chave'}</p>
                        <p className="text-[9px] text-white/50 truncate">{img.projectName || ''}</p>
                      </div>
                      <div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <div className="bg-amber-500 text-black rounded-full p-1"><Plus className="w-3 h-3" /></div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
              <p className="text-[10px] text-muted-foreground text-center mt-2">
                {galleryImages.filter(img => !gallerySearch || (img.keywords || '').toLowerCase().includes(gallerySearch.toLowerCase()) || (img.projectName || '').toLowerCase().includes(gallerySearch.toLowerCase())).length} de {galleryImages.length} imagens
              </p>
            </div>
          </DialogContent>
        </Dialog>

        <Dialog open={showFlipbookDialog} onOpenChange={setShowFlipbookDialog}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Adicionar Flipbook</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <label className="text-sm font-medium">Tipo de Flipbook</label>
                <select
                  className="w-full h-10 px-3 rounded-md border bg-background"
                  value={flipbookConfig.type}
                  onChange={(e) => setFlipbookConfig({ ...flipbookConfig, type: e.target.value })}
                  data-testid="flipbook-type-select"
                >
                  <option value="external">URL Externa (FlipHTML5, Issuu, etc.)</option>
                  <option value="pdf">Upload de PDF</option>
                  <option value="images">Múltiplas Imagens</option>
                </select>
              </div>
              
              {flipbookConfig.type === 'external' && (
                <div>
                  <label className="text-sm font-medium">URL do Flipbook</label>
                  <Input
                    placeholder="https://fliphtml5.com/..."
                    value={flipbookConfig.url}
                    onChange={(e) => setFlipbookConfig({ ...flipbookConfig, url: e.target.value })}
                    data-testid="flipbook-url-input"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Cole a URL de embed do seu flipbook (FlipHTML5, Issuu, Flipsnack, etc.)
                  </p>
                </div>
              )}
              
              {flipbookConfig.type === 'pdf' && (
                <div>
                  <label className="text-sm font-medium">URL do PDF</label>
                  <Input
                    placeholder="https://exemplo.com/documento.pdf"
                    value={flipbookConfig.url}
                    onChange={(e) => setFlipbookConfig({ ...flipbookConfig, url: e.target.value })}
                    data-testid="flipbook-pdf-input"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    O PDF será exibido em um visualizador integrado.
                  </p>
                </div>
              )}
              
              {flipbookConfig.type === 'images' && (
                <div>
                  <label className="text-sm font-medium">URLs das Imagens (uma por linha)</label>
                  <textarea
                    className="w-full h-32 p-3 rounded-md border bg-background text-sm"
                    placeholder="https://exemplo.com/pagina1.jpg&#10;https://exemplo.com/pagina2.jpg"
                    value={flipbookConfig.pages.join('\n')}
                    onChange={(e) => setFlipbookConfig({ 
                      ...flipbookConfig, 
                      pages: e.target.value.split('\n').filter(url => url.trim()) 
                    })}
                    data-testid="flipbook-images-input"
                  />
                </div>
              )}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowFlipbookDialog(false)}>
                Cancelar
              </Button>
              <Button onClick={handleAddFlipbook} data-testid="confirm-add-flipbook">
                Adicionar Flipbook
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* HeyGen Avatar Video Dialog */}
        <Dialog open={showHeygenDialog} onOpenChange={setShowHeygenDialog}>
          <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <User className="w-5 h-5" />
                🎭 Criar Vídeo com Avatar (HeyGen)
              </DialogTitle>
            </DialogHeader>
            
            {/* Credits Display */}
            {heygenCreditsLoading ? (
              <div className="flex items-center justify-center p-3 rounded-lg border bg-slate-500/10 border-slate-500/30">
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                <span className="text-sm text-slate-400">Verificando créditos...</span>
              </div>
            ) : heygenCredits ? (
              <div className={`flex items-center justify-between p-3 rounded-lg border ${
                heygenCredits.has_credits 
                  ? 'bg-green-500/10 border-green-500/30' 
                  : 'bg-red-500/10 border-red-500/30'
              }`}>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">
                    {heygenCredits.has_credits ? '✅' : '⚠️'} Créditos HeyGen:
                  </span>
                  <span className={`font-bold ${heygenCredits.has_credits ? 'text-green-500' : 'text-red-500'}`}>
                    {heygenCredits.has_credits
                      ? `${heygenCredits.remaining_quota} créditos API`
                      : heygenCredits.has_plan_credits
                        ? `API: 0 | Plano: ${heygenCredits.plan_credit}`
                        : 'Sem créditos'}
                  </span>
                </div>
                {!heygenCredits.has_credits && heygenCredits.has_plan_credits && (
                  <p className="text-xs text-amber-400 mt-1">
                    Seus créditos do plano ({heygenCredits.plan_credit}) são para o Studio web. Para usar a API, verifique se sua chave API tem créditos habilitados em app.heygen.com
                  </p>
                )}
                {!heygenCredits.has_credits && (
                  <span className="text-xs text-red-500">
                    Recarregue para gerar vídeos
                  </span>
                )}
              </div>
            ) : null}
            
            {heygenLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
                <span className="ml-3">Carregando avatares e vozes...</span>
              </div>
            ) : (
              <div className="space-y-6 py-4">
                {/* Avatar Selection */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium">Selecionar Avatar</label>
                    <select
                      className="text-xs px-2 py-1 rounded border bg-background"
                      value={heygenAvatarGenderFilter}
                      onChange={(e) => {
                        setHeygenAvatarGenderFilter(e.target.value);
                        reloadHeygenAvatars(e.target.value);
                      }}
                      data-testid="heygen-avatar-gender-filter"
                    >
                      <option value="all">👥 Todos</option>
                      <option value="male">👨 Masculino</option>
                      <option value="female">👩 Feminino</option>
                    </select>
                  </div>
                  <div className="grid grid-cols-4 gap-2 max-h-48 overflow-y-auto p-2 border rounded-lg">
                    {heygenAvatars.map((avatar) => (
                      <div
                        key={avatar.avatar_id}
                        className={`cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${
                          heygenConfig.avatarId === avatar.avatar_id 
                            ? 'border-purple-500 ring-2 ring-purple-500/30' 
                            : 'border-transparent hover:border-gray-300'
                        }`}
                        onClick={() => setHeygenConfig({ ...heygenConfig, avatarId: avatar.avatar_id })}
                      >
                        <div className="relative">
                          <img
                            src={avatar.preview_image_url}
                            alt={avatar.avatar_name}
                            className="w-full aspect-square object-cover"
                          />
                          <span className="absolute top-1 right-1 text-xs bg-black/50 px-1 rounded">
                            {avatar.gender === 'male' ? '♂' : avatar.gender === 'female' ? '♀' : ''}
                          </span>
                        </div>
                        <div className="text-xs text-center py-1 truncate px-1">
                          {avatar.avatar_name}
                        </div>
                      </div>
                    ))}
                    {heygenAvatars.length === 0 && (
                      <div className="col-span-4 text-center py-8 text-muted-foreground">
                        Nenhum avatar disponível. Verifique sua API Key.
                      </div>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {heygenAvatars.length} avatares disponíveis
                  </div>
                </div>

                {/* Voice Selection */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium">Selecionar Voz</label>
                    <div className="flex gap-2">
                      <select
                        className="text-xs px-2 py-1 rounded border bg-background"
                        value={heygenVoiceLanguageFilter}
                        onChange={(e) => {
                          setHeygenVoiceLanguageFilter(e.target.value);
                          reloadHeygenVoices(e.target.value, heygenVoiceGenderFilter);
                        }}
                        data-testid="heygen-voice-language-filter"
                      >
                        <option value="all">🌐 Todos idiomas</option>
                        {heygenAvailableLanguages.map((lang) => (
                          <option key={lang.value} value={lang.value}>
                            {lang.label}
                          </option>
                        ))}
                      </select>
                      <select
                        className="text-xs px-2 py-1 rounded border bg-background"
                        value={heygenVoiceGenderFilter}
                        onChange={(e) => {
                          setHeygenVoiceGenderFilter(e.target.value);
                          reloadHeygenVoices(heygenVoiceLanguageFilter, e.target.value);
                        }}
                        data-testid="heygen-voice-gender-filter"
                      >
                        <option value="all">👥 Todos</option>
                        <option value="male">👨 Masculino</option>
                        <option value="female">👩 Feminino</option>
                      </select>
                    </div>
                  </div>
                  <select
                    className="w-full h-10 px-3 rounded-md border bg-background"
                    value={heygenConfig.voiceId}
                    onChange={(e) => setHeygenConfig({ ...heygenConfig, voiceId: e.target.value })}
                    data-testid="heygen-voice-select"
                  >
                    <option value="">Selecione uma voz...</option>
                    {heygenVoices.map((voice) => (
                      <option key={voice.voice_id} value={voice.voice_id}>
                        {voice.country_flag} {voice.name} ({voice.language}) - {voice.gender === 'male' ? '♂ Masc' : voice.gender === 'female' ? '♀ Fem' : voice.gender}
                      </option>
                    ))}
                  </select>
                  <div className="text-xs text-muted-foreground mt-1">
                    {heygenVoices.length} vozes disponíveis
                  </div>
                </div>

                {/* Script Input */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium">
                      Script do Vídeo
                      <span className="text-muted-foreground ml-2 text-xs">
                        ({heygenConfig.script.length}/5000 caracteres)
                      </span>
                    </label>
                    <div className="flex gap-1 bg-muted rounded-lg p-1">
                      <button
                        className={`px-3 py-1 text-xs rounded-md transition-all ${
                          scriptMode === 'manual' 
                            ? 'bg-background shadow-sm font-medium' 
                            : 'text-muted-foreground hover:text-foreground'
                        }`}
                        onClick={() => setScriptMode('manual')}
                      >
                        Digitar
                      </button>
                      <button
                        className={`px-3 py-1 text-xs rounded-md transition-all ${
                          scriptMode === 'ocr' 
                            ? 'bg-gradient-to-r from-purple-500 to-cyan-500 text-white font-medium' 
                            : 'text-muted-foreground hover:text-foreground'
                        }`}
                        onClick={() => setScriptMode('ocr')}
                        data-testid="heygen-ocr-tab"
                      >
                        <Sparkles className="w-3 h-3 inline mr-1" />Ler Slide
                      </button>
                      <button
                        className={`px-3 py-1 text-xs rounded-md transition-all ${
                          scriptMode === 'ai' 
                            ? 'bg-gradient-to-r from-purple-500 to-cyan-500 text-white font-medium' 
                            : 'text-muted-foreground hover:text-foreground'
                        }`}
                        onClick={() => setScriptMode('ai')}
                      >
                        Tema Livre
                      </button>
                    </div>
                  </div>

                  {scriptMode === 'manual' ? (
                    <>
                      <textarea
                        className="w-full h-40 p-3 rounded-md border bg-background text-sm"
                        placeholder="Digite o texto que o avatar irá narrar..."
                        value={heygenConfig.script}
                        onChange={(e) => setHeygenConfig({ ...heygenConfig, script: e.target.value.slice(0, 5000) })}
                        data-testid="heygen-script-input"
                      />
                      <p className="text-xs text-muted-foreground mt-1">
                        Dica: Escreva de forma natural, como se estivesse conversando. O avatar irá falar com sincronismo labial realista.
                      </p>
                    </>
                  ) : scriptMode === 'ocr' ? (
                    <div className="space-y-3 p-4 border rounded-lg bg-gradient-to-br from-purple-500/5 to-cyan-500/5">
                      <p className="text-sm text-muted-foreground">
                        A IA irá ler o conteúdo do slide atual (textos, imagens) e sugerir 3 opções de script para o avatar narrar.
                      </p>
                      <div className="flex items-center gap-3">
                        <select
                          data-testid="heygen-ocr-style-select"
                          className="text-sm px-3 py-2 rounded-md border bg-background flex-1"
                          value={heygenOcrStyle}
                          onChange={(e) => setHeygenOcrStyle(e.target.value)}
                        >
                          <option value="educational">Educativo</option>
                          <option value="conversational">Conversacional</option>
                          <option value="formal">Formal</option>
                          <option value="friendly">Amigável</option>
                        </select>
                        <Button
                          data-testid="heygen-ocr-generate-btn"
                          onClick={handleHeygenOcrGenerate}
                          disabled={heygenOcrLoading || !currentSlide}
                          className="bg-gradient-to-r from-purple-600 to-cyan-500 gap-2"
                        >
                          {heygenOcrLoading ? (
                            <><Loader2 className="w-4 h-4 animate-spin" />Lendo slide...</>
                          ) : (
                            <><Sparkles className="w-4 h-4" />Ler Slide e Gerar</>
                          )}
                        </Button>
                      </div>

                      {heygenOcrLoading && (
                        <div className="flex items-center justify-center py-6 border rounded-lg bg-purple-500/5 border-purple-500/20">
                          <Loader2 className="w-5 h-5 animate-spin text-purple-400 mr-2" />
                          <span className="text-sm text-purple-300">Analisando slide com Gemini Vision...</span>
                        </div>
                      )}

                      {heygenOcrOptions.length > 0 && (
                        <div data-testid="heygen-ocr-options" className="space-y-2">
                          <p className="text-xs font-medium text-muted-foreground">Escolha uma opção:</p>
                          {heygenOcrOptions.map((option, idx) => (
                            <div
                              key={idx}
                              data-testid={`heygen-ocr-option-${idx}`}
                              onClick={() => handleSelectHeygenOcrOption(option)}
                              className="cursor-pointer p-3 border rounded-lg transition-all hover:border-purple-500/60 hover:bg-purple-500/10 group"
                            >
                              <div className="flex items-start justify-between gap-2">
                                <div className="flex-1">
                                  <span className="text-xs font-semibold text-purple-400 mb-1 block">Opção {idx + 1}</span>
                                  <p className="text-sm leading-relaxed">{option}</p>
                                </div>
                                <Check className="w-4 h-4 text-purple-400 opacity-0 group-hover:opacity-100 transition-opacity mt-1 shrink-0" />
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-4 p-4 border rounded-lg bg-gradient-to-br from-purple-500/5 to-cyan-500/5">
                      <div>
                        <label className="text-sm font-medium mb-1 block">Tema do Vídeo</label>
                        <textarea
                          className="w-full h-24 p-3 rounded-md border bg-background text-sm"
                          placeholder="Descreva o tema do vídeo. Ex: Explique os benefícios do trabalho em equipe para empresas modernas, focando em produtividade e bem-estar..."
                          value={aiScriptTopic}
                          onChange={(e) => setAiScriptTopic(e.target.value)}
                          data-testid="ai-script-topic"
                        />
                      </div>
                      
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="text-sm font-medium mb-1 block">Estilo</label>
                          <select
                            className="w-full h-10 px-3 rounded-md border bg-background text-sm"
                            value={aiScriptStyle}
                            onChange={(e) => setAiScriptStyle(e.target.value)}
                          >
                            <option value="educational">📚 Educativo</option>
                            <option value="conversational">💬 Conversacional</option>
                            <option value="formal">👔 Formal</option>
                            <option value="friendly">😊 Amigável</option>
                          </select>
                        </div>
                        <div>
                          <label className="text-sm font-medium mb-1 block">Duração</label>
                          <select
                            className="w-full h-10 px-3 rounded-md border bg-background text-sm"
                            value={aiScriptDuration}
                            onChange={(e) => setAiScriptDuration(e.target.value)}
                          >
                            <option value="short">⚡ Curto (30s-1min)</option>
                            <option value="medium">📝 Médio (1-2min)</option>
                            <option value="long">📖 Longo (3-5min)</option>
                          </select>
                        </div>
                      </div>

                      <Button
                        onClick={handleGenerateAiScript}
                        disabled={aiGeneratingScript || !aiScriptTopic.trim()}
                        className="w-full bg-gradient-to-r from-purple-600 to-cyan-500"
                        data-testid="generate-ai-script-btn"
                      >
                        {aiGeneratingScript ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            Gerando script...
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-4 h-4 mr-2" />
                            Gerar Script com IA
                          </>
                        )}
                      </Button>

                      {heygenConfig.script && (
                        <div className="mt-3 p-3 bg-background rounded-md border">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-medium text-green-600">✓ Script gerado</span>
                            <button
                              className="text-xs text-muted-foreground hover:text-foreground"
                              onClick={() => setScriptMode('manual')}
                            >
                              Editar →
                            </button>
                          </div>
                          <p className="text-xs text-muted-foreground line-clamp-3">
                            {heygenConfig.script.slice(0, 200)}...
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Video Title */}
                <div>
                  <label className="text-sm font-medium">Título do Vídeo</label>
                  <Input
                    placeholder="Ex: Introdução ao Curso"
                    value={heygenConfig.title}
                    onChange={(e) => setHeygenConfig({ ...heygenConfig, title: e.target.value })}
                    data-testid="heygen-title-input"
                  />
                </div>

                {/* Transparent Background Option */}
                <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                  <input
                    type="checkbox"
                    id="transparent-bg"
                    checked={heygenConfig.transparentBackground}
                    onChange={(e) => setHeygenConfig({ ...heygenConfig, transparentBackground: e.target.checked })}
                    className="w-4 h-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                    data-testid="heygen-transparent-bg"
                  />
                  <label htmlFor="transparent-bg" className="flex-1 cursor-pointer">
                    <span className="text-sm font-medium">Fundo Transparente</span>
                    <p className="text-xs text-muted-foreground">
                      Gera o vídeo com fundo transparente (WebM) para sobrepor em slides
                    </p>
                  </label>
                </div>

                {/* Status Display */}
                {heygenGenerating && (
                  <div className="bg-purple-500/10 border border-purple-500/30 rounded-lg p-4">
                    <div className="flex items-center gap-3">
                      <Loader2 className="w-5 h-5 animate-spin text-purple-500" />
                      <div className="flex-1">
                        <div className="font-medium text-purple-700">Gerando vídeo com avatar...</div>
                        <div className="text-sm text-muted-foreground">
                          Status: <span className="capitalize">{heygenVideoStatus === 'processing' ? 'Processando' : heygenVideoStatus || 'Iniciando...'}</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-mono font-bold text-purple-600">
                          {formatTime(heygenElapsedTime)}
                        </div>
                        <div className="text-xs text-muted-foreground">decorrido</div>
                      </div>
                    </div>
                    
                    {/* Progress indicator */}
                    <div className="mt-3 space-y-2">
                      <div className="h-1.5 bg-purple-200 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-r from-purple-500 to-cyan-500 rounded-full animate-pulse"
                          style={{ width: '100%', animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite' }}
                        />
                      </div>
                      <div className="flex items-start gap-2 text-xs text-muted-foreground">
                        <span className="text-amber-600">⏱️</span>
                        <span>
                          A HeyGen está renderizando seu vídeo. Isso geralmente leva de <strong>2 a 10 minutos</strong> dependendo do tamanho do script. 
                          Você pode minimizar esta janela e continuar editando - será notificado quando estiver pronto.
                        </span>
                      </div>
                    </div>
                    
                    {/* Tips while waiting */}
                    {heygenElapsedTime > 120 && (
                      <div className="mt-3 p-2 bg-blue-500/10 rounded text-xs text-blue-700">
                        💡 <strong>Dica:</strong> Vídeos mais longos podem levar mais tempo. O tempo limite máximo é de 15 minutos.
                      </div>
                    )}
                  </div>
                )}

                {/* Video Ready */}
                {heygenVideoUrl && !heygenGenerating && (
                  <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center text-white">
                        ✓
                      </div>
                      <div className="font-medium text-green-700">Vídeo gerado com sucesso!</div>
                    </div>
                    <video
                      src={heygenVideoUrl}
                      controls
                      className="w-full rounded-lg"
                      style={{ maxHeight: '200px' }}
                    />
                  </div>
                )}
              </div>
            )}

            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={() => setShowHeygenDialog(false)}>
                Cancelar
              </Button>
              {heygenVideoUrl ? (
                <Button 
                  onClick={handleAddHeygenVideoToSlide}
                  className="bg-gradient-to-r from-purple-600 to-cyan-500"
                  data-testid="add-heygen-video-btn"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Adicionar ao Slide
                </Button>
              ) : (
                <Button 
                  onClick={handleGenerateHeygenVideo}
                  disabled={heygenGenerating || !heygenConfig.avatarId || !heygenConfig.voiceId || !heygenConfig.script}
                  className="bg-gradient-to-r from-purple-600 to-cyan-500"
                  data-testid="generate-heygen-video-btn"
                >
                  {heygenGenerating ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Gerando...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4 mr-2" />
                      Gerar Vídeo
                    </>
                  )}
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Slide Video Generation Dialog */}
        <Dialog open={showSlideVideoDialog} onOpenChange={setShowSlideVideoDialog}>
          <DialogContent className="sm:max-w-5xl max-h-[88vh] overflow-hidden flex flex-col">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Presentation className="w-5 h-5 text-amber-500" />
                Slides para Vídeo com Avatar
              </DialogTitle>
              <DialogDescription>
                Gere vídeos com avatar narrando cada slide do curso
              </DialogDescription>
            </DialogHeader>

            {/* Step indicator */}
            <div className="flex items-center gap-2 px-1">
              {['setup', 'scripts', 'generate'].map((step, i) => (
                <button key={step} onClick={() => setSlideVideoStep(step)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                    slideVideoStep === step ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' : 'text-muted-foreground hover:text-foreground'
                  }`}>
                  <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                    slideVideoStep === step ? 'bg-amber-500 text-black' : 'bg-muted'
                  }`}>{i + 1}</span>
                  {step === 'setup' ? 'Avatar e Voz' : step === 'scripts' ? 'Scripts' : 'Gerar'}
                </button>
              ))}
              {heygenCredits && (
                <div className={`ml-auto flex items-center gap-1.5 px-3 py-1 rounded-full text-xs ${heygenCredits.has_credits ? 'bg-green-500/10 text-green-400' : heygenCredits.has_plan_credits ? 'bg-amber-500/10 text-amber-400' : 'bg-red-500/10 text-red-400'}`}>
                  {heygenCredits.has_credits ? '✅' : '⚠️'}
                  {heygenCredits.has_credits
                    ? `${heygenCredits.remaining_quota} créditos API`
                    : heygenCredits.has_plan_credits
                      ? `API: 0 | Plano: ${heygenCredits.plan_credit}`
                      : '0 créditos'}
                </div>
              )}
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {/* ===== STEP 1: AVATAR & VOICE SELECTION ===== */}
              {slideVideoStep === 'setup' && (
                <>
                  {/* Avatar Section */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium">Avatar</label>
                      <div className="flex items-center gap-1.5">
                        <input
                          type="text"
                          placeholder="Buscar..."
                          value={avatarSearch}
                          onChange={e => setAvatarSearch(e.target.value)}
                          className="h-7 w-36 rounded-md border border-input bg-background px-2 text-xs"
                          data-testid="avatar-search-input"
                        />
                        {['all', 'male', 'female'].map(g => (
                          <button key={g} onClick={() => setAvatarGenderFilter(g)}
                            className={`px-2 py-1 rounded text-[11px] font-medium transition-all ${
                              avatarGenderFilter === g ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' : 'text-muted-foreground border border-transparent hover:border-border'
                            }`}
                            data-testid={`avatar-filter-${g}`}>
                            {g === 'all' ? 'Todos' : g === 'male' ? 'Masculino' : 'Feminino'}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="grid grid-cols-5 sm:grid-cols-6 md:grid-cols-8 gap-2 max-h-[240px] overflow-y-auto p-1" data-testid="avatar-grid">
                      {heygenLoading && heygenAvatars.length === 0 && (
                        <div className="col-span-full flex items-center justify-center py-8 text-sm text-muted-foreground">
                          <Loader2 className="w-5 h-5 animate-spin mr-2" /> Carregando avatares...
                        </div>
                      )}
                      {heygenAvatars
                        .filter(a => avatarGenderFilter === 'all' || a.gender === avatarGenderFilter)
                        .filter(a => !avatarSearch || (a.avatar_name || '').toLowerCase().includes(avatarSearch.toLowerCase()))
                        .slice(0, 48)
                        .map(a => (
                          <button key={a.avatar_id}
                            onClick={() => setHeygenConfig(prev => ({ ...prev, avatarId: a.avatar_id }))}
                            className={`group relative rounded-lg overflow-hidden border-2 transition-all aspect-[3/4] ${
                              heygenConfig.avatarId === a.avatar_id
                                ? 'border-amber-500 ring-2 ring-amber-500/30 scale-[1.02]'
                                : 'border-transparent hover:border-amber-500/40'
                            }`}
                            data-testid={`avatar-card-${a.avatar_id}`}>
                            {a.preview_image_url ? (
                              <img src={a.preview_image_url} alt={a.avatar_name}
                                className="w-full h-full object-cover" loading="lazy" />
                            ) : (
                              <div className="w-full h-full bg-muted flex items-center justify-center">
                                <User className="w-6 h-6 text-muted-foreground" />
                              </div>
                            )}
                            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-1.5">
                              <p className="text-[9px] text-white font-medium truncate leading-tight">{a.avatar_name}</p>
                              <p className="text-[8px] text-white/60">{a.gender === 'male' ? 'M' : 'F'}</p>
                            </div>
                            {heygenConfig.avatarId === a.avatar_id && (
                              <div className="absolute top-1 right-1 w-5 h-5 rounded-full bg-amber-500 flex items-center justify-center">
                                <Check className="w-3 h-3 text-black" />
                              </div>
                            )}
                          </button>
                        ))}
                    </div>
                    {heygenConfig.avatarId && (
                      <p className="text-xs text-amber-400">
                        Selecionado: {heygenAvatars.find(a => a.avatar_id === heygenConfig.avatarId)?.avatar_name || heygenConfig.avatarId}
                      </p>
                    )}
                  </div>

                  {/* Voice Section */}
                  <div className="space-y-2 border-t border-border pt-3">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium">Voz</label>
                      <div className="flex items-center gap-1.5">
                        <select value={voiceLanguageFilter}
                          onChange={e => setVoiceLanguageFilter(e.target.value)}
                          className="h-7 rounded-md border border-input bg-background px-2 text-xs"
                          data-testid="voice-language-filter">
                          <option value="">Todos idiomas</option>
                          <option value="Portuguese">Português</option>
                          <option value="English">Inglês</option>
                          <option value="Spanish">Espanhol</option>
                          <option value="French">Francês</option>
                          <option value="German">Alemão</option>
                          <option value="Italian">Italiano</option>
                        </select>
                        {['all', 'male', 'female'].map(g => (
                          <button key={g} onClick={() => setVoiceGenderFilter(g)}
                            className={`px-2 py-1 rounded text-[11px] font-medium transition-all ${
                              voiceGenderFilter === g ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'text-muted-foreground border border-transparent hover:border-border'
                            }`}
                            data-testid={`voice-filter-${g}`}>
                            {g === 'all' ? 'Todos' : g === 'male' ? 'Masculino' : 'Feminino'}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 max-h-[180px] overflow-y-auto" data-testid="voice-list">
                      {heygenLoading && heygenVoices.length === 0 && (
                        <div className="col-span-full flex items-center justify-center py-6 text-sm text-muted-foreground">
                          <Loader2 className="w-5 h-5 animate-spin mr-2" /> Carregando vozes...
                        </div>
                      )}
                      {heygenVoices
                        .filter(v => !voiceLanguageFilter || (v.language || '').includes(voiceLanguageFilter))
                        .filter(v => voiceGenderFilter === 'all' || v.gender === voiceGenderFilter)
                        .slice(0, 60)
                        .map(v => (
                          <button key={v.voice_id}
                            onClick={() => setHeygenConfig(prev => ({ ...prev, voiceId: v.voice_id }))}
                            className={`flex items-center gap-2 px-2.5 py-2 rounded-lg border text-left transition-all ${
                              heygenConfig.voiceId === v.voice_id
                                ? 'border-cyan-500 bg-cyan-500/10'
                                : 'border-border/50 hover:border-cyan-500/40'
                            }`}
                            data-testid={`voice-card-${v.voice_id}`}>
                            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                              v.gender === 'male' ? 'bg-blue-500/20 text-blue-400' : 'bg-pink-500/20 text-pink-400'
                            }`}>
                              {v.gender === 'male' ? 'M' : 'F'}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium truncate">{v.display_name || v.name}</p>
                              <p className="text-[10px] text-muted-foreground">{v.language}</p>
                            </div>
                            {v.preview_audio && (
                              <span role="button"
                                onClick={e => { e.stopPropagation(); new Audio(v.preview_audio).play(); }}
                                className="text-cyan-400 hover:text-cyan-300 shrink-0 cursor-pointer">
                                <Play className="w-3 h-3" />
                              </span>
                            )}
                            {heygenConfig.voiceId === v.voice_id && <Check className="w-3.5 h-3.5 text-cyan-400 shrink-0" />}
                          </button>
                        ))}
                    </div>
                  </div>
                </>
              )}

              {/* ===== STEP 2: SCRIPTS ===== */}
              {slideVideoStep === 'scripts' && (
                <>
                  {/* Controls */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <Button onClick={handleGenerateAllScripts} disabled={slideVideoScriptsLoading}
                      variant="outline" size="sm" data-testid="generate-all-scripts-btn">
                      {slideVideoScriptsLoading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Sparkles className="w-4 h-4 mr-1" />}
                      {slideVideoScriptsLoading ? 'Gerando...' : 'Gerar Scripts com IA'}
                    </Button>
                    <button onClick={() => setSlideVideoScripts(prev => prev.map(s => ({ ...s, enabled: true })))}
                      className="text-[11px] text-amber-400 hover:underline">Selecionar todos</button>
                    <button onClick={() => setSlideVideoScripts(prev => prev.map(s => ({ ...s, enabled: false })))}
                      className="text-[11px] text-muted-foreground hover:underline">Desmarcar todos</button>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {slideVideoScripts.filter(s => s.enabled).length} selecionados |
                      {slideVideoScripts.filter(s => s.script.trim()).length} com script
                    </span>
                  </div>

                  {/* Slide list */}
                  <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1" data-testid="slide-video-list">
                    {slideVideoScripts.map((s, i) => (
                      <div key={i}
                        className={`rounded-lg border p-3 transition-all ${
                          s.status === 'completed' ? 'border-green-500/40 bg-green-500/5' :
                          s.status === 'processing' ? 'border-amber-500/40 bg-amber-500/5' :
                          s.status === 'failed' ? 'border-red-500/40 bg-red-500/5' :
                          s.enabled ? 'border-border' : 'border-border/30 opacity-50'
                        }`} data-testid={`slide-video-row-${i}`}>
                        <div className="flex items-center gap-2 mb-2">
                          <input type="checkbox" checked={s.enabled}
                            onChange={() => setSlideVideoScripts(prev =>
                              prev.map((ss, ii) => ii === i ? { ...ss, enabled: !ss.enabled } : ss)
                            )} className="rounded" />
                          <span className="text-sm font-medium flex-1 truncate">{i + 1}. {s.title}</span>
                          {s.status === 'processing' && <Loader2 className="w-3 h-3 animate-spin text-amber-500" />}
                          {s.status === 'completed' && <Check className="w-3 h-3 text-green-500" />}
                          {s.status === 'failed' && <X className="w-3 h-3 text-red-500" />}
                          {s.videoUrl && (
                            <a href={s.videoUrl} target="_blank" rel="noreferrer"
                              className="text-xs text-cyan-400 hover:text-cyan-300 underline">Assistir</a>
                          )}
                        </div>
                        {s.enabled && (
                          <>
                            <textarea value={s.script}
                              onChange={e => setSlideVideoScripts(prev =>
                                prev.map((ss, ii) => ii === i ? { ...ss, script: e.target.value } : ss)
                              )}
                              placeholder="Script de narração..."
                              rows={2}
                              className="w-full text-xs bg-background border border-input rounded-md p-2 resize-none"
                              disabled={s.status === 'processing' || s.status === 'completed'}
                              data-testid={`slide-video-script-${i}`} />
                            {s.script && <span className="text-[10px] text-muted-foreground">{s.script.length} caracteres</span>}
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}

              {/* ===== STEP 3: GENERATE ===== */}
              {slideVideoStep === 'generate' && (
                <>
                  {/* Summary */}
                  <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
                    <h3 className="text-sm font-semibold">Resumo da Geração</h3>
                    <div className="grid grid-cols-3 gap-3 text-center">
                      <div className="rounded-lg bg-background p-3 border">
                        <p className="text-2xl font-bold text-amber-400">{slideVideoScripts.filter(s => s.enabled && s.script.trim()).length}</p>
                        <p className="text-[10px] text-muted-foreground">Slides com vídeo</p>
                      </div>
                      <div className="rounded-lg bg-background p-3 border">
                        <p className="text-sm font-medium truncate text-cyan-400">
                          {heygenAvatars.find(a => a.avatar_id === heygenConfig.avatarId)?.avatar_name || 'Não selecionado'}
                        </p>
                        <p className="text-[10px] text-muted-foreground">Avatar</p>
                      </div>
                      <div className="rounded-lg bg-background p-3 border">
                        <p className="text-sm font-medium truncate text-cyan-400">
                          {heygenVoices.find(v => v.voice_id === heygenConfig.voiceId)?.name || 'Não selecionada'}
                        </p>
                        <p className="text-[10px] text-muted-foreground">Voz</p>
                      </div>
                    </div>

                    {(!heygenConfig.avatarId || !heygenConfig.voiceId) && (
                      <p className="text-xs text-red-400 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" /> Volte ao passo 1 e selecione avatar e voz.
                      </p>
                    )}
                    {slideVideoScripts.filter(s => s.enabled && s.script.trim()).length === 0 && (
                      <p className="text-xs text-red-400 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" /> Volte ao passo 2 e gere scripts para os slides.
                      </p>
                    )}
                  </div>

                  {/* Batch progress */}
                  {slideVideoBatchId && (
                    <div className="rounded-lg bg-muted/50 p-3 border" data-testid="slide-video-batch-progress">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Progresso</span>
                        <span className="text-xs text-muted-foreground">
                          {slideVideoScripts.filter(s => s.status === 'completed').length}/
                          {slideVideoScripts.filter(s => s.enabled && s.script.trim()).length} concluídos
                        </span>
                      </div>
                      <div className="w-full bg-muted rounded-full h-2">
                        <div className="bg-green-500 h-2 rounded-full transition-all"
                          style={{ width: `${(slideVideoScripts.filter(s => s.status === 'completed').length / Math.max(slideVideoScripts.filter(s => s.enabled && s.script.trim()).length, 1)) * 100}%` }} />
                      </div>
                      {slideVideoBatchPolling && (
                        <p className="text-xs text-amber-400 mt-2 flex items-center gap-1">
                          <Loader2 className="w-3 h-3 animate-spin" /> Aguardando processamento do HeyGen...
                        </p>
                      )}

                      {/* Per-slide results */}
                      <div className="mt-3 space-y-1">
                        {slideVideoScripts.filter(s => s.enabled && s.script.trim()).map(s => (
                          <div key={s.index} className="flex items-center gap-2 text-xs py-1">
                            {s.status === 'completed' ? <Check className="w-3 h-3 text-green-500" /> :
                             s.status === 'processing' ? <Loader2 className="w-3 h-3 animate-spin text-amber-500" /> :
                             s.status === 'failed' ? <X className="w-3 h-3 text-red-500" /> :
                             <div className="w-3 h-3 rounded-full border border-muted-foreground" />}
                            <span className="flex-1 truncate">{s.index + 1}. {s.title}</span>
                            {s.videoUrl && (
                              <a href={s.videoUrl} target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline">Assistir</a>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={() => setShowSlideVideoDialog(false)}>Fechar</Button>
              {slideVideoStep === 'setup' && (
                <Button onClick={() => setSlideVideoStep('scripts')}
                  disabled={!heygenConfig.avatarId || !heygenConfig.voiceId}
                  className="bg-amber-600 hover:bg-amber-700">
                  Próximo: Scripts <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              )}
              {slideVideoStep === 'scripts' && (
                <Button onClick={() => setSlideVideoStep('generate')}
                  disabled={slideVideoScripts.filter(s => s.enabled && s.script.trim()).length === 0}
                  className="bg-amber-600 hover:bg-amber-700">
                  Próximo: Gerar <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              )}
              {slideVideoStep === 'generate' && (
                <Button onClick={handleGenerateBatchSlideVideos}
                  disabled={slideVideoGenerating || slideVideoBatchPolling || !heygenConfig.avatarId || !heygenConfig.voiceId || slideVideoScripts.filter(s => s.enabled && s.script.trim()).length === 0}
                  className="bg-gradient-to-r from-amber-500 to-rose-500 hover:from-amber-600 hover:to-rose-600"
                  data-testid="generate-batch-videos-btn">
                  {slideVideoGenerating ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Play className="w-4 h-4 mr-1" />}
                  Gerar {slideVideoScripts.filter(s => s.enabled && s.script.trim()).length} Vídeos
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Video Library Dialog */}
        <Dialog open={showVideoLibrary} onOpenChange={setShowVideoLibrary}>
          <DialogContent className="sm:max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Film className="w-5 h-5 text-cyan-500" />
                📹 Biblioteca de Vídeos
              </DialogTitle>
              <DialogDescription>
                Vídeos gerados anteriormente. Clique em um vídeo para adicioná-lo ao slide.
              </DialogDescription>
            </DialogHeader>
            
            <div className="flex-1 overflow-hidden">
              {videoLibraryLoading ? (
                <div className="flex items-center justify-center h-64">
                  <Loader2 className="w-8 h-8 animate-spin text-cyan-500" />
                </div>
              ) : videoLibraryItems.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-64 text-center">
                  <Film className="w-16 h-16 text-muted-foreground/30 mb-4" />
                  <h3 className="text-lg font-medium text-muted-foreground">Nenhum vídeo encontrado</h3>
                  <p className="text-sm text-muted-foreground/60 mt-1">
                    Crie um vídeo com avatar usando o botão 🎭 na barra de ferramentas
                  </p>
                </div>
              ) : (
                <ScrollArea className="h-[calc(85vh-200px)]">
                  <div className="space-y-3 p-1 pr-4">
                    {videoLibraryItems.map((video) => (
                      <div
                        key={video.video_id}
                        className={`group border rounded-lg overflow-hidden transition-all hover:border-cyan-500/50 hover:shadow-md ${
                          video.status === 'completed' ? 'cursor-pointer' : 'opacity-80'
                        }`}
                        onClick={() => video.status === 'completed' && handleAddLibraryVideoToSlide(video)}
                      >
                        <div className="flex gap-4 p-4">
                          {/* Thumbnail */}
                          <div className="flex-shrink-0 w-32 h-20 bg-muted rounded overflow-hidden relative">
                            {video.thumbnail_url ? (
                              <img 
                                src={video.thumbnail_url} 
                                alt={video.title}
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center">
                                <Video className="w-8 h-8 text-muted-foreground/30" />
                              </div>
                            )}
                            {video.duration && (
                              <div className="absolute bottom-1 right-1 px-1.5 py-0.5 bg-black/70 rounded text-[10px] text-white font-mono">
                                {formatDuration(video.duration)}
                              </div>
                            )}
                          </div>
                          
                          {/* Info */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-start justify-between gap-2">
                              <div>
                                <h4 className="font-medium truncate">{video.title || 'Sem título'}</h4>
                                <div className="flex items-center gap-2 mt-1">
                                  {getStatusBadge(video.status)}
                                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                                    <Clock className="w-3 h-3" />
                                    {formatDateTime(video.created_at)}
                                  </span>
                                </div>
                              </div>
                              
                              <div className="flex items-center gap-1">
                                {video.status !== 'completed' && (
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 px-2"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      refreshVideoStatus(video.video_id);
                                    }}
                                    disabled={refreshingVideoId === video.video_id}
                                    data-testid={`refresh-video-${video.video_id}`}
                                  >
                                    {refreshingVideoId === video.video_id ? (
                                      <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                      <RefreshCw className="w-4 h-4" />
                                    )}
                                    <span className="ml-1 text-xs">Atualizar</span>
                                  </Button>
                                )}
                                
                                {video.status === 'completed' && (
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 px-2 text-cyan-600 hover:text-cyan-700 hover:bg-cyan-50"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleAddLibraryVideoToSlide(video);
                                    }}
                                    data-testid={`add-video-${video.video_id}`}
                                  >
                                    <Plus className="w-4 h-4" />
                                    <span className="ml-1 text-xs">Adicionar</span>
                                  </Button>
                                )}
                                
                                {/* Delete button - always visible */}
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-8 px-2 text-red-500 hover:text-red-600 hover:bg-red-50"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDeleteLibraryVideo(video.video_id, video.title);
                                  }}
                                  data-testid={`delete-video-${video.video_id}`}
                                >
                                  <Trash2 className="w-4 h-4" />
                                  <span className="ml-1 text-xs">Excluir</span>
                                </Button>
                              </div>
                            </div>
                            
                            {/* Script preview */}
                            {video.script && (
                              <div className="mt-2 p-2 bg-muted/50 rounded text-xs text-muted-foreground max-h-16 overflow-hidden relative">
                                <div className="flex items-start gap-1.5">
                                  <FileText className="w-3 h-3 flex-shrink-0 mt-0.5" />
                                  <p className="line-clamp-2">{video.script}</p>
                                </div>
                                <div className="absolute bottom-0 left-0 right-0 h-4 bg-gradient-to-t from-muted/50 to-transparent" />
                              </div>
                            )}
                          </div>
                        </div>
                        
                        {/* Video preview for completed videos */}
                        {video.status === 'completed' && video.video_url && (
                          <div 
                            className="hidden group-hover:block border-t bg-black"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <video
                              src={video.video_url}
                              controls
                              className="w-full max-h-48"
                              preload="metadata"
                            />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </div>

            <DialogFooter className="gap-2 mt-4">
              <Button
                variant="outline"
                onClick={loadVideoLibrary}
                disabled={videoLibraryLoading}
              >
                {videoLibraryLoading ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4 mr-2" />
                )}
                Atualizar Lista
              </Button>
              <Button variant="outline" onClick={() => setShowVideoLibrary(false)}>
                Fechar
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* ElevenLabs TTS Dialog */}
        <Dialog open={showTTSDialog} onOpenChange={setShowTTSDialog}>
          <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Volume2 className="w-5 h-5 text-orange-500" />
                🔊 Text-to-Speech (ElevenLabs)
              </DialogTitle>
              <DialogDescription>
                Converta texto em narração. Todas as vozes suportam Português, Inglês e Espanhol.
              </DialogDescription>
            </DialogHeader>

            {ttsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-orange-500" />
                <span className="ml-3">Carregando vozes...</span>
              </div>
            ) : (
              <div className="space-y-6 py-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium">Selecionar Voz ({ttsVoices.length})</label>
                    <select
                      className="text-xs px-2 py-1 rounded border bg-background"
                      value={ttsGenderFilter}
                      onChange={(e) => handleTTSGenderFilterChange(e.target.value)}
                    >
                      <option value="all">👥 Todos</option>
                      <option value="male">👨 Masculino</option>
                      <option value="female">👩 Feminino</option>
                    </select>
                  </div>
                  <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto p-2 border rounded-lg">
                    {ttsVoices.map((voice) => (
                      <div
                        key={voice.voice_id}
                        className={`cursor-pointer p-3 rounded-lg border-2 transition-all ${
                          ttsSelectedVoice?.voice_id === voice.voice_id
                            ? 'border-orange-500 bg-orange-500/10'
                            : 'border-transparent hover:border-gray-300 hover:bg-muted/50'
                        }`}
                        onClick={() => setTTSSelectedVoice(voice)}
                      >
                        <div className="flex items-center gap-2">
                          <span>{voice.gender === 'male' ? '👨' : voice.gender === 'female' ? '👩' : '🧑'}</span>
                          <div>
                            <p className="font-medium text-sm">{voice.name}</p>
                            <p className="text-xs text-muted-foreground truncate max-w-[140px]">
                              {voice.accent || 'Multilíngue'}
                            </p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium">Texto para Narração</label>
                    <div className="flex items-center gap-2">
                      <select
                        data-testid="ai-narration-style-select"
                        className="text-xs px-2 py-1 rounded border bg-background"
                        value={aiNarrationStyle}
                        onChange={(e) => setAiNarrationStyle(e.target.value)}
                      >
                        <option value="educational">Educativo</option>
                        <option value="conversational">Conversacional</option>
                        <option value="formal">Formal</option>
                        <option value="friendly">Amigável</option>
                      </select>
                      <Button
                        data-testid="ai-generate-narration-btn"
                        size="sm"
                        variant="outline"
                        onClick={handleGenerateAiNarration}
                        disabled={aiNarrationLoading || !currentSlide}
                        className="text-xs border-purple-500/50 text-purple-400 hover:bg-purple-500/10 hover:text-purple-300"
                      >
                        {aiNarrationLoading ? (
                          <><Loader2 className="w-3 h-3 mr-1 animate-spin" />Gerando...</>
                        ) : (
                          <><Sparkles className="w-3 h-3 mr-1" />Gerar com IA</>
                        )}
                      </Button>
                    </div>
                  </div>

                  {showAiNarrationOptions && (
                    <div data-testid="ai-narration-options" className="mb-3 space-y-2">
                      {aiNarrationLoading ? (
                        <div className="flex items-center justify-center py-6 border rounded-lg bg-purple-500/5 border-purple-500/20">
                          <Loader2 className="w-5 h-5 animate-spin text-purple-400 mr-2" />
                          <span className="text-sm text-purple-300">Gerando 3 opções com Gemini...</span>
                        </div>
                      ) : aiNarrationOptions.length > 0 ? (
                        <>
                          <p className="text-xs text-muted-foreground">Escolha uma das opções geradas pela IA:</p>
                          {aiNarrationOptions.map((option, idx) => (
                            <div
                              key={idx}
                              data-testid={`ai-narration-option-${idx}`}
                              onClick={() => handleSelectAiNarration(option)}
                              className="cursor-pointer p-3 border rounded-lg transition-all hover:border-purple-500/60 hover:bg-purple-500/10 group"
                            >
                              <div className="flex items-start justify-between gap-2">
                                <div className="flex-1">
                                  <span className="text-xs font-semibold text-purple-400 mb-1 block">Opção {idx + 1}</span>
                                  <p className="text-sm leading-relaxed">{option}</p>
                                </div>
                                <Check className="w-4 h-4 text-purple-400 opacity-0 group-hover:opacity-100 transition-opacity mt-1 shrink-0" />
                              </div>
                            </div>
                          ))}
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => { setShowAiNarrationOptions(false); setAiNarrationOptions([]); }}
                            className="text-xs text-muted-foreground"
                          >
                            <X className="w-3 h-3 mr-1" />Fechar opções
                          </Button>
                        </>
                      ) : null}
                    </div>
                  )}

                  <textarea
                    data-testid="tts-text-input"
                    className="w-full h-32 p-3 border rounded-lg bg-background resize-none"
                    placeholder="Digite o texto ou gere com IA..."
                    value={ttsText}
                    onChange={(e) => setTTSText(e.target.value)}
                  />
                </div>

                {ttsAudioUrl && (
                  <div className="p-4 border rounded-lg bg-green-500/10 border-green-500/30">
                    <span className="text-sm font-medium text-green-400 block mb-2">✅ Áudio Gerado</span>
                    <audio src={ttsAudioUrl} controls className="w-full" />
                  </div>
                )}
              </div>
            )}

            <DialogFooter className="flex justify-between gap-2">
              <Button variant="ghost" onClick={() => setShowTTSDialog(false)}>Cancelar</Button>
              <div className="flex gap-2">
                <Button
                  onClick={handleGenerateTTS}
                  disabled={ttsGenerating || !ttsText.trim() || !ttsSelectedVoice}
                  className="bg-orange-600 hover:bg-orange-700"
                >
                  {ttsGenerating ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Gerando...</> : <><Volume2 className="w-4 h-4 mr-2" />Gerar Áudio</>}
                </Button>
                {ttsAudioUrl && (
                  <Button onClick={handleAddTTSToSlide} className="bg-green-600 hover:bg-green-700">
                    <Plus className="w-4 h-4 mr-2" />Adicionar ao Slide
                  </Button>
                )}
              </div>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Rich Text Editor with AI Dialog */}
        <Dialog open={showRichTextDialog} onOpenChange={(open) => {
          if (!open) {
            handleCloseRichText();
          } else {
            setShowRichTextDialog(open);
          }
        }}>
          <DialogContent className="sm:max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-purple-500" />
                {editingHtmlElementId ? 'Editar Texto' : 'Criar Texto com IA'}
              </DialogTitle>
              <DialogDescription>
                {editingHtmlElementId 
                  ? 'Edite o texto existente ou gere novo conteúdo com IA'
                  : 'Escreva seu texto ou use a IA para gerar conteúdo formatado automaticamente'
                }
              </DialogDescription>
            </DialogHeader>
            
            <div className="py-4">
              <RichTextEditor
                key={editingHtmlElementId || 'new'}
                content={richTextContent}
                onChange={setRichTextContent}
                onGenerateAI={generateTextWithAI}
                onGenerateAIImage={generateImageWithAI}
                isGenerating={richTextGenerating}
                isGeneratingImage={richTextImageGenerating}
                placeholder="Digite seu texto ou clique em 'Gerar com IA' para criar conteúdo..."
                className="min-h-[400px]"
              />
            </div>

            <DialogFooter className="flex justify-between">
              <Button variant="ghost" onClick={handleCloseRichText}>
                Cancelar
              </Button>
              <Button 
                onClick={handleAddRichTextToSlide}
                disabled={!richTextContent.trim()}
                className="bg-purple-600 hover:bg-purple-700"
              >
                {editingHtmlElementId ? (
                  <>
                    <Check className="w-4 h-4 mr-2" />
                    Salvar Alterações
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4 mr-2" />
                    Adicionar ao Slide
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

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

