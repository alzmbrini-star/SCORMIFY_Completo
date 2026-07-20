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

// Auto-fit wrapper for full-document interactive HTML (simulators, infographics,
// etc). Mirrors backend _FIT_SNIPPET in services/ai_agent.py — content designed
// for a 960x540 stage is centered and scaled to fill the element viewport.
// Idempotent: skips content that already contains the #__stage wrapper.
const FIT_SNIPPET =
  '<style>html,body{margin:0!important;padding:0!important;width:100%;height:100%;' +
  'overflow:hidden!important;}body{display:flex!important;align-items:center!important;' +
  'justify-content:center!important;}</style>' +
  "<script>(function(){function b(){var bd=document.body;" +
  "if(!bd||document.getElementById('__stage'))return;" +
  "var st=document.createElement('div');st.id='__stage';" +
  "st.style.cssText='width:960px;flex:0 0 auto;position:relative;transform-origin:center center;';" +
  'while(bd.firstChild){st.appendChild(bd.firstChild);}bd.appendChild(st);' +
  'function fit(){var ch=Math.max(st.scrollHeight,540);var cw=Math.max(st.scrollWidth,960);' +
  'var s=Math.min(window.innerWidth/cw,window.innerHeight/ch);' +
  "st.style.transform='scale('+s+')';}" +
  "window.addEventListener('resize',fit);fit();setTimeout(fit,300);setTimeout(fit,1000);}" +
  "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',b);}" +
  'else{b();}})();</scr' + 'ipt>';

export const wrapInteractiveFullbleed = (html) => {
  if (!html || typeof html !== 'string' || html.includes('__stage')) return html;
  const idx = html.toLowerCase().lastIndexOf('</body>');
  if (idx !== -1) return html.slice(0, idx) + FIT_SNIPPET + html.slice(idx);
  return html + FIT_SNIPPET;
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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Lato:wght@300;400;700&family=Merriweather:wght@300;400;700&family=Montserrat:wght@300;400;500;600;700&family=Nunito:wght@300;400;600;700&family=Open+Sans:wght@300;400;600;700&family=Oswald:wght@300;400;500;600;700&family=Playfair+Display:wght@400;500;600;700&family=Poppins:wght@300;400;500;600;700&family=Raleway:wght@300;400;500;600;700&family=Roboto:wght@300;400;500;700&family=Source+Sans+3:wght@300;400;600;700&family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Georgia&family=Manrope:wght@400;600;700;800&family=Sora:wght@400;600;700&family=Fraunces:wght@400;600;700&family=Source+Serif+4:wght@400;600&family=Space+Grotesk:wght@400;600;700&family=IBM+Plex+Sans:wght@400;600&family=Archivo:wght@400;600;700&display=swap');

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
