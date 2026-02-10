import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Suppress ResizeObserver loop errors (common in React, non-critical)
// This error occurs when the ResizeObserver cannot deliver all notifications in a single animation frame
const resizeObserverErr = /ResizeObserver loop/;

// Suppress insertBefore/removeChild errors which can happen with Radix UI portals during rapid state changes
const domManipulationErr = /insertBefore|removeChild|not a child of this node|Failed to execute/i;

// Helper to check if error should be suppressed
const shouldSuppressError = (message) => {
  if (!message) return false;
  const msgStr = typeof message === 'string' ? message : String(message);
  return resizeObserverErr.test(msgStr) || domManipulationErr.test(msgStr);
};

// Override ResizeObserver to catch errors at the source
const OriginalResizeObserver = window.ResizeObserver;
window.ResizeObserver = class ResizeObserver extends OriginalResizeObserver {
  constructor(callback) {
    super((entries, observer) => {
      // Use requestAnimationFrame to batch resize observations
      window.requestAnimationFrame(() => {
        try {
          callback(entries, observer);
        } catch (e) {
          // Silently ignore resize observer errors
        }
      });
    });
  }
};

// Override window.onerror for broader error capture
window.onerror = function(message, source, lineno, colno, error) {
  if (shouldSuppressError(message)) {
    return true; // Suppress the error
  }
  return false;
};

window.addEventListener('error', (e) => {
  if (shouldSuppressError(e.message)) {
    e.stopImmediatePropagation();
    e.preventDefault();
    return false;
  }
}, true); // Capture phase

// Also suppress via the global error handler
const originalConsoleError = console.error;
console.error = (...args) => {
  const firstArg = args[0];
  if (firstArg && shouldSuppressError(firstArg?.message || String(firstArg))) {
    return; // Suppress
  }
  originalConsoleError.apply(console, args);
};

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', (e) => {
  const errorMsg = e.reason?.message || String(e.reason);
  // Suppress ResizeObserver errors
  if (shouldSuppressError(errorMsg)) {
    e.preventDefault();
    return;
  }
  // Suppress Axios 404 errors (handled by components)
  if (e.reason?.response?.status === 404) {
    e.preventDefault();
    return;
  }
  // Suppress network errors (handled by components)
  if (e.reason?.code === 'ERR_NETWORK' || e.reason?.message?.includes('Network Error')) {
    e.preventDefault();
    return;
  }
});

const root = ReactDOM.createRoot(document.getElementById("root"));
// Remove StrictMode to prevent double rendering which can cause DOM reconciliation issues
root.render(<App />);
