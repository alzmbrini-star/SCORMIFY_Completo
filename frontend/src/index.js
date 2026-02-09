import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Suppress ResizeObserver loop errors (common in React, non-critical)
// This error is benign and happens when resize observations can't be delivered in a single animation frame
const resizeObserverErr = /ResizeObserver loop/;

// Suppress insertBefore errors which can happen with Radix UI portals during rapid state changes
const insertBeforeErr = /insertBefore|not a child of this node/;

window.addEventListener('error', (e) => {
  if (e.message && resizeObserverErr.test(e.message)) {
    e.stopImmediatePropagation();
    e.preventDefault();
    return false;
  }
  // Suppress insertBefore errors from React/Radix portal reconciliation
  if (e.message && insertBeforeErr.test(e.message)) {
    console.warn('Suppressed portal reconciliation error:', e.message);
    e.stopImmediatePropagation();
    e.preventDefault();
    return false;
  }
});

// Also suppress via the global error handler
const originalConsoleError = console.error;
console.error = (...args) => {
  if (args[0] && typeof args[0] === 'string' && resizeObserverErr.test(args[0])) {
    return;
  }
  // Suppress insertBefore errors
  if (args[0] && typeof args[0] === 'string' && insertBeforeErr.test(args[0])) {
    console.warn('Suppressed console error:', args[0].substring(0, 100));
    return;
  }
  originalConsoleError.apply(console, args);
};

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', (e) => {
  // Suppress ResizeObserver errors
  if (e.reason?.message && resizeObserverErr.test(e.reason.message)) {
    e.preventDefault();
    return;
  }
  // Suppress Axios 404 errors (handled by components)
  if (e.reason?.response?.status === 404) {
    console.warn('Unhandled 404:', e.reason?.config?.url);
    e.preventDefault();
    return;
  }
  // Suppress network errors (handled by components)
  if (e.reason?.code === 'ERR_NETWORK' || e.reason?.message?.includes('Network Error')) {
    console.warn('Network error suppressed');
    e.preventDefault();
    return;
  }
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
