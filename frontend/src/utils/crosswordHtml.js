import { crosswordRuntime } from '../components/games/crosswordRuntime';

export function upgradeCrosswordHtml(html) {
  if (!html || typeof html !== 'string' || html.includes('scormify-crossword-v4') || !/["']type["']\s*:\s*["']crossword["']/.test(html)) return html;
  if (!html.includes('renderCrossword') || !html.includes('const QE=')) return html;
  html=html.replace(/<script\b[^>]*\bid=["']scormify-crossword-v[23]["'][^>]*>[\s\S]*?<\/script>/gi,'');
  const script = `<script id="scormify-crossword-v4">(${crosswordRuntime.toString()})(Game,BANK,QE,document.getElementById('stage'));</script>`;
  return /<\/body>/i.test(html) ? html.replace(/<\/body>/i,script+'</body>') : html+script;
}
