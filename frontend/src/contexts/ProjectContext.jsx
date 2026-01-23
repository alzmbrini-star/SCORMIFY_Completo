import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import axios from 'axios';

const API_URL = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Configure axios to handle 404 errors gracefully
axios.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 404) {
      console.warn('Resource not found (404):', error.config?.url);
      // Don't show error overlay for 404s - let the component handle it
    }
    return Promise.reject(error);
  }
);

const ProjectContext = createContext();

export const useProject = () => {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error('useProject must be used within ProjectProvider');
  }
  return context;
};

export const ProjectProvider = ({ children }) => {
  const [projects, setProjects] = useState([]);
  const [currentProject, setCurrentProject] = useState(null);
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [selectedElementId, setSelectedElementId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchProjects = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_URL}/projects`);
      setProjects(response.data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchProject = useCallback(async (projectId) => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_URL}/projects/${projectId}`);
      setCurrentProject(response.data);
      setCurrentSlideIndex(0);
      setSelectedElementId(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const createProject = useCallback(async (name, description = '') => {
    try {
      setLoading(true);
      const response = await axios.post(`${API_URL}/projects`, { name, description });
      setProjects(prev => [response.data, ...prev]);
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const updateProject = useCallback(async (projectId, data) => {
    try {
      const response = await axios.put(`${API_URL}/projects/${projectId}`, data);
      setProjects(prev => prev.map(p => p.id === projectId ? response.data : p));
      if (currentProject?.id === projectId) {
        setCurrentProject(response.data);
      }
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject]);

  const deleteProject = useCallback(async (projectId) => {
    try {
      await axios.delete(`${API_URL}/projects/${projectId}`);
      setProjects(prev => prev.filter(p => p.id !== projectId));
      if (currentProject?.id === projectId) {
        setCurrentProject(null);
      }
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject]);

  const uploadPPT = useCallback(async (file, projectName) => {
    try {
      setLoading(true);
      const formData = new FormData();
      formData.append('file', file);
      if (projectName) {
        formData.append('project_name', projectName);
      }
      const response = await axios.post(`${API_URL}/ppt/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const checkJobStatus = useCallback(async (jobId) => {
    try {
      const response = await axios.get(`${API_URL}/job/${jobId}`);
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, []);

  const saveCourse = useCallback(async () => {
    if (!currentProject) return;
    try {
      await axios.post(`${API_URL}/course/${currentProject.id}/save`, currentProject.course);
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject]);

  const addSlide = useCallback(async (slideData = {}) => {
    if (!currentProject) return;
    try {
      const response = await axios.post(
        `${API_URL}/projects/${currentProject.id}/slides`,
        { title: slideData.title || 'New Slide', background: slideData.background || '#FFFFFF' }
      );
      setCurrentProject(prev => ({
        ...prev,
        course: {
          ...prev.course,
          slides: [...(prev.course.slides || []), response.data]
        }
      }));
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject]);

  const updateSlide = useCallback(async (slideId, data) => {
    if (!currentProject) return;
    try {
      const response = await axios.put(
        `${API_URL}/projects/${currentProject.id}/slides/${slideId}`,
        data
      );
      setCurrentProject(prev => ({
        ...prev,
        course: {
          ...prev.course,
          slides: prev.course.slides.map(s => s.id === slideId ? response.data : s)
        }
      }));
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject]);

  const deleteSlide = useCallback(async (slideId) => {
    if (!currentProject) return;
    try {
      await axios.delete(`${API_URL}/projects/${currentProject.id}/slides/${slideId}`);
      setCurrentProject(prev => {
        const newSlides = prev.course.slides.filter(s => s.id !== slideId);
        return {
          ...prev,
          course: { ...prev.course, slides: newSlides }
        };
      });
      if (currentSlideIndex >= currentProject.course.slides.length - 1) {
        setCurrentSlideIndex(Math.max(0, currentSlideIndex - 1));
      }
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject, currentSlideIndex]);

  const duplicateSlide = useCallback(async (slideId) => {
    if (!currentProject) return;
    try {
      const response = await axios.post(
        `${API_URL}/projects/${currentProject.id}/slides/${slideId}/duplicate`
      );
      await fetchProject(currentProject.id);
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject, fetchProject]);

  const reorderSlides = useCallback(async (slideIds) => {
    if (!currentProject) return;
    try {
      await axios.post(
        `${API_URL}/projects/${currentProject.id}/slides/reorder`,
        { slideIds }
      );
      await fetchProject(currentProject.id);
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject, fetchProject]);

  const addElement = useCallback(async (slideId, elementData) => {
    if (!currentProject) return;
    try {
      const response = await axios.post(
        `${API_URL}/projects/${currentProject.id}/slides/${slideId}/elements`,
        elementData
      );
      setCurrentProject(prev => ({
        ...prev,
        course: {
          ...prev.course,
          slides: prev.course.slides.map(s => 
            s.id === slideId 
              ? { ...s, elements: [...(s.elements || []), response.data] }
              : s
          )
        }
      }));
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject]);

  const updateElement = useCallback(async (slideId, elementId, data) => {
    if (!currentProject) return;
    try {
      const response = await axios.put(
        `${API_URL}/projects/${currentProject.id}/slides/${slideId}/elements/${elementId}`,
        data
      );
      setCurrentProject(prev => ({
        ...prev,
        course: {
          ...prev.course,
          slides: prev.course.slides.map(s => 
            s.id === slideId 
              ? { ...s, elements: s.elements.map(e => e.id === elementId ? response.data : e) }
              : s
          )
        }
      }));
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject]);

  const deleteElement = useCallback(async (slideId, elementId) => {
    if (!currentProject) return;
    try {
      await axios.delete(
        `${API_URL}/projects/${currentProject.id}/slides/${slideId}/elements/${elementId}`
      );
      setCurrentProject(prev => ({
        ...prev,
        course: {
          ...prev.course,
          slides: prev.course.slides.map(s => 
            s.id === slideId 
              ? { ...s, elements: s.elements.filter(e => e.id !== elementId) }
              : s
          )
        }
      }));
      setSelectedElementId(null);
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject]);

  const uploadMedia = useCallback(async (file) => {
    if (!currentProject) return;
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await axios.post(
        `${API_URL}/projects/${currentProject.id}/media`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject]);

  const uploadSlideAudio = useCallback(async (slideId, file, audioType = 'narration') => {
    if (!currentProject) return;
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('audio_type', audioType);
      const response = await axios.post(
        `${API_URL}/projects/${currentProject.id}/slides/${slideId}/audio`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      await fetchProject(currentProject.id);
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject, fetchProject]);

  const setGlobalAudio = useCallback(async (file) => {
    if (!currentProject) return;
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await axios.post(
        `${API_URL}/projects/${currentProject.id}/global-audio`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      await fetchProject(currentProject.id);
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject, fetchProject]);

  const removeGlobalAudio = useCallback(async () => {
    if (!currentProject) return;
    try {
      await axios.delete(`${API_URL}/projects/${currentProject.id}/global-audio`);
      await fetchProject(currentProject.id);
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject, fetchProject]);

  const updateGlobalAudioVolume = useCallback(async (volume) => {
    if (!currentProject) return;
    try {
      const response = await axios.put(
        `${API_URL}/projects/${currentProject.id}/global-audio/volume`,
        null,
        { params: { volume } }
      );
      await fetchProject(currentProject.id);
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject, fetchProject]);

  const removeSlideAudio = useCallback(async (slideId, audioId) => {
    if (!currentProject) return;
    try {
      await axios.delete(
        `${API_URL}/projects/${currentProject.id}/slides/${slideId}/audio/${audioId}`
      );
      await fetchProject(currentProject.id);
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject, fetchProject]);

  const updateSlideAudioVolume = useCallback(async (slideId, audioId, volume) => {
    if (!currentProject) return;
    try {
      const response = await axios.put(
        `${API_URL}/projects/${currentProject.id}/slides/${slideId}/audio/${audioId}/volume`,
        null,
        { params: { volume } }
      );
      await fetchProject(currentProject.id);
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject, fetchProject]);

  const addAnnotation = useCallback(async (slideId, annotationData) => {
    if (!currentProject) return;
    try {
      const response = await axios.post(
        `${API_URL}/projects/${currentProject.id}/slides/${slideId}/annotations`,
        annotationData
      );
      // Update local state without resetting slide index
      setCurrentProject(prev => {
        if (!prev) return prev;
        const updatedSlides = prev.course.slides.map(slide => {
          if (slide.id === slideId) {
            return {
              ...slide,
              annotations: [...(slide.annotations || []), response.data]
            };
          }
          return slide;
        });
        return {
          ...prev,
          course: {
            ...prev.course,
            slides: updatedSlides
          }
        };
      });
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject]);

  const deleteAnnotation = useCallback(async (slideId, annotationId) => {
    if (!currentProject) return;
    try {
      await axios.delete(
        `${API_URL}/projects/${currentProject.id}/slides/${slideId}/annotations/${annotationId}`
      );
      // Update local state without resetting slide index
      setCurrentProject(prev => {
        if (!prev) return prev;
        const updatedSlides = prev.course.slides.map(slide => {
          if (slide.id === slideId) {
            return {
              ...slide,
              annotations: (slide.annotations || []).filter(a => a.id !== annotationId)
            };
          }
          return slide;
        });
        return {
          ...prev,
          course: {
            ...prev.course,
            slides: updatedSlides
          }
        };
      });
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [currentProject]);

  const exportScorm = useCallback(async () => {
    if (!currentProject) return;
    try {
      setLoading(true);
      const response = await axios.post(`${API_URL}/course/${currentProject.id}/export-scorm`);
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [currentProject]);

  const currentSlide = currentProject?.course?.slides?.[currentSlideIndex] || null;
  const selectedElement = currentSlide?.elements?.find(e => e.id === selectedElementId) || null;

  const value = {
    projects,
    currentProject,
    currentSlideIndex,
    currentSlide,
    selectedElementId,
    selectedElement,
    loading,
    error,
    setCurrentSlideIndex,
    setSelectedElementId,
    setCurrentProject,
    fetchProjects,
    fetchProject,
    createProject,
    updateProject,
    deleteProject,
    uploadPPT,
    checkJobStatus,
    saveCourse,
    addSlide,
    updateSlide,
    deleteSlide,
    duplicateSlide,
    reorderSlides,
    addElement,
    updateElement,
    deleteElement,
    uploadMedia,
    uploadSlideAudio,
    setGlobalAudio,
    removeGlobalAudio,
    updateGlobalAudioVolume,
    removeSlideAudio,
    updateSlideAudioVolume,
    addAnnotation,
    deleteAnnotation,
    exportScorm,
    clearError: () => setError(null)
  };

  return (
    <ProjectContext.Provider value={value}>
      {children}
    </ProjectContext.Provider>
  );
};
