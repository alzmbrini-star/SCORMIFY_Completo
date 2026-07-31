import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import SlideCanvas from './SlideCanvas';

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

  const slide = {
    id: 'slide-1',
    width: 960,
    height: 540,
    duration: 10,
    background: '#ffffff',
    elements: [{
      id: 'element-1',
      type: 'shape',
      shapeType: 'rectangle',
      x: 20,
      y: 30,
      width: 200,
      height: 100,
      style: { fill: '#7c3aed' },
    }],
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

    await act(async () => {
      root.render(
        <SlideCanvas
          slide={slide}
          selectedElementId="element-1"
          onSelectElement={jest.fn()}
          onUpdateElement={onUpdateElement}
          onDeleteElement={jest.fn()}
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

  it('stops moving immediately on mouse-up while persistence is pending', () => {
    const element = container.querySelector('[data-testid="element-element-1"]');

    act(() => {
      element.dispatchEvent(new MouseEvent('mousedown', {
        bubbles: true,
        cancelable: true,
        clientX: 50,
        clientY: 60,
        button: 0,
      }));
    });
    act(() => {
      window.dispatchEvent(new MouseEvent('mousemove', {
        bubbles: true,
        clientX: 150,
        clientY: 110,
        buttons: 1,
      }));
    });

    expect(element.style.left).toBe('120px');
    expect(element.style.top).toBe('80px');

    act(() => {
      window.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    });
    expect(onUpdateElement).toHaveBeenCalledTimes(1);
    expect(onUpdateElement).toHaveBeenCalledWith('element-1', { x: 120, y: 80 });

    act(() => {
      window.dispatchEvent(new MouseEvent('mousemove', {
        bubbles: true,
        clientX: 400,
        clientY: 300,
        buttons: 0,
      }));
    });

    expect(element.style.left).toBe('120px');
    expect(element.style.top).toBe('80px');
  });

  it('stops resizing immediately on mouse-up while persistence is pending', () => {
    const element = container.querySelector('[data-testid="element-element-1"]');
    const handle = container.querySelector('[data-testid="resize-se-element-1"]');

    act(() => {
      handle.dispatchEvent(new MouseEvent('mousedown', {
        bubbles: true,
        cancelable: true,
        clientX: 220,
        clientY: 130,
        button: 0,
      }));
    });
    act(() => {
      window.dispatchEvent(new MouseEvent('mousemove', {
        bubbles: true,
        clientX: 270,
        clientY: 180,
        buttons: 1,
      }));
    });

    expect(element.style.width).toBe('250px');
    expect(element.style.height).toBe('150px');

    act(() => {
      window.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    });
    expect(onUpdateElement).toHaveBeenCalledTimes(1);
    expect(onUpdateElement).toHaveBeenCalledWith('element-1', {
      x: 20,
      y: 30,
      width: 250,
      height: 150,
    });

    act(() => {
      window.dispatchEvent(new MouseEvent('mousemove', {
        bubbles: true,
        clientX: 500,
        clientY: 400,
        buttons: 0,
      }));
    });

    expect(element.style.width).toBe('250px');
    expect(element.style.height).toBe('150px');
  });
});
