import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import Timeline from './Timeline';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock('../ui/button', () => {
  const ReactModule = require('react');
  return {
    Button: ({ children, ...props }) => ReactModule.createElement('button', props, children),
  };
});

jest.mock('../ui/input', () => {
  const ReactModule = require('react');
  return {
    Input: (props) => ReactModule.createElement('input', props),
  };
});

jest.mock('../ui/slider', () => {
  const ReactModule = require('react');
  return {
    Slider: ({ className, 'data-testid': dataTestId }) => ReactModule.createElement(
      'div',
      { className, 'data-testid': dataTestId },
    ),
  };
});

jest.mock('../ui/tooltip', () => {
  const ReactModule = require('react');
  const Wrapper = ({ children }) => ReactModule.createElement(
    ReactModule.Fragment,
    null,
    children,
  );
  return {
    Tooltip: Wrapper,
    TooltipContent: Wrapper,
    TooltipTrigger: Wrapper,
  };
});

describe('Timeline clip dragging', () => {
  let container;
  let root;
  let originalRequestAnimationFrame;
  let originalCancelAnimationFrame;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    originalRequestAnimationFrame = window.requestAnimationFrame;
    originalCancelAnimationFrame = window.cancelAnimationFrame;
    window.requestAnimationFrame = (callback) => {
      callback();
      return 1;
    };
    window.cancelAnimationFrame = jest.fn();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    window.requestAnimationFrame = originalRequestAnimationFrame;
    window.cancelAnimationFrame = originalCancelAnimationFrame;
  });

  it('previews locally and persists only once when the drag ends', async () => {
    const onUpdateElement = jest.fn(() => Promise.resolve({
      id: 'element-1',
      startTime: 3,
      endTime: 5,
    }));
    const slide = {
      id: 'slide-1',
      duration: 10,
      elements: [{
        id: 'element-1',
        type: 'text',
        content: 'Elemento',
        startTime: 1,
        endTime: 3,
      }],
      annotations: [],
      audio: [],
    };

    await act(async () => {
      root.render(
        <Timeline
          slide={slide}
          onUpdateElement={onUpdateElement}
        />,
      );
    });

    const tracks = container.querySelector('[data-testid="timeline-tracks"]');
    const clip = container.querySelector('[data-testid="timeline-clip-element-1"]');
    tracks.getBoundingClientRect = () => ({
      left: 0,
      right: 1000,
      top: 0,
      bottom: 200,
      width: 1000,
      height: 200,
      x: 0,
      y: 0,
      toJSON: () => {},
    });

    act(() => {
      clip.dispatchEvent(new MouseEvent('mousedown', {
        bubbles: true,
        clientX: 100,
        button: 0,
      }));
    });

    act(() => {
      window.dispatchEvent(new MouseEvent('mousemove', {
        bubbles: true,
        clientX: 300,
        button: 0,
      }));
    });

    expect(onUpdateElement).not.toHaveBeenCalled();
    expect(clip.style.left).toBe('30%');

    await act(async () => {
      window.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
      await Promise.resolve();
    });

    expect(onUpdateElement).toHaveBeenCalledTimes(1);
    expect(onUpdateElement).toHaveBeenCalledWith('element-1', {
      startTime: 3,
      endTime: 5,
    });
  });
});
