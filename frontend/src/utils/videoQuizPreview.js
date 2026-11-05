import { videoQuizSnapshot } from './videoQuizDraft';

// Match the export player's isolated-activity rule. Never reflow a custom
// composition with overlays, annotations or other authored elements.
export function fluidVideoQuizSlide(slide) {
  const items=slide?.elements || [], item=items[0];
  return items.length===1 && item.type==='html' && Boolean(videoQuizSnapshot(item)) &&
    !(slide.annotations || []).length && (item.x || 0)<=20 && (item.y || 0)<=20 &&
    item.width >= (slide.width || 960)*.9 && item.height >= (slide.height || 540)*.9;
}
