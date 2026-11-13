const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const path = require('path');
const source = fs.readFileSync(path.join(__dirname, '../services/export_assets/player.js'), 'utf8');
function section(from, to) { return source.slice(source.indexOf(from), source.indexOf(to, source.indexOf(from))); }
function node() {
  const classes = new Set();
  return {children: [], style: {}, textContent: '', innerHTML: '',
    classList: {add: (...v) => v.forEach(x => classes.add(x)), remove: (...v) => v.forEach(x => classes.delete(x)), contains: x => classes.has(x)},
    appendChild(n) { this.children.push(n); },
    querySelector() { return this.children.at(-1)?.children.at(-1); }};
}
const dots = node(), sidebar = node();
const pendingFilter = {checked:false}, pendingCount = node(), empty = node();
const ctx = {
  console: {log() {}},
  window: {VideoQuizHost: {configFor: el => el.videoConfig}},
  course: {slides: [
    {title: 'Texto', elements: []},
    {title: 'Dois quizzes', elements: [{id:'q1',type:'quiz'}, {id:'a1',type:'html',assessmentConfig:{}}]},
    {title: 'Vídeo avaliado', elements: [{id:'v1',type:'html',videoConfig:{graded:true}}]},
    {title: 'Vídeo formativo', elements: [{id:'v2',type:'html',videoConfig:{graded:false}}]},
    {title: 'Cenário', elements: [{id:'s1',type:'scenario'}]},
    {title: 'Fim', elements: []}
  ]},
  currentSlide: 5, totalSlides: 6, courseCompleted: false, completionRequested: false,
  completedQuizzes: {}, totalQuizzes: 3,
  ScormAPI: {recordAssessment() {}, beginRetry() {}},
  checkAndSetCompletion() {}, updateNavigation() {},
  document: {
    getElementById(id) { return ({'progress-dots':dots,'sidebar-slides':sidebar,'sidebar-pending-only':pendingFilter,'sidebar-pending-count':pendingCount,'sidebar-pending-empty':empty})[id] || null; },
    createElement: node,
    querySelectorAll() { return sidebar.children; },
    querySelector() { return null; }
  }
};
vm.createContext(ctx);
vm.runInContext(section('    function gradedVideo(', '    function loadCourse(') +
  section('    function slideCompletionState(', '    function updateNavigation(') +
  section('    function applyPendingSlideFilter(', '    // Keyboard navigation') +
  section('    function onQuizComplete(', '    // Called by ScenarioController'), ctx);
ctx.renderSidebar();
const status = i => sidebar.children[i].querySelector('.sidebar-slide-status');
assert.equal(status(1).textContent, '⚠ Quiz pendente (2/2)', 'Skipping must not complete quizzes');
assert(status(1).classList.contains('quiz-pending'));
assert.equal(status(0).textContent, '✓ Concluído');
assert.equal(status(3).textContent, '✓ Concluído', 'Ungraded video is not a completion gate');
assert.equal(status(4).textContent, '✓ Concluído', 'Scenario behavior is unchanged');
ctx.updateProgress();
assert(dots.innerHTML.includes('quiz-pending'));
assert(dots.innerHTML.includes('Slide 2: ⚠ Quiz pendente (2/2)'));
ctx.onQuizComplete('q1', 0);
assert.equal(status(1).textContent, '⚠ Quiz pendente (1/2)', 'Score is independent of finalization');
ctx.onQuizComplete('a1', 100);
assert.equal(status(1).textContent, '✓ Quiz concluído');
ctx.onQuizComplete('v1', 100);
assert.equal(status(2).textContent, '✓ Quiz concluído');
assert(!dots.innerHTML.includes('quiz-pending'));
ctx.onQuizRetry('q1');
assert.equal(status(1).textContent, '⚠ Quiz pendente (1/2)');
assert(dots.innerHTML.includes('quiz-pending'));
// Resume uses the completion IDs restored by configureResults(), not position.
ctx.completedQuizzes = {q1:true, a1:true, v1:true};
ctx.currentSlide = 0;
ctx.updateProgress();
assert.equal(status(1).textContent, '✓ Quiz concluído', 'Restored result stays complete ahead of bookmark');
ctx.currentSlide = 1; delete ctx.completedQuizzes.a1; ctx.updateProgress();
assert.equal(status(1).textContent, '⚠ Quiz pendente (1/2) · Atual');
ctx.courseCompleted = true; ctx.currentSlide=5; ctx.updateProgress();
assert.equal(status(5).textContent, '✓ Concluído · Atual');
assert.equal(status(1).textContent, '⚠ Quiz pendente (1/2)', 'Course flag must not hide missing assessments');
// Filtering reads the same completion states; it never mutates course/results.
const originalCourse = JSON.stringify(ctx.course), originalResults = JSON.stringify(ctx.completedQuizzes);
pendingFilter.checked = true; pendingFilter.onchange();
assert.equal(sidebar.children[0].hidden, true);
assert.equal(sidebar.children[1].hidden, false, 'Visited quiz with missing result remains visible');
assert.equal(sidebar.children[5].hidden, true, 'Completed current slide is hidden too');
assert.equal(pendingCount.textContent, '1 de 6 slides pendentes');
assert.equal(empty.hidden, true);
assert.equal(ctx.currentSlide, 5);
assert.equal(JSON.stringify(ctx.course), originalCourse);
assert.equal(JSON.stringify(ctx.completedQuizzes), originalResults);
ctx.completedQuizzes.a1 = true; ctx.updateSidebar();
assert(sidebar.children.every(item=>item.hidden));
assert.equal(empty.hidden, false);
ctx.onQuizRetry('q1');
assert.equal(sidebar.children[1].hidden, false, 'Retry immediately restores pending item');
assert.equal(empty.hidden, true);
pendingFilter.checked = false; pendingFilter.onchange();
assert(sidebar.children.every(item=>!item.hidden));
ctx.currentSlide = 0; ctx.courseCompleted = false; ctx.updateSidebar();
pendingFilter.checked = true; pendingFilter.onchange();
assert.equal(sidebar.children[0].hidden, false, 'Current unfinished non-quiz slide stays visible');
assert.equal(sidebar.children[5].hidden, false, 'Future unfinished slide stays visible');
ctx.window.ScormifyGuided = {slideState:()=>({stage:'practice',done:true})};
ctx.course.metadata = {guidedPath:true}; ctx.updateSidebar();
assert(sidebar.children.every(item=>item.hidden), 'Guided path uses its own completion state');
ctx.window.ScormifyGuided.slideState=()=>({stage:'practice',done:false}); ctx.updateSidebar();
assert(sidebar.children.every(item=>!item.hidden));
console.log('SCORM navigation: skipped, partial, completed, retry, restored, current, graded video and dots passed');
