from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import re

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

    @field_validator('borderRadius', 'fontSize', 'strokeWidth', mode='before')
    @classmethod
    def parse_numeric_with_unit(cls, v):
        """Accept '24px', '1.5rem', '50%', etc. by stripping the unit suffix.
        Returns None for empty/invalid values."""
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            m = re.match(r'^\s*([+-]?[\d.]+)', v)
            return float(m.group(1)) if m else None
        return None

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
    type: Optional[str] = "text"  # text, image, shape, video, audio, smartart, wordart, table, chart, button, html, flipbook, quiz, scenario
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
    
    # Scenario specific
    scenarioData: Optional[Dict[str, Any]] = None  # Scenario decision tree data
    
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
    type: str = "narration"  # narration, soundtrack
    src: Optional[str] = None
    filename: Optional[str] = None
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
    width: Optional[float] = 1920
    height: Optional[float] = 820
    background: Optional[str] = "#FFFFFF"
    backgroundImage: Optional[str] = None
    
    elements: List[SlideElement] = Field(default_factory=list)
    annotations: List[Annotation] = Field(default_factory=list)
    transition: SlideTransition = Field(default_factory=SlideTransition)
    audio: List[SlideAudio] = Field(default_factory=list)
    
    # Notes for presenter
    notes: Optional[str] = None
    
    # LIBRAS script for VLibras avatar translation
    librasScript: Optional[str] = None
    
    # Thumbnail
    thumbnail: Optional[str] = None
    
    # Timeline duration (auto-calculated or manual)
    duration: float = 5.0  # seconds

class GlobalAudio(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(default_factory=generate_id)
    src: Optional[str] = None
    filename: Optional[str] = None
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
    
    # Accessibility settings
    enableVlibras: bool = True  # Enable VLibras LIBRAS plugin in exports

    # Presentation mode: 'traditional' (slide-by-slide) or 'single_page' (vertical scroll w/ gated progression)
    singlePageMode: bool = False
    
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

# API Models
class ProjectCreate(BaseModel):
    name: str
    description: str = ""

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enableVlibras: Optional[bool] = None
    singlePageMode: Optional[bool] = None

class SlideCreate(BaseModel):
    title: str = "New Slide"
    background: str = "#FFFFFF"
    width: int = 1920  # 21:9 aspect ratio for better mobile landscape viewing
    height: int = 820

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
    librasScript: Optional[str] = None
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



# ============================================
# Authentication & Multi-Tenancy Models
# ============================================

class UserRole(BaseModel):
    """User roles within a company"""
    # Roles: 'super_admin' (system-wide), 'company_admin', 'editor', 'aprovador'
    pass

class Company(BaseModel):
    """Company/Tenant model for multi-tenancy"""
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(default_factory=lambda: f"company_{uuid.uuid4().hex[:12]}")
    name: str
    slug: str  # URL-friendly identifier
    logo: Optional[str] = None
    
    # API Permissions for this company
    permissions: Dict[str, bool] = Field(default_factory=lambda: {
        "heygen": False,
        "elevenlabs": False
    })
    
    # Limits
    maxUsers: int = 10
    maxProjects: int = 100
    
    isActive: bool = True
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

class CompanyCreate(BaseModel):
    """Create a new company"""
    name: str
    slug: str
    logo: Optional[str] = None
    permissions: Optional[Dict[str, bool]] = None
    maxUsers: Optional[int] = 10
    maxProjects: Optional[int] = 100

class CompanyUpdate(BaseModel):
    """Update company"""
    name: Optional[str] = None
    logo: Optional[str] = None
    permissions: Optional[Dict[str, bool]] = None
    maxUsers: Optional[int] = None
    maxProjects: Optional[int] = None
    isActive: Optional[bool] = None

class User(BaseModel):
    """User model"""
    model_config = ConfigDict(extra="allow")
    
    user_id: str = Field(default_factory=lambda: f"user_{uuid.uuid4().hex[:12]}")
    email: str
    name: str
    picture: Optional[str] = None
    
    # Company association (None for super_admin)
    companyId: Optional[str] = None
    
    # Role within company: 'super_admin', 'company_admin', 'editor', 'aprovador'
    role: str = "editor"
    
    # Password hash (for email/password auth)
    passwordHash: Optional[str] = None
    
    isActive: bool = True
    lastLogin: Optional[datetime] = None
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

class UserCreate(BaseModel):
    """Create a new user"""
    email: str
    name: str
    password: Optional[str] = None  # Optional for Google OAuth users
    companyId: str
    role: str = "editor"  # 'company_admin' or 'editor'

class UserUpdate(BaseModel):
    """Update user"""
    name: Optional[str] = None
    role: Optional[str] = None
    isActive: Optional[bool] = None

class UserSession(BaseModel):
    """User session for auth"""
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(default_factory=lambda: f"session_{uuid.uuid4().hex[:16]}")
    user_id: str
    session_token: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=now_utc)

class LoginRequest(BaseModel):
    """Login with email/password"""
    email: str
    password: str

class LoginResponse(BaseModel):
    """Login response"""
    user: Dict[str, Any]
    token: str

class GoogleAuthRequest(BaseModel):
    """Process Google OAuth session"""
    session_id: str

class ChangePasswordRequest(BaseModel):
    """Change password request"""
    currentPassword: str
    newPassword: str



# ==================== GAMIFICATION MODELS ====================

class BadgeCriteria(BaseModel):
    """Criteria for earning a badge"""
    model_config = ConfigDict(extra="allow")
    
    type: str  # "quiz_score", "scenario_score", "course_completion", "custom"
    threshold: float = 80.0  # Percentage threshold (e.g., 80 = 80%)
    operator: str = "gte"  # "gte" (>=), "gt" (>), "eq" (=), "lte" (<=), "lt" (<)

class Badge(BaseModel):
    """Badge definition for gamification"""
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(default_factory=generate_id)
    name: str  # e.g., "Mestre dos Quizzes"
    description: str = ""  # e.g., "Acertou mais de 80% das questões"
    icon: str = "trophy"  # Icon name or "custom" for uploaded image
    iconColor: str = "#fbbf24"  # Color for predefined icons
    customImage: Optional[str] = None  # Base64 or URL for custom badge image
    criteria: BadgeCriteria
    isDefault: bool = False  # True for predefined badges
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class FeedbackRange(BaseModel):
    """Feedback message for a score range"""
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(default_factory=generate_id)
    minScore: float = 0  # Minimum score percentage
    maxScore: float = 100  # Maximum score percentage
    title: str  # e.g., "Excelente!"
    message: str  # e.g., "Você demonstrou domínio completo do conteúdo!"
    emoji: str = "🎉"  # Optional emoji

class GamificationConfig(BaseModel):
    """Full gamification configuration for a project"""
    model_config = ConfigDict(extra="allow")
    
    enabled: bool = True
    showBadgesAfterQuiz: bool = True
    showBadgesAfterScenario: bool = True
    showFinalSummary: bool = True
    badges: List[Badge] = []
    quizFeedbackRanges: List[FeedbackRange] = []
    scenarioFeedbackRanges: List[FeedbackRange] = []
    completionFeedback: Optional[FeedbackRange] = None

# Default badges that come pre-configured
DEFAULT_BADGES = [
    Badge(
        id="badge_quiz_master",
        name="Mestre dos Quizzes",
        description="Acertou mais de 80% das questões",
        icon="award",
        iconColor="#fbbf24",
        criteria=BadgeCriteria(type="quiz_score", threshold=80, operator="gte"),
        isDefault=True
    ),
    Badge(
        id="badge_quiz_perfect",
        name="Perfeição Total",
        description="Acertou 100% das questões",
        icon="star",
        iconColor="#f59e0b",
        criteria=BadgeCriteria(type="quiz_score", threshold=100, operator="eq"),
        isDefault=True
    ),
    Badge(
        id="badge_decision_maker",
        name="Tomador de Decisões",
        description="Obteve mais de 70% nos cenários",
        icon="target",
        iconColor="#10b981",
        criteria=BadgeCriteria(type="scenario_score", threshold=70, operator="gte"),
        isDefault=True
    ),
    Badge(
        id="badge_strategic_thinker",
        name="Pensador Estratégico",
        description="Obteve mais de 90% nos cenários",
        icon="brain",
        iconColor="#8b5cf6",
        criteria=BadgeCriteria(type="scenario_score", threshold=90, operator="gte"),
        isDefault=True
    ),
    Badge(
        id="badge_course_complete",
        name="Curso Concluído",
        description="Completou todo o curso",
        icon="check-circle",
        iconColor="#06b6d4",
        criteria=BadgeCriteria(type="course_completion", threshold=100, operator="eq"),
        isDefault=True
    ),
]

DEFAULT_QUIZ_FEEDBACK = [
    FeedbackRange(id="quiz_fb_low", minScore=0, maxScore=50, title="Precisa Revisar", message="Recomendamos revisar o conteúdo e tentar novamente.", emoji="📚"),
    FeedbackRange(id="quiz_fb_medium", minScore=51, maxScore=70, title="Bom Progresso", message="Você está no caminho certo! Continue estudando.", emoji="👍"),
    FeedbackRange(id="quiz_fb_good", minScore=71, maxScore=89, title="Muito Bem!", message="Ótimo desempenho! Você domina a maior parte do conteúdo.", emoji="🌟"),
    FeedbackRange(id="quiz_fb_excellent", minScore=90, maxScore=100, title="Excelente!", message="Parabéns! Você demonstrou domínio completo do conteúdo!", emoji="🎉"),
]

DEFAULT_SCENARIO_FEEDBACK = [
    FeedbackRange(id="scenario_fb_low", minScore=0, maxScore=50, title="Oportunidade de Melhoria", message="Suas escolhas podem ser aprimoradas. Que tal tentar novamente?", emoji="🔄"),
    FeedbackRange(id="scenario_fb_medium", minScore=51, maxScore=70, title="Boas Decisões", message="Você tomou decisões razoáveis. Há espaço para melhorar!", emoji="💪"),
    FeedbackRange(id="scenario_fb_good", minScore=71, maxScore=89, title="Decisões Estratégicas", message="Suas escolhas demonstram boa capacidade de análise!", emoji="🎯"),
    FeedbackRange(id="scenario_fb_excellent", minScore=90, maxScore=100, title="Liderança Exemplar!", message="Suas decisões foram excepcionais! Você é um líder nato!", emoji="🏆"),
]
