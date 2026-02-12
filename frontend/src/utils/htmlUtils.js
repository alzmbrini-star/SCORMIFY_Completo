/**
 * HTML Utility functions for sanitizing and processing HTML content
 * Used across Editor, SlideCanvas, and export components
 */

/**
 * Sanitize HTML content by removing Tailwind CSS variables and editor artifacts
 * This prevents style pollution from the main application affecting rendered content
 * @param {string} htmlContent - The HTML string to sanitize
 * @returns {string} - Cleaned HTML string
 */
export const sanitizeHtmlForDisplay = (htmlContent) => {
  if (!htmlContent) return htmlContent;
  
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
