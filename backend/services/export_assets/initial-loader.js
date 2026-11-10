/* Initial visual readiness only. Never changes SCORM results, questions or navigation. */
(function () {
    'use strict';
    var overlay = document.getElementById('scormify-loader');
    if (!overlay || window.ScormifyInitialLoader) return;
    var bar = document.getElementById('scormify-loader-bar');
    var percent = document.getElementById('scormify-loader-percent');
    var finished = false, lastProgress = 0, stableAt = 0, signature = '', startedAt = Date.now();
    var images = new WeakMap(), frameListeners = new WeakSet(), loadedFrames = new WeakSet();
    var ids = new WeakMap(), nextId = 1, timer;
    var message = document.createElement('p');
    message.id = 'scormify-loader-message';
    message.style.cssText = 'max-width:520px;margin:12px 18px 0;text-align:center;color:#cbd5e1;font:14px/1.5 system-ui,sans-serif';
    message.textContent = 'Preparando o conteúdo e as imagens do primeiro slide…';
    var actions = document.createElement('div');
    actions.hidden = true;
    actions.style.cssText = 'gap:10px;flex-wrap:wrap;justify-content:center;margin:16px';
    overlay.appendChild(message); overlay.appendChild(actions);
    function progress(value) {
        lastProgress = Math.max(lastProgress, Math.min(100, value));
        if (bar) bar.style.width = Math.round(lastProgress) + '%';
        if (percent) percent.textContent = Math.round(lastProgress) + '%';
    }
    function finish(manual) {
        if (finished) return;
        finished = true;
        clearInterval(timer);
        progress(100);
        window.ScormifyInitialLoader.ready = true;
        window.dispatchEvent(new CustomEvent('scormify:initial-visual-ready', {detail: {manual: !!manual}}));
        // Give decoded images a paint before exposing the canvas.
        requestAnimationFrame(function () { requestAnimationFrame(function () {
            overlay.classList.add('hidden');
            setTimeout(function () { if (overlay.parentNode) overlay.parentNode.removeChild(overlay); }, 650);
        }); });
    }
    function button(label, handler) {
        var control = document.createElement('button');
        control.type = 'button'; control.textContent = label;
        control.style.cssText = 'min-height:44px;padding:10px 14px;border:1px solid #93c5fd;border-radius:8px;background:#173b62;color:#fff;font:600 14px system-ui,sans-serif;cursor:pointer';
        control.addEventListener('click', handler); actions.appendChild(control);
    }
    button('Tentar novamente', function () { window.location.reload(); });
    button('Continuar mesmo assim', function () { finish(true); });
    function id(node) { if (!ids.has(node)) ids.set(node, nextId++); return ids.get(node); }
    function imageState(image) {
        if (!image.complete) return 'pending';
        if (!image.naturalWidth) return 'failed';
        if (typeof image.decode !== 'function') return 'ready';
        var state = images.get(image);
        if (!state) {
            state = {status: 'pending'}; images.set(image, state);
            try { image.decode().then(function () { state.status = 'ready'; }, function () { state.status = 'failed'; }); }
            catch (_) { state.status = 'failed'; }
        }
        return state.status;
    }
    function collect(root, depth, result) {
        Array.prototype.forEach.call(root.querySelectorAll('img'), function (image) {
            if (!(image.getAttribute('src') || image.getAttribute('srcset'))) return;
            // Lazy images in the initial HTML cannot wait for scrolling under the overlay.
            image.loading = 'eager';
            var state = imageState(image);
            result.ids.push(id(image)); result.total++;
            if (state === 'pending') result.pending++;
            if (state === 'failed') result.failed++;
        });
        if (depth > 4) return;
        Array.prototype.forEach.call(root.querySelectorAll('iframe'), function (frame) {
            if (result.frames++ > 80) return;
            var src = frame.getAttribute('src') || '';
            var srcdoc = frame.getAttribute('srcdoc');
            var doc;
            try { doc = frame.contentDocument; } catch (_) { return; }
            // External video/provider frames are not readable and must not block the course.
            if (!doc) return;
            if (!frameListeners.has(frame)) {
                frameListeners.add(frame);
                frame.addEventListener('load', function () { loadedFrames.add(frame); });
            }
            result.ids.push('f' + id(frame));
            if ((src || srcdoc) && (!doc.body || doc.readyState !== 'complete' ||
                (doc.URL === 'about:blank' && !loadedFrames.has(frame)))) result.pending++;
            if (doc.body) collect(doc.body, depth + 1, result);
        });
    }
    function tick() {
        if (finished) return;
        var root = document.getElementById('slide-container') || document.getElementById('slide-elements') || document.getElementById('slide-canvas') || document.querySelector('main section, article section, section.sp-slide, section[data-slide-index]');
        var elapsed = Date.now() - startedAt;
        if (root && root.children.length) {
            var result = {ids: [], total: 0, pending: 0, failed: 0, frames: 0};
            collect(root, 0, result);
            var current = result.ids.join(',') + ':' + result.pending + ':' + root.children.length;
            if (current !== signature) { signature = current; stableAt = Date.now(); }
            if (result.failed) {
                message.textContent = 'Algumas imagens não puderam ser carregadas. Verifique sua conexão ou tente novamente.';
                actions.hidden = false; actions.style.display = 'flex';
            } else if (!result.pending && Date.now() - stableAt >= 350) {
                finish(false); return;
            }
            progress(result.pending ? 45 + 45 * Math.max(0, result.total - result.pending) / Math.max(1, result.total) : 95);
        } else {
            stableAt = 0; progress(Math.min(35, 5 + elapsed / 600));
        }
        if (elapsed >= 30000) {
            message.textContent = 'O conteúdo está demorando mais que o esperado. Estamos aguardando o curso e suas imagens. Você pode tentar novamente ou continuar mesmo assim.';
            actions.hidden = false; actions.style.display = 'flex';
        }
    }
    window.ScormifyInitialLoader = {ready: false, finish: finish};
    timer = setInterval(tick, 100);
    window.addEventListener('pagehide', function () { clearInterval(timer); });
    tick();
})();
