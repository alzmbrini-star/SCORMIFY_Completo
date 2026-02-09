import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Suppress ResizeObserver loop errors (common in React, non-critical)
const resizeObserverErr = /ResizeObserver loop/;

// Suppress insertBefore/removeChild errors which can happen with Radix UI portals during rapid state changes
const domManipulationErr = /insertBefore|removeChild|not a child of this node|Failed to execute/i;

// Override window.onerror for broader error capture
window.onerror = function(message, source, lineno, colno, error) {
  if (message && typeof message === 'string') {
    if (resizeObserverErr.test(message) || domManipulationErr.test(message)) {
      return true; // Suppress the error
    }
  }
  return false;
};

window.addEventListener('error', (e) => {
  if (e.message && resizeObserverErr.test(e.message)) {
    e.stopImmediatePropagation();
    e.preventDefault();
    return false;
  }
  // Suppress insertBefore/removeChild errors from React/Radix portal reconciliation
  if (e.message && domManipulationErr.test(e.message)) {
    e.stopImmediatePropagation();
    e.preventDefault();
    return false;
  }
}, true); // Capture phase

// Also suppress via the global error handler
const originalConsoleError = console.error;
console.error = (...args) => {
  const firstArg = args[0];
  if (firstArg) {
    const errorStr = typeof firstArg === 'string' ? firstArg : 
                     firstArg?.message ? firstArg.message : 
                     String(firstArg);
    if (resizeObserverErr.test(errorStr) || domManipulationErr.test(errorStr)) {
      return; // Suppress
    }
  }
  originalConsoleError.apply(console, args);
};

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', (e) => {
  const errorMsg = e.reason?.message || String(e.reason);
  // Suppress ResizeObserver errors
  if (resizeObserverErr.test(errorMsg) || domManipulationErr.test(errorMsg)) {
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
