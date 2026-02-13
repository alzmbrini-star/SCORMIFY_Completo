/**
 * Quiz Controller - Handles quiz functionality in SCORM package
 */
var QuizController = (function() {
    var quizzes = {};
    var questions = {};
    
    // Shuffle array helper
    function shuffleArray(array) {
        var shuffled = array.slice();
        for (var i = shuffled.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var temp = shuffled[i];
            shuffled[i] = shuffled[j];
            shuffled[j] = temp;
        }
        return shuffled;
    }
    
    return {
        // Initialize with course data
        init: function(courseData) {
            questions = {};
            if (courseData && courseData.questions) {
                courseData.questions.forEach(function(q) {
                    questions[q.id] = q;
                });
            }
        },
        
        // Start a quiz
        startQuiz: function(elementId) {
            var container = document.querySelector('.quiz-player-container[data-element-id="' + elementId + '"]');
            if (!container) {
                console.error('Quiz container not found:', elementId);
                return;
            }
            
            var config = JSON.parse(container.dataset.quizConfig || '{}');
            var questionIds = config.questionIds || [];
            var quizQuestions = questionIds.map(function(id) { return questions[id]; }).filter(Boolean);
            
            if (quizQuestions.length === 0) {
                container.innerHTML = '<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:#fbbf24;"><span style="font-size:48px;">â ï¸</span><p style="margin-left:16px;">Nenhuma questÃ£o encontrada para este quiz</p></div>';
                return;
            }
            
            // Apply shuffle if configured
            if (config.shuffleQuestions !== false) {
                quizQuestions = shuffleArray(quizQuestions);
            }
            
            // Limit to question count
            var count = Math.min(config.questionCount || quizQuestions.length, quizQuestions.length);
            quizQuestions = quizQuestions.slice(0, count);
            
            // Shuffle alternatives if configured
            if (config.shuffleAlternatives !== false) {
                quizQuestions = quizQuestions.map(function(q) {
                    return Object.assign({}, q, { alternatives: shuffleArray(q.alternatives || []) });
                });
            }
            
            // Store quiz state
            quizzes[elementId] = {
                config: config,
                questions: quizQuestions,
                currentIndex: 0,
                answers: [],
                showingFeedback: false
            };
            
            this.renderQuestion(elementId);
        },
        
        // Render current question
        renderQuestion: function(elementId) {
            var quiz = quizzes[elementId];
            if (!quiz) return;
            
            var container = document.querySelector('.quiz-player-container[data-element-id="' + elementId + '"]');
            if (!container) return;
            
            var question = quiz.questions[quiz.currentIndex];
            var total = quiz.questions.length;
            var current = quiz.currentIndex + 1;
            var progress = (current / total) * 100;
            
            // Get font size from config (default 16px)
            var baseFontSize = quiz.config.fontSize || 16;
            var titleFontSize = Math.round(baseFontSize * 0.8125); // 13px at 16
            var questionFontSize = Math.round(baseFontSize * 0.875); // 14px at 16
            var altFontSize = Math.round(baseFontSize * 0.75); // 12px at 16
            var smallFontSize = Math.round(baseFontSize * 0.6875); // 11px at 16
            
            var html = '<style>.quiz-scroll::-webkit-scrollbar{width:4px;height:4px;}.quiz-scroll::-webkit-scrollbar-track{background:transparent;}.quiz-scroll::-webkit-scrollbar-thumb{background:rgba(100,116,139,0.4);border-radius:4px;}.quiz-scroll::-webkit-scrollbar-thumb:hover{background:rgba(100,116,139,0.6);}.quiz-scroll{scrollbar-width:thin;scrollbar-color:rgba(100,116,139,0.4) transparent;}</style>' +
                '<div style="display:flex;flex-direction:column;height:100%;background:#1e293b;color:#fff;font-family:system-ui,-apple-system,sans-serif;">' +
                // Progress header - compact with question type inline
                '<div style="padding:10px 16px 8px;border-bottom:1px solid #334155;">' +
                '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">' +
                '<div style="display:flex;align-items:center;gap:8px;">' +
                '<span style="font-weight:500;font-size:' + titleFontSize + 'px;">' + (quiz.config.title || 'Quiz') + '</span>' +
                '<span style="padding:2px 6px;font-size:9px;border-radius:3px;font-weight:500;' + 
                (question.type === 'true_false' ? 'background:rgba(168,85,247,0.15);color:#a78bfa;' : 'background:rgba(6,182,212,0.15);color:#22d3ee;') + '">' +
                (question.type === 'true_false' ? 'V/F' : 'MÃºltipla') + '</span></div>' +
                '<span style="color:#94a3b8;font-size:' + altFontSize + 'px;">' + current + '/' + total + '</span>' +
                '</div>' +
                '<div style="height:3px;background:#334155;border-radius:2px;overflow:hidden;">' +
                '<div style="height:100%;width:' + progress + '%;background:#06b6d4;transition:width 0.3s;"></div>' +
                '</div></div>' +
                
                // Question content - compact with thin scrollbar
                '<div class="quiz-scroll" style="flex:1;padding:12px 16px;overflow:auto;">' +
                '<h3 style="font-size:' + questionFontSize + 'px;font-weight:600;margin-bottom:12px;color:#f1f5f9;line-height:1.4;">' + question.text + '</h3>' +
                
                // Alternatives in 2x2 grid - smaller
                '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:6px;">';
            
            question.alternatives.forEach(function(alt, idx) {
                var isSelected = quiz.selectedAnswer === alt.id;
                var isCorrect = alt.isCorrect;
                var showingFeedback = quiz.showingFeedback;
                
                var altStyle = 'padding:8px 10px;border-radius:6px;cursor:pointer;display:flex;align-items:center;gap:8px;transition:all 0.2s;text-align:left;width:100%;';
                var circleStyle = 'width:20px;height:20px;min-width:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;';
                var textStyle = 'font-size:' + altFontSize + 'px;line-height:1.3;';
                
                if (showingFeedback) {
                    if (isCorrect) {
                        altStyle += 'background:transparent;border:2px solid #22c55e;';
                        circleStyle += 'background:#22c55e;color:#fff;';
                        textStyle += 'color:#f1f5f9;';
                    } else if (isSelected && !isCorrect) {
                        altStyle += 'background:transparent;border:2px solid #ef4444;';
                        circleStyle += 'background:#ef4444;color:#fff;';
                        textStyle += 'color:#94a3b8;';
                    } else {
                        altStyle += 'background:transparent;border:2px solid #475569;opacity:0.5;';
                        circleStyle += 'background:#475569;color:#94a3b8;';
                        textStyle += 'color:#94a3b8;';
                    }
                } else if (isSelected) {
                    altStyle += 'background:transparent;border:2px solid #06b6d4;';
                    circleStyle += 'background:#06b6d4;color:#fff;';
                    textStyle += 'color:#f1f5f9;';
                } else {
                    altStyle += 'background:transparent;border:2px solid #475569;';
                    circleStyle += 'background:#475569;color:#94a3b8;';
                    textStyle += 'color:#cbd5e1;';
                }
                
                html += '<button style="' + altStyle + '" onclick="QuizController.selectAnswer(\'' + elementId + '\', \'' + alt.id + '\')" ' + (showingFeedback ? 'disabled' : '') + '>' +
                    '<div style="' + circleStyle + '">' + (showingFeedback && isCorrect ? 'â' : (showingFeedback && isSelected && !isCorrect ? 'â' : '')) + '</div>' +
                    '<span style="flex:1;' + textStyle + '">' + alt.text + '</span></button>';
            });
            
            html += '</div>';
            
            // Feedback section - compact
            if (quiz.showingFeedback) {
                var selectedAlt = question.alternatives.find(function(a) { return a.id === quiz.selectedAnswer; });
                var correctAlt = question.alternatives.find(function(a) { return a.isCorrect; });
                var wasCorrect = selectedAlt && selectedAlt.isCorrect;
                
                html += '<div style="margin-top:10px;padding:10px 12px;border-radius:6px;' + 
                    (wasCorrect ? 'background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.25);' : 'background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);') + '">' +
                    '<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">' +
                    '<span style="width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;' + 
                    (wasCorrect ? 'background:#22c55e;color:#fff;' : 'background:#ef4444;color:#fff;') + '">' + (wasCorrect ? 'â' : 'â') + '</span>' +
                    '<span style="font-weight:600;font-size:' + altFontSize + 'px;' + (wasCorrect ? 'color:#22c55e;' : 'color:#ef4444;') + '">' + (wasCorrect ? 'Correto!' : 'Incorreto') + '</span></div>';
                
                if (question.explanation) {
                    html += '<p style="color:#cbd5e1;font-size:' + smallFontSize + 'px;margin:0;line-height:1.4;">' + question.explanation + '</p>';
                }
                if (!wasCorrect && correctAlt) {
                    html += '<p style="color:#94a3b8;margin-top:4px;font-size:' + Math.round(baseFontSize * 0.625) + 'px;">Correta: <span style="color:#22c55e;font-weight:500;">' + correctAlt.text + '</span></p>';
                }
                html += '</div>';
            }
            
            html += '</div>' +
                
                // Action footer - compact
                '<div style="padding:10px 16px;border-top:1px solid #334155;display:flex;justify-content:space-between;align-items:center;background:#1e293b;">' +
                '<button style="padding:6px 12px;background:transparent;border:none;color:#94a3b8;cursor:pointer;font-size:' + altFontSize + 'px;display:flex;align-items:center;gap:4px;" ' + 
                (quiz.currentIndex === 0 || quiz.showingFeedback ? 'disabled style="padding:6px 12px;background:transparent;border:none;color:#94a3b8;opacity:0.4;cursor:not-allowed;font-size:' + altFontSize + 'px;display:flex;align-items:center;gap:4px;"' : '') + 
                ' onclick="QuizController.prevQuestion(\'' + elementId + '\')">â¹ Anterior</button>';
            
            if (quiz.showingFeedback) {
                if (quiz.currentIndex < total - 1) {
                    html += '<button style="padding:8px 16px;background:#475569;color:#fff;border:none;border-radius:6px;font-weight:500;font-size:' + altFontSize + 'px;cursor:pointer;" onclick="QuizController.nextQuestion(\'' + elementId + '\')">PrÃ³xima âº</button>';
                } else {
                    html += '<button style="padding:8px 16px;background:#22c55e;color:#fff;border:none;border-radius:6px;font-weight:500;font-size:' + altFontSize + 'px;cursor:pointer;" onclick="QuizController.showResults(\'' + elementId + '\')">Ver Resultado</button>';
                }
            } else {
                html += '<button style="padding:8px 16px;background:#475569;color:#fff;border:none;border-radius:6px;font-weight:500;font-size:' + altFontSize + 'px;cursor:pointer;' + 
                    (!quiz.selectedAnswer ? 'opacity:0.4;cursor:not-allowed;' : '') + '" ' +
                    (!quiz.selectedAnswer ? 'disabled' : '') + 
                    ' onclick="QuizController.confirmAnswer(\'' + elementId + '\')">Confirmar â</button>';
            }
            
            html += '</div></div>';
            
            container.innerHTML = html;
        },
        
        // Select answer
        selectAnswer: function(elementId, altId) {
            var quiz = quizzes[elementId];
            if (!quiz || quiz.showingFeedback) return;
            
            quiz.selectedAnswer = altId;
            this.renderQuestion(elementId);
        },
        
        // Confirm answer
        confirmAnswer: function(elementId) {
            var quiz = quizzes[elementId];
            if (!quiz || !quiz.selectedAnswer) return;
            
            var question = quiz.questions[quiz.currentIndex];
            var selectedAlt = question.alternatives.find(function(a) { return a.id === quiz.selectedAnswer; });
            
            quiz.answers.push({
                questionId: question.id,
                selectedAlternativeId: quiz.selectedAnswer,
                isCorrect: selectedAlt && selectedAlt.isCorrect
            });
            
            if (quiz.config.showFeedback !== false) {
                quiz.showingFeedback = true;
                this.renderQuestion(elementId);
            } else {
                this.nextQuestion(elementId);
            }
        },
        
        // Next question
        nextQuestion: function(elementId) {
            var quiz = quizzes[elementId];
            if (!quiz) return;
            
            quiz.showingFeedback = false;
            quiz.selectedAnswer = null;
            
            if (quiz.currentIndex < quiz.questions.length - 1) {
                quiz.currentIndex++;
                this.renderQuestion(elementId);
            } else {
                this.showResults(elementId);
            }
        },
        
        // Previous question
        prevQuestion: function(elementId) {
            var quiz = quizzes[elementId];
            if (!quiz || quiz.currentIndex === 0 || quiz.showingFeedback) return;
            
            quiz.currentIndex--;
            quiz.selectedAnswer = quiz.answers[quiz.currentIndex]?.selectedAlternativeId || null;
            quiz.answers.pop();
            this.renderQuestion(elementId);
        },
        
        // Show results
        showResults: function(elementId) {
            var quiz = quizzes[elementId];
            if (!quiz) return;
            
            var container = document.querySelector('.quiz-player-container[data-element-id="' + elementId + '"]');
            if (!container) return;
            
            var correctCount = quiz.answers.filter(function(a) { return a.isCorrect; }).length;
            var totalCount = quiz.answers.length;
            var percentage = totalCount > 0 ? (correctCount / totalCount) * 100 : 0;
            var score = Math.round(percentage) / 10; // 0-10 scale
            var passed = percentage >= (quiz.config.passingScore || 60);
            
            // Get font size from config (default 16px)
            var baseFontSize = quiz.config.fontSize || 16;
            var titleFontSize = Math.round(baseFontSize * 1.25); // 20px at 16
            var subtitleFontSize = Math.round(baseFontSize * 0.8125); // 13px at 16
            var scoreFontSize = Math.round(baseFontSize * 3); // 48px at 16
            var statsFontSize = Math.round(baseFontSize * 1.25); // 20px at 16
            var smallFontSize = Math.round(baseFontSize * 0.6875); // 11px at 16
            var buttonFontSize = Math.round(baseFontSize * 0.875); // 14px at 16
            
            // Report score to SCORM
            if (typeof ScormAPI !== 'undefined') {
                ScormAPI.setScore(Math.round(percentage));
                // Mark course as complete when quiz is finished (regardless of pass/fail)
                // The score is already recorded, so LMS can track if they passed or not
                ScormAPI.setComplete();
                
                // Also set lesson_status based on pass/fail
                var api = ScormAPI.getAPI ? ScormAPI.getAPI() : null;
                if (api) {
                    api.LMSSetValue("cmi.core.lesson_status", passed ? "passed" : "failed");
                    api.LMSCommit("");
                }
            }
            
            var html = '<style>.quiz-scroll::-webkit-scrollbar{width:4px;height:4px;}.quiz-scroll::-webkit-scrollbar-track{background:transparent;}.quiz-scroll::-webkit-scrollbar-thumb{background:rgba(100,116,139,0.4);border-radius:4px;}.quiz-scroll::-webkit-scrollbar-thumb:hover{background:rgba(100,116,139,0.6);}.quiz-scroll{scrollbar-width:thin;scrollbar-color:rgba(100,116,139,0.4) transparent;}</style>' +
                '<div class="quiz-scroll" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;padding:16px;background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff;overflow:auto;">' +
                '<div style="max-width:360px;width:100%;background:#0f172a;border-radius:12px;padding:20px;text-align:center;">' +
                
                // Icon - smaller
                '<div style="width:60px;height:60px;margin:0 auto 12px;border-radius:50%;display:flex;align-items:center;justify-content:center;' +
                (passed ? 'background:rgba(34,197,94,0.2);' : 'background:rgba(239,68,68,0.2);') + '">' +
                '<span style="font-size:32px;">' + (passed ? 'ð' : 'â ï¸') + '</span></div>' +
                
                // Title - smaller
                '<h2 style="font-size:' + titleFontSize + 'px;font-weight:bold;margin-bottom:4px;">' + (passed ? 'ParabÃ©ns!' : 'NÃ£o foi dessa vez') + '</h2>' +
                '<p style="color:#94a3b8;font-size:' + subtitleFontSize + 'px;margin-bottom:16px;">' + (passed ? 'VocÃª atingiu a nota mÃ­nima' : 'Tente novamente para melhorar') + '</p>' +
                
                // Score - smaller
                '<div style="margin-bottom:16px;">' +
                '<div style="font-size:' + scoreFontSize + 'px;font-weight:bold;line-height:1;' + (passed ? 'color:#22c55e;' : 'color:#ef4444;') + '">' + score.toFixed(1) + '</div>' +
                '<p style="color:#94a3b8;font-size:' + Math.round(baseFontSize * 0.75) + 'px;margin-top:4px;">de 10</p></div>' +
                
                // Stats - more compact
                '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;padding:12px;background:#1e293b;border-radius:8px;">' +
                '<div><p style="font-size:' + statsFontSize + 'px;font-weight:bold;color:#22c55e;margin:0;">' + correctCount + '</p><p style="font-size:' + smallFontSize + 'px;color:#94a3b8;margin:2px 0 0;">Corretas</p></div>' +
                '<div><p style="font-size:' + statsFontSize + 'px;font-weight:bold;color:#ef4444;margin:0;">' + (totalCount - correctCount) + '</p><p style="font-size:' + smallFontSize + 'px;color:#94a3b8;margin:2px 0 0;">Incorretas</p></div></div>' +
                
                // Progress bar - compact
                '<div style="margin-bottom:16px;">' +
                '<div style="display:flex;justify-content:space-between;font-size:' + Math.round(baseFontSize * 0.75) + 'px;margin-bottom:4px;"><span>Aproveitamento</span><span>' + Math.round(percentage) + '%</span></div>' +
                '<div style="height:8px;background:#334155;border-radius:4px;overflow:hidden;">' +
                '<div style="height:100%;width:' + percentage + '%;transition:width 0.5s;' + (passed ? 'background:#22c55e;' : 'background:#ef4444;') + '"></div></div>' +
                '<p style="font-size:' + smallFontSize + 'px;color:#94a3b8;margin-top:4px;">Nota mÃ­nima: ' + (quiz.config.passingScore || 60) + '%</p></div>' +
                
                // Restart button - compact
                '<button style="width:100%;padding:10px 20px;background:linear-gradient(135deg,#06b6d4,#8b5cf6);color:#fff;border:none;border-radius:8px;font-size:' + buttonFontSize + 'px;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;" onclick="QuizController.restartQuiz(\'' + elementId + '\')">' +
                '<span>ð</span> Tentar Novamente</button>' +
                
                '</div></div>';
            
            container.innerHTML = html;
        },
        
        // Restart quiz
        restartQuiz: function(elementId) {
            var quiz = quizzes[elementId];
            if (!quiz) return;
            
            quiz.currentIndex = 0;
            quiz.answers = [];
            quiz.selectedAnswer = null;
            quiz.showingFeedback = false;
            
            // Re-shuffle if configured
            var config = quiz.config;
            if (config.shuffleQuestions !== false) {
                quiz.questions = shuffleArray(quiz.questions);
            }
            if (config.shuffleAlternatives !== false) {
                quiz.questions = quiz.questions.map(function(q) {
                    return Object.assign({}, q, { alternatives: shuffleArray(q.alternatives || []) });
                });
            }
            
            this.renderQuestion(elementId);
        }
    };
})();
