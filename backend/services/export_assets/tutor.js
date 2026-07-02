/**
 * AI Tutor Chat Widget for SCORM/HTML Courses
 * Slide-aware: reads the current slide content and provides contextual explanations
 * Communicates with the backend Gemini API for course-specific tutoring
 */
var AiTutor = (function() {
    var config = {};
    var history = [];
    var sessionId = 'tutor-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    var messagesUsed = 0;
    var isOpen = false;
    var isLoading = false;
    var isMaximized = false;
    var isStatsOpen = false;
    var currentSlideIndex = 0;
    var slideContexts = [];
    var msgCounter = 0;
    var feedbackStore = {};  // messageId -> 'up' | 'down'
    var lastQuestion = '';   // text of the last user question (paired with next assistant reply)
    var msgIdToQA = {};       // assistantMsgId -> { question, answer } for feedback context

    // Session stats tracked locally for the in-widget chart.
    var stats = {
        startedAt: Date.now(),
        questionTimestamps: [],            // [ts1, ts2, ...] one per user question
        perSlide: {},                      // { slideIdx: count }
        ratings: { up: 0, down: 0 },       // counts (rolling, reflects current feedbackStore)
    };

    function init(tutorConfig) {
        config = tutorConfig || {};
        if (!config.enabled) return;
        slideContexts = config.slideContexts || [];
        buildUI();
        addWelcomeMessage();
    }

    function buildUI() {
        // Inject CSS (skip if already inlined in HTML export)
        if (!config.cssInlined) {
            var cssLink = document.createElement('link');
            cssLink.rel = 'stylesheet';
            cssLink.href = 'styles/tutor.css';
            document.head.appendChild(cssLink);
        }

        // FAB button
        var fab = document.createElement('button');
        fab.className = 'tutor-fab';
        fab.id = 'tutor-fab';
        fab.setAttribute('data-testid', 'tutor-fab-button');
        fab.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span class="tutor-badge"></span>';
        fab.onclick = togglePanel;
        document.body.appendChild(fab);

        // Chat panel
        var panel = document.createElement('div');
        panel.className = 'tutor-panel';
        panel.id = 'tutor-panel';
        panel.setAttribute('data-testid', 'tutor-chat-panel');

        var tutorName = config.tutorName || 'Tutor IA';
        var courseTopic = config.courseTopic || 'este curso';

        // Build suggestions HTML
        var suggestionsHtml = '';
        var suggestions = config.suggestedQuestions || [];
        // Add default slide-aware suggestion
        var allSuggestions = ['Explique o conteudo deste slide'].concat(suggestions);
        suggestionsHtml = '<div class="tutor-suggestions" id="tutor-suggestions" data-testid="tutor-suggestions">';
        for (var i = 0; i < allSuggestions.length && i < 4; i++) {
            suggestionsHtml += '<button class="tutor-suggestion-btn" data-testid="tutor-suggestion-' + i + '" onclick="AiTutor.sendSuggestion(this)">' + escapeHtml(allSuggestions[i]) + '</button>';
        }
        suggestionsHtml += '</div>';

        panel.innerHTML =
            '<div class="tutor-header">' +
                '<div class="tutor-avatar" id="tutor-avatar-el">' +
                    (config.avatarUrl
                        ? '<img src="' + escapeHtml(config.avatarUrl) + '" alt="' + escapeHtml(tutorName) + '" />'
                        : '&#x1F393;') +
                '</div>' +
                '<div class="tutor-header-info">' +
                    '<h3>' + escapeHtml(tutorName) + '</h3>' +
                    '<p>Assistente do curso</p>' +
                '</div>' +
                '<button class="tutor-stats-btn" data-testid="tutor-stats-button" onclick="AiTutor.toggleStats()" title="Estatísticas da sessão">' +
                    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>' +
                '</button>' +
                '<button class="tutor-maximize" data-testid="tutor-maximize-button" onclick="AiTutor.toggleMaximize()" title="Maximizar">' +
                    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>' +
                '</button>' +
                '<button class="tutor-close" data-testid="tutor-close-button" onclick="AiTutor.toggle()" title="Fechar">&#x2715;</button>' +
            '</div>' +
            // Accessibility bar — font size (A+/A-) and contrast presets.
            // Choices are saved in localStorage so the student's preference
            // survives across slides and reload.
            '<div class="tutor-a11y-bar" data-testid="tutor-a11y-bar">' +
                '<span class="tutor-a11y-label">ACESSIBILIDADE:</span>' +
                '<button class="tutor-a11y-btn tutor-a11y-font-up" data-testid="tutor-a11y-font-up" onclick="AiTutor.changeFontSize(1)" title="Aumentar fonte"><span style="font-weight:700;font-size:15px">A+</span></button>' +
                '<button class="tutor-a11y-btn tutor-a11y-font-down" data-testid="tutor-a11y-font-down" onclick="AiTutor.changeFontSize(-1)" title="Diminuir fonte"><span style="font-weight:500;font-size:12px">A-</span></button>' +
                '<span class="tutor-a11y-sep"></span>' +
                '<span class="tutor-a11y-label">CONTRASTE:</span>' +
                '<button class="tutor-a11y-btn tutor-a11y-contrast" data-contrast="dark" data-testid="tutor-a11y-contrast-dark" onclick="AiTutor.setContrast(\'dark\')" title="Contraste escuro"><span class="tutor-contrast-swatch dark"></span></button>' +
                '<button class="tutor-a11y-btn tutor-a11y-contrast" data-contrast="light" data-testid="tutor-a11y-contrast-light" onclick="AiTutor.setContrast(\'light\')" title="Contraste claro"><span class="tutor-contrast-swatch light"></span></button>' +
                '<button class="tutor-a11y-btn tutor-a11y-contrast" data-contrast="high" data-testid="tutor-a11y-contrast-high" onclick="AiTutor.setContrast(\'high\')" title="Alto contraste"><span class="tutor-contrast-swatch high"></span></button>' +
            '</div>' +
            '<div class="tutor-slide-indicator" id="tutor-slide-indicator" data-testid="tutor-slide-indicator"></div>' +
            suggestionsHtml +
            '<div class="tutor-messages" id="tutor-messages" data-testid="tutor-messages">' +
                '<div class="tutor-typing" id="tutor-typing"><span></span><span></span><span></span></div>' +
            '</div>' +
            '<div class="tutor-stats-pane" id="tutor-stats-pane" data-testid="tutor-stats-pane" hidden></div>' +
            '<div class="tutor-counter" id="tutor-counter" data-testid="tutor-counter"></div>' +
            '<div class="tutor-input-area">' +
                '<input class="tutor-input" id="tutor-input" data-testid="tutor-input" placeholder="Pergunte sobre este slide..." />' +
                '<button class="tutor-send" id="tutor-send" data-testid="tutor-send-button" onclick="AiTutor.send()">' +
                    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>' +
                '</button>' +
            '</div>';

        document.body.appendChild(panel);

        // Backdrop overlay (used only in maximized mode — blurs everything
        // behind the panel so the student can focus on the answer).
        var backdrop = document.createElement('div');
        backdrop.className = 'tutor-backdrop';
        backdrop.id = 'tutor-backdrop';
        backdrop.setAttribute('data-testid', 'tutor-backdrop');
        backdrop.onclick = function() {
            // Click on backdrop closes the maximized view (back to FAB-sized panel).
            if (isMaximized) toggleMaximize();
        };
        document.body.appendChild(backdrop);

        // Stop ALL keyboard events from propagating to the SCORM player
        var tutorInput = document.getElementById('tutor-input');
        tutorInput.addEventListener('keydown', function(e) {
            e.stopPropagation();
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                AiTutor.send();
            }
        });
        tutorInput.addEventListener('keyup', function(e) { e.stopPropagation(); });
        tutorInput.addEventListener('keypress', function(e) { e.stopPropagation(); });

        updateCounter();
        updateSlideIndicator();
        applyA11yPrefs();
    }

    // Accessibility preferences — persisted in localStorage so student
    // choice survives across slides and page reloads.
    var FONT_STEPS = ['small', 'default', 'large', 'xlarge'];  // 4 levels
    function loadA11yPrefs() {
        try {
            return {
                font: localStorage.getItem('tutor-a11y-font') || 'default',
                contrast: localStorage.getItem('tutor-a11y-contrast') || 'dark',
            };
        } catch (e) {
            return { font: 'default', contrast: 'dark' };
        }
    }
    function saveA11yPrefs(prefs) {
        try {
            localStorage.setItem('tutor-a11y-font', prefs.font);
            localStorage.setItem('tutor-a11y-contrast', prefs.contrast);
        } catch (e) { /* private mode / disabled — best effort */ }
    }
    function applyA11yPrefs() {
        var panel = document.getElementById('tutor-panel');
        if (!panel) return;
        var prefs = loadA11yPrefs();
        // Clear then apply font class
        FONT_STEPS.forEach(function(s) { panel.classList.remove('tutor-font-' + s); });
        panel.classList.add('tutor-font-' + prefs.font);
        // Clear then apply contrast class
        ['dark', 'light', 'high'].forEach(function(c) { panel.classList.remove('tutor-contrast-' + c); });
        panel.classList.add('tutor-contrast-' + prefs.contrast);
        // Mark active contrast button
        var buttons = panel.querySelectorAll('.tutor-a11y-contrast');
        for (var i = 0; i < buttons.length; i++) {
            var btn = buttons[i];
            btn.classList.toggle('active', btn.getAttribute('data-contrast') === prefs.contrast);
        }
    }
    function changeFontSize(delta) {
        var prefs = loadA11yPrefs();
        var idx = FONT_STEPS.indexOf(prefs.font);
        if (idx === -1) idx = 1;  // 'default'
        idx = Math.max(0, Math.min(FONT_STEPS.length - 1, idx + delta));
        prefs.font = FONT_STEPS[idx];
        saveA11yPrefs(prefs);
        applyA11yPrefs();
    }
    function setContrast(mode) {
        var prefs = loadA11yPrefs();
        prefs.contrast = mode;
        saveA11yPrefs(prefs);
        applyA11yPrefs();
    }

    function addWelcomeMessage() {
        var tutorName = config.tutorName || 'Tutor IA';
        var topic = config.courseTopic || 'este curso';
        var welcome = 'Ola! Sou o <strong>' + escapeHtml(tutorName) + '</strong>, seu assistente para o curso sobre <strong>' + escapeHtml(topic) + '</strong>. Posso explicar o conteudo de cada slide - basta perguntar!';
        appendMessage('assistant', welcome);
    }

    function onSlideChange(slideIndex) {
        currentSlideIndex = slideIndex;
        updateSlideIndicator();
    }

    function updateSlideIndicator() {
        var indicator = document.getElementById('tutor-slide-indicator');
        if (indicator) {
            var slideNum = currentSlideIndex + 1;
            var ctx = slideContexts[currentSlideIndex];
            if (ctx) {
                var preview = ctx.length > 60 ? ctx.substring(0, 60) + '...' : ctx;
                indicator.innerHTML = '<strong>Slide ' + slideNum + '</strong>: ' + escapeHtml(preview);
            } else {
                indicator.innerHTML = '<strong>Slide ' + slideNum + '</strong>';
            }
            indicator.style.display = 'block';
        }
    }

    function getCurrentSlideContext() {
        var ctx = slideContexts[currentSlideIndex] || '';
        var slideNum = currentSlideIndex + 1;
        return 'O aluno esta no Slide ' + slideNum + '. Conteudo do slide atual:\n' + ctx;
    }

    function togglePanel() {
        isOpen = !isOpen;
        var panel = document.getElementById('tutor-panel');
        if (panel) {
            if (isOpen) {
                panel.classList.add('open');
                var input = document.getElementById('tutor-input');
                if (input) input.focus();
                updateSlideIndicator();
            } else {
                panel.classList.remove('open');
                // Closing the panel also exits maximized state — opening
                // it back later starts in the compact bottom-right view.
                if (isMaximized) {
                    isMaximized = false;
                    panel.classList.remove('maximized');
                    var backdrop = document.getElementById('tutor-backdrop');
                    if (backdrop) backdrop.classList.remove('open');
                }
            }
        }
    }

    function toggleMaximize() {
        isMaximized = !isMaximized;
        var panel = document.getElementById('tutor-panel');
        var backdrop = document.getElementById('tutor-backdrop');
        var btn = document.querySelector('.tutor-maximize');
        if (panel) panel.classList.toggle('maximized', isMaximized);
        if (backdrop) backdrop.classList.toggle('open', isMaximized);
        if (btn) {
            // Swap the icon: in maximized mode show a "shrink" glyph,
            // otherwise the diagonal arrows for "expand".
            btn.title = isMaximized ? 'Restaurar' : 'Maximizar';
            btn.innerHTML = isMaximized
                ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/><line x1="14" y1="10" x2="21" y2="3"/><line x1="3" y1="21" x2="10" y2="14"/></svg>'
                : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>';
        }
        // Auto-scroll messages to bottom when toggling (height changes).
        var container = document.getElementById('tutor-messages');
        if (container) setTimeout(function() { container.scrollTop = container.scrollHeight; }, 50);
    }

    function appendMessage(role, text) {
        var container = document.getElementById('tutor-messages');
        if (!container) return;
        var typing = document.getElementById('tutor-typing');
        var msgId = 'tutor-msg-' + (++msgCounter);

        var wrap = document.createElement('div');
        wrap.className = 'tutor-msg-wrap ' + role;
        wrap.id = msgId;

        var div = document.createElement('div');
        div.className = 'tutor-msg ' + role;
        div.innerHTML = role === 'assistant' ? formatMarkdown(text) : escapeHtml(text);
        // Stash the original (un-formatted) text so "Copy" returns plain
        // text rather than the rendered HTML with <strong>/<br>/etc.
        div.setAttribute('data-raw', text);
        wrap.appendChild(div);

        // Action toolbar (copy + feedback) — only on assistant messages.
        if (role === 'assistant') {
            // Remember the (question, answer) pair for this assistant
            // message so the feedback POST has the full context.
            msgIdToQA[msgId] = { question: lastQuestion, answer: text };
            var actions = document.createElement('div');
            actions.className = 'tutor-msg-actions';
            actions.setAttribute('data-testid', 'tutor-msg-actions-' + msgCounter);
            actions.innerHTML =
                '<button class="tutor-msg-action" data-testid="tutor-msg-copy" title="Copiar resposta" onclick="AiTutor.copyMessage(\'' + msgId + '\', this)">' +
                    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>' +
                '</button>' +
                '<button class="tutor-msg-action" data-testid="tutor-msg-thumbs-up" title="Resposta útil" onclick="AiTutor.rateMessage(\'' + msgId + '\', \'up\', this)">' +
                    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>' +
                '</button>' +
                '<button class="tutor-msg-action" data-testid="tutor-msg-thumbs-down" title="Resposta ruim" onclick="AiTutor.rateMessage(\'' + msgId + '\', \'down\', this)">' +
                    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>' +
                '</button>';
            wrap.appendChild(actions);
        }

        container.insertBefore(wrap, typing);
        container.scrollTop = container.scrollHeight;
    }

    function copyMessage(msgId, btn) {
        var wrap = document.getElementById(msgId);
        if (!wrap) return;
        var msg = wrap.querySelector('.tutor-msg');
        var text = msg ? (msg.getAttribute('data-raw') || msg.innerText || msg.textContent || '') : '';
        var done = function() {
            if (!btn) return;
            var original = btn.innerHTML;
            btn.classList.add('copied');
            btn.title = 'Copiado!';
            btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="14" height="14"><polyline points="20 6 9 17 4 12"/></svg>';
            setTimeout(function() {
                btn.classList.remove('copied');
                btn.title = 'Copiar resposta';
                btn.innerHTML = original;
            }, 1600);
        };
        var fail = function(err) { console.warn('Tutor copy failed:', err); };
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(done).catch(function() {
                _fallbackCopy(text); done();
            });
        } else {
            _fallbackCopy(text); done();
        }
    }

    function _fallbackCopy(text) {
        try {
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
        } catch (e) { /* swallow — copy is best-effort */ }
    }

    function rateMessage(msgId, rating, btn) {
        // Toggle: clicking the same rating twice clears it. Clicking the
        // opposite rating switches sides.
        var previous = feedbackStore[msgId];
        var wrap = document.getElementById(msgId);
        if (!wrap) return;
        var actions = wrap.querySelector('.tutor-msg-actions');
        if (!actions) return;
        var upBtn = actions.querySelector('[data-testid="tutor-msg-thumbs-up"]');
        var downBtn = actions.querySelector('[data-testid="tutor-msg-thumbs-down"]');
        if (upBtn) upBtn.classList.remove('rated');
        if (downBtn) downBtn.classList.remove('rated');

        var nextRating;
        if (previous === rating) {
            delete feedbackStore[msgId];
            nextRating = null;
        } else {
            feedbackStore[msgId] = rating;
            if (btn) btn.classList.add('rated');
            nextRating = rating;
        }

        // Recompute rolling rating counts for the stats chart.
        stats.ratings.up = 0;
        stats.ratings.down = 0;
        for (var k in feedbackStore) {
            if (feedbackStore[k] === 'up') stats.ratings.up++;
            else if (feedbackStore[k] === 'down') stats.ratings.down++;
        }
        if (isStatsOpen) renderStatsChart();

        // Persist to backend (best-effort, fire-and-forget). Failure is
        // silent — the in-memory feedbackStore still drives the UI.
        var qa = msgIdToQA[msgId] || {};
        var payload = {
            sessionId: sessionId,
            messageId: msgId,
            rating: nextRating,
            projectId: config.projectId || '',
            companyId: config.companyId || '',
            question: qa.question || '',
            answer: qa.answer || '',
        };
        try {
            fetch(config.apiUrl + '/api/tutor/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                keepalive: true,
            }).catch(function(e) { console.warn('Tutor feedback POST failed:', e); });
        } catch (e) { /* swallow */ }
    }

    // ===== Stats / Chart =====

    function toggleStats() {
        isStatsOpen = !isStatsOpen;
        var pane = document.getElementById('tutor-stats-pane');
        var messages = document.getElementById('tutor-messages');
        var btn = document.querySelector('.tutor-stats-btn');
        if (pane) pane.hidden = !isStatsOpen;
        if (messages) messages.style.display = isStatsOpen ? 'none' : '';
        if (btn) btn.classList.toggle('active', isStatsOpen);
        if (isStatsOpen) renderStatsChart();
    }

    function renderStatsChart() {
        var pane = document.getElementById('tutor-stats-pane');
        if (!pane) return;
        var totalQuestions = stats.questionTimestamps.length;
        var elapsedMs = Date.now() - stats.startedAt;
        var elapsedMin = Math.max(1, Math.round(elapsedMs / 60000));
        var avgPerMin = (totalQuestions / elapsedMin).toFixed(1);
        var totalRated = stats.ratings.up + stats.ratings.down;
        var satisfactionPct = totalRated > 0
            ? Math.round((stats.ratings.up / totalRated) * 100)
            : null;

        // Build the per-slide bar chart (top 6 slides by question count).
        var perSlideEntries = [];
        for (var k in stats.perSlide) perSlideEntries.push([parseInt(k, 10), stats.perSlide[k]]);
        perSlideEntries.sort(function(a, b) { return b[1] - a[1]; });
        perSlideEntries = perSlideEntries.slice(0, 6);
        var maxCount = perSlideEntries.reduce(function(m, e) { return Math.max(m, e[1]); }, 0) || 1;

        var chartW = 280, barH = 22, gap = 8, padL = 70, padR = 30, padT = 8;
        var chartH = perSlideEntries.length * (barH + gap) + padT * 2;
        var barChartSvg = '';
        if (perSlideEntries.length > 0) {
            var barsHtml = '';
            for (var i = 0; i < perSlideEntries.length; i++) {
                var entry = perSlideEntries[i];
                var slideIdx = entry[0];
                var count = entry[1];
                var w = Math.round((count / maxCount) * (chartW - padL - padR));
                var y = padT + i * (barH + gap);
                barsHtml +=
                    '<text x="' + (padL - 8) + '" y="' + (y + barH / 2 + 4) + '" text-anchor="end" fill="#cbd5e1" font-size="11">Slide ' + (slideIdx + 1) + '</text>' +
                    '<rect x="' + padL + '" y="' + y + '" width="' + w + '" height="' + barH + '" rx="4" fill="url(#tutor-bar-grad)"></rect>' +
                    '<text x="' + (padL + w + 6) + '" y="' + (y + barH / 2 + 4) + '" fill="#e2e8f0" font-size="11" font-weight="600">' + count + '</text>';
            }
            barChartSvg =
                '<svg class="tutor-stats-svg" width="100%" viewBox="0 0 ' + chartW + ' ' + chartH + '" data-testid="tutor-stats-bar-chart">' +
                    '<defs><linearGradient id="tutor-bar-grad" x1="0" x2="1" y1="0" y2="0">' +
                        '<stop offset="0%" stop-color="#6366f1"/><stop offset="100%" stop-color="#06b6d4"/>' +
                    '</linearGradient></defs>' +
                    barsHtml +
                '</svg>';
        } else {
            barChartSvg = '<div class="tutor-stats-empty" data-testid="tutor-stats-empty">Faça perguntas e o gráfico aparece aqui ✨</div>';
        }

        // Render satisfaction donut (only when at least one rating exists).
        var satisfactionHtml = '';
        if (satisfactionPct !== null) {
            var dash = Math.round(satisfactionPct * 1.51);  // out of ~151 (2πr at r=24)
            satisfactionHtml =
                '<div class="tutor-stats-donut-wrap">' +
                    '<svg class="tutor-stats-donut" width="64" height="64" viewBox="0 0 64 64" data-testid="tutor-stats-donut">' +
                        '<circle cx="32" cy="32" r="24" fill="none" stroke="rgba(148,163,184,0.25)" stroke-width="8"/>' +
                        '<circle cx="32" cy="32" r="24" fill="none" stroke="#10b981" stroke-width="8" stroke-linecap="round" transform="rotate(-90 32 32)" stroke-dasharray="' + dash + ' 151"/>' +
                        '<text x="32" y="37" text-anchor="middle" font-size="14" font-weight="700" fill="#f1f5f9">' + satisfactionPct + '%</text>' +
                    '</svg>' +
                    '<div class="tutor-stats-donut-label">satisfação</div>' +
                '</div>';
        }

        pane.innerHTML =
            '<h4 class="tutor-stats-title">Sua sessão</h4>' +
            '<div class="tutor-stats-grid">' +
                '<div class="tutor-stats-tile"><div class="tutor-stats-num" data-testid="tutor-stats-total">' + totalQuestions + '</div><div class="tutor-stats-lbl">perguntas</div></div>' +
                '<div class="tutor-stats-tile"><div class="tutor-stats-num">' + avgPerMin + '</div><div class="tutor-stats-lbl">por minuto</div></div>' +
                '<div class="tutor-stats-tile"><div class="tutor-stats-num">' + (stats.ratings.up + stats.ratings.down) + '</div><div class="tutor-stats-lbl">avaliações</div></div>' +
            '</div>' +
            satisfactionHtml +
            '<h5 class="tutor-stats-sub">Perguntas por slide</h5>' +
            barChartSvg;
    }

    function showTyping(show) {
        var el = document.getElementById('tutor-typing');
        if (el) el.className = show ? 'tutor-typing show' : 'tutor-typing';
    }

    function updateCounter() {
        var el = document.getElementById('tutor-counter');
        var limit = config.messageLimit || 50;
        if (el) {
            el.textContent = messagesUsed + ' / ' + limit + ' mensagens';
        }
    }

    function setLoading(val) {
        isLoading = val;
        var btn = document.getElementById('tutor-send');
        var input = document.getElementById('tutor-input');
        if (btn) btn.disabled = val;
        if (input) input.disabled = val;
        showTyping(val);
    }

    function send() {
        if (isLoading) return;
        var input = document.getElementById('tutor-input');
        var text = input ? input.value.trim() : '';
        if (!text) return;

        input.value = '';
        appendMessage('user', text);
        history.push({ role: 'user', content: text });
        messagesUsed++;
        updateCounter();

        // Stats tracking — record one entry per user question.
        lastQuestion = text;
        stats.questionTimestamps.push(Date.now());
        stats.perSlide[currentSlideIndex] = (stats.perSlide[currentSlideIndex] || 0) + 1;
        if (isStatsOpen) renderStatsChart();

        // Hide suggestions after first message
        var sugg = document.getElementById('tutor-suggestions');
        if (sugg) sugg.style.display = 'none';

        setLoading(true);

        // Build context: current slide + general course context
        var slideContext = getCurrentSlideContext();
        var fullContext = slideContext + '\n\n--- Contexto geral do curso ---\n' + (config.courseContext || '');

        var payload = {
            message: text,
            courseTopic: config.courseTopic || '',
            courseContext: fullContext,
            history: history,
            sessionId: sessionId,
            // CRITICAL attribution: without these the chat lands in
            // tutor_logs with an empty projectId, which means the admin
            // dashboard aggregation buckets every student question under
            // the SAME empty key and can never enrich it with the
            // matching feedback rows. (Bug 2026-06-30 part 2.)
            projectId: config.projectId || '',
            companyId: config.companyId || ''
        };

        fetch(config.apiUrl + '/api/tutor/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(function(res) {
            if (!res.ok) {
                return res.text().then(function(text) {
                    // Try to extract a human-friendly `detail` from the
                    // backend's JSON error envelope. If parsing fails or
                    // there's no `detail`, fall back to the raw body
                    // (truncated to keep the chat bubble readable).
                    var detail = null;
                    try {
                        var parsed = JSON.parse(text);
                        if (parsed && typeof parsed.detail === 'string') {
                            detail = parsed.detail;
                        }
                    } catch (e) { /* ignore */ }
                    var err = new Error(detail || ('HTTP ' + res.status + ': ' + text.substring(0, 200)));
                    err.status = res.status;
                    err.friendly = !!detail;
                    throw err;
                });
            }
            return res.json();
        })
        .then(function(data) {
            setLoading(false);
            if (data.response) {
                appendMessage('assistant', data.response);
                history.push({ role: 'assistant', content: data.response });
            }
            if (data.limitReached) {
                var input = document.getElementById('tutor-input');
                if (input) { input.disabled = true; input.placeholder = 'Limite de mensagens atingido'; }
                var btn = document.getElementById('tutor-send');
                if (btn) btn.disabled = true;
            }
            if (data.messagesUsed) messagesUsed = data.messagesUsed;
            updateCounter();
        })
        .catch(function(err) {
            setLoading(false);
            // When the backend already returned a friendly message
            // (status 429/503 with text in `detail`), show it verbatim.
            // Otherwise wrap the technical error in a generic apology.
            var errorMsg;
            if (err && err.friendly) {
                errorMsg = err.message;
            } else {
                errorMsg = 'Desculpe, ocorreu um erro ao conectar com o tutor.';
                if (err && err.message) errorMsg += ' (' + err.message + ')';
            }
            appendMessage('assistant', errorMsg);
            console.error('Tutor error:', err, 'API URL:', config.apiUrl);
        });
    }

    function sendSuggestion(btn) {
        var input = document.getElementById('tutor-input');
        if (input) {
            input.value = btn.textContent;
            send();
        }
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(text));
        return div.innerHTML;
    }

    function formatMarkdown(text) {
        if (!text) return '';
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n- /g, '</p><ul><li>')
            .replace(/\n\d+\. /g, '</p><ol><li>')
            .replace(/\n/g, '<br>')
            .replace(/^/, '<p>')
            .replace(/$/, '</p>');
    }

    return {
        init: init,
        toggle: togglePanel,
        toggleMaximize: toggleMaximize,
        toggleStats: toggleStats,
        send: send,
        sendSuggestion: sendSuggestion,
        copyMessage: copyMessage,
        rateMessage: rateMessage,
        onSlideChange: onSlideChange,
        changeFontSize: changeFontSize,
        setContrast: setContrast
    };
})();
