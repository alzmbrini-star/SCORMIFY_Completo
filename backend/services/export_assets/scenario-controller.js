/**
 * ScenarioController - Interactive scenario player for SCORM/HTML exports
 * Handles decision-tree navigation, feedback, scoring, and endings.
 */
var ScenarioController = (function() {
    var scenarios = {};

    function escapeHtmlSafe(s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // Format the LLM-generated scenario narrative into readable HTML. The
    // model often emits walls of text with embedded dialogue (email replies,
    // quoted conversations). We split on blank lines AND extract quoted
    // blocks into highlighted cards so dialogue pops visually.
    function formatNarrative(text, fs) {
        if (!text) return '';
        var t = String(text).replace(/\r\n/g, '\n').trim();
        var paragraphs = t.split(/\n{2,}/).map(function(p) { return p.trim(); }).filter(Boolean);
        // Single mega-paragraph: try to split around a long quoted chunk
        if (paragraphs.length === 1) {
            var m = paragraphs[0].match(/(['"\u2018\u2019\u201C\u201D])([^'"\u2018\u2019\u201C\u201D]{40,})\1/);
            if (m) {
                var before = paragraphs[0].slice(0, m.index).trim();
                var quote = m[2].trim();
                var after = paragraphs[0].slice(m.index + m[0].length).trim();
                paragraphs = [];
                if (before) paragraphs.push(before);
                paragraphs.push({ quoted: quote });
                if (after) paragraphs.push(after);
            }
        } else {
            paragraphs = paragraphs.map(function(p) {
                if (typeof p !== 'string') return p;
                var f = p.charAt(0), l = p.charAt(p.length - 1);
                if (p.length > 30 && '"\u201C\u2018\''.indexOf(f) !== -1 && '"\u201D\u2019\''.indexOf(l) !== -1) {
                    return { quoted: p.slice(1, -1).trim() };
                }
                return p;
            });
        }
        var html = '';
        paragraphs.forEach(function(p) {
            if (typeof p === 'object' && p.quoted) {
                html += '<div style="background:rgba(99,102,241,0.15);border-left:3px solid #6366f1;padding:10px 14px;margin:8px 0;border-radius:4px;font-style:italic;color:#cbd5e1;line-height:1.55;font-size:' + (fs * 0.85) + 'px;text-align:left">' + escapeHtmlSafe(p.quoted).replace(/\n/g, '<br>') + '</div>';
            } else {
                html += '<p style="margin:0 0 10px 0;line-height:1.6;color:#cbd5e1;font-size:' + (fs * 0.875) + 'px;text-align:left">' + escapeHtmlSafe(p).replace(/\n/g, '<br>') + '</p>';
            }
        });
        return html;
    }

    function startScenario(elementId) {
        var container = document.querySelector('.scenario-player-container[data-element-id="' + elementId + '"]');
        if (!container) { console.warn('[ScenarioController] Container not found:', elementId); return; }
        var data;
        try { data = JSON.parse(container.dataset.scenario || '{}'); } catch(e) { console.error('[ScenarioController] JSON parse error:', e); return; }
        var nodesMap = {};
        (data.nodes || []).forEach(function(n) {
            nodesMap[n.id] = n;
        });
        scenarios[elementId] = {
            data: data,
            nodesMap: nodesMap,
            currentNodeId: data.start_node_id || (data.nodes && data.nodes[0] ? data.nodes[0].id : null),
            history: [],
            optimalCount: 0,
            totalDecisions: 0,
            container: container
        };
        renderNode(elementId);
    }

    function renderNode(elementId) {
        var sc = scenarios[elementId];
        if (!sc) return;
        var node = sc.nodesMap[sc.currentNodeId];
        if (!node) return;
        if (node.is_ending) { renderEnding(elementId, node); return; }
        var fs = sc.data.fontSize || 16;
        var s = fs / 16;

        var html = '<div style="display:flex;flex-direction:column;height:100%;background:linear-gradient(180deg,#0f172a,#1e293b);border-radius:12px;overflow:hidden;">';
        // Header
        html += '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 16px;background:rgba(30,41,59,0.8);border-bottom:1px solid rgba(51,65,85,0.5);">';
        html += '<div style="display:flex;align-items:center;gap:8px;"><svg style="width:16px;height:16px;color:#22d3ee;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6 3v12"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>';
        html += '<span style="font-size:' + (fs*0.75) + 'px;color:#cbd5e1;font-weight:500;">' + (sc.data.title || 'Cenário') + '</span></div>';
        html += '<div style="display:flex;align-items:center;gap:12px;">';
        html += '<span style="font-size:' + (fs*0.75) + 'px;color:#64748b;">Cena ' + (sc.history.length + 1) + '</span>';
        html += '<span style="font-size:' + (fs*0.75) + 'px;color:#fbbf24;">★ ' + sc.optimalCount + '/' + sc.totalDecisions + '</span>';
        html += '</div></div>';
        // Content
        html += '<div style="flex:1;overflow-y:auto;padding:16px;">';
        if (node.character_speaking) {
            html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">';
            html += '<div style="width:' + (28*s) + 'px;height:' + (28*s) + 'px;border-radius:50%;background:linear-gradient(135deg,#06b6d4,#2563eb);display:flex;align-items:center;justify-content:center;flex-shrink:0;">';
            html += '<svg style="width:' + (14*s) + 'px;height:' + (14*s) + 'px;color:#fff;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></div>';
            html += '<span style="font-size:' + (fs*0.75) + 'px;font-weight:500;color:#67e8f9;">' + node.character_speaking + '</span></div>';
        }
        html += '<h3 style="font-size:' + fs + 'px;font-weight:600;color:#fff;margin-bottom:8px;">' + (node.title || '') + '</h3>';
        html += '<div style="margin-bottom:16px">' + formatNarrative(node.narrative || '', fs) + '</div>';
        // Choices
        if (node.choices && node.choices.length > 0) {
            html += '<p style="font-size:' + (fs*0.75) + 'px;color:#64748b;margin-bottom:8px;font-weight:500;">O que você faria?</p>';
            node.choices.forEach(function(choice, idx) {
                var letter = String.fromCharCode(65 + idx);
                html += '<button onclick="ScenarioController.selectChoice(\'' + elementId + '\',\'' + choice.id + '\')" style="display:flex;align-items:center;gap:8px;width:100%;text-align:left;padding:10px 12px;margin-bottom:8px;border-radius:8px;border:1px solid rgba(51,65,85,0.5);background:rgba(30,41,59,0.5);color:#e2e8f0;font-size:' + (fs*0.875) + 'px;cursor:pointer;" onmouseover="this.style.background=\'rgba(51,65,85,0.7)\';this.style.borderColor=\'rgba(34,211,238,0.4)\';" onmouseout="this.style.background=\'rgba(30,41,59,0.5)\';this.style.borderColor=\'rgba(51,65,85,0.5)\';">';
                html += '<span style="width:' + (24*s) + 'px;height:' + (24*s) + 'px;border-radius:50%;background:#334155;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:' + (fs*0.7) + 'px;font-weight:bold;color:#94a3b8;">' + letter + '</span>';
                html += '<span style="flex:1;">' + (choice.text || '') + '</span>';
                html += '<span style="color:#475569;font-size:16px;">›</span></button>';
            });
            // Tutor IA hint button — only when AiTutor is loaded (admin toggled enabled)
            if (typeof window !== 'undefined' && window.AiTutor) {
                html += '<button onclick="ScenarioController.askTutor(\'' + elementId + '\',\'hint\',\'' + sc.currentNodeId + '\')" '
                      + 'style="margin-top:8px;display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:rgba(99,102,241,0.15);color:#a5b4fc;border:1px dashed #6366f1;border-radius:999px;font-size:' + (fs*0.75) + 'px;font-weight:600;cursor:pointer;">'
                      + '💡 Pedir dica do Tutor IA</button>';
            }
        }
        html += '</div></div>';
        sc.container.innerHTML = html;
    }

    function selectChoice(elementId, choiceId) {
        var sc = scenarios[elementId];
        if (!sc) return;
        var node = sc.nodesMap[sc.currentNodeId];
        if (!node) return;
        var choice = node.choices.find(function(c) { return c.id === choiceId; });
        if (!choice) return;
        
        sc.totalDecisions += 1;
        if (choice.is_optimal) sc.optimalCount += 1;
        renderFeedback(elementId, choice);
    }

    function renderFeedback(elementId, choice) {
        var sc = scenarios[elementId];
        if (!sc) return;
        var fs = sc.data.fontSize || 16;
        var fbColor = choice.is_optimal ? '#10b981' : '#f59e0b';
        var fbBg = choice.is_optimal ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.1)';
        var fbBorder = choice.is_optimal ? 'rgba(16,185,129,0.3)' : 'rgba(245,158,11,0.3)';
        var fbLabel = choice.is_optimal ? 'Excelente escolha!' : 'Considere outras perspectivas';
        var fbIcon = choice.is_optimal ? '✓' : '⚠';

        var html = '<div style="display:flex;flex-direction:column;height:100%;background:linear-gradient(180deg,#0f172a,#1e293b);border-radius:12px;overflow:hidden;padding:16px;">';
        html += '<div style="padding:10px 12px;border-radius:8px;background:rgba(51,65,85,0.4);border:1px solid rgba(51,65,85,0.4);margin-bottom:12px;">';
        html += '<p style="font-size:' + (fs*0.75) + 'px;color:#64748b;margin-bottom:4px;">Sua escolha:</p>';
        html += '<p style="font-size:' + (fs*0.875) + 'px;color:#fff;">' + (choice.text || '') + '</p></div>';
        html += '<div style="padding:10px 12px;border-radius:8px;background:' + fbBg + ';border:1px solid ' + fbBorder + ';margin-bottom:12px;">';
        html += '<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">';
        html += '<span style="color:' + fbColor + ';font-size:' + (fs*0.875) + 'px;">' + fbIcon + '</span>';
        html += '<span style="font-size:' + (fs*0.75) + 'px;font-weight:500;color:' + fbColor + ';">' + fbLabel + '</span>';
        if (choice.points > 0) html += '<span style="margin-left:auto;font-size:' + (fs*0.75) + 'px;color:#fbbf24;">+' + choice.points + ' pts</span>';
        html += '</div>';
        html += '<p style="font-size:' + (fs*0.875) + 'px;color:#cbd5e1;line-height:1.5;">' + (choice.feedback || '') + '</p></div>';
        // Proactive Tutor IA button after sub-optimal choice (only if AiTutor loaded)
        if (!choice.is_optimal && typeof window !== 'undefined' && window.AiTutor) {
            html += '<button onclick="ScenarioController.askTutor(\'' + elementId + '\',\'rescue\',\'' + sc.currentNodeId + '\',\'' + (choice.id || '') + '\')" '
                  + 'style="width:100%;margin-bottom:12px;padding:10px 14px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;border:0;border-radius:8px;font-size:' + (fs*0.875) + 'px;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px;">'
                  + '🤖 Quer entender melhor por quê?</button>';
        }
        html += '<button onclick="ScenarioController.proceed(\'' + elementId + '\',\'' + (choice.next_node_id || '') + '\')" style="width:100%;padding:10px 20px;background:linear-gradient(135deg,#0891b2,#2563eb);color:#fff;border:none;border-radius:8px;font-size:' + fs + 'px;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px;">Continuar →</button>';
        html += '</div>';
        sc.container.innerHTML = html;
    }

    function proceed(elementId, nextNodeId) {
        var sc = scenarios[elementId];
        if (!sc) return;
        sc.history.push(sc.currentNodeId);
        if (nextNodeId && sc.nodesMap[nextNodeId]) {
            sc.currentNodeId = nextNodeId;
            renderNode(elementId);
        } else {
            renderEnding(elementId, sc.nodesMap[sc.currentNodeId] || {});
        }
    }

    function renderEnding(elementId, node) {
        var sc = scenarios[elementId];
        if (!sc) return;
        var fs = sc.data.fontSize || 16;
        
        // Calculate score based on optimal decisions, not points
        // If user made all optimal decisions, score should be 100%
        var calcScore = sc.totalDecisions > 0 
            ? Math.round((sc.optimalCount / sc.totalDecisions) * 100) 
            : 0;
        
        var endColor = calcScore >= 80 ? '#10b981' : calcScore >= 50 ? '#f59e0b' : '#ef4444';
        var endIcon = calcScore >= 80 ? '🏆' : calcScore >= 50 ? '⚠' : '✗';

        var html = '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;background:linear-gradient(180deg,#0f172a,#1e293b);border-radius:12px;padding:24px;text-align:center;">';
        html += '<div style="font-size:' + (fs*3) + 'px;margin-bottom:12px;">' + endIcon + '</div>';
        html += '<h2 style="font-size:' + (fs*1.25) + 'px;font-weight:bold;color:' + endColor + ';margin-bottom:8px;">' + (node.title || 'Fim') + '</h2>';
        html += '<div style="max-width:600px;margin-bottom:16px">' + formatNarrative(node.narrative || '', fs) + '</div>';
        html += '<div style="display:flex;align-items:center;gap:8px;background:rgba(51,65,85,0.5);padding:8px 16px;border-radius:999px;margin-bottom:8px;">';
        html += '<span style="color:#fbbf24;">★</span><span style="color:#fff;font-weight:600;font-size:' + fs + 'px;">Pontuação: ' + calcScore + '%</span></div>';
        html += '<div style="display:flex;flex-direction:column;align-items:center;gap:4px;margin-bottom:16px;">';
        html += '<span style="font-size:' + (fs*0.75) + 'px;color:#94a3b8;">Decisões ideais: ' + sc.optimalCount + ' de ' + sc.totalDecisions + '</span>';
        html += '</div>';
        html += '<button onclick="ScenarioController.startScenario(\'' + elementId + '\')" style="padding:10px 20px;background:transparent;border:1px solid rgba(34,211,238,0.5);color:#22d3ee;border-radius:8px;font-size:' + fs + 'px;cursor:pointer;">↻ Tentar Novamente</button>';
        html += '</div>';
        sc.container.innerHTML = html;
        
        // Report scenario score to SCORM
        if (typeof ScormAPI !== 'undefined') {
            ScormAPI.setScore(calcScore);
            console.log('[ScenarioController] Score sent to SCORM:', calcScore);
        }
        
        // Notify gamification engine
        if (typeof Gamification !== 'undefined') {
            var scenarioTitle = sc.data.title || 'Cenário';
            setTimeout(function() {
                Gamification.onScenarioComplete(calcScore, scenarioTitle);
            }, 500);
        }
        
        // Notify CoursePlayer that this scenario is complete
        // CoursePlayer will check if all quizzes/scenarios are done before setting SCORM complete
        console.log('[ScenarioController] Scenario ended. ElementId:', elementId, 'Score:', calcScore + '%');
        if (typeof CoursePlayer !== 'undefined' && CoursePlayer.onScenarioComplete) {
            CoursePlayer.onScenarioComplete(elementId);
            console.log('[ScenarioController] CoursePlayer.onScenarioComplete called successfully');
        } else {
            console.error('[ScenarioController] CoursePlayer NOT available!', typeof CoursePlayer);
        }
    }

    function askTutor(elementId, mode, nodeId, choiceId) {
        if (typeof window === 'undefined' || !window.AiTutor) return;
        var sc = scenarios[elementId];
        if (!sc) return;
        var node = sc.nodesMap[nodeId];
        if (!node) return;
        var scTitle = sc.data.title || 'cenário';
        var prompt = '';
        if (mode === 'hint') {
            var nodeTitle = node.title || '';
            var narrative = (node.narrative || '').substring(0, 400);
            var choicesText = (node.choices || []).map(function(c, i){ return (i+1) + ') ' + (c.text || ''); }).join(' | ');
            prompt = 'Estou em um cenário interativo "' + scTitle + '"'
                   + (nodeTitle ? ', no nó "' + nodeTitle + '"' : '')
                   + '. Contexto: ' + narrative
                   + '. Minhas opções são: ' + choicesText
                   + '. Pode me ajudar a refletir sobre o que considerar antes de escolher? (não me dê a resposta direta)';
        } else if (mode === 'rescue') {
            var choice = (node.choices || []).find(function(c){ return c.id === choiceId; });
            if (choice) {
                prompt = 'Em um cenário sobre "' + scTitle + '", eu escolhi: "' + (choice.text || '') + '". '
                       + 'O sistema disse que essa não é a melhor escolha. '
                       + (choice.feedback ? 'O feedback foi: "' + choice.feedback + '". ' : '')
                       + 'Pode me ajudar a entender por que essa decisão é problemática e quais princípios eu deveria considerar para escolher melhor da próxima vez?';
            }
        }
        try {
            if (typeof AiTutor.toggle === 'function') AiTutor.toggle();
            var input = document.getElementById('tutor-input');
            if (input) { input.value = prompt; input.focus(); }
        } catch(e) {}
    }

    return {
        startScenario: startScenario,
        selectChoice: selectChoice,
        proceed: proceed,
        askTutor: askTutor
    };
})();
