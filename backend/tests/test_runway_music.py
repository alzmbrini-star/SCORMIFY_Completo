import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from services import runway_ai, runway_narration as narration
from tests.test_runway import route
from tests.test_runway_narration import asyncio_run_inspect


class MusicTests(unittest.IsolatedAsyncioTestCase):
    def test_strict_optional_configuration(self):
        self.assertIsNone(runway_ai.validate_music(None))
        self.assertIsNone(runway_ai.validate_music({'enabled': False}))
        value = runway_ai.validate_music({'enabled': True, 'prompt': 'Piano suave', 'volume': 12})
        self.assertTrue(value['instrumental'])
        for volume in (-1, 51, True, float('nan'), '20'):
            with self.subTest(volume=volume), self.assertRaises(ValueError):
                runway_ai.validate_music({'enabled': True, 'prompt': 'Piano', 'volume': volume})

    async def test_music_paid_post_is_instrumental_and_never_retried(self):
        identifier = '17f20503-6c24-4c16-946b-35dbbce2af2f'
        with patch.object(runway_ai, 'request', AsyncMock(return_value={'id': identifier})) as request:
            self.assertEqual(await runway_ai.submit_music({'prompt': 'Piano suave'}, 10), identifier)
            request.assert_awaited_once_with('POST', 'text_to_music', {'model': 'eleven_music_v2_5',
                'promptText': 'Piano suave', 'instrumental': True, 'duration': 10})
        with patch.object(runway_ai, 'request', AsyncMock(side_effect=TimeoutError)) as request:
            with self.assertRaises(TimeoutError):
                await runway_ai.submit_music({'prompt': 'Piano'}, 5)
            request.assert_awaited_once()

    async def test_music_submission_failure_does_not_pay_for_video(self):
        provider = SimpleNamespace(configured=lambda: True, build_payload=lambda _: None,
            validate_music=runway_ai.validate_music, submit_music=AsyncMock(side_effect=TimeoutError), submit=AsyncMock())
        collection = SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)),
            find_one=AsyncMock(return_value={'runwayPending': []}))
        class Request:
            async def json(self):
                return {'prompt':'Cena', 'projectId':'p', 'slideId':'s', 'music':{'enabled':True, 'prompt':'Piano'}}
        fn = route('generate', runway_ai=provider, can_edit=lambda _:None, db=SimpleNamespace(projects=collection),
            load_authorized_project=AsyncMock(return_value={'course':{'slides':[{'id':'s'}]}}), placeholder=route('placeholder'))
        with patch.object(narration, 'media_tools', return_value=('ffmpeg', 'ffprobe')):
            result = await fn(Request(), {})
        self.assertEqual(result['status'], 'unknown')
        provider.submit_music.assert_awaited_once()
        provider.submit.assert_not_awaited()

    async def test_actual_ffmpeg_music_only_and_ducked_voice(self):
        binary = Path(__file__).resolve().parents[1]/'.venv/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe'
        if not binary.is_file():
            import shutil
            found = shutil.which('ffmpeg')
            if not found: self.skipTest('FFmpeg indisponível')
            binary = Path(found)
        with tempfile.TemporaryDirectory() as directory:
            source, voice, music = [Path(directory)/p for p in ('v.mp4','voice.mp3','music.mp3')]
            await narration.run_media([str(binary),'-y','-v','error','-f','lavfi','-i','color=c=blue:s=320x180:r=24','-t','1','-c:v','libx264',str(source)])
            for path, frequency in ((voice,440),(music,220)):
                await narration.run_media([str(binary),'-y','-v','error','-f','lavfi','-i',f'sine=frequency={frequency}','-t','2',str(path)])
            for audio in (None, voice):
                output = Path(directory)/('mixed.mp4' if audio else 'music_only.mp4')
                values = [1,2] if audio else [1]
                with patch.object(narration,'media_tools',return_value=(str(binary),None)), patch.object(narration,'duration',AsyncMock(side_effect=values)):
                    await narration.compose(source,audio,output,music=music,volume=15)
                self.assertRegex(await asyncio_run_inspect(binary,output), r'Audio: aac')

