import { crosswordRuntime } from '../components/games/crosswordRuntime';

export function upgradeCrosswordHtml(html) {
  if (!html || typeof html !== 'string' || html.includes('scormify-crossword-v2') || !/["']type["']\s*:\s*["']crossword["']/.test(html)) return html;
  if (!html.includes('renderCrossword') || !html.includes('const QE=')) return html;
  const script = `<script id="scormify-crossword-v2">(${crosswordRuntime.toString()})(Game,BANK,QE,document.getElementById('stage'));</script>`;
  return /<\/body>/i.test(html) ? html.replace(/<\/body>/i,script+'</body>') : html+script;
}
