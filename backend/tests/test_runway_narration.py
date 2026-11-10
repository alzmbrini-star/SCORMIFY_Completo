import os
from pathlib import Path
import re
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from services import runway_narration as narration
from services import runway_ai
from tests.test_runway import route


class NarrationTests(unittest.IsolatedAsyncioTestCase):
    def test_optional_and_strict_validation(self):
        self.assertIsNone(narration.validate(None))
        self.assertIsNone(narration.validate({'enabled':False}))
        valid=narration.validate({'enabled':True,'text':'Olá, Brasil!','voiceId':'voice123'})
        self.assertEqual(valid['language'],'pt-BR')
        self.assertEqual(valid['model'],'eleven_flash_v2_5')
        for value in (True, {'enabled':True,'text':'x'*601,'voiceId':'voice'},
                      {'enabled':True,'text':'Olá','voiceId':'../../secret'},
                      {'enabled':True,'text':'Olá','voiceId':'voice','language':'en'},
                      {'enabled':True,'text':'','voiceId':'voice'}):
            with self.subTest(value=value),self.assertRaises(ValueError):narration.validate(value)

    def test_brazilian_voice_detection_does_not_guess_from_voice_name(self):
        self.assertTrue(narration.voice_info({'labels':{'accent':'Brazilian'}})['brazilian'])
        self.assertTrue(narration.voice_info({'verified_languages':[{'locale':'pt-BR'}]})['brazilian'])
        self.assertFalse(narration.voice_info({'name':'Brazil','labels':{'accent':'American'}})['brazilian'])
        self.assertFalse(narration.voice_info({'labels':{'language':'portuguese','accent':'Portuguese'}})['brazilian'])

    async def test_paid_tts_uses_portuguese_and_no_automatic_retry(self):
        client=AsyncMock()
        client.get.return_value=SimpleNamespace(status_code=200,json=lambda:{'labels':{'accent':'brazilian'}})
        client.post.return_value=SimpleNamespace(status_code=200,content=b'mock-mp3')
        manager=AsyncMock();manager.__aenter__.return_value=client
        with patch.dict(os.environ,{'ELEVENLABS_API_KEY':'secret'}),patch.object(narration.httpx,'AsyncClient',return_value=manager):
            result=await narration.speech(narration.validate({'enabled':True,'text':'Olá, Brasil!','voiceId':'voice123'}))
        self.assertEqual(result,b'mock-mp3')
        client.post.assert_awaited_once()
        self.assertEqual(client.post.call_args.kwargs['json']['language_code'],'pt')
        self.assertEqual(client.post.call_args.kwargs['json']['model_id'],'eleven_flash_v2_5')
        self.assertNotIn('secret',str(client.post.call_args.kwargs['json']))

    async def test_non_brazilian_voice_requires_explicit_opt_in_before_paid_call(self):
        client=AsyncMock()
        client.get.return_value=SimpleNamespace(status_code=200,json=lambda:{'labels':{'accent':'american'}})
        manager=AsyncMock();manager.__aenter__.return_value=client
        with patch.dict(os.environ,{'ELEVENLABS_API_KEY':'secret'}),patch.object(narration.httpx,'AsyncClient',return_value=manager):
            with self.assertRaises(ValueError):
                await narration.speech(narration.validate({'enabled':True,'text':'Olá!','voiceId':'voice123'}))
        client.post.assert_not_awaited()

    def test_no_speech_truncation_or_acceleration_in_composition_command(self):
        command,total=narration.composition_args('ffmpeg','input.mp4','voice.mp3','output.mp4',5,12)
        self.assertAlmostEqual(total,12.25)
        self.assertIn('tpad=stop_mode=clone:stop_duration=7.250000',command)
        self.assertIn('apad',command)
        self.assertNotIn('-shortest',command)
        self.assertNotIn('atempo',' '.join(command))
        command,total=narration.composition_args('ffmpeg','input.mp4','voice.mp3','output.mp4',10,3)
        self.assertEqual(total,10)
        self.assertIn('copy',command)
        self.assertNotIn('-vf',command)
        with self.assertRaises(ValueError):narration.composition_args('f','v','a','o',5,95)

    async def test_permission_and_missing_configuration_stop_before_any_paid_video(self):
        class Request:
            async def json(self):return {'prompt':'Cena','narration':{'enabled':True,'text':'Olá!','voiceId':'voice123'}}
        provider=SimpleNamespace(configured=lambda:True,build_payload=lambda _:None,validate_music=runway_ai.validate_music,submit=AsyncMock())
        fn=route('generate',can_edit=lambda _:None,runway_ai=provider,narration_allowed=lambda _:False)
        with self.assertRaises(Exception) as exc:await fn(Request(),{})
        self.assertEqual(exc.exception.status_code,403)
        provider.submit.assert_not_awaited()
        fn=route('generate',can_edit=lambda _:None,runway_ai=provider,narration_allowed=lambda _:True)
        with patch.object(narration,'available',return_value=False):
            with self.assertRaises(Exception) as exc:await fn(Request(),{})
        self.assertEqual(exc.exception.status_code,503)
        provider.submit.assert_not_awaited()

    async def test_voice_failure_never_submits_a_video(self):
        collection=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)))
        provider=SimpleNamespace(configured=lambda:True,build_payload=lambda _:None,validate_music=runway_ai.validate_music,submit=AsyncMock())
        class Request:
            async def json(self):return {'projectId':'p1','slideId':'s1','prompt':'Cena','narration':{'enabled':True,'text':'Olá!','voiceId':'voice123'}}
        fn=route('generate',can_edit=lambda _:None,db=SimpleNamespace(projects=collection),runway_ai=provider,
                 narration_allowed=lambda _:True,load_authorized_project=AsyncMock(return_value={'course':{'slides':[{'id':'s1'}]}}),
                 placeholder=route('placeholder'),prepare_audio=AsyncMock(side_effect=ValueError('Falha de voz')))
        with patch.object(narration,'available',return_value=True):result=await fn(Request(),{})
        self.assertEqual(result['status'],'failed')
        provider.submit.assert_not_awaited()

    async def test_voice_is_prepared_before_video_submission(self):
        collection=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)))
        order=[]
        async def prepare(*args):order.append('audio')
        async def submit(*args):order.append('video');return 'task'
        provider=SimpleNamespace(configured=lambda:True,build_payload=lambda _:None,validate_music=runway_ai.validate_music,submit=submit)
        class Request:
            async def json(self):return {'projectId':'p1','slideId':'s1','prompt':'Cena','narration':{'enabled':True,'text':'Olá!','voiceId':'voice123'}}
        fn=route('generate',can_edit=lambda _:None,db=SimpleNamespace(projects=collection),runway_ai=provider,
                 narration_allowed=lambda _:True,load_authorized_project=AsyncMock(return_value={'course':{'slides':[{'id':'s1'}]}}),
                 placeholder=route('placeholder'),prepare_audio=prepare)
        with patch.object(narration,'available',return_value=True):result=await fn(Request(),{})
        self.assertEqual(order,['audio','video'])
        self.assertEqual(result['taskId'],'task')

    async def test_polling_restores_persistent_audio_without_synthesizing_again(self):
        collection=SimpleNamespace(update_one=AsyncMock(),find_one=AsyncMock(return_value={'course':{'slides':[]}}))
        speech=AsyncMock()
        async def download(url,path):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'original-video')
        async def compose(source,audio,destination):
            self.assertEqual(audio.read_bytes(),b'persisted-audio');destination.write_bytes(b'narrated');return 12.25
        with tempfile.TemporaryDirectory() as directory:
            fn=route('save_result',db=SimpleNamespace(projects=collection),PROJECTS_DIR=directory,Path=Path,
                     runway_ai=SimpleNamespace(download=download),store_asset_async=AsyncMock(return_value=True),
                     retrieve_asset_async=AsyncMock(return_value=(b'persisted-audio','audio/mpeg')),
                     runway_narration=SimpleNamespace(compose=compose,speech=speech))
            await fn('p1',{'id':'job','narration':{'text':'Olá!'}},'https://example.com/video.mp4')
        speech.assert_not_awaited()
        final=collection.update_one.call_args.args[1]['$set']
        self.assertEqual(final['runwayPending.$.durationActual'],12.25)
        self.assertEqual(final['runwayPending.$.narrationStatus'],'completed')


class ActualCompositionTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_ffmpeg_mux_preserves_entire_longer_audio(self):
        binary=Path(__file__).resolve().parents[1]/'.venv/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe'
        if not binary.is_file():
            import shutil
            found=shutil.which('ffmpeg')
            if not found:self.skipTest('FFmpeg indisponível neste ambiente de teste')
            binary=Path(found)
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.mp4';audio=Path(directory)/'audio.mp3';output=Path(directory)/'result.mp4'
            await narration.run_media([str(binary),'-y','-v','error','-f','lavfi','-i','color=c=blue:s=320x180:r=24','-t','1','-c:v','libx264',str(source)])
            await narration.run_media([str(binary),'-y','-v','error','-f','lavfi','-i','sine=frequency=440','-t','2.4',str(audio)])
            original=source.read_bytes()
            with patch.object(narration,'media_tools',return_value=(str(binary),None)),patch.object(narration,'duration',AsyncMock(side_effect=[1,2.4])):
                length=await narration.compose(source,audio,output)
            self.assertAlmostEqual(length,2.65)
            self.assertEqual(source.read_bytes(),original)
            # Inspect/decode using the actual local FFmpeg, with no API calls.
            result=await asyncio_run_inspect(binary,output)
            self.assertRegex(result,r'Audio: aac')
            duration_match=re.search(r'Duration: 00:00:(\d+\.\d+)',result)
            self.assertIsNotNone(duration_match)
            self.assertGreaterEqual(float(duration_match.group(1)),2.6)
            self.assertFalse(output.with_name('result_composing.mp4').exists())


async def asyncio_run_inspect(binary,path):
    import asyncio
    result=await asyncio.to_thread(subprocess.run,[str(binary),'-i',str(path),'-f','null','-'],capture_output=True,timeout=30)
    if result.returncode:raise AssertionError(result.stderr.decode(errors='replace'))
    return result.stderr.decode(errors='replace')
