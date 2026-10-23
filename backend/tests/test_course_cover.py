import unittest
from unittest.mock import patch
from services.ai_agent import _build_title_slide,generate_course_from_storyboard

PALETTE={'accent':'#34d399','text':'#f4f4f5','mode':'dark','contentBg':'#121417'}


class CoverTests(unittest.IsolatedAsyncioTestCase):
    def test_course_title_wins_over_generic_slide_title_and_is_escaped(self):
        cover=_build_title_slide({'title':'Capa do Curso','elements':[{'content':'<p style="color:red">Pratique &amp; aprenda.</p>'}]},PALETTE,'Feedback & Liderança <img src=x>', ['Introdução'],'/image.png')
        text=cover[0]['htmlContent']
        self.assertIn('Feedback &amp; Liderança &lt;img src=x&gt;',text)
        self.assertNotIn('Capa do Curso',text)
        self.assertIn('Pratique &amp; aprenda.',text)
        self.assertEqual(cover[1]['src'],'/image.png')
        self.assertLessEqual(cover[0]['x']+cover[0]['width'],cover[1]['x'])

    def test_missing_image_has_safe_visual_not_broken_asset(self):
        cover=_build_title_slide({'title':'Capa do Curso'},PALETTE,'Título real',[])
        self.assertIn('<svg',cover[1]['htmlContent'])
        self.assertNotIn('src=',cover[1]['htmlContent'])
        for element in cover:
            self.assertLessEqual(element['y']+element['height'],820)
            self.assertLessEqual(element['x']+element['width'],1920)

    async def test_generator_reuses_course_image_and_moves_journey_without_paid_extra(self):
        storyboard={'slides':[{'type':'title','title':'Capa do Curso','moduleName':'Introdução','elements':[]},
            {'type':'content','title':'Como escutar','moduleName':'Prática','elements':[{'content':'<h2>Escuta</h2><p>Ouça com atenção e descreva o comportamento.</p>'}]}]}
        result=await generate_course_from_storyboard('test',storyboard,{'title':'Como Aplicar Feedback'},
            media_config={'1':{'type':'gallery_image','galleryImageUrl':'https://images.test/feedback.png','narration':{'enabled':True,'selectedScript':'Escuta ativa','voiceId':'voice-test'}}})
        self.assertEqual(len(result['slides']),3)
        self.assertEqual(result['slides'][0]['title'],'Como Aplicar Feedback')
        self.assertEqual(result['slides'][1]['title'],'Sua jornada de aprendizagem')
        self.assertEqual(result['slides'][2]['title'],'Como escutar')
        self.assertEqual(next(e for e in result['slides'][0]['elements'] if e.get('journeyRole')=='course_cover_image')['src'],'https://images.test/feedback.png')
        self.assertEqual(result['narrationPending'][0]['slideIndex'],2)
        self.assertEqual(result['narrationPending'][0]['slideId'],result['slides'][2]['id'])
        self.assertEqual(storyboard['slides'][0]['title'],'Capa do Curso')

    async def test_explicit_cover_image_wins_and_existing_journey_not_duplicated(self):
        result=await generate_course_from_storyboard('test',{'slides':[
            {'type':'title','title':'Capa do Curso','elements':[]},
            {'type':'content','title':'Sua jornada de aprendizagem','moduleName':'Introdução','elements':[]}]},
            {'title':'Curso'},media_config={'0':{'type':'gallery_image','galleryImageUrl':'https://images.test/cover.png'},'1':{'type':'none'}})
        self.assertEqual(len(result['slides']),2)
        self.assertEqual(next(e for e in result['slides'][0]['elements'] if e.get('journeyRole')=='course_cover_image')['src'],'https://images.test/cover.png')

    async def test_pending_kling_video_keeps_target_after_journey_insertion(self):
        result=await generate_course_from_storyboard('test',{'slides':[
            {'type':'title','title':'Capa do Curso','moduleName':'Abertura','elements':[]},
            {'type':'content','title':'Prática','moduleName':'Prática','elements':[{'content':'<p>Uma cena de aprendizagem.</p>'}]}]},
            {'title':'Curso'},media_config={'1':{'type':'kling','prompt':'Uma cena de aprendizagem'}})
        self.assertEqual(result['klingPending'][0]['slideIndex'],2)
        self.assertEqual(result['klingPending'][0]['slideId'],result['slides'][2]['id'])

    def test_journey_preserves_all_modules_and_escapes_names(self):
        from services.course_cover import build_journey
        modules=[f'Módulo {i} <prática>' for i in range(30)]
        text=build_journey(modules,PALETTE)['elements'][0]['htmlContent']
        self.assertEqual(text.count('<li '),30)
        self.assertIn('Módulo 29 &lt;prática&gt;',text)


if __name__=='__main__':unittest.main()
