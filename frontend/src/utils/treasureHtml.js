import { treasureRuntime } from '../components/games/treasureRuntime';

export function upgradeTreasureHtml(html) {
  if (!html || typeof html !== 'string' || html.includes('scormify-treasure-v1') || !/["']type["']\s*:\s*["']treasure["']/.test(html)) return html;
  if (!html.includes('renderAdventure') || !html.includes('const QE=')) return html;
  const script=`<script id="scormify-treasure-v1">(${treasureRuntime.toString()})(Game,BANK,QE,document.getElementById('stage'));</script>`;
  return /<\/body>/i.test(html) ? html.replace(/<\/body>/i,script+'</body>') : html+script;
}
