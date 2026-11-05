import subprocess
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_scorm_media_timeline_runtime():
    result=subprocess.run([shutil.which('node'),str(ROOT/'tests/video-quiz-scorm-timeline.cjs')],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr

def test_classic_player_uses_media_clock_only_for_video_questions():
    player=(ROOT/'backend/services/export_assets/player.js').read_text(encoding='utf-8')
    assert 'VideoQuizHost.createTimeline(slide)' in player
    assert 'createElementNode(element, mediaTimeline && mediaTimeline.update)' in player
    assert 'mediaTimeline.add(annotationEl, annotation, 1)' in player
    assert 'if (!mediaTimeline && startTime > 0)' in player
    assert 'if (!mediaTimeline && endTime < slideDuration)' in player
    assert 'if (!mediaTimeline) startSlideProgress(slideDuration)' in player
