import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import SlideCanvas from './SlideCanvas';
import { getApiUrl } from '../../utils/apiUrl';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock('../../contexts/ProjectContext', () => ({
  useProject: () => ({
    addAnnotation: jest.fn(() => Promise.resolve()),
    deleteAnnotation: jest.fn(() => Promise.resolve()),
  }),
}));

describe('SlideCanvas element interactions', () => {
  let container;
  let root;
  let resolveSave;
  let onUpdateElement;
  let onDeleteElement;

  const slide = {
    id: 'slide-1',
    width: 960,
    height: 540,
    duration: 10,
    background: '#ffffff',
    elements: [{
      id: 'element-1',
      type: 'html',
      htmlContent: '<!doctype html><html><body><button>Conteúdo interativo</button></body></html>',
      htmlDisplayMode: 'page',
      x: 20,
      y: 30,
      width: 200,
      height: 100,
      style: {},
    }],
  };

  const pointerEvent = (type, init = {}, pointerId = 7) => {
    const event = new MouseEvent(type, init);
    Object.defineProperty(event, 'pointerId', { value: pointerId });
    Object.defineProperty(event, 'pointerType', { value: 'mouse' });
    return event;
  };

  const enablePointerCapture = (target) => {
    target.setPointerCapture = jest.fn();
    target.hasPointerCapture = jest.fn(() => true);
    target.releasePointerCapture = jest.fn();
    return target;
  };

  beforeEach(async () => {
    global.ResizeObserver = class ResizeObserver {
      observe() {}
      disconnect() {}
    };
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    onUpdateElement = jest.fn(() => new Promise((resolve) => {
      resolveSave = resolve;
    }));
    onDeleteElement = jest.fn();

    await act(async () => {
      root.render(
        <SlideCanvas
          slide={slide}
          selectedElementId="element-1"
          onSelectElement={jest.fn()}
          onUpdateElement={onUpdateElement}
          onDeleteElement={onDeleteElement}
        />,
      );
    });

    const canvas = container.querySelector('[data-testid="slide-canvas"]');
    canvas.getBoundingClientRect = () => ({
      left: 0,
      right: 960,
      top: 0,
      bottom: 540,
      width: 960,
      height: 540,
      x: 0,
      y: 0,
      toJSON: () => {},
    });
  });

  it('does not delete the selected element while a modal dialog is open', () => {
    const dialog = document.createElement('div');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('data-state', 'open');
    const button = document.createElement('button');
    dialog.appendChild(button);
    document.body.appendChild(dialog);
    button.focus();

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', {
        key: 'Backspace',
        bubbles: true,
      }));
    });

    expect(onDeleteElement).not.toHaveBeenCalled();
    dialog.remove();
  });

  afterEach(async () => {
    if (resolveSave) {
      await act(async () => {
        resolveSave({ id: 'element-1' });
        await Promise.resolve();
      });
    }
    act(() => root.unmount());
    container.remove();
    delete global.ResizeObserver;
  });

  it('keeps control across an iframe and stops moving immediately on pointer-up', () => {
    const element = container.querySelector('[data-testid="element-element-1"]');
    const moveHandle = enablePointerCapture(
      container.querySelector('[data-testid="move-handle-element-1"]'),
    );

    expect(element.querySelector('iframe')).not.toBeNull();

    act(() => {
      moveHandle.dispatchEvent(pointerEvent('pointerdown', {
        bubbles: true,
        cancelable: true,
        clientX: 50,
        clientY: 60,
        button: 0,
      }));
    });
    expect(moveHandle.setPointerCapture).toHaveBeenCalledWith(7);

    act(() => {
      window.dispatchEvent(pointerEvent('pointermove', {
        bubbles: true,
        clientX: 150,
        clientY: 110,
        buttons: 1,
      }));
    });

    expect(element.style.left).toBe('120px');
    expect(element.style.top).toBe('80px');

    act(() => {
      window.dispatchEvent(pointerEvent('pointerup', { bubbles: true, buttons: 0 }));
    });
    expect(moveHandle.releasePointerCapture).toHaveBeenCalledWith(7);
    expect(onUpdateElement).toHaveBeenCalledTimes(1);
    expect(onUpdateElement).toHaveBeenCalledWith('element-1', { x: 120, y: 80 });

    act(() => {
      window.dispatchEvent(pointerEvent('pointermove', {
        bubbles: true,
        clientX: 400,
        clientY: 300,
        buttons: 0,
      }));
    });

    expect(element.style.left).toBe('120px');
    expect(element.style.top).toBe('80px');
  });

  it('converts legacy percentage HTML dimensions into a valid iframe viewport', async () => {
    const legacySlide = {
      ...slide,
      elements: [{
        ...slide.elements[0],
        x: '0%',
        y: '0%',
        width: '100%',
        height: '100%',
      }],
    };

    await act(async () => {
      root.render(
        <SlideCanvas
          slide={legacySlide}
          selectedElementId="element-1"
          onSelectElement={jest.fn()}
          onUpdateElement={onUpdateElement}
          onDeleteElement={onDeleteElement}
        />,
      );
    });

    const iframe = container.querySelector('[data-testid="element-element-1"] iframe');
    expect(iframe.style.width).toBe('960px');
    expect(iframe.style.height).toBe('540px');
    expect(iframe.getAttribute('style')).not.toContain('%px');
  });

  it('stops resizing immediately on pointer-up while persistence is pending', () => {
    const element = container.querySelector('[data-testid="element-element-1"]');
    const handle = enablePointerCapture(
      container.querySelector('[data-testid="resize-se-element-1"]'),
    );

    act(() => {
      handle.dispatchEvent(pointerEvent('pointerdown', {
        bubbles: true,
        cancelable: true,
        clientX: 220,
        clientY: 130,
        button: 0,
      }));
    });
    expect(handle.setPointerCapture).toHaveBeenCalledWith(7);

    act(() => {
      window.dispatchEvent(pointerEvent('pointermove', {
        bubbles: true,
        clientX: 270,
        clientY: 180,
        buttons: 1,
      }));
    });

    expect(element.style.width).toBe('250px');
    expect(element.style.height).toBe('150px');

    act(() => {
      window.dispatchEvent(pointerEvent('pointerup', { bubbles: true, buttons: 0 }));
    });
    expect(handle.releasePointerCapture).toHaveBeenCalledWith(7);
    expect(onUpdateElement).toHaveBeenCalledTimes(1);
    expect(onUpdateElement).toHaveBeenCalledWith('element-1', {
      x: 20,
      y: 30,
      width: 250,
      height: 150,
    });

    act(() => {
      window.dispatchEvent(pointerEvent('pointermove', {
        bubbles: true,
        clientX: 500,
        clientY: 400,
        buttons: 0,
      }));
    });

    expect(element.style.width).toBe('250px');
    expect(element.style.height).toBe('150px');
  });

  it('preserves double-click text editing after pointer capture was introduced', async () => {
    const textSlide = {
      ...slide,
      elements: [{
        id: 'element-1',
        type: 'text',
        content: 'Texto original',
        x: 20,
        y: 30,
        width: 200,
        height: 100,
        style: { fontSize: 18 },
      }],
    };

    await act(async () => {
      root.render(
        <SlideCanvas
          slide={textSlide}
          selectedElementId="element-1"
          onSelectElement={jest.fn()}
          onUpdateElement={onUpdateElement}
          onDeleteElement={jest.fn()}
        />,
      );
    });

    const element = enablePointerCapture(
      container.querySelector('[data-testid="element-element-1"]'),
    );

    const dispatchMouseClick = () => {
      const down = pointerEvent('pointerdown', {
        bubbles: true,
        cancelable: true,
        clientX: 60,
        clientY: 60,
        button: 0,
      });
      act(() => element.dispatchEvent(down));
      expect(down.defaultPrevented).toBe(false);
      act(() => window.dispatchEvent(pointerEvent('pointerup', {
        bubbles: true,
        buttons: 0,
      })));
      act(() => element.dispatchEvent(new MouseEvent('click', {
        bubbles: true,
        cancelable: true,
        clientX: 60,
        clientY: 60,
        button: 0,
      })));
    };

    dispatchMouseClick();
    dispatchMouseClick();
    act(() => {
      element.dispatchEvent(new MouseEvent('dblclick', {
        bubbles: true,
        cancelable: true,
        clientX: 60,
        clientY: 60,
        button: 0,
      }));
    });

    const textarea = container.querySelector('textarea');
    expect(textarea).not.toBeNull();
    expect(textarea.value).toBe('Texto original');

    act(() => {
      const valueSetter = Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype,
        'value',
      ).set;
      valueSetter.call(textarea, 'Texto atualizado');
      textarea.dispatchEvent(new Event('input', { bubbles: true }));
    });

    await act(async () => {
      await Promise.resolve();
    });

    act(() => {
      textarea.dispatchEvent(new FocusEvent('focusout', { bubbles: true }));
    });

    expect(onUpdateElement).toHaveBeenCalledWith('element-1', {
      content: 'Texto atualizado',
    });
  });

  it('resolves PDF page images against the backend instead of the static frontend', async () => {
    const pdfSlide = {
      ...slide,
      elements: [{
        id: 'element-1',
        type: 'flipbook',
        flipbookType: 'pdf',
        pdfDisplay: 'pages',
        pdfPages: ['/api/projects/project-123/assets/document_p1.png'],
        x: 20,
        y: 30,
        width: 400,
        height: 300,
        style: {},
      }],
    };

    await act(async () => {
      root.render(
        <SlideCanvas
          slide={pdfSlide}
          selectedElementId="element-1"
          onSelectElement={jest.fn()}
          onUpdateElement={onUpdateElement}
          onDeleteElement={jest.fn()}
        />,
      );
    });

    const image = container.querySelector('[data-testid="pdf-pages-element-1"] img');
    expect(image).not.toBeNull();
    expect(image.getAttribute('src')).toBe(
      `${getApiUrl()}/api/projects/project-123/assets/document_p1.png`,
    );
  });

  it('repairs a Whiteboard URL saved with the static frontend origin', async () => {
    const whiteboardSlide = {
      ...slide,
      elements: [{
        id: 'element-1',
        type: 'image',
        src: 'https://scormify-app.onrender.com/api/whiteboard/file/wb_plan_saved.png',
        isWhiteboard: true,
        isAnimatedPng: true,
        x: 20,
        y: 30,
        width: 400,
        height: 300,
        style: {},
      }],
    };

    await act(async () => {
      root.render(
        <SlideCanvas
          slide={whiteboardSlide}
          selectedElementId="element-1"
          onSelectElement={jest.fn()}
          onUpdateElement={onUpdateElement}
          onDeleteElement={jest.fn()}
        />,
      );
    });

    const image = container.querySelector('img');
    expect(image).not.toBeNull();
    expect(image.getAttribute('src')).toBe(
      `${getApiUrl()}/api/whiteboard/file/wb_plan_saved.png`,
    );
  });
});
