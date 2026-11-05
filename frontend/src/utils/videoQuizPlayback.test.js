import { videoQuizPlaybackRuntime, videoQuizFeedbackLayoutRuntime, upgradeVideoQuizPlayback } from './videoQuizPlayback';

describe('recorded avatar buffering feedback', () => {
  let video, button, paused, currentTime, ready;
  beforeEach(() => {
    jest.useFakeTimers(); paused = true; currentTime = 0; ready = 2;
    document.body.innerHTML = '<video id="video"></video><div class="controls"><button id="play">Reproduzir</button></div><script id="video-quiz-data" type="application/json">{"checkpoints":[{"at":10}]}</script><p id="question">Pergunta original</p>';
    video = document.getElementById('video'); button = document.getElementById('play');
    Object.defineProperties(video, {paused: {get: () => paused, configurable:true}, ended:{get:()=>false,configurable:true},currentTime:{get:()=>currentTime,configurable:true},readyState:{get:()=>ready,configurable:true}});
    videoQuizPlaybackRuntime();
  });
  afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); document.body.innerHTML = ''; document.querySelectorAll('#video-quiz-alpha-style').forEach(n => n.remove()); });
  const emit = name => document.getElementById('video').dispatchEvent(new Event(name));
  test('play request shows loading, not a claim that playback has started', () => {
    paused = false; emit('play');
    expect(button.textContent).toBe('Carregando vídeo…');
    expect(button.getAttribute('aria-busy')).toBe('true');
    expect(document.getElementById('video-load-status').hidden).toBe(false);
    ready = 4; emit('playing');
    expect(button.textContent).toBe('Pausar');
    expect(document.getElementById('video-load-status').hidden).toBe(true);
  });
  test('stalled download gets actionable feedback without resetting or releasing questions', () => {
    paused = false; emit('play'); jest.advanceTimersByTime(12000);
    expect(document.getElementById('video-load-status').textContent).toContain('demorando');
    expect(document.getElementById('question').textContent).toBe('Pergunta original');
    expect(video.currentTime).toBe(0);
    paused = true; emit('pause');
    expect(button.textContent).toBe('Reproduzir');
    expect(jest.getTimerCount()).toBe(0);
  });
  test('buffering while playing keeps a loading state until media actually advances', () => {
    paused = false; ready = 4; emit('waiting'); emit('timeupdate');
    expect(button.textContent).toBe('Carregando vídeo…');
    currentTime = 1; emit('timeupdate'); expect(button.textContent).toBe('Pausar');
  });
  test('network/media error does not leave the button stuck on loading', () => {
    paused = false; emit('play'); paused = true; emit('error');
    expect(button.textContent).toBe('Reproduzir');
    expect(document.getElementById('video-load-status').textContent).toContain('Não foi possível');
  });
  test('upgrade is idempotent and preserves data and the existing click handler', () => {
    const click = jest.fn(); button.onclick = click;
    videoQuizPlaybackRuntime(); button.click(); expect(click).toHaveBeenCalledTimes(1);
    expect(document.querySelectorAll('#video-load-status')).toHaveLength(1);
    const original = '<html><body><script id="video-quiz-data" type="application/json">{"src":"clip.mp4"}</script></body></html>';
    const upgraded = upgradeVideoQuizPlayback(original);
    expect(upgraded).toContain('{"src":"clip.mp4"}');
    expect(upgradeVideoQuizPlayback(upgraded)).toBe(upgraded);
    expect(upgradeVideoQuizPlayback('<html>Outro conteúdo</html>')).toBe('<html>Outro conteúdo</html>');
  });
  test('transparent avatars keep their original file and have no opaque player backing', () => {
    video.src = 'https://example.org/original-alpha.webm';
    videoQuizPlaybackRuntime();
    expect(video.src).toBe('https://example.org/original-alpha.webm');
    expect(video.dataset.preserveTransparency).toBe('true');
    expect(document.getElementById('video-quiz-alpha-style').textContent).toContain('.avatar,#video{background:transparent!important}');
  });
  test('author can retain the dark backing for opaque videos', () => {
    document.getElementById('video-quiz-data').textContent = '{"preserveTransparency":false}';
    delete video.dataset.playbackStatus;
    delete video.dataset.preserveTransparency;
    document.getElementById('video-quiz-alpha-style').remove();
    videoQuizPlaybackRuntime();
    expect(document.getElementById('video-quiz-alpha-style')).toBeNull();
    expect(video.dataset.preserveTransparency).toBeUndefined();
  });
  test('upgrades old loading UI without running two copies', () => {
    const old = '<body><script id="video-quiz-data" type="application/json">{}</script><script id="video-quiz-playback-v1">oldRuntime();</script></body>';
    const next = upgradeVideoQuizPlayback(old);
    expect(next).not.toContain('oldRuntime()');
    expect(next.match(/id="video-quiz-playback-v2"/g)).toHaveLength(1);
  });
});

test('moves live feedback and loading regions to the question panel without replacing nodes', () => {
  document.body.innerHTML = '<script id="video-quiz-data" type="application/json">{}</script><section class="avatar"><video id="video"></video><div class="controls"><button id="play">Reproduzir</button></div><p id="feedback" hidden role="status" aria-live="polite"></p><p id="video-load-status" hidden></p></section><section id="panel"><p id="message"></p><button id="continue">Continuar</button></section>';
  const feedback = document.getElementById('feedback'), loading = document.getElementById('video-load-status');
  const avatar = document.querySelector('.avatar');
  videoQuizFeedbackLayoutRuntime();
  const unchangedVideoArea = avatar.innerHTML;
  ['Acertou!', 'Tente novamente.', 'Explicação longa para revisão.'].forEach(text => {
    feedback.hidden = false; feedback.textContent = text;
    loading.hidden = false; loading.textContent = 'Carregando';
    expect(avatar.innerHTML).toBe(unchangedVideoArea);
    expect(feedback.parentNode.id).toBe('panel');
    expect(loading.parentNode.id).toBe('panel');
  });
  expect(feedback.nextElementSibling.id).toBe('continue');
  expect(feedback.getAttribute('aria-live')).toBe('polite');
  videoQuizFeedbackLayoutRuntime();
  expect(document.querySelectorAll('#video-quiz-feedback-style')).toHaveLength(1);
  expect(document.getElementById('feedback')).toBe(feedback);
  document.body.innerHTML=''; document.getElementById('video-quiz-feedback-style').remove();
});

test('saved playback-v2 documents also get the new feedback layout', () => {
  const old='<body><script id="video-quiz-data" type="application/json">{"key":"keep"}</script><script id="video-quiz-playback-v2">existing();</script></body>';
  const upgraded=upgradeVideoQuizPlayback(old);
  expect(upgraded).toContain('existing();');
  expect(upgraded).toContain('id="video-quiz-feedback-v1"');
  expect(upgradeVideoQuizPlayback(upgraded)).toBe(upgraded);
});
