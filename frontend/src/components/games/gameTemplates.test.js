import { generateEducationalGameHtml } from './gameTemplates';

const questions = Array.from({ length: 5 }, (_, index) => ({
  id: `q-${index}`,
  question: `Pergunta ${index + 1}`,
  alternatives: [{ id: 'a', text: 'Correta' }, { id: 'b', text: 'Incorreta' }],
  correctAnswer: 'a',
  explanation: 'Explicação pedagógica',
}));

describe('educational game templates', () => {
  test.each(['penalty', 'quiz_show', 'memory', 'hangman'])('builds an offline %s game', (gameType) => {
    const html = generateEducationalGameHtml({
      gameType,
      title: 'Jogo de teste',
      questions,
      config: { lives: 3, time: 30, shuffle: true },
    });
    expect(html).toContain('<!doctype html>');
    expect(html).toContain('QuestionEngine');
    expect(html).toContain(`"type":"${gameType}"`);
    expect(html).toContain('Pergunta 1');
    expect(html).toContain('scormify-game-results');
  });
});
