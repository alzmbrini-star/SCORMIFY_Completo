import React, { act, useState } from 'react';
import { createRoot } from 'react-dom/client';
import SlideCanvas from './SlideCanvas';
import AnnotationToolbar from './AnnotationToolbar';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const mockAddAnnotation = jest.fn(async () => {});
jest.mock('../assessment/AssessmentBuilder', () => ({ buildAssessmentHtml: jest.fn() }));
jest.mock('../../contexts/ProjectContext', () => ({ useProject: () => ({ addAnnotation: mockAddAnnotation, deleteAnnotation: jest.fn() }) }));
jest.mock('../ui/tooltip', () => ({ Tooltip: ({ children }) => children, TooltipTrigger: ({ children }) => children, TooltipContent: () => null }));
jest.mock('../ui/popover', () => ({ Popover: ({ children }) => children, PopoverTrigger: ({ children }) => children, PopoverContent: ({ children }) => children }));
jest.mock('../ui/slider', () => ({ Slider: () => null }));

const slide = { id: 'slide-1', width: 960, height: 540, duration: 10, background: '#fff', elements: [] };
function Harness({ mode, saved = [] }) {
  const [color, setColor] = useState('#EF4444');
  const [width, setWidth] = useState(6);
  return <>
    <AnnotationToolbar annotationMode={mode} setAnnotationMode={() => {}} annotationColor={color} setAnnotationColor={setColor} strokeWidth={width} setStrokeWidth={setWidth} />
    <SlideCanvas slide={{ ...slide, annotations: saved }} annotationMode={mode} annotationColor={color} annotationStrokeWidth={width} onSelectElement={() => {}} />
  </>;
}
function pointer(target, type, x, y) {
  const event = new MouseEvent(type, { bubbles: true, clientX: x, clientY: y, button: 0, buttons: type === 'pointerup' ? 0 : 1 });
  Object.defineProperty(event, 'pointerId', { value: 7 });
  target.dispatchEvent(event);
}

describe('annotation style from toolbar through drawing and persistence', () => {
  let root, container;
  beforeEach(() => {
    mockAddAnnotation.mockClear();
    global.ResizeObserver = class { observe() {} disconnect() {} };
    container = document.createElement('div'); document.body.appendChild(container);
    root = createRoot(container);
  });
  afterEach(() => { act(() => root.unmount()); container.remove(); delete global.ResizeObserver; });

  test('native color picker accepts a custom light blue, not just preset swatches', async () => {
    act(() => root.render(<Harness mode="freehand" />));
    const picker = container.querySelector('input[type="color"]');
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(picker, '#83d9f1');
      picker.dispatchEvent(new Event('input', { bubbles: true }));
    });
    const canvas = container.querySelector('[data-testid="slide-canvas"]');
    canvas.getBoundingClientRect = () => ({ left: 0, top: 0, width: 960, height: 540 });
    act(() => pointer(canvas, 'pointerdown', 20, 20));
    act(() => pointer(window, 'pointermove', 80, 70));
    act(() => pointer(window, 'pointermove', 160, 130));
    expect(canvas.querySelector('[stroke="#83d9f1"]')).not.toBeNull();
    await act(async () => pointer(window, 'pointerup', 160, 130));
    expect(mockAddAnnotation.mock.calls[0][1].color).toBe('#83d9f1');
  });

  test.each(['freehand', 'arrow', 'circle', 'rectangle'])('%s uses selected color and width in preview and saved payload', async mode => {
    act(() => root.render(<Harness mode={mode} />));
    const swatch = [...container.querySelectorAll('button')].find(button => button.style.backgroundColor === 'rgb(59, 130, 246)');
    act(() => swatch.click());
    expect(container.querySelector('input[type="color"]').value).toBe('#3b82f6');
    const canvas = container.querySelector('[data-testid="slide-canvas"]');
    canvas.getBoundingClientRect = () => ({ left: 0, top: 0, width: 960, height: 540 });
    act(() => pointer(canvas, 'pointerdown', 20, 20));
    act(() => pointer(window, 'pointermove', 80, 70));
    act(() => pointer(window, 'pointermove', 160, 130));
    const shape = canvas.querySelector('[stroke="#3B82F6"]');
    expect(shape).not.toBeNull();
    expect(shape.getAttribute('stroke-width')).toBe('6');
    if (mode === 'arrow') expect(canvas.querySelector('marker polygon').getAttribute('fill')).toBe('#3B82F6');
    await act(async () => pointer(window, 'pointerup', 160, 130));
    expect(mockAddAnnotation).toHaveBeenCalledTimes(1);
    const saved = mockAddAnnotation.mock.calls[0][1];
    expect(saved).toMatchObject({ type: mode, color: '#3B82F6', strokeWidth: 6, includeInExport: true });
    act(() => root.render(<Harness mode={mode} saved={[{ ...saved, id: 'saved-1' }]} />));
    const green = [...container.querySelectorAll('button')].find(button => button.style.backgroundColor === 'rgb(16, 185, 129)');
    act(() => green.click());
    expect(canvas.querySelector('[stroke="#3B82F6"]')).not.toBeNull();
    act(() => pointer(canvas, 'pointerdown', 10, 10));
    act(() => pointer(window, 'pointermove', 50, 50));
    act(() => pointer(window, 'pointermove', 100, 100));
    expect(canvas.querySelector('[stroke="#10B981"]')).not.toBeNull();
    await act(async () => pointer(window, 'pointerup', 100, 100));
    expect(mockAddAnnotation.mock.calls[1][1].color).toBe('#10B981');
  });
});
