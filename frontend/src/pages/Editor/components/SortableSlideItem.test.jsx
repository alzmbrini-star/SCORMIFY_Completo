import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import SortableSlideItem from './SortableSlideItem';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
jest.mock('@/lib/utils', () => jest.requireActual('../../../lib/utils'), { virtual: true });
jest.mock('@dnd-kit/sortable', () => ({ useSortable: () => ({ attributes: {}, listeners: {}, setNodeRef: () => {}, transform: null }) }));
jest.mock('./SlideThumbnailContent', () => () => <div>Prévia</div>);
jest.mock('../utils', () => ({ getThumbAssetUrl: value => value }));
// Menu behavior is owned by Radix; these tests cover the slide selection UI.
jest.mock('../../../components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }) => <>{children}</>,
  DropdownMenuContent: () => null,
  DropdownMenuItem: () => null,
}));

describe('Editor slide thumbnail identification', () => {
  let root, container;
  beforeEach(() => {
    global.ResizeObserver = class { observe() {} disconnect() {} };
    container = document.createElement('div'); document.body.appendChild(container);
    root = createRoot(container);
  });
  afterEach(() => { act(() => root.unmount()); container.remove(); });

  const slides = [
    { id: 'first', title: 'Introdução', elements: [{ id: 'text' }] },
    { id: 'second', title: 'Atividade', elements: [] },
  ];
  function render(active, onClick = jest.fn()) {
    act(() => root.render(<>{slides.map((slide, index) => <SortableSlideItem key={slide.id} slide={slide} index={index} isActive={active === index} onClick={() => onClick(index)} onDuplicate={jest.fn()} onDelete={jest.fn()} />)}</>));
  }

  test('always shows unscaled numbers, including slides with content', () => {
    render(0);
    expect([...container.querySelectorAll('.slide-thumbnail-number')].map(el => el.textContent)).toEqual(['1', '2']);
    expect(container.querySelector('.slide-thumbnail-number').parentElement.dataset.testid).toBe('slide-0');
  });

  test('moves the active border, label and accessible current state with the canvas', () => {
    render(0);
    expect(container.querySelectorAll('.slide-thumbnail.active')).toHaveLength(1);
    expect(container.querySelector('[aria-current="step"]').getAttribute('aria-label')).toBe('Slide 1: Introdução');
    render(1);
    expect(container.querySelector('.slide-thumbnail.active').dataset.testid).toBe('slide-1');
    expect(container.querySelectorAll('.slide-thumbnail-current')).toHaveLength(1);
    expect(container.querySelector('[aria-current="step"]').getAttribute('aria-label')).toBe('Slide 2: Atividade');
  });

  test('selects once through a native keyboard-accessible button without hiding slide actions', () => {
    const select = jest.fn(); render(0, select);
    act(() => container.querySelectorAll('.slide-thumbnail-select')[1].click());
    expect(select.mock.calls).toEqual([[1]]);
    expect(container.querySelector('[aria-label="Opções do slide 2"]')).not.toBeNull();
    expect(container.querySelector('[aria-label="Mover slide 2"]')).not.toBeNull();
  });
});
