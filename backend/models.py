from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid

def generate_id():
    return str(uuid.uuid4())

def now_utc():
    return datetime.now(timezone.utc)

# Element Models
class ElementStyle(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    fill: Optional[str] = None
    stroke: Optional[str] = None
    strokeWidth: Optional[float] = None
    opacity: Optional[float] = 1.0
    fontSize: Optional[float] = None
    fontFamily: Optional[str] = None
    fontWeight: Optional[str] = None
    fontColor: Optional[str] = None
    textAlign: Optional[str] = None
    verticalAlign: Optional[str] = None
    shadow: Optional[Dict[str, Any]] = None
    borderRadius: Optional[float] = None

class Animation(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(default_factory=generate_id)
    type: str  # entrance, exit, emphasis, motion
    effect: str  # fade, fly, zoom, etc.
    trigger: str = "onClick"  # onClick, afterPrevious, withPrevious
    duration: float = 0.5  # seconds
    delay: float = 0.0
    startTime: Optional[float] = None  # for timeline sync
    easing: str = "ease"

class SlideElement(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(default_factory=generate_id)
    type: str  # text, image, shape, video, audio, smartart, wordart, table, chart, button, html, flipbook, quiz
    x: float = 0
    y: float = 0
    width: float = 100
    height: float = 100
    rotation: float = 0
    zIndex: int = 0
    visible: bool = True
    locked: bool = False
    
    # Content
    content: Optional[str] = None  # text content or media URL
    src: Optional[str] = None  # for images/videos
    embedUrl: Optional[str] = None  # for YouTube/Vimeo
    embedType: Optional[str] = None  # youtube, vimeo
    openInNewWindow: bool = False
    
    # Hyperlink
    hyperlink: Optional[str] = None
    
    # Styling
    style: ElementStyle = Field(default_factory=ElementStyle)
    
    # Shape specific
    shapeType: Optional[str] = None  # rectangle, ellipse, arrow, etc.
    
    # Button specific
    buttonText: Optional[str] = None
    buttonIcon: Optional[str] = None  # icon name or emoji
    buttonStyle: Optional[str] = "primary"  # primary, secondary, outline, ghost
    buttonUrl: Optional[str] = None
    openInNewTab: bool = True
    
    # HTML specific
    htmlContent: Optional[str] = None  # raw HTML code
    
    # Flipbook specific
    flipbookType: Optional[str] = None  # pdf, images, external
    flipbookUrl: Optional[str] = None  # external flipbook URL
    flipbookPages: Optional[List[str]] = None  # list of image URLs for pages
    flipbookPdfUrl: Optional[str] = None  # PDF file URL
    
    # Quiz specific
    quizConfig: Optional[Dict[str, Any]] = None  # Quiz configuration
    
    # Timeline properties
    startTime: float = 0.0  # When element appears (seconds)
    endTime: Optional[float] = None  # When element disappears (None = until end of slide)
    
    # Animations
    animations: List[Animation] = Field(default_factory=list)
    
    # SVG/Vector data for complex shapes
    svgPath: Optional[str] = None
    
    # For fallback rendering
    fallbackImage: Optional[str] = None

class Annotation(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(default_factory=generate_id)
    type: str  # arrow, circle, rectangle, freehand
    shapeType: Optional[str] = None  # arrow, circle, rect, freehand
    points: List[Dict[str, float]] = Field(default_factory=list)
    color: str = "#EF4444"
    strokeWidth: float = 2
    includeInExport: bool = False
    
    # Timeline properties
    startTime: float = 0.0  # When annotation appears (seconds)
    endTime: Optional[float] = None  # When annotation disappears (None = until end of slide)

class SlideTransition(BaseModel):
    type: str = "none"  # fade, push, wipe, etc.
    duration: float = 0.5
    direction: Optional[str] = None

class SlideAudio(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(default_factory=generate_id)
    type: str  # narration, soundtrack
    src: str
    filename: str
    duration: float = 0
    volume: float = 1.0
    fadeIn: float = 0
    fadeOut: float = 0
    startTime: float = 0

class Slide(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(default_factory=generate_id)
    title: str = "Slide"
    order: int = 0
    width: float = 1536
    height: float = 864
    background: Optional[str] = "#FFFFFF"
    backgroundImage: Optional[str] = None
    
    elements: List[SlideElement] = Field(default_factory=list)
    annotations: List[Annotation] = Field(default_factory=list)
    transition: SlideTransition = Field(default_factory=SlideTransition)
    audio: List[SlideAudio] = Field(default_factory=list)
    
    # Notes for presenter
    notes: Optional[str] = None
    
    # Thumbnail
    thumbnail: Optional[str] = None
    
    # Timeline duration (auto-calculated or manual)
    duration: float = 5.0  # seconds

class GlobalAudio(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(default_factory=generate_id)
    src: str
    filename: str
    duration: float = 0
    volume: float = 0.5
    fadeIn: float = 0
    fadeOut: float = 0
    loop: bool = True

class CourseMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    title: str = "Untitled Course"
    description: str = ""
    author: str = ""
    organization: str = ""
    version: str = "1.0"
    language: str = "pt-BR"
    keywords: List[str] = Field(default_factory=list)

class Course(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(default_factory=generate_id)
    metadata: CourseMetadata = Field(default_factory=CourseMetadata)
    slides: List[Slide] = Field(default_factory=list)
    globalAudio: Optional[GlobalAudio] = None
    
    # Original PPT info
    originalFilename: Optional[str] = None
    
    # Conversion report
    conversionReport: Optional[Dict[str, Any]] = None
    
    # Timestamps
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

class Project(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(default_factory=generate_id)
    name: str
    description: str = ""
    thumbnail: Optional[str] = None
    course: Course = Field(default_factory=Course)
    status: str = "draft"  # draft, processing, ready, exported
    
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

# API Models
class ProjectCreate(BaseModel):
    name: str
    description: str = ""

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class SlideCreate(BaseModel):
    title: str = "New Slide"
    background: str = "#FFFFFF"
    width: int = 1536
    height: int = 864

class SlideUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    title: Optional[str] = None
    background: Optional[str] = None
    backgroundImage: Optional[str] = None
    elements: Optional[List[SlideElement]] = None
    annotations: Optional[List[Annotation]] = None
    transition: Optional[SlideTransition] = None
    audio: Optional[List[SlideAudio]] = None
    notes: Optional[str] = None
    duration: Optional[float] = None

class ElementCreate(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    type: str
    x: float = 0
    y: float = 0
    width: float = 100
    height: float = 100
    content: Optional[str] = None
    src: Optional[str] = None
    embedUrl: Optional[str] = None
    embedType: Optional[str] = None
    style: Optional[ElementStyle] = None

class ElementUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    rotation: Optional[float] = None
    zIndex: Optional[int] = None
    visible: Optional[bool] = None
    locked: Optional[bool] = None
    content: Optional[str] = None
    src: Optional[str] = None
    embedUrl: Optional[str] = None
    style: Optional[ElementStyle] = None
    animations: Optional[List[Animation]] = None
    hyperlink: Optional[str] = None
    startTime: Optional[float] = None
    endTime: Optional[float] = None

class JobStatus(BaseModel):
    id: str
    status: str  # pending, processing, completed, failed
    progress: int = 0
    message: str = ""
    result: Optional[Dict[str, Any]] = None

class AnnotationCreate(BaseModel):
    type: str
    shapeType: Optional[str] = None
    points: List[Dict[str, float]]
    color: str = "#EF4444"
    strokeWidth: float = 2
    includeInExport: bool = False
    startTime: float = 0.0
    endTime: Optional[float] = None

class AnnotationUpdate(BaseModel):
    startTime: Optional[float] = None
    endTime: Optional[float] = None
    color: Optional[str] = None
    strokeWidth: Optional[float] = None
    includeInExport: Optional[bool] = None

class ReorderSlidesRequest(BaseModel):
    slideIds: List[str]

# ============================================
# Quiz Models
# ============================================

class QuizAlternative(BaseModel):
    """Represents one alternative/option in a quiz question"""
    id: str = Field(default_factory=generate_id)
    text: str
    isCorrect: bool = False

class QuizQuestion(BaseModel):
    """Represents a quiz question"""
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(default_factory=generate_id)
    projectId: Optional[str] = None  # Optional: links to a specific project
    type: str  # 'multiple_choice' or 'true_false'
    text: str  # The question text
    alternatives: List[QuizAlternative] = Field(default_factory=list)
    explanation: Optional[str] = None  # Explanation shown after answering
    points: float = 1.0  # Points for this question
    tags: List[str] = Field(default_factory=list)  # For categorization
    
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

class QuizConfig(BaseModel):
    """Configuration for a quiz element on a slide"""
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(default_factory=generate_id)
    title: str = "Quiz"
    questionIds: List[str] = Field(default_factory=list)  # IDs of questions to include
    questionCount: int = 5  # Number of questions to show (can be less than available)
    shuffleQuestions: bool = True
    shuffleAlternatives: bool = True
    showFeedback: bool = True  # Show correct/incorrect after each question
    showExplanation: bool = True  # Show explanation text
    passingScore: float = 60.0  # Percentage needed to pass (0-100)
    maxAttempts: int = 0  # 0 = unlimited

class QuizAttempt(BaseModel):
    """Records a user's attempt at a quiz"""
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(default_factory=generate_id)
    quizId: str
    projectId: str
    userId: Optional[str] = None  # Anonymous if not logged in
    answers: List[Dict[str, Any]] = Field(default_factory=list)  # [{questionId, selectedAlternativeId, isCorrect}]
    score: float = 0.0  # Final score (0-10)
    percentage: float = 0.0  # Percentage correct (0-100)
    passed: bool = False
    completedAt: Optional[datetime] = None
    
    createdAt: datetime = Field(default_factory=now_utc)

# API Models for Quiz
class QuizQuestionCreate(BaseModel):
    """Create a new quiz question"""
    projectId: Optional[str] = None
    type: str  # 'multiple_choice' or 'true_false'
    text: str
    alternatives: List[Dict[str, Any]]  # [{text, isCorrect}]
    explanation: Optional[str] = None
    points: float = 1.0
    tags: List[str] = Field(default_factory=list)

class QuizQuestionUpdate(BaseModel):
    """Update a quiz question"""
    text: Optional[str] = None
    alternatives: Optional[List[Dict[str, Any]]] = None
    explanation: Optional[str] = None
    points: Optional[float] = None
    tags: Optional[List[str]] = None

class QuizGenerateRequest(BaseModel):
    """Request to generate quiz questions using AI"""
    projectId: Optional[str] = None
    source: str  # 'prompt' or 'document'
    prompt: Optional[str] = None  # For AI generation from prompt
    context: Optional[str] = None  # Additional context
    documentContent: Optional[str] = None  # Extracted text from .doc file
    questionType: str = "multiple_choice"  # 'multiple_choice', 'true_false', 'mixed'
    count: int = 5  # Number of questions to generate

class QuizSubmitRequest(BaseModel):
    """Submit quiz answers"""
    quizId: str
    answers: List[Dict[str, Any]]  # [{questionId, selectedAlternativeId}]
