"""
SCORM 1.2 Exporter Service
Generates SCORM 1.2 compliant packages
"""
import os
import json
import zipfile
import logging
import re
import httpx
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import shutil

from models import Course, Project

logger = logging.getLogger(__name__)

IMS_MANIFEST_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="{identifier}" version="1.0"
    xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
    xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd
                        http://www.imsglobal.org/xsd/imsmd_rootv1p2p1 imsmd_rootv1p2p1.xsd
                        http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
    <metadata>
        <schema>ADL SCORM</schema>
        <schemaversion>1.2</schemaversion>
    </metadata>
    <organizations default="org1">
        <organization identifier="org1">
            <title>{title}</title>
            <item identifier="item1" identifierref="resource1">
                <title>{title}</title>
                <adlcp:masteryscore>80</adlcp:masteryscore>
            </item>
        </organization>
    </organizations>
    <resources>
        <resource identifier="resource1" type="webcontent" adlcp:scormtype="sco" href="index.html">
            <file href="index.html"/>
            <file href="course.json"/>
            <file href="scripts/scorm-api.js"/>
            <file href="scripts/player.js"/>
            {resource_files}
        </resource>
    </resources>
</manifest>'''

SCORM_API_JS = '''/**
 * SCORM 1.2 API Wrapper
 */
var ScormAPI = (function() {
    var API = null;
    var initialized = false;
    var finished = false;
    var startTime = null;
    
    function findAPI(win) {
        var findAPITries = 0;
        while ((win.API == null) && (win.parent != null) && (win.parent != win)) {
            findAPITries++;
            if (findAPITries > 500) return null;
            win = win.parent;
        }
        return win.API;
    }
    
    function getAPI() {
        if (API == null) {
            API = findAPI(window);
            if (API == null && window.opener) {
                API = findAPI(window.opener);
            }
        }
        return API;
    }
    
    function formatTime(totalSeconds) {
        var hours = Math.floor(totalSeconds / 3600);
        var minutes = Math.floor((totalSeconds % 3600) / 60);
        var seconds = Math.floor(totalSeconds % 60);
        
        return String(hours).padStart(4, '0') + ':' + 
               String(minutes).padStart(2, '0') + ':' + 
               String(seconds).padStart(2, '0');
    }
    
    return {
        initialize: function() {
            if (initialized) return true;
            
            var api = getAPI();
            if (api) {
                var result = api.LMSInitialize("");
                if (result === "true" || result === true) {
                    initialized = true;
                    startTime = new Date();
                    
                    // Set initial status if not already set
                    var status = api.LMSGetValue("cmi.core.lesson_status");
                    if (status === "" || status === "not attempted") {
                        api.LMSSetValue("cmi.core.lesson_status", "incomplete");
                    }
                    
                    // Restore bookmark
                    var location = api.LMSGetValue("cmi.core.lesson_location");
                    if (location && location !== "") {
                        window.scormBookmark = parseInt(location) || 0;
                    }
                    
                    return true;
                }
            }
            console.log("SCORM API not found - running in standalone mode");
            return false;
        },
        
        finish: function() {
            if (!initialized || finished) return true;
            
            var api = getAPI();
            if (api) {
                // Set session time
                if (startTime) {
                    var endTime = new Date();
                    var totalSeconds = Math.floor((endTime - startTime) / 1000);
                    api.LMSSetValue("cmi.core.session_time", formatTime(totalSeconds));
                }
                
                api.LMSCommit("");
                var result = api.LMSFinish("");
                finished = true;
                return result === "true" || result === true;
            }
            return false;
        },
        
        setLocation: function(slideIndex) {
            if (!initialized) return false;
            
            var api = getAPI();
            if (api) {
                api.LMSSetValue("cmi.core.lesson_location", String(slideIndex));
                api.LMSCommit("");
                return true;
            }
            return false;
        },
        
        getLocation: function() {
            if (!initialized) return 0;
            
            var api = getAPI();
            if (api) {
                var location = api.LMSGetValue("cmi.core.lesson_location");
                return parseInt(location) || 0;
            }
            return window.scormBookmark || 0;
        },
        
        setComplete: function() {
            if (!initialized) return false;
            
            var api = getAPI();
            if (api) {
                api.LMSSetValue("cmi.core.lesson_status", "completed");
                api.LMSCommit("");
                return true;
            }
            return false;
        },
        
        setScore: function(score) {
            if (!initialized) return false;
            
            var api = getAPI();
            if (api) {
                api.LMSSetValue("cmi.core.score.raw", String(score));
                api.LMSSetValue("cmi.core.score.min", "0");
                api.LMSSetValue("cmi.core.score.max", "100");
                api.LMSCommit("");
                return true;
            }
            return false;
        },
        
        commit: function() {
            if (!initialized) return false;
            
            var api = getAPI();
            if (api) {
                api.LMSCommit("");
                return true;
            }
            return false;
        }
    };
})();

// Initialize on load
window.addEventListener('load', function() {
    ScormAPI.initialize();
});

// Finish on unload
window.addEventListener('beforeunload', function() {
    ScormAPI.finish();
});
'''

PLAYER_JS = '''/**
 * SCORM Course Player
 */

// Mobile orientation detection - Show overlay when in portrait mode on small screens
function checkMobileOrientation() {
    var overlay = document.getElementById('orientation-overlay');
    var playerContainer = document.getElementById('player-container');
    if (!overlay || !playerContainer) return;
    
    // Check if screen is in portrait mode and is a small screen (mobile/tablet)
    var isPortrait = window.innerHeight > window.innerWidth;
    var isSmallScreen = window.innerWidth < 900; // Increased threshold
    var aspectRatio = window.innerWidth / window.innerHeight;
    
    // Show overlay if portrait mode on small screen with poor aspect ratio for slides
    if (isPortrait && isSmallScreen && aspectRatio < 0.8) {
        overlay.style.display = 'flex';
        playerContainer.style.display = 'none';
    } else {
        overlay.style.display = 'none';
        playerContainer.style.display = 'flex';
    }
}

// Listen for orientation changes
window.addEventListener('orientationchange', function() {
    setTimeout(checkMobileOrientation, 150);
});

// Listen for resize events
window.addEventListener('resize', function() {
    checkMobileOrientation();
});

// Initial check on load
window.addEventListener('load', function() {
    setTimeout(checkMobileOrientation, 100);
});

// Also check on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    checkMobileOrientation();
});

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
    
    function loadCourse(courseData) {
        course = courseData;
        totalSlides = course.slides.length;
        
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
        
        // Setup global audio if exists
        if (course.globalAudio && course.globalAudio.src) {
            setupGlobalAudio();
        }
        
        // Check if first slide has audio and show start overlay
        checkAndShowStartOverlay();
        
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
        
        // Listen for fullscreen changes to prevent re-renders
        document.addEventListener('fullscreenchange', handleFullscreenChange);
        document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
        document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    }
    
    function updateSlideScale() {
        // Just update the transform scale without re-rendering elements
        var slideContainer = document.getElementById('slide-container');
        var slideContent = document.getElementById('slide-content');
        if (!slideContainer || !slideContent) return;
        
        var slide = course.slides[currentSlide];
        if (!slide) return;
        
        var slideWidth = slide.width || 960;
        var slideHeight = slide.height || 540;
        
        var containerRect = slideContainer.getBoundingClientRect();
        var containerWidth = containerRect.width || slideContainer.clientWidth;
        var containerHeight = containerRect.height || slideContainer.clientHeight;
        
        var scaleX = containerWidth / slideWidth;
        var scaleY = containerHeight / slideHeight;
        var scale = Math.min(scaleX, scaleY, 1);
        
        slideContent.style.transform = 'scale(' + scale + ')';
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
    
    // Stop all currently playing slide audios
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
    }
    
    function renderSlide(index) {
        // Don't re-render if a video is in fullscreen or just exited fullscreen
        if (isVideoFullscreen || fullscreenExitProtection) {
            return;
        }
        
        // Stop any playing slide audio before rendering new slide
        stopAllSlideAudios();
        
        var slide = course.slides[index];
        var container = document.getElementById('slide-container');
        var wrapper = document.getElementById('slide-wrapper');
        
        // Get slide dimensions
        var slideWidth = slide.width || 960;
        var slideHeight = slide.height || 540;
        
        // Calculate scale to fit in wrapper while maintaining aspect ratio
        var wrapperRect = wrapper.getBoundingClientRect();
        var availableWidth = wrapperRect.width - 40; // padding
        var availableHeight = wrapperRect.height - 40; // padding
        
        var scaleX = availableWidth / slideWidth;
        var scaleY = availableHeight / slideHeight;
        var scale = Math.min(scaleX, scaleY, 1); // Never scale up, only down
        
        // Apply scale and size
        container.style.width = slideWidth + 'px';
        container.style.height = slideHeight + 'px';
        container.style.transform = 'scale(' + scale + ')';
        
        // Clear previous content
        container.innerHTML = '';
        
        // Clear any existing timeline timers
        if (window.slideTimelineTimers) {
            window.slideTimelineTimers.forEach(function(timer) {
                clearTimeout(timer);
            });
        }
        window.slideTimelineTimers = [];
        
        // Set background
        container.style.backgroundColor = slide.background || '#FFFFFF';
        if (slide.backgroundImage) {
            // Create background image element - must fill entire container
            var bgImg = document.createElement('img');
            bgImg.src = slide.backgroundImage;
            bgImg.style.position = 'absolute';
            bgImg.style.top = '0';
            bgImg.style.left = '0';
            bgImg.style.width = '100%';
            bgImg.style.height = '100%';
            bgImg.style.objectFit = 'fill'; // Fill the entire container to match element positions
            bgImg.style.pointerEvents = 'none';
            bgImg.style.zIndex = '0';
            container.appendChild(bgImg);
        }
        
        // Get slide duration for timeline
        var slideDuration = slide.duration || 10;
        
        // Render elements (filter out invisible ones)
        slide.elements.forEach(function(element, elemIndex) {
            // Skip invisible elements (used for accessibility text)
            if (element.visible === false) return;
            
            var el = createElementNode(element);
            if (el) {
                // Check if element has timeline settings
                var startTime = element.startTime || 0;
                var endTime = element.endTime !== undefined && element.endTime !== null ? element.endTime : slideDuration;
                
                // If element should not appear immediately, hide it
                if (startTime > 0) {
                    el.style.opacity = '0';
                    el.style.visibility = 'hidden';
                    el.style.transition = 'opacity 0.3s ease-in-out';
                    
                    // Schedule element to appear at startTime
                    var showTimer = setTimeout(function() {
                        el.style.opacity = '1';
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
                
                // Apply entrance animations
                if (element.animations && element.animations.length > 0) {
                    scheduleAnimations(el, element.animations);
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
                playSlideAudio(slide.audio);
            }
        }
        
        // Update navigation
        updateNavigation();
        
        // Save position to SCORM
        ScormAPI.setLocation(index);
        
        // Check completion
        if (index === totalSlides - 1) {
            ScormAPI.setComplete();
        }
    }
    
    function createElementNode(element) {
        var el;
        
        switch (element.type) {
            case 'text':
                el = document.createElement('div');
                el.className = 'slide-element text-element';
                el.innerHTML = element.content ? element.content.replace(/\\n/g, '<br>') : '';
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
                img.style.objectFit = 'contain';
                el.appendChild(img);
                break;
                
            case 'shape':
                el = document.createElement('div');
                el.className = 'slide-element shape-element';
                if (element.content) {
                    el.innerHTML = element.content.replace(/\\n/g, '<br>');
                }
                applyShapeStyles(el, element);
                break;
                
            case 'video':
                if (element.embedUrl) {
                    el = document.createElement('div');
                    el.className = 'slide-element video-element';
                    var iframe = document.createElement('iframe');
                    iframe.src = element.embedUrl;
                    iframe.allow = 'autoplay; fullscreen';
                    iframe.frameBorder = '0';
                    iframe.style.width = '100%';
                    iframe.style.height = '100%';
                    iframe.style.border = 'none';
                    el.appendChild(iframe);
                } else if (element.src) {
                    el = document.createElement('div');
                    el.className = 'slide-element video-element';
                    el.style.background = 'transparent';
                    var video = document.createElement('video');
                    video.src = element.src;
                    video.controls = true;
                    video.playsInline = true;
                    video.style.width = '100%';
                    video.style.height = '100%';
                    video.style.background = 'transparent';
                    video.style.objectFit = 'contain';
                    
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
                htmlIframe.srcdoc = element.htmlContent || '<p>HTML Content</p>';
                htmlIframe.style.width = '100%';
                htmlIframe.style.height = '100%';
                htmlIframe.style.border = 'none';
                htmlIframe.sandbox = 'allow-scripts allow-same-origin';
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
                } else if (element.flipbookType === 'pdf' && element.flipbookUrl) {
                    var pdfIframe = document.createElement('iframe');
                    pdfIframe.src = element.flipbookUrl;
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
                
            default:
                el = document.createElement('div');
                el.className = 'slide-element';
        }
        
        if (!el) return null;
        
        // Apply positioning and styles with explicit pixel values
        el.style.position = 'absolute';
        el.style.left = (element.x || 0) + 'px';
        el.style.top = (element.y || 0) + 'px';
        el.style.width = (element.width || 100) + 'px';
        el.style.height = (element.height || 100) + 'px';
        el.style.zIndex = (element.zIndex || 0) + 1;
        
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
        if (style.opacity !== undefined) el.style.opacity = style.opacity;
        if (style.fontSize) el.style.fontSize = style.fontSize + 'px';
        if (style.fontFamily) el.style.fontFamily = style.fontFamily;
        if (style.fontWeight) el.style.fontWeight = style.fontWeight;
        if (style.fontColor) el.style.color = style.fontColor;
        if (style.textAlign) el.style.textAlign = style.textAlign;
        if (style.borderRadius) el.style.borderRadius = style.borderRadius + 'px';
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
        
        if (element.style && element.style.fill) {
            el.style.backgroundColor = element.style.fill;
        }
        if (element.style && element.style.stroke) {
            el.style.border = '2px solid ' + element.style.stroke;
        }
    }
    
    function scheduleAnimations(el, animations) {
        animations.forEach(function(anim, index) {
            var delay = (anim.startTime || anim.delay || index * 0.3) * 1000;
            var duration = (anim.duration || 0.5) * 1000;
            
            // Initial state for entrance animations
            if (anim.type === 'entrance') {
                el.style.opacity = '0';
            }
            
            setTimeout(function() {
                el.style.transition = 'all ' + duration + 'ms ' + (anim.easing || 'ease');
                
                switch (anim.effect) {
                    case 'fade':
                        el.style.opacity = anim.type === 'exit' ? '0' : '1';
                        break;
                    case 'fly':
                        el.style.opacity = '1';
                        break;
                    case 'zoom':
                        el.style.transform = anim.type === 'entrance' ? 'scale(1)' : 'scale(0)';
                        el.style.opacity = '1';
                        break;
                    default:
                        el.style.opacity = '1';
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
    
    function playSlideAudio(audioList) {
        // Clear any previously tracked audios
        stopAllSlideAudios();
        
        audioList.forEach(function(audio) {
            var audioEl = new Audio(audio.src);
            audioEl.volume = audio.volume || 1;
            // Track this audio so we can stop it later
            activeSlideAudios.push(audioEl);
            audioEl.play().catch(function(e) {
                console.log('Audio autoplay blocked');
            });
        });
    }
    
    function nextSlide() {
        if (currentSlide < totalSlides - 1) {
            currentSlide++;
            renderSlide(currentSlide);
            updateProgress();
        }
    }
    
    function prevSlide() {
        if (currentSlide > 0) {
            currentSlide--;
            renderSlide(currentSlide);
            updateProgress();
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
        var progress = ((currentSlide + 1) / totalSlides) * 100;
        var progressBar = document.getElementById('progress-bar');
        var slideCounter = document.getElementById('slide-counter');
        
        if (progressBar) {
            progressBar.style.width = progress + '%';
        }
        if (slideCounter) {
            slideCounter.textContent = (currentSlide + 1) + ' / ' + totalSlides;
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
            nextBtn.disabled = currentSlide === totalSlides - 1;
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
            item.className = 'sidebar-slide-item' + (index === currentSlide ? ' active' : '');
            item.onclick = function() {
                goToSlide(index);
            };
            
            // Create thumbnail using background image or placeholder
            var thumbnail = document.createElement('div');
            thumbnail.className = 'sidebar-thumbnail';
            if (slide.backgroundImage) {
                thumbnail.style.backgroundImage = 'url(' + slide.backgroundImage + ')';
            } else {
                thumbnail.style.backgroundColor = slide.background || '#f0f0f0';
            }
            
            // Create slide info
            var info = document.createElement('div');
            info.className = 'sidebar-slide-info';
            
            var title = document.createElement('div');
            title.className = 'sidebar-slide-title';
            title.textContent = 'Slide ' + (index + 1);
            
            var status = document.createElement('div');
            status.className = 'sidebar-slide-status';
            if (index < currentSlide) {
                status.innerHTML = '✓ Concluído';
                status.classList.add('completed');
            } else if (index === currentSlide) {
                status.innerHTML = '● Atual';
                status.classList.add('current');
            } else {
                status.innerHTML = '○ Pendente';
            }
            
            info.appendChild(title);
            info.appendChild(status);
            item.appendChild(thumbnail);
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
                if (index < currentSlide) {
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
    
    // Keyboard navigation
    document.addEventListener('keydown', function(e) {
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
        toggleSidebar: toggleSidebar
    };
})();

// Load course on page ready
document.addEventListener('DOMContentLoaded', function() {
    fetch('course.json')
        .then(function(response) { return response.json(); })
        .then(function(data) { CoursePlayer.load(data); })
        .catch(function(error) { console.error('Failed to load course:', error); });
});
'''

PLAYER_HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #fff;
            overflow: hidden;
        }}
        
        #player-container {{
            width: 100vw;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        
        /* Sidebar Navigation Styles */
        #slide-sidebar {{
            position: fixed;
            left: -280px;
            top: 0;
            width: 280px;
            height: calc(100vh - 60px);
            background: #16213e;
            z-index: 500;
            transition: left 0.3s ease;
            display: flex;
            flex-direction: column;
            box-shadow: 4px 0 20px rgba(0,0,0,0.3);
        }}
        
        #slide-sidebar.open {{
            left: 0;
        }}
        
        .sidebar-header {{
            padding: 20px;
            background: #0f3460;
            border-bottom: 1px solid #1a4980;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .sidebar-header h3 {{
            margin: 0;
            font-size: 16px;
            font-weight: 600;
            color: #f1f5f9;
        }}
        
        .sidebar-close {{
            background: transparent;
            border: none;
            color: #94a3b8;
            font-size: 20px;
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 4px;
            transition: all 0.2s;
        }}
        
        .sidebar-close:hover {{
            background: rgba(255,255,255,0.1);
            color: #fff;
        }}
        
        #sidebar-slides {{
            flex: 1;
            overflow-y: auto;
            padding: 10px;
        }}
        
        #sidebar-slides::-webkit-scrollbar {{
            width: 6px;
        }}
        
        #sidebar-slides::-webkit-scrollbar-track {{
            background: #0f3460;
        }}
        
        #sidebar-slides::-webkit-scrollbar-thumb {{
            background: #1a4980;
            border-radius: 3px;
        }}
        
        .sidebar-slide-item {{
            display: flex;
            align-items: center;
            padding: 10px;
            margin-bottom: 8px;
            background: #0f3460;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
            border: 2px solid transparent;
        }}
        
        .sidebar-slide-item:hover {{
            background: #1a4980;
        }}
        
        .sidebar-slide-item.active {{
            border-color: #7c3aed;
            background: linear-gradient(135deg, rgba(124, 58, 237, 0.2), rgba(6, 182, 212, 0.1));
        }}
        
        .sidebar-thumbnail {{
            width: 80px;
            height: 45px;
            border-radius: 4px;
            background-size: cover;
            background-position: center;
            flex-shrink: 0;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        
        .sidebar-slide-info {{
            margin-left: 12px;
            flex: 1;
            min-width: 0;
        }}
        
        .sidebar-slide-title {{
            font-size: 14px;
            font-weight: 500;
            color: #f1f5f9;
            margin-bottom: 4px;
        }}
        
        .sidebar-slide-status {{
            font-size: 12px;
            color: #64748b;
        }}
        
        .sidebar-slide-status.completed {{
            color: #22c55e;
        }}
        
        .sidebar-slide-status.current {{
            color: #7c3aed;
        }}
        
        /* Adjust main content when sidebar is open */
        #slide-wrapper {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            background: #0f0f1a;
            overflow: hidden;
            transition: margin-left 0.3s ease;
        }}
        
        #slide-wrapper.sidebar-open {{
            margin-left: 280px;
        }}
        
        #slide-container {{
            width: {width}px;
            height: {height}px;
            background: #fff;
            position: relative;
            overflow: visible; /* Allow elements with negative positions to be visible */
            box-shadow: 0 10px 50px rgba(0,0,0,0.5);
            transform-origin: center center;
            /* Scale will be calculated dynamically by JS */
        }}
        
        .slide-element {{
            position: absolute !important;
            /* Removed overflow: hidden to allow proper rendering */
        }}
        
        .text-element {{
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        
        .image-element {{
            object-fit: contain;
        }}
        
        .image-element img {{
            width: 100% !important;
            height: 100% !important;
            object-fit: contain !important;
        }}
        
        .video-element {{
            border: none !important;
            background: transparent !important;
        }}
        
        .video-element iframe,
        .video-element video {{
            width: 100% !important;
            height: 100% !important;
            border: none !important;
            background: transparent !important;
        }}
        
        /* WebM videos with transparent background */
        .video-element video[src*=".webm"] {{
            background: transparent !important;
        }}
        
        /* Button Element Styles */
        .button-element {{
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .scorm-button {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
        }}
        
        .scorm-button.primary {{
            background: linear-gradient(135deg, #7c3aed, #06b6d4);
            color: white;
        }}
        
        .scorm-button.primary:hover {{
            opacity: 0.9;
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(124, 58, 237, 0.4);
        }}
        
        .scorm-button.secondary {{
            background: #4b5563;
            color: white;
        }}
        
        .scorm-button.secondary:hover {{
            background: #374151;
        }}
        
        .scorm-button.outline {{
            background: transparent;
            border: 2px solid #7c3aed;
            color: #7c3aed;
        }}
        
        .scorm-button.outline:hover {{
            background: rgba(124, 58, 237, 0.1);
        }}
        
        .scorm-button.ghost {{
            background: transparent;
            color: #374151;
        }}
        
        .scorm-button.ghost:hover {{
            background: rgba(0, 0, 0, 0.05);
        }}
        
        .scorm-button .btn-icon {{
            font-size: 1.2em;
        }}
        
        /* HTML Element Styles */
        .html-element {{
            background: white;
            border-radius: 4px;
            overflow: hidden;
        }}
        
        .html-element iframe {{
            width: 100%;
            height: 100%;
            border: none;
        }}
        
        /* Flipbook Element Styles */
        .flipbook-element {{
            background: #f0f0f0;
            border-radius: 4px;
            overflow: hidden;
        }}
        
        .flipbook-element iframe {{
            width: 100%;
            height: 100%;
            border: none;
        }}
        
        .flipbook-images-container {{
            width: 100%;
            height: 100%;
        }}
        
        #controls {{
            height: 60px;
            background: #16213e;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 20px;
            border-top: 1px solid #0f3460;
        }}
        
        .nav-buttons {{
            display: flex;
            gap: 10px;
        }}
        
        .control-btn {{
            background: #0f3460;
            border: none;
            color: #fff;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.2s;
        }}
        
        .control-btn:hover:not(:disabled) {{
            background: #1a4980;
        }}
        
        .control-btn:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}
        
        #progress-container {{
            flex: 1;
            margin: 0 20px;
            height: 6px;
            background: #0f3460;
            border-radius: 3px;
            overflow: hidden;
        }}
        
        #progress-bar {{
            height: 100%;
            background: linear-gradient(90deg, #7c3aed, #06b6d4);
            width: 0%;
            transition: width 0.3s ease;
        }}
        
        #slide-counter {{
            font-size: 14px;
            color: #94a3b8;
            min-width: 80px;
            text-align: center;
        }}
        
        .icon-btn {{
            background: transparent;
            border: none;
            color: #94a3b8;
            padding: 8px;
            cursor: pointer;
            border-radius: 4px;
            transition: color 0.2s, background 0.2s;
        }}
        
        .icon-btn:hover {{
            color: #fff;
            background: rgba(255,255,255,0.1);
        }}
        
        #global-audio {{
            display: none;
        }}
        
        /* Volume control styles */
        .volume-wrapper {{
            position: relative;
            display: flex;
            align-items: center;
        }}
        
        #volume-control {{
            display: none;
            position: absolute;
            bottom: 50px;
            left: 50%;
            transform: translateX(-50%);
            background: #16213e;
            padding: 15px 10px;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
            flex-direction: column;
            align-items: center;
            gap: 8px;
            z-index: 100;
        }}
        
        #volume-control::after {{
            content: '';
            position: absolute;
            bottom: -8px;
            left: 50%;
            transform: translateX(-50%);
            border-left: 8px solid transparent;
            border-right: 8px solid transparent;
            border-top: 8px solid #16213e;
        }}
        
        #volume-slider {{
            -webkit-appearance: none;
            width: 100px;
            height: 6px;
            border-radius: 3px;
            background: #0f3460;
            outline: none;
        }}
        
        #volume-slider::-webkit-slider-thumb {{
            -webkit-appearance: none;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: linear-gradient(135deg, #7c3aed, #06b6d4);
            cursor: pointer;
            transition: transform 0.1s;
        }}
        
        #volume-slider::-webkit-slider-thumb:hover {{
            transform: scale(1.2);
        }}
        
        #volume-slider::-moz-range-thumb {{
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: linear-gradient(135deg, #7c3aed, #06b6d4);
            cursor: pointer;
            border: none;
        }}
        
        #volume-value {{
            font-size: 12px;
            color: #94a3b8;
            min-width: 40px;
            text-align: center;
        }}
        
        /* Start overlay styles */
        #start-overlay {{
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 60px;
            background: rgba(15, 23, 42, 0.95);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            backdrop-filter: blur(10px);
        }}
        
        .start-overlay-content {{
            text-align: center;
            color: #fff;
            padding: 40px;
            max-width: 400px;
        }}
        
        .start-overlay-icon {{
            font-size: 64px;
            margin-bottom: 20px;
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); opacity: 1; }}
            50% {{ transform: scale(1.1); opacity: 0.8; }}
        }}
        
        .start-overlay-content h2 {{
            font-size: 24px;
            margin: 0 0 10px 0;
            color: #f1f5f9;
        }}
        
        .start-overlay-content p {{
            font-size: 14px;
            color: #94a3b8;
            margin: 0 0 30px 0;
        }}
        
        .start-btn {{
            background: linear-gradient(135deg, #7c3aed, #06b6d4);
            border: none;
            color: #fff;
            padding: 16px 40px;
            border-radius: 30px;
            cursor: pointer;
            font-size: 18px;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
            box-shadow: 0 4px 20px rgba(124, 58, 237, 0.4);
        }}
        
        .start-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 30px rgba(124, 58, 237, 0.6);
        }}
        
        .start-btn:active {{
            transform: translateY(0);
        }}
        
        /* Mobile Orientation Overlay */
        #orientation-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            z-index: 99999;
            justify-content: center;
            align-items: center;
            flex-direction: column;
        }}
        
        /* Force display on mobile portrait mode using CSS media query */
        @media screen and (orientation: portrait) and (max-width: 900px) {{
            #orientation-overlay {{
                display: flex !important;
            }}
            #player-container {{
                display: none !important;
            }}
        }}
        
        /* Also detect by aspect ratio for devices that don't report orientation correctly */
        @media screen and (max-aspect-ratio: 4/5) and (max-width: 900px) {{
            #orientation-overlay {{
                display: flex !important;
            }}
            #player-container {{
                display: none !important;
            }}
        }}
        
        .orientation-content {{
            text-align: center;
            padding: 30px;
            color: white;
            max-width: 90%;
        }}
        
        .orientation-icon {{
            font-size: 70px;
            margin-bottom: 10px;
            animation: shake 1.5s ease-in-out infinite;
        }}
        
        .orientation-arrow {{
            font-size: 50px;
            color: #7c3aed;
            margin-bottom: 15px;
            animation: rotate-hint 2s ease-in-out infinite;
        }}
        
        @keyframes rotate-hint {{
            0%, 100% {{ transform: rotate(0deg); }}
            50% {{ transform: rotate(90deg); }}
        }}
        
        @keyframes shake {{
            0%, 100% {{ transform: rotate(-10deg); }}
            50% {{ transform: rotate(10deg); }}
        }}
        
        .orientation-content h2 {{
            font-size: 24px;
            margin-bottom: 12px;
            color: #fff;
        }}
        
        .orientation-content p {{
            font-size: 14px;
            color: #a0aec0;
            margin-bottom: 25px;
            line-height: 1.5;
        }}
        
        .orientation-hint {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
            margin-top: 15px;
        }}
        
        .phone-icon {{
            font-size: 40px;
            transition: all 0.3s ease;
        }}
        
        .phone-icon.vertical {{
            opacity: 0.5;
        }}
        
        .phone-icon.horizontal {{
            transform: rotate(90deg);
            color: #7c3aed;
        }}
        
        .orientation-hint .arrow {{
            font-size: 24px;
            color: #7c3aed;
            animation: pulse-arrow 1s ease-in-out infinite;
        }}
        
        @keyframes pulse-arrow {{
            0%, 100% {{ transform: translateX(0); opacity: 1; }}
            50% {{ transform: translateX(10px); opacity: 0.5; }}
        }}
    </style>
</head>
<body>
    <!-- Mobile Orientation Overlay -->
    <div id="orientation-overlay">
        <div class="orientation-content">
            <div class="orientation-icon">📱</div>
            <div class="orientation-arrow">↻</div>
            <h2>Rotacione seu dispositivo</h2>
            <p>Para uma melhor experiência, por favor visualize este conteúdo no modo horizontal (paisagem)</p>
            <div class="orientation-hint">
                <span class="phone-icon vertical">📱</span>
                <span class="arrow">→</span>
                <span class="phone-icon horizontal">📱</span>
            </div>
        </div>
    </div>
    
    <div id="player-container">
        <!-- Sidebar Navigation -->
        <div id="slide-sidebar">
            <div class="sidebar-header">
                <h3>📚 Navegação</h3>
                <button class="sidebar-close" onclick="CoursePlayer.toggleSidebar()" title="Fechar menu">✕</button>
            </div>
            <div id="sidebar-slides"></div>
        </div>
        
        <div id="slide-wrapper">
            <div id="slide-container"></div>
        </div>
        
        <!-- Start overlay for audio autoplay permission -->
        <div id="start-overlay" style="display: none;">
            <div class="start-overlay-content">
                <div class="start-overlay-icon">🔊</div>
                <h2>Este curso contém áudio</h2>
                <p>Clique no botão abaixo para iniciar o curso com áudio</p>
                <button class="start-btn" onclick="CoursePlayer.startCourse()">
                    ▶ Iniciar Curso
                </button>
            </div>
        </div>
        
        <div id="controls">
            <div class="nav-buttons">
                <button class="icon-btn" onclick="CoursePlayer.toggleSidebar()" title="Menu de Navegação">
                    ☰
                </button>
                <button class="control-btn" id="prev-btn" onclick="CoursePlayer.prev()">
                    ← Anterior
                </button>
                <button class="control-btn" id="next-btn" onclick="CoursePlayer.next()">
                    Próximo →
                </button>
            </div>
            <div id="progress-container">
                <div id="progress-bar"></div>
            </div>
            <span id="slide-counter">1 / 1</span>
            <div class="nav-buttons">
                <div class="volume-wrapper">
                    <button class="icon-btn" id="volume-btn" onclick="CoursePlayer.toggleVolumeSlider()" title="Volume">
                        🔊
                    </button>
                    <div id="volume-control">
                        <input type="range" id="volume-slider" min="0" max="100" value="100" 
                               oninput="CoursePlayer.setVolume(this.value); document.getElementById('volume-value').textContent = this.value + '%'">
                        <span id="volume-value">100%</span>
                    </div>
                </div>
                <button class="icon-btn" onclick="CoursePlayer.fullscreen()" title="Tela Cheia">
                    ⛶
                </button>
            </div>
        </div>
    </div>
    <audio id="global-audio"></audio>
    <script src="scripts/scorm-api.js"></script>
    <script src="scripts/player.js"></script>
</body>
</html>'''

# XSD files content (minimal valid XSD for SCORM 1.2)
ADLCP_XSD = '''<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    targetNamespace="http://www.adlnet.org/xsd/adlcp_rootv1p2"
    xmlns="http://www.adlnet.org/xsd/adlcp_rootv1p2"
    elementFormDefault="qualified">
    <xsd:attribute name="scormtype">
        <xsd:simpleType>
            <xsd:restriction base="xsd:string">
                <xsd:enumeration value="sco"/>
                <xsd:enumeration value="asset"/>
            </xsd:restriction>
        </xsd:simpleType>
    </xsd:attribute>
    <xsd:element name="masteryscore" type="xsd:string"/>
</xsd:schema>'''

IMS_XML_XSD = '''<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    targetNamespace="http://www.w3.org/XML/1998/namespace"
    xml:lang="en">
    <xsd:attribute name="lang" type="xsd:language"/>
</xsd:schema>'''

IMSCP_XSD = '''<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    targetNamespace="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
    xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
    elementFormDefault="qualified">
    <xsd:element name="manifest"/>
    <xsd:element name="organizations"/>
    <xsd:element name="organization"/>
    <xsd:element name="item"/>
    <xsd:element name="resources"/>
    <xsd:element name="resource"/>
    <xsd:element name="file"/>
    <xsd:element name="metadata"/>
    <xsd:element name="title" type="xsd:string"/>
    <xsd:element name="schema" type="xsd:string"/>
    <xsd:element name="schemaversion" type="xsd:string"/>
</xsd:schema>'''

IMSMD_XSD = '''<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    targetNamespace="http://www.imsglobal.org/xsd/imsmd_rootv1p2p1"
    xmlns="http://www.imsglobal.org/xsd/imsmd_rootv1p2p1"
    elementFormDefault="qualified">
    <xsd:element name="lom"/>
    <xsd:element name="general"/>
    <xsd:element name="title"/>
    <xsd:element name="langstring" type="xsd:string"/>
</xsd:schema>'''

def export_scorm_package(project: Project, storage_dir: str, output_dir: str) -> str:
    """
    Export a project as a SCORM 1.2 package
    Returns the path to the generated ZIP file
    """
    logger.info(f"Exporting SCORM package for project: {project.id}")
    
    course = project.course
    
    # Create temp directory for package
    package_dir = Path(output_dir) / f"scorm_{project.id}"
    package_dir.mkdir(parents=True, exist_ok=True)
    
    # Create directory structure
    (package_dir / "assets").mkdir(exist_ok=True)
    (package_dir / "resources").mkdir(exist_ok=True)
    (package_dir / "scripts").mkdir(exist_ok=True)
    
    # Copy assets from storage
    project_assets = Path(storage_dir) / project.id / "assets"
    if project_assets.exists():
        for asset in project_assets.iterdir():
            shutil.copy2(asset, package_dir / "assets" / asset.name)
            logger.info(f"Copied asset: {asset.name}")
    
    # Write scripts
    with open(package_dir / "scripts" / "scorm-api.js", 'w') as f:
        f.write(SCORM_API_JS)
    
    with open(package_dir / "scripts" / "player.js", 'w') as f:
        f.write(PLAYER_JS)
    
    # Prepare course.json - Fix asset URLs for SCORM package
    course_data = course.model_dump()
    
    # Convert datetime to string
    course_data['createdAt'] = course.createdAt.isoformat() if course.createdAt else None
    course_data['updatedAt'] = course.updatedAt.isoformat() if course.updatedAt else None
    
    # Fix all asset URLs in slides
    for slide in course_data.get('slides', []):
        # Fix background image URL
        if slide.get('backgroundImage'):
            bg_url = slide['backgroundImage']
            # Convert /api/projects/{id}/assets/filename.png to assets/filename.png
            if '/assets/' in bg_url:
                filename = bg_url.split('/assets/')[-1]
                slide['backgroundImage'] = f"assets/{filename}"
                logger.info(f"Fixed backgroundImage URL: {slide['backgroundImage']}")
        
        # Fix element URLs
        for element in slide.get('elements', []):
            if element.get('src') and '/assets/' in element.get('src', ''):
                filename = element['src'].split('/assets/')[-1]
                element['src'] = f"assets/{filename}"
            # Handle external video URLs (like HeyGen videos)
            elif element.get('type') == 'video' and element.get('src') and element['src'].startswith('http'):
                try:
                    import hashlib
                    # Generate a unique filename based on the URL
                    url_hash = hashlib.md5(element['src'].encode()).hexdigest()[:12]
                    # Determine extension from URL or default to webm for HeyGen
                    if '.webm' in element['src'].lower():
                        ext = '.webm'
                    elif '.mp4' in element['src'].lower():
                        ext = '.mp4'
                    else:
                        ext = '.webm'  # Default to webm for HeyGen videos
                    video_filename = f"video_{url_hash}{ext}"
                    video_path = package_dir / "assets" / video_filename
                    
                    # Download the video
                    logger.info(f"Downloading external video: {element['src'][:100]}...")
                    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
                        response = client.get(element['src'])
                        if response.status_code == 200:
                            with open(video_path, 'wb') as vf:
                                vf.write(response.content)
                            element['src'] = f"assets/{video_filename}"
                            logger.info(f"Downloaded video as: {video_filename}")
                        else:
                            logger.warning(f"Failed to download video: {response.status_code}")
                except Exception as e:
                    logger.error(f"Error downloading external video: {e}")
            
            # Fix audio URLs
        for audio in slide.get('audio', []):
            if audio.get('src') and '/assets/' in audio.get('src', ''):
                filename = audio['src'].split('/assets/')[-1]
                audio['src'] = f"assets/{filename}"
    
    # Fix global audio URL
    if course_data.get('globalAudio') and course_data['globalAudio'].get('src'):
        if '/assets/' in course_data['globalAudio']['src']:
            filename = course_data['globalAudio']['src'].split('/assets/')[-1]
            course_data['globalAudio']['src'] = f"assets/{filename}"
    
    with open(package_dir / "course.json", 'w', encoding='utf-8') as f:
        json.dump(course_data, f, ensure_ascii=False, indent=2)
    
    # Get slide dimensions
    slide_width = 960
    slide_height = 540
    if course.slides:
        slide_width = int(course.slides[0].width)
        slide_height = int(course.slides[0].height)
    
    # Clean the course title - remove UUID prefix if present
    clean_title = course.metadata.title or project.name
    # Remove UUID pattern at the beginning (e.g., "a87fd1a0-1338-4043-9c2f-b0cc8572a12e_")
    clean_title = re.sub(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}_?', '', clean_title)
    clean_title = clean_title.strip('_').strip()
    if not clean_title:
        clean_title = 'Curso SCORM'
    
    # Generate index.html
    html_content = PLAYER_HTML_TEMPLATE.format(
        title=clean_title,
        lang=course.metadata.language or 'en',
        width=slide_width,
        height=slide_height
    )
    
    with open(package_dir / "index.html", 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Generate resource files list for manifest
    resource_files = []
    
    # Add assets
    assets_dir = package_dir / "assets"
    if assets_dir.exists():
        for asset in assets_dir.iterdir():
            resource_files.append(f'<file href="assets/{asset.name}"/>')
    
    # Generate imsmanifest.xml
    manifest_content = IMS_MANIFEST_TEMPLATE.format(
        identifier=f"SCORM_{project.id}",
        title=clean_title,
        resource_files='\n            '.join(resource_files)
    )
    
    with open(package_dir / "imsmanifest.xml", 'w', encoding='utf-8') as f:
        f.write(manifest_content)
    
    # Write XSD files
    with open(package_dir / "adlcp_rootv1p2.xsd", 'w', encoding='utf-8') as f:
        f.write(ADLCP_XSD)
    
    with open(package_dir / "ims_xml.xsd", 'w', encoding='utf-8') as f:
        f.write(IMS_XML_XSD)
    
    with open(package_dir / "imscp_rootv1p1p2.xsd", 'w', encoding='utf-8') as f:
        f.write(IMSCP_XSD)
    
    with open(package_dir / "imsmd_rootv1p2p1.xsd", 'w', encoding='utf-8') as f:
        f.write(IMSMD_XSD)
    
    # Create ZIP file
    # Clean the project name - remove UUID prefix if present and special characters
    clean_name = project.name
    # Remove UUID pattern at the beginning (e.g., "a87fd1a0-1338-4043-9c2f-b0cc8572a12e_")
    clean_name = re.sub(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}_?', '', clean_name)
    # Replace spaces with underscores and remove other special characters
    clean_name = re.sub(r'[^\w\s-]', '', clean_name)
    clean_name = clean_name.replace(' ', '_').strip('_')
    # Fallback to 'course' if name is empty
    if not clean_name:
        clean_name = 'course'
    
    zip_filename = f"{clean_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = Path(output_dir) / zip_filename
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(package_dir)
                zipf.write(file_path, arcname)
    
    # Cleanup temp directory
    shutil.rmtree(package_dir)
    
    logger.info(f"SCORM package created: {zip_path}")
    return str(zip_path)
