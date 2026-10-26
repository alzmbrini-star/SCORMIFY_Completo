import { assessmentRuntime } from './assessmentRuntime';

const cases = [
  { type: 'single_choice', options: [{ id: 'a', text: 'A', isCorrect: true }, { id: 'b', text: 'B' }] },
  { type: 'multiple_choice', options: [{ id: 'a', text: 'A', isCorrect: true }, { id: 'b', text: 'B', isCorrect: true }] },
  { type: 'ordering', items: [{ id: 'a', text: 'A' }, { id: 'b', text: 'B' }], correctOrder: ['a', 'b'] },
  { type: 'categorization', targets: [{ id: 'x', label: 'X' }, { id: 'y', label: 'Y' }], items: [{ id: 'a', text: 'A', correctTarget: 'x' }, { id: 'b', text: 'B', correctTarget: 'y' }] },
];

afterEach(() => { document.body.replaceChildren(); });

test.each(cases)('$type displays associated image beside the question, not in the answer panel', question => {
  document.body.innerHTML = '<script id="assessment-data" type="application/json"></script><main id="app"></main>';
  document.getElementById('assessment-data').textContent = JSON.stringify({ title: 'Avaliação', questions: [{
    ...question, id: 'question-1', title: 'Situação prática', prompt: 'Enunciado preservado', category: 'Contexto',
    media: { kind: 'image', url: '/api/projects/project-1/assets/support.png', name: 'Imagem contextual' },
  }] });
  assessmentRuntime();
  const stage = document.querySelector('.stage');
  expect(stage.querySelector('img').getAttribute('src')).toContain('/assets/support.png');
  expect(document.querySelector('.prompt').textContent).toBe('Enunciado preservado');
  expect(document.querySelector('.prompt').parentElement.querySelector('img')).toBeNull();
  if (question.type === 'categorization') {
    expect(stage.querySelector('.assessment-support img')).not.toBeNull();
    expect(stage.querySelector('.dropzones')).not.toBeNull();
  }
  const enlarge = [...document.querySelectorAll('button')].find(button => button.textContent.includes('Ampliar'));
  expect(enlarge).toBeDefined();
  enlarge.click();
  expect(document.querySelector('.image-overlay img').getAttribute('src')).toContain('/assets/support.png');
});
