import { fitGameElementToSlide, isGeneratedGameHtml, wrapInteractiveFullbleed } from './htmlUtils';

describe('interactive fixed-stage fitting', () => {
  test('planning workspace owns a readable scrolling viewport without content-height scaling',()=>{
    const html='<html><body data-sim-engine="entity-planning-v1"><main>Planejamento</main></body></html>';
    expect(wrapInteractiveFullbleed(html,'fit')).toBe(html);
    expect(fitGameElementToSlide({type:'html',htmlContent:html},960,540)).toMatchObject({x:0,y:0,width:960,height:540});
  });
  test('upgrades an existing generated game without an enlargement cap', () => {
    const legacy = `<!doctype html><html><body><main class="game">Jogo</main>
      <script>const QuestionEngine={};const marker='__scormify_fit_v3';</script></body></html>`;

    const upgraded = wrapInteractiveFullbleed(legacy, 'fit');

    expect(upgraded).toContain('__scormify_game_fit_v9');
    expect(upgraded).toContain('responsive=fixed&&fixed.querySelector');
    expect(upgraded).toContain('(innerHeight-p*2)/540));');
    expect(upgraded).toContain('setInterval(function(){f();if(++n>=24)clearInterval(t)},100)');
    expect(upgraded).not.toContain('(innerHeight-p*2)/540,1.55)');
  });

  test('does not inject the game override into ordinary HTML pages', () => {
    const page = '<!doctype html><html><body><main class="app">Relatório</main></body></html>';
    expect(wrapInteractiveFullbleed(page, 'page')).not.toContain('__scormify_game_fit_v9');
  });

  test('recognizes canonical games even when a legacy export omitted QuestionEngine', () => {
    const game = '<html><body><main class="app game">SCORMIFY ADVENTURES - EXPEDIÇÃO DO SABER</main></body></html>';
    expect(isGeneratedGameHtml(game)).toBe(true);
    expect(wrapInteractiveFullbleed(game, 'fit')).toContain('__scormify_game_fit_v9');
  });

  test('recognizes an encoded legacy Forca and expands it to the slide', () => {
    const forca = '<html><body><main class="game">ARENA DAS PALAVRAS</main><script>const QuestionEngine={};</script></body></html>';
    const encoded = `__B64__:${btoa(forca)}`;
    expect(isGeneratedGameHtml(encoded)).toBe(true);
    expect(fitGameElementToSlide({ type: 'html', htmlContent: encoded, width: 640, height: 360 }, 1920, 1080)).toMatchObject({
      x: 19, y: 11, width: 1882, height: 1058,
    });
  });

  test('expands game elements to the slide viewport while preserving a safe margin', () => {
    const element = { type: 'html', interactiveType: 'game', x: 320, y: 180, width: 960, height: 540 };
    expect(fitGameElementToSlide(element, 1920, 1080)).toMatchObject({
      x: 19, y: 11, width: 1882, height: 1058, objectFit: 'cover', htmlDisplayMode: 'fit',
    });
  });
});
