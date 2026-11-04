import { resolveHtmlAssetUrls } from './htmlAssetUrls';

const backend = 'https://media.example';
const path = '/api/projects/p/assets/kling_saved.mp4';
const question = { at: 4, question: 'Qual ação?', options: ['A', 'B'], correctIndex: 1 };

test.each([path, 'https://old.example'+path, 'https://frontend.example'+path])(
  'resolves the video JSON snapshot as well as src attributes: %s', src => {
    const config = {src, key: 'resume-key', checkpoints: [question], graded: false};
    const html = '<video src="'+src+'"></video><script id="video-quiz-data" type="application/json">'+JSON.stringify(config)+'</script>';
    const output = resolveHtmlAssetUrls(html, backend+'/');
    const doc = new DOMParser().parseFromString(output, 'text/html');
    const after = JSON.parse(doc.getElementById('video-quiz-data').textContent);
    expect(after).toEqual({...config, src:backend+path});
    expect(doc.querySelector('video').getAttribute('src')).toBe(backend+path);
    expect(resolveHtmlAssetUrls(output, backend)).toBe(output);
  },
);

test('keeps external provider links, embedded data, questions and scripts intact', () => {
  const html = '<script>const src="https://resource2.heygen.ai/avatar.webm?token=abc"; const thumb="data:image/png;base64,AAAA"; const marker="resume-key";</script>';
  expect(resolveHtmlAssetUrls(html, backend)).toBe(html);
  expect(resolveHtmlAssetUrls(null, backend)).toBe('');
  expect(resolveHtmlAssetUrls(html, '')).toBe(html);
});

test('resolves quoted project/global media strings used by activity code', () => {
  expect(resolveHtmlAssetUrls("const video='/api/projects/p/assets/a.mp4'; const image=\"/api/assets/a.png\";", backend))
    .toBe("const video='https://media.example/api/projects/p/assets/a.mp4'; const image=\"https://media.example/api/assets/a.png\";");
});
