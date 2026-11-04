import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.video_quiz import build_video_quiz,normalize_video_quiz
from services.video_quiz_playback import upgrade_video_quiz_playback,refresh_video_quiz_documents

def sample(graded=False):
 return {'src':'https://example.org/alpha.webm','instanceId':'e','graded':graded,'checkpoints':[
  {'at':n,'question':q,'options':['Errada','Certa'],'correctIndex':1,'explanation':'Certa é a resposta.','maxAttempts':2} for n,q in [(5,'Primeira?'),(10,'Segunda?')]]}

def test_legacy_defaults_free_and_keeps_its_original_resume_key():
 old=sample();del old['graded']
 free=normalize_video_quiz(old);graded=normalize_video_quiz(sample(True))
 assert free['graded'] is False
 assert free['key']==normalize_video_quiz(sample(False))['key']
 assert graded['key']!=free['key'] and graded['graded'] is True

def test_legacy_runtime_upgrade_preserves_snapshot_and_is_idempotent():
 config,html=build_video_quiz(sample())
 old=html.replace('id="video-quiz-runtime-v2"','id="legacy-player"')
 before=old.split('<script id="video-quiz-data" type="application/json">')[1].split('</script>')[0]
 upgraded=upgrade_video_quiz_playback(old)
 assert 'id="video-quiz-runtime-v2"' in upgraded
 assert before==upgraded.split('<script id="video-quiz-data" type="application/json">')[1].split('</script>')[0]
 assert upgrade_video_quiz_playback(upgraded)==upgraded
 project={'course':{'slides':[{'id':'s','elements':[{'id':'e','type':'html','htmlContent':old,'width':1920,'height':820}]}]}}
 refresh_video_quiz_documents(project)
 assert project['course']['slides'][0]['elements'][0]['width']==1920

def test_graded_and_free_runtime_and_trusted_host_bridge():
 root=Path(__file__).resolve().parents[2]
 payload={'ungraded':build_video_quiz(sample())[1],'graded':build_video_quiz(sample(True))[1],
          'host':(root/'backend/services/export_assets/video-quiz-host.js').read_text(encoding='utf-8')}
 result=subprocess.run([shutil.which('node'),str(root/'tests/video-quiz-modes.cjs')],input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True,cwd=root)
 assert result.returncode==0,result.stdout+result.stderr

def test_singlepage_publishes_trusted_grading_attributes(tmp_path):
 from services.single_page_exporter import _render_html_element_inner
 config,html=build_video_quiz(sample(True))
 rendered=_render_html_element_inner({'type':'html','htmlContent':html,'height':540},'p',str(tmp_path),'',0,0)
 assert 'data-video-quiz-graded="true"' in rendered and 'data-video-quiz-total="2"' in rendered
 assert config['key'] in rendered
