/**
 * ScenarioController - Interactive scenario player for SCORM/HTML exports
 * Handles decision-tree navigation, feedback, scoring, and endings.
 */
var ScenarioController = (function() {
    var scenarios = {};

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
        html += '<p style="font-size:' + (fs*0.875) + 'px;color:#cbd5e1;line-height:1.6;margin-bottom:16px;white-space:pre-line;">' + (node.narrative || '') + '</p>';
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
        html += '<p style="font-size:' + (fs*0.875) + 'px;color:#cbd5e1;max-width:400px;line-height:1.6;margin-bottom:16px;">' + (node.narrative || '') + '</p>';
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
        if (typeof CoursePlayer !== 'undefined' && CoursePlayer.onScenarioComplete) {
            CoursePlayer.onScenarioComplete(elementId);
        }
    }

    return {
        startScenario: startScenario,
        selectChoice: selectChoice,
        proceed: proceed
    };
})();
