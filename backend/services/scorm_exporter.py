"""
SCORM 1.2 Exporter Service
Generates SCORM 1.2 compliant packages
"""
import os
import json
import zipfile
import logging
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
        
        // Restore position from SCORM
        var savedPosition = ScormAPI.getLocation();
        if (savedPosition > 0 && savedPosition < totalSlides) {
            currentSlide = savedPosition;
        }
        
        renderSlide(currentSlide);
        updateProgress();
        
        // Setup global audio if exists
        if (course.globalAudio && course.globalAudio.src) {
            setupGlobalAudio();
        }
        
        // Check if first slide has audio and show start overlay
        checkAndShowStartOverlay();
        
        // Recalculate scale on window resize
        window.addEventListener('resize', function() {
            renderSlide(currentSlide);
        });
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
        
        // Render elements (filter out invisible ones)
        slide.elements.forEach(function(element, elemIndex) {
            // Skip invisible elements (used for accessibility text)
            if (element.visible === false) return;
            
            var el = createElementNode(element);
            if (el) {
                container.appendChild(el);
                
                // Apply entrance animations
                if (element.animations && element.animations.length > 0) {
                    scheduleAnimations(el, element.animations);
                }
            }
        });
        
        // Render annotations if included in export
        if (slide.annotations) {
            slide.annotations.forEach(function(annotation) {
                if (annotation.includeInExport) {
                    renderAnnotation(container, annotation);
                }
            });
        }
        
        // Play slide audio
        if (slide.audio && slide.audio.length > 0) {
            playSlideAudio(slide.audio);
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
                    var video = document.createElement('video');
                    video.src = element.src;
                    video.controls = true;
                    video.style.width = '100%';
                    video.style.height = '100%';
                    el.appendChild(video);
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
        
        if (annotation.type === 'freehand' && points.length > 0) {
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
        else if (annotation.type === 'arrow' && points.length >= 2) {
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
        else if (annotation.type === 'circle' && points.length >= 2) {
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
        else if (annotation.type === 'rectangle' && points.length >= 2) {
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
            currentSlide = index;
            renderSlide(currentSlide);
            updateProgress();
        }
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
        playAudio: playGlobalAudio
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
        
        #slide-wrapper {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            background: #0f0f1a;
            overflow: hidden; /* Clip at wrapper level */
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
            background: #000 !important;
        }}
        
        .video-element iframe,
        .video-element video {{
            width: 100% !important;
            height: 100% !important;
            border: none !important;
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
    </style>
</head>
<body>
    <div id="player-container">
        <div id="slide-wrapper">
            <div id="slide-container"></div>
        </div>
        <div id="controls">
            <div class="nav-buttons">
                <button class="control-btn" id="prev-btn" onclick="CoursePlayer.prev()">
                    ← Previous
                </button>
                <button class="control-btn" id="next-btn" onclick="CoursePlayer.next()">
                    Next →
                </button>
            </div>
            <div id="progress-container">
                <div id="progress-bar"></div>
            </div>
            <span id="slide-counter">1 / 1</span>
            <div class="nav-buttons">
                <button class="icon-btn" onclick="CoursePlayer.playAudio()" title="Play Audio">
                    🔊
                </button>
                <button class="icon-btn" onclick="CoursePlayer.fullscreen()" title="Fullscreen">
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
    
    # Generate index.html
    html_content = PLAYER_HTML_TEMPLATE.format(
        title=course.metadata.title,
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
        title=course.metadata.title,
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
    zip_filename = f"{project.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
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
