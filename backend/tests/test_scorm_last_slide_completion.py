from pathlib import Path


EXPORT_ASSETS = Path(__file__).resolve().parents[1] / "services" / "export_assets"


def test_player_initializes_scorm_before_rendering_the_course():
    player = (EXPORT_ASSETS / "player.js").read_text(encoding="utf-8")
    load_start = player.index("function loadCourse(courseData)")
    render_start = player.index("renderSlide(currentSlide);", load_start)
    init_start = player.index("ScormAPI.initialize();", load_start)
    assert init_start < render_start


def test_last_slide_is_visually_completed_only_after_lms_accepts_status():
    player = (EXPORT_ASSETS / "player.js").read_text(encoding="utf-8")
    assert "if (ScormAPI.setComplete())" in player
    assert "courseCompleted = true;" in player
    assert "courseCompleted && index === totalSlides - 1" in player


def test_completion_requires_an_explicit_action_on_the_real_last_slide():
    player = (EXPORT_ASSETS / "player.js").read_text(encoding="utf-8")
    render_section = player[player.index("function renderSlide(index)"):player.index("function checkAndSetCompletion")]
    next_section = player[player.index("function nextSlide()"):player.index("function prevSlide()")]
    completion_section = player[player.index("function checkAndSetCompletion()"):player.index("function onQuizComplete")]
    assert "visitedLastSlide = true;" in render_section
    assert "checkAndSetCompletion();" not in render_section
    assert "completionRequested = true;" in next_section
    assert "if (!completionRequested)" in completion_section
    assert "Concluir curso" in player


def test_scorm_wrapper_rechecks_completion_after_browser_load():
    wrapper = (EXPORT_ASSETS / "scorm-api.js").read_text(encoding="utf-8")
    load_handler = wrapper.index("window.addEventListener('load'")
    assert wrapper.index("ScormAPI.initialize();", load_handler) > load_handler
    assert wrapper.index("CoursePlayer.finalCompletionCheck();", load_handler) > load_handler


def test_scorm_12_final_status_remains_completed():
    wrapper = (EXPORT_ASSETS / "scorm-api.js").read_text(encoding="utf-8")
    set_complete = wrapper[wrapper.index("setComplete: function()"):wrapper.index("setScore: function")]
    assert 'LMSSetValue("cmi.core.lesson_status", "completed")' in set_complete
    assert 'LMSSetValue("cmi.core.lesson_status", "passed")' not in set_complete
