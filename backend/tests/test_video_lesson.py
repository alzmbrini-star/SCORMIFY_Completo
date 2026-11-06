"""Offline only: narration planning, audio-backed timing and safe review fallback."""
import ast
import asyncio
import copy
import json
import math
import struct
import shutil
import subprocess
import sys
import types
import wave
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from services.video_lesson import (validate_lesson, plan_video_lesson, prepare_video_lessons,
    align_questions, resolve_lesson_timing, measure_silences, _provider_file)
from services.video_quiz import build_video_quiz, normalize_video_quiz


def lesson():
    question = dict(question='Qual conduta foi explicada?', options=['A', 'B', 'C', 'D'],
                    correctIndex=1, explanation='B corresponde à conduta explicada.')
    return dict(blocks=[
        dict(narration='Primeiro explicamos a conduta segura.', transition='Antes de continuar, escolha a conduta mais segura.', question=question),
        dict(narration='Continuando, confira a segunda conduta.', transition='Agora pense no próximo passo desta situação.', question=question)],
        continuation='Vamos retomar o conteúdo e concluir esta explicação.')


def subtitles():
    return ('1\n00:00:00,000 --> 00:00:03,000\nPrimeiro explicamos a conduta segura. Antes de continuar, escolha a conduta mais segura.\n\n'
            '2\n00:00:04,000 --> 00:00:07,000\nContinuando, confira a segunda conduta. Agora pense no próximo passo desta situação.\n\n'
            '3\n00:00:08,000 --> 00:00:10,000\nVamos retomar o conteúdo e concluir esta explicação.\n')


def pending():
    plan = validate_lesson(lesson())
    return dict(src='https://resource2.heygen.ai/avatar.webm', title='Aula', graded=True,
        timingReviewRequired=True, checkpoints=plan['checkpoints'], narrationScript=plan['narrationScript'])


def test_joint_plan_includes_exact_spoken_cues_without_guessed_times():
    plan = validate_lesson(lesson())
    assert len(plan['narrationScript']) <= 2000
    assert all(cp['at'] is None and not cp['relative'] for cp in plan['checkpoints'])
    assert all(cp['pauseCue'] in plan['narrationScript'] for cp in plan['checkpoints'])
    assert plan['narrationScript'].endswith(lesson()['continuation'])
    raw = lesson(); raw['blocks'][1]['transition'] = raw['blocks'][0]['transition']
    with pytest.raises(ValueError, match='única'): validate_lesson(raw)
    raw = lesson(); raw['blocks'][0]['narration'] *= 60
    with pytest.raises(ValueError): validate_lesson(raw)  # never slice a sentence


def test_malformed_ai_output_is_repaired_before_media(monkeypatch):
    calls = []
    class Chat:
        async def send_message(self, message):
            calls.append(message.text)
            return json.dumps({'blocks': []} if len(calls)==1 else lesson())
    monkeypatch.setitem(sys.modules, 'services.ai_agent', types.SimpleNamespace(
        _new_chat=lambda _:Chat(), _extract_json=json.loads,
        UserMessage=lambda **kwargs:types.SimpleNamespace(**kwargs)))
    result = asyncio.run(plan_video_lesson('Somente o conteúdo autorizado.'))
    assert len(calls)==2 and 'Corrija' in calls[1]
    assert 'Somente o conteúdo autorizado.' in calls[0]
    assert result['checkpoints'][0]['at'] is None


def test_failed_repair_is_bounded_and_actionable(monkeypatch):
    send = AsyncMock(return_value='{}')
    monkeypatch.setitem(sys.modules, 'services.ai_agent', types.SimpleNamespace(
        _new_chat=lambda _:types.SimpleNamespace(send_message=send), _extract_json=json.loads,
        UserMessage=lambda **kwargs:types.SimpleNamespace(**kwargs)))
    with pytest.raises(ValueError, match='antes da geração de mídia'):
        asyncio.run(plan_video_lesson('Conteúdo'))
    assert send.await_count==3


def test_validated_plan_cache_reuses_identical_input_not_changed_content(monkeypatch):
    from services import video_lesson
    planner = AsyncMock(return_value=validate_lesson(lesson()))
    monkeypatch.setattr(video_lesson, 'plan_video_lesson', planner)
    class Sessions:
        def __init__(self): self.cache={}
        async def find_one(self, *args): return {'videoLessonPlans':self.cache}
        async def update_one(self, query, update):
            for key,value in update['$set'].items(): self.cache[key.split('.')[1]]=value
    db=types.SimpleNamespace(agent_sessions=Sessions())
    slides=[dict(type='content', title='Válvulas', narrationScript='Feche a válvula antes de continuar.')]
    media={'0':dict(type='heygen',videoQuizEnabled=True)}
    async def run():
        await prepare_video_lessons(slides,media,'s',db)
        await prepare_video_lessons(slides,media,'s',db)
        slides[0]['narrationScript']+=' Conteúdo alterado.'
        await prepare_video_lessons(slides,media,'s',db)
    asyncio.run(run())
    assert planner.await_count==2
    tree=ast.parse((Path(__file__).resolve().parents[1]/'services/ai_agent.py').read_text(encoding='utf-8'))
    fn=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='generate_course_from_storyboard')
    source=ast.get_source_segment((Path(__file__).resolve().parents[1]/'services/ai_agent.py').read_text(encoding='utf-8'),fn)
    assert source.index('await prepare_video_lessons') < source.index('if ai_image_tasks:')
    assert 'await plan_video_questions' not in source
    assert '"script": clean_text if media.get(\'videoQuizEnabled\')' in source


def test_alignment_requires_real_silence_and_unique_complete_caption_cue():
    rows=align_questions(pending()['checkpoints'],subtitles(),[(2.9,4),(6.9,8)],10)
    assert 3 < rows[0]['at'] < 4 and 7 < rows[1]['at'] < 8
    assert all(cp['timingStatus']=='audio-aligned' and not cp['relative'] for cp in rows)
    with pytest.raises(ValueError,match='pausa de áudio'):
        align_questions(pending()['checkpoints'],subtitles(),[],10)
    with pytest.raises(ValueError,match='isola'):
        align_questions(pending()['checkpoints'],subtitles().replace('mais segura.','mais segura. Já estou falando novamente.'),[(2.9,4),(6.9,8)],10)
    with pytest.raises(ValueError):
        align_questions(pending()['checkpoints'],subtitles().replace('Antes de continuar,','Texto diferente,'),[(2.9,4),(6.9,8)],10)


def test_unavailable_timing_preserves_questions_video_and_grading_as_non_executable_draft():
    raw=pending()
    result=asyncio.run(resolve_lesson_timing(raw,raw['src'],{}))
    assert result['checkpoints']==raw['checkpoints'] and result['graded']
    config,html=build_video_quiz(result)
    assert config['timingReviewRequired'] and config['checkpoints'][0]['at'] is None
    assert 'narrationScript' in config and 'pauseCue' in config['checkpoints'][0]
    assert 'Tempos de pausa aguardam revisão' in html
    root=Path(__file__).resolve().parents[2]
    runtime=subprocess.run([shutil.which('node'),str(root/'tests/video-lesson-review.cjs')],
        input=html,text=True,encoding='utf-8',capture_output=True,cwd=root)
    assert runtime.returncode==0,runtime.stdout+runtime.stderr
    from services.assessment_assets import inline_assessment_assets
    with pytest.raises(ValueError,match='revise e confirme'):
        inline_assessment_assets(html,'unused')
    raw.pop('timingReviewRequired')
    with pytest.raises(ValueError,match='tempo inválido'): normalize_video_quiz(raw)


def test_successful_resolution_uses_audio_and_subtitles_not_duration_fractions(monkeypatch):
    from services import video_lesson
    fetched=[]
    async def fetch(url,destination=None,limit=0):
        fetched.append(url)
        return None if destination else subtitles()
    monkeypatch.setattr(video_lesson,'_provider_file',fetch)
    monkeypatch.setattr(video_lesson,'measure_silences',lambda *args:[(2.9,4),(6.9,8)])
    raw=pending()
    result=asyncio.run(resolve_lesson_timing(raw,raw['src'],dict(duration=10,subtitle_url='subtitles')))
    assert 'timingReviewRequired' not in result
    assert len(fetched)==2
    assert result['checkpoints'][0]['at'] != 10/3
    assert raw['checkpoints'][0]['at'] is None  # immutable original


@pytest.mark.parametrize('url',['http://resource2.heygen.ai/v.mp4','https://127.0.0.1/v.mp4',
    'https://heygen.ai.evil.invalid/x','https://evil.invalid/x','https://user:pass@heygen.ai/x'])
def test_sync_fetch_rejects_untrusted_urls_without_network(url):
    with pytest.raises(ValueError): asyncio.run(_provider_file(url))


def test_real_local_audio_silence_measurement(tmp_path):
    audio=tmp_path/'speech-fixture.wav'
    with wave.open(str(audio),'wb') as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(8000)
        out.writeframes(b''.join(struct.pack('<h',0 if 1 <= i/8000 < 2 else int(12000*math.sin(i*2*math.pi*440/8000))) for i in range(24000)))
    intervals=measure_silences(audio,3)
    assert any(abs(a-1)<.02 and abs(b-2)<.02 for a,b in intervals)


def test_player_pauses_without_waiting_for_delayed_timeupdate():
    root=Path(__file__).resolve().parents[2]
    document=build_video_quiz(dict(src='https://example.org/video.webm',checkpoints=[dict(
        at=3.2,question='Qual?',options=['A','B'],correctIndex=1,explanation='B.')]))[1]
    result=subprocess.run([shutil.which('node'),str(root/'tests/video-lesson-pause.cjs')],
        input=document,text=True,encoding='utf-8',capture_output=True,cwd=root)
    assert result.returncode==0,result.stdout+result.stderr


def test_metadata_lookup_is_read_only_and_never_changes_transparent_video(monkeypatch):
    import httpx
    from services.video_lesson import fetch_timing_metadata
    calls=[]
    class Client:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def get(self,url,headers):
            calls.append(url)
            return types.SimpleNamespace(status_code=200,json=lambda:{'data':{'duration':10,
                'subtitle_url':'https://files.heygen.ai/test.srt','video_url':'different.mp4'}})
    monkeypatch.setattr(httpx,'AsyncClient',Client)
    original={'video_url':'alpha.webm'}
    result=asyncio.run(fetch_timing_metadata('video_123',original,'https://api.heygen.com',{}))
    assert calls==['https://api.heygen.com/v3/videos/video_123']
    assert result['video_url']=='alpha.webm' and result['duration']==10
    assert original=={'video_url':'alpha.webm'}


def test_tutor_describes_entry_point_timing_review_and_no_guessed_pauses():
    from services.creator_guide import GUIDE
    text=' '.join(next(t for t in GUIDE if t['id']=='video-quiz')['steps'])
    for word in ('Mídia','silêncio medido','transição','revisão','créditos','HTML','SCORM'):
        assert word in text
