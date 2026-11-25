/* Shared native Quiz typography. Rendering-only: never rewrites saved config. */
window.ScormifyQuizTypography = (function () {
    function fontSize(config) {
        var value = config && config.fontSize;
        if (typeof value === 'string' && /^\d+(?:\.\d+)?(?:px)?$/.test(value.trim())) value = parseFloat(value);
        return typeof value === 'number' && isFinite(value) && value >= 8 && value <= 96 ? value : 16;
    }
    function bind(container, config) {
        if (!container) return;
        var base = fontSize(config);
        container.dataset.quizTypography = 'v1';
        container.style.setProperty('--quiz-font-size', base + 'px');
        container.style.setProperty('--quiz-question-font-size', (base * 1.125) + 'px');
        container.style.setProperty('--quiz-support-font-size', Math.max(12, base * .875) + 'px');
        container.style.fontSize = base + 'px';
        if (!document.getElementById('scormify-native-quiz-typography')) {
            var style = document.createElement('style');
            style.id = 'scormify-native-quiz-typography';
            var scope = '.quiz-player-container[data-quiz-typography="v1"]';
            style.textContent = scope + ' h3{font-size:var(--quiz-question-font-size)!important;line-height:1.4;overflow-wrap:anywhere;}' +
                scope + ' .quiz-native-option-text{font-size:var(--quiz-font-size)!important;line-height:1.4;overflow-wrap:anywhere;}' +
                scope + ' .quiz-scroll p,' + scope + ' button{font-size:var(--quiz-support-font-size)!important;}' +
                scope + ' .quiz-native-options{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:10px!important;}' +
                scope + ' .quiz-native-options>button{min-width:0;white-space:normal;}' +
                scope + ' .quiz-scroll{min-height:0;}' +
                '@media(max-width:640px){' + scope + ' .quiz-native-options{grid-template-columns:minmax(0,1fr)!important;}}';
            (document.head || document.documentElement).appendChild(style);
        }
    }
    return {fontSize: fontSize, bind: bind};
})();
