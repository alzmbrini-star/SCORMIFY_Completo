/**
 * SCORM Course Player
 */

// Detect mobile device and apply mobile mode
function initMobileMode() {
    var isMobileDevice = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    var isSmallScreen = window.innerWidth < 1024 || window.innerHeight < 700;
    var isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    
    console.log('[Mobile] Detection:', { isMobileDevice: isMobileDevice, isSmallScreen: isSmallScreen, isTouchDevice: isTouchDevice });
    
    if (isMobileDevice || (isSmallScreen && isTouchDevice)) {
        document.body.classList.add('mobile-mode');
        console.log('[Mobile] Mobile mode enabled via JS');
    }
}

// Run mobile detection immediately
initMobileMode();

// Also run on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    initMobileMode();
});

// Mobile orientation detection - Show overlay when in portrait mode on small screens
var pendingScaleUpdate = false;

function checkMobileOrientation() {
    var overlay = document.getElementById('orientation-overlay');
    var playerContainer = document.getElementById('player-container');
    if (!overlay || !playerContainer) return;
    
    // Use multiple methods to detect orientation
    // Method 1: Screen dimensions (most reliable for actual device)
    var screenWidth = screen.width || 0;
    var screenHeight = screen.height || 0;
    
    // Method 2: Window dimensions
    var windowWidth = window.innerWidth || document.documentElement.clientWidth || 0;
    var windowHeight = window.innerHeight || document.documentElement.clientHeight || 0;
    
    // Method 3: Screen orientation API
    var orientationType = (screen.orientation && screen.orientation.type) || '';
    var isOrientationPortrait = orientationType.includes('portrait');
    
    // Method 4: matchMedia (CSS media query via JS)
    var mediaPortrait = window.matchMedia && window.matchMedia('(orientation: portrait)').matches;
    
    // Calculate aspect ratios
    var screenAspectRatio = screenWidth / screenHeight;
    var windowAspectRatio = windowWidth / windowHeight;
    
    // Detect mobile device
    var isMobileDevice = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    var isSmallScreen = Math.min(screenWidth, windowWidth) < 900;
    
    // Log for debugging
    console.log('[Orientation] check:', {
        screen: screenWidth + 'x' + screenHeight,
        window: windowWidth + 'x' + windowHeight,
        orientationType: orientationType,
        mediaPortrait: mediaPortrait,
        isMobile: isMobileDevice
    });
    
    // Determine if we should show the overlay (force landscape on mobile)
    var isPortrait = windowWidth < windowHeight;
    var shouldShowOverlay = false;
    
    if (isMobileDevice || isSmallScreen) {
        // Use multiple signals to detect portrait mode
        if (isOrientationPortrait || mediaPortrait || isPortrait) {
            shouldShowOverlay = true;
        }
    }
    
    // Check if user dismissed the overlay
    var overlayDismissed = false;
    try { overlayDismissed = sessionStorage.getItem('orientation_overlay_dismissed') === 'true'; } catch(e) {}
    
    var wasHidden = playerContainer.style.display === 'none';
    
    if (shouldShowOverlay && !overlayDismissed) {
        overlay.style.display = 'flex';
        playerContainer.style.display = 'none';
    } else {
        overlay.style.display = 'none';
        playerContainer.style.display = 'flex';
        
        // Update scale when returning from portrait overlay
        if (wasHidden && typeof CoursePlayer !== 'undefined' && CoursePlayer.updateScale) {
            setTimeout(function() {
                CoursePlayer.updateScale();
            }, 100);
        }
    }
}

// Listen for orientation changes (mobile devices)
var orientationCheckTimeout = null;
function debouncedOrientationCheck() {
    clearTimeout(orientationCheckTimeout);
    orientationCheckTimeout = setTimeout(checkMobileOrientation, 200);
}

window.addEventListener('orientationchange', function() {
    debouncedOrientationCheck();
});

// Listen for resize events
var resizeTimeout = null;
window.addEventListener('resize', function() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(function() {
        checkMobileOrientation();
        if (typeof CoursePlayer !== 'undefined' && CoursePlayer.updateScale) {
            CoursePlayer.updateScale();
        }
    }, 150);
});

// Initial check on load
window.addEventListener('load', function() {
    checkMobileOrientation();
});

// Also check on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(checkMobileOrientation, 50);
});

// VLibras automatic translation helper
// Uses Plugin.translate(text) which requires the Unity player to be fully loaded
// The player emits a 'load' event when ready. player.isLoaded() checks readiness.
var _vlibrasQueue = [];
var _vlibrasPlayerLoaded = false;
var _vlibrasSetupDone = false;

function _processVLibrasQueue() {
    if (_vlibrasQueue.length > 0 && window.plugin && typeof window.plugin.translate === 'function') {
        var item = _vlibrasQueue[_vlibrasQueue.length - 1];
        _vlibrasQueue = [];
        // Small delay for stability after player load
        setTimeout(function() {
            try {
                window.plugin.translate(item.text);
                console.log('[VLibras] Queued translation sent for slide ' + (item.slideIndex + 1));
            } catch(e) {
                console.log('[VLibras] Translation error:', e);
            }
        }, 1500);
    }
}

function _setupVLibrasWatcher() {
    if (_vlibrasSetupDone) return;
    _vlibrasSetupDone = true;
    
    console.log('[VLibras] Setting up player readiness watcher...');
    
    // Poll for window.plugin and player
    var pollId = setInterval(function() {
        if (!window.plugin || !window.plugin.player) return;
        clearInterval(pollId);
        console.log('[VLibras] Plugin and player instances found');
        
        var player = window.plugin.player;
        
        // Check if already loaded
        if (typeof player.isLoaded === 'function' && player.isLoaded()) {
            console.log('[VLibras] Player already loaded');
            _vlibrasPlayerLoaded = true;
            _processVLibrasQueue();
            return;
        }
        
        // Listen for load event
        if (typeof player.on === 'function') {
            player.on('load', function() {
                console.log('[VLibras] Player load event fired');
                _vlibrasPlayerLoaded = true;
                _processVLibrasQueue();
            });
            console.log('[VLibras] Listening for player load event');
        }
        
        // Backup: poll for canvas element (Unity WebGL indicator)
        var canvasPoll = setInterval(function() {
            if (_vlibrasPlayerLoaded) { clearInterval(canvasPoll); return; }
            var wrapper = document.querySelector('[vw-plugin-wrapper]');
            if (wrapper) {
                var canvas = wrapper.querySelector('canvas');
                if (canvas) {
                    clearInterval(canvasPoll);
                    console.log('[VLibras] Unity canvas detected');
                    if (!_vlibrasPlayerLoaded) {
                        _vlibrasPlayerLoaded = true;
                        _processVLibrasQueue();
                    }
                }
            }
        }, 2000);
        setTimeout(function() { clearInterval(canvasPoll); }, 120000);
        
    }, 500);
    setTimeout(function() { clearInterval(pollId); }, 120000);
}

function translateWithVLibras(text, slideIndex) {
    if (!text) return;
    console.log('[VLibras] Translation requested for slide ' + (slideIndex + 1));
    
    if (_vlibrasPlayerLoaded && window.plugin && typeof window.plugin.translate === 'function') {
        try {
            window.plugin.translate(text);
            console.log('[VLibras] Translation sent immediately');
        } catch(e) {
            console.log('[VLibras] Translate error:', e);
        }
    } else {
        // Queue the text and ensure watcher is running
        _vlibrasQueue = [{ text: text, slideIndex: slideIndex }];
        _setupVLibrasWatcher();
        console.log('[VLibras] Text queued, waiting for player to load...');
    }
}

var CoursePlayer = (function() {
    var course = null;
    var currentSlide = 0;
    var totalSlides = 0;
    var isPlaying = false;
    var slideTimer = null;
    var audioContext = null;
    var globalAudio = null;
    var activeSlideAudios = []; // Track active slide audios to stop them on navigation
    var userHasInteracted = false; // Track if user has interacted with the page
    // True if ANY slide in the course has a quiz element.
    // When true, SCORM completion must come from QuizController, NOT from navigation.
    var courseHasQuiz = false;
    
    // True if ANY slide in the course has a scenario element.
    var courseHasScenario = false;
    
    // Track completion of interactive elements
    var completedQuizzes = {};
    var completedScenarios = {};
    var totalQuizzes = 0;
    var totalScenarios = 0;
    var visitedLastSlide = false; // Track if user has reached the last slide
    var completionRequested = false; // Explicit click on "Concluir curso"
    var courseCompleted = false; // True only after the LMS accepts completion
    
    // Slide timeline progress
    var slideProgressTimer = null;
    var slideStartTimestamp = 0;
    
    // Swipe navigation variables
    var touchStartX = 0;
    var touchStartY = 0;
    var touchEndX = 0;
    var touchEndY = 0;
    var minSwipeDistance = 60;
    var swipeEnabled = true;
    
    // Auto-hide controls variables (mobile only)
    var controlsHideTimeout = null;
    var controlsHidden = false;
    var CONTROLS_HIDE_DELAY = 3000; // 3 seconds before hiding
    
    function setupAutoHideControls() {
        // Only enable on mobile devices
        var isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || window.innerWidth < 1024;
        if (!isMobile) {
            console.log('[AutoHide] Not a mobile device, skipping auto-hide setup');
            return;
        }
        
        console.log('[AutoHide] Setting up auto-hide controls for mobile');
        var controls = document.getElementById('controls');
        var playerContainer = document.getElementById('player-container');
        var slideWrapper = document.getElementById('slide-wrapper');
        if (!controls || !playerContainer) return;
        
        var controlsHeight = controls.offsetHeight || 60;
        
        // Add CSS class for transitions
        controls.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
        
        // Function to hide controls and expand content
        function hideControls() {
            if (controlsHidden) return;
            controls.style.transform = 'translateY(100%)';
            controls.style.opacity = '0';
            controls.style.pointerEvents = 'none';
            controlsHidden = true;
            
            // Add class to expand content
            playerContainer.classList.add('controls-hidden');
            
            // Recalculate scale to use more space after transition
            setTimeout(function() { 
                updateSlideScale();
                console.log('[AutoHide] Scale updated after hide');
            }, 350);
            console.log('[AutoHide] Controls hidden, expanding content');
        }
        
        // Function to show controls and restore content
        function showControls() {
            controls.style.transform = 'translateY(0)';
            controls.style.opacity = '1';
            controls.style.pointerEvents = 'auto';
            controlsHidden = false;
            
            // Remove class to restore content
            playerContainer.classList.remove('controls-hidden');
            
            // Recalculate scale after transition
            setTimeout(function() { 
                updateSlideScale();
                console.log('[AutoHide] Scale updated after show');
            }, 350);
            console.log('[AutoHide] Controls shown');
            resetHideTimeout();
        }
        
        // Reset the hide timeout
        function resetHideTimeout() {
            if (controlsHideTimeout) {
                clearTimeout(controlsHideTimeout);
            }
            controlsHideTimeout = setTimeout(hideControls, CONTROLS_HIDE_DELAY);
        }
        
        // Show controls on any interaction
        document.addEventListener('touchstart', function(e) {
            showControls();
        }, { passive: true });
        
        document.addEventListener('click', function(e) {
            showControls();
        }, { passive: true });
        
        // Start the initial hide timeout
        resetHideTimeout();
    }
    
    function setupSwipeNavigation() {
        console.log('[Swipe] Setting up swipe navigation');
        
        // Variables to track touch positions
        var swipeTouchStartX = 0;
        var swipeTouchStartY = 0;
        var swipeInProgress = false;
        
        // Add swipe support - use capture phase to get events before iframes
        document.addEventListener('touchstart', function(e) {
            // Don't track swipes if touching an iframe directly
            if (e.target.tagName === 'IFRAME') {
                console.log('[Swipe] Touch on iframe, skipping');
                return;
            }
            swipeTouchStartX = e.touches[0].clientX;
            swipeTouchStartY = e.touches[0].clientY;
            swipeInProgress = true;
            console.log('[Swipe] Touch start at X:', swipeTouchStartX);
        }, { passive: true, capture: true });
        
        document.addEventListener('touchmove', function(e) {
            if (!swipeInProgress) return;
            
            // If scrolling vertically, cancel swipe detection
            var currentY = e.touches[0].clientY;
            var deltaY = Math.abs(currentY - swipeTouchStartY);
            if (deltaY > 50) {
                swipeInProgress = false;
                console.log('[Swipe] Cancelled - vertical scroll detected');
            }
        }, { passive: true, capture: true });
        
        document.addEventListener('touchend', function(e) {
            if (!swipeInProgress) {
                return;
            }
            swipeInProgress = false;
            
            var touchEndX = e.changedTouches[0].clientX;
            var touchEndY = e.changedTouches[0].clientY;
            
            var deltaX = touchEndX - swipeTouchStartX;
            var deltaY = Math.abs(touchEndY - swipeTouchStartY);
            
            console.log('[Swipe] Touch end. DeltaX:', deltaX, 'DeltaY:', deltaY);
            
            // Require significant horizontal swipe (100px) and mostly horizontal movement
            if (Math.abs(deltaX) > 100 && Math.abs(deltaX) > deltaY * 2) {
                // Don't swipe if touching interactive elements
                var target = e.target;
                if (target.closest && (target.closest('button') || target.closest('.quiz-player-container') || target.closest('input') || target.closest('select') || target.closest('a'))) {
                    console.log('[Swipe] Touch on interactive element, skipping');
                    return;
                }
                
                if (deltaX < 0) {
                    // Swipe left - go to next slide
                    console.log('[Swipe] Left swipe detected, going to next slide');
                    CoursePlayer.next();
                } else {
                    // Swipe right - go to previous slide
                    console.log('[Swipe] Right swipe detected, going to previous slide');
                    CoursePlayer.prev();
                }
            }
        }, { passive: true, capture: true });
        
        // Also add swipe detection on the main container
        var slideContent = document.getElementById('slide-content');
        if (slideContent) {
            slideContent.addEventListener('touchstart', function(e) {
                swipeTouchStartX = e.touches[0].clientX;
                swipeTouchStartY = e.touches[0].clientY;
                swipeInProgress = true;
            }, { passive: true });
            
            slideContent.addEventListener('touchend', function(e) {
                if (!swipeInProgress) return;
                swipeInProgress = false;
                
                var touchEndX = e.changedTouches[0].clientX;
                var touchEndY = e.changedTouches[0].clientY;
                
                var deltaX = touchEndX - swipeTouchStartX;
                var deltaY = Math.abs(touchEndY - swipeTouchStartY);
                
                if (Math.abs(deltaX) > 100 && Math.abs(deltaX) > deltaY * 2) {
                    if (deltaX < 0) {
                        CoursePlayer.next();
                    } else {
                        CoursePlayer.prev();
                    }
                }
            }, { passive: true });
        }
        
        console.log('[Swipe] Swipe navigation setup complete');
    }
    
    function loadCourse(courseData) {
        course = courseData;
        totalSlides = course.slides.length;

        // Initialize synchronously before reading the bookmark or rendering
        // the last slide. Waiting only for window.load created a race where
        // setComplete() ran while the wrapper was still uninitialized.
        ScormAPI.initialize();
        
        // Detect if ANY slide contains a quiz element.
        // If so, completion must be sent from QuizController.showResults(), not from navigation.
        courseHasQuiz = course.slides.some(function(s) {
            return s.elements && s.elements.some(function(el) {
                return (el.type || '').toLowerCase() === 'quiz';
            });
        });
        
        // Detect if ANY slide contains a scenario element.
        courseHasScenario = course.slides.some(function(s) {
            return s.elements && s.elements.some(function(el) {
                return (el.type || '').toLowerCase() === 'scenario';
            });
        });
        
        // Count total quizzes and scenarios for completion tracking
        totalQuizzes = 0;
        totalScenarios = 0;
        course.slides.forEach(function(s, slideIndex) {
            if (s.elements) {
                s.elements.forEach(function(el) {
                    if ((el.type || '').toLowerCase() === 'quiz') {
                        totalQuizzes++;
                    }
                    if ((el.type || '').toLowerCase() === 'scenario') {
                        totalScenarios++;
                    }
                });
            }
        });
        
        console.log('[Player] courseHasQuiz:', courseHasQuiz, 'totalQuizzes:', totalQuizzes);
        console.log('[Player] courseHasScenario:', courseHasScenario, 'totalScenarios:', totalScenarios);
        
        // Check orientation on load
        checkMobileOrientation();
        
        // Restore position from SCORM
        var savedPosition = ScormAPI.getLocation();
        if (savedPosition > 0 && savedPosition < totalSlides) {
            currentSlide = savedPosition;
        }
        
        renderSlide(currentSlide);
        updateProgress();
        renderSidebar();
        
        // Force scale update after initial render (ensures correct size after orientation)
        setTimeout(updateSlideScale, 50);
        setTimeout(updateSlideScale, 150);
        setTimeout(updateSlideScale, 300);
        
        // Setup global audio if exists
        if (course.globalAudio && course.globalAudio.src) {
            setupGlobalAudio();
        }
        
        // Check if first slide has audio and show start overlay
        checkAndShowStartOverlay();
        
        // Setup swipe navigation for mobile
        setupSwipeNavigation();
        
        // Recalculate scale on window resize - only update scale, don't re-render
        var resizeTimeout;
        window.addEventListener('resize', function() {
            // Skip completely if a video is in fullscreen mode
            var fullscreenElement = document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement;
            if (fullscreenElement) {
                return;
            }
            
            // Skip if we just exited fullscreen
            if (fullscreenExitProtection) {
                return;
            }
            
            // Debounce resize
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(function() {
                // Only update scale, don't re-render the entire slide
                updateSlideScale();
            }, 150);
        });
        
        // Handle orientation change specifically - needs multiple updates due to browser timing
        window.addEventListener('orientationchange', function() {
            // Update immediately
            updateSlideScale();
            // Update again after a short delay (browser may not have finished layout)
            setTimeout(updateSlideScale, 100);
            // And again after layout is definitely complete
            setTimeout(updateSlideScale, 300);
            setTimeout(updateSlideScale, 500);
        });
        
        // Listen for fullscreen changes to prevent re-renders
        document.addEventListener('fullscreenchange', handleFullscreenChange);
        document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
        document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    }
    
    function updateSlideScale() {
        // Just update the transform scale without re-rendering elements
        var container = document.getElementById('slide-container');
        var wrapper = document.getElementById('slide-wrapper');
        if (!container || !wrapper) return;
        
        var slide = course.slides[currentSlide];
        if (!slide) return;
        
        var slideWidth = slide.width || 960;
        var slideHeight = slide.height || 540;
        var slideAspectRatio = slideWidth / slideHeight;
        
        // Detect mobile device
        var isMobileDevice = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        var isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
        var isSmallScreen = window.innerWidth <= 1024 || window.innerHeight <= 600;
        // Consider it mobile if any of these conditions are true
        var isMobile = isMobileDevice || isTouchDevice || isSmallScreen;
        
        // Detect portrait orientation
        var isPortrait = window.innerHeight > window.innerWidth;
        var isMobilePortrait = isMobile && isPortrait;
        
        console.log('[Scale] Device:', { isMobile: isMobile, isPortrait: isPortrait, innerWidth: window.innerWidth, innerHeight: window.innerHeight });
        
        // Portrait mode: use standard scaling (overlay is dismissable)
        
        // DESKTOP / LANDSCAPE MODE - Fit within available space
        // Reset wrapper styles that might have been modified
        wrapper.style.padding = '';
        wrapper.style.margin = '';
        wrapper.style.width = '';
        wrapper.style.maxWidth = '';
        wrapper.style.alignItems = '';
        wrapper.style.justifyContent = '';
        wrapper.style.paddingTop = '';
        container.style.marginLeft = '';
        container.style.boxShadow = '';
        
        // Detect mobile landscape mode
        var isMobileLandscape = isMobile && !isPortrait;
        
        // DESKTOP / LANDSCAPE MODE - Standard scaling with padding
        // Reset container position if it was set to fixed
        container.style.position = '';
        container.style.top = '';
        container.style.left = '';
        container.style.zIndex = '';
        
        // Reset wrapper styles
        wrapper.style.cssText = '';
        
        // Get available space from wrapper, accounting for padding
        var wrapperRect = wrapper.getBoundingClientRect();
        var wrapperStyle = window.getComputedStyle(wrapper);
        var paddingX = parseFloat(wrapperStyle.paddingLeft) + parseFloat(wrapperStyle.paddingRight);
        var paddingY = parseFloat(wrapperStyle.paddingTop) + parseFloat(wrapperStyle.paddingBottom);
        
        var availableWidth = wrapperRect.width - paddingX;
        var availableHeight = wrapperRect.height - paddingY;
        
        // Skip if dimensions are invalid
        if (availableWidth < 100 || availableHeight < 100) return;
        
        // Calculate scale to fit available space
        var scaleX = availableWidth / slideWidth;
        var scaleY = availableHeight / slideHeight;
        
        // Use the smaller scale to maintain aspect ratio
        var scale = Math.min(scaleX, scaleY);
        
        // On desktop, cap at 1.2 to avoid pixelation
        var maxScale = 1.2;
        scale = Math.min(scale, maxScale);
        
        // Ensure minimum scale for readability (lowered for portrait mobile support)
        var minScale = 0.15;
        scale = Math.max(scale, minScale);
        
        // Apply scale to container
        container.style.width = slideWidth + 'px';
        container.style.height = slideHeight + 'px';
        container.style.transform = 'scale(' + scale + ')';
        container.style.transformOrigin = '0 0';
        
        // Shrink layout box to match visual size so flexbox centering works correctly
        container.style.marginRight = -(slideWidth * (1 - scale)) + 'px';
        container.style.marginBottom = -(slideHeight * (1 - scale)) + 'px';
        
        // Log for debugging
        console.log('[Scale] scale:', scale.toFixed(2), 'available:', availableWidth + 'x' + availableHeight);
    }
    
    var isVideoFullscreen = false;
    var fullscreenExitProtection = false;
    var videoStates = {}; // Store video states by element ID
    var lastFullscreenVideoId = null; // Track which video was in fullscreen
    
    function saveAllVideoStates() {
        var videos = document.querySelectorAll('#slide-container video');
        videos.forEach(function(video) {
            var elementId = video.dataset.elementId;
            if (elementId) {
                videoStates[elementId] = {
                    currentTime: video.currentTime,
                    paused: video.paused,
                    muted: video.muted,
                    volume: video.volume,
                    src: video.src
                };
                console.log('Saved video state:', elementId, videoStates[elementId]);
            }
        });
    }
    
    function restoreVideoState(video) {
        var elementId = video.dataset.elementId;
        if (elementId && videoStates[elementId]) {
            var state = videoStates[elementId];
            console.log('Restoring video state:', elementId, state);
            try {
                video.currentTime = state.currentTime;
                video.muted = state.muted;
                video.volume = state.volume;
                if (!state.paused) {
                    video.play().catch(function() {
                        video.muted = true;
                        video.play().catch(function() {});
                    });
                }
            } catch (e) {
                console.log('Error restoring video state:', e);
            }
        }
    }
    
    function restoreAllVideoStates() {
        var videos = document.querySelectorAll('#slide-container video');
        videos.forEach(function(video) {
            restoreVideoState(video);
        });
    }
    
    function handleFullscreenChange() {
        var fullscreenElement = document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement;
        
        if (fullscreenElement && fullscreenElement.tagName === 'VIDEO') {
            // Video entering fullscreen
            isVideoFullscreen = true;
            fullscreenExitProtection = false;
            lastFullscreenVideoId = fullscreenElement.dataset.elementId;
            // Save state of ALL videos when entering fullscreen
            saveAllVideoStates();
            console.log('Entered fullscreen:', lastFullscreenVideoId);
        } else if (isVideoFullscreen) {
            // Video just exited fullscreen
            console.log('Exited fullscreen:', lastFullscreenVideoId);
            isVideoFullscreen = false;
            fullscreenExitProtection = true;
            
            // Immediately restore all video states after exit
            setTimeout(function() {
                restoreAllVideoStates();
            }, 100);
            
            // Keep protection for longer to ensure no re-render happens
            setTimeout(function() {
                fullscreenExitProtection = false;
                lastFullscreenVideoId = null;
            }, 3000);
        }
    }
    
    function checkAndShowStartOverlay() {
        // Only show overlay if on first slide and it has audio (or global audio)
        var firstSlide = course.slides[0];
        var hasAudio = (firstSlide.audio && firstSlide.audio.length > 0) || 
                       (course.globalAudio && course.globalAudio.src);
        
        if (currentSlide === 0 && hasAudio && !userHasInteracted) {
            showStartOverlay();
        }
    }
    
    function showStartOverlay() {
        var overlay = document.getElementById('start-overlay');
        if (overlay) {
            overlay.style.display = 'flex';
        }
    }
    
    function hideStartOverlay() {
        var overlay = document.getElementById('start-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
        userHasInteracted = true;
        
        // Now play the audio
        var firstSlide = course.slides[0];
        if (firstSlide.audio && firstSlide.audio.length > 0) {
            playSlideAudio(firstSlide.audio);
        }
        if (globalAudio) {
            globalAudio.play().catch(function(e) {
                console.log('Global audio play failed:', e);
            });
        }
    }
    
    function setupGlobalAudio() {
        globalAudio = document.getElementById('global-audio');
        if (globalAudio && course.globalAudio) {
            globalAudio.src = course.globalAudio.src;
            globalAudio.volume = course.globalAudio.volume || 0.5;
            globalAudio.loop = course.globalAudio.loop !== false;
        }
    }
    
    // Stop all currently playing slide audios and scheduled audio timers
    function stopAllSlideAudios() {
        activeSlideAudios.forEach(function(audio) {
            try {
                audio.pause();
                audio.currentTime = 0;
            } catch(e) {
                console.log('Error stopping audio:', e);
            }
        });
        activeSlideAudios = [];
        // Clear any scheduled audio timeline timers
        if (window.audioTimelineTimers) {
            window.audioTimelineTimers.forEach(function(t) { clearTimeout(t); });
            window.audioTimelineTimers = [];
        }
    }
    
    // Slide timeline progress bar
    function startSlideProgress(slideDuration) {
        stopSlideProgress();
        var fill = document.getElementById('slide-timeline-fill');
        var bar = document.getElementById('slide-timeline-bar');
        if (!fill || !bar) return;
        
        fill.classList.remove('complete');
        fill.style.width = '0%';
        bar.style.display = '';
        
        if (!slideDuration || slideDuration <= 0) {
            // No duration set - hide the bar
            bar.style.display = 'none';
            return;
        }
        
        slideStartTimestamp = Date.now();
        var durationMs = slideDuration * 1000;
        
        slideProgressTimer = setInterval(function() {
            var elapsed = Date.now() - slideStartTimestamp;
            var pct = Math.min((elapsed / durationMs) * 100, 100);
            fill.style.width = pct + '%';
            
            if (pct >= 100) {
                fill.classList.add('complete');
                clearInterval(slideProgressTimer);
                slideProgressTimer = null;
            }
        }, 50);
    }
    
    function stopSlideProgress() {
        if (slideProgressTimer) {
            clearInterval(slideProgressTimer);
            slideProgressTimer = null;
        }
    }
    
    function renderSlide(index) {
        // Don't re-render if a video is in fullscreen or just exited fullscreen
        if (isVideoFullscreen || fullscreenExitProtection) {
            return;
        }
        
        // Stop any playing slide audio before rendering new slide
        stopAllSlideAudios();
        stopSlideProgress();
        
        var slide = course.slides[index];
        var container = document.getElementById('slide-container');
        var wrapper = document.getElementById('slide-wrapper');
        
        // Get slide dimensions - use the slide's own dimensions
        var slideWidth = slide.width || 960;
        var slideHeight = slide.height || 540;
        
        // Set initial container dimensions (scale will be applied by updateSlideScale)
        container.style.width = slideWidth + 'px';
        container.style.height = slideHeight + 'px';
        
        // Clear previous content
        container.innerHTML = '';
        
        // Clear any existing timeline timers
        if (window.slideTimelineTimers) {
            window.slideTimelineTimers.forEach(function(timer) {
                clearTimeout(timer);
            });
        }
        window.slideTimelineTimers = [];
        
        // Helper function to optimize elements for mobile
        // Mobile optimization removed: transform: scale() on the container
        // already handles proportional sizing for ALL elements.
        // Position/size overrides were causing element overlap on multi-element slides.
        
        // Zoom-on-hotspot effect (Tutorial Agent imports): when slide carries
        // a `zoomEffect`, we wrap the bg-image + every element in a transform
        // stage so the magnify animation moves the background AND the hotspot
        // overlay together (so the hotspot keeps pointing at the right thing).
        var zoomStage = null;
        var zoomEffect = slide.zoomEffect && typeof slide.zoomEffect === 'object' ? slide.zoomEffect : null;
        if (zoomEffect && parseFloat(zoomEffect.scale || 1) > 1) {
            zoomStage = document.createElement('div');
            zoomStage.className = 'slide-zoom-stage';
            zoomStage.style.position = 'absolute';
            zoomStage.style.inset = '0';
            zoomStage.style.transformOrigin =
                (zoomEffect.focusX != null ? zoomEffect.focusX : 50) + '% ' +
                (zoomEffect.focusY != null ? zoomEffect.focusY : 50) + '%';
            zoomStage.style.willChange = 'transform';
            zoomStage.style.zIndex = '0';
            // Container must clip what overflows when the stage scales up
            container.style.overflow = 'hidden';
            container.appendChild(zoomStage);
        }
        // Single place to append every render target so the wrapper logic
        // is decided exactly once per slide.
        var renderTarget = zoomStage || container;

        // Set background (use 'background' shorthand to support gradients)
        container.style.background = slide.background || '#FFFFFF';
        if (slide.backgroundImage) {
            // Create background image element - must fill entire container
            var bgImg = document.createElement('img');
            bgImg.src = slide.backgroundImage;
            bgImg.style.position = 'absolute';
            bgImg.style.top = '0';
            bgImg.style.left = '0';
            bgImg.style.width = '100%';
            bgImg.style.height = '100%';
            // 2026-05-25: honor `backgroundImageFit` per slide. Modo Fiel
            // sets `"contain"` so the WHOLE PDF page is visible (no top/
            // side cropping when aspect ratios differ). Other slides keep
            // the default `cover` so decorative backgrounds fill the canvas.
            // Backwards-compat: legacy Modo Fiel slides exported before
            // this fix are detected via `_pdfFaithful`/`type==='content'`
            // + presence of `backgroundImage` and forced to contain.
            var fitMode = slide.backgroundImageFit;
            if (!fitMode) {
                if (slide._pdfFaithful) {
                    fitMode = 'contain';
                } else {
                    fitMode = 'cover';
                }
            }
            bgImg.style.objectFit = fitMode;
            bgImg.style.objectPosition = 'center center';
            bgImg.style.pointerEvents = 'none';
            bgImg.style.zIndex = '0';
            // Apply background image opacity if set
            if (slide.backgroundImageOpacity != null && slide.backgroundImageOpacity !== undefined) {
                bgImg.style.opacity = slide.backgroundImageOpacity;
            }
            renderTarget.appendChild(bgImg);

            // Aesthetic Analyzer scrim/overlay over background image
            if (slide.backgroundImageOverlay) {
                var overlay = document.createElement('div');
                overlay.style.position = 'absolute';
                overlay.style.inset = '0';
                overlay.style.pointerEvents = 'none';
                overlay.style.zIndex = '1';
                if (slide.backgroundImageOverlay === 'dark') {
                    overlay.style.background = 'linear-gradient(180deg,rgba(0,0,0,0.45),rgba(0,0,0,0.65))';
                } else if (slide.backgroundImageOverlay === 'light') {
                    overlay.style.background = 'linear-gradient(180deg,rgba(255,255,255,0.55),rgba(255,255,255,0.75))';
                } else {
                    overlay.style.background = slide.backgroundImageOverlay;
                }
                renderTarget.appendChild(overlay);
            }
        }
        
        // Get slide duration for timeline - consider audio and video durations
        var slideDuration = slide.duration || 10;
        
        // Calculate actual media duration (audio + video)
        var maxMediaDuration = 0;
        if (slide.audio && slide.audio.length > 0) {
            slide.audio.forEach(function(a) {
                var audioEnd = (a.startTime || 0) + (a.duration || 0);
                if (audioEnd > maxMediaDuration) maxMediaDuration = audioEnd;
            });
        }
        // Check for HeyGen/video elements
        if (slide.elements) {
            slide.elements.forEach(function(el) {
                if (el.type === 'video' || el.type === 'heygen') {
                    var videoEnd = (el.startTime || 0) + (el.duration || 0);
                    if (videoEnd > maxMediaDuration) maxMediaDuration = videoEnd;
                }
            });
        }
        // Use the longer of slide duration or media duration (with 1s buffer)
        if (maxMediaDuration > 0 && maxMediaDuration > slideDuration) {
            slideDuration = maxMediaDuration + 1;
        }
        
        // Render elements
        slide.elements.forEach(function(element, elemIndex) {
            // Note: visible=false elements from PPT import are still rendered
            // (the editor shows them too). Only skip if explicitly marked for exclusion.
            
            var el = createElementNode(element);
            if (el) {
                // Get the intended opacity from element style (default 1)
                var elementOpacity = (element.style && element.style.opacity !== undefined && element.style.opacity !== null) 
                    ? element.style.opacity : 1;
                
                // Check if element has timeline settings
                var startTime = element.startTime || 0;
                var endTime = element.endTime !== undefined && element.endTime !== null ? element.endTime : slideDuration;
                
                // If element should not appear immediately, hide it
                if (startTime > 0) {
                    el.style.opacity = '0';
                    el.style.visibility = 'hidden';
                    el.style.transition = 'opacity 0.3s ease-in-out';
                    
                    // Schedule element to appear at startTime (respecting element's own opacity)
                    var showTimer = setTimeout(function() {
                        el.style.opacity = String(elementOpacity);
                        el.style.visibility = 'visible';
                    }, startTime * 1000);
                    window.slideTimelineTimers.push(showTimer);
                }
                
                // Schedule element to hide at endTime (if endTime is before slide duration)
                if (endTime < slideDuration) {
                    var hideTimer = setTimeout(function() {
                        el.style.opacity = '0';
                        el.style.visibility = 'hidden';
                    }, endTime * 1000);
                    window.slideTimelineTimers.push(hideTimer);
                }
                
                container.appendChild(el);
                // When a zoom stage exists, also mirror the element inside the
                // stage so it scales with the magnify. (We keep it in the
                // container for stable z-ordering and event handling — the
                // visible stage copy is the one the user sees animate.)
                if (zoomStage) {
                    // Re-parent into the stage. The element is positioned
                    // by absolute left/top in slide-pixel units, so it lays
                    // out identically whether parented to container or to
                    // the inset:0 stage.
                    zoomStage.appendChild(el);
                }
                
                // Apply entrance animations
                var anims = element.animations && element.animations.length > 0 ? element.animations : [];
                if (!anims.length && element.animation && element.animation.effect) {
                    anims = [{
                        type: element.animation.type || 'entrance',
                        effect: element.animation.effect,
                        duration: element.animation.duration || 0.5,
                        startTime: element.animation.delay || 0,
                    }];
                }
                if (anims.length > 0) {
                    scheduleAnimations(el, anims, elementOpacity);
                }
            }
        });
        
        // Render annotations if included in export (with timeline support)
        if (slide.annotations) {
            slide.annotations.forEach(function(annotation) {
                if (annotation.includeInExport) {
                    var annotationEl = renderAnnotation(container, annotation);
                    if (annotationEl) {
                        // Check if annotation has timeline settings
                        var startTime = annotation.startTime || 0;
                        var endTime = annotation.endTime !== undefined && annotation.endTime !== null ? annotation.endTime : slideDuration;
                        
                        // If annotation should not appear immediately, hide it
                        if (startTime > 0) {
                            annotationEl.style.opacity = '0';
                            annotationEl.style.visibility = 'hidden';
                            annotationEl.style.transition = 'opacity 0.3s ease-in-out';
                            
                            // Schedule annotation to appear at startTime
                            var showTimer = setTimeout(function() {
                                annotationEl.style.opacity = '1';
                                annotationEl.style.visibility = 'visible';
                            }, startTime * 1000);
                            window.slideTimelineTimers.push(showTimer);
                        }
                        
                        // Schedule annotation to hide at endTime (if endTime is before slide duration)
                        if (endTime < slideDuration) {
                            var hideTimer = setTimeout(function() {
                                annotationEl.style.opacity = '0';
                                annotationEl.style.visibility = 'hidden';
                            }, endTime * 1000);
                            window.slideTimelineTimers.push(hideTimer);
                        }
                    }
                }
            });
        }
        
        // Play slide audio (only if user has interacted or not first slide)
        if (slide.audio && slide.audio.length > 0) {
            if (userHasInteracted || index > 0) {
                playSlideAudio(slide.audio, slideDuration, function(actualDuration) {
                    // When audio reveals its real duration, restart progress bar if needed
                    if (actualDuration > slideDuration) {
                        slideDuration = actualDuration + 1;
                        startSlideProgress(slideDuration);
                    }
                });
            }
        }
        
        // Start slide timeline progress bar
        startSlideProgress(slideDuration);
        
        // Apply scale for current device/orientation
        updateSlideScale();
        
        // Update navigation
        updateNavigation();
        
        // Save position to SCORM
        ScormAPI.setLocation(index);
        
        // Send LIBRAS script to VLibras for automatic translation
        if (slide.librasScript && slide.librasScript.trim()) {
            translateWithVLibras(slide.librasScript.trim(), index);
        }
        
        // Reaching the last slide only makes it eligible for completion.
        // The LMS status is sent after the learner explicitly clicks the
        // final "Concluir curso" action; this prevents an LMS stage from
        // closing while the final content is still being consumed.
        if (index === totalSlides - 1) {
            visitedLastSlide = true;
        }

        // Trigger the zoom-on-hotspot animation (Tutorial Agent imports).
        // We schedule the start AFTER the slide fade-in completes (200ms)
        // so the scale animation reads as a "magnify-in" instead of a jump.
        if (zoomStage && zoomEffect) {
            var z_scale = parseFloat(zoomEffect.scale || 1);
            var z_intro = parseInt(zoomEffect.intro || 800, 10);
            var z_hold = parseInt(zoomEffect.hold || 2400, 10);
            var z_outro = parseInt(zoomEffect.outro || 600, 10);
            // Reset transition so a re-render of the same slide replays
            zoomStage.style.transition = 'none';
            zoomStage.style.transform = 'scale(1)';
            // Force reflow so the browser commits the reset
            void zoomStage.offsetWidth;
            var introTimer = setTimeout(function() {
                zoomStage.style.transition = 'transform ' + z_intro + 'ms cubic-bezier(.2,.8,.2,1)';
                zoomStage.style.transform = 'scale(' + z_scale + ')';
                var outroTimer = setTimeout(function() {
                    zoomStage.style.transition = 'transform ' + z_outro + 'ms cubic-bezier(.4,0,.2,1)';
                    zoomStage.style.transform = 'scale(1)';
                }, z_intro + z_hold);
                window.slideTimelineTimers.push(outroTimer);
            }, 300);
            window.slideTimelineTimers.push(introTimer);
        }
    }
    
    // Central function to check if all interactive elements are done and set completion
    function checkAndSetCompletion() {
        var quizzesComplete = Object.keys(completedQuizzes).length >= totalQuizzes;
        var scenariosComplete = Object.keys(completedScenarios).length >= totalScenarios;
        
        console.log('[Player] Checking completion:', {
            visitedLastSlide: visitedLastSlide,
            completionRequested: completionRequested,
            quizzesComplete: quizzesComplete,
            completedQuizzes: Object.keys(completedQuizzes).length,
            totalQuizzes: totalQuizzes,
            scenariosComplete: scenariosComplete,
            completedScenarios: Object.keys(completedScenarios).length,
            totalScenarios: totalScenarios
        });
        
        // Completion rules:
        // 1. Must visit the last slide (navigation complete)
        // 2. If course has quizzes, all quizzes must be completed
        // 3. Scenarios are optional (enrich learning but don't block completion)
        if (!visitedLastSlide) {
            console.log('[Player] Completion deferred - user has not reached last slide');
            return;
        }

        if (!completionRequested) {
            console.log('[Player] Completion deferred - waiting for explicit final action');
            return;
        }
        
        if (courseHasQuiz && !quizzesComplete) {
            console.log('[Player] Completion deferred - quizzes pending:', totalQuizzes - Object.keys(completedQuizzes).length);
            return;
        }
        
        // All conditions met: visited last slide + all quizzes done (if any)
        if (ScormAPI.setComplete()) {
            courseCompleted = true;
            updateSidebar();
            updateNavigation();
            console.log('[Player] Course marked COMPLETE! (lastSlide=' + visitedLastSlide + ', quizzes=' + Object.keys(completedQuizzes).length + '/' + totalQuizzes + ', scenarios=' + Object.keys(completedScenarios).length + '/' + totalScenarios + ')');
        } else {
            console.warn('[Player] Completion is ready but LMS API is not initialized yet; it will be retried after load/unload.');
        }
    }
    
    // Called by QuizController when a quiz is completed
    function onQuizComplete(elementId) {
        completedQuizzes[elementId] = true;
        console.log('[Player] Quiz completed:', elementId, '- Total:', Object.keys(completedQuizzes).length, '/', totalQuizzes);
        checkAndSetCompletion();
    }
    
    // Called by ScenarioController when a scenario is completed
    function onScenarioComplete(elementId) {
        completedScenarios[elementId] = true;
        console.log('[Player] Scenario completed:', elementId, '- Total:', Object.keys(completedScenarios).length, '/', totalScenarios);
        checkAndSetCompletion();
    }
    
    function createElementNode(element) {
        var el;
        // `currentSlide` is the numeric index in the classic SCORM player.
        // Always resolve the actual slide before reading its type/dimensions;
        // otherwise games fall back to 960x540 inside a 1920-wide slide.
        var activeSlide = (course && course.slides && course.slides[currentSlide]) || {};
        
        switch (element.type) {
            case 'text':
                el = document.createElement('div');
                el.className = 'slide-element text-element';
                el.innerHTML = element.content ? element.content.replace(/\n/g, '<br>') : '';
                // Set default text color (black) - matches editor behavior
                // Inline HTML styles or fontColor from element.style will override this
                el.style.color = '#000000';
                // Apply background color (transparent by default)
                if (element.style && element.style.backgroundColor) {
                    el.style.backgroundColor = element.style.backgroundColor;
                } else {
                    // Default to transparent background
                    el.style.backgroundColor = 'transparent';
                }
                break;
                
            case 'image':
                el = document.createElement('div');
                el.className = 'slide-element image-element';
                var img = document.createElement('img');
                img.src = element.src;
                img.alt = '';
                img.draggable = false;
                img.style.width = '100%';
                img.style.height = '100%';
                img.style.objectFit = element.objectFit || 'contain';
                el.appendChild(img);
                break;
                
            case 'shape':
                el = document.createElement('div');
                el.className = 'slide-element shape-element';
                // Set default text color for shape text content
                el.style.color = '#000000';
                if (element.content) {
                    el.innerHTML = element.content.replace(/\n/g, '<br>');
                }
                applyShapeStyles(el, element);
                break;
                
            case 'video':
                if (element.embedUrl) {
                    el = document.createElement('div');
                    el.className = 'slide-element video-element';
                    
                    // Extract video ID for YouTube/Vimeo
                    var embedUrl = element.embedUrl;
                    var videoId = '';
                    var isYouTube = embedUrl.indexOf('youtube') !== -1 || embedUrl.indexOf('youtu.be') !== -1;
                    var isVimeo = embedUrl.indexOf('vimeo') !== -1;
                    var isBunny = embedUrl.indexOf('iframe.mediadelivery.net') !== -1;
                    
                    if (isYouTube) {
                        var ytMatch = embedUrl.match(/(?:embed\/|v=|youtu\.be\/)([^?&"'>]+)/);
                        if (ytMatch) videoId = ytMatch[1];
                    } else if (isVimeo) {
                        var vimeoMatch = embedUrl.match(/vimeo\.com\/(?:video\/)?(\d+)/);
                        if (vimeoMatch) videoId = vimeoMatch[1];
                    }
                    
                    // For YouTube: Use iframe embed directly
                    if (isYouTube && videoId) {
                        el.style.position = 'relative';
                        el.style.background = '#000';
                        el.style.overflow = 'hidden';
                        
                        var iframe = document.createElement('iframe');
                        // Build proper YouTube embed URL
                        var ytEmbedUrl = 'https://www.youtube.com/embed/' + videoId;
                        ytEmbedUrl += '?autoplay=1&rel=0&modestbranding=1&playsinline=1&enablejsapi=1';
                        
                        iframe.src = ytEmbedUrl;
                        iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; fullscreen';
                        iframe.setAttribute('allowfullscreen', 'true');
                        iframe.setAttribute('frameborder', '0');
                        iframe.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;border:none;';
                        
                        el.appendChild(iframe);
                    } else if (isVimeo) {
                        // Vimeo: use iframe directly (generally more permissive with embedding)
                        // Add positioning for proper fullscreen
                        el.style.position = 'relative';
                        el.style.overflow = 'hidden';
                        
                        var iframe = document.createElement('iframe');
                        var vimeoSep = embedUrl.indexOf('?') !== -1 ? '&' : '?';
                        // Add parameters for better fullscreen experience
                        embedUrl += vimeoSep + 'autoplay=1&muted=0&background=0&dnt=1&title=0&byline=0&portrait=0';
                        
                        iframe.src = embedUrl;
                        iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; fullscreen';
                        iframe.allowFullscreen = true;
                        iframe.frameBorder = '0';
                        iframe.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;border:none;';
                        el.appendChild(iframe);
                    } else if (isBunny) {
                        // Bunny Stream: iframe.mediadelivery.net embed player
                        el.style.position = 'relative';
                        el.style.background = '#000';
                        el.style.overflow = 'hidden';

                        var iframe = document.createElement('iframe');
                        // Preserve the original URL byte-for-byte. Secure Bunny embeds
                        // depend on their token/expires pair and must not be reconstructed.
                        iframe.src = embedUrl;
                        iframe.allow = 'accelerometer; gyroscope; autoplay; encrypted-media; picture-in-picture;';
                        iframe.allowFullscreen = true;
                        iframe.setAttribute('allowfullscreen', 'true');
                        iframe.setAttribute('loading', 'lazy');
                        iframe.referrerPolicy = 'strict-origin-when-cross-origin';
                        iframe.frameBorder = '0';
                        iframe.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;border:none;';
                        el.appendChild(iframe);
                    } else {
                        // Other video embeds
                        var iframe = document.createElement('iframe');
                        iframe.src = embedUrl;
                        iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
                        iframe.allowFullscreen = true;
                        iframe.frameBorder = '0';
                        iframe.style.width = '100%';
                        iframe.style.height = '100%';
                        iframe.style.border = 'none';
                        el.appendChild(iframe);
                    }
                } else if (element.src) {
                    el = document.createElement('div');
                    el.className = 'slide-element video-element';
                    el.style.background = 'transparent';
                    var video = document.createElement('video');
                    video.src = element.src;
                    video.controls = false;  // Hide video controls
                    video.playsInline = true;
                    video.style.width = '100%';
                    video.style.height = '100%';
                    video.style.background = 'transparent';
                    video.style.objectFit = element.objectFit || 'contain';
                    video.style.pointerEvents = 'none';  // Prevent interaction
                    
                    // Store video reference for slide change handling
                    video.dataset.elementId = element.id;
                    
                    // Check if we have saved state for this video
                    var hasSavedState = videoStates && videoStates[element.id];
                    
                    el.appendChild(video);
                    
                    // Wait for video to be ready, then restore state or autoplay
                    video.addEventListener('loadedmetadata', function() {
                        if (hasSavedState) {
                            restoreVideoState(this);
                        } else {
                            // Autoplay only if no saved state
                            this.play().catch(function() {
                                video.muted = true;
                                video.play().catch(function() {
                                    console.log('Autoplay blocked by browser');
                                });
                            });
                        }
                    });
                    
                    // Also try immediate restore/autoplay for cached videos
                    if (video.readyState >= 1) {
                        if (hasSavedState) {
                            restoreVideoState(video);
                        } else {
                            video.play().catch(function() {
                                video.muted = true;
                                video.play().catch(function() {});
                            });
                        }
                    }
                }
                break;
            
            case 'button':
                el = document.createElement('div');
                el.className = 'slide-element button-element';
                el.style.display = 'flex';
                el.style.alignItems = 'center';
                el.style.justifyContent = 'center';
                
                var btn = document.createElement('button');
                btn.className = 'scorm-button ' + (element.buttonStyle || 'primary');
                btn.innerHTML = (element.buttonIcon ? '<span class="btn-icon">' + element.buttonIcon + '</span>' : '') + 
                               '<span>' + (element.buttonText || 'Clique aqui') + '</span>';
                btn.onclick = function(e) {
                    e.preventDefault();
                    if (element.buttonUrl) {
                        window.open(element.buttonUrl, element.openInNewTab !== false ? '_blank' : '_self');
                    }
                };
                el.appendChild(btn);
                break;
            
            case 'html':
                el = document.createElement('div');
                el.className = 'slide-element html-element';
                var htmlIframe = document.createElement('iframe');
                var htmlContent = element.htmlContent || '<p>HTML Content</p>';
                
                // Check if content is base64 encoded
                if (htmlContent.startsWith('__B64__:')) {
                    try {
                        var binaryString = atob(htmlContent.substring(8));
                        var bytes = new Uint8Array(binaryString.length);
                        for (var i = 0; i < binaryString.length; i++) {
                            bytes[i] = binaryString.charCodeAt(i);
                        }
                        htmlContent = new TextDecoder('utf-8').decode(bytes);
                    } catch(e) {
                        console.error('Failed to decode htmlContent:', e);
                    }
                }

                // Games use a deterministic 960x540 stage. Mark both current
                // and legacy game elements so they receive a full-slide
                // viewport and may scale above 1x.
                var isGeneratedGame = activeSlide.type === 'game' || element.interactiveType === 'game' || !!element.gameType || !!element.gameConfig ||
                    (/QuestionEngine|SCORMIFY\s+(?:GAMES|ADVENTURES)|EXPEDIÇÃO\s+DO\s+SABER|ARENA\s+DAS\s+PALAVRAS|LABORATÓRIO\s+DA\s+MEMÓRIA/i.test(htmlContent) &&
                     /\b(?:game|app|jogo|quest(?:ion)?engine)\b/i.test(htmlContent));
                if (isGeneratedGame) el.setAttribute('data-scormify-game', 'true');
                
                // Check if this element is truly fullscreen (covers most of the slide area)
                var slideWidth = activeSlide.width || 960;
                var slideHeight = activeSlide.height || 540;
                var isHtmlFullscreen = element.objectFit === 'cover' && 
                    element.width >= slideWidth * 0.95 && 
                    element.height >= slideHeight * 0.95 &&
                    element.x <= slideWidth * 0.05 &&
                    element.y <= slideHeight * 0.05;
                
                // Wrap in full HTML with proper CSS for text wrapping around images
                var isMobileView = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || window.innerWidth < 1024;
                // The whole 1920x1080 slide is already scaled by
                // updateSlideScale(). Do not reduce typography again inside
                // HTML iframes on mobile: doing both made authored text roughly
                // half the intended visual size and discarded inline font sizes.
                var mobileCSS = isMobileView ?
                    'body{padding:12px!important;overflow-x:hidden!important;}' +
                    'img{float:none!important;display:block!important;max-width:100%!important;width:auto!important;height:auto!important;margin:12px auto!important;clear:both!important;position:relative!important;left:0!important;right:0!important;}' +
                    'div[style*="float"]{float:none!important;width:100%!important;}'
                    : '';
                // Detect if content is a full HTML document (AI-generated)
                var isFullDoc = /<!doctype\s+html|<html[\s>]/i.test(htmlContent);
                var wrappedHtml;
                if (isFullDoc) {
                    wrappedHtml = htmlContent;
                    if (isGeneratedGame && wrappedHtml.indexOf('__scormify_game_fit_v7') === -1) {
                        var gameFit = '<style id="__scormify_game_fit_v7">html,body{margin:0!important;padding:0!important;width:100%!important;height:100%!important;overflow:hidden!important;}#__stage{width:960px!important;height:540px!important;min-width:960px!important;min-height:540px!important;max-width:none!important;max-height:none!important;transform-origin:0 0!important;}</style>' +
                            '<script>(function(){function f(){var st=document.getElementById("__stage")||document.querySelector("main.app,main.game,.app,.game");if(!st)return;var p=2,s=Math.max(.1,Math.min((innerWidth-p*2)/960,(innerHeight-p*2)/540)),x=(innerWidth-960*s)/2,y=(innerHeight-540*s)/2;st.style.setProperty("width","960px","important");st.style.setProperty("height","540px","important");st.style.setProperty("transform-origin","0 0","important");st.style.setProperty("transform","translate("+x+"px,"+y+"px) scale("+s+")","important");}addEventListener("resize",f);f();var n=0,t=setInterval(function(){f();if(++n>=24)clearInterval(t)},100);})();<\/script>';
                        var gameBodyIdx = wrappedHtml.toLowerCase().lastIndexOf('</body>');
                        wrappedHtml = gameBodyIdx !== -1 ? wrappedHtml.slice(0, gameBodyIdx) + gameFit + wrappedHtml.slice(gameBodyIdx) : wrappedHtml + gameFit;
                    }
                    // Upgrade simulators saved with the legacy flex-centered
                    // stage. CSS transforms do not affect flex layout size,
                    // so tall content was centered before scaling and its top
                    // and bottom were clipped. Absolute centering measures the
                    // full content first and then fits it with safe padding.
                    if (wrappedHtml.indexOf('__stage') !== -1 && wrappedHtml.indexOf('__scormify_fit_v3') === -1) {
                        var fitUpgrade = '<style id="__scormify_fit_v3">html,body{overflow:hidden!important;}body{display:block!important;position:relative!important;}</style>' +
                            '<script>(function(){function u(){var st=document.getElementById("__stage");if(!st)return;st.style.position="absolute";st.style.left="0";st.style.top="0";st.style.margin="0";st.style.transformOrigin="0 0";function fit(){st.style.transform="none";var sr=st.getBoundingClientRect(),minX=0,minY=0,maxX=Math.max(960,st.scrollWidth,st.offsetWidth),maxY=Math.max(540,st.scrollHeight,st.offsetHeight);Array.prototype.forEach.call(st.querySelectorAll("*"),function(n){var cs=getComputedStyle(n);if(cs.display==="none"||cs.visibility==="hidden")return;var r=n.getBoundingClientRect();if(!r.width&&!r.height)return;minX=Math.min(minX,r.left-sr.left);minY=Math.min(minY,r.top-sr.top);maxX=Math.max(maxX,r.right-sr.left);maxY=Math.max(maxY,r.bottom-sr.top);});var cw=maxX-minX,ch=maxY-minY,p=12,s=Math.max(.1,Math.min((innerWidth-p*2)/cw,(innerHeight-p*2)/ch,1)),tx=(innerWidth-cw*s)/2-minX*s,ty=(innerHeight-ch*s)/2-minY*s;st.style.transform="translate("+tx+"px,"+ty+"px) scale("+s+")";}addEventListener("resize",fit);fit();setTimeout(fit,300);setTimeout(fit,1000);}if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",u);else u();})();<\/script>';
                        var legacyBodyIdx = wrappedHtml.toLowerCase().lastIndexOf('</body>');
                        wrappedHtml = legacyBodyIdx !== -1
                            ? wrappedHtml.slice(0, legacyBodyIdx) + fitUpgrade + wrappedHtml.slice(legacyBodyIdx)
                            : wrappedHtml + fitUpgrade;
                    }
                    // Full HTML added through the Editor is a real page viewport,
                    // not a tall screenshot squeezed into the element. Fixed-stage
                    // simulations may explicitly opt into "fit".
                    if (wrappedHtml.indexOf('__stage') === -1 &&
                        wrappedHtml.indexOf('__scormify_page_mode') === -1 &&
                        (element.htmlDisplayMode || 'page') !== 'fit') {
                        var pageViewportStyle = '<style id="__scormify_page_mode">' +
                            'html{margin:0!important;padding:0!important;width:100%!important;height:100%!important;overflow-x:hidden!important;overflow-y:auto!important;scrollbar-gutter:stable;}' +
                            'body{margin:0!important;width:100%!important;min-width:0!important;min-height:100%!important;height:auto!important;overflow:visible!important;transform:none!important;}' +
                            'body>*{max-width:100%;box-sizing:border-box;}img,video,canvas,svg{max-width:100%;}' +
                            '</style>';
                        var pageHeadIdx = wrappedHtml.toLowerCase().lastIndexOf('</head>');
                        var pageBodyIdx = wrappedHtml.toLowerCase().lastIndexOf('</body>');
                        if (pageHeadIdx !== -1) {
                            wrappedHtml = wrappedHtml.slice(0, pageHeadIdx) + pageViewportStyle + wrappedHtml.slice(pageHeadIdx);
                        } else if (pageBodyIdx !== -1) {
                            wrappedHtml = wrappedHtml.slice(0, pageBodyIdx) + pageViewportStyle + wrappedHtml.slice(pageBodyIdx);
                        } else {
                            wrappedHtml += pageViewportStyle;
                        }
                    } else if (wrappedHtml.indexOf('__stage') === -1 &&
                               (element.htmlDisplayMode || 'page') === 'fit') {
                        var fixedStageSnippet = '<style id="__scormify_fit_v3">html,body{margin:0!important;padding:0!important;width:100%;height:100%;overflow:hidden!important;}body{display:block!important;position:relative!important;}</style>' +
                            '<script>(function(){function b(){var bd=document.body;if(!bd||document.getElementById("__stage"))return;var st=document.createElement("div");st.id="__stage";st.style.cssText="width:960px;position:absolute;left:0;top:0;margin:0;transform-origin:0 0;";while(bd.firstChild){st.appendChild(bd.firstChild);}bd.appendChild(st);function fit(){st.style.transform="none";var sr=st.getBoundingClientRect(),minX=0,minY=0,maxX=Math.max(960,st.scrollWidth,st.offsetWidth),maxY=Math.max(540,st.scrollHeight,st.offsetHeight);Array.prototype.forEach.call(st.querySelectorAll("*"),function(n){var cs=getComputedStyle(n);if(cs.display==="none"||cs.visibility==="hidden")return;var r=n.getBoundingClientRect();if(!r.width&&!r.height)return;minX=Math.min(minX,r.left-sr.left);minY=Math.min(minY,r.top-sr.top);maxX=Math.max(maxX,r.right-sr.left);maxY=Math.max(maxY,r.bottom-sr.top);});var cw=maxX-minX,ch=maxY-minY,p=12,s=Math.max(.1,Math.min((innerWidth-p*2)/cw,(innerHeight-p*2)/ch,1)),tx=(innerWidth-cw*s)/2-minX*s,ty=(innerHeight-ch*s)/2-minY*s;st.style.transform="translate("+tx+"px,"+ty+"px) scale("+s+")";}addEventListener("resize",fit);fit();setTimeout(fit,300);setTimeout(fit,1000);}if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",b);else b();})();<\/script>';
                        var fitBodyIdx = wrappedHtml.toLowerCase().lastIndexOf('</body>');
                        wrappedHtml = fitBodyIdx !== -1
                            ? wrappedHtml.slice(0, fitBodyIdx) + fixedStageSnippet + wrappedHtml.slice(fitBodyIdx)
                            : wrappedHtml + fixedStageSnippet;
                    }
                } else {
                wrappedHtml = '<html><head><style>' +
                    (isHtmlFullscreen ? 
                        // FULLSCREEN MODE - image fills entire container
                        'html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:transparent!important;}' +
                        'body>div,body>*{width:100%;height:100%;margin:0;padding:0;text-align:center;position:relative;}' +
                        'img,body img{width:100%!important;height:100%!important;max-width:none!important;max-height:none!important;min-width:100%!important;min-height:100%!important;object-fit:cover!important;display:block!important;margin:0!important;padding:0!important;border:none!important;border-radius:0!important;float:none!important;position:absolute!important;top:0!important;left:0!important;}'
                    :
                        // NORMAL MODE - preserve image sizes and positions, content must stay within bounds
                        'html{margin:0;padding:0;width:100%;height:100%;overflow:hidden!important;}' +
                        'body{margin:0;padding:8px;background:transparent!important;font-family:Arial,sans-serif;color:#f1f5f9;line-height:1.6;overflow:auto!important;word-wrap:break-word;overflow-wrap:break-word;width:100%!important;height:100%!important;box-sizing:border-box!important;}' +
                        '*{box-sizing:border-box!important;max-width:100%!important;}' +
                        'img{border:none!important;outline:none!important;box-shadow:none!important;max-width:100%!important;width:auto!important;height:auto!important;}' +
                        'img[style*="width"]{max-width:100%!important;width:auto!important;height:auto!important;}' +
                        'img.rtf-image-float-left,body img.rtf-image-float-left{float:left!important;clear:left!important;max-width:45%!important;width:auto!important;height:auto!important;border-radius:4px!important;margin:0 16px 12px 0!important;display:block!important;border:none!important;outline:none!important;}' +
                        'img.rtf-image-float-right,body img.rtf-image-float-right{float:right!important;clear:right!important;max-width:45%!important;width:auto!important;height:auto!important;border-radius:4px!important;margin:0 0 12px 16px!important;display:block!important;border:none!important;outline:none!important;}' +
                        'img.rtf-image-center{display:inline-block!important;max-width:80%!important;width:auto!important;height:auto!important;border:none!important;outline:none!important;}' +
                        'img.rtf-image-inline{display:block!important;max-width:100%!important;width:auto!important;height:auto!important;margin:8px 0!important;border:none!important;outline:none!important;}' +
                        'img.rtf-image-float-left,img[style*="float: left"],img[style*="float:left"]{float:left!important;max-width:45%!important;margin-right:16px!important;margin-bottom:12px!important;height:auto!important;object-fit:contain!important;}' +
                        'img.rtf-image-float-right,img[style*="float: right"],img[style*="float:right"]{float:right!important;max-width:45%!important;margin-left:16px!important;margin-bottom:12px!important;height:auto!important;object-fit:contain!important;}' +
                        'body::after{content:\'\';display:table;clear:both;}' +
                        'p,div,span,ul,ol,li,h1,h2,h3,h4,h5,h6{overflow:visible!important;word-wrap:break-word;overflow-wrap:break-word;max-width:100%!important;word-break:normal;hyphens:auto;-webkit-hyphens:auto;}' +
                        mobileCSS
                    ) +
                    /* Typography and scrollbar - apply to both modes */
                    'html,body{scrollbar-width:thin;scrollbar-color:rgba(100,116,139,0.3) transparent;}' +
                    '::-webkit-scrollbar{width:4px;height:4px;}' +
                    '::-webkit-scrollbar-track{background:transparent;}' +
                    '::-webkit-scrollbar-thumb{background:rgba(100,116,139,0.3);border-radius:4px;}' +
                    '::-webkit-scrollbar-thumb:hover{background:rgba(100,116,139,0.5);}' +
                    'h1{font-size:1.5rem;font-weight:bold;margin-bottom:1rem;}' +
                    'h2{font-size:1.25rem;font-weight:bold;margin-bottom:0.75rem;}' +
                    'h3{font-size:1.1rem;font-weight:bold;margin-bottom:0.5rem;}' +
                    'p{margin-bottom:0.75rem;}' +
                    'ul{list-style:disc;padding-left:1.5rem;margin-bottom:0.75rem;}' +
                    'ol{list-style:decimal;padding-left:1.5rem;margin-bottom:0.75rem;}' +
                    'li{margin-bottom:0.25rem;}' +
                    'table{border-collapse:separate;border-spacing:0;width:100%;margin:1rem 0;border-radius:8px;overflow:hidden;box-shadow:0 4px 6px -1px rgba(0,0,0,0.3);}' +
                    'th{background:linear-gradient(to bottom,#475569,#334155);border-bottom:2px solid #22d3ee;padding:0.75rem 1rem;font-weight:600;text-align:left;color:#f1f5f9;}' +
                    'td{border-bottom:1px solid #334155;padding:0.75rem 1rem;background:#1e293b;color:#e2e8f0;}' +
                    // Google Fonts for design-template visibility. Without
                    // this every theme picker preset falls back to sans-serif.
                    '@import url("https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Lato:wght@300;400;700&family=Merriweather:wght@300;400;700&family=Montserrat:wght@300;400;500;600;700&family=Nunito:wght@300;400;600;700&family=Oswald:wght@300;400;500;600;700&family=Playfair+Display:wght@400;500;600;700&family=Poppins:wght@300;400;500;600;700&family=Raleway:wght@300;400;500;600;700&family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap");' +
                    'tr:nth-child(even) td{background:#1a2433;}' +
                    // Text-shadow — from element.style.textShadow.
                    // Broad selector + !important so RichText / RTF also picks up.
                    (element.style && element.style.textShadow ?
                        'body,body *{text-shadow:' + element.style.textShadow + '!important;}' : '') +
                    '</style></head><body>' + htmlContent + '</body></html>';
                }
                htmlIframe.srcdoc = wrappedHtml;
                htmlIframe.style.cssText = 'width:100%!important;height:100%!important;border:none!important;background:transparent!important;overflow:' + (isHtmlFullscreen ? 'hidden' : 'auto') + '!important;display:block!important;';
                htmlIframe.sandbox = 'allow-scripts allow-same-origin';
                el.style.overflow = 'hidden';
                el.appendChild(htmlIframe);
                break;
            
            case 'flipbook':
                el = document.createElement('div');
                el.className = 'slide-element flipbook-element';
                
                if (element.flipbookType === 'external' && element.flipbookUrl) {
                    var flipIframe = document.createElement('iframe');
                    flipIframe.src = element.flipbookUrl;
                    flipIframe.style.width = '100%';
                    flipIframe.style.height = '100%';
                    flipIframe.style.border = 'none';
                    flipIframe.allow = 'fullscreen';
                    el.appendChild(flipIframe);
                } else if (element.flipbookType === 'pdf' && element.pdfDisplay === 'pages' && element.pdfPages && element.pdfPages.length > 0) {
                    // Pages-only mode: render pre-converted page images, no PDF chrome
                    var pdfPagesWrap = document.createElement('div');
                    pdfPagesWrap.style.cssText = 'width:100%;height:100%;overflow:auto;background:transparent;';
                    element.pdfPages.forEach(function(pu) {
                        var pimg = document.createElement('img');
                        pimg.src = pu;
                        pimg.style.cssText = 'width:100%;height:auto;display:block;margin-bottom:8px;';
                        pdfPagesWrap.appendChild(pimg);
                    });
                    el.appendChild(pdfPagesWrap);
                } else if (element.flipbookType === 'pdf' && element.flipbookUrl) {
                    var pdfIframe = document.createElement('iframe');
                    var pdfViewerSrc = element.flipbookUrl;
                    if (element.pdfDisplay === 'clean') { pdfViewerSrc += '#toolbar=0&navpanes=0&scrollbar=0'; }
                    pdfIframe.src = pdfViewerSrc;
                    pdfIframe.style.width = '100%';
                    pdfIframe.style.height = '100%';
                    pdfIframe.style.border = 'none';
                    el.appendChild(pdfIframe);
                } else if (element.flipbookType === 'images' && element.flipbookPages && element.flipbookPages.length > 0) {
                    // Simple image flipbook viewer
                    var flipContainer = document.createElement('div');
                    flipContainer.className = 'flipbook-images-container';
                    flipContainer.style.cssText = 'width:100%;height:100%;display:flex;flex-direction:column;background:#222;';
                    
                    var flipImg = document.createElement('img');
                    flipImg.src = element.flipbookPages[0];
                    flipImg.style.cssText = 'flex:1;object-fit:contain;max-height:calc(100% - 40px);';
                    flipImg.dataset.pages = JSON.stringify(element.flipbookPages);
                    flipImg.dataset.currentPage = '0';
                    
                    var flipNav = document.createElement('div');
                    flipNav.style.cssText = 'height:40px;display:flex;align-items:center;justify-content:center;gap:10px;background:#333;';
                    
                    var prevBtn = document.createElement('button');
                    prevBtn.innerHTML = '◀ Anterior';
                    prevBtn.style.cssText = 'padding:5px 10px;border:none;background:#555;color:#fff;border-radius:4px;cursor:pointer;';
                    prevBtn.onclick = function() {
                        var pages = JSON.parse(flipImg.dataset.pages);
                        var current = parseInt(flipImg.dataset.currentPage);
                        if (current > 0) {
                            flipImg.dataset.currentPage = current - 1;
                            flipImg.src = pages[current - 1];
                            pageInfo.textContent = (current) + ' / ' + pages.length;
                        }
                    };
                    
                    var pageInfo = document.createElement('span');
                    pageInfo.style.cssText = 'color:#fff;font-size:14px;';
                    pageInfo.textContent = '1 / ' + element.flipbookPages.length;
                    
                    var nextBtn = document.createElement('button');
                    nextBtn.innerHTML = 'Próximo ▶';
                    nextBtn.style.cssText = 'padding:5px 10px;border:none;background:#555;color:#fff;border-radius:4px;cursor:pointer;';
                    nextBtn.onclick = function() {
                        var pages = JSON.parse(flipImg.dataset.pages);
                        var current = parseInt(flipImg.dataset.currentPage);
                        if (current < pages.length - 1) {
                            flipImg.dataset.currentPage = current + 1;
                            flipImg.src = pages[current + 1];
                            pageInfo.textContent = (current + 2) + ' / ' + pages.length;
                        }
                    };
                    
                    flipNav.appendChild(prevBtn);
                    flipNav.appendChild(pageInfo);
                    flipNav.appendChild(nextBtn);
                    flipContainer.appendChild(flipImg);
                    flipContainer.appendChild(flipNav);
                    el.appendChild(flipContainer);
                } else {
                    el.innerHTML = '<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:#f0f0f0;color:#666;">Flipbook</div>';
                }
                break;
            
            case 'quiz':
                el = document.createElement('div');
                el.className = 'slide-element quiz-element';
                var _quizCfg = element.quizConfig || {};
                var _quizTransparent = _quizCfg.transparentBackground === true;
                if (_quizTransparent) {
                    el.style.background = 'transparent';
                    el.style.borderRadius = '0';
                    el.style.border = 'none';
                } else {
                    el.style.background = 'linear-gradient(135deg, #1e293b, #0f172a)';
                    el.style.borderRadius = '12px';
                    el.style.border = '2px solid rgba(34, 211, 238, 0.3)';
                }
                el.style.overflow = 'hidden';
                
                // Get quiz config
                var quizConfig = _quizCfg;
                var questionIds = quizConfig.questionIds || [];
                var quizTitle = quizConfig.title || 'Quiz';
                var passingScore = quizConfig.passingScore || 60;
                var shuffleQuestions = quizConfig.shuffleQuestions !== false;
                var shuffleAlts = quizConfig.shuffleAlternatives !== false;
                var showFeedback = quizConfig.showFeedback !== false;
                
                // Quiz player will be initialized with questions from course.json
                var quizContainer = document.createElement('div');
                quizContainer.className = 'quiz-player-container';
                quizContainer.dataset.elementId = element.id;
                quizContainer.dataset.quizConfig = JSON.stringify(quizConfig);
                quizContainer.style.cssText = 'width:100%;height:100%;display:flex;flex-direction:column;';
                
                // Placeholder until quiz is initialized
                var _quizPlaceholderTitleColor = _quizTransparent ? '#e0f2fe' : '#fff';
                var _quizPlaceholderMetaColor = _quizTransparent ? '#cbd5e1' : '#94a3b8';
                var _quizPlaceholderTextShadow = _quizTransparent ? 'text-shadow:0 1px 2px rgba(0,0,0,0.6);' : '';
                quizContainer.innerHTML = '<div style="width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px;">' +
                    '<div style="font-size:48px;margin-bottom:16px;">📝</div>' +
                    '<h3 style="font-size:20px;font-weight:bold;color:' + _quizPlaceholderTitleColor + ';margin-bottom:8px;' + _quizPlaceholderTextShadow + '">' + quizTitle + '</h3>' +
                    '<p style="color:' + _quizPlaceholderMetaColor + ';font-size:14px;margin-bottom:16px;' + _quizPlaceholderTextShadow + '">' + questionIds.length + ' questões</p>' +
                    '<button class="quiz-start-btn" style="padding:12px 32px;background:linear-gradient(135deg,#06b6d4,#8b5cf6);color:#fff;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;" ' +
                    'onclick="QuizController.startQuiz(\'' + element.id + '\')">Iniciar Quiz</button>' +
                    '</div>';
                
                el.appendChild(quizContainer);
                break;

            case 'scenario':
                el = document.createElement('div');
                el.className = 'slide-element scenario-element';
                el.style.background = 'linear-gradient(135deg, #0f172a, #164e63)';
                el.style.borderRadius = '12px';
                el.style.border = '2px solid rgba(34, 211, 238, 0.3)';
                el.style.overflow = 'hidden';

                var scenarioData = element.scenarioData || {};
                var scenarioContainer = document.createElement('div');
                scenarioContainer.className = 'scenario-player-container';
                scenarioContainer.dataset.elementId = element.id;
                scenarioContainer.dataset.scenario = JSON.stringify(scenarioData);
                scenarioContainer.style.cssText = 'width:100%;height:100%;display:flex;flex-direction:column;';

                scenarioContainer.innerHTML = '<div style="width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px;">' +
                    '<svg style="width:48px;height:48px;color:#22d3ee;margin-bottom:16px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6 3v12"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>' +
                    '<h3 style="font-size:20px;font-weight:bold;color:#fff;margin-bottom:8px;">' + (scenarioData.title || 'Cenário Interativo') + '</h3>' +
                    '<p style="color:#94a3b8;font-size:14px;margin-bottom:16px;">' + (scenarioData.nodes ? scenarioData.nodes.length : 0) + ' cenas</p>' +
                    '<button class="scenario-start-btn" style="padding:12px 32px;background:linear-gradient(135deg,#06b6d4,#0891b2);color:#fff;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;" ' +
                    'onclick="ScenarioController.startScenario(\'' + element.id + '\')">Iniciar Cenário</button>' +
                    '</div>';

                el.appendChild(scenarioContainer);
                break;
                
            default:
                el = document.createElement('div');
                el.className = 'slide-element';
        }
        
        if (!el) return null;
        
        // Apply positioning and styles with explicit pixel values
        el.style.position = 'absolute';
        var useGameViewport = el.getAttribute('data-scormify-game') === 'true';
        var viewportSlide = activeSlide;
        var viewportWidth = viewportSlide.width || 960;
        var viewportHeight = viewportSlide.height || 540;
        var gameMarginX = Math.max(4, Math.round(viewportWidth * 0.01));
        var gameMarginY = Math.max(4, Math.round(viewportHeight * 0.01));
        el.style.left = (useGameViewport ? gameMarginX : (element.x || 0)) + 'px';
        el.style.top = (useGameViewport ? gameMarginY : (element.y || 0)) + 'px';
        el.style.width = (useGameViewport ? viewportWidth - gameMarginX * 2 : (element.width || 100)) + 'px';
        el.style.height = (useGameViewport ? viewportHeight - gameMarginY * 2 : (element.height || 100)) + 'px';
        el.style.zIndex = (element.zIndex || 0) + 1;
        el.style.overflow = 'hidden';  // Ensure content stays within bounds
        
        if (element.rotation) {
            el.style.transform = 'rotate(' + element.rotation + 'deg)';
        }
        
        // Apply styles
        if (element.style) {
            applyElementStyles(el, element.style);
        }
        
        // Apply hyperlink
        if (element.hyperlink) {
            el.style.cursor = 'pointer';
            el.onclick = function() {
                window.open(element.hyperlink, '_blank');
            };
        }
        
        return el;
    }
    
    function applyElementStyles(el, style) {
        if (style.fill) el.style.backgroundColor = style.fill;
        if (style.stroke) el.style.borderColor = style.stroke;
        if (style.strokeWidth) el.style.borderWidth = style.strokeWidth + 'px';
        // Apply opacity from element style (0 to 1 range)
        if (style.opacity !== undefined && style.opacity !== null) {
            el.style.opacity = style.opacity;
        }
        if (style.fontSize) el.style.fontSize = style.fontSize + 'px';
        if (style.fontFamily) el.style.fontFamily = style.fontFamily;
        if (style.fontWeight) el.style.fontWeight = style.fontWeight;
        if (style.fontColor) el.style.color = style.fontColor;
        if (style.textAlign) el.style.textAlign = style.textAlign;
        if (style.borderRadius) el.style.borderRadius = (typeof style.borderRadius === 'number' ? style.borderRadius + 'px' : style.borderRadius);
        // Aesthetic Analyzer additions: plate, padding, text shadow.
        if (style.textBackgroundColor) el.style.backgroundColor = style.textBackgroundColor;
        else if (style.backgroundColor) el.style.backgroundColor = style.backgroundColor;
        if (style.padding) el.style.padding = (typeof style.padding === 'number' ? style.padding + 'px' : style.padding);
        if (style.textShadow) el.style.textShadow = style.textShadow;
    }
    
    function applyShapeStyles(el, element) {
        var shapeType = element.shapeType || 'rectangle';
        
        switch (shapeType) {
            case 'oval':
            case 'ellipse':
                el.style.borderRadius = '50%';
                break;
            case 'rounded_rectangle':
                el.style.borderRadius = '10px';
                break;
        }
        
        // Apply background color (transparent by default)
        if (element.style && element.style.fill) {
            el.style.backgroundColor = element.style.fill;
        } else if (element.style && element.style.backgroundColor) {
            el.style.backgroundColor = element.style.backgroundColor;
        } else {
            el.style.backgroundColor = 'transparent';
        }
        
        if (element.style && element.style.stroke) {
            el.style.border = '2px solid ' + element.style.stroke;
        }
    }
    
    function scheduleAnimations(el, animations, elementOpacity) {
        var targetOpacity = (elementOpacity !== undefined && elementOpacity !== null) ? String(elementOpacity) : '1';
        animations.forEach(function(anim, index) {
            var delay = (anim.startTime || anim.delay || index * 0.3) * 1000;
            var duration = (anim.duration || 0.5) * 1000;
            var effect = anim.effect || '';
            var easing = anim.easing || 'cubic-bezier(0.25, 0.46, 0.45, 0.94)';
            
            // Initial state for entrance animations
            if (anim.type === 'entrance') {
                el.style.opacity = '0';
                switch (effect) {
                    case 'slideInLeft': el.style.transform = 'translateX(-60px)'; break;
                    case 'slideInRight': el.style.transform = 'translateX(60px)'; break;
                    case 'slideInUp': el.style.transform = 'translateY(40px)'; break;
                    case 'slideInDown': el.style.transform = 'translateY(-40px)'; break;
                    case 'zoomIn': el.style.transform = 'scale(0.5)'; break;
                    case 'bounce': el.style.transform = 'translateY(-30px)'; break;
                    case 'typewriter': el.style.opacity = targetOpacity; el.style.clipPath = 'inset(0 100% 0 0)'; break;
                }
            }
            
            setTimeout(function() {
                if (effect === 'typewriter') {
                    el.style.transition = 'clip-path ' + duration + 'ms steps(20, end)';
                    el.style.clipPath = 'inset(0 0% 0 0)';
                } else if (effect === 'bounce') {
                    el.style.transition = 'opacity ' + duration + 'ms ease, transform ' + duration + 'ms cubic-bezier(0.34, 1.56, 0.64, 1)';
                    el.style.opacity = targetOpacity;
                    el.style.transform = 'translateY(0) translateX(0) scale(1)';
                } else {
                    el.style.transition = 'opacity ' + duration + 'ms ' + easing + ', transform ' + duration + 'ms ' + easing;
                    el.style.opacity = anim.type === 'exit' ? '0' : targetOpacity;
                    el.style.transform = 'translateY(0) translateX(0) scale(1)';
                }
            }, delay);
        });
    }
    
    function renderAnnotation(container, annotation) {
        var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.style.position = 'absolute';
        svg.style.top = '0';
        svg.style.left = '0';
        svg.style.width = '100%';
        svg.style.height = '100%';
        svg.style.pointerEvents = 'none';
        svg.style.zIndex = '1000';
        
        var color = annotation.color || '#EF4444';
        var strokeWidth = annotation.strokeWidth || 3;
        var points = annotation.points || [];
        var shapeType = annotation.shapeType || annotation.type;
        
        if (shapeType === 'freehand' && points.length > 0) {
            var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('stroke', color);
            path.setAttribute('stroke-width', strokeWidth);
            path.setAttribute('fill', 'none');
            path.setAttribute('stroke-linecap', 'round');
            path.setAttribute('stroke-linejoin', 'round');
            var d = 'M ' + points[0].x + ' ' + points[0].y;
            for (var i = 1; i < points.length; i++) {
                d += ' L ' + points[i].x + ' ' + points[i].y;
            }
            path.setAttribute('d', d);
            svg.appendChild(path);
        }
        else if (shapeType === 'arrow' && points.length >= 2) {
            // Create arrowhead marker
            var defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            var marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
            marker.setAttribute('id', 'arrowhead-' + annotation.id);
            marker.setAttribute('markerWidth', '10');
            marker.setAttribute('markerHeight', '7');
            marker.setAttribute('refX', '9');
            marker.setAttribute('refY', '3.5');
            marker.setAttribute('orient', 'auto');
            var polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
            polygon.setAttribute('points', '0 0, 10 3.5, 0 7');
            polygon.setAttribute('fill', color);
            marker.appendChild(polygon);
            defs.appendChild(marker);
            svg.appendChild(defs);
            
            var line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', points[0].x);
            line.setAttribute('y1', points[0].y);
            line.setAttribute('x2', points[1].x);
            line.setAttribute('y2', points[1].y);
            line.setAttribute('stroke', color);
            line.setAttribute('stroke-width', strokeWidth);
            line.setAttribute('marker-end', 'url(#arrowhead-' + annotation.id + ')');
            svg.appendChild(line);
        }
        else if ((shapeType === 'circle' || shapeType === 'ellipse') && points.length >= 2) {
            var cx = (points[0].x + points[1].x) / 2;
            var cy = (points[0].y + points[1].y) / 2;
            var rx = Math.abs(points[1].x - points[0].x) / 2;
            var ry = Math.abs(points[1].y - points[0].y) / 2;
            var ellipse = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
            ellipse.setAttribute('cx', cx);
            ellipse.setAttribute('cy', cy);
            ellipse.setAttribute('rx', rx);
            ellipse.setAttribute('ry', ry);
            ellipse.setAttribute('stroke', color);
            ellipse.setAttribute('stroke-width', strokeWidth);
            ellipse.setAttribute('fill', 'none');
            svg.appendChild(ellipse);
        }
        else if ((shapeType === 'rectangle' || shapeType === 'rect') && points.length >= 2) {
            var x = Math.min(points[0].x, points[1].x);
            var y = Math.min(points[0].y, points[1].y);
            var width = Math.abs(points[1].x - points[0].x);
            var height = Math.abs(points[1].y - points[0].y);
            var rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.setAttribute('x', x);
            rect.setAttribute('y', y);
            rect.setAttribute('width', width);
            rect.setAttribute('height', height);
            rect.setAttribute('stroke', color);
            rect.setAttribute('stroke-width', strokeWidth);
            rect.setAttribute('fill', 'none');
            svg.appendChild(rect);
        }
        
        container.appendChild(svg);
        return svg; // Return the created element for timeline control
    }
    
    function playSlideAudio(audioList, currentSlideDuration, onDurationKnown) {
        // Clear any previously tracked audios and timers
        stopAllSlideAudios();
        
        // Always initialize the timer tracking array
        window.audioTimelineTimers = [];
        
        if (!audioList || audioList.length === 0) return;
        
        console.log('[Audio] Playing', audioList.length, 'audio(s)');
        
        // Sort by startTime to ensure correct order
        var sortedList = audioList.slice().sort(function(a, b) {
            return (a.startTime || 0) - (b.startTime || 0);
        });
        
        // Helper to track max real audio end time and report back
        var reportedDuration = false;
        function reportAudioDuration(audioEl, startTime) {
            if (reportedDuration) return;
            audioEl.addEventListener('loadedmetadata', function() {
                var realEnd = (startTime || 0) + audioEl.duration;
                if (realEnd > (currentSlideDuration || 10) && onDurationKnown) {
                    reportedDuration = true;
                    onDurationKnown(realEnd);
                }
            });
        }
        
        // Determine playback mode
        var hasExplicitTimeline = sortedList.some(function(a) {
            return typeof a.startTime === 'number' && a.startTime > 0;
        });
        
        if (hasExplicitTimeline) {
            console.log('[Audio] Timeline mode - scheduling at startTime positions');
            sortedList.forEach(function(audio, idx) {
                var startMs = Math.round((audio.startTime || 0) * 1000);
                var timer = setTimeout(function() {
                    // Check if timers were cleared (slide changed)
                    if (!window.audioTimelineTimers || window.audioTimelineTimers.length === 0) return;
                    var audioEl = new Audio(audio.src);
                    audioEl.volume = audio.volume || 1;
                    activeSlideAudios.push(audioEl);
                    reportAudioDuration(audioEl, audio.startTime || 0);
                    console.log('[Audio] Playing audio', idx + 1, 'at', audio.startTime, 's');
                    audioEl.play().catch(function(e) {
                        console.log('[Audio] Play blocked for audio', idx + 1, ':', e.message);
                    });
                }, startMs);
                window.audioTimelineTimers.push(timer);
            });
        } else if (sortedList.length > 1) {
            console.log('[Audio] Sequential mode - chaining', sortedList.length, 'audios');
            var seqIndex = 0;
            function playNextInSequence() {
                if (seqIndex >= sortedList.length) return;
                if (window.audioTimelineTimers && window.audioTimelineTimers.length === 0) return; // Slide changed
                var audio = sortedList[seqIndex];
                var audioEl = new Audio(audio.src);
                audioEl.volume = audio.volume || 1;
                activeSlideAudios.push(audioEl);
                audioEl.addEventListener('ended', function() {
                    seqIndex++;
                    playNextInSequence();
                });
                console.log('[Audio] Sequential: playing audio', seqIndex + 1);
                audioEl.play().catch(function(e) {
                    console.log('[Audio] Sequential play blocked:', e.message);
                    seqIndex++;
                    playNextInSequence();
                });
            }
            window.audioTimelineTimers = [1]; // Sentinel to track active state
            playNextInSequence();
        } else {
            // Single audio - play immediately
            var audio = sortedList[0];
            var audioEl = new Audio(audio.src);
            audioEl.volume = audio.volume || 1;
            activeSlideAudios.push(audioEl);
            reportAudioDuration(audioEl, 0);
            audioEl.play().catch(function(e) {
                console.log('[Audio] Single play blocked:', e.message);
            });
        }
    }
    
    function nextSlide() {
        if (currentSlide < totalSlides - 1) {
            currentSlide++;
            renderSlide(currentSlide);
            updateProgress();
            if (typeof AiTutor !== 'undefined') AiTutor.onSlideChange(currentSlide);
        } else if (currentSlide === totalSlides - 1 && !courseCompleted) {
            completionRequested = true;
            checkAndSetCompletion();
        }
    }
    
    function prevSlide() {
        if (currentSlide > 0) {
            currentSlide--;
            renderSlide(currentSlide);
            updateProgress();
            if (typeof AiTutor !== 'undefined') AiTutor.onSlideChange(currentSlide);
        }
    }
    
    function goToSlide(index) {
        if (index >= 0 && index < totalSlides) {
            // Pause all videos on current slide before changing
            pauseAllVideos(true);
            
            // Clear saved video states when changing slides
            videoStates = {};
            
            currentSlide = index;
            renderSlide(currentSlide);
            updateProgress();
            if (typeof AiTutor !== 'undefined') AiTutor.onSlideChange(currentSlide);
        }
    }
    
    function pauseAllVideos(resetPosition) {
        var videos = document.querySelectorAll('#slide-content video');
        videos.forEach(function(video) {
            video.pause();
            // Only reset position if explicitly requested (slide change)
            if (resetPosition) {
                video.currentTime = 0;
            }
        });
    }
    
    function autoplayVideosOnSlide() {
        var videos = document.querySelectorAll('#slide-content video');
        videos.forEach(function(video) {
            var elementId = video.dataset.elementId;
            // Only autoplay if no saved state exists for this video
            if (!videoStates[elementId]) {
                video.currentTime = 0;
                video.play().catch(function() {
                    video.muted = true;
                    video.play().catch(function() {
                        console.log('Autoplay blocked');
                    });
                });
            }
        });
    }
    
    function updateProgress() {
        var dotsContainer = document.getElementById('progress-dots');
        
        if (dotsContainer) {
            var html = '';
            for (var i = 0; i < totalSlides; i++) {
                var cls = 'progress-dot';
                if (i === currentSlide) cls += ' active';
                else if (i < currentSlide) cls += ' completed';
                html += '<div class="' + cls + '" onclick="CoursePlayer.goTo(' + i + ')"></div>';
            }
            dotsContainer.innerHTML = html;
        }
        
        // Update mobile slide counter
        var mobileCounter = document.getElementById('mobile-slide-counter');
        if (mobileCounter) {
            mobileCounter.textContent = (currentSlide + 1) + ' / ' + totalSlides;
        }
        
        // Update mobile nav button visibility
        var mobilePrev = document.getElementById('mobile-nav-prev');
        var mobileNext = document.getElementById('mobile-nav-next');
        if (mobilePrev) {
            mobilePrev.style.opacity = currentSlide === 0 ? '0.3' : '1';
            mobilePrev.style.pointerEvents = currentSlide === 0 ? 'none' : 'auto';
        }
        if (mobileNext) {
            mobileNext.style.opacity = '1';
            mobileNext.style.pointerEvents = courseCompleted ? 'none' : 'auto';
            mobileNext.title = currentSlide === totalSlides - 1 ? 'Concluir curso' : 'Próximo';
            mobileNext.innerHTML = currentSlide === totalSlides - 1 ? '✓' : '›';
        }
        
        // Update sidebar
        updateSidebar();
    }
    
    function updateNavigation() {
        var prevBtn = document.getElementById('prev-btn');
        var nextBtn = document.getElementById('next-btn');
        
        if (prevBtn) {
            prevBtn.disabled = currentSlide === 0;
        }
        if (nextBtn) {
            nextBtn.disabled = courseCompleted;
            nextBtn.innerHTML = currentSlide === totalSlides - 1
                ? (courseCompleted ? '✓ Curso concluído' : 'Concluir curso ✓')
                : 'Próximo →';
        }
    }
    
    function toggleFullscreen() {
        var container = document.getElementById('player-container');
        if (!document.fullscreenElement) {
            container.requestFullscreen().catch(function(e) {
                console.log('Fullscreen error:', e);
            });
        } else {
            document.exitFullscreen();
        }
    }
    
    function playGlobalAudio() {
        if (globalAudio) {
            globalAudio.play().catch(function(e) {
                console.log('Audio play blocked');
            });
        }
    }
    
    function toggleMute() {
        var volumeBtn = document.getElementById('volume-btn');
        var volumeSlider = document.getElementById('volume-slider');
        
        if (globalAudio) {
            if (globalAudio.muted) {
                globalAudio.muted = false;
                if (volumeBtn) volumeBtn.innerHTML = '🔊';
                if (volumeSlider) volumeSlider.value = globalAudio.volume * 100;
            } else {
                globalAudio.muted = true;
                if (volumeBtn) volumeBtn.innerHTML = '🔇';
            }
        }
        
        // Also mute/unmute active slide audios
        activeSlideAudios.forEach(function(audio) {
            audio.muted = globalAudio ? globalAudio.muted : !audio.muted;
        });
    }
    
    function setVolume(value) {
        var volume = value / 100;
        var volumeBtn = document.getElementById('volume-btn');
        
        if (globalAudio) {
            globalAudio.volume = volume;
            globalAudio.muted = false;
        }
        
        // Update volume for active slide audios
        activeSlideAudios.forEach(function(audio) {
            audio.volume = volume;
            audio.muted = false;
        });
        
        // Update button icon based on volume level
        if (volumeBtn) {
            if (volume === 0) {
                volumeBtn.innerHTML = '🔇';
            } else if (volume < 0.5) {
                volumeBtn.innerHTML = '🔉';
            } else {
                volumeBtn.innerHTML = '🔊';
            }
        }
    }
    
    function toggleVolumeSlider() {
        var slider = document.getElementById('volume-control');
        if (slider) {
            slider.style.display = slider.style.display === 'none' ? 'flex' : 'none';
        }
    }
    
    function toggleSidebar() {
        var sidebar = document.getElementById('slide-sidebar');
        var wrapper = document.getElementById('slide-wrapper');
        if (sidebar) {
            var isOpen = sidebar.classList.contains('open');
            if (isOpen) {
                sidebar.classList.remove('open');
                wrapper.classList.remove('sidebar-open');
            } else {
                sidebar.classList.add('open');
                wrapper.classList.add('sidebar-open');
            }
        }
    }
    
    function renderSidebar() {
        var sidebarList = document.getElementById('sidebar-slides');
        if (!sidebarList || !course) return;
        
        sidebarList.innerHTML = '';
        
        course.slides.forEach(function(slide, index) {
            var item = document.createElement('div');
            var hasPptThumb = !!slide.backgroundImage;
            item.className = 'sidebar-slide-item' + (index === currentSlide ? ' active' : '') + (hasPptThumb ? '' : ' no-thumb');
            item.onclick = function() {
                goToSlide(index);
            };
            
            // Create slide info
            var info = document.createElement('div');
            info.className = 'sidebar-slide-info';
            
            if (hasPptThumb) {
                // PPT import: show thumbnail + "Slide N" + status
                var thumbnail = document.createElement('div');
                thumbnail.className = 'sidebar-thumbnail';
                thumbnail.style.backgroundImage = 'url(' + slide.backgroundImage + ')';
                item.appendChild(thumbnail);
                
                var title = document.createElement('div');
                title.className = 'sidebar-slide-title';
                title.textContent = 'Slide ' + (index + 1);
                info.appendChild(title);
            } else {
                // Agent/manual: show slide number + title (like HTML export)
                var label = document.createElement('div');
                label.className = 'sidebar-slide-label';
                label.textContent = 'Slide ' + (index + 1);
                info.appendChild(label);
                
                var title = document.createElement('div');
                title.className = 'sidebar-slide-title';
                title.textContent = slide.title || 'Slide ' + (index + 1);
                info.appendChild(title);
            }
            
            var status = document.createElement('div');
            status.className = 'sidebar-slide-status';
            if (courseCompleted && index === totalSlides - 1) {
                status.innerHTML = '✓ Concluído';
                status.classList.add('completed');
            } else if (index < currentSlide) {
                status.innerHTML = '✓ Concluído';
                status.classList.add('completed');
            } else if (index === currentSlide) {
                status.innerHTML = '● Atual';
                status.classList.add('current');
            } else {
                status.innerHTML = '○ Pendente';
            }
            
            info.appendChild(status);
            item.appendChild(info);
            sidebarList.appendChild(item);
        });
    }
    
    function updateSidebar() {
        var items = document.querySelectorAll('.sidebar-slide-item');
        items.forEach(function(item, index) {
            item.classList.remove('active');
            if (index === currentSlide) {
                item.classList.add('active');
            }
            
            var status = item.querySelector('.sidebar-slide-status');
            if (status) {
                status.classList.remove('completed', 'current');
                if (courseCompleted && index === totalSlides - 1) {
                    status.innerHTML = '✓ Concluído';
                    status.classList.add('completed');
                } else if (index < currentSlide) {
                    status.innerHTML = '✓ Concluído';
                    status.classList.add('completed');
                } else if (index === currentSlide) {
                    status.innerHTML = '● Atual';
                    status.classList.add('current');
                } else {
                    status.innerHTML = '○ Pendente';
                }
            }
        });
        
        // Scroll active item into view
        var activeItem = document.querySelector('.sidebar-slide-item.active');
        if (activeItem) {
            activeItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }
    
    // Keyboard navigation - skip when user is typing in an input/textarea (e.g. AI Tutor)
    document.addEventListener('keydown', function(e) {
        var tag = (e.target.tagName || '').toLowerCase();
        if (tag === 'input' || tag === 'textarea' || e.target.isContentEditable) {
            return; // Let the user type freely
        }
        switch (e.key) {
            case 'ArrowRight':
            case 'Space':
            case 'Enter':
                e.preventDefault();
                nextSlide();
                break;
            case 'ArrowLeft':
            case 'Backspace':
                e.preventDefault();
                prevSlide();
                break;
            case 'Home':
                e.preventDefault();
                goToSlide(0);
                break;
            case 'End':
                e.preventDefault();
                goToSlide(totalSlides - 1);
                break;
            case 'f':
            case 'F':
                e.preventDefault();
                toggleFullscreen();
                break;
        }
    });
    
    return {
        load: loadCourse,
        next: nextSlide,
        prev: prevSlide,
        goTo: goToSlide,
        fullscreen: toggleFullscreen,
        playAudio: playGlobalAudio,
        startCourse: hideStartOverlay,
        toggleMute: toggleMute,
        setVolume: setVolume,
        toggleVolumeSlider: toggleVolumeSlider,
        toggleSidebar: toggleSidebar,
        updateScale: updateSlideScale,
        onQuizComplete: onQuizComplete,
        onScenarioComplete: onScenarioComplete,
        // Final check before page unload - ensures completion is set if all activities are done
        finalCompletionCheck: function() {
            var quizzesComplete = Object.keys(completedQuizzes).length >= totalQuizzes;
            
            console.log('[Player] Final completion check before unload:', {
                visitedLastSlide: visitedLastSlide,
                completionRequested: completionRequested,
                quizzesComplete: quizzesComplete,
                completedQuizzes: Object.keys(completedQuizzes).length,
                totalQuizzes: totalQuizzes
            });
            
            // Mark complete if user visited last slide and all quizzes are done
            if (visitedLastSlide && completionRequested && (!courseHasQuiz || quizzesComplete)) {
                if (ScormAPI.setComplete()) {
                    courseCompleted = true;
                    updateSidebar();
                    updateNavigation();
                    console.log('[Player] Final check: Marked complete');
                }
            }
        },
        refresh: function() {
            // Re-render current slide completely (used after orientation change)
            if (course && course.slides) {
                renderSlide(currentSlide);
            }
        }
    };
})();

// Load course on page ready
document.addEventListener('DOMContentLoaded', function() {
    fetch('course.json')
        .then(function(response) { return response.json(); })
        .then(function(data) { 
            CoursePlayer.load(data);
            // Initialize quiz controller with questions
            if (typeof QuizController !== 'undefined' && data.questions) {
                QuizController.init(data);
            }
            // Initialize AI Tutor if configured
            if (typeof AiTutor !== 'undefined' && data.tutorConfig && data.tutorConfig.enabled) {
                AiTutor.init(data.tutorConfig);
            }
        })
        .catch(function(error) { console.error('Failed to load course:', error); });
});
