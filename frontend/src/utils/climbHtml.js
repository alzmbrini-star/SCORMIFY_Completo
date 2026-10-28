import { climbRuntime } from '../components/games/climbRuntime';

export function upgradeClimbHtml(html) {
  if(!html || typeof html!=='string' || html.includes('scormify-climb-v1') || !/["']type["']\s*:\s*["']climb["']/.test(html))return html;
  if(!html.includes('renderAdventure') || !html.includes('const QE='))return html;
  const script=`<script id="scormify-climb-v1">(${climbRuntime.toString()})(Game,BANK,QE,document.getElementById('stage'),SETTINGS);</script>`;
  return /<\/body>/i.test(html)?html.replace(/<\/body>/i,script+'</body>'):html+script;
}
