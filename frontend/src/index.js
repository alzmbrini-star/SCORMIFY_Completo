import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Suppress ResizeObserver loop errors (common in React, non-critical)
window.addEventListener('error', (e) => {
  if (e.message && e.message.includes('ResizeObserver loop')) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
});

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', (e) => {
  // Suppress ResizeObserver errors
  if (e.reason?.message?.includes('ResizeObserver')) {
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
