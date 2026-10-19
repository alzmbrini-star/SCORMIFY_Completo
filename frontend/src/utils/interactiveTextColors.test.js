import { applyInteractiveTextColors, readInteractiveTextColors } from './interactiveTextColors';

const original = '<html><head><style>.bubble{color:black}</style></head><body><main class="conversation"><p>Olá</p></main><script>advanceTurn()</script></body></html>';

test('persists regional overrides without changing activity scripts', () => {
  const html = applyInteractiveTextColors(original, { scene:'#ffffff', panel:'#123456' });
  expect(readInteractiveTextColors(html)).toEqual({ scene:'#ffffff', panel:'#123456' });
  expect(html).toContain('<script>advanceTurn()</script>');
  expect(html).toContain('color:#ffffff!important');
  expect(html).toContain('button:not(.primary):not(.secondary)');
});

test('replace is idempotent and restore returns exact original', () => {
  const colors = {title:'#eeeeee'};
  const once = applyInteractiveTextColors(original, colors);
  expect(applyInteractiveTextColors(once, colors)).toBe(once);
  expect(applyInteractiveTextColors(once, {})).toBe(original);
});

test('ignores invalid color and unknown region without injecting CSS', () => {
  expect(applyInteractiveTextColors(original,{scene:'red;display:none',unknown:'#ffffff'})).toBe(original);
});
