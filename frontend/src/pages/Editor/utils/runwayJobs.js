// Merge only Runway slots. Never replace unrelated unsaved slide edits.
export function mergeRunwayProject(previous, saved) {
  if (!previous || previous.id !== saved.id) return previous;
  return {...previous, runwayPending:saved.runwayPending || [], course:{...previous.course,
    slides:previous.course.slides.map(slide => {
      const remote = saved.course?.slides?.find(item => item.id === slide.id);
      let duration = Number(slide.duration || 5);
      const elements = (slide.elements || []).map(element => {
        if (!(element.htmlContent || '').includes('data-runway-job=')) return element;
        const replacement = remote?.elements?.find(item => item.id === element.id && item.provider === 'runway');
        if (!replacement) return element;
        const startTime = Number(element.startTime ?? replacement.startTime ?? 0);
        duration = Math.max(duration, startTime + Number(replacement.duration || 5));
        return {...replacement, x:element.x, y:element.y, width:element.width, height:element.height, startTime};
      });
      return {...slide, elements, duration};
    })}};
}
