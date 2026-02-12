import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useProject } from '../contexts/ProjectContext';
import { useTheme } from '../contexts/ThemeContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import { Slider } from '../components/ui/slider';
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
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  ArrowLeft,
  Sun,
  Moon,
  Save,
  Download,
  Play,
  Plus,
  Copy,
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
  GripVertical,
  Pause,
  StopCircle,
  MoreVertical,
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
} from 'lucide-react';
import SlideCanvas from '../components/editor/SlideCanvas';
import Timeline from '../components/editor/Timeline';
import AnnotationToolbar from '../components/editor/AnnotationToolbar';
import CoursePreview from '../components/editor/CoursePreview';
import RichTextEditor from '../components/RichTextEditor';
import QuizGenerator from '../components/quiz/QuizGenerator';

// Sortable Slide Item Component
const SortableSlideItem = ({ slide, index, isActive, onClick, onDuplicate, onDelete }) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: slide.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 1000 : 'auto',
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`slide-thumbnail relative group ${isActive ? 'active' : ''} ${isDragging ? 'ring-2 ring-primary' : ''}`}
      onClick={onClick}
      data-testid={`slide-${index}`}
    >
      {/* Drag Handle */}
      <div
        {...attributes}
        {...listeners}
        className="absolute left-1 top-1/2 -translate-y-1/2 cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-100 z-10 p-1 bg-background/80 rounded"
        onClick={(e) => e.stopPropagation()}
      >
        <GripVertical className="w-3 h-3 text-muted-foreground" />
      </div>
      
      <div
        className="w-full h-full"
        style={{
          backgroundColor: slide.background || '#fff',
          backgroundImage: slide.backgroundImage ? `url(${slide.backgroundImage})` : 'none',
          backgroundSize: 'cover',
        }}
      >
        <div className="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
          {index + 1}
        </div>
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="absolute top-1 right-1 h-6 w-6 opacity-0 group-hover:opacity-100"
            onClick={(e) => e.stopPropagation()}
          >
            <MoreVertical className="w-3 h-3" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => onDuplicate(slide.id)}>
            <Copy className="w-4 h-4 mr-2" />
            Duplicar
          </DropdownMenuItem>
          <DropdownMenuItem
            className="text-destructive"
            onClick={() => onDelete(slide.id)}
          >
            <Trash2 className="w-4 h-4 mr-2" />
            Excluir
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
};

// Sortable Layer Item component for drag-and-drop in Layers tab
const SortableLayerItem = ({ element, index, isSelected, onClick, onDelete }) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: element.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 1000 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-2 p-2 rounded cursor-pointer group ${
        isSelected ? 'bg-primary/10' : 'hover:bg-muted'
      } ${isDragging ? 'shadow-lg bg-card' : ''}`}
      onClick={onClick}
    >
      <div {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing">
        <GripVertical className="w-4 h-4 text-muted-foreground" />
      </div>
      {element.type === 'text' && <Type className="w-4 h-4" />}
      {element.type === 'image' && <Image className="w-4 h-4" />}
      {element.type === 'shape' && <Square className="w-4 h-4" />}
      {element.type === 'video' && <Video className="w-4 h-4" />}
      {element.type === 'button' && <ExternalLink className="w-4 h-4" />}
      {element.type === 'html' && <Code className="w-4 h-4" />}
      {element.type === 'flipbook' && <BookOpen className="w-4 h-4" />}
      <span className="text-sm truncate flex-1">
        {element.type === 'button' ? (element.buttonText || 'Botão') : 
         element.type === 'html' ? 'HTML' :
         element.type === 'flipbook' ? 'Flipbook' :
         element.type === 'video' ? 'Vídeo' :
         element.type === 'image' ? 'Imagem' :
         element.type === 'text' ? 'Texto' :
         `${element.type} ${element.id.slice(0, 4)}`}
      </span>
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 opacity-0 group-hover:opacity-100"
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
      >
        <Trash2 className="w-3 h-3 text-destructive" />
      </Button>
    </div>
  );
};

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

  const [showExportDialog, setShowExportDialog] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [showMediaDialog, setShowMediaDialog] = useState(false);
  const [mediaType, setMediaType] = useState('image');
  const [videoUrl, setVideoUrl] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [annotationMode, setAnnotationMode] = useState(null);
  const [selectedAnnotationId, setSelectedAnnotationId] = useState(null);
  const [showTimeline, setShowTimeline] = useState(true);
  const [showTimelineExpanded, setShowTimelineExpanded] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [showAudioDialog, setShowAudioDialog] = useState(false);
  const [audioFile, setAudioFile] = useState(null);
  const [audioTarget, setAudioTarget] = useState('slide'); // 'slide' or 'global'
  const [showPreview, setShowPreview] = useState(false); // Preview mode state
  
  // New element dialogs
  const [showButtonDialog, setShowButtonDialog] = useState(false);
  const [showHtmlDialog, setShowHtmlDialog] = useState(false);
  const [showFlipbookDialog, setShowFlipbookDialog] = useState(false);
  const [buttonConfig, setButtonConfig] = useState({
    text: 'Clique aqui',
    url: '',
    icon: '',
    style: 'primary',
    openInNewTab: true,
  });
  const [htmlConfig, setHtmlConfig] = useState({
    content: '',
  });
  const [flipbookConfig, setFlipbookConfig] = useState({
    type: 'external', // 'external', 'images', 'pdf'
    url: '',
    pages: [],
  });
  
  // HeyGen Avatar Video states
  const [showHeygenDialog, setShowHeygenDialog] = useState(false);
  const [heygenAvatars, setHeygenAvatars] = useState([]);
  const [heygenVoices, setHeygenVoices] = useState([]);
  const [heygenLoading, setHeygenLoading] = useState(false);
  const [heygenCreditsLoading, setHeygenCreditsLoading] = useState(false); // Separate loading state for credits
  const [heygenGenerating, setHeygenGenerating] = useState(false);
  const [heygenVideoId, setHeygenVideoId] = useState(null);
  const [heygenVideoStatus, setHeygenVideoStatus] = useState(null);
  const [heygenVideoUrl, setHeygenVideoUrl] = useState(null);
  const [heygenElapsedTime, setHeygenElapsedTime] = useState(0);
  const [heygenCredits, setHeygenCredits] = useState(null); // Credits info
  // Filter states
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
    transparentBackground: true, // Default to transparent
  });
  
  // Ref for HeyGen timer interval
  const heygenTimerRef = useRef(null);
  
  // Video Library states
  const [showVideoLibrary, setShowVideoLibrary] = useState(false);
  const [videoLibraryItems, setVideoLibraryItems] = useState([]);
  const [videoLibraryLoading, setVideoLibraryLoading] = useState(false);
  const [refreshingVideoId, setRefreshingVideoId] = useState(null);
  
  // AI Script Generation states
  const [scriptMode, setScriptMode] = useState('manual'); // 'manual' or 'ai'
  const [aiScriptTopic, setAiScriptTopic] = useState('');
  const [aiScriptStyle, setAiScriptStyle] = useState('educational');
  const [aiScriptDuration, setAiScriptDuration] = useState('medium');
  const [aiGeneratingScript, setAiGeneratingScript] = useState(false);
  
  // Timeline playback state (shared between Timeline and SlideCanvas)
  const [timelineTime, setTimelineTime] = useState(0);
  const [timelineIsPlaying, setTimelineIsPlaying] = useState(false);
  
  // Audio playback states
  const [playingAudioId, setPlayingAudioId] = useState(null);
  const [globalAudioVolume, setGlobalAudioVolume] = useState(0.5);
  const [slideAudioVolumes, setSlideAudioVolumes] = useState({});
  
  // Rich Text Editor with AI states
  const [showRichTextDialog, setShowRichTextDialog] = useState(false);
  const [richTextContent, setRichTextContent] = useState('');
  const [richTextGenerating, setRichTextGenerating] = useState(false);
  const [richTextImageGenerating, setRichTextImageGenerating] = useState(false);
  const [editingHtmlElementId, setEditingHtmlElementId] = useState(null); // Track which HTML element is being edited
  const [editingHtmlSlideId, setEditingHtmlSlideId] = useState(null); // Store slide ID when editing starts
  const [rtfSaveFailed, setRtfSaveFailed] = useState(false); // Track if last save attempt failed

  // Quiz Generator states
  const [showQuizDialog, setShowQuizDialog] = useState(false);

  // ElevenLabs TTS states
  const [showTTSDialog, setShowTTSDialog] = useState(false);
  const [ttsVoices, setTTSVoices] = useState([]);
  const [ttsLoading, setTTSLoading] = useState(false);
  const [ttsGenerating, setTTSGenerating] = useState(false);
  const [ttsGenderFilter, setTTSGenderFilter] = useState('all');
  const [ttsSelectedVoice, setTTSSelectedVoice] = useState(null);
  const [ttsText, setTTSText] = useState('');
  const [ttsPreviewUrl, setTTSPreviewUrl] = useState(null);
  const [ttsAudioUrl, setTTSAudioUrl] = useState(null);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recordingIntervalRef = useRef(null);
  const fileInputRef = useRef(null);
  const audioPlayerRef = useRef(null);
  const isRecordingRef = useRef(false); // Track recording state for cleanup

  const API_URL = process.env.REACT_APP_BACKEND_URL;

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

  // Reset timeline when slide changes
  useEffect(() => {
    setTimelineTime(0);
    setTimelineIsPlaying(false);
    
    // Stop recording if active when changing slides
    if (isRecordingRef.current && mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      isRecordingRef.current = false;
      clearInterval(recordingIntervalRef.current);
      toast.info('Gravação salva automaticamente ao trocar de slide');
    }
    
    // Stop any playing audio preview when changing slides
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current.currentTime = 0;
    }
  }, [currentSlideIndex]);

  // Sync volume states with project data
  useEffect(() => {
    if (currentProject?.course?.globalAudio) {
      setGlobalAudioVolume(currentProject.course.globalAudio.volume ?? 0.5);
    }
    if (currentSlide?.audio) {
      const volumes = {};
      currentSlide.audio.forEach(audio => {
        volumes[audio.id] = audio.volume ?? 1;
      });
      setSlideAudioVolumes(volumes);
    }
  }, [currentProject?.course?.globalAudio, currentSlide?.audio]);

  // Cleanup audio and HeyGen timer on unmount
  useEffect(() => {
    return () => {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
        audioPlayerRef.current = null;
      }
      if (heygenTimerRef.current) {
        clearInterval(heygenTimerRef.current);
        heygenTimerRef.current = null;
      }
    };
  }, []);

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

  const handleExport = async () => {
    try {
      setExportLoading(true);
      const result = await exportScorm();
      setDownloadUrl(`${process.env.REACT_APP_BACKEND_URL}${result.downloadUrl}`);
      toast.success('SCORM package ready!');
    } catch (err) {
      toast.error('Export failed');
    } finally {
      setExportLoading(false);
    }
  };

  const handleExportHTML = async () => {
    try {
      setExportLoading(true);
      const response = await axios.post(
        `${process.env.REACT_APP_BACKEND_URL}/api/course/${currentProject.id}/export-html`
      );
      setDownloadUrl(`${process.env.REACT_APP_BACKEND_URL}${response.data.downloadUrl}`);
      toast.success('HTML file ready!');
    } catch (err) {
      console.error('HTML export error:', err);
      toast.error('Export failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setExportLoading(false);
    }
  };

  // Audio playback functions
  const playAudio = (audioUrl, audioId) => {
    // Stop any currently playing audio
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current = null;
    }
    
    if (playingAudioId === audioId) {
      // If same audio, just stop
      setPlayingAudioId(null);
      return;
    }

    const audio = new Audio(audioUrl);
    audio.volume = audioId === 'global' ? globalAudioVolume : (slideAudioVolumes[audioId] ?? 1);
    
    audio.onended = () => {
      setPlayingAudioId(null);
      audioPlayerRef.current = null;
    };
    
    audio.onerror = () => {
      toast.error('Erro ao reproduzir áudio');
      setPlayingAudioId(null);
      audioPlayerRef.current = null;
    };
    
    audioPlayerRef.current = audio;
    audio.play();
    setPlayingAudioId(audioId);
  };

  const stopAudio = () => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current = null;
    }
    setPlayingAudioId(null);
  };

  const getAudioUrl = (filename) => {
    if (!filename || !currentProject) return '';
    return `${API_URL}/api/projects/${currentProject.id}/assets/${filename}`;
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
        embedUrl = `https://www.youtube.com/embed/${youtubeMatch[1]}`;
        embedType = 'youtube';
      }
      
      // Parse Vimeo URL
      const vimeoMatch = videoUrl.match(/vimeo\.com\/(\d+)/);
      if (vimeoMatch) {
        embedUrl = `https://player.vimeo.com/video/${vimeoMatch[1]}`;
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
        src: `${process.env.REACT_APP_BACKEND_URL}${media.url}`,
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

  // HeyGen Functions
  const loadHeygenData = async () => {
    setHeygenLoading(true);
    setHeygenCreditsLoading(true);
    
    try {
      // Load avatars and voices with current filters
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
      
      // Set available filter options (only on first load)
      if (avatarsRes.data.available_genders) {
        setHeygenAvailableGenders(avatarsRes.data.available_genders);
      }
      if (voicesRes.data.available_languages) {
        setHeygenAvailableLanguages(voicesRes.data.available_languages);
      }
      
      // Set defaults if available and not already set
      if (avatarsRes.data.avatars?.length > 0 && !heygenConfig.avatarId) {
        setHeygenConfig(prev => ({ ...prev, avatarId: avatarsRes.data.avatars[0].avatar_id }));
      }
      if (voicesRes.data.voices?.length > 0 && !heygenConfig.voiceId) {
        setHeygenConfig(prev => ({ ...prev, voiceId: voicesRes.data.voices[0].voice_id }));
      }
      
      setHeygenLoading(false);
      
      // Load credits separately (don't block UI if it's slow)
      try {
        const creditsRes = await axios.get(`${API_URL}/api/heygen/credits`);
        if (creditsRes.data) {
          setHeygenCredits(creditsRes.data);
        }
      } catch (creditsErr) {
        console.warn('Could not load HeyGen credits:', creditsErr);
        // Don't show error - credits info is optional
      } finally {
        setHeygenCreditsLoading(false);
      }
      
    } catch (err) {
      console.error('Error loading HeyGen data:', err);
      toast.error('Falha ao carregar dados do HeyGen. Verifique a API Key.');
      setHeygenLoading(false);
      setHeygenCreditsLoading(false);
    }
  };
  
  // Reload avatars when gender filter changes
  const reloadHeygenAvatars = async (gender) => {
    try {
      const params = gender !== 'all' ? `?gender=${gender}` : '';
      const response = await axios.get(`${API_URL}/api/heygen/avatars${params}`);
      setHeygenAvatars(response.data.avatars || []);
      // Reset avatar selection if current avatar is not in filtered list
      if (heygenConfig.avatarId && !response.data.avatars?.find(a => a.avatar_id === heygenConfig.avatarId)) {
        setHeygenConfig(prev => ({ 
          ...prev, 
          avatarId: response.data.avatars?.[0]?.avatar_id || '' 
        }));
      }
    } catch (err) {
      console.error('Error reloading avatars:', err);
    }
  };
  
  // Reload voices when filters change
  const reloadHeygenVoices = async (language, gender) => {
    try {
      const params = new URLSearchParams();
      if (language !== 'all') params.append('language', language);
      if (gender !== 'all') params.append('gender', gender);
      const query = params.toString() ? `?${params.toString()}` : '';
      
      const response = await axios.get(`${API_URL}/api/heygen/voices${query}`);
      setHeygenVoices(response.data.voices || []);
      // Reset voice selection if current voice is not in filtered list
      if (heygenConfig.voiceId && !response.data.voices?.find(v => v.voice_id === heygenConfig.voiceId)) {
        setHeygenConfig(prev => ({ 
          ...prev, 
          voiceId: response.data.voices?.[0]?.voice_id || '' 
        }));
      }
    } catch (err) {
      console.error('Error reloading voices:', err);
    }
  };

  const handleOpenHeygenDialog = () => {
    setShowHeygenDialog(true);
    loadHeygenData();
    setHeygenVideoId(null);
    setHeygenVideoStatus(null);
    setHeygenVideoUrl(null);
    setHeygenElapsedTime(0);
    // Clear any existing timer
    if (heygenTimerRef.current) {
      clearInterval(heygenTimerRef.current);
      heygenTimerRef.current = null;
    }
  };

  // AI Script Generation
  const handleGenerateAiScript = async () => {
    if (!aiScriptTopic.trim()) {
      toast.error('Por favor, descreva o tema do vídeo');
      return;
    }

    setAiGeneratingScript(true);
    
    try {
      const response = await axios.post(`${API_URL}/api/ai/generate-script`, {
        topic: aiScriptTopic,
        style: aiScriptStyle,
        duration: aiScriptDuration,
        language: 'português brasileiro'
      });
      
      setHeygenConfig(prev => ({ ...prev, script: response.data.script }));
      toast.success('Script gerado com sucesso!');
      setScriptMode('manual'); // Switch back to show the generated script
    } catch (err) {
      console.error('Error generating script:', err);
      toast.error(err.response?.data?.detail || 'Falha ao gerar script');
    } finally {
      setAiGeneratingScript(false);
    }
  };

  const handleGenerateHeygenVideo = async () => {
    if (!heygenConfig.avatarId || !heygenConfig.voiceId || !heygenConfig.script) {
      toast.error('Por favor, preencha todos os campos');
      return;
    }

    // Check credits before generating
    if (heygenCredits && !heygenCredits.has_credits) {
      toast.error('Você não possui créditos suficientes na HeyGen. Por favor, recarregue sua conta.');
      return;
    }

    setHeygenGenerating(true);
    setHeygenVideoStatus('processing');
    
    try {
      const response = await axios.post(`${API_URL}/api/heygen/generate-video`, {
        avatar_id: heygenConfig.avatarId,
        voice_id: heygenConfig.voiceId,
        script: heygenConfig.script,
        title: heygenConfig.title,
        aspect_ratio: '16:9',
        transparent_background: heygenConfig.transparentBackground,
        project_id: projectId // Associate video with current project
      });
      
      setHeygenVideoId(response.data.video_id);
      toast.success('Geração de vídeo iniciada! Aguarde...');
      
      // Refresh credits after starting generation
      try {
        const creditsRes = await axios.get(`${API_URL}/api/heygen/credits`);
        setHeygenCredits(creditsRes.data);
      } catch (e) {
        // Ignore credits refresh error
      }
      
      // Start polling for status
      pollHeygenVideoStatus(response.data.video_id);
    } catch (err) {
      console.error('Error generating video:', err);
      toast.error(err.response?.data?.detail || 'Falha ao gerar vídeo');
      setHeygenGenerating(false);
      setHeygenVideoStatus(null);
    }
  };

  const pollHeygenVideoStatus = async (videoId) => {
    // Start elapsed time counter
    setHeygenElapsedTime(0);
    if (heygenTimerRef.current) {
      clearInterval(heygenTimerRef.current);
    }
    heygenTimerRef.current = setInterval(() => {
      setHeygenElapsedTime(prev => prev + 1);
    }, 1000);
    
    const stopTimer = () => {
      if (heygenTimerRef.current) {
        clearInterval(heygenTimerRef.current);
        heygenTimerRef.current = null;
      }
    };
    
    // Use Server-Sent Events (SSE) for real-time updates instead of polling
    try {
      const eventSource = new EventSource(`${API_URL}/api/heygen/video-events/${videoId}`);
      
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('SSE event:', data);
          
          if (data.event === 'ping') {
            // Keepalive ping, ignore
            return;
          }
          
          if (data.status) {
            setHeygenVideoStatus(data.status);
          }
          
          if (data.status === 'completed' && data.video_url) {
            stopTimer();
            setHeygenVideoUrl(data.video_url);
            setHeygenGenerating(false);
            toast.success('Vídeo gerado com sucesso!');
            eventSource.close();
          } else if (data.status === 'failed' || data.status === 'error') {
            stopTimer();
            setHeygenGenerating(false);
            toast.error('Falha na geração do vídeo. Tente novamente.');
            eventSource.close();
          } else if (data.event === 'timeout') {
            stopTimer();
            setHeygenGenerating(false);
            toast.error('Tempo limite excedido (15 min). O vídeo pode ainda estar sendo processado.');
            eventSource.close();
          }
        } catch (e) {
          console.error('Error parsing SSE event:', e);
        }
      };
      
      eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        eventSource.close();
        // Fallback to polling if SSE fails
        fallbackToPoll(videoId, stopTimer);
      };
      
      // Store eventSource reference for cleanup
      const currentEventSource = eventSource;
      
      // Cleanup on unmount or dialog close
      return () => {
        currentEventSource.close();
        stopTimer();
      };
      
    } catch (e) {
      console.error('Error setting up SSE:', e);
      // Fallback to polling
      fallbackToPoll(videoId, stopTimer);
    }
  };
  
  // Fallback polling function if SSE doesn't work
  const fallbackToPoll = async (videoId, stopTimer) => {
    const maxAttempts = 180; // 15 minutes max (5s intervals)
    let attempts = 0;
    
    const poll = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/heygen/video-status/${videoId}`);
        const status = response.data.status;
        setHeygenVideoStatus(status);
        
        if (status === 'completed') {
          stopTimer();
          setHeygenVideoUrl(response.data.video_url);
          setHeygenGenerating(false);
          toast.success('Vídeo gerado com sucesso!');
          return;
        } else if (status === 'failed' || status === 'error') {
          stopTimer();
          setHeygenGenerating(false);
          toast.error('Falha na geração do vídeo. Tente novamente.');
          return;
        }
        
        // Continue polling
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(poll, 5000);
        } else {
          stopTimer();
          setHeygenGenerating(false);
          toast.error('Tempo limite excedido (15 min). O vídeo pode ainda estar sendo processado.');
        }
      } catch (err) {
        console.error('Error polling status:', err);
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(poll, 5000);
        } else {
          stopTimer();
          setHeygenGenerating(false);
          toast.error('Erro de conexão. Verifique sua internet e tente novamente.');
        }
      }
    };
    
    poll();
  };

  const handleAddHeygenVideoToSlide = async () => {
    if (!heygenVideoUrl) {
      toast.error('Vídeo ainda não está pronto');
      return;
    }

    try {
      await addElement(currentSlide.id, {
        type: 'video',
        x: 50,
        y: 50,
        width: 640,
        height: 360,
        src: heygenVideoUrl,
        embedUrl: null,
        embedType: null,
      });
      setShowHeygenDialog(false);
      setHeygenConfig({ avatarId: '', voiceId: '', script: '', title: 'Avatar Video', transparentBackground: true });
      setHeygenVideoId(null);
      setHeygenVideoStatus(null);
      setHeygenVideoUrl(null);
      toast.success('Vídeo do avatar adicionado ao slide!');
    } catch (err) {
      toast.error('Falha ao adicionar vídeo ao slide');
    }
  };

  // Video Library functions
  const loadVideoLibrary = async () => {
    setVideoLibraryLoading(true);
    try {
      const response = await axios.get(`${API_URL}/api/heygen/videos`);
      setVideoLibraryItems(response.data.videos || []);
    } catch (err) {
      console.error('Error loading video library:', err);
      toast.error('Falha ao carregar biblioteca de vídeos');
    } finally {
      setVideoLibraryLoading(false);
    }
  };

  const refreshVideoStatus = async (videoId) => {
    setRefreshingVideoId(videoId);
    try {
      const response = await axios.get(`${API_URL}/api/heygen/videos/${videoId}/refresh`);
      // Update the video in the list
      setVideoLibraryItems(prev => prev.map(v => 
        v.video_id === videoId 
          ? { ...v, ...response.data }
          : v
      ));
      
      if (response.data.status === 'completed') {
        toast.success('Vídeo pronto para uso!');
      } else if (response.data.status === 'failed') {
        toast.error('Vídeo falhou na geração');
      } else {
        toast.info(`Status: ${response.data.status}`);
      }
    } catch (err) {
      console.error('Error refreshing video status:', err);
      toast.error('Falha ao atualizar status do vídeo');
    } finally {
      setRefreshingVideoId(null);
    }
  };

  const handleAddLibraryVideoToSlide = async (video) => {
    if (!video.video_url) {
      toast.error('Este vídeo ainda não está pronto. Clique em "Atualizar Status".');
      return;
    }

    try {
      await addElement(currentSlide.id, {
        type: 'video',
        x: 50,
        y: 50,
        width: 640,
        height: 360,
        src: video.video_url,
        embedUrl: null,
        embedType: null,
      });
      setShowVideoLibrary(false);
      toast.success('Vídeo adicionado ao slide!');
    } catch (err) {
      toast.error('Falha ao adicionar vídeo ao slide');
    }
  };

  const handleDeleteLibraryVideo = async (videoId, videoTitle) => {
    if (!window.confirm(`Tem certeza que deseja excluir o vídeo "${videoTitle || 'Sem título'}"?\n\nEsta ação não pode ser desfeita.`)) {
      return;
    }

    try {
      await axios.delete(`${API_URL}/api/heygen/videos/${videoId}`);
      // Remove from local state
      setVideoLibraryItems(prev => prev.filter(v => v.video_id !== videoId));
      toast.success('Vídeo excluído com sucesso!');
    } catch (err) {
      console.error('Error deleting video:', err);
      toast.error('Falha ao excluir vídeo');
    }
  };

  const handleOpenVideoLibrary = () => {
    loadVideoLibrary();
    setShowVideoLibrary(true);
  };

  const formatDuration = (seconds) => {
    if (!seconds) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDateTime = (isoString) => {
    if (!isoString) return 'Data desconhecida';
    const date = new Date(isoString);
    return date.toLocaleString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'completed':
        return <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-green-500/20 text-green-400">Concluído</span>;
      case 'processing':
        return <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-yellow-500/20 text-yellow-400">Processando</span>;
      case 'failed':
        return <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-red-500/20 text-red-400">Falhou</span>;
      case 'pending':
        return <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-blue-500/20 text-blue-400">Pendente</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-gray-500/20 text-gray-400">{status || 'Desconhecido'}</span>;
    }
  };

  // =============================================================================
  // ElevenLabs TTS Functions
  // =============================================================================
  
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
        similarity_boost: 0.75
      });
      if (response.data.success) {
        setTTSAudioUrl(response.data.audio_base64);
        toast.success('Áudio gerado com sucesso!');
      }
    } catch (err) {
      console.error('Error generating TTS:', err);
      toast.error(err.response?.data?.detail || 'Falha ao gerar áudio');
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
      await fetchProject(currentProject.id);
      toast.success('Narração adicionada ao slide!');
      setShowTTSDialog(false);
      setTTSAudioUrl(null);
      setTTSText('');
    } catch (err) {
      console.error('Error adding audio to slide:', err);
      toast.error('Falha ao adicionar áudio ao slide');
    }
  };

  const handlePlayTTSPreview = (previewUrl) => {
    setTTSPreviewUrl(ttsPreviewUrl === previewUrl ? null : previewUrl);
  };

  // AI Text Generation function
  const generateTextWithAI = async (prompt) => {
    setRichTextGenerating(true);
    try {
      const response = await axios.post(`${API_URL}/api/ai/generate-text`, {
        prompt: prompt,
        format: 'html'
      });
      
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

  // AI Image Generation function
  const generateImageWithAI = async (prompt) => {
    setRichTextImageGenerating(true);
    try {
      const response = await axios.post(`${API_URL}/api/ai/generate-image`, {
        prompt: prompt,
        size: '1024x1024'
      });
      
      if (response.data.success && response.data.imageUrl) {
        toast.success('Imagem gerada com sucesso!');
        // Return relative URL only - this prevents issues when domain changes
        // The frontend will resolve the full URL when displaying
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

  // Add or update rich text element
  const handleAddRichTextToSlide = async () => {
    if (!richTextContent.trim()) {
      toast.error('Escreva ou gere um texto primeiro');
      return;
    }

    // Use stored slideId for editing, or current slide for new elements
    const targetSlideId = editingHtmlElementId ? editingHtmlSlideId : currentSlide?.id;
    
    if (!targetSlideId) {
      toast.error('Erro: nenhum slide selecionado. Feche e tente novamente.');
      return;
    }

    try {
      if (editingHtmlElementId) {
        // Update existing element
        await updateElement(targetSlideId, editingHtmlElementId, {
          htmlContent: richTextContent,
        });
        toast.success('Texto atualizado!');
      } else {
        // Create new element
        await addElement(targetSlideId, {
          type: 'html',
          x: 50,
          y: 50,
          width: 600,
          height: 400,
          htmlContent: richTextContent,
        });
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

  // Open RTF editor to edit existing HTML element
  const handleEditHtmlElement = (element) => {
    if (element.type === 'html' && element.htmlContent) {
      setRichTextContent(element.htmlContent);
      setEditingHtmlElementId(element.id);
      setEditingHtmlSlideId(currentSlide?.id); // Store slide ID at edit time
      setRtfSaveFailed(false);
      setShowRichTextDialog(true);
    }
  };

  const handleStartRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (e) => {
        audioChunksRef.current.push(e.data);
      };

      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const audioFile = new File([audioBlob], 'narration.webm', { type: 'audio/webm' });
        
        try {
          await uploadSlideAudio(currentSlide.id, audioFile, 'narration');
          toast.success('Narration saved');
        } catch (err) {
          toast.error('Failed to save narration');
        }
        
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
      isRecordingRef.current = true;
      setRecordingTime(0);
      
      recordingIntervalRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    } catch (err) {
      toast.error('Could not access microphone');
    }
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
        await uploadSlideAudio(currentSlide.id, audioFile, 'background');
        toast.success('Áudio adicionado ao slide!');
      }
      setShowAudioDialog(false);
      setAudioFile(null);
      setAudioTarget('slide');
    } catch (err) {
      toast.error('Erro ao fazer upload do áudio');
    }
  };

  const handleRemoveGlobalAudio = async () => {
    if (!currentProject) return;
    try {
      await removeGlobalAudio();
      toast.success('Trilha sonora removida');
    } catch (err) {
      toast.error('Erro ao remover áudio');
    }
  };

  const handleRemoveSlideAudio = async (audioId) => {
    if (!currentSlide) return;
    // Stop audio if playing
    if (playingAudioId === audioId) {
      stopAudio();
    }
    try {
      await removeSlideAudio(currentSlide.id, audioId);
      toast.success('Áudio removido do slide');
    } catch (err) {
      toast.error('Erro ao remover áudio');
    }
  };

  const handleGlobalVolumeChange = (value) => {
    const newVolume = value[0];
    setGlobalAudioVolume(newVolume);
    
    // Update playing audio volume in real-time
    if (audioPlayerRef.current && playingAudioId === 'global') {
      audioPlayerRef.current.volume = newVolume;
    }
  };

  const handleGlobalVolumeCommit = async (value) => {
    if (!currentProject?.course?.globalAudio) return;
    try {
      await updateGlobalAudioVolume(value[0]);
      toast.success('Volume atualizado');
    } catch (err) {
      console.error('Error updating volume:', err);
      toast.error('Erro ao atualizar volume');
    }
  };

  const handleSlideAudioVolumeChange = (audioId, value) => {
    const newVolume = value[0];
    setSlideAudioVolumes(prev => ({ ...prev, [audioId]: newVolume }));
    
    // Update playing audio volume in real-time
    if (audioPlayerRef.current && playingAudioId === audioId) {
      audioPlayerRef.current.volume = newVolume;
    }
  };

  const handleSlideAudioVolumeCommit = async (audioId, value) => {
    if (!currentSlide) return;
    try {
      await updateSlideAudioVolume(currentSlide.id, audioId, value[0]);
      toast.success('Volume atualizado');
    } catch (err) {
      console.error('Error updating volume:', err);
      toast.error('Erro ao atualizar volume');
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const slides = currentProject?.course?.slides || [];

  if (loading && !currentProject) {
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
              variant="outline" 
              className="gap-2" 
              onClick={() => setShowPreview(true)}
              data-testid="preview-btn"
            >
              <Eye className="w-4 h-4" />
              Visualizar
            </Button>
            <Button className="gap-2 btn-primary" onClick={() => setShowExportDialog(true)} data-testid="export-btn">
              <Download className="w-4 h-4" />
              Exportar
            </Button>
            <Dialog open={showExportDialog} onOpenChange={(open) => {
              setShowExportDialog(open);
              if (!open) {
                // Reset downloadUrl when dialog closes so next time shows Generate button
                setDownloadUrl(null);
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
                    </div>
                  )}
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </header>

        <div className="flex-1 flex overflow-hidden">
          {/* Left Sidebar - Slides */}
          <div className="w-64 border-r border-border bg-card flex flex-col">
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
          </div>

          {/* Main Canvas Area */}
          <div className="flex-1 flex flex-col overflow-hidden">
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
                    onClick={() => setShowRichTextDialog(true)}
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
            <div className="flex-1 bg-muted/30 overflow-auto flex items-center justify-center p-8">
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

          {/* Right Sidebar - Properties */}
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
                                getAudioUrl(currentProject.course.globalAudio.filename),
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
                                    getAudioUrl(audio.filename),
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
                    {typeof heygenCredits.remaining_quota === 'number' 
                      ? `${heygenCredits.remaining_quota.toFixed(1)} minutos`
                      : 'N/A'}
                  </span>
                </div>
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
                        ✍️ Digitar
                      </button>
                      <button
                        className={`px-3 py-1 text-xs rounded-md transition-all ${
                          scriptMode === 'ai' 
                            ? 'bg-gradient-to-r from-purple-500 to-cyan-500 text-white font-medium' 
                            : 'text-muted-foreground hover:text-foreground'
                        }`}
                        onClick={() => setScriptMode('ai')}
                      >
                        ✨ Gerar com IA
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
                        💡 Dica: Escreva de forma natural, como se estivesse conversando. O avatar irá falar com sincronismo labial realista.
                      </p>
                    </>
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
                  <label className="text-sm font-medium mb-2 block">Texto para Narração</label>
                  <textarea
                    className="w-full h-32 p-3 border rounded-lg bg-background resize-none"
                    placeholder="Digite o texto..."
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
            // Only clear content if save didn't fail - preserve user's edits on failure
            if (!rtfSaveFailed) {
              setEditingHtmlElementId(null);
              setEditingHtmlSlideId(null);
              setRichTextContent('');
            }
          }
          setShowRichTextDialog(open);
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
              <Button variant="ghost" onClick={() => {
                setShowRichTextDialog(false);
                setRichTextContent('');
                setEditingHtmlElementId(null);
              }}>
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

// Element Properties Panel
function ElementProperties({ element, onUpdate, slideWidth = 960, slideHeight = 540 }) {
  // Use element.style directly with fallback, no local state needed
  const style = element.style || {};

  const handleStyleChange = (key, value) => {
    const newStyle = { ...style, [key]: value };
    onUpdate({ style: newStyle });
  };

  return (
    <div className="p-4 space-y-4">
      <div className="panel-section">
        <h4 className="text-sm font-medium mb-3">Position & Size</h4>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-xs text-muted-foreground">X</label>
            <Input
              type="number"
              value={Math.round(element.x || 0)}
              onChange={(e) => onUpdate({ x: parseFloat(e.target.value) })}
              className="h-8"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Y</label>
            <Input
              type="number"
              value={Math.round(element.y || 0)}
              onChange={(e) => onUpdate({ y: parseFloat(e.target.value) })}
              className="h-8"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Width</label>
            <Input
              type="number"
              value={Math.round(element.width || 0)}
              onChange={(e) => onUpdate({ width: parseFloat(e.target.value) })}
              className="h-8"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Height</label>
            <Input
              type="number"
              value={Math.round(element.height || 0)}
              onChange={(e) => onUpdate({ height: parseFloat(e.target.value) })}
              className="h-8"
            />
          </div>
        </div>
        {/* Fullscreen Button */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => onUpdate({ 
            x: 0, 
            y: 0, 
            width: slideWidth, 
            height: slideHeight,
            objectFit: 'cover'
          })}
          className="w-full mt-3 gap-2"
          data-testid="element-fullscreen-btn"
        >
          <Maximize2 className="w-4 h-4" />
          Fullscreen
        </Button>
      </div>

      {element.type === 'text' && (
        <div className="panel-section">
          <h4 className="text-sm font-medium mb-3">Text</h4>
          <div className="space-y-2">
            <div>
              <label className="text-xs text-muted-foreground">Font Size</label>
              <Input
                type="number"
                value={style.fontSize || 16}
                onChange={(e) => handleStyleChange('fontSize', parseFloat(e.target.value))}
                className="h-8"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Color</label>
              <Input
                type="color"
                value={style.fontColor || '#000000'}
                onChange={(e) => handleStyleChange('fontColor', e.target.value)}
                className="h-8 p-1"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Background Color</label>
              <div className="flex gap-2 items-center">
                <Input
                  type="color"
                  value={style.backgroundColor || '#FFFFFF'}
                  onChange={(e) => handleStyleChange('backgroundColor', e.target.value)}
                  className="h-8 p-1 flex-1"
                  disabled={style.transparentBackground}
                />
                <label className="flex items-center gap-1 text-xs cursor-pointer">
                  <input
                    type="checkbox"
                    checked={style.transparentBackground || false}
                    onChange={(e) => handleStyleChange('transparentBackground', e.target.checked)}
                    className="w-4 h-4"
                  />
                  Transparent
                </label>
              </div>
            </div>
          </div>
        </div>
      )}

      {element.type === 'shape' && (
        <div className="panel-section">
          <h4 className="text-sm font-medium mb-3">Fill & Stroke</h4>
          <div className="space-y-2">
            <div>
              <label className="text-xs text-muted-foreground">Fill</label>
              <Input
                type="color"
                value={style.fill || '#7C3AED'}
                onChange={(e) => handleStyleChange('fill', e.target.value)}
                className="h-8 p-1"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Stroke</label>
              <Input
                type="color"
                value={style.stroke || '#000000'}
                onChange={(e) => handleStyleChange('stroke', e.target.value)}
                className="h-8 p-1"
              />
            </div>
          </div>
        </div>
      )}

      <div className="panel-section">
        <h4 className="text-sm font-medium mb-3">Hyperlink</h4>
        <Input
          placeholder="https://..."
          value={element.hyperlink || ''}
          onChange={(e) => onUpdate({ hyperlink: e.target.value })}
          className="h-8"
        />
      </div>
    </div>
  );
}

// Slide Properties Panel
function SlideProperties({ slide, onUpdate }) {
  return (
    <div className="p-4 space-y-4">
      <div className="panel-section">
        <h4 className="text-sm font-medium mb-3">Slide Settings</h4>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground">Title</label>
            <Input
              value={slide.title || ''}
              onChange={(e) => onUpdate({ title: e.target.value })}
              className="h-8"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Background</label>
            <Input
              type="color"
              value={slide.background || '#FFFFFF'}
              onChange={(e) => onUpdate({ background: e.target.value })}
              className="h-8 p-1"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Duration (seconds)</label>
            <Input
              type="number"
              value={slide.duration || 5}
              onChange={(e) => onUpdate({ duration: parseFloat(e.target.value) })}
              className="h-8"
            />
          </div>
        </div>
      </div>

      <div className="panel-section">
        <h4 className="text-sm font-medium mb-3">Notes</h4>
        <textarea
          className="w-full h-24 p-2 text-sm bg-background border rounded resize-none"
          placeholder="Presenter notes..."
          value={slide.notes || ''}
          onChange={(e) => onUpdate({ notes: e.target.value })}
        />
      </div>
    </div>
  );
}
