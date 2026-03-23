/**
 * Gamification Engine for SCORM/HTML Courses
 * Handles badges, feedback, and achievements based on quiz and scenario performance
 */
var Gamification = (function() {
    var config = {
        enabled: true,
        showBadgesAfterQuiz: true,
        showBadgesAfterScenario: true,
        showFinalSummary: true,
        badges: [],
        quizFeedbackRanges: [],
        scenarioFeedbackRanges: [],
        completionFeedback: null
    };
    
    var earnedBadges = [];
    var quizScores = [];
    var scenarioScores = [];
    var courseCompleted = false;
    
    // Icon SVGs for badges
    var BADGE_ICONS = {
        'trophy': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 22V9m4 13V9"/><path d="M8 5h8a2 2 0 0 1 2 2v4a6 6 0 0 1-12 0V7a2 2 0 0 1 2-2z"/></svg>',
        'award': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="6"/><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11"/></svg>',
        'star': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>',
        'medal': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7.21 15 2.66 7.14a2 2 0 0 1 .13-2.2L4.4 2.8A2 2 0 0 1 6 2h12a2 2 0 0 1 1.6.8l1.6 2.14a2 2 0 0 1 .14 2.2L16.79 15"/><path d="M11 12 5.12 2.2"/><path d="m13 12 5.88-9.8"/><path d="M8 7h8"/><circle cx="12" cy="17" r="5"/><path d="M12 18v-2h-.5"/></svg>',
        'crown': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 4l3 12h14l3-12-6 7-4-7-4 7-6-7zm3 16h14"/></svg>',
        'target': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
        'brain': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/><path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4"/><path d="M17.599 6.5a3 3 0 0 0 .399-1.375"/><path d="M6.003 5.125A3 3 0 0 0 6.401 6.5"/><path d="M3.477 10.896a4 4 0 0 1 .585-.396"/><path d="M19.938 10.5a4 4 0 0 1 .585.396"/><path d="M6 18a4 4 0 0 1-1.967-.516"/><path d="M19.967 17.484A4 4 0 0 1 18 18"/></svg>',
        'lightbulb': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>',
        'puzzle': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19.439 7.85c-.049.322.059.648.289.878l1.568 1.568c.47.47.706 1.087.706 1.704s-.235 1.233-.706 1.704l-1.611 1.611a.98.98 0 0 1-.837.276c-.47-.07-.802-.48-.968-.925a2.501 2.501 0 1 0-3.214 3.214c.446.166.855.497.925.968a.979.979 0 0 1-.276.837l-1.61 1.61a2.404 2.404 0 0 1-1.705.707 2.402 2.402 0 0 1-1.704-.706l-1.568-1.568a1.026 1.026 0 0 0-.877-.29c-.493.074-.84.504-1.02.968a2.5 2.5 0 1 1-3.237-3.237c.464-.18.894-.527.967-1.02a1.026 1.026 0 0 0-.289-.877l-1.568-1.568A2.402 2.402 0 0 1 1.998 12c0-.617.236-1.234.706-1.704L4.23 8.77c.24-.24.581-.353.917-.303.515.077.877.528 1.073 1.01a2.5 2.5 0 1 0 3.259-3.259c-.482-.196-.933-.558-1.01-1.073-.05-.336.062-.676.303-.917l1.525-1.525A2.402 2.402 0 0 1 12 1.998c.617 0 1.234.236 1.704.706l1.568 1.568c.23.23.556.338.877.29.493-.074.84-.504 1.02-.968a2.5 2.5 0 1 1 3.237 3.237c-.464.18-.894.527-.967 1.02Z"/></svg>',
        'rocket': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></svg>',
        'flame': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>',
        'zap': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
        'check-circle': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
        'badge': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z"/></svg>',
        'shield': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
        'heart': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>',
        'thumbs-up': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a3.13 3.13 0 0 1 3 3.88Z"/></svg>',
        'smile': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>'
    };
    
    function init(gamificationConfig) {
        config = Object.assign(config, gamificationConfig || {});
        if (!config.enabled) return;
        injectStyles();
    }
    
    function injectStyles() {
        var style = document.createElement('style');
        style.textContent = [
            '.gamification-modal { position: fixed; inset: 0; background: rgba(0,0,0,0.8); display: flex; align-items: center; justify-content: center; z-index: 10000; animation: fadeIn 0.3s ease; }',
            '.gamification-content { background: linear-gradient(135deg, #1e293b, #0f172a); border-radius: 16px; padding: 32px; max-width: 500px; width: 90%; text-align: center; animation: slideUp 0.4s ease; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); }',
            '.gamification-emoji { font-size: 64px; margin-bottom: 16px; animation: bounce 0.6s ease; }',
            '.gamification-title { font-size: 28px; font-weight: bold; color: #fff; margin-bottom: 8px; }',
            '.gamification-message { color: #94a3b8; font-size: 16px; line-height: 1.6; margin-bottom: 24px; }',
            '.gamification-badge { display: inline-flex; flex-direction: column; align-items: center; padding: 16px; background: rgba(99,102,241,0.1); border-radius: 12px; margin: 8px; border: 1px solid rgba(99,102,241,0.3); animation: popIn 0.5s ease backwards; }',
            '.gamification-badge-icon { width: 48px; height: 48px; margin-bottom: 8px; }',
            '.gamification-badge-name { color: #fff; font-weight: 600; font-size: 14px; }',
            '.gamification-badge-desc { color: #64748b; font-size: 12px; margin-top: 4px; }',
            '.gamification-badges-grid { display: flex; flex-wrap: wrap; justify-content: center; gap: 12px; margin-bottom: 24px; }',
            '.gamification-btn { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; border: none; padding: 12px 32px; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; }',
            '.gamification-btn:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(99,102,241,0.3); }',
            '.gamification-score { font-size: 48px; font-weight: bold; background: linear-gradient(135deg, #fbbf24, #f59e0b); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; }',
            '.gamification-score-label { color: #64748b; font-size: 14px; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 16px; }',
            '.gamification-divider { height: 1px; background: linear-gradient(90deg, transparent, #334155, transparent); margin: 24px 0; }',
            '.gamification-summary-item { display: flex; align-items: center; gap: 12px; padding: 12px; background: rgba(30,41,59,0.5); border-radius: 8px; margin-bottom: 8px; }',
            '.gamification-summary-icon { width: 32px; height: 32px; }',
            '.gamification-summary-text { flex: 1; text-align: left; }',
            '.gamification-summary-label { color: #94a3b8; font-size: 12px; }',
            '.gamification-summary-value { color: #fff; font-weight: 600; }',
            '@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }',
            '@keyframes slideUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }',
            '@keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }',
            '@keyframes popIn { from { opacity: 0; transform: scale(0.8); } to { opacity: 1; transform: scale(1); } }'
        ].join('\n');
        document.head.appendChild(style);
    }
    
    function getBadgeIcon(iconName, color) {
        var svg = BADGE_ICONS[iconName] || BADGE_ICONS['award'];
        return '<div class="gamification-badge-icon" style="color: ' + color + '">' + svg + '</div>';
    }
    
    function checkBadgeCriteria(badge, type, score) {
        if (!badge.criteria || badge.criteria.type !== type) return false;
        var threshold = badge.criteria.threshold;
        var operator = badge.criteria.operator;
        
        switch (operator) {
            case 'gte': return score >= threshold;
            case 'gt': return score > threshold;
            case 'eq': return Math.abs(score - threshold) < 0.01;
            case 'lte': return score <= threshold;
            case 'lt': return score < threshold;
            default: return score >= threshold;
        }
    }
    
    function getFeedbackForScore(score, ranges) {
        for (var i = 0; i < ranges.length; i++) {
            var range = ranges[i];
            if (score >= range.minScore && score <= range.maxScore) {
                return range;
            }
        }
        return null;
    }
    
    function showFeedbackModal(options) {
        var modal = document.createElement('div');
        modal.className = 'gamification-modal';
        modal.onclick = function(e) { if (e.target === modal && options.allowClose) closeModal(); };
        
        var content = '<div class="gamification-content">';
        
        if (options.emoji) {
            content += '<div class="gamification-emoji">' + options.emoji + '</div>';
        }
        
        if (options.score !== undefined) {
            content += '<div class="gamification-score">' + Math.round(options.score) + '%</div>';
            content += '<div class="gamification-score-label">Sua Pontuação</div>';
        }
        
        content += '<div class="gamification-title">' + (options.title || 'Resultado') + '</div>';
        content += '<div class="gamification-message">' + (options.message || '') + '</div>';
        
        if (options.badges && options.badges.length > 0) {
            content += '<div class="gamification-divider"></div>';
            content += '<div class="gamification-score-label">Badges Conquistados</div>';
            content += '<div class="gamification-badges-grid">';
            options.badges.forEach(function(badge, index) {
                content += '<div class="gamification-badge" style="animation-delay: ' + (index * 0.1) + 's">';
                if (badge.customImage) {
                    content += '<img src="' + badge.customImage + '" class="gamification-badge-icon" alt="' + badge.name + '">';
                } else {
                    content += getBadgeIcon(badge.icon, badge.iconColor);
                }
                content += '<div class="gamification-badge-name">' + badge.name + '</div>';
                content += '<div class="gamification-badge-desc">' + badge.description + '</div>';
                content += '</div>';
            });
            content += '</div>';
        }
        
        content += '<button class="gamification-btn" onclick="Gamification.closeModal()">Continuar</button>';
        content += '</div>';
        
        modal.innerHTML = content;
        document.body.appendChild(modal);
    }
    
    function closeModal() {
        var modal = document.querySelector('.gamification-modal');
        if (modal) {
            modal.style.animation = 'fadeIn 0.2s ease reverse';
            setTimeout(function() { modal.remove(); }, 200);
        }
    }
    
    function onQuizComplete(score, totalQuestions, correctAnswers) {
        if (!config.enabled) return;
        
        quizScores.push(score);
        
        // Check for new badges
        var newBadges = [];
        config.badges.forEach(function(badge) {
            if (checkBadgeCriteria(badge, 'quiz_score', score)) {
                if (earnedBadges.indexOf(badge.id) === -1) {
                    earnedBadges.push(badge.id);
                    newBadges.push(badge);
                }
            }
        });
        
        if (!config.showBadgesAfterQuiz) return;
        
        // Get feedback
        var feedback = getFeedbackForScore(score, config.quizFeedbackRanges);
        
        showFeedbackModal({
            emoji: feedback ? feedback.emoji : '📝',
            score: score,
            title: feedback ? feedback.title : 'Quiz Concluído',
            message: feedback ? feedback.message : 'Você completou o quiz.',
            badges: newBadges,
            allowClose: true
        });
    }
    
    function onScenarioComplete(score, scenarioTitle) {
        if (!config.enabled) return;
        
        scenarioScores.push(score);
        
        // Check for new badges
        var newBadges = [];
        config.badges.forEach(function(badge) {
            if (checkBadgeCriteria(badge, 'scenario_score', score)) {
                if (earnedBadges.indexOf(badge.id) === -1) {
                    earnedBadges.push(badge.id);
                    newBadges.push(badge);
                }
            }
        });
        
        if (!config.showBadgesAfterScenario) return;
        
        // Get feedback
        var feedback = getFeedbackForScore(score, config.scenarioFeedbackRanges);
        
        showFeedbackModal({
            emoji: feedback ? feedback.emoji : '🎭',
            score: score,
            title: feedback ? feedback.title : 'Cenário Concluído',
            message: feedback ? feedback.message : 'Você completou o cenário "' + scenarioTitle + '".',
            badges: newBadges,
            allowClose: true
        });
    }
    
    function onCourseComplete() {
        if (!config.enabled) return;
        
        courseCompleted = true;
        
        // Check for completion badge
        var newBadges = [];
        config.badges.forEach(function(badge) {
            if (checkBadgeCriteria(badge, 'course_completion', 100)) {
                if (earnedBadges.indexOf(badge.id) === -1) {
                    earnedBadges.push(badge.id);
                    newBadges.push(badge);
                }
            }
        });
        
        if (!config.showFinalSummary) return;
        
        // Calculate averages
        var avgQuiz = quizScores.length > 0 ? quizScores.reduce(function(a,b) { return a+b; }, 0) / quizScores.length : null;
        var avgScenario = scenarioScores.length > 0 ? scenarioScores.reduce(function(a,b) { return a+b; }, 0) / scenarioScores.length : null;
        
        // Get all earned badges
        var allEarnedBadges = config.badges.filter(function(b) {
            return earnedBadges.indexOf(b.id) !== -1;
        });
        
        var feedback = config.completionFeedback || { emoji: '🎓', title: 'Curso Concluído!', message: 'Parabéns por completar o curso!' };
        
        showFeedbackModal({
            emoji: feedback.emoji,
            title: feedback.title,
            message: feedback.message,
            badges: allEarnedBadges,
            allowClose: true
        });
    }
    
    function getEarnedBadges() {
        return config.badges.filter(function(b) {
            return earnedBadges.indexOf(b.id) !== -1;
        });
    }
    
    function getStats() {
        return {
            quizScores: quizScores,
            scenarioScores: scenarioScores,
            averageQuizScore: quizScores.length > 0 ? quizScores.reduce(function(a,b) { return a+b; }, 0) / quizScores.length : 0,
            averageScenarioScore: scenarioScores.length > 0 ? scenarioScores.reduce(function(a,b) { return a+b; }, 0) / scenarioScores.length : 0,
            earnedBadges: getEarnedBadges(),
            courseCompleted: courseCompleted
        };
    }
    
    return {
        init: init,
        onQuizComplete: onQuizComplete,
        onScenarioComplete: onScenarioComplete,
        onCourseComplete: onCourseComplete,
        getEarnedBadges: getEarnedBadges,
        getStats: getStats,
        closeModal: closeModal
    };
})();
