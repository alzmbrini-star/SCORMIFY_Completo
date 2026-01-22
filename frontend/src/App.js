import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { ProjectProvider } from './contexts/ProjectContext';
import { Toaster } from './components/ui/sonner';
import Dashboard from './pages/Dashboard';
import Editor from './pages/Editor';
import './index.css';

function App() {
  return (
    <ThemeProvider>
      <ProjectProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/editor/:projectId" element={<Editor />} />
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" />
      </ProjectProvider>
    </ThemeProvider>
  );
}

export default App;
