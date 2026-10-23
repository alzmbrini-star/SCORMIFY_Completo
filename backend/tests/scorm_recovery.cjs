const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(require('path').join(__dirname, '../services/export_assets/scorm-api.js'), 'utf8');
function session(score = '', mastery = '80', reject = '', commit = true) {
  const values = {'cmi.core.score.raw': score, 'cmi.student_data.mastery_score': mastery};
  let finishes = 0;
  const api = {
    LMSInitialize: () => 'true', LMSGetValue: key => values[key] ?? '',
    LMSSetValue: (key, value) => { if (key === reject) return 'false'; values[key] = value; return 'true'; },
    LMSCommit: () => String(commit), LMSFinish: () => { finishes++; return 'true'; }, LMSGetLastError: () => '101'
  };
  const window = {API: api, addEventListener() {}}; window.parent = window;
  const context = {window, console: {log() {}, warn() {}, error() {}}, Date};
  vm.createContext(context); vm.runInContext(source, context); context.ScormAPI.initialize();
  return {wrapper: context.ScormAPI, values, finishes: () => finishes};
}
for (const [score, mastery, expected] of [['', '80', 'completed'], ['90', '80', 'passed'], ['60', '80', 'failed'], ['70', '60', 'passed'], ['85', '', 'passed']]) {
  const s = session(score, mastery); assert.strictEqual(s.wrapper.setComplete(), true);
  assert.strictEqual(s.values['cmi.core.lesson_status'], expected);
  assert.strictEqual(s.values['cmi.core.exit'], expected==='failed'?'suspend':'');
}
assert.strictEqual(session('', '80', 'cmi.core.lesson_status').wrapper.setComplete(), false);
const rejectedCommit = session('90', '80', '', false);
assert.strictEqual(rejectedCommit.wrapper.setComplete(), false);
assert.strictEqual(rejectedCommit.wrapper.finish(), false);
assert.strictEqual(rejectedCommit.finishes(), 0, 'Failed commit must not terminate the session');
assert.strictEqual(session('', '80', 'cmi.core.score.raw').wrapper.setScore(90), false);
assert.strictEqual(session('', '60').wrapper.getPassingScore(), 60);
assert.strictEqual(session('', '').wrapper.getPassingScore(), 80);
console.log('SCORM 1.2: completion, pass/fail, mastery, write rejection and commit rejection passed');
const recovery=session('0','80');
recovery.wrapper.configureResults([{id:'quiz1',weight:3},{id:'quiz2',weight:3},{id:'assessment',weight:1}]);
recovery.wrapper.recordAssessment('quiz1',100);
assert.equal(recovery.wrapper.setComplete(),false,'Must not complete before every graded activity');
recovery.wrapper.recordAssessment('quiz2',0);recovery.wrapper.recordAssessment('assessment',100);
assert.equal(recovery.wrapper.setComplete(),true);
assert.equal(recovery.wrapper.getCompletionResult().status,'failed');
assert.equal(recovery.values['cmi.core.exit'],'suspend');
assert.equal(recovery.wrapper.beginRetry('quiz2'),true);
assert.equal(recovery.values['cmi.core.lesson_status'],'incomplete');
assert.equal(recovery.wrapper.setComplete(),false,'Retake pending must block finalization');
recovery.wrapper.recordAssessment('quiz2',100);
assert.equal(recovery.wrapper.setComplete(),true);
assert.equal(recovery.values['cmi.core.lesson_status'],'passed');
recovery.wrapper.beginRetry('quiz2');recovery.wrapper.recordAssessment('quiz2',0);recovery.wrapper.setComplete();
assert.equal(recovery.values['cmi.core.lesson_status'],'passed','Review must not demote passing result');
const resumed=session('50','80');
resumed.values['cmi.suspend_data']=JSON.stringify({scormifyResults:1,results:{quiz1:100,quiz2:0}});
assert.equal(resumed.wrapper.configureResults([{id:'quiz1',weight:3},{id:'quiz2',weight:3}]).length,2);
resumed.wrapper.beginRetry('quiz2');resumed.wrapper.recordAssessment('quiz2',100);resumed.wrapper.setComplete();
assert.equal(resumed.values['cmi.core.lesson_status'],'passed');
console.log('Weighted result aggregation, pending gates, failed->retry->passed, resume and passed protection OK');
