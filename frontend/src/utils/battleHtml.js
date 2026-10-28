import { battleRuntime } from '../components/games/battleRuntime';

export function upgradeBattleHtml(html) {
  if (!html || typeof html !== 'string' || html.includes('scormify-battle-v1') || !/["']type["']\s*:\s*["']battle["']/.test(html)) return html;
  if (!html.includes('enemyHealth') || !html.includes('const QE=')) return html;
  const script=`<script id="scormify-battle-v1">(${battleRuntime.toString()})(Game,BANK,QE,document.getElementById('stage'),SETTINGS);</script>`;
  return /<\/body>/i.test(html) ? html.replace(/<\/body>/i,script+'</body>') : html+script;
}
