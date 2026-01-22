import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/dialog';
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
} from 'lucide-react';
import SlideCanvas from '../components/editor/SlideCanvas';
import Timeline from '../components/editor/Timeline';
import AnnotationToolbar from '../components/editor/AnnotationToolbar';

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
    addElement,
    updateElement,
    deleteElement,
    uploadMedia,
    uploadSlideAudio,
    setGlobalAudio,
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
  const [showTimeline, setShowTimeline] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recordingIntervalRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (projectId) {
      fetchProject(projectId);
    }
  }, [projectId, fetchProject]);

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

      try {
        await addElement(currentSlide.id, {
          type: 'video',
          x: 100,
          y: 100,
          width: 560,
          height: 315,
          embedUrl,
          embedType,
        });
        setShowMediaDialog(false);
        setVideoUrl('');
        toast.success('Video added');
      } catch (err) {
        toast.error('Failed to add video');
      }
    }
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const media = await uploadMedia(file);
      await addElement(currentSlide.id, {
        type: 'image',
        x: 100,
        y: 100,
        width: 300,
        height: 200,
        src: `${process.env.REACT_APP_BACKEND_URL}${media.url}`,
      });
      toast.success('Image added');
    } catch (err) {
      toast.error('Failed to upload image');
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
      clearInterval(recordingIntervalRef.current);
    }
  };

  const handleGlobalAudioUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      await setGlobalAudio(file);
      toast.success('Soundtrack added');
    } catch (err) {
      toast.error('Failed to upload soundtrack');
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
      <div className="h-screen w-screen overflow-hidden flex flex-col bg-background">
        {/* Header */}
        <header className="h-14 border-b border-border bg-card flex items-center px-4 justify-between z-50">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => navigate('/')} data-testid="back-btn">
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <Separator orientation="vertical" className="h-6" />
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
            <Dialog open={showExportDialog} onOpenChange={setShowExportDialog}>
              <Button className="gap-2 btn-primary" onClick={() => setShowExportDialog(true)} data-testid="export-btn">
                <Download className="w-4 h-4" />
                Export SCORM
              </Button>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Export SCORM 1.2 Package</DialogTitle>
                </DialogHeader>
                <div className="py-4">
                  {downloadUrl ? (
                    <div className="text-center">
                      <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4">
                        <Download className="w-8 h-8 text-green-500" />
                      </div>
                      <p className="mb-4">Your SCORM package is ready!</p>
                      <Button asChild className="w-full">
                        <a href={downloadUrl} download data-testid="download-scorm-btn">
                          Download Package
                        </a>
                      </Button>
                    </div>
                  ) : (
                    <div className="text-center">
                      <p className="text-muted-foreground mb-4">
                        Export your course as a SCORM 1.2 package that can be imported into any LMS.
                      </p>
                      <Button
                        onClick={handleExport}
                        disabled={exportLoading}
                        className="w-full gap-2"
                        data-testid="generate-scorm-btn"
                      >
                        {exportLoading ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Generating...
                          </>
                        ) : (
                          <>
                            <Download className="w-4 h-4" />
                            Generate Package
                          </>
                        )}
                      </Button>
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
                {slides.map((slide, index) => (
                  <div
                    key={slide.id}
                    className={`slide-thumbnail relative group ${
                      index === currentSlideIndex ? 'active' : ''
                    }`}
                    onClick={() => setCurrentSlideIndex(index)}
                    data-testid={`slide-${index}`}
                  >
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
                        <DropdownMenuItem onClick={() => handleDuplicateSlide(slide.id)}>
                          <Copy className="w-4 h-4 mr-2" />
                          Duplicate
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={() => handleDeleteSlide(slide.id)}
                        >
                          <Trash2 className="w-4 h-4 mr-2" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                ))}
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

              <div className="ml-auto flex items-center gap-2">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => setShowTimeline(!showTimeline)}
                    >
                      {showTimeline ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Toggle Timeline</TooltipContent>
                </Tooltip>
              </div>
            </div>

            {/* Canvas */}
            <div className="flex-1 bg-muted/30 overflow-auto flex items-center justify-center p-8">
              <SlideCanvas
                slide={currentSlide}
                selectedElementId={selectedElementId}
                onSelectElement={setSelectedElementId}
                onUpdateElement={(elementId, data) => updateElement(currentSlide?.id, elementId, data)}
                onDeleteElement={(elementId) => deleteElement(currentSlide?.id, elementId)}
                annotationMode={annotationMode}
              />
            </div>

            {/* Timeline */}
            {showTimeline && (
              <Timeline
                slide={currentSlide}
                onUpdateSlide={(data) => updateSlide(currentSlide?.id, data)}
              />
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

              <TabsContent value="properties" className="flex-1 mt-0 overflow-auto">
                <ScrollArea className="h-full">
                  {selectedElement ? (
                    <ElementProperties
                      element={selectedElement}
                      onUpdate={(data) => updateElement(currentSlide?.id, selectedElement.id, data)}
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

              <TabsContent value="layers" className="flex-1 mt-0 overflow-auto">
                <ScrollArea className="h-full">
                  {currentSlide?.elements?.length > 0 ? (
                    <div className="p-2 space-y-1">
                      {[...currentSlide.elements]
                        .sort((a, b) => (b.zIndex || 0) - (a.zIndex || 0))
                        .map((element) => (
                          <div
                            key={element.id}
                            className={`flex items-center gap-2 p-2 rounded cursor-pointer ${
                              selectedElementId === element.id ? 'bg-primary/10' : 'hover:bg-muted'
                            }`}
                            onClick={() => setSelectedElementId(element.id)}
                          >
                            <GripVertical className="w-4 h-4 text-muted-foreground" />
                            {element.type === 'text' && <Type className="w-4 h-4" />}
                            {element.type === 'image' && <Image className="w-4 h-4" />}
                            {element.type === 'shape' && <Square className="w-4 h-4" />}
                            {element.type === 'video' && <Video className="w-4 h-4" />}
                            <span className="text-sm truncate flex-1">
                              {element.type} {element.id.slice(0, 4)}
                            </span>
                          </div>
                        ))}
                    </div>
                  ) : (
                    <div className="p-4 text-center text-muted-foreground">
                      No elements
                    </div>
                  )}
                </ScrollArea>
              </TabsContent>

              <TabsContent value="media" className="flex-1 mt-0 overflow-auto">
                <ScrollArea className="h-full">
                  <div className="p-4 space-y-4">
                    <div>
                      <label className="text-sm font-medium mb-2 block">Global Soundtrack</label>
                      <div className="space-y-2">
                        {currentProject?.course?.globalAudio ? (
                          <div className="flex items-center gap-2 p-2 bg-muted rounded">
                            <Music className="w-4 h-4" />
                            <span className="text-sm truncate flex-1">
                              {currentProject.course.globalAudio.filename}
                            </span>
                          </div>
                        ) : (
                          <label className="block">
                            <div className="border border-dashed rounded p-4 text-center cursor-pointer hover:border-primary/50 transition-colors">
                              <Music className="w-6 h-6 mx-auto text-muted-foreground mb-2" />
                              <span className="text-sm text-muted-foreground">Add soundtrack</span>
                            </div>
                            <input
                              type="file"
                              accept="audio/*"
                              className="hidden"
                              onChange={handleGlobalAudioUpload}
                            />
                          </label>
                        )}
                      </div>
                    </div>

                    <Separator />

                    <div>
                      <label className="text-sm font-medium mb-2 block">Slide Narration</label>
                      {currentSlide?.audio?.length > 0 ? (
                        <div className="space-y-2">
                          {currentSlide.audio.map((audio) => (
                            <div key={audio.id} className="flex items-center gap-2 p-2 bg-muted rounded">
                              <Mic className="w-4 h-4" />
                              <span className="text-sm truncate flex-1">{audio.type}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">No narration recorded</p>
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
      </div>
    </TooltipProvider>
  );
}

// Element Properties Panel
function ElementProperties({ element, onUpdate }) {
  const [localStyle, setLocalStyle] = useState(element.style || {});

  useEffect(() => {
    setLocalStyle(element.style || {});
  }, [element]);

  const handleStyleChange = (key, value) => {
    const newStyle = { ...localStyle, [key]: value };
    setLocalStyle(newStyle);
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
      </div>

      {element.type === 'text' && (
        <div className="panel-section">
          <h4 className="text-sm font-medium mb-3">Text</h4>
          <div className="space-y-2">
            <div>
              <label className="text-xs text-muted-foreground">Font Size</label>
              <Input
                type="number"
                value={localStyle.fontSize || 16}
                onChange={(e) => handleStyleChange('fontSize', parseFloat(e.target.value))}
                className="h-8"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Color</label>
              <Input
                type="color"
                value={localStyle.fontColor || '#000000'}
                onChange={(e) => handleStyleChange('fontColor', e.target.value)}
                className="h-8 p-1"
              />
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
                value={localStyle.fill || '#7C3AED'}
                onChange={(e) => handleStyleChange('fill', e.target.value)}
                className="h-8 p-1"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Stroke</label>
              <Input
                type="color"
                value={localStyle.stroke || '#000000'}
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
