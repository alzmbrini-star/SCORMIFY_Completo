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
    var currentSlideIndex = 0;
    var slideContexts = [];

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
                '<button class="tutor-close" data-testid="tutor-close-button" onclick="AiTutor.toggle()">&#x2715;</button>' +
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
            }
        }
    }

    function appendMessage(role, text) {
        var container = document.getElementById('tutor-messages');
        if (!container) return;
        var typing = document.getElementById('tutor-typing');
        var div = document.createElement('div');
        div.className = 'tutor-msg ' + role;
        div.innerHTML = role === 'assistant' ? formatMarkdown(text) : escapeHtml(text);
        container.insertBefore(div, typing);
        container.scrollTop = container.scrollHeight;
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
                    throw new Error('HTTP ' + res.status + ': ' + text.substring(0, 200));
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
            var errorMsg = 'Desculpe, ocorreu um erro ao conectar com o tutor.';
            if (err.message) {
                errorMsg += ' (' + err.message + ')';
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
        send: send,
        sendSuggestion: sendSuggestion,
        onSlideChange: onSlideChange
    };
})();
