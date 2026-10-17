/**
 * SCORM 1.2 API Wrapper
 */
var ScormAPI = (function() {
    var API = null;
    var initialized = false;
    var finished = false;
    var startTime = null;
    function accepted(result) { return result === true || result === 'true'; }
    function write(api, key, value) {
        try {
            if (accepted(api.LMSSetValue(key, String(value)))) return true;
            console.error('[ScormAPI] LMS rejected', key, api.LMSGetLastError ? api.LMSGetLastError() : '');
        } catch (error) { console.error('[ScormAPI] LMS write failed', key, error); }
        return false;
    }
    function save(api) {
        try { return accepted(api.LMSCommit('')); }
        catch (error) { console.error('[ScormAPI] Commit failed', error); return false; }
    }
    
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
                
                if (!save(api)) return false;
                var result = api.LMSFinish("");
                finished = accepted(result);
                return finished;
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
            if (!initialized) {
                console.warn('[ScormAPI] setComplete called but not initialized');
                return false;
            }
            
            var api = getAPI();
            if (api) {
                try {
                    var raw = api.LMSGetValue('cmi.core.score.raw');
                    var mastery = api.LMSGetValue('cmi.student_data.mastery_score');
                    var hasScore = raw !== null && String(raw).trim() !== '' && isFinite(Number(raw));
                    // The package declares 80. Prefer the threshold supplied by
                    // the LMS so it cannot reinterpret a passing result as failed.
                    var threshold = mastery !== null && String(mastery).trim() !== '' && isFinite(Number(mastery)) ? Number(mastery) : 80;
                    var status = hasScore ? (Number(raw) >= threshold ? 'passed' : 'failed') : 'completed';
                    if (!write(api, 'cmi.core.lesson_status', status)) return false;
                    if (!write(api, 'cmi.core.exit', '')) return false;
                    if (!save(api)) return false;
                    console.log('[ScormAPI] lesson_status saved:', status);
                    return true;
                } catch (error) { console.error('[ScormAPI] Completion failed', error); return false; }
            }
            console.warn('[ScormAPI] setComplete failed - no API');
            return false;
        },
        
        setScore: function(score) {
            if (!initialized) return false;
            
            var api = getAPI();
            if (api) {
                if (!isFinite(Number(score)) || Number(score) < 0 || Number(score) > 100) return false;
                var minSaved = write(api, 'cmi.core.score.min', '0');
                var maxSaved = write(api, 'cmi.core.score.max', '100');
                var rawSaved = write(api, 'cmi.core.score.raw', score);
                return minSaved && maxSaved && rawSaved && save(api);
            }
            return false;
        },

        getPassingScore: function(fallback) {
            var api = getAPI();
            try {
                var mastery = initialized && api ? api.LMSGetValue('cmi.student_data.mastery_score') : '';
                if (mastery !== null && String(mastery).trim() !== '' && isFinite(Number(mastery))) return Number(mastery);
            } catch (error) { console.warn('[ScormAPI] Could not read mastery score', error); }
            return typeof fallback === 'number' ? fallback : 80;
        },
        
        commit: function() {
            if (!initialized) return false;
            
            var api = getAPI();
            if (api) {
                api.LMSCommit("");
                return true;
            }
            return false;
        },
        
        getAPI: function() {
            return getAPI();
        },
        
        isInitialized: function() {
            return initialized;
        },
        
        // Direct low-level call to force status - use as last resort
        forceStatus: function(status) {
            var api = getAPI();
            if (api) {
                api.LMSSetValue("cmi.core.lesson_status", status);
                api.LMSCommit("");
                console.log('[ScormAPI] forceStatus:', status);
                return true;
            }
            return false;
        }
    };
})();

// Initialize on load
window.addEventListener('load', function() {
    ScormAPI.initialize();
    // Course JSON may have rendered the bookmarked/last slide before the
    // browser load event. Re-run the final check now that the LMS API is ready.
    if (typeof CoursePlayer !== 'undefined' && CoursePlayer.finalCompletionCheck) {
        CoursePlayer.finalCompletionCheck();
    }
});

// Before unload: let CoursePlayer do final completion check, then finish SCORM
window.addEventListener('beforeunload', function() {
    // Give CoursePlayer a chance to set completion before finishing
    if (typeof CoursePlayer !== 'undefined' && CoursePlayer.finalCompletionCheck) {
        CoursePlayer.finalCompletionCheck();
    }
    ScormAPI.finish();
});
