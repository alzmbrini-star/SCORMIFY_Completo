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
    var currentSlideIndex = 0;
    var slideContexts = [];
    var msgCounter = 0;
    var feedbackStore = {};  // messageId -> 'up' | 'down'

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
                '<div class="tutor-avatar">&#x1F393;</div>' +
                '<div class="tutor-header-info">' +
                    '<h3>' + escapeHtml(tutorName) + '</h3>' +
                    '<p>Assistente do curso</p>' +
                '</div>' +
                '<button class="tutor-maximize" data-testid="tutor-maximize-button" onclick="AiTutor.toggleMaximize()" title="Maximizar">' +
                    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>' +
                '</button>' +
                '<button class="tutor-close" data-testid="tutor-close-button" onclick="AiTutor.toggle()" title="Fechar">&#x2715;</button>' +
            '</div>' +
            '<div class="tutor-slide-indicator" id="tutor-slide-indicator" data-testid="tutor-slide-indicator"></div>' +
            suggestionsHtml +
            '<div class="tutor-messages" id="tutor-messages" data-testid="tutor-messages">' +
                '<div class="tutor-typing" id="tutor-typing"><span></span><span></span><span></span></div>' +
            '</div>' +
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
        // opposite rating switches sides. Feedback is kept only in the
        // session (no backend submit for now — the data-testid hooks let
        // future tooling capture it).
        var previous = feedbackStore[msgId];
        var wrap = document.getElementById(msgId);
        if (!wrap) return;
        var actions = wrap.querySelector('.tutor-msg-actions');
        if (!actions) return;
        var upBtn = actions.querySelector('[data-testid="tutor-msg-thumbs-up"]');
        var downBtn = actions.querySelector('[data-testid="tutor-msg-thumbs-down"]');
        if (upBtn) upBtn.classList.remove('rated');
        if (downBtn) downBtn.classList.remove('rated');

        if (previous === rating) {
            delete feedbackStore[msgId];
        } else {
            feedbackStore[msgId] = rating;
            if (btn) btn.classList.add('rated');
        }
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
            sessionId: sessionId
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
        send: send,
        sendSuggestion: sendSuggestion,
        copyMessage: copyMessage,
        rateMessage: rateMessage,
        onSlideChange: onSlideChange
    };
})();
