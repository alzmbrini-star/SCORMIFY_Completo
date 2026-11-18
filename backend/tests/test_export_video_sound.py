import copy
import json
import subprocess
import shutil
from pathlib import Path
from services.html_exporter import generate_html_template
from services.creator_guide import topics_for

ASSETS=Path(__file__).parents[1]/'services/export_assets'

def test_html_embedded_video_gates_without_mutating_course():
    course={'slides':[{'id':'s','width':1280,'height':720,'elements':[{'id':'v','type':'video','src':'movie.mp4','x':0,'y':0,'width':1280,'height':720}]}]}
    before=copy.deepcopy(course)
    html=generate_html_template('Sound',course,1280,720,False)
    assert 'ScormifyMediaSound.hasSound(course)' in html
    assert 'mediaSound.unlock()' in html
    assert "mediaSound.setMuted(isMuted)" in html
    assert 'Autoplay blocked, trying muted' not in html
    assert 'data-intent-muted' in html
    assert course==before

def test_scorm_includes_shared_runtime_and_current_slide_unlock():
    exporter=(ASSETS.parent/'scorm_exporter.py').read_text(encoding='utf-8')
    player=(ASSETS/'player.js').read_text(encoding='utf-8')
    assert '_read_asset("media-sound.js")' in exporter
    assert 'ScormifyMediaSound.hasSound(course)' in player
    assert 'var firstSlide = course.slides[currentSlide]' in player
    assert 'video.muted = true' not in player
    assert 'mediaSound.setVolume(volume)' in player
    template=(ASSETS/'player_template.html').read_text(encoding='utf-8')
    assert 'id="volume-control" style="display:none"' in template
    assert 'Ativar ou silenciar áudio' in template

def test_shared_runtime_blocks_silent_fallback_and_respects_explicit_mute():
    script=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let all=[],gates=0;
const scope={window:{},document:{querySelectorAll:()=>all},WeakMap,WeakSet,Number};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),scope);
const api=scope.window.ScormifyMediaSound;
assert(api.hasSound({slides:[{elements:[{type:'video'}]}]}));
assert(api.hasSound({slides:[{}, {elements:[{type:'video'}]}]}));
assert(api.hasSound({slides:[{}, {audio:[{src:'a.mp3'}]}]}));
assert(!api.hasSound({slides:[{elements:[{type:'text'}]}]}));
function video(){return {muted:false,volume:1,style:{},controls:false,count:0,pause(){},play(){this.count++;return Promise.resolve();}};}
(async()=>{
const v=video(),intentional=video();all=[v,intentional];
const sound=api.create({root:'#slide-container',showGate:()=>gates++});
sound.prepare(v,false);sound.prepare(intentional,true);sound.play(v);assert.equal(v.count,0);
sound.unlock();await Promise.resolve();assert.equal(v.count,1);assert.equal(v.muted,false);assert.equal(intentional.muted,true);
sound.setMuted(true);assert(v.muted);sound.setMuted(false);assert(!v.muted);assert(intentional.muted);
sound.setVolume(.25);assert.equal(v.volume,.25);
const later=video();all.push(later);sound.prepare(later,false);assert.equal(later.volume,.25);
v.play=function(){this.count++;return Promise.reject({name:'NotAllowedError'});};
sound.play(v);await Promise.resolve();assert.equal(gates,1);assert.equal(v.muted,false);assert(v.controls);assert.equal(v.count,2);
sound.setVolume(NaN);assert.equal(v.volume,.25);sound.setVolume(8);assert.equal(v.volume,1);
console.log('audible video guards passed');
})().catch(e=>{console.error(e);process.exit(1);});
'''
    result=subprocess.run([shutil.which('node') or 'C:/Program Files/nodejs/node.exe','-e',script,str(ASSETS/'media-sound.js')],capture_output=True,text=True)
    assert result.returncode==0,result.stderr

def test_scorm_resume_unlock_uses_only_current_slide_narration():
    player=(ASSETS/'player.js').read_text(encoding='utf-8')
    function=player[player.index('    function hideStartOverlay()'):player.index('    function setupGlobalAudio()')]
    script="""
const vm=require('vm'),assert=require('assert');let played=[],unlocks=0;
const scope={document:{getElementById:()=>({style:{}})},currentSlide:1,
course:{slides:[{audio:[{src:'first.mp3'}]},{audio:[{src:'resume.mp3'}]}]},
userHasInteracted:false,mediaSound:{unlock:()=>unlocks++},globalAudio:null,
playSlideAudio:a=>played.push(a[0].src)};
vm.runInNewContext(process.argv[1]+';hideStartOverlay();',scope);
assert.deepEqual(played,['resume.mp3']);assert.equal(unlocks,1);assert(scope.userHasInteracted);
"""
    result=subprocess.run([shutil.which('node') or 'C:/Program Files/nodejs/node.exe','-e',script,function],capture_output=True,text=True)
    assert result.returncode==0,result.stderr

def test_tutor_documents_reexport_without_new_media():
    topic=next(t for t in topics_for({'role':'superadmin'}) if t['id']=='export-video-sound')
    for text in ('MP4','slide atual','não muda automaticamente','reexporte','Página Única','não altera nota'):
        assert text in str(topic)
