import { generateEducationalGameHtml } from './gameTemplates';

const questions = Array.from({ length: 5 }, (_, index) => ({
  id: `q-${index}`,
  question: `Pergunta ${index + 1}`,
  alternatives: [{ id: 'a', text: 'Correta' }, { id: 'b', text: 'Incorreta' }],
  correctAnswer: 'a',
  explanation: 'Explicação pedagógica',
}));

describe('educational game templates', () => {
  test.each(['penalty', 'quiz_show', 'memory', 'hangman', 'climb', 'crossword', 'sudoku', 'race', 'battle', 'treasure'])('builds an offline %s game', (gameType) => {
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

  test('memory game starts face-down and keeps long labels inside the cards', () => {
    const html = generateEducationalGameHtml({
      gameType: 'memory',
      title: 'Memória de conceitos',
      questions,
      config: { lives: 3, time: 30, shuffle: true },
    });

    expect(html).toContain('className=\'memory-face\'');
    expect(html).toContain('className=\'memory-cover\'');
    expect(html).toContain("cover.textContent='?'");
    expect(html).toContain('.memory-card:not(.open):not(.matched) .memory-face{opacity:0;visibility:hidden');
    expect(html).toContain('-webkit-line-clamp:5');
    expect(html).toContain("if(this.locked||this.opened.includes(i)||this.pairs[i].matched)return");
  });
});
