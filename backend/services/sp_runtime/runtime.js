(function(){
  var SECTIONS = __SECTIONS_INDEX__;
  var SCORM_MODE = __SCORM_MODE__;
  var state = {
    currentIndex: 0,
    unlocked: {0: true},
    completed: {},
    quizScores: {},
    interactionIdx: 0,
  };

  function $(sel, root){ return (root||document).querySelector(sel); }
  function $$(sel, root){ return Array.prototype.slice.call((root||document).querySelectorAll(sel)); }

  // --- SCORM helpers (no-op when SCORM_MODE=false or window.SCORM missing) ---
  function scormSaveState(){
    if (!SCORM_MODE || !window.SCORM || !window.SCORM.api) return;
    try {
      window.SCORM.saveSuspend({
        unlocked: state.unlocked,
        completed: state.completed,
        quizScores: state.quizScores,
        currentIndex: state.currentIndex,
      });
      window.SCORM.setLocation(String(state.currentIndex));
      window.SCORM.commit();
    } catch (e) {}
  }
  function scormReportQuiz(quizId, response, correct, qIdx, qText){
    if (!SCORM_MODE || !window.SCORM || !window.SCORM.api) return;
    try {
      window.SCORM.recordInteraction(quizId + ':q' + qIdx, qText, response, correct);
    } catch (e) {}
  }
  function scormUpdateScore(){
    if (!SCORM_MODE || !window.SCORM || !window.SCORM.api) return;
    var totalCorrect = 0, totalQuestions = 0;
    Object.keys(state.quizScores).forEach(function(k){
      totalCorrect += state.quizScores[k].correct;
      totalQuestions += state.quizScores[k].total;
    });
    var raw = totalQuestions > 0 ? Math.round((totalCorrect/totalQuestions)*100) : 0;
    try { window.SCORM.setScore(raw, 100, 0); } catch (e) {}
  }
  function scormMarkComplete(){
    if (!SCORM_MODE || !window.SCORM || !window.SCORM.api) return;
    var allUnlocked = Object.keys(state.unlocked).length >= (SECTIONS.length + 1);
    var quizzesPassed = Object.keys(state.quizScores).every(function(k){
      return state.quizScores[k].pct >= 80;
    });
    var passed = allUnlocked && (Object.keys(state.quizScores).length === 0 || quizzesPassed);
    try {
      window.SCORM.complete(passed);
      window.SCORM.commit();
    } catch (e) {}
  }
  function scormRestoreState(){
    if (!SCORM_MODE || !window.SCORM || !window.SCORM.api) return false;
    try {
      var data = window.SCORM.getSuspend();
      if (!data) return false;
      Object.keys(data.unlocked || {}).forEach(function(k){
        var idx = parseInt(k, 10);
        if (!isNaN(idx)) {
          state.unlocked[idx] = true;
          var sec = $('.sp-section[data-index="'+idx+'"]');
          if (sec) { sec.removeAttribute('data-locked'); sec.classList.add('unlocked'); }
        }
      });
      state.completed = data.completed || {};
      state.quizScores = data.quizScores || {};
      // Mark interactives data-completed=true based on sections that were completed
      Object.keys(state.completed).forEach(function(k){
        var sec = $('.sp-section[data-index="'+k+'"]');
        if (!sec) return;
        $$('[data-required="true"]', sec).forEach(function(el){
          el.dataset.completed = 'true';
        });
      });
      var resumeIdx = data.currentIndex != null ? parseInt(data.currentIndex, 10) : 0;
      if (!isNaN(resumeIdx) && state.unlocked[resumeIdx]) {
        state.currentIndex = resumeIdx;
        setTimeout(function(){
          var sec = $('.sp-section[data-index="'+resumeIdx+'"]');
          if (sec) sec.scrollIntoView({behavior:'instant', block:'start'});
        }, 100);
      }
      return true;
    } catch (e) { return false; }
  }

  function updateProgress(){
    var unlockedCount = Object.keys(state.unlocked).length;
    var pct = Math.min(100, Math.round((unlockedCount-1) / Math.max(1, SECTIONS.length) * 100));
    if (state.currentIndex >= SECTIONS.length) pct = 100;
    var fill = $('.sp-progress-fill');
    if (fill) fill.style.width = pct + '%';
  }

  function buildDrawer(){
    var ul = $('.sp-drawer-list');
    if (!ul) return;
    ul.innerHTML = '';
    SECTIONS.forEach(function(item){
      var li = document.createElement('li');
      li.dataset.index = item.index;
      li.textContent = item.title;
      li.dataset.testid = 'sp-drawer-item-' + item.index;
      if (state.unlocked[item.index]) li.classList.add('unlocked');
      else li.classList.add('locked');
      if (state.completed[item.index]) li.classList.add('completed');
      if (state.currentIndex === item.index) li.classList.add('active');
      li.addEventListener('click', function(){
        if (!state.unlocked[item.index]) return;
        SP.gotoSection(item.index);
      });
      ul.appendChild(li);
    });
  }

  function unlockSection(idx){
    state.unlocked[idx] = true;
    var sec = $('.sp-section[data-index="'+idx+'"]');
    if (sec){
      sec.removeAttribute('data-locked');
      sec.classList.add('unlocked');
      // If this section has a timeline, start it now (it might already be in
      // viewport and the IntersectionObserver may not re-fire since intersectionRatio
      // didn't change — only data-locked did).
      if (sec.querySelector('.sp-timeline-gate')) {
        setTimeout(function(){ startSectionTimeline(sec); }, 200);
      }
    }
    buildDrawer();
    updateProgress();
    scormSaveState();
  }

  function getCurrentSection(){
    return $('.sp-section[data-index="'+state.currentIndex+'"]');
  }

  function translateCurrentSection(){
    var item = SECTIONS.filter(function(section){
      return section.index === state.currentIndex;
    })[0];
    if (!item || !item.librasScript || typeof window.scormifyTranslateLibras !== 'function') return;
    window.scormifyTranslateLibras(item.librasScript);
  }

  function isSectionComplete(idx){
    var sec = $('.sp-section[data-index="'+idx+'"]');
    if (!sec) return false;
    var pending = $$('[data-required="true"]', sec).filter(function(el){
      return el.dataset.completed !== 'true';
    });
    return pending.length === 0;
  }

  function updateNextButton(){
    var btn = $('.sp-next-btn');
    if (!btn) return;
    var idx = state.currentIndex;
    if (idx >= SECTIONS.length){ btn.hidden = true; return; }
    if (isSectionComplete(idx)){
      btn.hidden = false;
    } else {
      btn.hidden = true;
    }
  }

  // Detect which section is currently in viewport (for drawer "active" + next button gating)
  function detectActiveSection(){
    var sections = $$('.sp-section[data-index]');
    var midline = window.innerHeight * 0.4 + window.scrollY;
    var current = state.currentIndex;
    sections.forEach(function(sec){
      var top = sec.offsetTop;
      var bottom = top + sec.offsetHeight;
      if (top <= midline && bottom > midline){
        var idx = parseInt(sec.dataset.index, 10);
        if (idx !== current && state.unlocked[idx]){
          state.currentIndex = idx;
          buildDrawer();
          translateCurrentSection();
          // Re-fire the zoom animation when the section comes into focus
          // (so the user sees the magnify each time they advance, not just
          // on initial page load).
          if (sec.hasAttribute('data-zoom-scale') && typeof window.__triggerZoom === 'function') {
            window.__triggerZoom(sec);
          }
        }
      }
    });
    updateNextButton();
  }

  // ---- public API
  window.SP = {
    markPlayed: function(el){
      if (!el) return;
      el.dataset.completed = 'true';
      this.checkSectionCompletion(el);
    },
    markClicked: function(el){
      if (!el) return;
      el.dataset.completed = 'true';
      this.checkSectionCompletion(el);
    },
    checkSectionCompletion: function(el){
      var sec = el.closest('.sp-section');
      if (!sec) return;
      var idx = parseInt(sec.dataset.index, 10);
      if (isSectionComplete(idx)){
        state.completed[idx] = true;
        buildDrawer();
        updateNextButton();
        scormSaveState();
      }
    },
    advance: function(){
      var idx = state.currentIndex;
      var nextIdx = idx + 1;
      // If end-card section
      if (nextIdx > SECTIONS.length){ return; }
      state.currentIndex = nextIdx;          // update BEFORE unlockSection so SCORM saves the new location
      unlockSection(nextIdx);
      var nextSec = $('.sp-section[data-index="'+nextIdx+'"]');
      if (nextSec){ nextSec.scrollIntoView({behavior:'smooth', block:'start'}); }
      translateCurrentSection();
      // when reaching end card, dispatch course-completed + mark SCORM completed
      if (nextIdx >= SECTIONS.length){
        scormMarkComplete();
        try {
          window.dispatchEvent(new CustomEvent('sp:course-completed', {
            detail: { quizScores: state.quizScores }
          }));
        } catch(e){}
        // Gamification: trigger course completion badges + final summary
        try {
          if (window.Gamification && typeof Gamification.onCourseComplete === 'function') {
            Gamification.onCourseComplete();
          }
        } catch(e){}
      }
    },
    gotoSection: function(idx){
      if (!state.unlocked[idx]) return;
      state.currentIndex = idx;
      var sec = $('.sp-section[data-index="'+idx+'"]');
      if (sec){ sec.scrollIntoView({behavior:'smooth', block:'start'}); }
      translateCurrentSection();
      this.toggleDrawer(false);
      buildDrawer();
      updateNextButton();
    },
    toggleDrawer: function(force){
      var d = $('.sp-drawer');
      if (!d) return;
      var isOpen = d.dataset.open === 'true';
      var nextOpen = (typeof force === 'boolean') ? force : !isOpen;
      d.dataset.open = nextOpen ? 'true' : 'false';
      d.setAttribute('aria-hidden', nextOpen ? 'false' : 'true');
    },
    startScenario: function(scenarioEl){
      try {
        var data = JSON.parse(scenarioEl.dataset.scenario || '{}');
      } catch(e) { return; }
      var nodes = data.nodes || [];
      if (!nodes.length) { SP.markClicked(scenarioEl); return; }
      var nodeMap = {};
      nodes.forEach(function(n){ nodeMap[n.id] = n; });
      // Hide intro, show play area
      var intro = scenarioEl.querySelector('.sp-scenario-intro');
      if (intro) intro.hidden = true;
      var play = scenarioEl.querySelector('.sp-scenario-play');
      if (!play) return;
      play.hidden = false;
      play.style.background = '#fff';
      play.style.color = '#0f172a';
      play.style.borderRadius = '8px';
      play.style.padding = '20px';
      play.style.textAlign = 'left';
      var totalPoints = 0;
      var maxPoints = 0;
      var optimalChoices = 0;
      var totalChoices = 0;
      // Compute max possible points (assume optimal at every node)
      nodes.forEach(function(n){
        if (n.choices && n.choices.length) {
          var maxP = Math.max.apply(null, n.choices.map(function(c){ return c.points || 0; }));
          maxPoints += maxP;
        }
      });
      function renderNode(nodeId){
        var n = nodeMap[nodeId];
        if (!n) return;
        var html = '';
        if (n.title) {
          html += '<h4 style="margin:0 0 10px 0;font-size:18px;color:#1e3a8a">' + escapeHtml(n.title) + '</h4>';
        }
        if (n.character_speaking) {
          html += '<div style="font-size:12px;font-weight:700;color:#7c2d12;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">💬 ' + escapeHtml(n.character_speaking) + '</div>';
        }
        if (n.narrative) {
          html += '<div style="font-size:14px;margin-bottom:16px">' + formatScenarioNarrative(n.narrative) + '</div>';
        }
        if (n.is_ending) {
          var endLabel = n.ending_type === 'positive' ? '🎉 Final Positivo' : (n.ending_type === 'negative' ? '⚠️ Final com Aprendizado' : '🏁 Final');
          var endColor = n.ending_type === 'positive' ? '#16a34a' : (n.ending_type === 'negative' ? '#dc2626' : '#2563eb');
          var pct = maxPoints > 0 ? Math.round((totalPoints/maxPoints)*100) : 100;
          html += '<div style="background:' + endColor + ';color:#fff;padding:14px;border-radius:8px;text-align:center;font-weight:700;margin-bottom:10px">'
                + endLabel + ' • Score: ' + totalPoints + '/' + maxPoints + ' (' + pct + '%)'
                + '</div>';
          if (n.score) {
            html += '<div style="font-size:13px;color:#64748b;text-align:center">Avaliação do nó: ' + escapeHtml(String(n.score)) + '</div>';
          }
          html += '<button type="button" class="sp-btn sp-btn-primary" style="margin-top:14px;width:100%" '
                + 'onclick="window.SP.markClicked(this.closest(&quot;.sp-scenario&quot;))">'
                + '✓ Concluir cenário e liberar próxima seção</button>';
          play.innerHTML = html;
          // Track scenario completion stats for SCORM
          state.quizScores[scenarioEl.dataset.interactiveId] = {
            correct: optimalChoices, total: totalChoices, pct: pct
          };
          scormUpdateScore();
          scormSaveState();
          // Gamification: trigger scenario badges + feedback modal
          try {
            if (window.Gamification && typeof Gamification.onScenarioComplete === 'function') {
              var scenarioTitle = (scenarioEl.querySelector('.sp-scenario-title') || {}).textContent || 'Cenário';
              Gamification.onScenarioComplete(pct, scenarioTitle);
            }
          } catch(e){}
        } else if (n.choices && n.choices.length) {
          html += '<div style="font-weight:600;font-size:13px;color:#475569;margin-bottom:10px">Qual sua decisão?</div>';
          html += '<div class="sp-scenario-choices" style="display:flex;flex-direction:column;gap:10px">';
          n.choices.forEach(function(ch, ci){
            html += '<button type="button" class="sp-scenario-choice" data-choice-idx="' + ci + '" '
                  + 'style="text-align:left;padding:14px 16px;border:2px solid #cbd5e1;background:#f8fafc;border-radius:8px;cursor:pointer;font-size:13px;line-height:1.5;color:#0f172a;transition:all .15s">'
                  + '<span style="display:inline-block;background:#1e3a8a;color:#fff;width:22px;height:22px;border-radius:50%;text-align:center;font-weight:700;margin-right:8px;font-size:11px;line-height:22px">' + (ci+1) + '</span>'
                  + escapeHtml(ch.text)
                  + '</button>';
          });
          html += '</div>';
          // Tutor IA hint button — only when AiTutor is loaded (admin toggled enabled)
          if (window.AiTutor) {
            html += '<button type="button" class="sp-scenario-hint" '
                  + 'style="margin-top:14px;display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:rgba(99,102,241,.12);color:#4f46e5;border:1px dashed #818cf8;border-radius:999px;font-size:12px;font-weight:600;cursor:pointer">'
                  + '💡 Pedir dica do Tutor IA</button>';
          }
          play.innerHTML = html;
          // Wire hint button (contextualized prompt for current node)
          var hintBtn = play.querySelector('.sp-scenario-hint');
          if (hintBtn) {
            hintBtn.addEventListener('click', function(){
              try {
                var nodeTitle = n.title || '';
                var narrative = (n.narrative || '').substring(0, 400);
                var choicesText = (n.choices || []).map(function(c, i){ return (i+1) + ') ' + (c.text || ''); }).join(' | ');
                var prompt = 'Estou em um cenário interativo "' + (scenarioEl.querySelector('.sp-scenario-title') || {}).textContent + '"'
                           + (nodeTitle ? ', no nó "' + nodeTitle + '"' : '')
                           + '. Contexto: ' + narrative
                           + '. Minhas opções são: ' + choicesText
                           + '. Pode me ajudar a refletir sobre o que considerar antes de escolher? (não me dê a resposta direta)';
                if (typeof AiTutor.toggle === 'function') AiTutor.toggle();
                var input = document.getElementById('tutor-input');
                if (input) { input.value = prompt; input.focus(); }
              } catch(e) {}
            });
          }
          play.querySelectorAll('.sp-scenario-choice').forEach(function(btn, ci){
            btn.addEventListener('mouseenter', function(){ btn.style.borderColor='#2563eb'; btn.style.background='#eff6ff'; });
            btn.addEventListener('mouseleave', function(){ btn.style.borderColor='#cbd5e1'; btn.style.background='#f8fafc'; });
            btn.addEventListener('click', function(){
              var ch = n.choices[ci];
              totalChoices++;
              if (ch.is_optimal) optimalChoices++;
              totalPoints += (ch.points || 0);
              showFeedback(ch, n);
            });
          });
        } else {
          // Node has no choices and no ending — fallback
          html += '<button type="button" class="sp-btn sp-btn-primary" '
                + 'onclick="window.SP.markClicked(this.closest(&quot;.sp-scenario&quot;))">Encerrar cenário</button>';
          play.innerHTML = html;
        }
      }
      function showFeedback(choice, fromNode){
        var bgColor = choice.is_optimal ? '#dcfce7' : '#fef2f2';
        var borderColor = choice.is_optimal ? '#16a34a' : '#dc2626';
        var textColor = choice.is_optimal ? '#15803d' : '#991b1b';
        var icon = choice.is_optimal ? '✅' : '⚠️';
        var label = choice.is_optimal ? 'Excelente escolha!' : 'Pense bem nas consequências:';
        var html = '<div style="background:' + bgColor + ';border:2px solid ' + borderColor + ';color:' + textColor + ';padding:16px;border-radius:8px;margin-bottom:14px">'
                 + '<div style="font-weight:700;margin-bottom:6px">' + icon + ' ' + label + ' (+' + (choice.points||0) + ' pts)</div>'
                 + '<div style="font-size:13px;line-height:1.5">' + escapeHtml(choice.feedback || '') + '</div>'
                 + '</div>';
        // Proactive Tutor IA button after sub-optimal choice (only if AiTutor loaded)
        var showTutorRescue = !choice.is_optimal && window.AiTutor;
        if (showTutorRescue) {
          html += '<button type="button" class="sp-scenario-rescue" '
                + 'style="width:100%;margin-bottom:12px;padding:10px 14px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;border:0;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px">'
                + '🤖 Quer entender melhor por quê?</button>';
        }
        var nextId = choice.next_node_id;
        if (nextId && nodeMap[nextId]) {
          html += '<button type="button" class="sp-btn sp-btn-primary" style="width:100%" id="sp-scenario-continue">Continuar →</button>';
          play.innerHTML = html;
          wireRescueBtn(choice);
          play.querySelector('#sp-scenario-continue').addEventListener('click', function(){
            renderNode(nextId);
            play.scrollIntoView({behavior:'smooth', block:'nearest'});
          });
        } else {
          // No next node — treat as ending
          var pct = maxPoints > 0 ? Math.round((totalPoints/maxPoints)*100) : 100;
          html += '<div style="background:#2563eb;color:#fff;padding:14px;border-radius:8px;text-align:center;font-weight:700;margin-bottom:10px">'
                + '🏁 Cenário concluído • Score: ' + totalPoints + '/' + maxPoints + ' (' + pct + '%)'
                + '</div>';
          html += '<button type="button" class="sp-btn sp-btn-primary" style="width:100%" '
                + 'onclick="window.SP.markClicked(this.closest(&quot;.sp-scenario&quot;))">'
                + '✓ Liberar próxima seção</button>';
          play.innerHTML = html;
          wireRescueBtn(choice);
          state.quizScores[scenarioEl.dataset.interactiveId] = { correct: optimalChoices, total: totalChoices, pct: pct };
          scormUpdateScore();
          scormSaveState();
          // Gamification: trigger scenario badges + feedback modal (fallback ending — no next_node_id)
          try {
            if (window.Gamification && typeof Gamification.onScenarioComplete === 'function') {
              var scenarioTitle = (scenarioEl.querySelector('.sp-scenario-title') || {}).textContent || 'Cenário';
              Gamification.onScenarioComplete(pct, scenarioTitle);
            }
          } catch(e){}
        }
      }
      function escapeHtml(s){
        return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
      }
      function formatScenarioNarrative(text){
        // Format LLM-generated narrative into readable HTML. The model often
        // emits walls of text with embedded dialogue ("Prezado(a) ...", email
        // replies) without any markup. We split into paragraphs and highlight
        // quoted blocks as styled cards.
        if (!text) return '';
        var t = String(text).replace(/\r\n/g, '\n').trim();
        var paragraphs = t.split(/\n{2,}/).map(function(p){return p.trim();}).filter(Boolean);
        // If we got a single mega-paragraph, try to split on a big quoted chunk
        if (paragraphs.length === 1) {
          var m = paragraphs[0].match(/(['"\u2018\u2019\u201C\u201D])([^'"\u2018\u2019\u201C\u201D]{40,})\1/);
          if (m) {
            var before = paragraphs[0].slice(0, m.index).trim();
            var quote = m[2].trim();
            var after = paragraphs[0].slice(m.index + m[0].length).trim();
            paragraphs = [];
            if (before) paragraphs.push(before);
            paragraphs.push({quoted: quote});
            if (after) paragraphs.push(after);
          }
        } else {
          // Mark paragraphs that are fully wrapped in quotes
          paragraphs = paragraphs.map(function(p){
            if (typeof p !== 'string') return p;
            var f = p.charAt(0), l = p.charAt(p.length - 1);
            if (p.length > 30 && '"\u201C\u2018\''.indexOf(f) !== -1 && '"\u201D\u2019\''.indexOf(l) !== -1) {
              return {quoted: p.slice(1, -1).trim()};
            }
            return p;
          });
        }
        var html = '';
        paragraphs.forEach(function(p){
          if (typeof p === 'object' && p.quoted) {
            html += '<div style="background:rgba(79,70,229,0.08);border-left:3px solid #4f46e5;padding:12px 16px;margin:10px 0;border-radius:4px;font-style:italic;color:#334155;line-height:1.55">'
                  + escapeHtml(p.quoted).replace(/\n/g, '<br>') + '</div>';
          } else {
            html += '<p style="margin:0 0 10px 0;line-height:1.6">' + escapeHtml(p).replace(/\n/g, '<br>') + '</p>';
          }
        });
        return html;
      }
      function wireRescueBtn(choice){
        var btn = play.querySelector('.sp-scenario-rescue');
        if (!btn) return;
        btn.addEventListener('click', function(){
          try {
            var scTitle = (scenarioEl.querySelector('.sp-scenario-title') || {}).textContent || 'cenário';
            var prompt = 'Em um cenário sobre "' + scTitle + '", eu escolhi: "' + (choice.text || '') + '". '
                       + 'O sistema disse que essa não é a melhor escolha. '
                       + (choice.feedback ? 'O feedback foi: "' + choice.feedback + '". ' : '')
                       + 'Pode me ajudar a entender por que essa decisão é problemática e quais princípios eu deveria considerar para escolher melhor da próxima vez?';
            if (typeof AiTutor.toggle === 'function') AiTutor.toggle();
            var input = document.getElementById('tutor-input');
            if (input) { input.value = prompt; input.focus(); }
          } catch(e){}
        });
      }
      // Start at the first node
      renderNode(nodes[0].id);
      play.scrollIntoView({behavior:'smooth', block:'nearest'});
    },
    startQuiz: function(quizEl){
      var qs = JSON.parse(quizEl.dataset.questions || '[]');
      var body = quizEl.querySelector('.sp-quiz-body');
      var startBtn = quizEl.querySelector('.sp-btn-primary');
      if (startBtn) startBtn.style.display = 'none';
      if (!body) return;
      body.hidden = false;
      var html = '<form class="sp-quiz-form">';
      qs.forEach(function(q, qi){
        html += '<fieldset class="sp-quiz-question" data-q-idx="'+qi+'" style="margin-bottom:18px;border:0;padding:0">';
        html += '<legend style="font-weight:600;margin-bottom:10px;font-size:15px">'+(qi+1)+'. '+(q.text||q.question||'')+'</legend>';
        (q.options||[]).forEach(function(opt, oi){
          var optText = (typeof opt === 'string') ? opt : (opt.text || opt.label || '');
          html += '<label class="sp-quiz-opt" data-opt-idx="'+oi+'" style="display:block;padding:8px 12px;margin:4px 0;cursor:pointer;border:2px solid #e2e8f0;border-radius:6px;transition:all .15s">'
                + '<input type="radio" name="q'+qi+'" value="'+oi+'" style="margin-right:8px"> '+optText
                + '</label>';
        });
        if (q.explanation) {
          html += '<div class="sp-quiz-explanation" hidden style="margin-top:8px;padding:10px 14px;border-left:4px solid #2563eb;background:#eff6ff;font-size:13px;color:#1e3a8a"><strong>💡 Explicação:</strong> '+q.explanation+'</div>';
        }
        html += '</fieldset>';
      });
      html += '<button type="button" class="sp-btn sp-btn-primary sp-quiz-submit">Enviar Respostas</button>';
      html += '<div class="sp-quiz-result" style="margin-top:14px;padding:14px;border-radius:8px;font-weight:700;font-size:16px;text-align:center"></div>';
      html += '</form>';
      body.innerHTML = html;
      var submit = body.querySelector('.sp-quiz-submit');
      var result = body.querySelector('.sp-quiz-result');
      submit.addEventListener('click', function(){
        var correct = 0;
        qs.forEach(function(q, qi){
          var selRadio = body.querySelector('input[name="q'+qi+'"]:checked');
          var fieldset = body.querySelector('.sp-quiz-question[data-q-idx="'+qi+'"]');
          var labels = fieldset.querySelectorAll('.sp-quiz-opt');
          var pickedIdx = selRadio ? parseInt(selRadio.value, 10) : -1;
          var qCorrectIdx = -1;
          (q.options||[]).forEach(function(opt, oi){
            var isThisCorrect = (typeof opt === 'object' && opt && opt.correct) || oi === q.correctAnswer || oi === q.correctIndex;
            if (isThisCorrect) qCorrectIdx = oi;
          });
          // Visual feedback per option
          labels.forEach(function(lbl, oi){
            lbl.style.cursor = 'default';
            var input = lbl.querySelector('input');
            if (input) input.disabled = true;
            if (oi === qCorrectIdx) {
              // The correct answer — always green
              lbl.style.borderColor = '#16a34a';
              lbl.style.background = '#f0fdf4';
              lbl.style.color = '#15803d';
              lbl.style.fontWeight = '600';
              lbl.innerHTML += ' <span style="color:#16a34a;font-weight:700;margin-left:6px">✓ Correta</span>';
            } else if (oi === pickedIdx) {
              // Picked but wrong — red
              lbl.style.borderColor = '#dc2626';
              lbl.style.background = '#fef2f2';
              lbl.style.color = '#991b1b';
              lbl.innerHTML += ' <span style="color:#dc2626;font-weight:700;margin-left:6px">✗ Sua resposta</span>';
            } else {
              lbl.style.opacity = '0.55';
            }
          });
          // Show explanation if available
          var exp = fieldset.querySelector('.sp-quiz-explanation');
          if (exp) exp.hidden = false;
          var isCorrect = (pickedIdx === qCorrectIdx);
          if (isCorrect) correct++;
          // Tutor IA rescue: if wrong answer + AiTutor loaded, offer detailed explanation per question
          if (!isCorrect && window.AiTutor) {
            var tutorBtn = document.createElement('button');
            tutorBtn.type = 'button';
            tutorBtn.className = 'sp-quiz-tutor';
            tutorBtn.innerHTML = '🤖 Pedir explicação detalhada ao Tutor IA';
            tutorBtn.style.cssText = 'margin-top:10px;padding:8px 14px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;border:0;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:6px';
            tutorBtn.addEventListener('click', function(){
              try {
                var qLabel = (q.text || q.question || '').substring(0, 400);
                var pickedText = (q.options && q.options[pickedIdx]) ? (typeof q.options[pickedIdx] === 'object' ? q.options[pickedIdx].text : q.options[pickedIdx]) : '(em branco)';
                var correctText = (q.options && q.options[qCorrectIdx]) ? (typeof q.options[qCorrectIdx] === 'object' ? q.options[qCorrectIdx].text : q.options[qCorrectIdx]) : '';
                var prompt = 'Em um quiz, a pergunta foi: "' + qLabel + '". '
                           + 'Eu respondi: "' + pickedText + '" (errei). '
                           + 'A resposta correta era: "' + correctText + '". '
                           + (q.explanation ? 'A explicação curta diz: "' + q.explanation + '". ' : '')
                           + 'Pode me explicar de forma mais detalhada por que minha resposta está incorreta e o raciocínio para chegar na resposta certa?';
                if (typeof AiTutor.toggle === 'function') AiTutor.toggle();
                var input = document.getElementById('tutor-input');
                if (input) { input.value = prompt; input.focus(); }
              } catch(e){}
            });
            fieldset.appendChild(tutorBtn);
          }
          // SCORM cmi.interactions tracking per question
          var qText = (q.text || q.question || '').substring(0, 250);
          scormReportQuiz(quizEl.dataset.interactiveId, String(pickedIdx), isCorrect, qi, qText);
        });
        var total = qs.length || 1;
        var pct = Math.round((correct/total)*100);
        state.quizScores[quizEl.dataset.interactiveId] = { correct: correct, total: total, pct: pct };
        // Final result banner
        var passed = pct >= 80;
        result.textContent = 'Você acertou ' + correct + ' de ' + total + ' (' + pct + '%) — ' +
          (passed ? '🎉 Aprovado!' : 'Revise as questões em vermelho');
        result.style.background = passed ? '#dcfce7' : '#fef2f2';
        result.style.color = passed ? '#15803d' : '#991b1b';
        result.style.border = '2px solid ' + (passed ? '#16a34a' : '#dc2626');
        SP.markClicked(quizEl);
        scormUpdateScore();
        scormSaveState();
        // Gamification: trigger quiz badges + feedback modal
        try {
          if (window.Gamification && typeof Gamification.onQuizComplete === 'function') {
            Gamification.onQuizComplete(pct, total, correct);
          }
        } catch(e){}
        submit.disabled = true;
        submit.style.display = 'none';
      });
    }
  };

  // ----- Timeline engine: respects per-element startTime/endTime -----
  // When a section enters viewport, we play through the timeline:
  // each .sp-element-timed gets `.sp-revealed` at its startTime (fade-in)
  // and optionally `.sp-hidden` at its endTime. The synthetic .sp-timeline-gate
  // updates a progress bar and is auto-completed when the timeline finishes.
  var timelinePlayed = {};
  function startSectionTimeline(sec){
    var idx = sec.dataset.index;
    if (timelinePlayed[idx]) return;
    var gate = sec.querySelector('.sp-timeline-gate');
    if (!gate) return;
    timelinePlayed[idx] = true;
    var timed = Array.from(sec.querySelectorAll('.sp-element-timed'));
    if (!timed.length) {
      // Section was marked as having timeline but no timed elements survived render.
      // Just mark the gate as completed.
      SP.markClicked(gate);
      return;
    }
    var totalDuration = parseFloat(gate.dataset.sectionDuration || '0') || 0;
    var startedAt = Date.now();
    timed.forEach(function(el){
      var st = parseFloat(el.dataset.startTime || '0') || 0;
      var et = parseFloat(el.dataset.endTime || '0') || 0;
      // Reveal at startTime (or immediately if 0)
      setTimeout(function(){ el.classList.add('sp-revealed'); }, Math.max(0, st * 1000));
      // Hide at endTime ONLY if defined AND the inner element is NOT a required
      // interactive (otherwise the student can't click to complete the section).
      // Required interactives: buttons, quizzes, scenarios, videos with required play.
      var hasRequiredInside = !!el.querySelector('[data-required="true"]');
      if (et > 0 && et > st && !hasRequiredInside) {
        setTimeout(function(){ el.classList.add('sp-hidden'); }, et * 1000);
      }
    });
    // Update progress bar every 100ms until end
    var bar = gate.querySelector('.sp-timeline-progress-bar');
    var progressTimer = setInterval(function(){
      var elapsed = (Date.now() - startedAt) / 1000;
      var pct = totalDuration > 0 ? Math.min(100, (elapsed / totalDuration) * 100) : 100;
      if (bar) bar.style.width = pct.toFixed(1) + '%';
      if (elapsed >= totalDuration) {
        clearInterval(progressTimer);
        if (bar) bar.style.width = '100%';
        SP.markClicked(gate);
      }
    }, 100);
  }

  function observeTimelines(){
    var sectionsWithTimeline = $$('.sp-section').filter(function(sec){
      return sec.querySelector('.sp-timeline-gate');
    });
    if (!sectionsWithTimeline.length || typeof IntersectionObserver === 'undefined') return;
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(entry){
        if (entry.isIntersecting && entry.intersectionRatio >= 0.4) {
          var sec = entry.target;
          // Only play once unlocked (so the locked overlay doesn't trigger it)
          if (!sec.hasAttribute('data-locked')) {
            startSectionTimeline(sec);
          }
        }
      });
    }, { threshold: [0.4] });
    sectionsWithTimeline.forEach(function(sec){ io.observe(sec); });
  }

  // ---------- Narration (slide.audio[]) — ElevenLabs TTS auto-play ----------
  // Auto-plays the section's narration when the section becomes active (>=40%
  // visible). Pauses all other narrations on transition. Honors a global mute
  // toggle persisted in sessionStorage. NEVER blocks progression — narration
  // is supportive, not gated like the audio interactive elements.
  var NARRATION_MUTE_KEY = 'sp:narration:muted';
  function isNarrationMuted(){
    try { return sessionStorage.getItem(NARRATION_MUTE_KEY) === '1'; } catch(e){ return false; }
  }
  function setNarrationMuted(v){
    try { sessionStorage.setItem(NARRATION_MUTE_KEY, v ? '1' : '0'); } catch(e){}
  }
  function pauseAllNarrations(except){
    $$('.sp-narration').forEach(function(n){
      if (n === except) return;
      n.removeAttribute('data-playing');
      var audios = n.querySelectorAll('.sp-narration-audio');
      audios.forEach(function(a){ try { a.pause(); a.currentTime = 0; } catch(e){} });
    });
  }
  function playNarration(narration){
    if (!narration) return;
    var audios = narration.querySelectorAll('.sp-narration-audio');
    if (!audios.length) return;
    pauseAllNarrations(narration);
    if (isNarrationMuted()) {
      narration.removeAttribute('data-playing');
      return;
    }
    narration.setAttribute('data-playing', 'true');
    // Play the first audio entry; if multiple, chain them sequentially.
    var queue = Array.prototype.slice.call(audios);
    function playNext(){
      var current = queue.shift();
      if (!current) {
        narration.removeAttribute('data-playing');
        return;
      }
      try {
        var vol = parseFloat(current.dataset.volume || '1');
        if (!isNaN(vol)) current.volume = Math.max(0, Math.min(1, vol));
      } catch(e){}
      current.onended = playNext;
      var p = current.play();
      if (p && typeof p.catch === 'function') {
        p.catch(function(){
          // Browser autoplay blocked — leave the play button visible so the
          // user can press it manually. Keep data-playing="false".
          narration.removeAttribute('data-playing');
        });
      }
    }
    playNext();
  }
  function observeNarrations(){
    var narrations = $$('.sp-narration');
    if (!narrations.length || typeof IntersectionObserver === 'undefined') return;
    // Inject mute toggle into the header (only when at least one narration exists).
    var headerEl = $('.sp-progress-bar') || $('header');
    if (headerEl && !$('.sp-narration-mute-toggle')) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'sp-narration-mute-toggle sp-visible';
      btn.setAttribute('data-testid', 'sp-narration-mute');
      btn.dataset.muted = isNarrationMuted() ? 'true' : 'false';
      btn.innerHTML = '<span class="sp-mute-icon">'+(isNarrationMuted()?'🔇':'🔊')+'</span><span>Narração</span>';
      btn.addEventListener('click', function(){
        var nowMuted = !isNarrationMuted();
        setNarrationMuted(nowMuted);
        btn.dataset.muted = nowMuted ? 'true' : 'false';
        btn.querySelector('.sp-mute-icon').textContent = nowMuted ? '🔇' : '🔊';
        if (nowMuted) {
          pauseAllNarrations(null);
        } else {
          // Re-trigger current section's narration if any
          var currentNarration = $('.sp-section[data-index="'+state.currentIndex+'"] .sp-narration');
          if (currentNarration) playNarration(currentNarration);
        }
      });
      // Insert at the end of the header (after progress fill)
      headerEl.appendChild(btn);
    }
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(entry){
        if (entry.isIntersecting && entry.intersectionRatio >= 0.4) {
          var sec = entry.target.closest('.sp-section');
          if (sec && !sec.hasAttribute('data-locked')) {
            playNarration(entry.target);
          }
        } else if (!entry.isIntersecting) {
          // Section scrolled away — pause its narration
          var n = entry.target;
          if (n.hasAttribute('data-playing')) {
            n.removeAttribute('data-playing');
            var audios = n.querySelectorAll('.sp-narration-audio');
            audios.forEach(function(a){ try { a.pause(); } catch(e){} });
          }
        }
      });
    }, { threshold: [0.4] });
    narrations.forEach(function(n){ io.observe(n); });
    // Wire per-section play/restart buttons (manual fallback when autoplay is blocked).
    $$('.sp-narration-btn').forEach(function(btn){
      btn.addEventListener('click', function(ev){
        ev.stopPropagation();
        var narration = btn.closest('.sp-narration');
        if (!narration) return;
        var action = btn.dataset.narrationAction;
        var audios = narration.querySelectorAll('.sp-narration-audio');
        if (action === 'restart') {
          audios.forEach(function(a){ try { a.pause(); a.currentTime = 0; } catch(e){} });
          playNarration(narration);
        } else if (action === 'toggle') {
          if (narration.hasAttribute('data-playing')) {
            audios.forEach(function(a){ try { a.pause(); } catch(e){} });
            narration.removeAttribute('data-playing');
          } else {
            playNarration(narration);
          }
        }
      });
    });
  }
  // ---------- end narration runtime ----------

  // ---------- Fullscreen / kiosk mode ----------
  // Press F11 or click the fullscreen button to toggle. State persists in
  // sessionStorage so the user keeps kiosk mode across in-page navigation.
  // The header auto-hides after 2.5s of mouse inactivity for true cinema feel.
  var FULLSCREEN_KEY = 'sp:fullscreen';
  var headerIdleTimer = null;
  function isInBrowserFullscreen(){
    return !!(document.fullscreenElement || document.webkitFullscreenElement
              || document.mozFullScreenElement || document.msFullscreenElement);
  }
  function requestBrowserFullscreen(){
    var el = document.documentElement;
    var fn = el.requestFullscreen || el.webkitRequestFullscreen
             || el.mozRequestFullScreen || el.msRequestFullscreen;
    if (fn) {
      try { fn.call(el); } catch(e){}
    }
  }
  function exitBrowserFullscreen(){
    var fn = document.exitFullscreen || document.webkitExitFullscreen
             || document.mozCancelFullScreen || document.msExitFullscreen;
    if (fn) {
      try { fn.call(document); } catch(e){}
    }
  }
  function setFullscreenMode(active){
    document.body.dataset.fullscreen = active ? 'true' : 'false';
    try { sessionStorage.setItem(FULLSCREEN_KEY, active ? '1' : '0'); } catch(e){}
    if (active) {
      requestBrowserFullscreen();
      scheduleHeaderAutoHide();
    } else {
      if (isInBrowserFullscreen()) exitBrowserFullscreen();
      var hdr = $('.sp-header');
      if (hdr) hdr.classList.remove('sp-header-hidden');
      if (headerIdleTimer) { clearTimeout(headerIdleTimer); headerIdleTimer = null; }
    }
  }
  function scheduleHeaderAutoHide(){
    if (headerIdleTimer) clearTimeout(headerIdleTimer);
    var hdr = $('.sp-header');
    if (!hdr) return;
    hdr.classList.remove('sp-header-hidden');
    headerIdleTimer = setTimeout(function(){
      if (document.body.dataset.fullscreen === 'true') {
        hdr.classList.add('sp-header-hidden');
      }
    }, 2500);
  }
  function setupFullscreen(){
    var btn = $('.sp-fullscreen-btn');
    if (!btn) return;
    btn.addEventListener('click', function(){
      var nowActive = document.body.dataset.fullscreen !== 'true';
      setFullscreenMode(nowActive);
    });
    // Keyboard: F11 or "f" toggles. Esc is already handled by the browser.
    document.addEventListener('keydown', function(ev){
      if (ev.key === 'F11' || (ev.key === 'f' && !ev.ctrlKey && !ev.metaKey
                                && !ev.altKey && !/INPUT|TEXTAREA|SELECT/.test(ev.target.tagName||''))) {
        ev.preventDefault();
        var nowActive = document.body.dataset.fullscreen !== 'true';
        setFullscreenMode(nowActive);
      }
    });
    // Sync our flag when user exits fullscreen via Esc / browser chrome
    ['fullscreenchange','webkitfullscreenchange','mozfullscreenchange','MSFullscreenChange']
      .forEach(function(ev){
        document.addEventListener(ev, function(){
          if (!isInBrowserFullscreen() && document.body.dataset.fullscreen === 'true') {
            // User pressed Esc — sync our internal flag too
            document.body.dataset.fullscreen = 'false';
            try { sessionStorage.setItem(FULLSCREEN_KEY, '0'); } catch(e){}
            var hdr = $('.sp-header');
            if (hdr) hdr.classList.remove('sp-header-hidden');
            if (headerIdleTimer) { clearTimeout(headerIdleTimer); headerIdleTimer = null; }
          }
        });
      });
    // Show header again on mouse movement; reschedule auto-hide
    document.addEventListener('mousemove', function(){
      if (document.body.dataset.fullscreen === 'true') scheduleHeaderAutoHide();
    });
    // Restore state if user already had kiosk mode active (only auto-toggle
    // CSS — we cannot programmatically request fullscreen without a user
    // gesture, so we wait for the user to click again)
    try {
      if (sessionStorage.getItem(FULLSCREEN_KEY) === '1') {
        document.body.dataset.fullscreen = 'true';
      }
    } catch(e){}
  }
  // ---------- end fullscreen runtime ----------

  // ---------- SFX (one-shot section-enter effects) ----------
  var sfxPlayedSections = new Set();
  function playSfxForSection(sectionIdx){
    if (sfxPlayedSections.has(sectionIdx)) return;
    sfxPlayedSections.add(sectionIdx);
    var sfx = document.querySelector('[data-sfx-section="'+sectionIdx+'"]');
    if (!sfx) return;
    var audios = sfx.querySelectorAll('.sp-sfx-audio');
    audios.forEach(function(a){
      try {
        var vol = parseFloat(a.dataset.volume || '0.6');
        if (!isNaN(vol)) a.volume = Math.max(0, Math.min(1, vol));
        var p = a.play();
        if (p && typeof p.catch === 'function') { p.catch(function(){}); }
      } catch(e){}
    });
  }
  function observeSfx(){
    var sfxNodes = $$('.sp-sfx');
    if (!sfxNodes.length || typeof IntersectionObserver === 'undefined') return;
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(entry){
        if (entry.isIntersecting && entry.intersectionRatio >= 0.4) {
          var sec = entry.target.closest('.sp-section');
          if (sec && !sec.hasAttribute('data-locked')) {
            var idx = parseInt(entry.target.dataset.sfxSection, 10);
            if (!isNaN(idx)) playSfxForSection(idx);
          }
        }
      });
    }, { threshold: [0.4] });
    sfxNodes.forEach(function(n){ io.observe(n); });
  }
  // ---------- end SFX runtime ----------

  // ---------- Background Music (type="background" ambient loop) ----------
  var BG_MUSIC_MUTE_KEY = 'sp:bgmusic:muted';
  function isBgMusicMuted(){
    try { return sessionStorage.getItem(BG_MUSIC_MUTE_KEY) === '1'; } catch(e){ return false; }
  }
  function setBgMusicMuted(v){
    try { sessionStorage.setItem(BG_MUSIC_MUTE_KEY, v ? '1' : '0'); } catch(e){}
  }
  function setupBgMusic(){
    var audio = document.getElementById('sp-bg-music');
    var btn = $('.sp-bg-music-toggle');
    if (!audio || !btn) return;
    try {
      var vol = parseFloat(audio.dataset.volume || '0.2');
      if (!isNaN(vol)) audio.volume = Math.max(0, Math.min(1, vol));
    } catch(e){}
    function refreshBtn(){
      var muted = isBgMusicMuted();
      btn.dataset.muted = muted ? 'true' : 'false';
      var icon = btn.querySelector('.sp-bg-music-icon');
      if (icon) icon.textContent = muted ? '🔇' : '🎵';
    }
    refreshBtn();
    // Start on first user interaction (browser autoplay policy) — unless muted
    var started = false;
    function tryStart(){
      if (started || isBgMusicMuted()) return;
      var p = audio.play();
      if (p && typeof p.catch === 'function') {
        p.then(function(){ started = true; }).catch(function(){});
      } else { started = true; }
    }
    ['click','keydown','touchstart'].forEach(function(ev){
      document.addEventListener(ev, function once(){
        tryStart();
      }, { once: true, passive: true });
    });
    btn.addEventListener('click', function(ev){
      ev.stopPropagation();
      var nowMuted = !isBgMusicMuted();
      setBgMusicMuted(nowMuted);
      refreshBtn();
      if (nowMuted) {
        try { audio.pause(); } catch(e){}
      } else {
        tryStart();
      }
    });
  }
  // ---------- end background music runtime ----------

  document.addEventListener('DOMContentLoaded', function(){
    if (SCORM_MODE && window.SCORM) {
      try { window.SCORM.init(); } catch(e) {}
      scormRestoreState();
    }
    buildDrawer();
    updateProgress();
    updateNextButton();
    translateCurrentSection();
    observeTimelines();
    observeNarrations();
    observeSfx();
    setupBgMusic();
    setupFullscreen();
    // Quizzes are content, not launch dialogs. Reveal their questions on the
    // initial paint so learners do not spend an extra click on every quiz.
    document.querySelectorAll('.sp-quiz[data-autostart="true"]').forEach(function(quiz){
      try { SP.startQuiz(quiz); } catch(e) {}
    });
    window.addEventListener('scroll', detectActiveSection, {passive:true});
    document.addEventListener('click', function(){ setTimeout(updateNextButton, 50); }, true);

    // Zoom-on-hotspot animation for Tutorial Agent imports.
    // Each <section data-zoom-scale="..."> has a `.sp-zoom-stage` child
    // that holds the bg image + hotspot. We animate `transform: scale(N)`
    // anchored at (fx%, fy%) on the stage so the section title and body
    // strip stay anchored while the background magnifies.
    function triggerZoom(sec) {
      var stage = sec.querySelector('.sp-zoom-stage') || sec.querySelector('.sp-section-inner');
      if (!stage || sec.__zoomActive) return;
      sec.__zoomActive = true;
      var scale = parseFloat(sec.getAttribute('data-zoom-scale') || '1');
      if (!scale || scale <= 1) { sec.__zoomActive = false; return; }
      var fx = parseFloat(sec.getAttribute('data-zoom-fx') || '50');
      var fy = parseFloat(sec.getAttribute('data-zoom-fy') || '50');
      var intro = parseInt(sec.getAttribute('data-zoom-intro') || '800', 10);
      var hold = parseInt(sec.getAttribute('data-zoom-hold') || '2400', 10);
      var outro = parseInt(sec.getAttribute('data-zoom-outro') || '600', 10);
      stage.style.transformOrigin = fx + '% ' + fy + '%';
      stage.style.transition = 'none';
      stage.style.transform = 'scale(1)';
      void stage.offsetWidth;
      stage.style.transition = 'transform ' + intro + 'ms cubic-bezier(.2,.8,.2,1)';
      stage.style.transform = 'scale(' + scale + ')';
      setTimeout(function(){
        stage.style.transition = 'transform ' + outro + 'ms cubic-bezier(.4,0,.2,1)';
        stage.style.transform = 'scale(1)';
        setTimeout(function(){ sec.__zoomActive = false; }, outro + 100);
      }, intro + hold);
    }
    // Expose so detectActiveSection can call into it when a section
    // becomes the currently-focused one.
    window.__triggerZoom = triggerZoom;

    var zoomSections = document.querySelectorAll('section[data-zoom-scale]');
    if (zoomSections.length && typeof IntersectionObserver !== 'undefined') {
      var zoomIO = new IntersectionObserver(function(entries){
        entries.forEach(function(entry){
          if (entry.isIntersecting && entry.intersectionRatio > 0.2) {
            triggerZoom(entry.target);
          }
        });
      }, { threshold: [0, 0.2, 0.5, 1] });
      zoomSections.forEach(function(sec){ zoomIO.observe(sec); });

      // Kick off the first visible zoom immediately on load so users see
      // the magnify effect without having to scroll. IntersectionObserver
      // fires asynchronously and may miss the initial paint on a content
      // already in view.
      setTimeout(function(){
        for (var i = 0; i < zoomSections.length; i++) {
          var s = zoomSections[i];
          if (s.getAttribute('data-locked') === 'true') continue;
          var r = s.getBoundingClientRect();
          if (r.bottom > 0 && r.top < window.innerHeight) {
            triggerZoom(s);
            break;
          }
        }
      }, 400);
    }

    if (SCORM_MODE && window.SCORM) {
      window.addEventListener('beforeunload', function(){
        try { window.SCORM.finish(); } catch(e){}
      });
    }
  });
})();
