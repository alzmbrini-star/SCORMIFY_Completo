import { slidePreviewText } from './slidePreviewText';

test('reads course heading instead of preceding CSS', () => {
  const html='<style>h1 { color: #0f172a !important; }</style><h1>Como Aplicar um <strong>Feedback</strong> Efetivo</h1><p>Trilha do Curso</p>';
  expect(slidePreviewText(html,['h1'])).toBe('Como Aplicar um Feedback Efetivo');
});
test('ignores scripts, hidden labels and decodes entities without execution', () => {
  const html='<script>window.bad=true</script><div hidden>Escondido</div><p style="display:none">Oculto</p><h1>Gestão &amp; Liderança</h1>';
  expect(slidePreviewText(html,['h1'])).toBe('Gestão & Liderança');
  expect(window.bad).toBeUndefined();
});
test('CSS-only documents yield empty text for caller fallback', () => {
  expect(slidePreviewText('<style>h1 {color:red}</style>',['h1'])).toBe('');
  expect(slidePreviewText(null)).toBe('');
});
test('legacy span headings and subtitles remain readable', () => {
  expect(slidePreviewText('<span style="font-size:40px">Título da capa</span>',['h1'])).toBe('Título da capa');
  expect(slidePreviewText('<style>p{color:white}</style><p>Trilha do Curso</p>',['p'])).toBe('Trilha do Curso');
});
