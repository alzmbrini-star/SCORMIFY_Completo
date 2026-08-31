/**
 * HTML Utility functions for sanitizing and processing HTML content
 * Used across Editor, SlideCanvas, and export components
 */

import { getApiUrl } from './apiUrl';
const API_URL = getApiUrl();

/**
 * Sanitize HTML content by removing Tailwind CSS variables and editor artifacts
 * This prevents style pollution from the main application affecting rendered content
 * @param {string} htmlContent - The HTML string to sanitize
 * @returns {string} - Cleaned HTML string
 */
export const sanitizeHtmlForDisplay = (htmlContent) => {
  if (!htmlContent || typeof htmlContent !== 'string') return htmlContent || '';
  
  // Remove --tw-* CSS custom properties from inline styles
  let cleaned = htmlContent.replace(/--tw-[^;:]+:[^;]*;?\s*/g, '');
  
  // Remove outline styles from editor selection artifacts
  cleaned = cleaned.replace(/outline-style:\s*dashed\s*;?\s*/g, '');
  cleaned = cleaned.replace(/outline-width:\s*[^;]+;?\s*/g, '');
  
  // Clean up empty style attributes or those with only whitespace/semicolons
  cleaned = cleaned.replace(/style="\s*;?\s*"/g, '');
  cleaned = cleaned.replace(/style='\s*;?\s*'/g, '');
  
  return cleaned;
};

/**
 * Alias for backward compatibility
 * Some components use sanitizeHtmlContent instead of sanitizeHtmlForDisplay
 */
export const sanitizeHtmlContent = sanitizeHtmlForDisplay;

/**
 * Strip absolute domain from asset URLs, converting them to relative paths.
 * This MUST be called before saving htmlContent to the database to prevent
 * broken links when the environment domain changes (e.g., after a fork).
 * 
 * Converts: https://any-domain.com/api/assets/file.jpg → /api/assets/file.jpg
 * Converts: https://any-domain.com/api/projects/id/assets/file.jpg → /api/projects/id/assets/file.jpg
 * @param {string} htmlContent - The HTML string with potential absolute URLs
 * @returns {string} - HTML string with relative asset URLs
 */
export const stripDomainFromAssetUrls = (htmlContent) => {
  if (!htmlContent || typeof htmlContent !== 'string') return htmlContent || '';
  
  // Strip domain from /api/assets/ URLs (global AI-generated images)
  let result = htmlContent.replace(
    /https?:\/\/[^/\s"']+\/api\/assets\//g,
    '/api/assets/'
  );
  
  // Strip domain from /api/projects/{id}/assets/ URLs (project-specific media)
  result = result.replace(
    /https?:\/\/[^/\s"']+\/api\/projects\//g,
    '/api/projects/'
  );
  
  return result;
};

/**
 * Resolve relative asset URLs to absolute URLs using the current backend URL.
 * This is needed when loading content into the browser's contentEditable editor
 * or rendering in iframes, where relative URLs may not resolve correctly.
 * 
 * Converts: /api/assets/file.jpg → https://current-domain.com/api/assets/file.jpg
 * Converts: /api/projects/id/assets/file.jpg → https://current-domain.com/api/projects/id/assets/file.jpg
 * @param {string} htmlContent - The HTML string with relative asset URLs
 * @returns {string} - HTML string with absolute asset URLs
 */
export const resolveAssetUrls = (htmlContent) => {
  if (!htmlContent || typeof htmlContent !== 'string' || !API_URL) return htmlContent || '';
  
  // First strip any old absolute domains to normalize
  let result = stripDomainFromAssetUrls(htmlContent);
  
  // Then resolve relative /api/ URLs to the current domain
  // Match src="/api/..." or src='/api/...' attributes
  result = result.replace(
    /(src=["'])\/api\//g,
    `$1${API_URL}/api/`
  );
  
  return result;
};

// Full HTML documents pasted into the Editor are web pages, not screenshots.
// Page mode keeps the iframe as a real viewport with its own vertical scroll.
// Fit mode remains available for fixed 960x540 simulations/infographics.
const PAGE_VIEWPORT_SNIPPET =
  '<style id="__scormify_page_mode">' +
  'html{margin:0!important;padding:0!important;width:100%!important;height:100%!important;' +
  'overflow-x:hidden!important;overflow-y:auto!important;scrollbar-gutter:stable;}' +
  'body{margin:0!important;width:100%!important;min-width:0!important;min-height:100%!important;' +
  'height:auto!important;overflow:visible!important;transform:none!important;}' +
  'body>*{max-width:100%;box-sizing:border-box;}' +
  'img,video,canvas,svg{max-width:100%;}' +
  '</style>';

// Auto-fit wrapper for fixed-stage interactive HTML (simulators, infographics,
// etc). Content designed for a 960x540 stage is centered and scaled.
const FIT_SNIPPET =
  '<style id="__scormify_fit_v3">html,body{margin:0!important;padding:0!important;width:100%;height:100%;' +
  'overflow:hidden!important;}body{display:block!important;position:relative!important;}</style>' +
  "<script>(function(){function b(){var bd=document.body;" +
  "if(!bd||document.getElementById('__stage'))return;" +
  "var st=document.createElement('div');st.id='__stage';" +
  "st.style.cssText='width:960px;position:absolute;left:0;top:0;margin:0;transform-origin:0 0;';" +
  'while(bd.firstChild){st.appendChild(bd.firstChild);}bd.appendChild(st);' +
  "function fit(){st.style.transform='none';var sr=st.getBoundingClientRect(),minX=0,minY=0;" +
  'var maxX=Math.max(960,st.scrollWidth,st.offsetWidth),maxY=Math.max(540,st.scrollHeight,st.offsetHeight);' +
  "Array.prototype.forEach.call(st.querySelectorAll('*'),function(n){var cs=getComputedStyle(n);if(cs.display==='none'||cs.visibility==='hidden')return;var r=n.getBoundingClientRect();if(!r.width&&!r.height)return;minX=Math.min(minX,r.left-sr.left);minY=Math.min(minY,r.top-sr.top);maxX=Math.max(maxX,r.right-sr.left);maxY=Math.max(maxY,r.bottom-sr.top);});" +
  'var cw=maxX-minX,ch=maxY-minY,pad=12,s=Math.min((innerWidth-pad*2)/cw,(innerHeight-pad*2)/ch,1);s=Math.max(.1,s);' +
  "var tx=(innerWidth-cw*s)/2-minX*s,ty=(innerHeight-ch*s)/2-minY*s;st.style.transform='translate('+tx+'px,'+ty+'px) scale('+s+')';}" +
  "window.addEventListener('resize',fit);fit();setTimeout(fit,300);setTimeout(fit,1000);}" +
  "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',b);}" +
  'else{b();}})();</scr' + 'ipt>';

const FIT_UPGRADE_SNIPPET =
  '<style id="__scormify_fit_v3">html,body{overflow:hidden!important;}' +
  'body{display:block!important;position:relative!important;}</style>' +
  "<script>(function(){function u(){var st=document.getElementById('__stage');if(!st)return;" +
  "st.style.position='absolute';st.style.left='0';st.style.top='0';st.style.margin='0';" +
  "st.style.transformOrigin='0 0';function fit(){st.style.transform='none';var sr=st.getBoundingClientRect(),minX=0,minY=0;" +
  'var maxX=Math.max(960,st.scrollWidth,st.offsetWidth),maxY=Math.max(540,st.scrollHeight,st.offsetHeight);' +
  "Array.prototype.forEach.call(st.querySelectorAll('*'),function(n){var cs=getComputedStyle(n);if(cs.display==='none'||cs.visibility==='hidden')return;var r=n.getBoundingClientRect();if(!r.width&&!r.height)return;minX=Math.min(minX,r.left-sr.left);minY=Math.min(minY,r.top-sr.top);maxX=Math.max(maxX,r.right-sr.left);maxY=Math.max(maxY,r.bottom-sr.top);});" +
  'var cw=maxX-minX,ch=maxY-minY,pad=12,s=Math.min((innerWidth-pad*2)/cw,(innerHeight-pad*2)/ch,1);s=Math.max(.1,s);' +
  "var tx=(innerWidth-cw*s)/2-minX*s,ty=(innerHeight-ch*s)/2-minY*s;st.style.transform='translate('+tx+'px,'+ty+'px) scale('+s+')';}" +
  "addEventListener('resize',fit);fit();setTimeout(fit,300);setTimeout(fit,1000);}" +
  "if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',u);else u();})();</scr" + 'ipt>';

// Generated games have a deterministic 960x540 stage. Older saved games
// contain generic fit scripts that cap enlargement at 1x or 1.35x, leaving a
// small game in the centre of a wide slide. This override is appended even
// when a legacy fit marker exists, repairing existing courses in-place.
const GAME_FIT_SNIPPET =
  '<style id="__scormify_game_fit_v5">' +
  'html,body{margin:0!important;padding:0!important;width:100%!important;height:100%!important;overflow:hidden!important;}' +
  '#__stage{width:960px!important;height:540px!important;min-width:960px!important;min-height:540px!important;' +
  'max-width:none!important;max-height:none!important;transform-origin:0 0!important;}' +
  '</style><script>(function(){function f(){var st=document.getElementById("__stage");if(!st)return;var p=4;' +
  'var s=Math.max(.1,Math.min((innerWidth-p*2)/960,(innerHeight-p*2)/540));' +
  'var x=(innerWidth-960*s)/2,y=(innerHeight-540*s)/2;' +
  'st.style.setProperty("width","960px","important");st.style.setProperty("height","540px","important");' +
  'st.style.setProperty("transform-origin","0 0","important");' +
  'st.style.setProperty("transform","translate("+x+"px,"+y+"px) scale("+s+")","important");}' +
  // Legacy fixed-stage scripts may run again at 300ms and 1000ms. Reassert
  // the game viewport briefly through hydration so the old 1x scale can
  // never become the final visual state (the visible grow-then-shrink bug).
  'addEventListener("resize",f);f();var n=0,t=setInterval(function(){f();if(++n>=24)clearInterval(t)},100);})();</scr' + 'ipt>';

const injectDocumentSnippet = (html, snippet) => {
  const headIdx = html.toLowerCase().lastIndexOf('</head>');
  if (headIdx !== -1) return html.slice(0, headIdx) + snippet + html.slice(headIdx);
  const bodyIdx = html.toLowerCase().lastIndexOf('</body>');
  if (bodyIdx !== -1) return html.slice(0, bodyIdx) + snippet + html.slice(bodyIdx);
  return html + snippet;
};

export const isGeneratedGameHtml = (html) => {
  if (!html || typeof html !== 'string') return false;
  let source = html;
  // Older Agent slides can persist full documents as UTF-8 base64. Detecting
  // only the encoded string made Forca miss the full-slide game viewport.
  if (source.startsWith('__B64__:')) {
    try { source = globalThis.atob(source.slice(8)); } catch (_) { /* keep original */ }
  }
  return /QuestionEngine|SCORMIFY\s+(?:GAMES|ADVENTURES)|EXPEDIÇÃO\s+DO\s+SABER|ARENA\s+DAS\s+PALAVRAS|LABORATÓRIO\s+DA\s+MEMÓRIA/i.test(source)
    && /\b(?:game|app|jogo|quest(?:ion)?engine)\b/i.test(source);
};

export const fitGameElementToSlide = (element, slideWidth = 960, slideHeight = 540) => {
  if (!element || element.type !== 'html') return element;
  const isGame = element.interactiveType === 'game' || element.gameType || element.gameConfig
    || isGeneratedGameHtml(element.htmlContent || '');
  if (!isGame) return element;
  const marginX = Math.max(4, Math.round(slideWidth * 0.01));
  const marginY = Math.max(4, Math.round(slideHeight * 0.01));
  return {
    ...element,
    x: marginX,
    y: marginY,
    width: slideWidth - marginX * 2,
    height: slideHeight - marginY * 2,
    objectFit: 'cover',
    htmlDisplayMode: 'fit',
  };
};

export const wrapInteractiveFullbleed = (html, mode = 'page') => {
  if (!html || typeof html !== 'string') return html;
  const isGeneratedGame = isGeneratedGameHtml(html);
  if (isGeneratedGame && !html.includes('__scormify_game_fit_v5')) {
    const upgraded = html.includes('__stage')
      ? html
      : injectDocumentSnippet(html, html.includes('__scormify_fit_v3') ? FIT_UPGRADE_SNIPPET : FIT_SNIPPET);
    return injectDocumentSnippet(upgraded, GAME_FIT_SNIPPET);
  }
  if (html.includes('__scormify_fit_v3') || html.includes('__scormify_page_mode')) return html;
  if (html.includes('__stage')) return injectDocumentSnippet(html, FIT_UPGRADE_SNIPPET);
  return injectDocumentSnippet(html, mode === 'fit' ? FIT_SNIPPET : PAGE_VIEWPORT_SNIPPET);
};

/**
 * Generate inline CSS styles for RTF content rendering in iframes
 * This is needed because iframes don't have access to external stylesheets
 * @param {Object} options - Style options
 * @param {string} options.textColor - Text color (default: inherit)
 * @param {string} options.backgroundColor - Background color (default: transparent)
 * @returns {string} - CSS string for injection into iframe
 */
export const getRtfContentStyles = (options = {}) => {
  const { textColor = 'inherit', backgroundColor = 'transparent' } = options;
  
  return `
    /* Google Fonts — required for the design-template feature. Without this
       import the iframe falls back to system sans-serif and every "Aplicar
       Tema Visual" preset looks identical because Nunito / Playfair Display /
       JetBrains Mono / Poppins / etc are not shipped by any OS. */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Lato:wght@300;400;700&family=Merriweather:wght@300;400;700&family=Montserrat:wght@300;400;500;600;700&family=Nunito:wght@300;400;600;700&family=Open+Sans:wght@300;400;600;700&family=Oswald:wght@300;400;500;600;700&family=Playfair+Display:wght@400;500;600;700&family=Poppins:wght@300;400;500;600;700&family=Raleway:wght@300;400;500;600;700&family=Roboto:wght@300;400;500;700&family=Source+Sans+3:wght@300;400;600;700&family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Georgia&family=Manrope:wght@400;600;700;800&family=Sora:wght@400;600;700&family=Fraunces:wght@400;600;700&family=Source+Serif+4:wght@400;600&family=IBM+Plex+Sans:wght@400;600&family=Archivo:wght@400;600;700&display=swap');

    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body {
      width: 100%;
      height: 100%;
      margin: 0;
      padding: 0;
      font-family: system-ui, -apple-system, sans-serif;
      font-size: 14px;
      line-height: 1.5;
      color: ${textColor};
      background: ${backgroundColor};
    }
    body {
      padding: 8px;
      overflow: auto;
      word-wrap: break-word;
      overflow-wrap: break-word;
    }
    
    /* Content wrapper for proper text flow and image clearing */
    .content-wrapper {
      width: 100%;
      height: 100%;
    }
    .content-wrapper::after {
      content: '';
      display: table;
      clear: both;
    }
    
    /* Base image styles */
    img {
      max-width: 100%;
      height: auto;
      border: none;
      outline: none;
    }
    
    /* Float left images */
    img.rtf-image-float-left,
    body img.rtf-image-float-left,
    img[style*="float: left"],
    img[style*="float:left"] {
      float: left !important;
      max-width: 45% !important;
      margin-right: 16px !important;
      margin-bottom: 12px !important;
      height: auto !important;
      object-fit: contain !important;
    }
    
    /* Float right images */
    img.rtf-image-float-right,
    body img.rtf-image-float-right,
    img[style*="float: right"],
    img[style*="float:right"] {
      float: right !important;
      max-width: 45% !important;
      margin-left: 16px !important;
      margin-bottom: 12px !important;
      height: auto !important;
      object-fit: contain !important;
    }
    
    /* Centered images */
    img.rtf-image-center {
      display: inline-block !important;
      max-width: 80% !important;
      height: auto !important;
    }
    
    /* Inline/block images */
    img.rtf-image-inline {
      display: block !important;
      max-width: 100% !important;
      height: auto !important;
      margin: 8px 0 !important;
    }
    
    /* Typography */
    p { margin: 0 0 1em 0; }
    p:last-child { margin-bottom: 0; }
    h1, h2, h3, h4, h5, h6 { margin: 0 0 0.5em 0; line-height: 1.3; }
    ul, ol { margin: 0 0 1em 1.5em; padding: 0; }
    li { margin: 0 0 0.25em 0; }
    a { color: #3b82f6; text-decoration: underline; }
    blockquote { margin: 1em 0; padding-left: 1em; border-left: 3px solid #cbd5e1; color: #64748b; }
    pre, code { font-family: monospace; background: rgba(0, 0, 0, 0.05); border-radius: 4px; }
    pre { padding: 1em; overflow-x: auto; }
    code { padding: 0.2em 0.4em; }
    table { width: 100%; border-collapse: collapse; margin: 1em 0; }
    th, td { border: 1px solid #e2e8f0; padding: 0.5em; text-align: left; }
    th { background: rgba(0, 0, 0, 0.05); font-weight: 600; }
  `;
};
