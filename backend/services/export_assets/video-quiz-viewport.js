/* Reflow isolated full-slide video activities; never rewrite authored data. */
(function () {
  'use strict';
  window.VideoQuizViewport = {
    fit: function (container, wrapper, slide) {
      var elements = slide.elements || [], item = elements[0], raw = item && item.htmlContent || '';
      if (raw.indexOf('__B64__:') === 0) { try { raw = atob(raw.slice(8)); } catch (_) { raw = ''; } }
      var isolated = elements.length === 1 && item.type === 'html' &&
        (item.videoQuizConfig || /id=["']video-quiz-data["']/.test(raw)) &&
        !(slide.annotations || []).length &&
        (item.x || 0) <= 20 && (item.y || 0) <= 20 &&
        item.width >= (slide.width || 960) * .9 && item.height >= (slide.height || 540) * .9;
      container.style.flexShrink = '0';
      if (!isolated) { delete container.dataset.videoQuizFluid; return false; }
      var rect = wrapper.getBoundingClientRect(), w = Math.max(1, rect.width - 12), h = Math.max(1, rect.height - 12);
      container.dataset.videoQuizFluid = 'true';
      container.style.width = w + 'px'; container.style.height = h + 'px';
      container.style.transform = 'none'; container.style.transformOrigin = '0 0';
      container.style.margin = '0'; container.style.boxShadow = 'none';
      var element = container.querySelector('.slide-element');
      if (element) {
        element.style.left = '0'; element.style.top = '0';
        element.style.width = '100%'; element.style.height = '100%';
      }
      return true;
    }
  };
})();
